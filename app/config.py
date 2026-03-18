from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Uazapi
    uazapi_base_url: str
    uazapi_token: str
    
    # Azure Speech
    azure_speech_key: str
    azure_speech_region: str = "eastus"
    
    # OpenAI
    openai_api_key: str
    
    # ElevenLabs (opcional)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
