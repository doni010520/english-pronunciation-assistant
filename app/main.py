import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from supabase import acreate_client

from app.config import get_settings
from app.models import UazapiWebhook
from app.services import (
    UazapiService,
    AzureSpeechService,
    BrazilianErrorAnalyzer,
    FeedbackGenerator,
    extract_phone_from_jid,
    SessionManager,
)
import app.services.session_manager as sm


# ============================================
# CONFIGURAÇÃO DE LOGGING
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================
# SERVIÇOS GLOBAIS
# ============================================

uazapi_service: UazapiService = None
azure_service: AzureSpeechService = None
error_analyzer: BrazilianErrorAnalyzer = None
feedback_generator: FeedbackGenerator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa serviços no startup"""
    global uazapi_service, azure_service, error_analyzer, feedback_generator

    logger.info("Inicializando servicos...")

    settings = get_settings()

    # Supabase
    supabase_client = await acreate_client(settings.supabase_url, settings.supabase_key)
    sm.session_manager = SessionManager(supabase_client)

    uazapi_service = UazapiService()
    azure_service = AzureSpeechService()
    error_analyzer = BrazilianErrorAnalyzer()
    feedback_generator = FeedbackGenerator()

    logger.info("Servicos inicializados!")

    yield

    logger.info("Encerrando aplicacao...")


# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(
    title="English Pronunciation Assistant",
    description="Assistente de pronúncia de inglês para brasileiros via WhatsApp",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================
# COMANDOS DO BOT
# ============================================

COMMANDS = {
    "/start": "Inicia uma nova sessão de prática",
    "/help": "Mostra os comandos disponíveis",
    "/phrase": "Recebe uma nova frase para praticar",
    "/progress": "Mostra seu progresso na sessão atual",
    "/level": "Escolhe o nível (beginner, intermediate, advanced)",
    "/focus": "Escolhe o foco (th_sounds, vowels, r_sound, general)",
}

WELCOME_MESSAGE = """🎓 *English Pronunciation Assistant*

Olá! Sou seu assistente de pronúncia de inglês.

*Como funciona:*
1️⃣ Envie /phrase para receber uma frase
2️⃣ Grave um áudio pronunciando a frase
3️⃣ Receba feedback detalhado sobre sua pronúncia

*Comandos:*
/phrase - Nova frase para praticar
/progress - Ver seu progresso
/level beginner|intermediate|advanced - Escolher nível
/focus th_sounds|vowels|r_sound - Focar em sons específicos
/help - Ver esta mensagem

Vamos começar? Envie /phrase! 🚀"""


# ============================================
# PROCESSAMENTO DE MENSAGENS
# ============================================

async def process_text_message(phone: str, text: str, message_id: str):
    """Processa mensagens de texto (comandos)"""
    text = text.strip().lower()
    
    if text in ["/start", "/help", "oi", "olá", "ola", "hello", "hi"]:
        await uazapi_service.send_text(phone, WELCOME_MESSAGE)
        return
    
    if text == "/phrase" or text.startswith("/phrase"):
        # Determinar foco e nível
        parts = text.split()
        focus = parts[1] if len(parts) > 1 else "general"
        
        # Gerar frase
        phrase = await sm.session_manager.get_next_phrase(phone, focus=focus)

        # Criar sessão
        await sm.session_manager.create_session(phone, phrase)
        
        message = f"""📝 *Frase para praticar:*

"{phrase}"

🎤 Agora grave um áudio pronunciando esta frase!

