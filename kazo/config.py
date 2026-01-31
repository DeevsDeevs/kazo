from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    telegram_bot_token: str
    allowed_chat_ids: list[int] = []
    db_path: str = "kazo.db"
    claude_model: str = "sonnet"
    claude_timeout: int = 60
    frankfurter_url: str = "https://api.frankfurter.dev/v1/latest"
    exchange_rate_cache_hours: int = 24


settings = Settings()
