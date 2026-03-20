import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Header, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
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
azure_service: AzureSpeechService = None
error_analyzer: BrazilianErrorAnalyzer = None
feedback_generator: FeedbackGenerator = None
agent: ConversationalAgent = None
rag_service: RAGService = None
openai_client: AsyncOpenAI = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global uazapi_service, azure_service, error_analyzer, feedback_generator, agent, rag_service, openai_client

    logger.info("Inicializando servicos...")
    settings = get_settings()

    # Supabase
    supabase_client = await acreate_client(settings.supabase_url, settings.supabase_key)
    sm.session_manager = SessionManager(supabase_client)

    # OpenAI client compartilhado
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)  # noqa: F841 — used as global

    # Serviços existentes
    uazapi_service = UazapiService()
    azure_service = AzureSpeechService()
    error_analyzer = BrazilianErrorAnalyzer()
    feedback_generator = FeedbackGenerator()

    # Novos serviços
    rag_service = RAGService(supabase_client, openai_client)
    agent = ConversationalAgent(supabase_client, openai_client, rag_service, sm.session_manager)

    logger.info("Servicos inicializados!")
    yield
    logger.info("Encerrando aplicacao...")


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
# MESSAGE BUFFER (debounce)
# ============================================

BUFFER_DELAY_SECONDS = 4  # esperar 4s de silêncio antes de processar


@dataclass
class BufferedMessage:
    """Uma mensagem no buffer."""
    msg_type: str  # "text", "audio", "image"
    text: Optional[str] = None
    message_id: Optional[str] = None
    audio_bytes: Optional[bytes] = None
    audio_mimetype: Optional[str] = None
    image_bytes: Optional[bytes] = None
    image_mimetype: Optional[str] = None


@dataclass
class UserBuffer:
    """Buffer de mensagens de um usuário."""
    messages: list = field(default_factory=list)
    timer_task: Optional[asyncio.Task] = None
    push_name: str = "Aluno"


# phone → UserBuffer
message_buffers: dict[str, UserBuffer] = {}
buffer_lock = asyncio.Lock()


async def _add_to_buffer(phone: str, msg: BufferedMessage, push_name: str):
    """Adiciona mensagem ao buffer e reinicia o timer."""
    async with buffer_lock:
        if phone not in message_buffers:
            message_buffers[phone] = UserBuffer()

        buf = message_buffers[phone]
        buf.messages.append(msg)
        buf.push_name = push_name

        # Cancelar timer anterior
        if buf.timer_task and not buf.timer_task.done():
            buf.timer_task.cancel()

        # Iniciar novo timer
        buf.timer_task = asyncio.create_task(_buffer_timer(phone))


async def _buffer_timer(phone: str):
    """Espera o delay e dispara o processamento."""
    try:
        await asyncio.sleep(BUFFER_DELAY_SECONDS)
        await _flush_buffer(phone)
    except asyncio.CancelledError:
        pass  # timer cancelado porque chegou nova mensagem


