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


def test_get_latest_10q_valid_ticker():
    """Test getting latest 10-Q for a valid ticker."""
    from stock_index_info.sec_edgar import get_latest_10q
    from stock_index_info.models import SECFilingRecord

    result = get_latest_10q("AAPL")

    assert result is not None
    assert isinstance(result, SECFilingRecord)
    assert result.ticker == "AAPL"
    assert result.form_type == "10-Q"
    assert result.filing_url.startswith("https://www.sec.gov")
    assert len(result.filing_date) == 10  # YYYY-MM-DD format


def test_get_latest_10q_invalid_ticker():
    """Test getting 10-Q for invalid ticker returns None."""
    from stock_index_info.sec_edgar import get_latest_10q

    result = get_latest_10q("INVALIDTICKER123")
    assert result is None
