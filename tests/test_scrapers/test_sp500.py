"""Tests for S&P 500 Wikipedia scraper."""

from datetime import date
from unittest.mock import patch, MagicMock


from stock_index_info.scrapers.sp500 import SP500Scraper


# Sample HTML fixture for testing (subset of actual Wikipedia table)
SAMPLE_CURRENT_TABLE_HTML = """
<table class="wikitable sortable">
<tr><th>Symbol</th><th>Security</th><th>GICS Sector</th><th>Date added</th></tr>
<tr><td>AAPL</td><td>Apple Inc.</td><td>Information Technology</td><td>1982-11-30</td></tr>
<tr><td>MSFT</td><td>Microsoft Corp</td><td>Information Technology</td><td>1994-06-01</td></tr>
</table>
"""

SAMPLE_CHANGES_TABLE_HTML = """
<table class="wikitable">
<tr><th>Date</th><th colspan="2">Added</th><th colspan="2">Removed</th><th>Reason</th></tr>
<tr><th></th><th>Ticker</th><th>Security</th><th>Ticker</th><th>Security</th><th></th></tr>
<tr><td>December 22, 2024</td><td>HOOD</td><td>Robinhood</td><td>PARA</td><td>Paramount</td><td>Market cap</td></tr>
</table>
"""


class TestSP500Scraper:
    def test_index_code(self) -> None:
        scraper = SP500Scraper()
        assert scraper.index_code == "sp500"
        assert scraper.index_name == "S&P 500"

    @patch("stock_index_info.scrapers.sp500.httpx.get")
    def test_fetch_current_constituents(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = f"<html><body>{SAMPLE_CURRENT_TABLE_HTML}{SAMPLE_CHANGES_TABLE_HTML}</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        scraper = SP500Scraper()
        records = scraper.fetch()

        # Should find AAPL and MSFT from current table
        tickers = {r.ticker for r in records}
        assert "AAPL" in tickers
        assert "MSFT" in tickers

        # Check AAPL details
        aapl = next(r for r in records if r.ticker == "AAPL" and r.removed_date is None)
        assert aapl.added_date == date(1982, 11, 30)
        assert aapl.index_code == "sp500"

    @patch("stock_index_info.scrapers.sp500.httpx.get")
    def test_fetch_parses_changes(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = f"<html><body>{SAMPLE_CURRENT_TABLE_HTML}{SAMPLE_CHANGES_TABLE_HTML}</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        scraper = SP500Scraper()
        records = scraper.fetch()

        # PARA should be marked as removed
        para_records = [r for r in records if r.ticker == "PARA"]
        assert len(para_records) >= 1
        removed_para = next((r for r in para_records if r.removed_date is not None), None)
        assert removed_para is not None
        assert removed_para.removed_date == date(2024, 12, 22)
