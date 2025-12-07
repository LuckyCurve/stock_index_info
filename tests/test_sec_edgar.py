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


def test_get_recent_filings_valid_ticker():
    """Test getting recent filings for a valid ticker."""
    from stock_index_info.sec_edgar import get_recent_filings
    from stock_index_info.models import RecentFilings

    result = get_recent_filings("AAPL")

    assert result is not None
    assert isinstance(result, RecentFilings)
    # Should have up to 4 quarterly reports
    assert len(result.quarterly) <= 4
    assert len(result.quarterly) > 0  # AAPL should have at least one 10-Q
    for q in result.quarterly:
        assert q.form_type == "10-Q"
        assert q.ticker == "AAPL"
        assert q.filing_url.startswith("https://www.sec.gov")
    # Should have annual report
    assert result.annual is not None
    assert result.annual.form_type == "10-K"
    assert result.annual.ticker == "AAPL"


def test_get_recent_filings_invalid_ticker():
    """Test getting recent filings for invalid ticker returns None."""
    from stock_index_info.sec_edgar import get_recent_filings

    result = get_recent_filings("INVALIDTICKER123")
    assert result is None


def test_get_recent_filings_quarterly_order():
    """Test that quarterly filings are returned in descending date order."""
    from stock_index_info.sec_edgar import get_recent_filings

    result = get_recent_filings("AAPL")
    assert result is not None
    # Verify descending order by filing_date
    dates = [q.filing_date for q in result.quarterly]
    assert dates == sorted(dates, reverse=True)
