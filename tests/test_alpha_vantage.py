"""Tests for Alpha Vantage module."""

import pytest


def test_fetch_annual_eps_valid_ticker():
    """Test fetching annual EPS for a valid ticker."""
    from stock_index_info.config import ALPHA_VANTAGE_API_KEY
    from stock_index_info.alpha_vantage import fetch_annual_eps

    if not ALPHA_VANTAGE_API_KEY:
        pytest.skip("ALPHA_VANTAGE_API_KEY not set")

    records = fetch_annual_eps("IBM")

    assert records is not None
    assert len(records) >= 7  # Should have at least 7 years
    assert all(r.ticker == "IBM" for r in records)
    assert all(r.fiscal_year >= 2000 for r in records)
    # Should be sorted by year descending
    years = [r.fiscal_year for r in records]
    assert years == sorted(years, reverse=True)


def test_fetch_annual_eps_invalid_ticker():
    """Test fetching EPS for invalid ticker returns None."""
    from stock_index_info.config import ALPHA_VANTAGE_API_KEY
    from stock_index_info.alpha_vantage import fetch_annual_eps

    if not ALPHA_VANTAGE_API_KEY:
        pytest.skip("ALPHA_VANTAGE_API_KEY not set")

    records = fetch_annual_eps("INVALIDTICKER12345")
    assert records is None


def test_fetch_annual_eps_no_api_key(monkeypatch):
    """Test that fetch returns None when API key not configured."""
    from stock_index_info import config
    from stock_index_info.alpha_vantage import fetch_annual_eps

    monkeypatch.setattr(config, "ALPHA_VANTAGE_API_KEY", None)

    records = fetch_annual_eps("AAPL")
    assert records is None


def test_get_current_price_valid_ticker():
    """Test getting current price for a valid ticker."""
    from stock_index_info.alpha_vantage import get_current_price

    price = get_current_price("AAPL")

    # May return None if rate limited by Yahoo Finance
    if price is not None:
        assert price > 0


def test_get_current_price_invalid_ticker():
    """Test getting price for invalid ticker returns None."""
    from stock_index_info.alpha_vantage import get_current_price

    price = get_current_price("INVALIDTICKER12345")
    assert price is None


def test_calculate_7year_avg_pe():
    """Test calculating 7-year average P/E."""
    from stock_index_info.alpha_vantage import calculate_7year_avg_pe
    from stock_index_info.models import EarningsRecord

    records = [
        EarningsRecord(ticker="TEST", fiscal_year=2024, eps=5.0),
        EarningsRecord(ticker="TEST", fiscal_year=2023, eps=4.0),
        EarningsRecord(ticker="TEST", fiscal_year=2022, eps=3.0),
        EarningsRecord(ticker="TEST", fiscal_year=2021, eps=4.0),
        EarningsRecord(ticker="TEST", fiscal_year=2020, eps=5.0),
        EarningsRecord(ticker="TEST", fiscal_year=2019, eps=6.0),
        EarningsRecord(ticker="TEST", fiscal_year=2018, eps=8.0),
    ]
    # Average EPS = (5+4+3+4+5+6+8) / 7 = 35 / 7 = 5.0
    # P/E = 100 / 5.0 = 20.0
    current_price = 100.0

    pe = calculate_7year_avg_pe(records, current_price)

    assert pe is not None
    assert abs(pe - 20.0) < 0.01


def test_calculate_7year_avg_pe_insufficient_data():
    """Test that P/E returns None when less than 7 years of data."""
    from stock_index_info.alpha_vantage import calculate_7year_avg_pe
    from stock_index_info.models import EarningsRecord

    records = [
        EarningsRecord(ticker="TEST", fiscal_year=2024, eps=5.0),
        EarningsRecord(ticker="TEST", fiscal_year=2023, eps=4.0),
        EarningsRecord(ticker="TEST", fiscal_year=2022, eps=3.0),
    ]
    current_price = 100.0

    pe = calculate_7year_avg_pe(records, current_price)

    assert pe is None


def test_calculate_7year_avg_pe_negative_average():
    """Test that P/E returns None when average EPS is negative or zero."""
    from stock_index_info.alpha_vantage import calculate_7year_avg_pe
    from stock_index_info.models import EarningsRecord

    records = [
        EarningsRecord(ticker="TEST", fiscal_year=2024, eps=-5.0),
        EarningsRecord(ticker="TEST", fiscal_year=2023, eps=-4.0),
        EarningsRecord(ticker="TEST", fiscal_year=2022, eps=-3.0),
        EarningsRecord(ticker="TEST", fiscal_year=2021, eps=-4.0),
        EarningsRecord(ticker="TEST", fiscal_year=2020, eps=-5.0),
        EarningsRecord(ticker="TEST", fiscal_year=2019, eps=-6.0),
        EarningsRecord(ticker="TEST", fiscal_year=2018, eps=-8.0),
    ]
    current_price = 100.0

    pe = calculate_7year_avg_pe(records, current_price)

    assert pe is None


def test_get_7year_pe_with_cache(db_connection):
    """Test getting 7-year P/E uses cache when available."""
    from stock_index_info.alpha_vantage import get_7year_pe
    from stock_index_info.db import save_earnings
    from stock_index_info.models import EarningsRecord

    # Pre-populate cache with 7 years of data
    records = [
        EarningsRecord(ticker="TEST", fiscal_year=2024, eps=5.0),
        EarningsRecord(ticker="TEST", fiscal_year=2023, eps=4.0),
        EarningsRecord(ticker="TEST", fiscal_year=2022, eps=3.0),
        EarningsRecord(ticker="TEST", fiscal_year=2021, eps=4.0),
        EarningsRecord(ticker="TEST", fiscal_year=2020, eps=5.0),
        EarningsRecord(ticker="TEST", fiscal_year=2019, eps=6.0),
        EarningsRecord(ticker="TEST", fiscal_year=2018, eps=8.0),
    ]
    save_earnings(db_connection, "TEST", records, "2025-01-15")

    # Mock current price
    result = get_7year_pe(db_connection, "TEST", current_price=100.0)

    assert result is not None
    assert abs(result - 20.0) < 0.01
