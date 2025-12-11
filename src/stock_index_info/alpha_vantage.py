"""Alpha Vantage API client for fetching income statement data."""

import logging
import sqlite3
import time
from datetime import date
from typing import Optional

from curl_cffi import requests
import yfinance as yf

from stock_index_info.config import ALPHA_VANTAGE_API_KEY
from stock_index_info.db import get_cached_income, save_income
from stock_index_info.exchange_rate import convert_to_usd
from stock_index_info.models import IncomeRecord, PEResult

logger = logging.getLogger(__name__)


def format_currency(amount: float) -> str:
    """Format a dollar amount in a compact human-readable format.

    Args:
        amount: Dollar amount (can be negative)

    Returns:
        Formatted string like "$12.5B", "$500.0M", "$50.0K", or "$5000"
    """
    negative = amount < 0
    abs_amount = abs(amount)
    prefix = "-" if negative else ""

    if abs_amount >= 1_000_000_000:
        return f"{prefix}${abs_amount / 1_000_000_000:.1f}B"
    elif abs_amount >= 1_000_000:
        return f"{prefix}${abs_amount / 1_000_000:.1f}M"
    elif abs_amount >= 10_000:
        return f"{prefix}${abs_amount / 1_000:.1f}K"
    else:
        return f"{prefix}${int(abs_amount)}"


def fetch_annual_net_income(ticker: str) -> Optional[list[IncomeRecord]]:
    """Fetch annual net income data from Alpha Vantage INCOME_STATEMENT API.

    Net income values are converted to USD if reported in a different currency.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        List of IncomeRecord sorted by fiscal_year descending (net_income in USD),
        or None if API key not configured or ticker not found.
    """
    ticker_upper = ticker.upper()

    if not ALPHA_VANTAGE_API_KEY:
        logger.error(
            f"[API] fetch_annual_net_income({ticker_upper}): "
            "ALPHA_VANTAGE_API_KEY not configured, skipping request"
        )
        return None

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "INCOME_STATEMENT",
        "symbol": ticker.upper(),
        "apikey": ALPHA_VANTAGE_API_KEY,
    }

    logger.info(
        f"[API] fetch_annual_net_income({ticker_upper}): requesting Alpha Vantage INCOME_STATEMENT"
    )
    start_time = time.time()

    try:
        response = requests.get(url, params=params, timeout=30)
        elapsed_ms = (time.time() - start_time) * 1000
        response.raise_for_status()
        data = response.json()

        logger.info(
            f"[API] fetch_annual_net_income({ticker_upper}): "
            f"response status={response.status_code}, elapsed={elapsed_ms:.0f}ms"
        )

        # Check for error responses
        if "Error Message" in data:
            logger.warning(
                f"[API] fetch_annual_net_income({ticker_upper}): "
                f"API returned error: {data.get('Error Message')}"
            )
            return None
        if "Note" in data:
            logger.warning(
                f"[API] fetch_annual_net_income({ticker_upper}): "
                f"API rate limit or note: {data.get('Note')}"
            )
            return None

        annual_reports = data.get("annualReports", [])
        if not annual_reports:
            logger.warning(
                f"[API] fetch_annual_net_income({ticker_upper}): no annualReports in response"
            )
            return None

        records: list[IncomeRecord] = []

        # Get reported currency from the first report (same for all reports)
        reported_currency = annual_reports[0].get("reportedCurrency", "USD")
        if reported_currency != "USD":
            logger.info(f"{ticker_upper} reports in {reported_currency}, will convert to USD")

        for entry in annual_reports:
            fiscal_date = entry.get("fiscalDateEnding", "")
            net_income_str = entry.get("netIncome", "")

            # Skip entries with missing or invalid data
            if not fiscal_date or not net_income_str or net_income_str == "None":
                continue

            try:
                fiscal_year = int(fiscal_date[:4])
                net_income = float(net_income_str)

                # Convert to USD if necessary
                if reported_currency != "USD":
                    net_income_usd = convert_to_usd(net_income, reported_currency)
                    if net_income_usd is None:
                        logger.warning(
                            f"Failed to convert {ticker_upper} net income from {reported_currency} to USD"
                        )
                        return None
                    net_income = net_income_usd

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
            logger.warning(
                f"[API] fetch_annual_net_income({ticker_upper}): no valid records after parsing"
            )
            return None

        # Sort by fiscal year descending
        records.sort(key=lambda r: r.fiscal_year, reverse=True)
        logger.info(
            f"[API] fetch_annual_net_income({ticker_upper}): "
            f"successfully parsed {len(records)} annual records"
        )
        return records

    except requests.RequestsError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[API] fetch_annual_net_income({ticker_upper}): "
            f"request failed after {elapsed_ms:.0f}ms - {type(e).__name__}: {e}"
        )
        return None
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[API] fetch_annual_net_income({ticker_upper}): "
            f"unexpected error after {elapsed_ms:.0f}ms - {type(e).__name__}: {e}",
            exc_info=True,
        )
        return None