async def _flush_buffer(phone: str):
    """Processa todas as mensagens acumuladas do usuário."""
    async with buffer_lock:
        buf = message_buffers.pop(phone, None)

    if not buf or not buf.messages:
        return

    push_name = buf.push_name
    messages = buf.messages

    try:
        await uazapi_service.send_presence(phone, "composing")

        # Coletar textos e dados de pronúncia de todas as mensagens
        text_parts = []
        pronunciation_notes = []
        has_audio = False
        last_message_id = None

        for msg in messages:
            if msg.message_id:
                last_message_id = msg.message_id

            if msg.msg_type == "text" and msg.text:
                text_parts.append(msg.text)

            elif msg.msg_type == "audio" and msg.audio_bytes:
                has_audio = True
                # Transcrever
                transcription = await _transcribe_audio(msg.audio_bytes, msg.audio_mimetype)
                if transcription:
                    text_parts.append(transcription)

                    # Avaliação de pronúncia nos bastidores
                    try:
                        fmt = "ogg" if "ogg" in msg.audio_mimetype else "mp3" if "mp3" in msg.audio_mimetype else "ogg"
                        pron_result = await azure_service.assess_pronunciation(
                            audio_bytes=msg.audio_bytes,
                            reference_text=transcription,
                            audio_format=fmt,
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
                                f"Gross pronunciation errors in this audio: {errors_text}."
                            )
                        try:
                            await sm.session_manager.update_session(phone, pron_result.overall_score)
                        except Exception:
                            pass
                    except Exception as e:
                        logger.warning(f"Pronúncia falhou: {e}")

            elif msg.msg_type == "image":
                # Extrair texto da imagem
                try:
                    extracted = await feedback_generator.extract_text_from_image(
                        msg.image_bytes, msg.image_mimetype
                    )
                    if extracted:
                        text_parts.append(f"[Sent an image with this English text: \"{extracted}\"]")
                        await sm.session_manager.create_session(phone, extracted)
                    else:
                        text_parts.append("[Sent an image but no English text was found in it]")
                except Exception as e:
                    logger.warning(f"Imagem falhou: {e}")

        if not text_parts:
            return

        # Montar mensagem combinada para o agente
        combined = "\n".join(text_parts)
        if pronunciation_notes:
            combined += "\n[PRONUNCIATION DATA — invisible to student, for your reference only: "
            combined += " ".join(pronunciation_notes)
            combined += " If relevant, correct inline while conversing. Do NOT list errors or mention scores.]"

        logger.info(f"Buffer processado ({len(messages)} msgs): {combined[:100]}...")

        # Enviar pro agente
        reply = await agent.process_message(phone, combined, push_name)

        # Responder: se veio áudio, responder em áudio. Se só texto, responder em texto.
        if has_audio:
            await _send_voice_parts(phone, reply)
        else:
            await uazapi_service.send_text(phone, reply, reply_to=last_message_id)

        logger.info(f"Resposta enviada para {phone}")

    except Exception as e:
        logger.error(f"Erro ao processar buffer: {e}", exc_info=True)
        try:
            await uazapi_service.send_text(
                phone, "Desculpe, tive um problema. Tente novamente!"
            )
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

        # Salvar push_name
        try:
            await sm.session_manager.save_push_name(phone, push_name)
        except Exception:
            pass

        # Texto → buffer
        if msg_type in ("Conversation", "ExtendedTextMessage"):
            text = message.get("text", "")
            if text:
                await _add_to_buffer(
                    phone,
                    BufferedMessage(msg_type="text", text=text, message_id=message_id),
                    push_name,
                )
                return JSONResponse({"status": "buffered", "type": "text"})

        # Áudio → baixar agora (webhook pode expirar), colocar no buffer
        if msg_type == "AudioMessage":
            try:
                audio_bytes, mimetype = await uazapi_service.download_audio(full_message_id)
                await _add_to_buffer(
                    phone,
                    BufferedMessage(
                        msg_type="audio",
                        message_id=full_message_id,
                        audio_bytes=audio_bytes,
                        audio_mimetype=mimetype,
                    ),
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
                await _add_to_buffer(
                    phone,
                    BufferedMessage(
                        msg_type="image",
                        message_id=full_message_id,
                        image_bytes=image_bytes,
                        image_mimetype=mimetype,
                    ),
                    push_name,
                )
                return JSONResponse({"status": "buffered", "type": "image"})
            except Exception as e:
                logger.error(f"Falha ao baixar imagem: {e}")
                return JSONResponse({"status": "error", "message": str(e)})

        logger.info(f"Tipo não suportado: {msg_type}")
        return JSONResponse({"status": "ignored", "reason": f"unsupported: {msg_type}"})

    except Exception as e:
        logger.error(f"Erro no webhook: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)})


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
