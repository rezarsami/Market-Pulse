"""
Fallback search tool for when Anthropic's native web_search server tool is
not available on the API key in use (e.g. an older key, or an org that has
disabled it). Implements the same conceptual call signature -- a ticker +
query in, a list of {title, url, snippet, published_at} results out -- so
the rest of the agent architecture (tool loop, structured output, grounding
pass) does not need to change based on which search backend is active.

Tries Tavily first (if TAVILY_API_KEY set), then Exa (if EXA_API_KEY set).
Both are search APIs purpose-built for LLM agents, not general scraping.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from app.config import get_settings

logger = logging.getLogger("market_pulse")


@dataclass
class FallbackSearchResult:
    title: str
    url: str
    snippet: str
    published_at: str = ""


@dataclass
class FallbackSearchResponse:
    query: str
    results: list[FallbackSearchResult] = field(default_factory=list)
    provider: str = ""
    error: str | None = None


def _search_tavily(query: str, api_key: str, max_results: int = 6) -> FallbackSearchResponse:
    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": False,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results = [
            FallbackSearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", "")[:1000],
                published_at=r.get("published_date", "") or "",
            )
            for r in data.get("results", [])
        ]
        return FallbackSearchResponse(query=query, results=results, provider="tavily")
    except Exception as e:
        logger.warning(f"Tavily search failed: {e}")
        return FallbackSearchResponse(query=query, provider="tavily", error=str(e))


def _search_exa(query: str, api_key: str, max_results: int = 6) -> FallbackSearchResponse:
    try:
        resp = httpx.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={
                "query": query,
                "numResults": max_results,
                "type": "auto",
                "contents": {"text": {"maxCharacters": 1000}},
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results = [
            FallbackSearchResult(
                title=r.get("title", "") or "",
                url=r.get("url", ""),
                snippet=(r.get("text") or "")[:1000],
                published_at=r.get("publishedDate", "") or "",
            )
            for r in data.get("results", [])
        ]
        return FallbackSearchResponse(query=query, results=results, provider="exa")
    except Exception as e:
        logger.warning(f"Exa search failed: {e}")
        return FallbackSearchResponse(query=query, provider="exa", error=str(e))


def fallback_search(query: str, max_results: int = 6) -> FallbackSearchResponse:
    settings = get_settings()
    if settings.tavily_api_key:
        result = _search_tavily(query, settings.tavily_api_key, max_results)
        if not result.error:
            return result
    if settings.exa_api_key:
        result = _search_exa(query, settings.exa_api_key, max_results)
        if not result.error:
            return result
    return FallbackSearchResponse(
        query=query,
        provider="none",
        error=(
            "No working fallback search provider configured. Set TAVILY_API_KEY "
            "or EXA_API_KEY in the environment."
        ),
    )
