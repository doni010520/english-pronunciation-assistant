from openai import AsyncOpenAI

from app.config import get_settings
from app.models import ErrorAnalysis


class FeedbackGenerator:
    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4.1-mini"
    
    async def generate_feedback(
        self, 
        analysis: ErrorAnalysis,
        student_name: str = None,
        attempt_number: int = 1
    ) -> str:
        """
        Gera feedback humanizado e pedagógico para o aluno
        """
        # Preparar contexto
        result = analysis.pronunciation_result
        errors = analysis.brazilian_errors
        
        # Formatar erros para o prompt
        errors_text = ""
        if errors:
            errors_text = "\n".join([
                f"- Palavra '{e.word}': fonema /{e.expected_phoneme}/ com score {e.accuracy:.0f}/100"
                for e in errors[:5]  # Limitar a 5 erros
            ])
        else:
            errors_text = "Nenhum erro significativo detectado"
        
        # Determinar tom baseado no score
        if analysis.encouragement_level == "great":
            tone_instruction = "Tom: muito entusiasmado e congratulatório"
        elif analysis.encouragement_level == "good":
            tone_instruction = "Tom: encorajador e positivo, com dicas construtivas"
        else:
            tone_instruction = "Tom: gentil e motivador, sem desmotivar"
        
        prompt = f"""Você é um professor de inglês especializado em ajudar brasileiros com pronúncia.
Gere um feedback em português para o aluno sobre sua pronúncia.

CONTEXTO:
- Nome do aluno: {student_name or 'Aluno'}
- Tentativa número: {attempt_number}
- Frase praticada: "{result.transcription}"
- Score geral: {result.overall_score:.0f}/100
- Score de precisão: {result.accuracy_score:.0f}/100
- Score de fluência: {result.fluency_score:.0f}/100
- Score de completude: {result.completeness_score:.0f}/100

ERROS IDENTIFICADOS:
{errors_text}

PRINCIPAL DESAFIO: {analysis.main_issue or 'Nenhum específico'}

INSTRUÇÕES:
1. {tone_instruction}
2. Comece com algo positivo sobre o esforço ou progresso
3. Foque em NO MÁXIMO 1 erro para corrigir (o mais importante)
4. Dê uma dica prática e memorável, usando comparações com português
5. Termine com encorajamento
6. Use emojis moderadamente (2-3 no máximo)
7. Máximo 5 linhas - seja direto e útil
8. Se o score for acima de 85, apenas parabenize sem focar em erros

FORMATO: Texto corrido, como uma mensagem de WhatsApp de um professor amigo."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Você é um professor de inglês amigável e especializado em brasileiros."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    
    async def generate_practice_phrase(
        self, 
        difficulty: str = "intermediate",
        focus_phoneme: str = None
    ) -> str:
        """
        Gera uma frase para o aluno praticar
        """
        focus_instruction = ""
        if focus_phoneme:
            focus_instruction = f"A frase deve conter várias palavras com o som /{focus_phoneme}/."
        
        prompt = f"""Gere UMA frase em inglês para um brasileiro praticar pronúncia.

Nível: {difficulty}
{focus_instruction}

Requisitos:
- 5 a 10 palavras
- Frase natural e útil no dia a dia
- Sem vocabulário muito técnico
- Retorne APENAS a frase em inglês, sem tradução ou explicação"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.9
        )
        
        return response.choices[0].message.content.strip()
    
    async def generate_encouragement(self, score: float, previous_score: float = None) -> str:
        """
        Gera mensagem de encorajamento baseada no progresso
        """
        if previous_score and score > previous_score:
            improvement = score - previous_score
            return f"🎉 Você melhorou {improvement:.0f} pontos! De {previous_score:.0f} para {score:.0f}!"
        elif score >= 90:
            return "🌟 Pronúncia excelente! Você está quase nativo!"
        elif score >= 75:
            return "👏 Muito bom! Continue assim!"
        elif score >= 60:
            return "💪 Bom trabalho! A prática leva à perfeição!"
        else:
            return "🌱 Cada tentativa te deixa melhor! Vamos lá!"
