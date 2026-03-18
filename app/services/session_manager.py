from typing import Optional
from datetime import datetime, timedelta
from app.models import PracticeSession


# ============================================
# FRASES PARA PRÁTICA POR NÍVEL E FOCO
# ============================================

PRACTICE_PHRASES = {
    "th_sounds": [
        "I think that this thing is thoughtful",
        "The three brothers thought about the weather",
        "They think these clothes are worth buying",
        "Mother and father think that math is the best",
        "This is the third thing I thought about today",
    ],
    "vowels": [
        "The cat sat on a bad mat",
        "Did you live near the ship?",
        "Put the good book on the foot stool",
        "I love to come up and have some fun",
        "The man had a plan to catch the van",
    ],
    "r_sound": [
        "The red car ran around the corner",
        "Her world turned around in February",
        "The girl heard the bird in the garden",
        "Work hard and learn more every day",
        "The farmer's daughter brought water from the river",
    ],
    "general": [
        "How are you doing today?",
        "I would like to order a coffee please",
        "What time does the meeting start?",
        "Thank you very much for your help",
        "I think we should go to the park this weekend",
        "Could you please repeat that?",
        "I'm learning English to improve my career",
        "The weather is beautiful today",
    ],
    "beginner": [
        "Hello, how are you?",
        "My name is...",
        "Nice to meet you",
        "Thank you very much",
        "See you tomorrow",
    ],
    "intermediate": [
        "I've been working on this project for three months",
        "Could you tell me where the nearest station is?",
        "I think the weather will be better tomorrow",
        "What do you think about this idea?",
        "I would appreciate your feedback on this matter",
    ],
    "advanced": [
        "Although the circumstances were challenging, we persevered through",
        "The theoretical implications of this research are quite fascinating",
        "I thoroughly enjoyed the thought-provoking discussion we had",
        "Nevertheless, I believe there might be other approaches worth considering",
        "The entrepreneur's breakthrough innovation revolutionized the industry",
    ],
}


class SessionManager:
    """
    Gerenciador de sessões de prática em memória
    Em produção, usar Redis ou Supabase
    """
    
    def __init__(self):
        # phone -> PracticeSession
        self._sessions: dict[str, PracticeSession] = {}
        self._phrase_index: dict[str, int] = {}  # phone -> índice da próxima frase
        self._session_timeout = timedelta(minutes=30)
    
    def get_session(self, phone: str) -> Optional[PracticeSession]:
        """Obtém sessão ativa do usuário"""
        session = self._sessions.get(phone)
        return session
    
    def create_session(
        self, 
        phone: str, 
        reference_text: str,
        level: str = "intermediate"
    ) -> PracticeSession:
        """Cria ou atualiza sessão de prática"""
        session = PracticeSession(
            phone=phone,
            reference_text=reference_text,
            attempt_number=1,
            previous_scores=[]
        )
        self._sessions[phone] = session
        return session
    
    def update_session(self, phone: str, score: float) -> PracticeSession:
        """Atualiza sessão com novo score"""
        session = self._sessions.get(phone)
        if session:
            session.previous_scores.append(score)
            session.attempt_number += 1
            return session
        return None
    
    def get_next_phrase(
        self, 
        phone: str, 
        focus: str = "general",
        level: str = "intermediate"
    ) -> str:
        """Obtém próxima frase para praticar"""
        # Determinar lista de frases
        if focus in PRACTICE_PHRASES:
            phrases = PRACTICE_PHRASES[focus]
        elif level in PRACTICE_PHRASES:
            phrases = PRACTICE_PHRASES[level]
        else:
            phrases = PRACTICE_PHRASES["general"]
        
        # Pegar índice atual e avançar
        key = f"{phone}_{focus}"
        index = self._phrase_index.get(key, 0)
        phrase = phrases[index % len(phrases)]
        self._phrase_index[key] = (index + 1) % len(phrases)
        
        return phrase
    
    def clear_session(self, phone: str):
        """Limpa sessão do usuário"""
        if phone in self._sessions:
            del self._sessions[phone]
    
    def get_user_progress(self, phone: str) -> dict:
        """Retorna progresso do usuário na sessão atual"""
        session = self._sessions.get(phone)
        if not session or not session.previous_scores:
            return {"attempts": 0, "average": 0, "best": 0, "trend": "neutral"}
        
        scores = session.previous_scores
        return {
            "attempts": len(scores),
            "average": sum(scores) / len(scores),
            "best": max(scores),
            "latest": scores[-1],
            "trend": "improving" if len(scores) > 1 and scores[-1] > scores[-2] else "neutral"
        }


# Instância global (em produção, usar injeção de dependência)
session_manager = SessionManager()
