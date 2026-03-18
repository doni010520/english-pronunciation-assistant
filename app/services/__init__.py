from app.services.uazapi import UazapiService, extract_phone_from_jid
from app.services.azure_speech import AzureSpeechService
from app.services.error_analyzer import BrazilianErrorAnalyzer
from app.services.feedback_generator import FeedbackGenerator
from app.services.session_manager import SessionManager, session_manager

__all__ = [
    "UazapiService",
    "extract_phone_from_jid",
    "AzureSpeechService",
    "BrazilianErrorAnalyzer",
    "FeedbackGenerator",
    "SessionManager",
    "session_manager",
]
