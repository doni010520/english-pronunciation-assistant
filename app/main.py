import asyncio
import json as json_mod
import logging
import os
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Header, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
from openai import AsyncOpenAI
from supabase import acreate_client

from app.config import get_settings
from app.services import (
    UazapiService,
    AzureSpeechService,
    BrazilianErrorAnalyzer,
    extract_phone_from_jid,
    SessionManager,
)
from app.services.rag import RAGService
from app.services.agent import ConversationalAgent
from app.services.feedback_generator import FeedbackGenerator
from app.services.sdr_agent import SDRAgent
import app.services.session_manager as sm


# ============================================
# LOGGING
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================
# SERVIÇOS GLOBAIS
# ============================================

uazapi_service: UazapiService = None
uazapi_sdr_service: UazapiService = None
azure_service: AzureSpeechService = None
error_analyzer: BrazilianErrorAnalyzer = None
feedback_generator: FeedbackGenerator = None
agent: ConversationalAgent = None
sdr_agent: SDRAgent = None
rag_service: RAGService = None
openai_client: AsyncOpenAI = None
redis_client: aioredis.Redis = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global uazapi_service, uazapi_sdr_service, azure_service, error_analyzer, feedback_generator, agent, sdr_agent, rag_service, openai_client, redis_client

    logger.info("Inicializando servicos...")
    settings = get_settings()

    # Supabase
    supabase_client = await acreate_client(settings.supabase_url, settings.supabase_key)
    sm.session_manager = SessionManager(supabase_client)

    # OpenAI client compartilhado
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Redis
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=False)
    logger.info("Redis conectado!")

    # Serviços existentes
    uazapi_service = UazapiService()
    azure_service = AzureSpeechService()
    error_analyzer = BrazilianErrorAnalyzer()
    feedback_generator = FeedbackGenerator()

    # Novos serviços
    rag_service = RAGService(supabase_client, openai_client)
    agent = ConversationalAgent(supabase_client, openai_client, rag_service, sm.session_manager, uazapi_service)

    # SDR Agent (separate WhatsApp number for sales)
    if settings.uazapi_sdr_base_url and settings.uazapi_sdr_token:
        uazapi_sdr_service = UazapiService(
            base_url=settings.uazapi_sdr_base_url,
            token=settings.uazapi_sdr_token,
        )
        sdr_agent = SDRAgent(supabase_client, openai_client, uazapi_sdr_service)
        logger.info("SDR Agent inicializado!")
    else:
        logger.warning("SDR Agent desabilitado: UAZAPI_SDR_BASE_URL ou UAZAPI_SDR_TOKEN não configurados.")

    logger.info("Servicos inicializados!")
    yield
    logger.info("Encerrando aplicacao...")
    if redis_client:
        await redis_client.close()


# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(
    title="English Pronunciation Assistant",
    description="Assistente de pronúncia de inglês para brasileiros via WhatsApp",
    version="2.0.0",
    lifespan=lifespan,
)


# ============================================
# AUTH HELPER
# ============================================

async def verify_admin(authorization: str = Header(None)):
    settings = get_settings()
    expected = f"Bearer {settings.admin_token}"
    if not authorization or authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ============================================
# MESSAGE BUFFER (Redis + debounce)
# ============================================

BUFFER_DELAY_SECONDS = 10
BUFFER_KEY = "buf:{phone}"        # lista de mensagens serializadas
LAST_MSG_KEY = "last:{phone}"     # id da última mensagem (para debounce)
BUFFER_TTL = 120                  # expira em 2 min (safety net)


import base64 as b64mod


def _serialize_msg(msg: dict) -> bytes:
    """Serializa uma mensagem para armazenar no Redis."""
    # Audio/image bytes vão como base64 dentro do JSON
    data = dict(msg)
    if data.get("audio_bytes"):
        data["audio_bytes"] = b64mod.b64encode(data["audio_bytes"]).decode("ascii")
    if data.get("image_bytes"):
        data["image_bytes"] = b64mod.b64encode(data["image_bytes"]).decode("ascii")
    return json_mod.dumps(data).encode("utf-8")


