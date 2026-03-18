from pydantic import BaseModel
from typing import Optional, Any


# ============================================
# WEBHOOK UAZAPI - Estrutura de entrada
# ============================================

class MessageKey(BaseModel):
    remoteJid: str
    fromMe: bool
    id: str


class AudioMessage(BaseModel):
    url: Optional[str] = None
    mimetype: Optional[str] = None
    fileSha256: Optional[str] = None
    fileLength: Optional[int] = None
    seconds: Optional[int] = None
    ptt: Optional[bool] = None
    mediaKey: Optional[str] = None
    fileEncSha256: Optional[str] = None
    directPath: Optional[str] = None


class TextMessage(BaseModel):
    text: Optional[str] = None


class Message(BaseModel):
    key: MessageKey
    messageTimestamp: Optional[int] = None
    pushName: Optional[str] = None
    audioMessage: Optional[AudioMessage] = None
    conversation: Optional[str] = None
    extendedTextMessage: Optional[dict] = None


class UazapiWebhook(BaseModel):
    event: str
    instance: Optional[str] = None
    message: Optional[Message] = None
    data: Optional[Any] = None
    
    class Config:
        extra = "allow"


# ============================================
# AZURE PRONUNCIATION - Respostas
# ============================================

class PhonemeAssessment(BaseModel):
    phoneme: str
    accuracy_score: float


class WordAssessment(BaseModel):
    word: str
    accuracy_score: float
    error_type: Optional[str] = None
    phonemes: list[PhonemeAssessment] = []


class PronunciationResult(BaseModel):
    overall_score: float
    accuracy_score: float
    fluency_score: float
    completeness_score: float
    words: list[WordAssessment]
    transcription: str


# ============================================
# ANÁLISE DE ERROS
# ============================================

class BrazilianError(BaseModel):
    word: str
    expected_phoneme: str
    accuracy: float
    tip: str
    practice_words: list[str]


class ErrorAnalysis(BaseModel):
    pronunciation_result: PronunciationResult
    brazilian_errors: list[BrazilianError]
    main_issue: Optional[str] = None
    encouragement_level: str  # "great", "good", "needs_work"


# ============================================
# SESSÃO DE PRÁTICA
# ============================================

class PracticeSession(BaseModel):
    phone: str
    reference_text: str
    attempt_number: int = 1
    previous_scores: list[float] = []
