import json
import time
import logging
from typing import Optional

from openai import AsyncOpenAI

from app.services.rag import RAGService

logger = logging.getLogger(__name__)

# --------------------------------------------------
# Prompt default — usado apenas se o admin não configurou nenhum prompt no painel
# --------------------------------------------------

DEFAULT_SYSTEM_PROMPT = """You are {agent_name}, a friendly and charismatic language tutor (English and French) chatting with a Brazilian student on WhatsApp.
Your personality: {personality}.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOLDEN RULE: CONVERSATION FIRST. ALWAYS.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are a CONVERSATION PARTNER who happens to be a great English teacher. Your #1 job is to make the student WANT to keep talking. Every reply must move the conversation forward.

FLOW: Respond to what they said → (correct if needed, embedded) → Ask something or react to keep it going.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO TALK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- WhatsApp style. Short messages (2-4 lines max). No walls of text.
- Match the student's language. English? Reply in English. Portuguese? Portuguese. Mixed? Mix.
- Be curious. Ask follow-up questions. React with genuine interest.
- Have opinions. Share experiences. Be a person, not a robot.
- Use humor naturally. Tease gently. Be warm.
- If the student says "I went to the park today" — talk about the park! Ask what they did there. Share that you love parks too. HAVE A CONVERSATION.
- NEVER ignore what the student said to give unsolicited teaching.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CORRECTIONS — THE ART OF INVISIBLE TEACHING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WHEN TO CORRECT:
- Only correct GROSS errors: completely wrong word, broken sentence, meaning-changing mistakes.
- Do NOT correct: accent, minor grammar, spelling typos, word order that's still understandable.

HOW TO CORRECT:
- ALWAYS use the "echo correction" technique: repeat the correct form naturally in your reply.
- NEVER say "the correct form is..." or "you should say..." or "it's actually..."
- NEVER list errors. NEVER lecture. NEVER stop the conversation to teach.
- The student should barely notice the correction. That's the goal.

EXAMPLES:
- Student: "I goed to the store" → You: "Oh you went to the store? Nice! What did you get?"
- Student: "She don't like pizza" → You: "Really? She doesn't like pizza? That's wild, pizza is amazing! What food does she like?"
- Student: "I'm agree with you" → You: "Glad you agree! So what do you think we should do about it?"

AFTER CORRECTING:
- Always continue the conversation. The correction is 10% of your reply. The conversation is 90%.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPONDING TO AUDIO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- When the student sends audio, you receive the transcription.
- You may also receive [PRONUNCIATION DATA] — this is INVISIBLE to the student. Background data only.
- ALWAYS respond to the CONTENT of what they said first.
- If pronunciation data shows a word with score below 40, you can gently echo-correct that word — but keep talking about the topic.
- Example: student says "I went to the bitch yesterday" (meant "beach") → You: "Oh nice, the beach! Was it sunny? I love going to the beach on weekends."
- NEVER mention scores. NEVER say "your pronunciation was good/bad". NEVER give pronunciation reports. Just TALK.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GAMES & QUIZZES (ENQUETES DO WHATSAPP)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You have the power to send interactive polls (enquetes) on WhatsApp using the send_quiz tool. This is one of your BEST engagement tools.

WHEN TO USE QUIZZES:
- After discussing a topic for a while, to test vocabulary naturally: "Hey, let me test you on something!"
- When the student seems bored or responses are getting short — a quiz re-energizes the conversation.
- When a correction opportunity arises — instead of correcting directly, turn it into a fun quiz.
- When the student asks to practice or play a game.
- Sprinkle them naturally every 5-8 messages. Don't overdo it.

QUIZ TYPES YOU CAN CREATE:
1. **Vocabulary**: "What does 'thorough' mean?" → options with correct + plausible wrong answers
2. **Grammar**: "Which is correct?" → "She doesn't like" / "She don't like" / "She not like"
3. **Complete the sentence**: "I've been ___ for 2 hours" → "waiting" / "waited" / "wait"
4. **Pronunciation awareness**: For English: "Which word has the 'TH' sound?" For French: "Which word has the nasal 'on' sound?"
5. **Idioms & expressions**: "What does 'break a leg' mean?" → "Good luck" / "Be careful" / "Run fast"
6. **Contextual**: Based on what you were just talking about. This is the BEST type.

HOW TO USE QUIZZES:
- CRITICAL: After calling send_quiz, your text response must NOT repeat the question or options. The poll widget already shows them. Just say something short.
- CRITICAL: After calling send_quiz_batch, your text response must be SHORT (1 line max). Say ONLY something like "Responda todas e te dou feedback!" or "Bora lá, responde aí!" — NEVER list the questions, NEVER number them (1., 2., 3.), NEVER repeat the options, NEVER ask "which one is correct?". The polls already show everything.
- Always set up the quiz conversationally: "Ooh wait, let me quiz you on this!" or "Quick challenge!"
- After the student answers (you'll receive poll results), react naturally: celebrate if correct, explain briefly if wrong, then CONTINUE THE CONVERSATION.
- Make it fun, not a test. The vibe is "game between friends", not "classroom exam".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOPIC MANAGEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- If the conversation stalls, introduce a new topic naturally: "Hey, random question — do you watch any series in English?"
- Vary topics: daily life, hobbies, travel, food, work, movies, music, culture, dreams, funny stories.
- If the student is beginner, keep topics simple and relatable.
- If advanced, go deeper: opinions, debates, hypotheticals ("What would you do if...?").
- Remember what the student told you in previous messages and reference it: "You mentioned you like cooking — have you tried any new recipes?"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROGRESSIVE DIFFICULTY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Adapt your English complexity to the student's level naturally.
- Beginner: Simple words, short sentences, more Portuguese mixed in. Be very encouraging.
- Intermediate: Normal conversational English. Introduce new vocabulary organically and explain only if asked.
- Advanced: Rich vocabulary, idioms, slang, complex structures. Challenge them.
- Gradually increase complexity as the student improves. Don't wait for permission — just naturally level up.

LANGUAGE DETECTION:
- Detect which language the student wants to practice based on context.
- If they write/speak in French or ask about French, switch to French mode.
- If they write/speak in English or ask about English, stay in English mode.
- When in French mode, give examples, corrections and quizzes in French.
- You can mix Portuguese (for explanations) with the target language (for practice).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOOLS AVAILABLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- give_practice_phrase: Give a phrase to practice pronunciation. Use when student asks to practice.
- show_progress: Show stats. Use when student asks how they're doing.
- set_level: Change difficulty. Use when student asks for easier/harder content.
- set_focus: Change phoneme focus. Use when student wants to work on specific sounds.
- send_quiz: Send a WhatsApp poll/quiz. Use to gamify learning and boost engagement.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABSOLUTE RULES (NEVER BREAK THESE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. NEVER give pronunciation scores or reports to the student.
2. NEVER list errors in a message.
3. NEVER say "let me correct you" or any variation.
4. NEVER send a reply without continuing the conversation (asking a question or reacting).
5. NEVER send long messages. Max 4 lines. If you need more, split into multiple tool calls or simplify.
6. NEVER be boring. If you wouldn't send that message to a friend, rewrite it.
7. ALWAYS make the student want to reply. Every message should invite a response."""

