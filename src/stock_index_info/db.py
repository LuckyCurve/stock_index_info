"""SQLite database operations for stock index data."""

import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

from stock_index_info.models import (
    ConstituentRecord,
    IndexMembership,
    INDEX_NAMES,
    IncomeRecord,
    CachedIncome,
    BalanceSheetRecord,
    CachedBalanceSheet,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS constituents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    index_code TEXT NOT NULL CHECK (index_code IN ('sp500', 'nasdaq100')),
    added_date TEXT,
    removed_date TEXT,
    reason TEXT,
    UNIQUE(ticker, index_code, added_date)
);

CREATE INDEX IF NOT EXISTS idx_constituents_ticker ON constituents(ticker);
CREATE INDEX IF NOT EXISTS idx_constituents_index ON constituents(index_code);

CREATE TABLE IF NOT EXISTS income_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    net_income REAL NOT NULL,
    last_updated TEXT NOT NULL,
    UNIQUE(ticker, fiscal_year)
);

CREATE INDEX IF NOT EXISTS idx_income_statements_ticker ON income_statements(ticker);

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
"""


def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize database with schema and return connection."""
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def insert_constituent(conn: sqlite3.Connection, record: ConstituentRecord) -> None:
    """Insert a constituent record, ignoring duplicates."""
    conn.execute(
        """
        INSERT OR IGNORE INTO constituents (ticker, index_code, added_date, removed_date, reason)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            record.ticker,
            record.index_code,
            record.added_date.isoformat() if record.added_date else None,
            record.removed_date.isoformat() if record.removed_date else None,
            record.reason,
        ),
    )
    conn.commit()


def delete_index_data(conn: sqlite3.Connection, index_code: str) -> int:
    """Delete all data for an index. Returns number of rows deleted."""
    cursor = conn.execute(
        "DELETE FROM constituents WHERE index_code = ?",
        (index_code,),
    )
    conn.commit()
    return cursor.rowcount


def get_stock_memberships(conn: sqlite3.Connection, ticker: str) -> list[IndexMembership]:
    """Get all index memberships for a stock."""
    cursor = conn.execute(
        """
        SELECT index_code, added_date, removed_date, reason
        FROM constituents
        WHERE ticker = ?
        ORDER BY added_date
        """,
        (ticker.upper(),),
    )
    memberships = []
    for row in cursor.fetchall():
        index_code = row[0]
        memberships.append(
            IndexMembership(
                index_code=index_code,
                index_name=INDEX_NAMES.get(index_code, index_code),
                added_date=date.fromisoformat(row[1]) if row[1] else None,
                removed_date=date.fromisoformat(row[2]) if row[2] else None,
                reason=row[3],
            )
        )
    return memberships


def get_index_constituents(
    conn: sqlite3.Connection,
    index_code: str,
    as_of_date: Optional[date] = None,
) -> list[str]:
    """Get current or historical constituents of an index."""
    if as_of_date is None:
        cursor = conn.execute(
            """
            SELECT ticker FROM constituents
            WHERE index_code = ? AND removed_date IS NULL
            ORDER BY ticker
            """,
            (index_code,),
        )
    else:
        cursor = conn.execute(
            """
            SELECT ticker FROM constituents
            WHERE index_code = ?
              AND added_date <= ?
              AND (removed_date IS NULL OR removed_date > ?)
            ORDER BY ticker
            """,
            (index_code, as_of_date.isoformat(), as_of_date.isoformat()),
        )
    return [row[0] for row in cursor.fetchall()]


def save_income(
    conn: sqlite3.Connection,
    ticker: str,
    records: list[IncomeRecord],
    last_updated: str,
) -> None:
    """Save income statement records for a ticker, replacing any existing data."""
    ticker_upper = ticker.upper()

    # Delete existing data for this ticker
    conn.execute("DELETE FROM income_statements WHERE ticker = ?", (ticker_upper,))

    # Insert new records
    for record in records:
        conn.execute(
            """
            INSERT INTO income_statements (ticker, fiscal_year, net_income, last_updated)
            VALUES (?, ?, ?, ?)
            """,
            (ticker_upper, record.fiscal_year, record.net_income, last_updated),
        )
    conn.commit()


def get_cached_income(conn: sqlite3.Connection, ticker: str) -> Optional[CachedIncome]:
    """Get cached income statements for a ticker, or None if not cached."""
    ticker_upper = ticker.upper()

    cursor = conn.execute(
        """
        SELECT fiscal_year, net_income, last_updated
        FROM income_statements
        WHERE ticker = ?
        ORDER BY fiscal_year DESC
        """,
        (ticker_upper,),
    )

    rows = cursor.fetchall()
    if not rows:
        return None

    records = [
        IncomeRecord(ticker=ticker_upper, fiscal_year=row[0], net_income=row[1]) for row in rows
    ]

    return CachedIncome(
        ticker=ticker_upper,
        last_updated=rows[0][2],  # All rows have same last_updated
        annual_income=records,
    )


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


def get_cached_balance_sheet(conn: sqlite3.Connection, ticker: str) -> Optional[CachedBalanceSheet]:
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
