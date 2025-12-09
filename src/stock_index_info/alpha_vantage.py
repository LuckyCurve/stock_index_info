"""Alpha Vantage API client for fetching earnings data."""

from typing import Optional

from curl_cffi import requests
import yfinance as yf

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


def get_current_price(ticker: str) -> Optional[float]:
    """Get current stock price using yfinance.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Current price as float, or None if not found.
    """
    try:
        stock = yf.Ticker(ticker.upper())
        # Try to get price from history (more reliable)
        hist = stock.history(period="1d")
        if not hist.empty and "Close" in hist.columns:
            price = hist["Close"].iloc[-1]
            return float(price) if price else None
        # Fall back to fast_info
        try:
            price = stock.fast_info.last_price
            if price is not None:
                return float(price)
        except Exception:
            pass
        return None
    except Exception:
        return None


def calculate_7year_avg_pe(
    earnings: list[EarningsRecord],
    current_price: float,
) -> Optional[float]:
    """Calculate P/E ratio using 7-year average EPS.

    Args:
        earnings: List of EarningsRecord, should be sorted by fiscal_year descending
        current_price: Current stock price

    Returns:
        P/E ratio, or None if insufficient data (< 7 years) or avg EPS <= 0
    """
    if len(earnings) < 7:
        return None

    # Take the 7 most recent years
    recent_7 = earnings[:7]
    avg_eps = sum(r.eps for r in recent_7) / 7

    if avg_eps <= 0:
        return None

    return current_price / avg_eps
