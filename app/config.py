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
    
    # Supabase
    supabase_url: str
    supabase_key: str

    # ElevenLabs (opcional)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    
    # Uazapi SDR (separate WhatsApp number for sales)
    uazapi_sdr_base_url: str = ""
    uazapi_sdr_token: str = ""

    # Redis
    redis_url: str = ""

    # Admin
    admin_token: str = "change-me-in-production"

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
