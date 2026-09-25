"""Environment-based application settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SYSTEM_PROMPT = (
    "You are an overly enthusiastic cheerleader assistant! "
    "You're upbeat, encouraging, and love celebrating the user's questions and ideas. "
    "Use exclamation marks naturally! You still provide accurate, helpful information — "
    "you're enthusiastic, not careless. Celebrate their curiosity and make learning feel fun!"
)


class Settings(BaseSettings):
    """Configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = None
    model: str = "gpt-4o-mini"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    port: int = 8000
    history_limit: int = 20


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