def _deserialize_msg(raw: bytes) -> dict:
    """Deserializa uma mensagem do Redis."""
    data = json_mod.loads(raw)
    if data.get("audio_bytes"):
        data["audio_bytes"] = b64mod.b64decode(data["audio_bytes"])
    if data.get("image_bytes"):
        data["image_bytes"] = b64mod.b64decode(data["image_bytes"])
    return data


async def _buffer_message(phone: str, msg: dict, push_name: str):
    """Salva mensagem no Redis, marca como última, e agenda processamento."""
    buf_key = BUFFER_KEY.format(phone=phone)
    last_key = LAST_MSG_KEY.format(phone=phone)

    # ID único para esta mensagem
    msg_uid = uuid.uuid4().hex

    # Salvar push_name na mensagem
    msg["push_name"] = push_name

    # Adicionar ao buffer e marcar como última
    pipe = redis_client.pipeline()
    pipe.rpush(buf_key, _serialize_msg(msg))
    pipe.set(last_key, msg_uid, ex=BUFFER_TTL)
    pipe.expire(buf_key, BUFFER_TTL)
    await pipe.execute()

    # Esperar e comparar — se ainda for a última, processar
    asyncio.create_task(_wait_and_process(phone, msg_uid))


async def _wait_and_process(phone: str, my_uid: str):
    """Espera o delay, verifica se é a última msg, e processa."""
    await asyncio.sleep(BUFFER_DELAY_SECONDS)

    last_key = LAST_MSG_KEY.format(phone=phone)
    current_uid = await redis_client.get(last_key)

    # Se outra mensagem chegou depois, não somos os últimos — sair
    if current_uid != my_uid.encode("utf-8"):
        return

    # Somos a última mensagem — flush
    await _flush_buffer(phone)


