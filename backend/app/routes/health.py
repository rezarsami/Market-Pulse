from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "anthropic_key_configured": bool(settings.anthropic_api_key),
        "fallback_search_configured": bool(
            settings.tavily_api_key or settings.exa_api_key
        ),
        "default_tool_strategy": settings.tool_strategy,
        "agent_model": settings.agent_model,
    }