# --------------------------------------------------
# Regras obrigatórias — SEMPRE adicionadas, mesmo com prompt customizado
# --------------------------------------------------

MANDATORY_RULES = """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY RULES (ALWAYS APPLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUIZ/POLL RESPONSES:
- After calling send_quiz: Your text response must be SHORT (1 line). Say "Bora!" or "Responde aí!" — NEVER repeat the question or options.
- After calling send_quiz_batch: Your text response must be 1 LINE ONLY. Say "Responda todas!" or "Bora lá!" — NEVER list questions (1., 2., 3.), NEVER number them, NEVER repeat options, NEVER ask "which one is correct?". The polls are already visible to the student.

GENERAL:
- WhatsApp style: Max 4 lines per message.
- NEVER give pronunciation scores or reports.
- NEVER list errors in a message.
- ALWAYS continue the conversation (ask a question or react)."""

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
            "name": "set_language",
            "description": "Sets the target language for practice. Use when the student wants to practice French instead of English, or switch back to English.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "enum": ["en-US", "fr-FR"],
                        "description": "The language to practice. en-US for English, fr-FR for French.",
                    }
                },
                "required": ["language"],
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
    {
        "type": "function",
        "function": {
            "name": "send_quiz",
            "description": (
                "Sends an interactive WhatsApp poll/quiz to the student. "
                "CRITICAL: Do NOT write ANY text about the quiz in your message — the poll widget already shows the question and options. "
                "Your text response must be SHORT (1 line max): 'Bora!', 'Responde aí!', 'Vamos ver!'. "
                "NEVER repeat the question. NEVER list options. NEVER explain what the quiz is about. "
                "Use naturally every 5-8 messages when the student seems disengaged or asks to play."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The quiz question. Keep it short and fun. E.g. 'Which is correct?', 'What does _thorough_ mean?'",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 12,
                        "description": "Answer options (2-12). Put the correct answer in any position — WhatsApp shuffles them.",
                    },
                    "correct_index": {
                        "type": "integer",
                        "description": "Zero-based index of the correct answer in the options array.",
                    },
                },
                "required": ["question", "options", "correct_index"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_quiz_batch",
            "description": (
                "Sends MULTIPLE quizzes at once (3-5 polls). Use when the student asks for 'more quizzes', 'send me more', "
                "'quero mais', 'manda mais', or wants to practice with several questions. "
                "CRITICAL: Your text response after this tool MUST be 1 line only, like 'Responda todas!' or 'Bora lá!'. "
                "NEVER list questions (1., 2., 3.), NEVER repeat options, NEVER write what the polls contain. The student sees the polls directly."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "quizzes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"},
                                "options": {"type": "array", "items": {"type": "string"}},
                                "correct_indices": {"type": "array", "items": {"type": "integer"}},
                                "selectable_count": {"type": "integer", "default": 1},
                            },
                            "required": ["question", "options", "correct_indices"],
                        },
                        "minItems": 5,
                        "maxItems": 5,
                        "description": "Array of 3-5 quiz objects. Each has question, options, correct_indices, and optional selectable_count.",
                    },
                },
                "required": ["quizzes"],
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
        uazapi_service=None,
    ):
        self._db = supabase_client
        self._openai = openai_client
        self._rag = rag_service
        self._session_manager = session_manager
        self._uazapi = uazapi_service
        self._model = "gpt-4.1-mini"
        self._settings_cache = None
        self._settings_cached_at = 0
        self._settings_ttl = 60  # seconds

    def _first_name(self, push_name: str) -> str:
        """Extrai apenas o primeiro nome."""
        return push_name.split()[0] if push_name else "Aluno"

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
        """Monta o system prompt: usa o prompt do painel admin, ou o default se vazio."""
        agent_name = settings.get("agent_name", "Emma")
        personality = settings.get("personality", "friendly, patient, encouraging")

        # Prompt único: vem do banco (painel admin). Se vazio, usa o default.
        admin_prompt = settings.get("system_prompt", "").strip()
        if admin_prompt:
            prompt = admin_prompt
        else:
            prompt = DEFAULT_SYSTEM_PROMPT

        # Substituir placeholders
        prompt = prompt.replace("{agent_name}", agent_name)
        prompt = prompt.replace("{personality}", personality)

        # Contexto RAG
        if rag_context:
            prompt += f"\n\nRELEVANT KNOWLEDGE:\n{rag_context}"

        # Nome do aluno (apenas primeiro nome)
        prompt += f"\n\nStudent name: {self._first_name(push_name)}"

        # Regras obrigatórias — SEMPRE adicionadas no final
        prompt += MANDATORY_RULES

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

    async def _save_pending_quiz_batch(self, phone: str, quizzes: list):
        """Salva múltiplos quizzes pendentes para comparar com respostas do aluno."""
        await self._db.table("pending_quizzes").upsert(
            {
                "phone": phone,
                "quizzes": quizzes,
                "total": len(quizzes),
                "answered": 0,
            },
            on_conflict="phone"
        ).execute()

    # --------------------------------------------------
    # Tool execution
    # --------------------------------------------------

    async def _execute_tool(self, phone: str, tool_name: str, args: dict) -> str:
        """Executa uma tool e retorna o resultado como string."""
        sm = self._session_manager

        if tool_name == "set_language":
            language = args["language"]
            await sm.set_user_language(phone, language)
            lang_name = "French" if language == "fr-FR" else "English"
            return json.dumps({"language": language, "name": lang_name, "updated": True})

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

        if tool_name == "send_quiz":
            question = args["question"]
            options = args["options"]
            correct_idx = args.get("correct_index", 0)
            correct_answer = options[correct_idx] if correct_idx < len(options) else options[0]
            
            if self._uazapi:
                try:
                    result = await self._uazapi.send_poll(
                        phone=phone,
                        question=question,
                        options=options,
                        selectable_count=1,
                    )
                    
                    # Extrair message_id da resposta do Uazapi
                    quiz_message_id = result.get("id", "") or result.get("messageId", "") or result.get("key", {}).get("id", "")
                    
                    # Salvar enquete pendente para rastrear resposta
                    await self._save_pending_single_quiz(
                        phone=phone,
                        quiz_message_id=quiz_message_id,
                        question=question,
                        options=options,
                        correct_answer=correct_answer,
                    )
                    
                    return json.dumps({
                        "sent": True,
                        "question": question,
                        "correct_answer": correct_answer,
                        "quiz_message_id": quiz_message_id,
                    })
                except Exception as e:
                    logger.error(f"Failed to send poll: {e}")
                    return json.dumps({"sent": False, "error": str(e)})
            return json.dumps({"sent": False, "error": "Uazapi service not available"})

        if tool_name == "send_quiz_batch":
            quizzes = args.get("quizzes", [])
            if not self._uazapi:
                return json.dumps({"sent": False, "error": "Uazapi service not available"})

            sent_count = 0
            all_correct_answers = []

            for quiz in quizzes:
                question = quiz["question"]
                options = quiz["options"]
                correct_indices = quiz.get("correct_indices", [0])
                selectable_count = quiz.get("selectable_count", 1)

                if isinstance(correct_indices, int):
                    correct_indices = [correct_indices]

                try:
                    await self._uazapi.send_poll(
                        phone=phone,
                        question=question,
                        options=options,
                        selectable_count=selectable_count,
                    )
                    sent_count += 1
                    correct_answers = [options[i] for i in correct_indices if i < len(options)]
                    all_correct_answers.append({
                        "question": question,
                        "correct_answers": correct_answers,
                    })
                except Exception as e:
                    logger.error(f"Failed to send poll in batch: {e}")

            # Salvar todos os quizzes pendentes
            await self._save_pending_quiz_batch(phone, all_correct_answers)

            return json.dumps({
                "sent": True,
                "count": sent_count,
                "total": len(quizzes),
            })

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    # --------------------------------------------------
    # Quiz answer processing (single quiz)
    # --------------------------------------------------

    async def _save_pending_single_quiz(
        self, 
        phone: str, 
        quiz_message_id: str,
        question: str,
        options: list,
        correct_answer: str
    ):
        """Salva uma enquete única pendente para rastrear resposta e tentativas."""
        await self._db.table("pending_quizzes").upsert(
            {
                "phone": phone,
                "quiz_message_id": quiz_message_id,
                "question": question,
                "options": options,
                "correct_answers": [correct_answer],
                "quizzes": None,
                "total": 1,
                "answered": 0,
                "attempts": 0,
                "max_attempts": 2,
                "awaiting_hint_response": False,
                "status": "pending",
                "quiz_type": "single",
                "followup_sent": False,
            },
            on_conflict="phone"
        ).execute()

    async def process_quiz_answer(self, phone: str, vote: str, quiz_message_id: str, push_name: str = "Aluno") -> str:
        """Processa a resposta de uma enquete e retorna feedback apropriado."""
        
        # Buscar enquete pendente
        result = await self._db.table("pending_quizzes").select("*").eq("phone", phone).execute()
        
        if not result.data:
            return None  # Nenhuma enquete pendente
        
        quiz_data = result.data[0]
        
        # Verificar se é single quiz
        if quiz_data.get("quiz_type") != "single":
            return None  # Batch será tratado separadamente
        
        correct_answer = quiz_data.get("correct_answers", [""])[0]
        question = quiz_data.get("question", "")
        attempts = quiz_data.get("attempts", 0)
        awaiting_hint = quiz_data.get("awaiting_hint_response", False)
        
        # Se estava aguardando resposta sobre dica
        if awaiting_hint:
            return await self._handle_hint_response(phone, vote, quiz_data, push_name)
        
        # Verificar se acertou
        is_correct = vote.strip().lower() == correct_answer.strip().lower()
        
        if is_correct:
            # Acertou! Marcar como respondido e gerar feedback
            await self._db.table("pending_quizzes").update({
                "status": "answered_correct",
                "answered": 1,
                "answered_at": "now()",
            }).eq("phone", phone).execute()
            
            return await self._generate_correct_feedback(question, correct_answer, push_name)
        
        else:
            # Errou
            new_attempts = attempts + 1
            
            if new_attempts >= 2:
                # Segunda tentativa errada - revelar resposta
                await self._db.table("pending_quizzes").update({
                    "status": "answered_wrong",
                    "answered": 1,
                    "attempts": new_attempts,
                    "answered_at": "now()",
                }).eq("phone", phone).execute()
                
                return await self._generate_wrong_feedback_final(question, correct_answer, vote, push_name)
            
            else:
                # Primeira tentativa errada - oferecer dica
                await self._db.table("pending_quizzes").update({
                    "attempts": new_attempts,
                    "awaiting_hint_response": True,
                }).eq("phone", phone).execute()
                
                return await self._generate_wrong_feedback_offer_hint(question, vote, push_name)

    async def _handle_hint_response(self, phone: str, response: str, quiz_data: dict, push_name: str) -> str:
        """Trata a resposta do aluno sobre querer ou não uma dica."""
        
        # Reset do estado de aguardando dica
        await self._db.table("pending_quizzes").update({
            "awaiting_hint_response": False,
        }).eq("phone", phone).execute()
        
        question = quiz_data.get("question", "")
        correct_answer = quiz_data.get("correct_answers", [""])[0]
        options = quiz_data.get("options", [])
        first_name = self._first_name(push_name)
        
        # Verificar se o aluno quer dica (sim, quero, yes, etc.)
        positive_responses = ["sim", "quero", "yes", "s", "ok", "pode", "manda", "vai", "bora", "please", "por favor"]
        wants_hint = any(p in response.lower() for p in positive_responses)
        
        if wants_hint:
            return await self._generate_hint(question, correct_answer, options, push_name)
        else:
            # Não quer dica, dar mais uma chance
            return f"Beleza, {first_name}! Tenta de novo então! 💪"

    async def _generate_correct_feedback(self, question: str, correct_answer: str, push_name: str) -> str:
        """Gera feedback para resposta correta usando GPT."""
        first_name = self._first_name(push_name)
        
        prompt = f"""O aluno {first_name} acertou uma enquete de inglês.

Pergunta: {question}
Resposta correta: {correct_answer}

Gere uma mensagem curta (máximo 3 linhas) que:
1. Parabenize o aluno de forma natural (use apenas o primeiro nome)
2. Explique brevemente POR QUE essa é a resposta certa (seja educativo mas conciso)
3. Use tom de WhatsApp, informal e amigável
4. Vá direto ao ponto, sem saudações elaboradas

Responda apenas com a mensagem, sem explicações adicionais."""

        response = await self._openai.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7,
        )
        
        return response.choices[0].message.content.strip()

    async def _generate_wrong_feedback_offer_hint(self, question: str, wrong_answer: str, push_name: str) -> str:
        """Gera feedback para primeira tentativa errada, oferecendo dica."""
        first_name = self._first_name(push_name)
        return f"Quase, {first_name}! 🤔 '{wrong_answer}' não é a resposta certa. Quer uma dica?"

    async def _generate_wrong_feedback_final(self, question: str, correct_answer: str, wrong_answer: str, push_name: str) -> str:
        """Gera feedback para segunda tentativa errada, revelando resposta."""
        first_name = self._first_name(push_name)
        
        prompt = f"""O aluno {first_name} errou uma enquete de inglês pela segunda vez.

Pergunta: {question}
Resposta do aluno: {wrong_answer}
Resposta correta: {correct_answer}

Gere uma mensagem curta (máximo 4 linhas) que:
1. Seja encorajadora (não desanime o aluno, use apenas o primeiro nome)
2. Revele a resposta correta
3. Explique brevemente POR QUE essa é a resposta certa
4. Use tom de WhatsApp, informal e amigável
5. Vá direto ao ponto, sem saudações elaboradas como "Oi Gabriel!"

Responda apenas com a mensagem, sem explicações adicionais."""

        response = await self._openai.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7,
        )
        
        return response.choices[0].message.content.strip()

    async def _generate_hint(self, question: str, correct_answer: str, options: list, push_name: str) -> str:
        """Gera uma dica pedagógica sem revelar a resposta."""
        
        prompt = f"""O aluno errou uma enquete de inglês e pediu uma dica.

Pergunta: {question}
Opções: {', '.join(options)}
Resposta correta: {correct_answer} (NÃO REVELE!)

Gere APENAS a dica (máximo 2 linhas):
- Vá direto ao ponto, sem saudação, sem "Oi", sem usar o nome do aluno
- Dê uma pista gramatical, contextual ou de significado
- NÃO revele a resposta
- Termine com "Tenta de novo!"

Responda apenas com a dica."""

        response = await self._openai.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0.7,
        )
        
        return response.choices[0].message.content.strip()

    # --------------------------------------------------
    # Processar mensagem de texto
    # --------------------------------------------------

    async def process_message(self, phone: str, text: str, push_name: str = "Aluno") -> str:
        """Processa uma mensagem de texto e retorna a resposta do agente."""
        settings = await self._get_settings()

        # Verificar se há quiz aguardando resposta sobre dica
        pending = await self._db.table("pending_quizzes").select("*").eq("phone", phone).execute()
        if pending.data and pending.data[0].get("awaiting_hint_response"):
            # Salvar mensagem do usuário antes de processar
            await self._save_message(phone, "user", text)
            return await self._handle_hint_response(phone, text, pending.data[0], push_name)

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
            # Incluir apenas o tool_call que estamos respondendo (evita erro se GPT retornar múltiplos)
            messages.append({
                "role": "assistant",
                "content": assistant_msg.content or "",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                ],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            })

            second_response = await self._openai.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=300,
                temperature=0.7,
            )

            reply = second_response.choices[0].message.content.strip()

        else:
            # Sem tool call — resposta direta
            reply = assistant_msg.content.strip() if assistant_msg.content else "..."

        # Salvar resposta do agente
        await self._save_message(phone, "assistant", reply)

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