_Dica: Fale devagar e claramente na primeira tentativa._"""
        
        await uazapi_service.send_text(phone, message)
        return
    
    if text == "/progress":
        progress = await sm.session_manager.get_user_progress(phone)
        
        if progress["attempts"] == 0 and not progress.get("lifetime_attempts"):
            await uazapi_service.send_text(
                phone,
                "Voce ainda nao tem progresso.\n\nEnvie /phrase para comecar!"
            )
        else:
            parts = []
            if progress["attempts"] > 0:
                trend_emoji = "+" if progress["trend"] == "improving" else "="
                parts.append(f"*Sessao Atual*\nTentativas: {progress['attempts']}\nMedia: {progress['average']:.0f}/100\nMelhor: {progress['best']:.0f}/100\nUltimo: {progress['latest']:.0f}/100 {trend_emoji}")

            lifetime = progress.get("lifetime_attempts", 0)
            if lifetime > 0:
                parts.append(f"*Historico Geral*\nTotal de tentativas: {lifetime}\nMedia geral: {progress['lifetime_average']:.0f}/100\nMelhor nota: {progress['lifetime_best']:.0f}/100")

            parts.append("Continue praticando! Envie /phrase para nova frase.")
            message = "\n\n".join(parts)
            await uazapi_service.send_text(phone, message)
        return
    
    if text.startswith("/level"):
        parts = text.split()
        if len(parts) > 1 and parts[1] in ["beginner", "intermediate", "advanced"]:
            await sm.session_manager.update_user_preferences(phone, level=parts[1])
            await uazapi_service.send_text(
                phone,
                f"Nivel definido para: *{parts[1]}*\n\nEnvie /phrase para praticar!"
            )
        else:
            await uazapi_service.send_text(
                phone,
                "Uso: /level beginner|intermediate|advanced"
            )
        return

    if text.startswith("/focus"):
        parts = text.split()
        options = ["th_sounds", "vowels", "r_sound", "general"]
        if len(parts) > 1 and parts[1] in options:
            await sm.session_manager.update_user_preferences(phone, focus=parts[1])
            await uazapi_service.send_text(
                phone,
                f"Foco definido para: *{parts[1]}*\n\nEnvie /phrase para praticar!"
            )
        else:
            await uazapi_service.send_text(
                phone,
                "Uso: /focus th_sounds|vowels|r_sound|general\n\n"
                "- th_sounds - Sons de TH (think, this)\n"
                "- vowels - Vogais problematicas\n"
                "- r_sound - R americano\n"
                "- general - Frases gerais"
            )
        return
    
    # Mensagem não reconhecida
    await uazapi_service.send_text(
        phone,
        "🤔 Não entendi. Envie /help para ver os comandos ou /phrase para praticar!"
    )


async def process_audio_message(phone: str, message_id: str, push_name: str = None):
    """Processa mensagens de áudio - o coração do sistema!"""
    
    # Verificar se tem sessão ativa
    session = await sm.session_manager.get_session(phone)
    
    if not session:
        await uazapi_service.send_text(
            phone,
            "🎤 Recebi seu áudio, mas você ainda não tem uma frase para praticar!\n\n"
            "Envie /phrase primeiro para receber uma frase."
        )
        return
    
    reference_text = session.reference_text
    
    try:
        # Indicar que estamos processando
        await uazapi_service.send_presence(phone, "composing")
        
        logger.info(f"📥 Processando áudio de {phone} para frase: {reference_text}")
        
        # 1. Baixar áudio
        audio_bytes, mimetype = await uazapi_service.download_audio(message_id)
        logger.info(f"✅ Áudio baixado: {len(audio_bytes)} bytes, tipo: {mimetype}")
        
        # Determinar formato
        if "ogg" in mimetype:
            audio_format = "ogg"
        elif "mp3" in mimetype:
            audio_format = "mp3"
        elif "wav" in mimetype:
            audio_format = "wav"
        else:
            audio_format = "ogg"  # Default WhatsApp
        
        # 2. Avaliar pronúncia com Azure
        logger.info("🎯 Enviando para Azure Speech...")
        pronunciation_result = await azure_service.assess_pronunciation(
            audio_bytes=audio_bytes,
            reference_text=reference_text,
            audio_format=audio_format
        )
        logger.info(f"✅ Score: {pronunciation_result.overall_score:.0f}/100")
        
        # 3. Analisar erros de brasileiros
        analysis = error_analyzer.analyze(pronunciation_result)
        
        # 4. Atualizar sessão com score
        await sm.session_manager.update_session(phone, pronunciation_result.overall_score)
        
        # 5. Gerar feedback humanizado
        feedback = await feedback_generator.generate_feedback(
            analysis=analysis,
            student_name=push_name,
            attempt_number=session.attempt_number
        )
        
        # 6. Montar resposta completa
        response_parts = []
        
        # Score visual
        score = pronunciation_result.overall_score
        if score >= 85:
            score_emoji = "🌟"
        elif score >= 70:
            score_emoji = "👏"
        elif score >= 55:
            score_emoji = "💪"
        else:
            score_emoji = "🌱"
        
        response_parts.append(f"{score_emoji} *Score: {score:.0f}/100*")
        response_parts.append("")
        response_parts.append(feedback)
        
        # Adicionar sugestão de próximo passo
        response_parts.append("")
        if score >= 85:
            response_parts.append("✨ Envie /phrase para uma nova frase!")
        else:
            response_parts.append("🔄 Tente novamente ou envie /phrase para nova frase")
        
        # Enviar resposta
        full_response = "\n".join(response_parts)
        await uazapi_service.send_text(phone, full_response, reply_to=message_id)
        
        logger.info(f"✅ Feedback enviado para {phone}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar áudio: {str(e)}", exc_info=True)
        await uazapi_service.send_text(
            phone,
            "😅 Ops! Tive um problema ao processar seu áudio.\n\n"
            "Por favor, tente gravar novamente. Dicas:\n"
            "• Fale em um ambiente silencioso\n"
            "• Grave pelo menos 2 segundos\n"
            "• Fale claramente e não muito rápido"
        )


# ============================================
# WEBHOOK ENDPOINT
# ============================================

@app.post("/webhook/uazapi")
async def webhook_uazapi(payload: UazapiWebhook, background_tasks: BackgroundTasks):
    """
    Webhook principal que recebe mensagens da Uazapi
    """
    try:
        # Filtrar eventos
        if payload.event != "messages":
            return JSONResponse({"status": "ignored", "reason": "not a message event"})
        
        if not payload.message:
            return JSONResponse({"status": "ignored", "reason": "no message"})
        
        message = payload.message
        
        # Ignorar mensagens enviadas por nós
        if message.key.fromMe:
            return JSONResponse({"status": "ignored", "reason": "from me"})
        
        # Extrair dados
        phone = extract_phone_from_jid(message.key.remoteJid)
        message_id = message.key.id
        push_name = message.pushName or "Aluno"
        
        logger.info(f"📨 Mensagem recebida de {phone} ({push_name})")
        
        # Determinar tipo de mensagem
        if message.audioMessage:
            # Processar em background para responder rápido ao webhook
            background_tasks.add_task(
                process_audio_message, 
                phone, 
                message_id,
                push_name
            )
            return JSONResponse({"status": "processing", "type": "audio"})
        
        elif message.conversation:
            # Mensagem de texto simples
            background_tasks.add_task(
                process_text_message,
                phone,
                message.conversation,
                message_id
            )
            return JSONResponse({"status": "processing", "type": "text"})
        
        elif message.extendedTextMessage:
            # Mensagem de texto com formatação
            text = message.extendedTextMessage.get("text", "")
            if text:
                background_tasks.add_task(
                    process_text_message,
                    phone,
                    text,
                    message_id
                )
                return JSONResponse({"status": "processing", "type": "extended_text"})
        
        return JSONResponse({"status": "ignored", "reason": "unsupported message type"})
        
    except Exception as e:
        logger.error(f"❌ Erro no webhook: {str(e)}", exc_info=True)
        # Não retornar erro para a Uazapi não reenviar
        return JSONResponse({"status": "error", "message": str(e)})


# ============================================
# ENDPOINTS DE HEALTH CHECK
# ============================================

@app.get("/health")
async def health_check():
    """Health check para load balancers"""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "name": "English Pronunciation Assistant",
        "version": "1.0.0",
        "status": "running",
        "webhook": "/webhook/uazapi"
    }


# ============================================
# EXECUÇÃO DIRETA
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