async def _flush_buffer(phone: str):
    """Coleta todas as mensagens do Redis e processa."""
    buf_key = BUFFER_KEY.format(phone=phone)
    last_key = LAST_MSG_KEY.format(phone=phone)

    # Pegar todas as mensagens e limpar atomicamente
    pipe = redis_client.pipeline()
    pipe.lrange(buf_key, 0, -1)
    pipe.delete(buf_key)
    pipe.delete(last_key)
    results = await pipe.execute()

    raw_messages = results[0]
    if not raw_messages:
        return

    messages = [_deserialize_msg(raw) for raw in raw_messages]
    push_name = messages[-1].get("push_name", "Aluno")

    logger.info(f"Buffer flush: {phone}, {len(messages)} mensagem(ns)")

    # --- Comando "limpar dados": apaga histórico do número ---
    for msg in messages:
        if msg["msg_type"] == "text" and msg.get("text", "").strip().lower() in ("limpar dados", "limpar conversa", "reset"):
            try:
                await agent._db.table("conversation_history").delete().eq("phone", phone).execute()
                logger.info(f"Histórico limpo para {phone}")
            except Exception as e:
                logger.warning(f"Erro ao limpar histórico: {e}")
            await uazapi_service.send_text(phone, "Conversa limpa! Pode começar de novo. 👋")
            return

    try:
        await uazapi_service.send_presence(phone, "composing")

        text_parts = []
        pronunciation_notes = []
        has_audio = False
        last_message_id = None

        for msg in messages:
            if msg.get("message_id"):
                last_message_id = msg["message_id"]

            if msg["msg_type"] == "text" and msg.get("text"):
                text_parts.append(msg["text"])

            elif msg["msg_type"] == "audio" and msg.get("audio_bytes"):
                has_audio = True
                transcription = await _transcribe_audio(msg["audio_bytes"], msg["audio_mimetype"])
                if transcription:
                    text_parts.append(transcription)

                    # Avaliação de pronúncia nos bastidores
                    try:
                        fmt = "ogg" if "ogg" in msg["audio_mimetype"] else "mp3" if "mp3" in msg["audio_mimetype"] else "ogg"
                        # Detectar idioma (exemplo simples)
                        user_language = await sm.session_manager.get_user_language(phone)
                        
                        pron_result = await azure_service.assess_pronunciation(
                            audio_bytes=msg["audio_bytes"],
                            reference_text=transcription,
                            audio_format=fmt,
                            language=user_language,
                        )
                        analysis = error_analyzer.analyze(pron_result)
                        gross_errors = [
                            e for e in (analysis.brazilian_errors or [])
                            if e.accuracy < 40
                        ]
                        if gross_errors:
                            errors_text = ", ".join(
                                f"'{e.word}' (score {e.accuracy:.0f}/100)"
                                for e in gross_errors[:3]
                            )
                            pronunciation_notes.append(
                                f"Gross pronunciation errors: {errors_text}."
                            )
                        try:
                            await sm.session_manager.update_session(phone, pron_result.overall_score)
                        except Exception:
                            pass
                    except Exception as e:
                        logger.warning(f"Pronúncia falhou: {e}")

            elif msg["msg_type"] == "image":
                try:
                    extracted = await feedback_generator.extract_text_from_image(
                        msg["image_bytes"], msg["image_mimetype"]
                    )
                    if extracted:
                        text_parts.append(f'[Sent an image with this English text: "{extracted}"]')
                        await sm.session_manager.create_session(phone, extracted)
                    else:
                        text_parts.append("[Sent an image but no English text was found in it]")
                except Exception as e:
                    logger.warning(f"Imagem falhou: {e}")

        if not text_parts:
            return

        # Montar mensagem combinada
        combined = "\n".join(text_parts)
        if pronunciation_notes:
            combined += "\n[PRONUNCIATION DATA — invisible to student, for your reference only: "
            combined += " ".join(pronunciation_notes)
            combined += " If relevant, correct inline while conversing. Do NOT list errors or mention scores.]"

        logger.info(f"Processando: {combined[:100]}...")

        reply = await agent.process_message(phone, combined, push_name)

        if has_audio:
            await _send_voice_parts(phone, reply)
        else:
            await _send_text_parts(phone, reply, reply_to=last_message_id)

        logger.info(f"Resposta enviada para {phone}")

    except Exception as e:
        logger.error(f"Erro ao processar buffer: {e}", exc_info=True)
        try:
            await uazapi_service.send_text(phone, "Desculpe, tive um problema. Tente novamente!")
        except Exception:
            pass


# ============================================
# PROCESSAMENTO DE MENSAGENS
# ============================================

async def _send_voice_reply(phone: str, text: str, reply_to: str = None):
    """Gera áudio TTS e envia como mensagem de voz."""
    try:
        audio_bytes = await feedback_generator.text_to_speech(text)
        import base64
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        await uazapi_service.send_voice(phone, audio_b64, reply_to=reply_to)
    except Exception as e:
        logger.warning(f"Falha ao enviar áudio TTS: {e}")


async def _send_voice_parts(phone: str, text: str):
    """Divide a resposta em partes e envia cada uma como áudio separado."""
    import re
    # Dividir por parágrafos ou por \n\n
    parts = [p.strip() for p in re.split(r'\n\n+', text) if p.strip()]
    if not parts:
        parts = [text]

    for part in parts:
        # Limpar markdown/emojis para TTS
        clean = re.sub(r'[*_~`#]', '', part)
        clean = re.sub(r'[\U0001f600-\U0001f9ff]', '', clean)  # emojis
        clean = clean.strip()
        if clean:
            await uazapi_service.send_presence(phone, "recording")
            await _send_voice_reply(phone, clean)
