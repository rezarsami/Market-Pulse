"""
Tests for the price history tool's "never fabricate data" guarantee.
We mock yfinance so tests don't depend on network access, and confirm
that an empty/erroring response from yfinance results in
no_data_found=True with zero bars, never invented OHLC values.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from app.tools.price_history import get_price_history


class TestPriceHistoryNoDataFound:
    @patch("app.tools.price_history.yf.Ticker")
    def test_empty_dataframe_reports_no_data_found(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = mock_ticker

        result = get_price_history("ZZZQXNOPE", "1M")

        assert result.no_data_found is True
        assert result.bars == []

    @patch("app.tools.price_history.yf.Ticker")
    def test_exception_reports_no_data_found_not_crash(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("symbol not found")
        mock_ticker_cls.return_value = mock_ticker

        result = get_price_history("BADTICKER", "1Y")

        assert result.no_data_found is True
        assert result.error is not None

    def test_unsupported_period_returns_error_not_crash(self):
        result = get_price_history("AAPL", "3W")
        assert result.error is not None
        assert result.bars == []

    @patch("app.tools.price_history.yf.Ticker")
    def test_valid_data_produces_bars(self, mock_ticker_cls):
        idx = pd.date_range("2026-01-01", periods=3, freq="D")
        df = pd.DataFrame(
            {
                "Open": [100.0, 101.0, 102.0],
                "High": [105.0, 106.0, 107.0],
                "Low": [99.0, 100.0, 101.0],
                "Close": [104.0, 105.0, 106.0],
                "Volume": [1000, 1100, 1200],
            },
            index=idx,
        )
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = df
        mock_ticker.fast_info = {"currency": "USD"}
        mock_ticker_cls.return_value = mock_ticker

        result = get_price_history("AAPL", "1M")

        assert result.no_data_found is False
        assert len(result.bars) == 3
        assert result.bars[0].open == 100.0
        assert result.currency == "USD"
