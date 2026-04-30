"""
Shared dependencies for API routes.
"""

from functools import lru_cache
from app.config import get_settings


@lru_cache()
def get_llm_info() -> dict:
    """Get current LLM configuration info."""
    settings = get_settings()
    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "has_key": bool(settings.groq_api_key or settings.openai_api_key),
    }