async def _send_text_parts(phone: str, text: str, reply_to: str = None):
    """Divide a resposta em partes e envia cada uma como mensagem separada."""
    import re
    
    # Remove asteriscos (markdown bold)
    clean = text.replace('*', '')
    
    # Quebra após pontuação + emoji opcional, ou após emoji seguido de espaço e letra maiúscula
    parts = re.split(r'(?<=[?!.])(\s*[\U0001F300-\U0001F9FF]*)?\s+(?=[A-ZÀ-Ú])', clean)
    parts = [p.strip() for p in parts if p and p.strip()]
        
    # Se não dividiu nada, envia o original
    if not parts:
        parts = [clean.strip()]
    
    # Se tem só 1 parte, envia direto sem delay
    if len(parts) == 1:
        await uazapi_service.send_text(phone, parts[0], reply_to=reply_to)
        return
    
    # Envia cada parte com delay de 3 segundos entre elas
    for i, part in enumerate(parts):
        # Só o primeiro responde à mensagem original
        rid = reply_to if i == 0 else None
        await uazapi_service.send_text(phone, part, reply_to=rid)
        
        # Delay entre mensagens (não espera após a última)
        if i < len(parts) - 1:
            await uazapi_service.send_presence(phone, "composing")
            await asyncio.sleep(2)

async def _transcribe_audio(audio_bytes: bytes, mimetype: str) -> str:
    """Transcreve áudio usando OpenAI Whisper."""
    import io
    ext = "ogg" if "ogg" in mimetype else "mp3" if "mp3" in mimetype else "ogg"
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = f"audio.{ext}"
    result = await openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
    )
    return result.text.strip()



# (Processamento individual removido — tudo passa pelo buffer acima)


# ============================================
# WEBHOOK UAZAPI
# ============================================

