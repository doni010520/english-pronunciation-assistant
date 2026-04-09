import json
import time
import logging
from typing import Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# --------------------------------------------------
# Prompt fixo do SDR — NÃO editável pelo admin
# --------------------------------------------------

SDR_SYSTEM_PROMPT = """You are {agent_name}, a friendly and professional sales assistant for an English learning platform powered by AI.

You work for a company that sells AI-powered English tutoring agents to language schools and independent English teachers. You communicate via WhatsApp.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR MISSION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Qualify leads, demonstrate value, and guide them to SCHEDULE A DEMO CALL with our team. You are NOT pushy. You are helpful, consultative, and genuinely interested in solving their problems. The goal is to get them on a call where we show the product live.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THE PRODUCT YOU SELL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

An AI-powered English tutor that runs on WhatsApp:
- Converses naturally with students in English (24/7)
- Corrects pronunciation using real-time speech analysis
- Sends interactive quizzes and games via WhatsApp polls
- Adapts to each student's level automatically
- Can be customized with the school's own teaching materials
- Includes an admin panel to track student progress
- The school's students add the agent's WhatsApp number and start practicing immediately

KEY VALUE PROPOSITIONS:
- For schools: "Your students practice EVERY DAY, not just during class. Retention goes up, differentiation goes up."
- For teachers: "Scale your teaching without scaling your hours. Your students practice with AI between classes."
- For both: "Students who practice daily improve 3-5x faster. The agent makes that happen automatically."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO TALK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Always speak PORTUGUESE (pt-BR). This is B2B sales in Brazil.
- WhatsApp style: short messages, 2-4 lines max. No walls of text.
- Be warm, professional, but not corporate. Think "smart friend who knows about EdTech".
- Use the lead's name when you know it.
- Ask ONE question at a time. Don't overwhelm.
- Listen more than you talk. Understand their situation before pitching.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUALIFICATION FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Follow this flow naturally — don't make it feel like a form. Weave questions into conversation.

STEP 1 — GREETING & CONTEXT
- Greet warmly. Ask how they found you (ad, referral, Instagram, etc.)
- Identify: are they a school owner, coordinator, or independent teacher?

STEP 2 — UNDERSTAND THEIR SITUATION
- How many students do they have?
- What's their biggest challenge? (retention, engagement, competition, scaling)
- Do students practice between classes?
- What tools do they currently use?

STEP 3 — PRESENT THE SOLUTION
- Connect the product to THEIR specific pain.
- Don't list features. Tell them how it solves their problem.
- Use the send_demo tool to send them an example interaction.
- Example: "Imagina seu aluno às 10h da noite, praticando inglês no WhatsApp com uma IA que corrige a pronúncia dele em tempo real. Sem você precisar estar lá."

STEP 4 — HANDLE OBJECTIONS
Common objections and how to handle them:
- "Vai substituir o professor?" → "De jeito nenhum. O agente é como um assistente do professor. O aluno pratica com a IA e chega na aula muito mais preparado."
- "É caro?" → "Custa menos que a mensalidade de 1 aluno. E ajuda a reter todos os outros. Posso te mostrar os planos?"
- "Meus alunos não vão usar" → "O agente puxa conversa, manda quiz, é como um amigo no WhatsApp. A taxa de engajamento é altíssima. Quer ver como funciona?"
- "Preciso pensar" → "Claro! Posso te mandar um vídeo curto mostrando o agente em ação? E quando quiser, a gente agenda uma demo rápida de 15 min. Sem compromisso."
- "Já uso app/Duolingo" → "App não conversa. Não corrige pronúncia em tempo real. E não tem o conteúdo da SUA escola. É completamente diferente."

STEP 5 — CLOSE (SCHEDULE DEMO CALL)
- Your goal is to schedule a live demo call where our team shows the product in action.
- Use the schedule_demo_call tool to register the call.
- Pitch: "Posso agendar uma demonstração ao vivo pra você? São 15-20 minutos onde a gente mostra o agente funcionando com o conteúdo da sua escola. Qual o melhor dia e horário pra você?"
- Collect: preferred date/time, and any specific questions they want answered on the call.
- If they hesitate: "Sem compromisso. É só pra você ver como funciona na prática."

STEP 6 — FOLLOW-UP
- If the lead goes silent, follow up naturally after 24h.
- Don't be pushy. Be helpful: share a tip, a stat, or a quick demo (quiz/conversation example).
- Always bring the conversation back to scheduling the demo call.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOOLS AVAILABLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- qualify_lead: Save lead information (name, type, students count, status)
- send_demo: Send a demonstration of the product (example conversation or quiz)
- schedule_demo_call: Schedule a live demo call with our team
- send_pricing: Send pricing information
- set_followup: Schedule a follow-up reminder

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ABSOLUTE RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. NEVER be pushy or aggressive. Consultative selling only.
2. NEVER make up data or statistics you don't have.
3. NEVER promise features that don't exist.
4. NEVER speak English unless the lead speaks English first.
5. ALWAYS ask before sending pricing — don't dump it unsolicited.
6. ALWAYS respond to what the lead said before advancing the flow.
7. Keep messages SHORT. This is WhatsApp, not email.
8. If the lead is not interested, be gracious: "Sem problema! Se mudar de ideia, estou por aqui."
"""

