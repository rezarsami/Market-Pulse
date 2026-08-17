"""
Client-tool (non-server-tool) definitions in Anthropic Messages API format,
plus a dispatcher that executes them. `search_news` here is our *client*
tool used when native web search is unavailable and we fall back to
Tavily/Exa. When native web search IS available, we instead attach
Anthropic's server-side `web_search` tool directly (see agent/loop.py) and
this client-side `search_news` tool is omitted from the tool list.

`get_price_history` and `calculate` are always client tools -- Anthropic
doesn't have a server tool for either.
"""
from __future__ import annotations

CALCULATE_TOOL = {
    "name": "calculate",
    "description": (
        "Evaluate a pure arithmetic expression safely (e.g. percent change, "
        "ratios, differences). Supports + - * / // % ** and the functions "
        "abs, round, min, max, sqrt. Does NOT support variables, string "
        "operations, or any Python statements -- arithmetic only."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "The arithmetic expression to evaluate, e.g. '(152.3 - 148.9) / 148.9 * 100'",
            }
        },
        "required": ["expression"],
    },
}

GET_PRICE_HISTORY_TOOL = {
    "name": "get_price_history",
    "description": (
        "Fetch historical OHLC (open/high/low/close/volume) price bars for a "
        "stock or ETF ticker. Use this to answer questions about price "
        "moves, or to compute % changes with the calculate tool."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock/ETF ticker symbol, e.g. AAPL"},
            "period": {
                "type": "string",
                "enum": ["1D", "1W", "1M", "1Y", "5Y"],
                "description": "Lookback window",
            },
        },
        "required": ["ticker", "period"],
    },
}

# Client-side fallback search tool (used only when native web_search is
# not attached to this request).
SEARCH_NEWS_FALLBACK_TOOL = {
    "name": "search_news",
    "description": (
        "Search the live web for recent news about a stock/ETF ticker that "
        "could plausibly move its price. Returns raw search results "
        "(title, url, snippet, published date) for you to read and cite -- "
        "it does not summarize or judge relevance for you."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock/ETF ticker symbol"},
            "query": {
                "type": "string",
                "description": "Search query, e.g. 'AAPL earnings guidance August 2026'",
            },
        },
        "required": ["ticker", "query"],
    },
}

ALL_CLIENT_TOOLS_NATIVE_SEARCH = [GET_PRICE_HISTORY_TOOL, CALCULATE_TOOL]
ALL_CLIENT_TOOLS_FALLBACK_SEARCH = [
    GET_PRICE_HISTORY_TOOL,
    CALCULATE_TOOL,
    SEARCH_NEWS_FALLBACK_TOOL,
]

NATIVE_WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
}
