"""Tests for balance sheet module."""

import pytest

from stock_index_info.models import BalanceSheetRecord


def test_fetch_balance_sheet_valid_ticker():
    """Test fetching balance sheet for a valid ticker."""
    from stock_index_info.config import ALPHA_VANTAGE_API_KEY
    from stock_index_info.balance_sheet import fetch_balance_sheet

    if not ALPHA_VANTAGE_API_KEY:
        pytest.skip("ALPHA_VANTAGE_API_KEY not set")

    records = fetch_balance_sheet("IBM")

    assert records is not None
    assert len(records) >= 1
    assert all(r.ticker == "IBM" for r in records)
    assert all(r.fiscal_year >= 2000 for r in records)
    # Total assets should be large for IBM
    assert all(r.total_assets > 1_000_000_000 for r in records)
    # Should be sorted by year descending
    years = [r.fiscal_year for r in records]
    assert years == sorted(years, reverse=True)


def test_fetch_balance_sheet_invalid_ticker():
    """Test fetching balance sheet for invalid ticker returns None."""
    from stock_index_info.config import ALPHA_VANTAGE_API_KEY
    from stock_index_info.balance_sheet import fetch_balance_sheet

    if not ALPHA_VANTAGE_API_KEY:
        pytest.skip("ALPHA_VANTAGE_API_KEY not set")

    records = fetch_balance_sheet("INVALIDTICKER12345")
    assert records is None


def test_fetch_balance_sheet_no_api_key(monkeypatch):
    """Test that fetch returns None when API key not configured."""
    from stock_index_info import balance_sheet
    from stock_index_info.balance_sheet import fetch_balance_sheet

    monkeypatch.setattr(balance_sheet, "ALPHA_VANTAGE_API_KEY", None)

    records = fetch_balance_sheet("AAPL")
    assert records is None


def test_calculate_asset_valuation_positive():
    """Test calculating NTA and NCAV with positive values."""
    from stock_index_info.balance_sheet import calculate_asset_valuation

    record = BalanceSheetRecord(
        ticker="TEST",
        fiscal_year=2024,
        total_assets=100_000_000_000,  # $100B
        total_liabilities=50_000_000_000,  # $50B
        total_current_assets=40_000_000_000,  # $40B
        goodwill=5_000_000_000,  # $5B
        intangible_assets=3_000_000_000,  # $3B
    )
    market_cap = 200_000_000_000.0  # $200B

    # NTA = 100B - 50B - 5B - 3B = 42B
    # NCAV = 40B - 50B = -10B
    # P/NTA = 200B / 42B = 4.76
    # P/NCAV = N/A (negative NCAV)

    result = calculate_asset_valuation(record, market_cap)

    assert result is not None
    assert abs(result.nta - 42_000_000_000) < 1
    assert abs(result.ncav - (-10_000_000_000)) < 1
    assert result.p_nta is not None
    assert abs(result.p_nta - 4.76) < 0.01
    assert result.p_ncav is None  # NCAV is negative


def test_calculate_asset_valuation_negative_nta():
    """Test calculating when NTA is negative."""
    from stock_index_info.balance_sheet import calculate_asset_valuation

    record = BalanceSheetRecord(
        ticker="TEST",
        fiscal_year=2024,
        total_assets=50_000_000_000,
        total_liabilities=60_000_000_000,
        total_current_assets=20_000_000_000,
        goodwill=5_000_000_000,
        intangible_assets=3_000_000_000,
    )
    market_cap = 100_000_000_000.0

    # NTA = 50B - 60B - 5B - 3B = -18B
    # NCAV = 20B - 60B = -40B

    result = calculate_asset_valuation(record, market_cap)

    assert result is not None
    assert result.nta < 0
    assert result.ncav < 0
    assert result.p_nta is None
    assert result.p_ncav is None


def test_calculate_asset_valuation_positive_ncav():
    """Test calculating when NCAV is positive (Graham value stock)."""
    from stock_index_info.balance_sheet import calculate_asset_valuation

    record = BalanceSheetRecord(
        ticker="TEST",
        fiscal_year=2024,
        total_assets=100_000_000_000,
        total_liabilities=30_000_000_000,  # Low debt
        total_current_assets=50_000_000_000,  # High current assets
        goodwill=2_000_000_000,
        intangible_assets=1_000_000_000,
    )
    market_cap = 40_000_000_000.0

    # NTA = 100B - 30B - 2B - 1B = 67B
    # NCAV = 50B - 30B = 20B
    # P/NTA = 40B / 67B = 0.60
    # P/NCAV = 40B / 20B = 2.0

    result = calculate_asset_valuation(record, market_cap)

    assert result is not None
    assert result.p_nta is not None
    assert abs(result.p_nta - 0.597) < 0.01
    assert result.p_ncav is not None
    assert abs(result.p_ncav - 2.0) < 0.01


def test_get_asset_valuation_with_cache(db_connection):
    """Test getting asset valuation uses cache when available."""
    from stock_index_info.balance_sheet import get_asset_valuation
    from stock_index_info.db import save_balance_sheet

    records = [
        BalanceSheetRecord(
            ticker="TEST",
            fiscal_year=2024,
            total_assets=100_000_000_000,
            total_liabilities=50_000_000_000,
            total_current_assets=40_000_000_000,
            goodwill=5_000_000_000,
            intangible_assets=3_000_000_000,
        ),
    ]
    save_balance_sheet(db_connection, "TEST", records, "2025-01-15")

    result = get_asset_valuation(db_connection, "TEST", market_cap=200_000_000_000.0)

    assert result is not None
    assert abs(result.nta - 42_000_000_000) < 1
