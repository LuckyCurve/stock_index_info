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
