"""
Central configuration, loaded from environment variables.

Only ANTHROPIC_API_KEY is truly required. Everything else has a sane
default so the app can run locally out of the box.
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    # --- Required ---
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # --- Optional fallback search provider (only used if native web search
    #     tool is unavailable on the API key being used) ---
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    exa_api_key: str = os.getenv("EXA_API_KEY", "")
    force_fallback_search: bool = _bool_env("FORCE_FALLBACK_SEARCH", False)

    # --- Models ---
    # Primary agent model (tool use, synthesis).
    agent_model: str = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
    # Cheap/fast model for the router classification step and for the
    # grounding verification pass.
    router_model: str = os.getenv("ROUTER_MODEL", "claude-haiku-4-5-20251001")
    grounding_model: str = os.getenv("GROUNDING_MODEL", "claude-haiku-4-5-20251001")
    judge_model: str = os.getenv("JUDGE_MODEL", "claude-sonnet-4-6")

    # --- Tool selection strategy: "agentic" | "router" ---
    tool_strategy: str = os.getenv("TOOL_STRATEGY", "router")

    # --- Web search ---
    web_search_max_uses: int = int(os.getenv("WEB_SEARCH_MAX_USES", "5"))

    # --- Guardrails / rate limiting ---
    rate_limit_requests_per_minute: int = int(
        os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "10")
    )
    rate_limit_requests_per_day: int = int(
        os.getenv("RATE_LIMIT_REQUESTS_PER_DAY", "200")
    )
    max_question_length: int = int(os.getenv("MAX_QUESTION_LENGTH", "500"))

    # --- Cost tracking (USD per token, approximate, updated periodically) ---
    # These are illustrative list prices; override via env if pricing changes.
    price_per_1m_input_tokens: dict[str, float] = {
        "claude-sonnet-4-6": 3.0,
        "claude-haiku-4-5-20251001": 0.80,
        "claude-opus-4-8": 15.0,
    }
    price_per_1m_output_tokens: dict[str, float] = {
        "claude-sonnet-4-6": 15.0,
        "claude-haiku-4-5-20251001": 4.0,
        "claude-opus-4-8": 75.0,
    }
    price_per_1k_web_searches: float = float(
        os.getenv("PRICE_PER_1K_WEB_SEARCHES", "10.0")
    )

    # --- Logging ---
    log_dir: str = os.getenv("LOG_DIR", "./logs")

    model_config = {"arbitrary_types_allowed": True}


@lru_cache
def get_settings() -> Settings:
    return Settings()
