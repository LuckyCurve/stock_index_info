"""Alpha Vantage API client for fetching earnings data."""

from typing import Optional

from curl_cffi import requests

from stock_index_info.config import ALPHA_VANTAGE_API_KEY
from stock_index_info.models import EarningsRecord


def fetch_annual_eps(ticker: str) -> Optional[list[EarningsRecord]]:
    """Fetch annual EPS data from Alpha Vantage EARNINGS API.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        List of EarningsRecord sorted by fiscal_year descending,
        or None if API key not configured or ticker not found.
    """
    if not ALPHA_VANTAGE_API_KEY:
        return None

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "EARNINGS",
        "symbol": ticker.upper(),
        "apikey": ALPHA_VANTAGE_API_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Check for error responses
        if "Error Message" in data or "Note" in data:
            return None

        annual_earnings = data.get("annualEarnings", [])
        if not annual_earnings:
            return None

        records: list[EarningsRecord] = []
        ticker_upper = ticker.upper()

        for entry in annual_earnings:
            fiscal_date = entry.get("fiscalDateEnding", "")
            eps_str = entry.get("reportedEPS", "")

            # Skip entries with missing or invalid data
            if not fiscal_date or not eps_str or eps_str == "None":
                continue

            try:
                fiscal_year = int(fiscal_date[:4])
                eps = float(eps_str)
                records.append(
                    EarningsRecord(ticker=ticker_upper, fiscal_year=fiscal_year, eps=eps)
                )
            except (ValueError, TypeError):
                continue

        if not records:
            return None

        # Sort by fiscal year descending
        records.sort(key=lambda r: r.fiscal_year, reverse=True)
        return records

    except Exception:
        return None
