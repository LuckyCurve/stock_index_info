"""SEC EDGAR API client for fetching company filings."""

from typing import Optional

from curl_cffi import requests


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
