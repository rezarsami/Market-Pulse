from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from app.guardrails.sanitize import sanitize_ticker
from app.models.schemas import PriceBar, PriceHistoryResponse
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
