import json
import time
import logging
from typing import Optional

from openai import AsyncOpenAI

from app.services.rag import RAGService

logger = logging.getLogger(__name__)

# --------------------------------------------------
# Prompt base — sempre presente, não editável pelo admin
# --------------------------------------------------

BASE_SYSTEM_PROMPT = """You are {agent_name}, a friendly English tutor chatting with a Brazilian student on WhatsApp.
Your personality: {personality}.

HOW TO BEHAVE:
- You are a REAL conversation partner, not a bot. Chat naturally.
- Match the student's language: if they write in Portuguese, reply in Portuguese. If in English, reply in English. If they mix, you can mix too.
- Keep messages short — 2 to 4 lines max, like a real WhatsApp message.
- Ask questions, react to what they say, share opinions, be fun and engaging.
- You are a tutor AND a friend. The student should enjoy talking to you.

WHEN THE STUDENT SENDS AN AUDIO FOR PRONUNCIATION PRACTICE:
- You will receive their pronunciation score and error details.
- Give brief, encouraging feedback. Focus on what they did well.
- Only mention errors if something was COMPLETELY wrong (wrong word, skipped word, unintelligible).
- NEVER correct accent, intonation, or subtle pronunciation differences. Those are normal and vary by region.
- After feedback, keep the conversation going — suggest trying again, ask if they want a new phrase, etc.

CORRECTIONS IN TEXT CONVERSATION:
- Only correct truly gross errors: completely wrong words, broken grammar that changes meaning.
- Do NOT correct minor spelling, accent-dependent pronunciation, or small nuances.
- When you correct, do it implicitly by using the correct form in your reply. NEVER lecture or list errors.
- Example: student writes "I goed to the store" → you reply "Oh you went to the store? What did you buy?" — correction is natural, conversation flows.

WHAT YOU CAN DO:
- Have free conversation in English or Portuguese
- Give practice phrases for pronunciation
- Show the student's progress and stats
- Adjust difficulty level and focus area
- Answer questions about English (grammar, vocabulary, expressions, culture)
- Help with any English learning need the student has

IMPORTANT: Always keep the conversation moving forward. Never end on just a correction or a score. Always give the student something to respond to."""

# --------------------------------------------------
# Tools (function calling) do agente
# --------------------------------------------------

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "give_practice_phrase",
            "description": "Gives the student a new English phrase to practice pronunciation. Use when the student wants to practice, asks for a phrase, says 'next', or wants to start.",
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "enum": ["general", "th_sounds", "vowels", "r_sound"],
                        "description": "The phoneme focus area. Default 'general'.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_progress",
            "description": "Shows the student's learning progress and statistics. Use when the student asks how they're doing, their score, progress, or stats.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_level",
            "description": "Changes the student's difficulty level. Use when they want easier or harder phrases.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["beginner", "intermediate", "advanced"],
                        "description": "The difficulty level.",
                    }
                },
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_focus",
            "description": "Changes the phoneme focus area for practice. Use when the student wants to work on specific sounds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "enum": ["th_sounds", "vowels", "r_sound", "general"],
                        "description": "The sound focus area.",
                    }
                },
                "required": ["focus"],
            },
        },
    },
]


