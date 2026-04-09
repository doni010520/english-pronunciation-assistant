import httpx
import tempfile
import os
from pathlib import Path

from app.config import get_settings


class UazapiService:
    def __init__(self, base_url: str = None, token: str = None):
        settings = get_settings()
        self.base_url = (base_url or settings.uazapi_base_url).rstrip("/")
        self.token = token or settings.uazapi_token
        self.headers = {"token": self.token}
    
    async def download_media(self, message_id: str, generate_mp3: bool = False) -> tuple[bytes, str]:
        """
        Baixa mídia de uma mensagem usando o endpoint /message/download.
        Funciona para áudio, imagem, vídeo, documento.
        Retorna: (bytes da mídia, mimetype)
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/message/download",
                headers=self.headers,
                json={
                    "id": message_id,
                    "return_base64": True,
                    "return_link": False,
                    "generate_mp3": generate_mp3,
                    "transcribe": False,
                }
            )
            response.raise_for_status()
            data = response.json()

            mimetype = data.get("mimetype", "application/octet-stream")

            # Tentar base64 primeiro, depois URL
            if data.get("base64Data"):
                import base64
                media_bytes = base64.b64decode(data["base64Data"])
            elif data.get("fileURL"):
                media_response = await client.get(data["fileURL"])
                media_response.raise_for_status()
                media_bytes = media_response.content
            else:
                raise ValueError("Resposta da Uazapi não contém mídia")

            return media_bytes, mimetype

    async def download_audio(self, message_id: str) -> tuple[bytes, str]:
        """Baixa áudio em OGG (formato nativo do WhatsApp)"""
        return await self.download_media(message_id, generate_mp3=False)

    async def download_image(self, message_id: str) -> tuple[bytes, str]:
        """Baixa imagem de uma mensagem"""
        return await self.download_media(message_id)
    
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
        """Envia áudio via URL (ptt = push to talk, aparece como gravação de voz)"""
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

    async def send_voice(
        self,
        phone: str,
        audio_base64: str,
        reply_to: str = None,
    ) -> dict:
        """Envia áudio base64 como mensagem de voz (PTT)."""
        import base64 as b64mod

        payload = {
            "number": phone,
            "type": "ptt",
            "file": f"data:audio/mp3;base64,{audio_base64}",
        }
        if reply_to:
            payload["replyid"] = reply_to

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/send/media",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
    
    async def send_poll(
        self,
        phone: str,
        question: str,
        options: list[str],
        selectable_count: int = 1,
    ) -> dict:
        """Envia enquete/poll interativa no WhatsApp via /send/menu type poll."""
        payload = {
            "number": phone,
            "type": "poll",
            "name": question,
            "options": options,
            "selectableCount": selectable_count,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/send/menu",
                headers=self.headers,
                json=payload,
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