# --------------------------------------------------
# Tools do SDR
# --------------------------------------------------

SDR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "qualify_lead",
            "description": (
                "Save or update lead qualification data. Use as you learn information about the lead "
                "during conversation. Call multiple times as you gather more info."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Lead's name.",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["school_owner", "coordinator", "independent_teacher", "other"],
                        "description": "Type of lead.",
                    },
                    "school_name": {
                        "type": "string",
                        "description": "Name of the school (if applicable).",
                    },
                    "student_count": {
                        "type": "integer",
                        "description": "Approximate number of students.",
                    },
                    "main_pain": {
                        "type": "string",
                        "description": "Their main challenge or pain point.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["new", "qualifying", "interested", "trial", "closed_won", "closed_lost"],
                        "description": "Current status in the pipeline.",
                    },
                    "source": {
                        "type": "string",
                        "description": "How they found us (instagram, ad, referral, etc.).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_demo",
            "description": (
                "Send a product demonstration to the lead. This sends an example quiz/poll "
                "showing how the English tutor agent works. Use when the lead wants to see it in action."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "demo_type": {
                        "type": "string",
                        "enum": ["quiz", "conversation_example", "pronunciation_example"],
                        "description": "Type of demo to send.",
                    },
                },
                "required": ["demo_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_demo_call",
            "description": (
                "Schedule a live demo call with our team. "
                "Use when the lead agrees to see a demonstration of the product."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "preferred_date": {
                        "type": "string",
                        "description": "Preferred date and time for the call (natural language, e.g. 'terça às 14h').",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Any specific questions or topics the lead wants to discuss on the call.",
                    },
                },
                "required": ["preferred_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_pricing",
            "description": (
                "Send pricing information to the lead. Only use when the lead asks about pricing "
                "or after you've demonstrated value."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_followup",
            "description": (
                "Schedule a follow-up reminder for this lead. Use when the lead needs time to think, "
                "goes silent, or asks to be contacted later."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days until follow-up (1, 3, or 7).",
                        "enum": [1, 3, 7],
                    },
                    "note": {
                        "type": "string",
                        "description": "Context for the follow-up (what to mention).",
                    },
                },
                "required": ["days"],
            },
        },
    },
]

# --------------------------------------------------
# Textos de demo pré-montados
# --------------------------------------------------

DEMO_QUIZ = {
    "question": "What's the past tense of 'go'?",
    "options": ["went", "goed", "goned", "has go"],
}

DEMO_CONVERSATION = """Exemplo de conversa real entre o agente e um aluno:

*Aluno*: I goed to the beach yesterday with my friends
*Agente*: Oh, you went to the beach! That sounds amazing! Was it sunny? I love beach days.
*Aluno*: Yes it was very hot! We stayed all day
*Agente*: All day? Nice! Did you swim or just relax on the sand?

Percebeu? O aluno errou "goed" e o agente corrigiu naturalmente para "went" sem parar a conversa. O aluno nem percebe que foi corrigido."""

DEMO_PRONUNCIATION = """Como funciona a correção de pronúncia:

1. O aluno manda um ÁUDIO no WhatsApp
2. A IA analisa a pronúncia em tempo real (fonema por fonema)
3. Identifica erros comuns de brasileiros (TH, vogais, R americano)
4. Responde naturalmente, corrigindo sem constrangimento

Tudo acontece automaticamente. O aluno pratica e melhora sem perceber que está sendo avaliado."""

PRICING_TEXT = """Nossos planos:

*Starter* — R$ 197/mês
Para professores autônomos. Até 30 alunos.

*Pro* — R$ 497/mês
Para escolas pequenas. Até 100 alunos. Inclui agente de captação (SDR) e relatórios.

*Business* — R$ 997/mês
Para escolas médias/grandes. Até 300 alunos. Tudo do Pro + personalização avançada.

*Enterprise* — Sob consulta
Para franquias e redes. Alunos ilimitados.

Todos incluem: agente professor completo, painel admin e suporte por WhatsApp. Agende uma demo gratuita para ver o produto funcionando ao vivo."""


