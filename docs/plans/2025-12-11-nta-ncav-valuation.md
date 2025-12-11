# NTA and NCAV Valuation Metrics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add P/NTA (Price to Net Tangible Assets) and P/NCAV (Price to Net Current Asset Value) metrics to the stock query response.

**Architecture:** Fetch balance sheet data from Alpha Vantage BALANCE_SHEET API, cache in SQLite (same pattern as income_statements), calculate NTA/NCAV/P-ratios, display in bot response alongside existing P/E.

**Tech Stack:** Alpha Vantage API, SQLite, existing project patterns

---

## Task 1: Add Balance Sheet Data Models

**Files:**
- Modify: `src/stock_index_info/models.py`

**Step 1: Add BalanceSheetRecord dataclass**

Add after `CachedIncome` class (around line 88):

```python
@dataclass
class BalanceSheetRecord:
    """Annual balance sheet record for a stock."""

    ticker: str
    fiscal_year: int
    total_assets: float
    total_liabilities: float
    total_current_assets: float
    goodwill: float
    intangible_assets: float


@dataclass
class CachedBalanceSheet:
    """Cached balance sheet data for a stock."""

    ticker: str
    last_updated: str  # ISO format date
    annual_records: list[BalanceSheetRecord]


@dataclass
class AssetValuationResult:
    """NTA and NCAV calculation result."""

    nta: float  # Net Tangible Assets
    ncav: float  # Net Current Asset Value
    p_nta: Optional[float]  # P/NTA ratio, None if NTA <= 0
    p_ncav: Optional[float]  # P/NCAV ratio, None if NCAV <= 0
```

**Step 2: Run type check**

Run: `uv run mypy src/stock_index_info/models.py`
Expected: Success

**Step 3: Commit**

```bash
git add src/stock_index_info/models.py
git commit -m "feat(models): add BalanceSheetRecord and AssetValuationResult dataclasses"
```

---

## Task 2: Add Balance Sheet Database Schema and Functions

**Files:**
- Modify: `src/stock_index_info/db.py`
- Create: `tests/test_balance_sheet_db.py`

**Step 1: Write failing test for save_balance_sheet**

Create `tests/test_balance_sheet_db.py`:

```python
"""Tests for balance sheet database operations."""

import pytest

from stock_index_info.db import save_balance_sheet, get_cached_balance_sheet
from stock_index_info.models import BalanceSheetRecord


def test_save_and_get_balance_sheet(db_connection):
    """Test saving and retrieving balance sheet data."""
    records = [
        BalanceSheetRecord(
            ticker="TEST",
            fiscal_year=2024,
            total_assets=100_000_000,
            total_liabilities=50_000_000,
            total_current_assets=30_000_000,
            goodwill=5_000_000,
            intangible_assets=3_000_000,
        ),
        BalanceSheetRecord(
            ticker="TEST",
            fiscal_year=2023,
            total_assets=90_000_000,
            total_liabilities=45_000_000,
            total_current_assets=28_000_000,
            goodwill=5_000_000,
            intangible_assets=3_000_000,
        ),
    ]

    save_balance_sheet(db_connection, "TEST", records, "2025-01-15")
    cached = get_cached_balance_sheet(db_connection, "TEST")

    assert cached is not None
    assert cached.ticker == "TEST"
    assert cached.last_updated == "2025-01-15"
    assert len(cached.annual_records) == 2
    assert cached.annual_records[0].fiscal_year == 2024
    assert cached.annual_records[0].total_assets == 100_000_000


def test_get_cached_balance_sheet_not_found(db_connection):
    """Test getting balance sheet for non-existent ticker."""
    cached = get_cached_balance_sheet(db_connection, "NOTFOUND")
    assert cached is None


def test_save_balance_sheet_replaces_existing(db_connection):
    """Test that saving balance sheet replaces existing data."""
    old_records = [
        BalanceSheetRecord(
            ticker="TEST",
            fiscal_year=2023,
            total_assets=80_000_000,
            total_liabilities=40_000_000,
            total_current_assets=25_000_000,
            goodwill=4_000_000,
            intangible_assets=2_000_000,
        ),
    ]
    save_balance_sheet(db_connection, "TEST", old_records, "2024-01-01")

    new_records = [
        BalanceSheetRecord(
            ticker="TEST",
            fiscal_year=2024,
            total_assets=100_000_000,
            total_liabilities=50_000_000,
            total_current_assets=30_000_000,
            goodwill=5_000_000,
            intangible_assets=3_000_000,
        ),
    ]
    save_balance_sheet(db_connection, "TEST", new_records, "2025-01-15")

    cached = get_cached_balance_sheet(db_connection, "TEST")

    assert cached is not None
    assert len(cached.annual_records) == 1
    assert cached.annual_records[0].fiscal_year == 2024
    assert cached.last_updated == "2025-01-15"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_balance_sheet_db.py -v`
