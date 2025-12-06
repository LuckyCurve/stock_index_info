"""SQLite database operations for stock index data."""

import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

from stock_index_info.models import ConstituentRecord, IndexMembership, INDEX_NAMES

SCHEMA = """
CREATE TABLE IF NOT EXISTS constituents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    index_code TEXT NOT NULL CHECK (index_code IN ('sp500', 'nasdaq100')),
    added_date TEXT NOT NULL,
    removed_date TEXT,
    reason TEXT,
    UNIQUE(ticker, index_code, added_date)
);

CREATE INDEX IF NOT EXISTS idx_constituents_ticker ON constituents(ticker);
CREATE INDEX IF NOT EXISTS idx_constituents_index ON constituents(index_code);
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
            record.added_date.isoformat(),
            record.removed_date.isoformat() if record.removed_date else None,
            record.reason,
        ),
    )
    conn.commit()


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
                added_date=date.fromisoformat(row[1]),
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