class ConversationalAgent:
    """Agente conversacional que substitui o sistema de comandos."""

    def __init__(
        self,
        supabase_client,
        openai_client: AsyncOpenAI,
        rag_service: RAGService,
        session_manager,
    ):
        self._db = supabase_client
        self._openai = openai_client
        self._rag = rag_service
        self._session_manager = session_manager
        self._model = "gpt-4.1-mini"
        self._settings_cache = None
        self._settings_cached_at = 0
        self._settings_ttl = 60  # seconds

    # --------------------------------------------------
    # Settings (com cache)
    # --------------------------------------------------

    async def _get_settings(self) -> dict:
        """Carrega settings do agent_settings com cache."""
        now = time.time()
        if self._settings_cache and (now - self._settings_cached_at) < self._settings_ttl:
            return self._settings_cache

        result = await self._db.table("agent_settings").select("*").eq("id", 1).execute()
        if result.data:
            self._settings_cache = result.data[0]
        else:
            self._settings_cache = {
                "agent_name": "Emma",
                "personality": "friendly, patient, encouraging",
                "system_prompt": "",
                "language": "pt-BR",
            }
        self._settings_cached_at = now
        return self._settings_cache

    # --------------------------------------------------
    # Build system prompt
    # --------------------------------------------------

    def _build_system_prompt(self, settings: dict, push_name: str, rag_context: str = None) -> str:
        """Monta o system prompt completo: base + admin custom + RAG + student name."""
        agent_name = settings.get("agent_name", "Emma")
        personality = settings.get("personality", "friendly, patient, encouraging")

        # Prompt base (sempre presente)
        prompt = BASE_SYSTEM_PROMPT.replace("{agent_name}", agent_name)
        prompt = prompt.replace("{personality}", personality)

        # Prompt customizado pelo admin (complemento, não substituto)
        admin_prompt = settings.get("system_prompt", "").strip()
        if admin_prompt:
            prompt += f"\n\nADDITIONAL INSTRUCTIONS FROM ADMIN:\n{admin_prompt}"

        # Contexto RAG
        if rag_context:
            prompt += f"\n\nRELEVANT KNOWLEDGE:\n{rag_context}"

        # Nome do aluno
        prompt += f"\n\nStudent name: {push_name}"

        return prompt

    # --------------------------------------------------
    # Conversation history
    # --------------------------------------------------

    async def _load_history(self, phone: str, limit: int = 20) -> list[dict]:
        """Carrega últimas N mensagens do histórico."""
        result = (
            await self._db.table("conversation_history")
            .select("role, content")
            .eq("phone", phone)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        # Reverter para ordem cronológica
        messages = [{"role": r["role"], "content": r["content"]} for r in reversed(result.data)]
        return messages

    async def _save_message(self, phone: str, role: str, content: str, metadata: dict = None):
        """Salva uma mensagem no histórico."""
        await self._db.table("conversation_history").insert(
            {
                "phone": phone,
                "role": role,
                "content": content,
                "metadata": metadata or {},
            }
        ).execute()

    # --------------------------------------------------
    # Tool execution
    # --------------------------------------------------

    async def _execute_tool(self, phone: str, tool_name: str, args: dict) -> str:
        """Executa uma tool e retorna o resultado como string."""
        sm = self._session_manager

        if tool_name == "give_practice_phrase":
            focus = args.get("focus", "general")
            phrase = await sm.get_next_phrase(phone, focus=focus)
            await sm.create_session(phone, phrase)
            return json.dumps({"phrase": phrase, "focus": focus})

        if tool_name == "show_progress":
            progress = await sm.get_user_progress(phone)
            return json.dumps(progress)

        if tool_name == "set_level":
            level = args["level"]
            await sm.update_user_preferences(phone, level=level)
            return json.dumps({"level": level, "updated": True})

        if tool_name == "set_focus":
            focus = args["focus"]
            await sm.update_user_preferences(phone, focus=focus)
            return json.dumps({"focus": focus, "updated": True})

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    # --------------------------------------------------
    # Processar mensagem de texto
    # --------------------------------------------------

    async def process_message(self, phone: str, text: str, push_name: str = "Aluno") -> str:
        """Processa uma mensagem de texto e retorna a resposta do agente."""
        settings = await self._get_settings()

        # Salvar mensagem do usuário
        await self._save_message(phone, "user", text)

        # Carregar histórico
        history = await self._load_history(phone)

        # Buscar contexto RAG
        rag_context = await self._rag.get_relevant_context(text)

        # Montar system prompt
        system_prompt = self._build_system_prompt(settings, push_name, rag_context)

        # Montar mensagens para o GPT
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)

        # Primeira chamada ao GPT
        response = await self._openai.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=AGENT_TOOLS,
            tool_choice="auto",
            max_tokens=300,
            temperature=0.7,
        )

        assistant_msg = response.choices[0].message

        # Verificar se há tool calls
        if assistant_msg.tool_calls:
            tool_call = assistant_msg.tool_calls[0]
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            logger.info(f"Tool call: {tool_name}({tool_args})")

            # Executar tool
            tool_result = await self._execute_tool(phone, tool_name, tool_args)

            # Segunda chamada ao GPT com resultado da tool
            messages.append(assistant_msg.model_dump())
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                }
            )

            response2 = await self._openai.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=300,
                temperature=0.7,
            )
            reply = response2.choices[0].message.content.strip()
        else:
            reply = assistant_msg.content.strip()

        # Salvar resposta do agente
        await self._save_message(phone, "assistant", reply)

        return reply

    # --------------------------------------------------
    # Processar resultado de áudio (pronúncia)
    # --------------------------------------------------

    async def process_audio_result(
        self,
        phone: str,
        reference_text: str,
        score: float,
        accuracy: float,
        fluency: float,
        completeness: float,
        errors_summary: str,
        attempt_number: int,
        push_name: str = "Aluno",
    ) -> str:
        """Gera feedback contextual para um resultado de pronúncia."""
        settings = await self._get_settings()

        # Montar prompt interno com dados da avaliação
        audio_context = (
            f"The student just practiced the phrase: \"{reference_text}\"\n"
            f"Score: {score:.0f}/100 (accuracy: {accuracy:.0f}, fluency: {fluency:.0f}, completeness: {completeness:.0f})\n"
            f"Attempt #{attempt_number} on this phrase.\n"
            f"Errors detected: {errors_summary}\n\n"
            f"Generate feedback in the same language the student has been using in the conversation. "
            f"Check the conversation history to determine the language.\n"
            f"This will be converted to speech audio, so write naturally as spoken language — "
            f"no emojis, no markdown, no asterisks, no special characters, no bullet points.\n"
            f"Be warm and brief (3-4 sentences). Keep the conversation going after the feedback."
        )

        await self._save_message(phone, "user", f"[audio: pronunciou \"{reference_text}\"]", {"type": "audio", "score": score})

        history = await self._load_history(phone)

        system_prompt = self._build_system_prompt(settings, push_name)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": audio_context})

        response = await self._openai.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )

        reply = response.choices[0].message.content.strip()
        await self._save_message(phone, "assistant", reply, {"type": "audio_feedback", "score": score})

        return reply

    # --------------------------------------------------
    # Processar resultado de imagem
    # --------------------------------------------------

    async def process_image_result(
        self, phone: str, extracted_text: str, push_name: str = "Aluno"
    ) -> str:
        """Gera resposta para texto extraído de uma imagem."""
        settings = await self._get_settings()

        image_context = (
            f"The student sent an image containing English text: \"{extracted_text}\"\n"
            f"A practice session was created with this text. "
            f"Tell the student the text you found and encourage them to record an audio pronouncing it. "
            f"Keep it short for WhatsApp."
        )

        await self._save_message(phone, "user", f"[imagem com texto: \"{extracted_text}\"]", {"type": "image"})

        history = await self._load_history(phone)

        system_prompt = self._build_system_prompt(settings, push_name)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": image_context})

        response = await self._openai.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )

        reply = response.choices[0].message.content.strip()
        await self._save_message(phone, "assistant", reply, {"type": "image_response"})

        return reply
