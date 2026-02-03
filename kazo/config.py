from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    telegram_bot_token: str
    allowed_chat_ids: list[int] = []

    @field_validator("allowed_chat_ids", mode="before")
    @classmethod
    def parse_chat_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return v

    anthropic_api_key: str | None = None
    base_currency: str = "EUR"
    db_path: str = "kazo.db"
    claude_model: str = "sonnet"
    claude_timeout: int = 60
    rate_limit_per_hour: int = 30
    debug: bool = False
    health_check_port: int = 8080
    exchange_rate_url: str = Field(
        default="https://open.er-api.com/v6/latest",
        validation_alias="frankfurter_url",
    )
    exchange_rate_cache_hours: int = 24


settings = Settings()
