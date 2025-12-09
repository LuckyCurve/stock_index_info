"""Alpha Vantage API client for fetching income statement data."""

import sqlite3
from datetime import date
from typing import Optional

from curl_cffi import requests
import yfinance as yf

from stock_index_info.config import ALPHA_VANTAGE_API_KEY
from stock_index_info.db import get_cached_income, save_income
from stock_index_info.models import IncomeRecord


def fetch_annual_net_income(ticker: str) -> Optional[list[IncomeRecord]]:
    """Fetch annual net income data from Alpha Vantage INCOME_STATEMENT API.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        List of IncomeRecord sorted by fiscal_year descending,
        or None if API key not configured or ticker not found.
    """
    if not ALPHA_VANTAGE_API_KEY:
        return None

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "INCOME_STATEMENT",
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

        annual_reports = data.get("annualReports", [])
        if not annual_reports:
            return None

        records: list[IncomeRecord] = []
        ticker_upper = ticker.upper()

        for entry in annual_reports:
            fiscal_date = entry.get("fiscalDateEnding", "")
            net_income_str = entry.get("netIncome", "")

            # Skip entries with missing or invalid data
            if not fiscal_date or not net_income_str or net_income_str == "None":
                continue

            try:
                fiscal_year = int(fiscal_date[:4])
                net_income = float(net_income_str)
                records.append(
                    IncomeRecord(
                        ticker=ticker_upper,
                        fiscal_year=fiscal_year,
                        net_income=net_income,
                    )
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


def get_market_cap(ticker: str) -> Optional[float]:
    """Get current market capitalization using yfinance.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Market cap in dollars as float, or None if not found.
    """
    try:
        stock = yf.Ticker(ticker.upper())
        # Try to get market cap from info
        info = stock.info
        if info and "marketCap" in info:
            market_cap = info["marketCap"]
            if market_cap is not None:
                return float(market_cap)
        return None
    except Exception:
        return None


def calculate_7year_avg_pe(
    income_records: list[IncomeRecord],
    market_cap: float,
) -> Optional[float]:
    """Calculate P/E ratio using 7-year average net income.

    Args:
        income_records: List of IncomeRecord, should be sorted by fiscal_year descending
        market_cap: Current market capitalization in dollars

    Returns:
        P/E ratio, or None if:
        - Less than 7 years of data
        - Years are not consecutive
        - Average net income <= 0
    """
    if len(income_records) < 7:
        return None

    # Take the 7 most recent years
    recent_7 = income_records[:7]

    # Check for consecutive years
    years = [r.fiscal_year for r in recent_7]
    for i in range(len(years) - 1):
        if years[i] - years[i + 1] != 1:
            return None

    avg_net_income = sum(r.net_income for r in recent_7) / 7

    if avg_net_income <= 0:
        return None

    return market_cap / avg_net_income


def get_7year_pe(
    conn: sqlite3.Connection,
    ticker: str,
    market_cap: Optional[float] = None,
    latest_filing_date: Optional[str] = None,
) -> Optional[float]:
    """Get 7-year average P/E ratio for a ticker.

    Uses cached net income data if available and not stale. Fetches from Alpha Vantage
    if cache is empty or if latest_filing_date is newer than cache.

    Args:
        conn: Database connection
        ticker: Stock ticker symbol
        market_cap: Current market cap (fetched via yfinance if not provided)
        latest_filing_date: Latest SEC filing date (ISO format). If newer than
                           cache last_updated, triggers cache refresh.

    Returns:
        7-year average P/E ratio, or None if insufficient data.
    """
    ticker_upper = ticker.upper()

    # Get cached data
    cached = get_cached_income(conn, ticker_upper)

    # Determine if we need to refresh cache
    need_refresh = False
    if cached is None:
        need_refresh = True
    elif latest_filing_date and latest_filing_date > cached.last_updated:
        need_refresh = True

    # Refresh cache if needed
    if need_refresh:
        new_records = fetch_annual_net_income(ticker_upper)
        if new_records:
            today = date.today().isoformat()
            save_income(conn, ticker_upper, new_records, today)
            cached = get_cached_income(conn, ticker_upper)

    # Check if we have enough data
    if cached is None or len(cached.annual_income) < 7:
        return None

    # Get market cap if not provided
    if market_cap is None:
        market_cap = get_market_cap(ticker_upper)
        if market_cap is None:
            return None

    return calculate_7year_avg_pe(cached.annual_income, market_cap)
