"""SEC EDGAR API client for fetching company filings."""

from typing import Optional

from curl_cffi import requests

from stock_index_info.models import SECFilingRecord


# SEC requires a User-Agent header with contact info
SEC_USER_AGENT = "StockIndexInfoBot contact@example.com"


def get_cik_from_ticker(ticker: str) -> Optional[str]:
    """Get CIK (Central Index Key) from ticker symbol.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        CIK as string without leading zeros, or None if not found
    """
    url = "https://www.sec.gov/files/company_tickers.json"

    try:
        response = requests.get(
            url,
            headers={"User-Agent": SEC_USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        # Data format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
        ticker_upper = ticker.upper()
        for entry in data.values():
            if entry.get("ticker") == ticker_upper:
                return str(entry["cik_str"])

        return None
    except Exception:
        return None


def get_latest_10q(ticker: str) -> Optional[SECFilingRecord]:
    """Get the latest 10-Q filing for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        SECFilingRecord with filing details, or None if not found
    """
    cik = get_cik_from_ticker(ticker)
    if cik is None:
        return None

    # Pad CIK to 10 digits for API
    cik_padded = cik.zfill(10)

    # Query company submissions endpoint
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"

    try:
        response = requests.get(
            url,
            headers={"User-Agent": SEC_USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        # Find latest 10-Q in recent filings
        recent_filings = data.get("filings", {}).get("recent", {})
        forms = recent_filings.get("form", [])
        accession_numbers = recent_filings.get("accessionNumber", [])
        filing_dates = recent_filings.get("filingDate", [])
        primary_documents = recent_filings.get("primaryDocument", [])

        for i, form in enumerate(forms):
            if form == "10-Q":
                accession = accession_numbers[i].replace("-", "")
                filing_date = filing_dates[i]
                primary_doc = primary_documents[i]

                filing_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}"
                )

                return SECFilingRecord(
                    ticker=ticker.upper(),
                    form_type="10-Q",
                    filing_date=filing_date,
                    filing_url=filing_url,
                )

        return None
    except Exception:
        return None
