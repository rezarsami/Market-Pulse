"""
Quantitative analytics computed from price history — the "data analysis"
segment. Unlike the news pipeline (where an LLM interprets), everything here
is deterministic math on real market data via pandas/numpy. No model, no
fabrication: if the data is insufficient for a metric, that metric is null.

Metrics and formulas (all annualized where noted, using daily bars):

  daily returns r_t = close_t / close_{t-1} - 1

  annualized volatility = std(r) * sqrt(252)
      252 = trading days/year. Uses sample std (ddof=1).

  cumulative return = close_last / close_first - 1

  max drawdown = min over t of (close_t / running_max(close)_t - 1)
      the largest peak-to-trough decline in the window.

  moving averages: simple mean of the last N closes (SMA-N), reported only
      when there are >= N bars.

  beta / correlation vs SPY: over the SAME dates, align the ticker's daily
      returns with SPY's, then:
        correlation = pearson corr of the two return series
        beta = cov(r_ticker, r_spy) / var(r_spy)
      Beta > 1 means more volatile than the market; correlation near 1 means
      it moves with the market.

  return distribution: counts of daily returns bucketed for a histogram, plus
      best/worst single-day return.

We compute on DAILY bars, so we force a daily interval regardless of the
window the chart is showing, and use a lookback tied to the requested period.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger("market_pulse")

_TRADING_DAYS = 252

# Lookback per requested window, always on daily bars for return math.
_LOOKBACK = {
    "1M": "1mo",
    "1Y": "1y",
    "5Y": "5y",
}


@dataclass
class ReturnBucket:
    label: str          # e.g. "-2% to -1%"
    count: int


@dataclass
class Analytics:
    ticker: str
    period: str
    n_days: int = 0
    currency: str | None = None

    cumulative_return_pct: float | None = None
    annualized_volatility_pct: float | None = None
    max_drawdown_pct: float | None = None
    best_day_pct: float | None = None
    worst_day_pct: float | None = None
    positive_day_share_pct: float | None = None

    sma_20: float | None = None
    sma_50: float | None = None
    last_close: float | None = None
    price_vs_sma50_pct: float | None = None

    beta_vs_spy: float | None = None
    correlation_vs_spy: float | None = None

    return_distribution: list[ReturnBucket] = field(default_factory=list)

    no_data_found: bool = False
    error: str | None = None


def _daily_closes(ticker: str, yf_period: str) -> pd.Series | None:
    try:
        hist = yf.Ticker(ticker).history(period=yf_period, interval="1d")
    except Exception as e:
        logger.warning(f"analytics: history failed for {ticker}: {e}")
        return None
    if hist is None or not isinstance(hist, pd.DataFrame) or hist.empty or "Close" not in hist:
        return None
    closes = hist["Close"].dropna()
    return closes if len(closes) >= 2 else None


def _distribution(returns: pd.Series) -> list[ReturnBucket]:
    # Buckets in percent terms; edges chosen to be readable for daily equity moves.
    edges = [-np.inf, -0.05, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, 0.05, np.inf]
    labels = [
        "< -5%", "-5% to -3%", "-3% to -2%", "-2% to -1%", "-1% to 0%",
        "0% to 1%", "1% to 2%", "2% to 3%", "3% to 5%", "> 5%",
    ]
    buckets: list[ReturnBucket] = []
    cats = pd.cut(returns, bins=edges, labels=labels, right=False)
    counts = cats.value_counts().reindex(labels, fill_value=0)
    for label in labels:
        buckets.append(ReturnBucket(label=label, count=int(counts[label])))
    return buckets


def compute_analytics(ticker: str, period: str = "1Y") -> Analytics:
    period_key = period.strip().upper()
    yf_period = _LOOKBACK.get(period_key, "1y")

    closes = _daily_closes(ticker, yf_period)
    if closes is None:
        return Analytics(ticker=ticker, period=period_key, no_data_found=True)

    returns = closes.pct_change().dropna()
    if len(returns) < 2:
        return Analytics(ticker=ticker, period=period_key, no_data_found=True)

    first, last = float(closes.iloc[0]), float(closes.iloc[-1])
    cumulative = (last / first - 1) * 100 if first else None

    vol = float(returns.std(ddof=1)) * np.sqrt(_TRADING_DAYS) * 100

    running_max = closes.cummax()
    drawdown_series = closes / running_max - 1
    max_dd = float(drawdown_series.min()) * 100

    best = float(returns.max()) * 100
    worst = float(returns.min()) * 100
    pos_share = float((returns > 0).mean()) * 100

    sma20 = float(closes.iloc[-20:].mean()) if len(closes) >= 20 else None
    sma50 = float(closes.iloc[-50:].mean()) if len(closes) >= 50 else None
    price_vs_sma50 = ((last / sma50 - 1) * 100) if sma50 else None

    # Beta / correlation vs SPY over the same dates.
    beta = corr = None
    spy_closes = _daily_closes("SPY", yf_period)
    if spy_closes is not None:
        spy_returns = spy_closes.pct_change().dropna()
        joined = pd.concat(
            [returns.rename("t"), spy_returns.rename("m")], axis=1, join="inner"
        ).dropna()
        if len(joined) >= 3 and joined["m"].var(ddof=1) > 0:
            cov = joined["t"].cov(joined["m"])
            var_m = joined["m"].var(ddof=1)
            beta = float(cov / var_m)
            corr = float(joined["t"].corr(joined["m"]))

    currency = None
    try:
        currency = yf.Ticker(ticker).fast_info.get("currency")
    except Exception:
        pass

    return Analytics(
        ticker=ticker,
        period=period_key,
        n_days=int(len(closes)),
        currency=currency,
        cumulative_return_pct=round(cumulative, 2) if cumulative is not None else None,
        annualized_volatility_pct=round(vol, 2),
        max_drawdown_pct=round(max_dd, 2),
        best_day_pct=round(best, 2),
        worst_day_pct=round(worst, 2),
        positive_day_share_pct=round(pos_share, 1),
        sma_20=round(sma20, 2) if sma20 is not None else None,
        sma_50=round(sma50, 2) if sma50 is not None else None,
        last_close=round(last, 2),
        price_vs_sma50_pct=round(price_vs_sma50, 2) if price_vs_sma50 is not None else None,
        beta_vs_spy=round(beta, 2) if beta is not None else None,
        correlation_vs_spy=round(corr, 2) if corr is not None else None,
        return_distribution=_distribution(returns),
        no_data_found=False,
    )
