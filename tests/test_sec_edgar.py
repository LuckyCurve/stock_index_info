"""Tests for SEC EDGAR module."""


def test_get_cik_from_ticker_valid():
    """Test getting CIK for a valid ticker."""
    from stock_index_info.sec_edgar import get_cik_from_ticker

    # AAPL's CIK is 320193
    cik = get_cik_from_ticker("AAPL")
    assert cik == "320193"


def test_get_cik_from_ticker_invalid():
    """Test getting CIK for an invalid ticker returns None."""
    from stock_index_info.sec_edgar import get_cik_from_ticker

    cik = get_cik_from_ticker("INVALIDTICKER123")
    assert cik is None


def test_get_cik_from_ticker_case_insensitive():
    """Test that ticker lookup is case insensitive."""
    from stock_index_info.sec_edgar import get_cik_from_ticker

    cik_upper = get_cik_from_ticker("AAPL")
    cik_lower = get_cik_from_ticker("aapl")
    assert cik_upper == cik_lower