@app.post("/webhook/uazapi")
async def webhook_uazapi(request: Request):
    """Webhook que recebe mensagens da Uazapi. Usa buffer com debounce."""
    try:
        payload = await request.json()

        event = payload.get("EventType", "")
        if event != "messages":
            return JSONResponse({"status": "ignored", "reason": f"event: {event}"})

        message = payload.get("message")
        if not message:
            return JSONResponse({"status": "ignored", "reason": "no message"})

        if message.get("fromMe", False) or message.get("wasSentByApi", False):
            return JSONResponse({"status": "ignored", "reason": "from me"})

        chatid = message.get("chatid", "")
        if not chatid:
            return JSONResponse({"status": "ignored", "reason": "no chatid"})

        phone = extract_phone_from_jid(chatid)
        message_id = message.get("messageid", "")
        full_message_id = message.get("id", message_id)
        push_name = message.get("senderName", "Aluno")
        msg_type = message.get("messageType", "")

        logger.info(f"{phone} ({push_name}) tipo: {msg_type}")
        logger.info(f"PAYLOAD COMPLETO: {payload}")

        # Salvar push_name
        try:
            await sm.session_manager.save_push_name(phone, push_name)
        except Exception:
            pass

        # Texto → buffer
        if msg_type in ("Conversation", "ExtendedTextMessage"):
            text = message.get("text", "")
            if text:
                await _buffer_message(
                    phone,
                    {"msg_type": "text", "text": text, "message_id": message_id},
                    push_name,
                )
                return JSONResponse({"status": "buffered", "type": "text"})

        # Áudio → baixar agora (webhook pode expirar), colocar no buffer
        if msg_type == "AudioMessage":
            try:
                audio_bytes, mimetype = await uazapi_service.download_audio(full_message_id)
                await _buffer_message(
                    phone,
                    {
                        "msg_type": "audio",
                        "message_id": full_message_id,
                        "audio_bytes": audio_bytes,
                        "audio_mimetype": mimetype,
                    },
                    push_name,
                )
                return JSONResponse({"status": "buffered", "type": "audio"})
            except Exception as e:
                logger.error(f"Falha ao baixar áudio: {e}")
                return JSONResponse({"status": "error", "message": str(e)})

        # Imagem → baixar agora, colocar no buffer
        if msg_type == "ImageMessage":
            try:
                image_bytes, mimetype = await uazapi_service.download_image(full_message_id)
                await _buffer_message(
                    phone,
                    {
                        "msg_type": "image",
                        "message_id": full_message_id,
                        "image_bytes": image_bytes,
                        "image_mimetype": mimetype,
                    },
                    push_name,
                )
                return JSONResponse({"status": "buffered", "type": "image"})
            except Exception as e:
                logger.error(f"Falha ao baixar imagem: {e}")
                return JSONResponse({"status": "error", "message": str(e)})

        # PollUpdateMessage → resposta de enquete
        if msg_type == "PollUpdateMessage":
            vote = message.get("vote", "")
            quoted_id = message.get("quoted", "")  # ID da enquete original
            
            if vote and agent:
                try:
                    feedback = await agent.process_quiz_answer(
                        phone=phone,
                        vote=vote,
                        quiz_message_id=quoted_id,
                        push_name=push_name,
                    )
                    
                    if feedback:
                        await uazapi_service.send_text(phone, feedback)
                        logger.info(f"Quiz feedback enviado para {phone}")
                        return JSONResponse({"status": "ok", "type": "poll_answer"})
                    
                except Exception as e:
                    logger.error(f"Erro ao processar resposta de enquete: {e}", exc_info=True)
            
            return JSONResponse({"status": "ok", "type": "poll_update"})

        logger.info(f"Tipo não suportado: {msg_type}")
        return JSONResponse({"status": "ignored", "reason": f"unsupported: {msg_type}"})

    except Exception as e:
        logger.error(f"Erro no webhook: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)})


# ============================================
# WEBHOOK SDR (WhatsApp sales number)
# ============================================

@app.post("/webhook/sdr")
async def webhook_sdr(request: Request):
    """Webhook que recebe mensagens do número SDR (vendas)."""
    try:
        if not sdr_agent or not uazapi_sdr_service:
            return JSONResponse({"status": "error", "message": "SDR agent not configured"}, status_code=503)

        payload = await request.json()

        event = payload.get("EventType", "")
        if event != "messages":
            return JSONResponse({"status": "ignored", "reason": f"event: {event}"})

        message = payload.get("message")
        if not message:
            return JSONResponse({"status": "ignored", "reason": "no message"})

        if message.get("fromMe", False) or message.get("wasSentByApi", False):
            return JSONResponse({"status": "ignored", "reason": "from me"})

        chatid = message.get("chatid", "")
        if not chatid:
            return JSONResponse({"status": "ignored", "reason": "no chatid"})

        phone = extract_phone_from_jid(chatid)
        push_name = message.get("senderName", "Lead")
        msg_type = message.get("messageType", "")

        logger.info(f"[SDR] {phone} ({push_name}) tipo: {msg_type}")

        # Handle text messages only (for now)
        if msg_type not in ("Conversation", "ExtendedTextMessage"):
            logger.info(f"[SDR] Tipo não suportado: {msg_type}")
            return JSONResponse({"status": "ignored", "reason": f"unsupported: {msg_type}"})

        text = message.get("text", "")
        if not text:
            return JSONResponse({"status": "ignored", "reason": "empty text"})

        # Send composing presence
        await uazapi_sdr_service.send_presence(phone, "composing")

        # Process with SDR agent
        reply = await sdr_agent.process_message(phone, text, push_name)

        # Send reply
        message_id = message.get("messageid", "")
        await uazapi_sdr_service.send_text(phone, reply, reply_to=message_id)

        logger.info(f"[SDR] Resposta enviada para {phone}")
        return JSONResponse({"status": "ok", "type": "text"})

    except Exception as e:
        logger.error(f"[SDR] Erro no webhook: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)})


# ============================================
# SDR LEADS API
# ============================================

@app.get("/api/sdr/leads")
async def list_sdr_leads(authorization: str = Header(None)):
    """Lista todos os leads do SDR (protegido por admin token)."""
    await verify_admin(authorization)

    if not sdr_agent:
        raise HTTPException(status_code=503, detail="SDR agent not configured")

    result = await sdr_agent._db.table("sdr_leads").select("*").order("created_at", desc=True).execute()
    return result.data


# ============================================
# LEAD CAPTURE (Landing Page Form)
# ============================================

@app.post("/api/leads")
async def capture_lead(request: Request):
    """Recebe lead do formulario da landing page, salva no banco e dispara SDR."""
    data = await request.json()

    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()
    lead_type = data.get("type", "other")
    school_name = data.get("school_name", "").strip()
    student_count = data.get("student_count")
    main_pain = data.get("main_pain", "")

    if not name or not phone:
        raise HTTPException(status_code=400, detail="Nome e telefone sao obrigatorios")

    # Normalizar telefone (garantir formato brasileiro com 55)
    phone = phone.lstrip("+")
    if not phone.startswith("55"):
        phone = "55" + phone

    # Salvar lead no banco
    lead_data = {
        "phone": phone,
        "name": name,
        "type": lead_type,
        "school_name": school_name or None,
        "student_count": student_count,
        "main_pain": main_pain or None,
        "source": "landing_page",
        "status": "new",
    }

    try:
        from supabase import PostgrestAPIError
    except ImportError:
        PostgrestAPIError = Exception

    try:
        await sdr_agent._db.table("sdr_leads").upsert(lead_data, on_conflict="phone").execute()
    except Exception as e:
        logger.error(f"Erro ao salvar lead: {e}")

    # Disparar primeira mensagem do SDR via WhatsApp
    if sdr_agent and uazapi_sdr_service:
        try:
            # Montar contexto do lead para o SDR
            pain_map = {
                "retention": "alunos desistindo",
                "engagement": "pouca pratica entre as aulas",
                "competition": "concorrencia com apps",
                "scaling": "dificuldade de escalar",
                "acquisition": "captacao de novos alunos",
            }
            pain_text = pain_map.get(main_pain, main_pain or "nao informado")
            type_map = {
                "school_owner": "dono(a) de escola",
                "coordinator": "coordenador(a)",
                "independent_teacher": "professor(a) autonomo(a)",
                "other": "outro",
            }
            type_text = type_map.get(lead_type, lead_type)

            context = (
                f"[LEAD DO FORMULARIO] Nome: {name}. "
                f"Tipo: {type_text}. "
                f"Escola: {school_name or 'nao informou'}. "
                f"Alunos: {student_count or 'nao informou'}. "
                f"Maior desafio: {pain_text}. "
                f"Essa pessoa acabou de preencher o formulario no site pedindo trial gratis. "
                f"Inicie a conversa de forma personalizada usando essas informacoes."
            )

            # Gerar primeira mensagem do SDR com contexto
            reply = await sdr_agent.process_message(phone, context, push_name=name)

            # Enviar para o WhatsApp do lead
            await uazapi_sdr_service.send_text(phone, reply)
            logger.info(f"SDR primeira mensagem enviada para {phone}")

        except Exception as e:
            logger.error(f"Erro ao disparar SDR para lead {phone}: {e}")

    return {"status": "ok", "message": "Lead capturado com sucesso"}


# ============================================
# ADMIN PANEL
# ============================================

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """Serve o painel admin."""
    html_path = STATIC_DIR / "admin.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Admin panel not found")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# --- Settings ---

@app.get("/api/admin/settings")
async def get_agent_settings(authorization: str = Header(None)):
    await verify_admin(authorization)
    result = await rag_service._db.table("agent_settings").select("*").eq("id", 1).execute()
    return result.data[0] if result.data else {}


@app.put("/api/admin/settings")
async def update_agent_settings(request: Request, authorization: str = Header(None)):
    await verify_admin(authorization)
    data = await request.json()
    allowed = {"agent_name", "personality", "system_prompt", "language"}
    update_data = {k: v for k, v in data.items() if k in allowed}
    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields")
    result = await rag_service._db.table("agent_settings").update(update_data).eq("id", 1).execute()
    # Invalidar cache do agente
    agent._settings_cache = None
    return result.data[0] if result.data else {}


# --- Documents ---

@app.get("/api/admin/documents")
async def list_documents(authorization: str = Header(None)):
    await verify_admin(authorization)
    docs = await rag_service.list_documents()
    return docs


@app.post("/api/admin/documents")
async def upload_document(file: UploadFile = File(...), authorization: str = Header(None)):
    await verify_admin(authorization)
    content = await file.read()
    filename = file.filename or "unknown"
    # Determinar tipo
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    doc = await rag_service.upload_document(filename, content, ext)
    return doc


@app.delete("/api/admin/documents/{document_id}")
async def delete_document(document_id: str, authorization: str = Header(None)):
    await verify_admin(authorization)
    await rag_service.delete_document(document_id)
    return {"status": "deleted"}


# --- Users ---

@app.get("/api/admin/users")
async def list_users(authorization: str = Header(None)):
    await verify_admin(authorization)
    users = await sm.session_manager.list_users_with_stats()
    return users


# ============================================
# WEB CHAT (avatar)
# ============================================

@app.get("/", response_class=HTMLResponse)
async def form_page():
    """Serve o formulario de captura de leads."""
    html_path = STATIC_DIR / "form.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Form page not found")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/landing", response_class=HTMLResponse)
