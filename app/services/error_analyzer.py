from app.models import PronunciationResult, BrazilianError, ErrorAnalysis


# ============================================
# MAPA DE FONEMAS PROBLEMÁTICOS PARA BRASILEIROS
# ============================================

BRAZILIAN_PHONEME_ISSUES = {
    # TH surdo (θ) - think, thought, three
    "θ": {
        "name": "TH surdo",
        "common_substitution": "T, F ou S",
        "tip": "Coloque a língua ENTRE os dentes superiores e inferiores, e sopre ar. Não é T nem F!",
        "practice_words": ["think", "thought", "three", "through", "thank"],
        "visual_tip": "👅 Língua pra fora, entre os dentes!"
    },
    
    # TH sonoro (ð) - this, that, the
    "ð": {
        "name": "TH sonoro",
        "common_substitution": "D ou Z",
        "tip": "Igual ao TH de 'think', mas com vibração nas cordas vocais. Sinta a vibração no pescoço!",
        "practice_words": ["this", "that", "the", "there", "they", "mother"],
        "visual_tip": "👅 Língua entre os dentes + vibração!"
    },
    
    # Vogal /æ/ - cat, bad, man
    "æ": {
        "name": "A aberto",
        "common_substitution": "É ou A fechado",
        "tip": "Abra bem a boca, como se fosse dizer 'É' e 'A' ao mesmo tempo. É mais aberto que o 'É' português!",
        "practice_words": ["cat", "bad", "man", "hat", "sat", "back"],
        "visual_tip": "😮 Boca bem aberta, quase como 'É'!"
    },
    
    # Vogal /ɪ/ - bit, sit, ship
    "ɪ": {
        "name": "I curto",
        "common_substitution": "I longo (ii)",
        "tip": "É um 'I' mais relaxado e curto, entre 'I' e 'E'. Não alongue! Pense em 'bit' = quase 'bet'.",
        "practice_words": ["bit", "sit", "ship", "live", "give", "this"],
        "visual_tip": "😊 I relaxado, não sorria tanto!"
    },
    
    # Vogal /ʊ/ - put, book, good
    "ʊ": {
        "name": "U curto",
        "common_substitution": "U longo (uu)",
        "tip": "É um 'U' mais relaxado e curto. Não arredonde muito os lábios!",
        "practice_words": ["put", "book", "good", "look", "foot", "would"],
        "visual_tip": "👄 Lábios relaxados, U curto!"
    },
    
    # Vogal /ʌ/ - cup, but, love
    "ʌ": {
        "name": "Schwa acentuado",
        "common_substitution": "A ou Ô",
        "tip": "É como um 'Â' neutro, bem no meio da boca. Pense em 'cup' = entre 'cap' e 'cop'.",
        "practice_words": ["cup", "but", "love", "come", "some", "up"],
        "visual_tip": "😐 Som neutro, boca relaxada!"
    },
    
    # R americano /ɹ/
    "ɹ": {
        "name": "R americano",
        "common_substitution": "R brasileiro (vibrante ou gutural)",
        "tip": "Curve a língua para trás SEM tocar o céu da boca. É como um 'R' fantasma!",
        "practice_words": ["red", "run", "car", "more", "world", "girl"],
        "visual_tip": "👅 Língua curvada para trás, sem encostar!"
    },
    
    # NG final /ŋ/
    "ŋ": {
        "name": "NG final",
        "common_substitution": "N + G separados",
        "tip": "O som sai pelo nariz, como em 'cantar' sem o 'tar'. Não fale o G!",
        "practice_words": ["sing", "ring", "thing", "going", "running"],
        "visual_tip": "👃 Som nasal, sem G no final!"
    },
    
    # L final /l/
    "l": {
        "name": "L final",
        "common_substitution": "U",
        "tip": "Encoste a ponta da língua nos dentes superiores. Não transforme em 'U'!",
        "practice_words": ["call", "tall", "feel", "school", "people"],
        "visual_tip": "👅 Língua nos dentes, não vira U!"
    },
}


# ============================================
# SERVIÇO DE ANÁLISE
# ============================================

