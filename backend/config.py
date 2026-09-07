from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://freak_town:freak_town@localhost:5432/freak_town"
    database_url_sync: str = "postgresql://freak_town:freak_town@localhost:5432/freak_town"
    redis_url: str = "redis://localhost:6379"
    secret_key: str = "change-me-in-production"

    domain: str = "kill.town"

    anthropic_api_key: str = ""
    openai_api_key: str = ""

    tts_voice: str = "en-US-GuyNeural"
    tts_voice_ella: str = "en-US-AriaNeural"

    rumble_live_stream_url: str = ""
    base_rpc_url: str = "https://mainnet.base.org"

    # Cloudflare R2
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_s3_endpoint: str = ""
    r2_bucket: str = "freak-town"

    allowed_origins: list[str] = ["http://localhost:8000", "http://localhost:3000"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
