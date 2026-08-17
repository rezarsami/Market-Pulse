"""
get_price_history tool: historical OHLC data via yfinance (free, keyless).

Never fabricates data -- if yfinance returns nothing for a ticker/period,
we report no_data_found=True rather than inventing bars.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf

logger = logging.getLogger("market_pulse")

# Map our simplified period vocabulary to yfinance period/interval pairs.
_PERIOD_MAP = {
    "1D": {"period": "1d", "interval": "5m"},
    "1W": {"period": "5d", "interval": "30m"},
    "1M": {"period": "1mo", "interval": "1d"},
    "1Y": {"period": "1y", "interval": "1d"},
    "5Y": {"period": "5y", "interval": "1wk"},
}


@dataclass
class PriceBarResult:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class PriceHistoryResult:
    ticker: str
    period: str
    interval: str
    bars: list[PriceBarResult] = field(default_factory=list)
    currency: str | None = None
    no_data_found: bool = False
    error: str | None = None


def get_price_history(ticker: str, period: str = "1M", interval: str | None = None) -> PriceHistoryResult:
    """
    Fetch historical OHLC data for `ticker`.

    `period` is one of 1D/1W/1M/1Y/5Y (case-insensitive). If `interval` is
    given explicitly it overrides the default mapping.
    """
    period_key = period.strip().upper()
    if period_key not in _PERIOD_MAP:
        return PriceHistoryResult(
            ticker=ticker,
            period=period,
            interval=interval or "",
            error=f"unsupported period '{period}'; must be one of {list(_PERIOD_MAP)}",
        )

    yf_params = _PERIOD_MAP[period_key]
    yf_interval = interval or yf_params["interval"]

    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period=yf_params["period"], interval=yf_interval)
    except Exception as e:  # network errors, bad ticker, etc.
        logger.warning(f"yfinance error for {ticker}: {e}")
        return PriceHistoryResult(
            ticker=ticker,
            period=period_key,
            interval=yf_interval,
            no_data_found=True,
            error=str(e),
        )

    if hist is None or not isinstance(hist, pd.DataFrame) or hist.empty:
        return PriceHistoryResult(
            ticker=ticker,
            period=period_key,
            interval=yf_interval,
            no_data_found=True,
        )

    bars: list[PriceBarResult] = []
    for idx, row in hist.iterrows():
        try:
            bars.append(
                PriceBarResult(
                    date=idx.isoformat(),
                    open=round(float(row["Open"]), 4),
                    high=round(float(row["High"]), 4),
                    low=round(float(row["Low"]), 4),
                    close=round(float(row["Close"]), 4),
                    volume=int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
                )
            )
        except (KeyError, ValueError, TypeError):
            continue

    if not bars:
        return PriceHistoryResult(
            ticker=ticker, period=period_key, interval=yf_interval, no_data_found=True
        )

    currency = None
    try:
        currency = tk.fast_info.get("currency")
    except Exception:
        pass

    return PriceHistoryResult(
        ticker=ticker,
        period=period_key,
        interval=yf_interval,
        bars=bars,
        currency=currency,
        no_data_found=False,
    )
