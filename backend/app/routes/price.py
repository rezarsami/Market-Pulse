from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from app.guardrails.sanitize import sanitize_ticker
from app.models.schemas import (
    AnalyticsResponse,
    PriceBar,
    PriceHistoryResponse,
    ReturnBucketOut,
)
from app.tools.analytics import compute_analytics
from app.tools.price_history import get_price_history

router = APIRouter()

_VALID_PERIODS = {"1D", "1W", "1M", "1Y", "5Y"}


@router.get("/price-history", response_model=PriceHistoryResponse)
def price_history(
    ticker: str = Query(..., min_length=1, max_length=10),
    period: str = Query("1M"),
) -> PriceHistoryResponse:
    ticker_result = sanitize_ticker(ticker)
    if not ticker_result.ok:
        raise HTTPException(status_code=400, detail=ticker_result.reason)

    period_norm = period.strip().upper()
    if period_norm not in _VALID_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"period must be one of {sorted(_VALID_PERIODS)}",
        )

    result = get_price_history(ticker_result.cleaned, period_norm)

    return PriceHistoryResponse(
        ticker=result.ticker,
        period=result.period,
        interval=result.interval,
        bars=[PriceBar(**asdict(b)) for b in result.bars],
        currency=result.currency,
        no_data_found=result.no_data_found,
    )



@router.get("/analytics", response_model=AnalyticsResponse)
def analytics(
    ticker: str = Query(..., min_length=1, max_length=10),
    period: str = Query("1Y"),
) -> AnalyticsResponse:
    ticker_result = sanitize_ticker(ticker)
    if not ticker_result.ok:
        raise HTTPException(status_code=400, detail=ticker_result.reason)

    period_norm = period.strip().upper()
    if period_norm not in {"1M", "1Y", "5Y"}:
        raise HTTPException(
            status_code=400, detail="period must be one of 1M, 1Y, 5Y"
        )

    a = compute_analytics(ticker_result.cleaned, period_norm)

    return AnalyticsResponse(
        ticker=a.ticker,
        period=a.period,
        n_days=a.n_days,
        currency=a.currency,
        cumulative_return_pct=a.cumulative_return_pct,
        annualized_volatility_pct=a.annualized_volatility_pct,
        max_drawdown_pct=a.max_drawdown_pct,
        best_day_pct=a.best_day_pct,
        worst_day_pct=a.worst_day_pct,
        positive_day_share_pct=a.positive_day_share_pct,
        sma_20=a.sma_20,
        sma_50=a.sma_50,
        last_close=a.last_close,
        price_vs_sma50_pct=a.price_vs_sma50_pct,
        beta_vs_spy=a.beta_vs_spy,
        correlation_vs_spy=a.correlation_vs_spy,
        return_distribution=[ReturnBucketOut(label=b.label, count=b.count) for b in a.return_distribution],
        no_data_found=a.no_data_found,
    )
