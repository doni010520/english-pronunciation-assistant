import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, Request, Header, HTTPException, UploadFile, File
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


async def process_text_message(phone: str, text: str, message_id: str, push_name: str = "Aluno"):
    """Processa mensagem de texto via agente conversacional."""
    try:
        await uazapi_service.send_presence(phone, "composing")
        reply = await agent.process_message(phone, text, push_name)
        await uazapi_service.send_text(phone, reply, reply_to=message_id)

    except Exception as e:
        logger.error(f"Erro ao processar texto: {e}", exc_info=True)
        await uazapi_service.send_text(
            phone, "Desculpe, tive um problema. Tente novamente em alguns segundos!"
        )


async def process_audio_message(phone: str, message_id: str, push_name: str = "Aluno"):
    """Processa áudio: transcreve com Whisper e conversa. Sempre conversa."""
    try:
        await uazapi_service.send_presence(phone, "composing")

        # 1. Baixar áudio
        audio_bytes, mimetype = await uazapi_service.download_audio(message_id)
        logger.info(f"Áudio recebido: {len(audio_bytes)} bytes, {mimetype}")

        # 2. Transcrever com Whisper
        transcription = await _transcribe_audio(audio_bytes, mimetype)
        logger.info(f"Transcrição: {transcription}")

        if not transcription:
            await _send_voice_reply(phone, "Não consegui entender o áudio. Pode tentar de novo?")
            return

        # 3. Passar pro agente como conversa normal — ele decide o que fazer
        reply = await agent.process_message(phone, transcription, push_name)

        # 4. Responder com áudio(s) — já que o aluno mandou áudio, respondemos em áudio
        await _send_voice_parts(phone, reply)

        logger.info(f"Resposta enviada para {phone}")

    except Exception as e:
        logger.error(f"Erro ao processar áudio: {e}", exc_info=True)
        await _send_voice_reply(
            phone,
            "Tive um problema ao processar seu áudio. Tente gravar novamente!",
        )


async def process_image_message(phone: str, message_id: str, push_name: str = "Aluno"):
    """Processa imagem — extrai texto e cria sessão via agente."""
    try:
        await uazapi_service.send_presence(phone, "composing")
        logger.info(f"📷 Processando imagem de {phone}")

        # 1. Baixar imagem
        image_bytes, mimetype = await uazapi_service.download_image(message_id)

        # 2. Extrair texto com GPT Vision
        extracted_text = await feedback_generator.extract_text_from_image(image_bytes, mimetype)

        if not extracted_text:
            reply = await agent.process_message(
                phone,
                "Enviei uma imagem mas parece não ter texto em inglês nela.",
                push_name,
            )
            await uazapi_service.send_text(phone, reply, reply_to=message_id)
            return

        # 3. Criar sessão com texto extraído
        await sm.session_manager.create_session(phone, extracted_text)

        # 4. Resposta via agente
        reply = await agent.process_image_result(phone, extracted_text, push_name)
        await uazapi_service.send_text(phone, reply, reply_to=message_id)

    except Exception as e:
        logger.error(f"❌ Erro ao processar imagem: {e}", exc_info=True)
        await uazapi_service.send_text(
            phone, "😅 Tive um problema ao processar sua imagem. Tente enviar novamente!"
        )


# ============================================
# WEBHOOK UAZAPI
# ============================================

@app.post("/webhook/uazapi")
async def webhook_uazapi(request: Request, background_tasks: BackgroundTasks):
    """Webhook que recebe mensagens da Uazapi."""
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

        logger.info(f"📨 {phone} ({push_name}) tipo: {msg_type}")

        # Salvar push_name
        try:
            await sm.session_manager.save_push_name(phone, push_name)
        except Exception:
            pass

        # Áudio
        if msg_type == "AudioMessage":
            background_tasks.add_task(process_audio_message, phone, full_message_id, push_name)
            return JSONResponse({"status": "processing", "type": "audio"})

        # Imagem
        if msg_type == "ImageMessage":
            background_tasks.add_task(process_image_message, phone, full_message_id, push_name)
            return JSONResponse({"status": "processing", "type": "image"})

        # Texto
        if msg_type in ("Conversation", "ExtendedTextMessage"):
            text = message.get("text", "")
            if text:
                background_tasks.add_task(process_text_message, phone, text, message_id, push_name)
                return JSONResponse({"status": "processing", "type": "text"})

        logger.info(f"⚠️ Tipo não suportado: {msg_type}")
        return JSONResponse({"status": "ignored", "reason": f"unsupported: {msg_type}"})

    except Exception as e:
        logger.error(f"❌ Erro no webhook: {e}", exc_info=True)
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