class SDRAgent:
    """Agente SDR que qualifica leads e vende o produto via WhatsApp."""

    def __init__(
        self,
        supabase_client,
        openai_client: AsyncOpenAI,
        uazapi_service=None,
    ):
        self._db = supabase_client
        self._openai = openai_client
        self._uazapi = uazapi_service
        self._model = "gpt-4.1-mini"
        self._settings_cache = None
        self._settings_cached_at = 0
        self._settings_ttl = 60

    # --------------------------------------------------
    # Settings
    # --------------------------------------------------

    async def _get_settings(self) -> dict:
        """Carrega settings do agent_settings."""
        now = time.time()
        if self._settings_cache and (now - self._settings_cached_at) < self._settings_ttl:
            return self._settings_cache

        result = await self._db.table("agent_settings").select("*").eq("id", 1).execute()
        if result.data:
            self._settings_cache = result.data[0]
        else:
            self._settings_cache = {"agent_name": "Luna"}
        self._settings_cached_at = now
        return self._settings_cache

    # --------------------------------------------------
    # Conversation history (tabela separada para leads)
    # --------------------------------------------------

    async def _load_history(self, phone: str, limit: int = 30) -> list[dict]:
        result = (
            await self._db.table("sdr_conversation_history")
            .select("role, content")
            .eq("phone", phone)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [{"role": r["role"], "content": r["content"]} for r in reversed(result.data)]

    async def _save_message(self, phone: str, role: str, content: str, metadata: dict = None):
        await self._db.table("sdr_conversation_history").insert(
            {"phone": phone, "role": role, "content": content, "metadata": metadata or {}}
        ).execute()

    # --------------------------------------------------
    # Tool execution
    # --------------------------------------------------

    async def _execute_tool(self, phone: str, tool_name: str, args: dict) -> str:
        if tool_name == "qualify_lead":
            # Upsert lead data
            lead_data = {"phone": phone}
            for field in ["name", "type", "school_name", "student_count", "main_pain", "status", "source"]:
                if field in args:
                    lead_data[field] = args[field]

            await self._db.table("sdr_leads").upsert(lead_data, on_conflict="phone").execute()
            return json.dumps({"saved": True, "data": lead_data})

        if tool_name == "send_demo":
            demo_type = args.get("demo_type", "quiz")

            if demo_type == "quiz" and self._uazapi:
                try:
                    await self._uazapi.send_poll(
                        phone=phone,
                        question=DEMO_QUIZ["question"],
                        options=DEMO_QUIZ["options"],
                    )
                    return json.dumps({"sent": True, "type": "quiz"})
                except Exception as e:
                    logger.error(f"Failed to send demo quiz: {e}")

            if demo_type == "conversation_example":
                if self._uazapi:
                    await self._uazapi.send_text(phone, DEMO_CONVERSATION)
                return json.dumps({"sent": True, "type": "conversation_example"})

            if demo_type == "pronunciation_example":
                if self._uazapi:
                    await self._uazapi.send_text(phone, DEMO_PRONUNCIATION)
                return json.dumps({"sent": True, "type": "pronunciation_example"})

            return json.dumps({"sent": False, "error": "Unknown demo type"})

        if tool_name == "schedule_demo_call":
            call_data = {
                "phone": phone,
                "preferred_date": args.get("preferred_date", ""),
                "notes": args.get("notes", ""),
                "status": "scheduled",
            }
            await self._db.table("sdr_demo_calls").insert(call_data).execute()
            # Update lead status
            await self._db.table("sdr_leads").upsert(
                {"phone": phone, "status": "demo_scheduled"}, on_conflict="phone"
            ).execute()
            return json.dumps({"scheduled": True, "data": call_data})

        if tool_name == "send_pricing":
            if self._uazapi:
                await self._uazapi.send_text(phone, PRICING_TEXT)
            return json.dumps({"sent": True})

        if tool_name == "set_followup":
            followup_data = {
                "phone": phone,
                "days": args.get("days", 1),
                "note": args.get("note", ""),
                "status": "pending",
            }
            await self._db.table("sdr_followups").insert(followup_data).execute()
            return json.dumps({"scheduled": True, "data": followup_data})

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    # --------------------------------------------------
    # Processar mensagem
    # --------------------------------------------------

    async def process_message(self, phone: str, text: str, push_name: str = "Lead") -> str:
        """Processa mensagem de um lead e retorna a resposta do SDR."""
        settings = await self._get_settings()

        await self._save_message(phone, "user", text)

        history = await self._load_history(phone)

        agent_name = settings.get("agent_name", "Luna")
        system_prompt = SDR_SYSTEM_PROMPT.replace("{agent_name}", agent_name)
        system_prompt += f"\n\nLead name: {push_name}"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)

        response = await self._openai.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=SDR_TOOLS,
            tool_choice="auto",
            max_tokens=400,
            temperature=0.7,
        )

        assistant_msg = response.choices[0].message

        # Handle tool calls
        if assistant_msg.tool_calls:
            tool_call = assistant_msg.tool_calls[0]
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            logger.info(f"SDR Tool call: {tool_name}({tool_args})")

            tool_result = await self._execute_tool(phone, tool_name, tool_args)

            messages.append(assistant_msg.model_dump())
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            })

            response2 = await self._openai.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=400,
                temperature=0.7,
            )
            reply = response2.choices[0].message.content.strip()
        else:
            reply = assistant_msg.content.strip()

        await self._save_message(phone, "assistant", reply)
        return reply
