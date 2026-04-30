"""
Application configuration via pydantic-settings.
Loads from .env file automatically.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration
    llm_provider: str = "groq"  # "groq" or "openai"
    llm_model: str = "llama-3.3-70b-versatile"

    # API Keys
    groq_api_key: str = ""
    openai_api_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # Analysis
    max_log_lines: int = 5000
    max_log_size_mb: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
