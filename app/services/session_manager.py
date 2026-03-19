import logging
from typing import Optional
from datetime import datetime, timedelta, timezone

from app.models import PracticeSession


logger = logging.getLogger(__name__)


# ============================================
# FRASES PARA PRATICA POR NIVEL E FOCO
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
    Gerenciador de sessoes de pratica com Supabase
    """

    def __init__(self, supabase_client):
        self._client = supabase_client
        self._session_timeout = timedelta(minutes=30)

    async def get_session(self, phone: str) -> Optional[PracticeSession]:
        """Obtem sessao ativa do usuario"""
        result = await (
            self._client.table("users")
            .select("*")
            .eq("phone", phone)
            .maybe_single()
            .execute()
        )

        if not result.data or result.data.get("reference_text") is None:
            return None

        row = result.data

        # Verificar timeout
        updated_at = datetime.fromisoformat(row["updated_at"])
        if datetime.now(timezone.utc) - updated_at > self._session_timeout:
            await self.clear_session(phone)
            return None

        return PracticeSession(
            phone=row["phone"],
            reference_text=row["reference_text"],
            attempt_number=row["attempt_number"],
            previous_scores=row["previous_scores"] or [],
            level=row["level"],
            focus=row["focus"],
            updated_at=updated_at,
        )

    async def create_session(
        self,
        phone: str,
        reference_text: str,
        level: str = "intermediate",
    ) -> PracticeSession:
        """Cria ou atualiza sessao de pratica"""
        data = {
            "phone": phone,
            "reference_text": reference_text,
            "attempt_number": 1,
            "previous_scores": [],
            "level": level,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        await (
            self._client.table("users")
            .upsert(data, on_conflict="phone")
            .execute()
        )

        return PracticeSession(
            phone=phone,
            reference_text=reference_text,
            attempt_number=1,
            previous_scores=[],
            level=level,
        )

    async def update_session(self, phone: str, score: float) -> Optional[PracticeSession]:
        """Atualiza sessao com novo score e grava historico"""
        session = await self.get_session(phone)
        if not session:
            return None

        new_scores = session.previous_scores + [score]
        new_attempt = session.attempt_number + 1

        await (
            self._client.table("users")
            .update({
                "previous_scores": new_scores,
                "attempt_number": new_attempt,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("phone", phone)
            .execute()
        )

        # Gravar no historico
        await (
            self._client.table("session_history")
            .insert({
                "phone": phone,
                "reference_text": session.reference_text,
                "score": score,
                "attempt_number": session.attempt_number,
            })
            .execute()
        )

        session.previous_scores = new_scores
        session.attempt_number = new_attempt
        return session

    async def get_next_phrase(
        self,
        phone: str,
        focus: str = "general",
        level: str = "intermediate",
    ) -> str:
        """Obtem proxima frase para praticar"""
        # Determinar lista de frases
        if focus in PRACTICE_PHRASES:
            phrases = PRACTICE_PHRASES[focus]
        elif level in PRACTICE_PHRASES:
            phrases = PRACTICE_PHRASES[level]
        else:
            phrases = PRACTICE_PHRASES["general"]

        # Buscar indice atual do usuario
        result = await (
            self._client.table("users")
            .select("phrase_focus, phrase_index")
            .eq("phone", phone)
            .maybe_single()
            .execute()
        )

        index = 0
        if result.data:
            # Se mudou o foco, resetar indice
            if result.data.get("phrase_focus") == focus:
                index = result.data.get("phrase_index", 0)

        phrase = phrases[index % len(phrases)]
        next_index = (index + 1) % len(phrases)

        # Upsert para salvar indice e garantir que o usuario existe
        await (
            self._client.table("users")
            .upsert(
                {
                    "phone": phone,
                    "phrase_focus": focus,
                    "phrase_index": next_index,
                    "level": level,
                    "focus": focus,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="phone",
            )
            .execute()
        )

        return phrase

    async def clear_session(self, phone: str):
        """Limpa sessao ativa do usuario"""
        await (
            self._client.table("users")
            .update({
                "reference_text": None,
                "previous_scores": [],
                "attempt_number": 0,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("phone", phone)
            .execute()
        )

    async def get_user_progress(self, phone: str) -> dict:
        """Retorna progresso do usuario (sessao atual + historico)"""
        session = await self.get_session(phone)

        progress = {"attempts": 0, "average": 0, "best": 0, "trend": "neutral"}

        if session and session.previous_scores:
            scores = session.previous_scores
            progress.update({
                "attempts": len(scores),
                "average": sum(scores) / len(scores),
                "best": max(scores),
                "latest": scores[-1],
                "trend": "improving" if len(scores) > 1 and scores[-1] > scores[-2] else "neutral",
            })

        # Stats de longo prazo
        result = await (
            self._client.rpc(
                "get_user_lifetime_stats",
                {"user_phone": phone},
            )
            .execute()
        )

        if result.data and len(result.data) > 0:
            stats = result.data[0]
            progress["lifetime_attempts"] = stats.get("total", 0)
            progress["lifetime_average"] = stats.get("avg_score", 0)
            progress["lifetime_best"] = stats.get("best_score", 0)

        return progress

    async def update_user_preferences(
        self, phone: str, level: str = None, focus: str = None
    ):
        """Atualiza preferencias do usuario"""
        data = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if level:
            data["level"] = level
        if focus:
            data["focus"] = focus

        await (
            self._client.table("users")
            .upsert({"phone": phone, **data}, on_conflict="phone")
            .execute()
        )


# Inicializado no lifespan do FastAPI
session_manager: Optional[SessionManager] = None
