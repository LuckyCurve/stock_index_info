"""Tests for NASDAQ 100 Wikipedia scraper."""

from unittest.mock import patch, MagicMock


from stock_index_info.scrapers.nasdaq100 import NASDAQ100Scraper


SAMPLE_CURRENT_TABLE_HTML = """
<table class="wikitable sortable">
<tr><th>Ticker</th><th>Company</th><th>ICB Industry</th></tr>
<tr><td>AAPL</td><td>Apple Inc.</td><td>Technology</td></tr>
<tr><td>GOOGL</td><td>Alphabet Inc.</td><td>Technology</td></tr>
</table>
"""

SAMPLE_CHANGES_TABLE_HTML = """
<table class="wikitable">
<tr><th>Date</th><th colspan="2">Added</th><th colspan="2">Removed</th><th>Reason</th></tr>
<tr><th></th><th>Ticker</th><th>Security</th><th>Ticker</th><th>Security</th><th></th></tr>
<tr><td>December 23, 2024</td><td>PLTR</td><td>Palantir</td><td>SMCI</td><td>Super Micro</td><td>Annual reconstitution</td></tr>
</table>
"""


class TestNASDAQ100Scraper:
    def test_index_code(self) -> None:
        scraper = NASDAQ100Scraper()
        assert scraper.index_code == "nasdaq100"
        assert scraper.index_name == "NASDAQ 100"

    @patch("stock_index_info.scrapers.nasdaq100.requests.get")
    def test_fetch_finds_current_constituents(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = (
            f"<html><body>{SAMPLE_CURRENT_TABLE_HTML}{SAMPLE_CHANGES_TABLE_HTML}</body></html>"
        )
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        scraper = NASDAQ100Scraper()
        records = scraper.fetch()

        tickers = {r.ticker for r in records}
        assert "AAPL" in tickers
        assert "GOOGL" in tickers

    @patch("stock_index_info.scrapers.nasdaq100.requests.get")
    def test_fetch_parses_changes(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = (
            f"<html><body>{SAMPLE_CURRENT_TABLE_HTML}{SAMPLE_CHANGES_TABLE_HTML}</body></html>"
        )
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        scraper = NASDAQ100Scraper()
        records = scraper.fetch()

        # SMCI should be marked as removed
        smci_records = [r for r in records if r.ticker == "SMCI"]
        assert len(smci_records) >= 1