def get_market_cap(ticker: str) -> Optional[float]:
    """Get current market capitalization.

    Tries yfinance first, falls back to Alpha Vantage OVERVIEW endpoint.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Market cap in dollars as float, or None if not found.
    """
    ticker_upper = ticker.upper()

    # Try yfinance first
    logger.info(f"[API] get_market_cap({ticker_upper}): requesting from yfinance")
    yf_start_time = time.time()
    try:
        stock = yf.Ticker(ticker_upper)
        info = stock.info
        yf_elapsed_ms = (time.time() - yf_start_time) * 1000
        if info and "marketCap" in info:
            market_cap = info["marketCap"]
            if market_cap is not None:
                logger.info(
                    f"[API] get_market_cap({ticker_upper}): "
                    f"yfinance returned {market_cap}, elapsed={yf_elapsed_ms:.0f}ms"
                )
                return float(market_cap)
        logger.warning(
            f"[API] get_market_cap({ticker_upper}): "
            f"yfinance returned no marketCap, elapsed={yf_elapsed_ms:.0f}ms"
        )
    except Exception as e:
        yf_elapsed_ms = (time.time() - yf_start_time) * 1000
        logger.warning(
            f"[API] get_market_cap({ticker_upper}): "
            f"yfinance failed after {yf_elapsed_ms:.0f}ms - {type(e).__name__}: {e}"
        )

    # Fallback to Alpha Vantage OVERVIEW endpoint
    if not ALPHA_VANTAGE_API_KEY:
        logger.error(
            f"[API] get_market_cap({ticker_upper}): "
            "yfinance failed and ALPHA_VANTAGE_API_KEY not configured"
        )
        return None

    logger.info(f"[API] get_market_cap({ticker_upper}): falling back to Alpha Vantage OVERVIEW")
    av_start_time = time.time()

    try:
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "OVERVIEW",
            "symbol": ticker_upper,
            "apikey": ALPHA_VANTAGE_API_KEY,
        }
        response = requests.get(url, params=params, timeout=30)
        av_elapsed_ms = (time.time() - av_start_time) * 1000
        response.raise_for_status()
        data = response.json()

        logger.info(
            f"[API] get_market_cap({ticker_upper}): "
            f"Alpha Vantage OVERVIEW response status={response.status_code}, elapsed={av_elapsed_ms:.0f}ms"
        )

        if "MarketCapitalization" in data:
            market_cap_str = data["MarketCapitalization"]
            if market_cap_str and market_cap_str != "None":
                market_cap = float(market_cap_str)
                logger.info(
                    f"[API] get_market_cap({ticker_upper}): Alpha Vantage returned {market_cap}"
                )
                return market_cap

        logger.warning(
            f"[API] get_market_cap({ticker_upper}): "
            "Alpha Vantage OVERVIEW has no MarketCapitalization"
        )
        return None
    except requests.RequestsError as e:
        av_elapsed_ms = (time.time() - av_start_time) * 1000
        logger.error(
            f"[API] get_market_cap({ticker_upper}): "
            f"Alpha Vantage request failed after {av_elapsed_ms:.0f}ms - {type(e).__name__}: {e}"
        )
        return None
    except Exception as e:
        av_elapsed_ms = (time.time() - av_start_time) * 1000
        logger.error(
            f"[API] get_market_cap({ticker_upper}): "
            f"unexpected error after {av_elapsed_ms:.0f}ms - {type(e).__name__}: {e}",
            exc_info=True,
        )
        return None


def calculate_7year_avg_pe(
    income_records: list[IncomeRecord],
    market_cap: float,
) -> Optional[PEResult]:
    """Calculate P/E ratio using 7-year average net income.

    Args:
        income_records: List of IncomeRecord, should be sorted by fiscal_year descending
        market_cap: Current market capitalization in dollars

    Returns:
        PEResult with P/E ratio and average income, or None if:
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

    pe = market_cap / avg_net_income
    return PEResult(pe=pe, avg_income=avg_net_income)


def get_7year_pe(
    conn: sqlite3.Connection,
    ticker: str,
    market_cap: Optional[float] = None,
    latest_filing_date: Optional[str] = None,
) -> Optional[PEResult]:
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
        PEResult with 7-year average P/E ratio and average income, or None if insufficient data.
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
