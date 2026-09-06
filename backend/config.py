from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://killella:killella@localhost:5432/killella"
    database_url_sync: str = "postgresql://killella:killella@localhost:5432/killella"
    redis_url: str = "redis://localhost:6379"
    secret_key: str = "change-me-in-production"

    anthropic_api_key: str = ""
    openai_api_key: str = ""

    tts_voice: str = "en-US-GuyNeural"
    tts_voice_ella: str = "en-US-AriaNeural"

    rumble_live_stream_url: str = ""
    base_rpc_url: str = "https://mainnet.base.org"

    allowed_origins: list[str] = ["http://localhost:8000", "http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
