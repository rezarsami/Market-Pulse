"""
Thin wrapper around the Anthropic SDK client that adds retry with
exponential backoff for transient errors (rate limits, timeouts,
5xx/overload). Kept separate from agent logic so retry policy lives in
exactly one place.
"""
from __future__ import annotations

import logging
import random
import time

import anthropic

from app.config import get_settings

logger = logging.getLogger("market_pulse")

_RETRYABLE_EXCEPTIONS = (
    anthropic.RateLimitError,
    anthropic.APITimeoutError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
)

_MAX_RETRIES = 4
_BASE_DELAY_SECONDS = 1.0


def get_client() -> anthropic.Anthropic:
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. See .env.example for required configuration."
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def create_message_with_retry(client: anthropic.Anthropic, **kwargs):
    """
    Call client.messages.create with exponential backoff + jitter on
    transient errors. Non-transient errors (bad request, auth, etc.)
    propagate immediately.
    """
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return client.messages.create(**kwargs)
        except _RETRYABLE_EXCEPTIONS as e:
            last_exc = e
            delay = _BASE_DELAY_SECONDS * (2**attempt) + random.uniform(0, 0.5)
            logger.warning(
                f"Transient Anthropic API error on attempt {attempt + 1}/{_MAX_RETRIES}: "
                f"{type(e).__name__}: {e}. Retrying in {delay:.2f}s"
            )
            if attempt < _MAX_RETRIES - 1:
                time.sleep(delay)
        except anthropic.APIStatusError as e:
            # 400-level errors that aren't rate limits are not retryable.
            if e.status_code in (429, 529) and attempt < _MAX_RETRIES - 1:
                delay = _BASE_DELAY_SECONDS * (2**attempt) + random.uniform(0, 0.5)
                logger.warning(
                    f"Retryable API status {e.status_code} on attempt {attempt + 1}. "
                    f"Retrying in {delay:.2f}s"
                )
                time.sleep(delay)
                last_exc = e
                continue
            raise
    raise last_exc  # exhausted retries
