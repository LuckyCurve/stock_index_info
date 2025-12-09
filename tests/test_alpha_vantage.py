"""Tests for Alpha Vantage module."""

import pytest


def test_fetch_annual_net_income_valid_ticker():
    """Test fetching annual net income for a valid ticker."""
    from stock_index_info.config import ALPHA_VANTAGE_API_KEY
    from stock_index_info.alpha_vantage import fetch_annual_net_income

    if not ALPHA_VANTAGE_API_KEY:
        pytest.skip("ALPHA_VANTAGE_API_KEY not set")

    records = fetch_annual_net_income("IBM")

    assert records is not None
    assert len(records) >= 7  # Should have at least 7 years
    assert all(r.ticker == "IBM" for r in records)
    assert all(r.fiscal_year >= 2000 for r in records)
    # Net income should be in dollars (large numbers)
    assert all(abs(r.net_income) > 1_000_000 for r in records)
    # Should be sorted by year descending
    years = [r.fiscal_year for r in records]
    assert years == sorted(years, reverse=True)


def test_fetch_annual_net_income_invalid_ticker():
    """Test fetching net income for invalid ticker returns None."""
    from stock_index_info.config import ALPHA_VANTAGE_API_KEY
    from stock_index_info.alpha_vantage import fetch_annual_net_income

    if not ALPHA_VANTAGE_API_KEY:
        pytest.skip("ALPHA_VANTAGE_API_KEY not set")

    records = fetch_annual_net_income("INVALIDTICKER12345")
    assert records is None


def test_fetch_annual_net_income_no_api_key(monkeypatch):
    """Test that fetch returns None when API key not configured."""
    from stock_index_info import alpha_vantage
    from stock_index_info.alpha_vantage import fetch_annual_net_income

    monkeypatch.setattr(alpha_vantage, "ALPHA_VANTAGE_API_KEY", None)

    records = fetch_annual_net_income("AAPL")
    assert records is None


def test_get_market_cap_valid_ticker():
    """Test getting market cap for a valid ticker."""
    from stock_index_info.alpha_vantage import get_market_cap

    market_cap = get_market_cap("AAPL")

    # May return None if rate limited by Yahoo Finance
    if market_cap is not None:
        # Apple's market cap should be in trillions
        assert market_cap > 1_000_000_000_000


def test_get_market_cap_invalid_ticker():
    """Test getting market cap for invalid ticker returns None."""
    from stock_index_info.alpha_vantage import get_market_cap

    market_cap = get_market_cap("INVALIDTICKER12345")
    assert market_cap is None


def test_calculate_7year_avg_pe():
    """Test calculating 7-year average P/E using market cap and net income."""
    from stock_index_info.alpha_vantage import calculate_7year_avg_pe
    from stock_index_info.models import IncomeRecord

    records = [
        IncomeRecord(ticker="TEST", fiscal_year=2024, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2023, net_income=90_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2022, net_income=80_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2021, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2020, net_income=110_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2019, net_income=120_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2018, net_income=100_000_000),
    ]
    # Average net income = 700_000_000 / 7 = 100_000_000
    # P/E = 2_000_000_000 / 100_000_000 = 20.0
    market_cap = 2_000_000_000.0

    pe = calculate_7year_avg_pe(records, market_cap)

    assert pe is not None
    assert abs(pe - 20.0) < 0.01


def test_calculate_7year_avg_pe_insufficient_data():
    """Test that P/E returns None when less than 7 years of data."""
    from stock_index_info.alpha_vantage import calculate_7year_avg_pe
    from stock_index_info.models import IncomeRecord

    records = [
        IncomeRecord(ticker="TEST", fiscal_year=2024, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2023, net_income=90_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2022, net_income=80_000_000),
    ]
    market_cap = 2_000_000_000.0

    pe = calculate_7year_avg_pe(records, market_cap)

    assert pe is None


def test_calculate_7year_avg_pe_negative_average():
    """Test that P/E returns None when average net income is negative or zero."""
    from stock_index_info.alpha_vantage import calculate_7year_avg_pe
    from stock_index_info.models import IncomeRecord

    records = [
        IncomeRecord(ticker="TEST", fiscal_year=2024, net_income=-100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2023, net_income=-90_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2022, net_income=-80_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2021, net_income=-100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2020, net_income=-110_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2019, net_income=-120_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2018, net_income=-100_000_000),
    ]
    market_cap = 2_000_000_000.0

    pe = calculate_7year_avg_pe(records, market_cap)

    assert pe is None


def test_calculate_7year_avg_pe_non_consecutive_years():
    """Test that P/E returns None when years are not consecutive."""
    from stock_index_info.alpha_vantage import calculate_7year_avg_pe
    from stock_index_info.models import IncomeRecord

    # Missing 2021 - years are not consecutive
    records = [
        IncomeRecord(ticker="TEST", fiscal_year=2024, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2023, net_income=90_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2022, net_income=80_000_000),
        # 2021 is missing
        IncomeRecord(ticker="TEST", fiscal_year=2020, net_income=110_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2019, net_income=120_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2018, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2017, net_income=90_000_000),
    ]
    market_cap = 2_000_000_000.0

    pe = calculate_7year_avg_pe(records, market_cap)

    assert pe is None


def test_get_7year_pe_with_cache(db_connection):
    """Test getting 7-year P/E uses cache when available."""
    from stock_index_info.alpha_vantage import get_7year_pe
    from stock_index_info.db import save_income
    from stock_index_info.models import IncomeRecord

    # Pre-populate cache with 7 consecutive years of data
    records = [
        IncomeRecord(ticker="TEST", fiscal_year=2024, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2023, net_income=90_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2022, net_income=80_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2021, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2020, net_income=110_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2019, net_income=120_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2018, net_income=100_000_000),
    ]
    save_income(db_connection, "TEST", records, "2025-01-15")

    # Average net income = 700_000_000 / 7 = 100_000_000
    # P/E = 2_000_000_000 / 100_000_000 = 20.0
    result = get_7year_pe(db_connection, "TEST", market_cap=2_000_000_000.0)

    assert result is not None
    assert abs(result - 20.0) < 0.01