class BrazilianErrorAnalyzer:
    def __init__(self):
        self.phoneme_issues = BRAZILIAN_PHONEME_ISSUES
        self.threshold_bad = 60  # Abaixo disso = problema sério
        self.threshold_ok = 80   # Acima disso = OK
    
    def analyze(self, pronunciation_result: PronunciationResult) -> ErrorAnalysis:
        """
        Analisa resultado de pronúncia e identifica erros típicos de brasileiros
        """
        brazilian_errors = []
        
        for word in pronunciation_result.words:
            for phoneme in word.phonemes:
                # Verificar se é um fonema problemático para brasileiros
                if phoneme.phoneme in self.phoneme_issues:
                    if phoneme.accuracy_score < self.threshold_bad:
                        issue = self.phoneme_issues[phoneme.phoneme]
                        brazilian_errors.append(
                            BrazilianError(
                                word=word.word,
                                expected_phoneme=phoneme.phoneme,
                                accuracy=phoneme.accuracy_score,
                                tip=issue["tip"],
                                practice_words=issue["practice_words"][:3]  # Limitar a 3
                            )
                        )
        
        # Identificar o problema principal (o mais frequente ou mais grave)
        main_issue = self._identify_main_issue(brazilian_errors)
        
        # Determinar nível de encorajamento
        overall_score = pronunciation_result.overall_score
        if overall_score >= 85:
            encouragement = "great"
        elif overall_score >= 65:
            encouragement = "good"
        else:
            encouragement = "needs_work"
        
        return ErrorAnalysis(
            pronunciation_result=pronunciation_result,
            brazilian_errors=brazilian_errors,
            main_issue=main_issue,
            encouragement_level=encouragement
        )
    
    def _identify_main_issue(self, errors: list[BrazilianError]) -> str | None:
        """Identifica o problema mais importante para focar"""
        if not errors:
            return None
        
        # Contar frequência de cada fonema
        phoneme_counts = {}
        phoneme_worst_score = {}
        
        for error in errors:
            ph = error.expected_phoneme
            phoneme_counts[ph] = phoneme_counts.get(ph, 0) + 1
            if ph not in phoneme_worst_score or error.accuracy < phoneme_worst_score[ph]:
                phoneme_worst_score[ph] = error.accuracy
        
        # Priorizar: TH é o mais comum e impactante para brasileiros
        priority_order = ["θ", "ð", "æ", "ɪ", "ɹ", "ŋ", "ʊ", "ʌ", "l"]
        
        for phoneme in priority_order:
            if phoneme in phoneme_counts:
                return self.phoneme_issues[phoneme]["name"]
        
        # Se não for nenhum dos prioritários, retornar o mais frequente
        if phoneme_counts:
            most_common = max(phoneme_counts, key=phoneme_counts.get)
            if most_common in self.phoneme_issues:
                return self.phoneme_issues[most_common]["name"]
        
        return None
    
    def get_phoneme_tip(self, phoneme: str) -> dict | None:
        """Retorna dicas para um fonema específico"""
        return self.phoneme_issues.get(phoneme)
    
    def get_focus_recommendation(self, analysis: ErrorAnalysis) -> str:
        """Gera recomendação de foco para o aluno"""
        if not analysis.brazilian_errors:
            return "Excelente! Continue praticando para manter a fluência."
        
        # Agrupar erros por tipo
        error_types = {}
        for error in analysis.brazilian_errors:
            if error.expected_phoneme not in error_types:
                error_types[error.expected_phoneme] = []
            error_types[error.expected_phoneme].append(error)
        
        # Recomendar focar no mais problemático
        if len(error_types) == 1:
            phoneme = list(error_types.keys())[0]
            tip = self.phoneme_issues.get(phoneme, {})
            return f"Foque no som {tip.get('name', phoneme)}: {tip.get('tip', '')}"
        
        # Múltiplos problemas - focar no principal
        if analysis.main_issue:
            return f"Seu principal desafio é o som '{analysis.main_issue}'. Vamos trabalhar nele!"
        
        return "Continue praticando, você está no caminho certo!"
