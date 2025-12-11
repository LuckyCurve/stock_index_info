"""Balance sheet data fetching and valuation calculations."""

import logging
import sqlite3
from datetime import date
from typing import Optional

from curl_cffi import requests

from stock_index_info.config import ALPHA_VANTAGE_API_KEY
from stock_index_info.db import get_cached_balance_sheet, save_balance_sheet
from stock_index_info.exchange_rate import convert_to_usd
from stock_index_info.models import (
    AssetValuationResult,
    BalanceSheetRecord,
)

logger = logging.getLogger(__name__)


def fetch_balance_sheet(ticker: str) -> Optional[list[BalanceSheetRecord]]:
    """Fetch annual balance sheet data from Alpha Vantage BALANCE_SHEET API.

    Values are converted to USD if reported in a different currency.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        List of BalanceSheetRecord sorted by fiscal_year descending,
        or None if API key not configured or ticker not found.
    """
    if not ALPHA_VANTAGE_API_KEY:
        return None

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "BALANCE_SHEET",
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

        records: list[BalanceSheetRecord] = []
        ticker_upper = ticker.upper()

        # Get reported currency from the first report
        reported_currency = annual_reports[0].get("reportedCurrency", "USD")
        if reported_currency != "USD":
            logger.info(f"{ticker_upper} reports in {reported_currency}, will convert to USD")

        for entry in annual_reports:
            fiscal_date = entry.get("fiscalDateEnding", "")

            # Extract required fields, treating "None" as 0
            def get_float(key: str) -> Optional[float]:
                val = entry.get(key, "0")
                if val is None or val == "None" or val == "":
                    return 0.0
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return None

            total_assets = get_float("totalAssets")
            total_liabilities = get_float("totalLiabilities")
            total_current_assets = get_float("totalCurrentAssets")
            goodwill = get_float("goodwill")
            intangible_assets = get_float("intangibleAssets")

            # Skip if essential fields are missing
            if total_assets is None or total_liabilities is None or total_current_assets is None:
                continue
            if goodwill is None:
                goodwill = 0.0
            if intangible_assets is None:
                intangible_assets = 0.0

            try:
                fiscal_year = int(fiscal_date[:4])

                # Convert to USD if necessary
                if reported_currency != "USD":
                    total_assets_usd = convert_to_usd(total_assets, reported_currency)
                    total_liabilities_usd = convert_to_usd(total_liabilities, reported_currency)
                    total_current_assets_usd = convert_to_usd(
                        total_current_assets, reported_currency
                    )
                    goodwill_usd = convert_to_usd(goodwill, reported_currency)
                    intangible_assets_usd = convert_to_usd(intangible_assets, reported_currency)

                    if (
                        total_assets_usd is None
                        or total_liabilities_usd is None
                        or total_current_assets_usd is None
                        or goodwill_usd is None
                        or intangible_assets_usd is None
                    ):
                        logger.warning(
                            f"Failed to convert {ticker_upper} balance sheet "
                            f"from {reported_currency} to USD"
                        )
                        return None

                    total_assets = total_assets_usd
                    total_liabilities = total_liabilities_usd
                    total_current_assets = total_current_assets_usd
                    goodwill = goodwill_usd
                    intangible_assets = intangible_assets_usd

                records.append(
                    BalanceSheetRecord(
                        ticker=ticker_upper,
                        fiscal_year=fiscal_year,
                        total_assets=total_assets,
                        total_liabilities=total_liabilities,
                        total_current_assets=total_current_assets,
                        goodwill=goodwill,
                        intangible_assets=intangible_assets,
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


def calculate_asset_valuation(
    record: BalanceSheetRecord,
    market_cap: float,
) -> AssetValuationResult:
    """Calculate NTA and NCAV valuation metrics.

    Args:
        record: Most recent balance sheet record
        market_cap: Current market capitalization in dollars

    Returns:
        AssetValuationResult with NTA, NCAV, and P-ratios.
        P-ratios are None if the underlying value is <= 0.
    """
    # NTA = Total Assets - Total Liabilities - Goodwill - Intangible Assets
    nta = (
        record.total_assets - record.total_liabilities - record.goodwill - record.intangible_assets
    )

    # NCAV = Total Current Assets - Total Liabilities
    ncav = record.total_current_assets - record.total_liabilities

    # Calculate P-ratios (None if denominator <= 0)
    p_nta = market_cap / nta if nta > 0 else None
    p_ncav = market_cap / ncav if ncav > 0 else None

    return AssetValuationResult(
        nta=nta,
        ncav=ncav,
        p_nta=p_nta,
        p_ncav=p_ncav,
    )


def get_asset_valuation(
    conn: sqlite3.Connection,
    ticker: str,
    market_cap: Optional[float] = None,
    latest_filing_date: Optional[str] = None,
) -> Optional[AssetValuationResult]:
    """Get NTA and NCAV valuation for a ticker.

    Uses cached balance sheet data if available and not stale. Fetches from
    Alpha Vantage if cache is empty or if latest_filing_date is newer than cache.

    Args:
        conn: Database connection
        ticker: Stock ticker symbol
        market_cap: Current market cap (required)
        latest_filing_date: Latest SEC filing date (ISO format). If newer than
                           cache last_updated, triggers cache refresh.

    Returns:
        AssetValuationResult or None if no data available.
    """
    if market_cap is None:
        return None

    ticker_upper = ticker.upper()

    # Get cached data
    cached = get_cached_balance_sheet(conn, ticker_upper)

    # Determine if we need to refresh cache
    need_refresh = False
    if cached is None:
        need_refresh = True
    elif latest_filing_date and latest_filing_date > cached.last_updated:
        need_refresh = True

    # Refresh cache if needed
    if need_refresh:
        new_records = fetch_balance_sheet(ticker_upper)
        if new_records:
            today = date.today().isoformat()
            save_balance_sheet(conn, ticker_upper, new_records, today)
            cached = get_cached_balance_sheet(conn, ticker_upper)

    # Check if we have data
    if cached is None or not cached.annual_records:
        return None

    # Use most recent balance sheet
    most_recent = cached.annual_records[0]

    return calculate_asset_valuation(most_recent, market_cap)
