import httpx
import tempfile
import os
from pathlib import Path

from app.config import get_settings


class UazapiService:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.uazapi_base_url.rstrip("/")
        self.token = settings.uazapi_token
        self.headers = {"token": self.token}
    
    async def download_audio(self, message_id: str) -> tuple[bytes, str]:
        """
        Baixa áudio de uma mensagem usando o endpoint /message/download
        Retorna: (bytes do áudio, transcription se houver)
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/message/download",
                headers=self.headers,
                json={
                    "id": message_id,
                    "transcribe": False  # Não usar Whisper da Uazapi, vamos usar Azure
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # O áudio vem em base64 ou URL dependendo da config
            if "base64" in data:
                import base64
                audio_bytes = base64.b64decode(data["base64"])
            elif "url" in data:
                # Baixa do URL
                audio_response = await client.get(data["url"])
                audio_bytes = audio_response.content
            else:
                raise ValueError("Resposta da Uazapi não contém áudio")
            
            return audio_bytes, data.get("mimetype", "audio/ogg")
    
    async def send_text(
        self, 
        phone: str, 
        text: str, 
        reply_to: str = None
    ) -> dict:
        """Envia mensagem de texto"""
        payload = {
            "number": phone,
            "text": text,
            "delay": 0
        }
        if reply_to:
            payload["replyid"] = reply_to
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/send/text",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
    
    async def send_audio(
        self, 
        phone: str, 
        audio_url: str,
        ptt: bool = True
    ) -> dict:
        """Envia áudio (ptt = push to talk, aparece como gravação de voz)"""
        payload = {
            "number": phone,
            "type": "ptt" if ptt else "audio",
            "file": audio_url,
            "delay": 0
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/send/media",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
    
    async def send_presence(self, phone: str, presence: str = "recording"):
        """
        Envia indicador de presença (digitando ou gravando)
        presence: "composing" (digitando) ou "recording" (gravando áudio)
        """
        payload = {
            "number": phone,
            "presence": presence,
            "delay": 3000
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                await client.post(
                    f"{self.base_url}/message/presence",
                    headers=self.headers,
                    json=payload
                )
            except Exception:
                pass  # Presença é opcional, não precisa falhar


def extract_phone_from_jid(jid: str) -> str:
    """Extrai número de telefone do JID do WhatsApp"""
    # JID format: 5511999999999@s.whatsapp.net
    return jid.split("@")[0]