Expected: FAIL with "ImportError: cannot import name 'save_balance_sheet'"

**Step 3: Add schema and imports to db.py**

In `src/stock_index_info/db.py`, update the imports (line 8-14):

```python
from stock_index_info.models import (
    ConstituentRecord,
    IndexMembership,
    INDEX_NAMES,
    IncomeRecord,
    CachedIncome,
    BalanceSheetRecord,
    CachedBalanceSheet,
)
```

Add to SCHEMA (after line 39, before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS balance_sheets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    total_assets REAL NOT NULL,
    total_liabilities REAL NOT NULL,
    total_current_assets REAL NOT NULL,
    goodwill REAL NOT NULL,
    intangible_assets REAL NOT NULL,
    last_updated TEXT NOT NULL,
    UNIQUE(ticker, fiscal_year)
);

CREATE INDEX IF NOT EXISTS idx_balance_sheets_ticker ON balance_sheets(ticker);
```

**Step 4: Implement save_balance_sheet function**

Add at end of `db.py`:

```python
def save_balance_sheet(
    conn: sqlite3.Connection,
    ticker: str,
    records: list[BalanceSheetRecord],
    last_updated: str,
) -> None:
    """Save balance sheet records for a ticker, replacing any existing data."""
    ticker_upper = ticker.upper()

    # Delete existing data for this ticker
    conn.execute("DELETE FROM balance_sheets WHERE ticker = ?", (ticker_upper,))

    # Insert new records
    for record in records:
        conn.execute(
            """
            INSERT INTO balance_sheets (
                ticker, fiscal_year, total_assets, total_liabilities,
                total_current_assets, goodwill, intangible_assets, last_updated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker_upper,
                record.fiscal_year,
                record.total_assets,
                record.total_liabilities,
                record.total_current_assets,
                record.goodwill,
                record.intangible_assets,
                last_updated,
            ),
        )
    conn.commit()


def get_cached_balance_sheet(
    conn: sqlite3.Connection, ticker: str
) -> Optional[CachedBalanceSheet]:
    """Get cached balance sheet for a ticker, or None if not cached."""
    ticker_upper = ticker.upper()

    cursor = conn.execute(
        """
        SELECT fiscal_year, total_assets, total_liabilities, total_current_assets,
               goodwill, intangible_assets, last_updated
        FROM balance_sheets
        WHERE ticker = ?
        ORDER BY fiscal_year DESC
        """,
        (ticker_upper,),
    )

    rows = cursor.fetchall()
    if not rows:
        return None

    records = [
        BalanceSheetRecord(
            ticker=ticker_upper,
            fiscal_year=row[0],
            total_assets=row[1],
            total_liabilities=row[2],
            total_current_assets=row[3],
            goodwill=row[4],
            intangible_assets=row[5],
        )
        for row in rows
    ]

    return CachedBalanceSheet(
        ticker=ticker_upper,
        last_updated=rows[0][6],  # All rows have same last_updated
        annual_records=records,
    )
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_balance_sheet_db.py -v`
Expected: All 3 tests PASS

**Step 6: Run code checks**

Run: `uv run ruff check src/stock_index_info/db.py tests/test_balance_sheet_db.py`
Expected: No errors

Run: `uv run mypy src/stock_index_info/db.py`
Expected: Success

**Step 7: Commit**

```bash
git add src/stock_index_info/db.py tests/test_balance_sheet_db.py
git commit -m "feat(db): add balance sheet table and cache functions"
```

---

## Task 3: Create Balance Sheet API Module

**Files:**
- Create: `src/stock_index_info/balance_sheet.py`
- Create: `tests/test_balance_sheet.py`

**Step 1: Write failing tests for fetch_balance_sheet**

Create `tests/test_balance_sheet.py`:

```python
"""Tests for balance sheet module."""

import pytest

from stock_index_info.models import BalanceSheetRecord, AssetValuationResult


def test_fetch_balance_sheet_valid_ticker():
    """Test fetching balance sheet for a valid ticker."""
    from stock_index_info.config import ALPHA_VANTAGE_API_KEY
    from stock_index_info.balance_sheet import fetch_balance_sheet

    if not ALPHA_VANTAGE_API_KEY:
        pytest.skip("ALPHA_VANTAGE_API_KEY not set")

    records = fetch_balance_sheet("IBM")

    assert records is not None
    assert len(records) >= 1
    assert all(r.ticker == "IBM" for r in records)
    assert all(r.fiscal_year >= 2000 for r in records)
    # Total assets should be large for IBM
    assert all(r.total_assets > 1_000_000_000 for r in records)
    # Should be sorted by year descending
    years = [r.fiscal_year for r in records]
    assert years == sorted(years, reverse=True)


def test_fetch_balance_sheet_invalid_ticker():
    """Test fetching balance sheet for invalid ticker returns None."""
    from stock_index_info.config import ALPHA_VANTAGE_API_KEY
    from stock_index_info.balance_sheet import fetch_balance_sheet

    if not ALPHA_VANTAGE_API_KEY:
        pytest.skip("ALPHA_VANTAGE_API_KEY not set")

    records = fetch_balance_sheet("INVALIDTICKER12345")
    assert records is None


def test_fetch_balance_sheet_no_api_key(monkeypatch):
    """Test that fetch returns None when API key not configured."""
    from stock_index_info import balance_sheet
    from stock_index_info.balance_sheet import fetch_balance_sheet

    monkeypatch.setattr(balance_sheet, "ALPHA_VANTAGE_API_KEY", None)

    records = fetch_balance_sheet("AAPL")
    assert records is None


def test_calculate_asset_valuation_positive():
    """Test calculating NTA and NCAV with positive values."""
    from stock_index_info.balance_sheet import calculate_asset_valuation

    record = BalanceSheetRecord(
        ticker="TEST",
        fiscal_year=2024,
        total_assets=100_000_000_000,  # $100B
        total_liabilities=50_000_000_000,  # $50B
        total_current_assets=40_000_000_000,  # $40B
        goodwill=5_000_000_000,  # $5B
        intangible_assets=3_000_000_000,  # $3B
    )
    market_cap = 200_000_000_000.0  # $200B

    # NTA = 100B - 50B - 5B - 3B = 42B
    # NCAV = 40B - 50B = -10B
    # P/NTA = 200B / 42B = 4.76
    # P/NCAV = N/A (negative NCAV)

    result = calculate_asset_valuation(record, market_cap)

    assert result is not None
    assert abs(result.nta - 42_000_000_000) < 1
    assert abs(result.ncav - (-10_000_000_000)) < 1
    assert result.p_nta is not None
    assert abs(result.p_nta - 4.76) < 0.01
    assert result.p_ncav is None  # NCAV is negative


def test_calculate_asset_valuation_negative_nta():
    """Test calculating when NTA is negative."""
    from stock_index_info.balance_sheet import calculate_asset_valuation

    record = BalanceSheetRecord(
        ticker="TEST",
        fiscal_year=2024,
        total_assets=50_000_000_000,
        total_liabilities=60_000_000_000,
        total_current_assets=20_000_000_000,
        goodwill=5_000_000_000,
        intangible_assets=3_000_000_000,
    )
    market_cap = 100_000_000_000.0

    # NTA = 50B - 60B - 5B - 3B = -18B
    # NCAV = 20B - 60B = -40B

    result = calculate_asset_valuation(record, market_cap)

    assert result is not None
    assert result.nta < 0
    assert result.ncav < 0
    assert result.p_nta is None
    assert result.p_ncav is None


def test_calculate_asset_valuation_positive_ncav():
    """Test calculating when NCAV is positive (Graham value stock)."""
    from stock_index_info.balance_sheet import calculate_asset_valuation

    record = BalanceSheetRecord(
        ticker="TEST",
        fiscal_year=2024,
        total_assets=100_000_000_000,
        total_liabilities=30_000_000_000,  # Low debt
        total_current_assets=50_000_000_000,  # High current assets
        goodwill=2_000_000_000,
        intangible_assets=1_000_000_000,
    )
    market_cap = 40_000_000_000.0

    # NTA = 100B - 30B - 2B - 1B = 67B
    # NCAV = 50B - 30B = 20B
    # P/NTA = 40B / 67B = 0.60
    # P/NCAV = 40B / 20B = 2.0

    result = calculate_asset_valuation(record, market_cap)

    assert result is not None
    assert result.p_nta is not None
    assert abs(result.p_nta - 0.597) < 0.01
    assert result.p_ncav is not None
    assert abs(result.p_ncav - 2.0) < 0.01


def test_get_asset_valuation_with_cache(db_connection):
    """Test getting asset valuation uses cache when available."""
    from stock_index_info.balance_sheet import get_asset_valuation
    from stock_index_info.db import save_balance_sheet

    records = [
        BalanceSheetRecord(
            ticker="TEST",
            fiscal_year=2024,
            total_assets=100_000_000_000,
            total_liabilities=50_000_000_000,
            total_current_assets=40_000_000_000,
            goodwill=5_000_000_000,
            intangible_assets=3_000_000_000,
        ),
    ]
    save_balance_sheet(db_connection, "TEST", records, "2025-01-15")

    result = get_asset_valuation(
        db_connection, "TEST", market_cap=200_000_000_000.0
    )

    assert result is not None
    assert abs(result.nta - 42_000_000_000) < 1
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_balance_sheet.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'stock_index_info.balance_sheet'"

**Step 3: Create balance_sheet.py module**

Create `src/stock_index_info/balance_sheet.py`:

```python
"""Balance sheet data fetching and valuation calculations."""

import logging
import sqlite3
from datetime import date
from typing import Optional

from curl_cffi import requests

from stock_index_info.config import ALPHA_VANTAGE_API_KEY
from stock_index_info.db import get_cached_balance_sheet, save_balance_sheet
from stock_index_info.exchange_rate import convert_to_usd
from stock_index_info.models import BalanceSheetRecord, CachedBalanceSheet, AssetValuationResult

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
                    total_current_assets_usd = convert_to_usd(total_current_assets, reported_currency)
                    goodwill_usd = convert_to_usd(goodwill, reported_currency)
                    intangible_assets_usd = convert_to_usd(intangible_assets, reported_currency)

                    if any(
                        v is None
                        for v in [
                            total_assets_usd,
                            total_liabilities_usd,
                            total_current_assets_usd,
                            goodwill_usd,
                            intangible_assets_usd,
                        ]
                    ):
                        logger.warning(
                            f"Failed to convert {ticker_upper} balance sheet from {reported_currency} to USD"
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
        record.total_assets
        - record.total_liabilities
        - record.goodwill
        - record.intangible_assets
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
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_balance_sheet.py -v`
Expected: All 7 tests PASS (2 skipped if no API key)

**Step 5: Run code checks**

Run: `uv run ruff check src/stock_index_info/balance_sheet.py tests/test_balance_sheet.py`
Expected: No errors

Run: `uv run mypy src/stock_index_info/balance_sheet.py`
Expected: Success

**Step 6: Commit**

```bash
git add src/stock_index_info/balance_sheet.py tests/test_balance_sheet.py
git commit -m "feat: add balance sheet API module with NTA/NCAV calculations"
```

---

## Task 4: Integrate Asset Valuation into Bot Response

**Files:**
- Modify: `src/stock_index_info/bot.py`

**Step 1: Add imports**

In `bot.py`, add import after existing imports (around line 36):

```python
from stock_index_info.balance_sheet import get_asset_valuation
```

**Step 2: Modify _query_ticker function**

In the `_query_ticker` function, add asset valuation display after the P/E section.

Find this block (around lines 265-270):

```python
        # Calculate and display 7-year average P/E (at the top)
        pe_result = get_7year_pe(conn, ticker, latest_filing_date=latest_filing_date)
        if pe_result is not None:
            lines.append(
                f"P/E (7Y Avg): {pe_result.pe:.1f} | Avg Income: {format_currency(pe_result.avg_income)}"
            )
            lines.append("")
```

Replace with:

```python
        # Get market cap once for all valuation calculations
        from stock_index_info.alpha_vantage import get_market_cap
        market_cap = get_market_cap(ticker)

        # Calculate and display 7-year average P/E (at the top)
        pe_result = get_7year_pe(conn, ticker, market_cap=market_cap, latest_filing_date=latest_filing_date)
        if pe_result is not None:
            lines.append(
                f"P/E (7Y Avg): {pe_result.pe:.1f} | Avg Income: {format_currency(pe_result.avg_income)}"
            )

        # Calculate and display NTA/NCAV valuation
        if market_cap is not None:
            asset_val = get_asset_valuation(
                conn, ticker, market_cap=market_cap, latest_filing_date=latest_filing_date
            )
            if asset_val is not None:
                # P/NTA line
                p_nta_str = f"{asset_val.p_nta:.1f}x" if asset_val.p_nta is not None else "N/A"
                lines.append(f"P/NTA: {p_nta_str} | NTA: {format_currency(asset_val.nta)}")

                # P/NCAV line
                p_ncav_str = f"{asset_val.p_ncav:.1f}x" if asset_val.p_ncav is not None else "N/A"
                lines.append(f"P/NCAV: {p_ncav_str} | NCAV: {format_currency(asset_val.ncav)}")

        # Add blank line after valuation metrics
        if pe_result is not None or (market_cap is not None and asset_val is not None):
            lines.append("")
```

**Step 3: Run code checks**

Run: `uv run ruff check src/stock_index_info/bot.py`
Expected: No errors

Run: `uv run mypy src/stock_index_info/bot.py`
Expected: Success

**Step 4: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/stock_index_info/bot.py
git commit -m "feat(bot): display P/NTA and P/NCAV in ticker query response"
```

---

## Task 5: Final Verification

**Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 2: Run full code checks**

Run: `uv run ruff check src/ tests/`
Expected: No errors

Run: `uv run mypy src/`
Expected: Success

**Step 3: Verify output format (optional manual test)**

If bot is configured, test with a ticker like `AAPL`. Expected output format:

```
*AAPL*

P/E (7Y Avg): 28.5 | Avg Income: $95.2B
P/NTA: 45.2x | NTA: $65.3B
P/NCAV: N/A | NCAV: -$120.5B

Index Membership:
...
```

**Step 4: Commit and push**

```bash
git push
```

---

## File Changes Summary

| Operation | File Path |
|-----------|-----------|
| Modify | `src/stock_index_info/models.py` |
| Modify | `src/stock_index_info/db.py` |
| Create | `tests/test_balance_sheet_db.py` |
| Create | `src/stock_index_info/balance_sheet.py` |
| Create | `tests/test_balance_sheet.py` |
| Modify | `src/stock_index_info/bot.py` |
