import azure.cognitiveservices.speech as speechsdk
import tempfile
import json
import asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from app.config import get_settings
from app.models import PronunciationResult, WordAssessment, PhonemeAssessment


# Executor para rodar código síncrono do Azure SDK
_executor = ThreadPoolExecutor(max_workers=4)


class AzureSpeechService:
    def __init__(self):
        settings = get_settings()
        self.speech_key = settings.azure_speech_key
        self.speech_region = settings.azure_speech_region
    
    def _create_speech_config(self) -> speechsdk.SpeechConfig:
        """Cria configuração do Azure Speech"""
        config = speechsdk.SpeechConfig(
            subscription=self.speech_key,
            region=self.speech_region
        )
        config.speech_recognition_language = "en-US"
        return config
    
    def _assess_pronunciation_sync(
        self, 
        audio_path: str, 
        reference_text: str
    ) -> dict:
        """
        Avalia pronúncia de forma síncrona (chamado via executor)
        """
        speech_config = self._create_speech_config()
        
        # Configurar áudio do arquivo
        audio_config = speechsdk.audio.AudioConfig(filename=audio_path)
        
        # Configurar avaliação de pronúncia
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=reference_text,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue=True
        )
        
        # Criar reconhecedor
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config
        )
        
        # Aplicar configuração de pronúncia
        pronunciation_config.apply_to(recognizer)
        
        # Reconhecer
        result = recognizer.recognize_once()
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            # Extrair JSON de avaliação de pronúncia
            pronunciation_result = speechsdk.PronunciationAssessmentResult(result)
            
            return {
                "success": True,
                "transcription": result.text,
                "overall_score": pronunciation_result.pronunciation_score,
                "accuracy_score": pronunciation_result.accuracy_score,
                "fluency_score": pronunciation_result.fluency_score,
                "completeness_score": pronunciation_result.completeness_score,
                "words": self._extract_word_details(result)
            }
        
        elif result.reason == speechsdk.ResultReason.NoMatch:
            return {
                "success": False,
                "error": "Não foi possível reconhecer a fala",
                "details": str(result.no_match_details)
            }
        
        else:
            return {
                "success": False,
                "error": f"Erro no reconhecimento: {result.reason}",
                "details": str(result.cancellation_details) if hasattr(result, 'cancellation_details') else None
            }
    
    def _extract_word_details(self, result) -> list[dict]:
        """Extrai detalhes de cada palavra e fonema"""
        words = []
        
        # Acessar JSON detalhado da avaliação
        json_result = result.properties.get(
            speechsdk.PropertyId.SpeechServiceResponse_JsonResult
        )
        
        if json_result:
            data = json.loads(json_result)
            
            # Navegar na estrutura do JSON
            if "NBest" in data and len(data["NBest"]) > 0:
                nbest = data["NBest"][0]
                
                if "Words" in nbest:
                    for word_data in nbest["Words"]:
                        phonemes = []
                        
                        if "Phonemes" in word_data:
                            for ph in word_data["Phonemes"]:
                                phonemes.append({
                                    "phoneme": ph.get("Phoneme", ""),
                                    "accuracy_score": ph.get("PronunciationAssessment", {}).get("AccuracyScore", 0)
                                })
                        
                        words.append({
                            "word": word_data.get("Word", ""),
                            "accuracy_score": word_data.get("PronunciationAssessment", {}).get("AccuracyScore", 0),
                            "error_type": word_data.get("PronunciationAssessment", {}).get("ErrorType", None),
                            "phonemes": phonemes
                        })
        
        return words
    
    async def assess_pronunciation(
        self, 
        audio_bytes: bytes, 
        reference_text: str,
        audio_format: str = "ogg"
    ) -> PronunciationResult:
        """
        Avalia pronúncia de um áudio
        
        Args:
            audio_bytes: Bytes do áudio
            reference_text: Texto que deveria ser falado
            audio_format: Formato do áudio (ogg, mp3, wav)
        
        Returns:
            PronunciationResult com scores e análise por palavra/fonema
        """
        # Salvar áudio em arquivo temporário
        with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as f:
            f.write(audio_bytes)
            temp_audio_path = f.name
        
        try:
            # Converter para WAV se necessário (Azure prefere WAV)
            wav_path = await self._convert_to_wav(temp_audio_path)
            
            # Rodar avaliação em thread separada (SDK é síncrono)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                _executor,
                self._assess_pronunciation_sync,
                wav_path,
                reference_text
            )
            
            if not result["success"]:
                raise Exception(result.get("error", "Erro desconhecido"))
            
            # Converter para modelo Pydantic
            words = [
                WordAssessment(
                    word=w["word"],
                    accuracy_score=w["accuracy_score"],
                    error_type=w.get("error_type"),
                    phonemes=[
                        PhonemeAssessment(
                            phoneme=p["phoneme"],
                            accuracy_score=p["accuracy_score"]
                        )
                        for p in w.get("phonemes", [])
                    ]
                )
                for w in result["words"]
            ]
            
            return PronunciationResult(
                overall_score=result["overall_score"],
                accuracy_score=result["accuracy_score"],
                fluency_score=result["fluency_score"],
                completeness_score=result["completeness_score"],
                words=words,
                transcription=result["transcription"]
            )
        
        finally:
            # Limpar arquivos temporários
            import os
            try:
                os.unlink(temp_audio_path)
                if 'wav_path' in locals() and wav_path != temp_audio_path:
                    os.unlink(wav_path)
            except Exception:
                pass
    
    async def _convert_to_wav(self, input_path: str) -> str:
        """Converte áudio para WAV 16kHz mono (formato ideal para Azure)"""
        from pydub import AudioSegment
        
        output_path = input_path.rsplit(".", 1)[0] + ".wav"
        
        # Detectar formato pelo conteúdo
        try:
            if input_path.endswith(".ogg"):
                audio = AudioSegment.from_ogg(input_path)
            elif input_path.endswith(".mp3"):
                audio = AudioSegment.from_mp3(input_path)
            elif input_path.endswith(".wav"):
                audio = AudioSegment.from_wav(input_path)
            else:
                # Tentar detectar automaticamente
                audio = AudioSegment.from_file(input_path)
            
            # Converter para formato Azure: 16kHz, mono, 16-bit
            audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            audio.export(output_path, format="wav")
            
            return output_path
        
        except Exception as e:
            raise Exception(f"Erro ao converter áudio: {str(e)}")
