"""
Input sanitization and a lightweight prompt-injection heuristic.

This is deliberately NOT a claim of robust jailbreak defense -- pattern
matching on strings is a shallow layer. It exists to catch the obvious,
common cases cheaply before the request ever reaches the model, and to
demonstrate that untrusted user input is treated as untrusted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MAX_TICKER_LENGTH = 10
MAX_QUESTION_LENGTH_DEFAULT = 500

# Common prompt-injection phrasing. Case-insensitive, substring-based.
# This list is intentionally short and legible -- it's a heuristic tripwire,
# not a security boundary.
_INJECTION_PATTERNS = [
    r"ignore (all|the|any|previous|prior|above) instructions",
    r"disregard (all|the|any|previous|prior|above) instructions",
    r"reveal (your|the) system prompt",
    r"show (me )?(your|the) system prompt",
    r"you are now",
    r"new instructions[:\s]",
    r"act as (if )?(a |an )?(unrestricted|jailbroken|dan)",
    r"pretend (you|to) (have no|bypass)",
    r"forget (everything|all) (you|above)",
    r"override (your|the) (guidelines|rules|instructions)",
    r"\bsystem\s*:\s*",  # attempt to inject a fake system turn
    r"<\s*system\s*>",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

_TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,10}$")


@dataclass
class SanitizeResult:
    ok: bool
    reason: str = ""
    cleaned: str = ""


def sanitize_ticker(raw: str) -> SanitizeResult:
    if raw is None:
        return SanitizeResult(ok=False, reason="ticker is required")
    ticker = raw.strip().upper()
    if not ticker:
        return SanitizeResult(ok=False, reason="ticker must not be empty")
    if len(ticker) > MAX_TICKER_LENGTH:
        return SanitizeResult(ok=False, reason="ticker too long")
    if not _TICKER_RE.match(ticker):
        return SanitizeResult(
            ok=False,
            reason="ticker must be alphanumeric (plus . or -), max 10 chars",
        )
    return SanitizeResult(ok=True, cleaned=ticker)


def sanitize_question(
    raw: str | None, max_length: int = MAX_QUESTION_LENGTH_DEFAULT
) -> SanitizeResult:
    if raw is None or raw.strip() == "":
        return SanitizeResult(ok=True, cleaned="")
    q = raw.strip()
    if len(q) > max_length:
        return SanitizeResult(
            ok=False, reason=f"question exceeds max length of {max_length} chars"
        )
    if _INJECTION_RE.search(q):
        return SanitizeResult(
            ok=False,
            reason="question matched a prompt-injection heuristic pattern and was rejected",
        )
    return SanitizeResult(ok=True, cleaned=q)


def looks_like_injection(text: str) -> bool:
    """Standalone helper usable on arbitrary text (e.g. before logging)."""
    if not text:
        return False
    return bool(_INJECTION_RE.search(text))