async def landing_page():
    """Serve a landing page (backup)."""
    html_path = STATIC_DIR / "landing.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Landing page not found")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/chat", response_class=HTMLResponse)
async def chat_page():
    """Serve a página de chat com avatar."""
    html_path = STATIC_DIR / "chat.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Chat page not found")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/chat/info")
async def chat_info():
    """Retorna info do agente para o frontend."""
    settings = await agent._get_settings()
    return {"agent_name": settings.get("agent_name", "Emma")}


@app.post("/api/chat")
async def chat_endpoint(
    request: Request,
    audio: UploadFile = File(None),
    text: str = Form(None),
    session_id: str = Form(None),
):
    """
    Endpoint unificado do chat web.
    Aceita texto (JSON ou form) ou áudio (multipart form).
    Retorna: { text, audio_base64, transcription? }
    """
    import io

    # Determinar input: JSON body ou multipart form
    content_type = request.headers.get("content-type", "")

    user_text = None
    transcription = None

    if "application/json" in content_type:
        body = await request.json()
        user_text = body.get("text", "").strip()
        session_id = body.get("session_id", session_id)

    elif audio and audio.filename:
        # Áudio enviado — transcrever com Whisper
        audio_bytes = await audio.read()
        if len(audio_bytes) < 500:
            return JSONResponse({"text": "Audio too short. Try again!", "audio_base64": None})

        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = audio.filename or "recording.webm"

        try:
            result = await openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
            transcription = result.text.strip()
            user_text = transcription
        except Exception as e:
            logger.error(f"Whisper falhou: {e}")
            return JSONResponse({"text": "Could not transcribe audio. Try again!", "audio_base64": None})

    elif text:
        user_text = text.strip()

    if not user_text:
        return JSONResponse({"text": "I didn't catch that. Could you try again?", "audio_base64": None})

    # Usar session_id como "phone" para o agente (web sessions)
    phone = session_id or f"web_{uuid.uuid4().hex[:8]}"

    try:
        # Processar com o agente
        reply = await agent.process_message(phone, user_text, "Student")

        # Gerar áudio da resposta
        audio_b64 = None
        try:
            import re
            # Limpar markdown/emojis para TTS
            clean_reply = re.sub(r'[*_~`#]', '', reply)
            clean_reply = re.sub(r'[\U0001f600-\U0001f9ff]', '', clean_reply).strip()

            if clean_reply:
                tts_bytes = await feedback_generator.text_to_speech(clean_reply)
                audio_b64 = b64mod.b64encode(tts_bytes).decode("ascii")
        except Exception as e:
            logger.warning(f"TTS falhou: {e}")

        response = {"text": reply, "audio_base64": audio_b64}
        if transcription:
            response["transcription"] = transcription

        return JSONResponse(response)

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return JSONResponse({"text": "Sorry, something went wrong. Try again!", "audio_base64": None})


# ============================================
# HEALTH CHECK
# ============================================

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}


@app.get("/")
async def root():
    return {
        "name": "English Pronunciation Assistant",
        "version": "2.0.0",
        "status": "running",
        "webhook": "/webhook/uazapi",
        "admin": "/admin",
    }


# ============================================
# EXECUÇÃO DIRETA
# ============================================

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)
