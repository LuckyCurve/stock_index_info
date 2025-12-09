"""Tests for database operations."""

import sqlite3
from datetime import date
from pathlib import Path


from stock_index_info.db import (
    init_db,
    insert_constituent,
    get_stock_memberships,
    get_index_constituents,
)
from stock_index_info.models import ConstituentRecord


class TestInitDb:
    def test_creates_tables(self, temp_db: Path) -> None:
        conn = init_db(temp_db)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        assert "constituents" in tables

    def test_idempotent(self, temp_db: Path) -> None:
        conn1 = init_db(temp_db)
        conn1.close()
        conn2 = init_db(temp_db)  # Should not raise
        conn2.close()


class TestConstituents:
    def test_insert_and_query(self, db_connection: sqlite3.Connection) -> None:
        record = ConstituentRecord(
            ticker="AAPL",
            index_code="sp500",
            added_date=date(1982, 11, 30),
        )
        insert_constituent(db_connection, record)

        memberships = get_stock_memberships(db_connection, "AAPL")
        assert len(memberships) == 1
        assert memberships[0].index_code == "sp500"
        assert memberships[0].added_date == date(1982, 11, 30)

    def test_insert_duplicate_ignored(self, db_connection: sqlite3.Connection) -> None:
        record = ConstituentRecord(
            ticker="AAPL",
            index_code="sp500",
            added_date=date(1982, 11, 30),
        )
        insert_constituent(db_connection, record)
        insert_constituent(db_connection, record)  # Should not raise

        memberships = get_stock_memberships(db_connection, "AAPL")
        assert len(memberships) == 1

    def test_get_index_constituents(self, db_connection: sqlite3.Connection) -> None:
        records = [
            ConstituentRecord("AAPL", "sp500", date(1982, 11, 30)),
            ConstituentRecord("MSFT", "sp500", date(1994, 6, 1)),
            ConstituentRecord("AAPL", "nasdaq100", date(1985, 1, 31)),
        ]
        for r in records:
            insert_constituent(db_connection, r)

        sp500_current = get_index_constituents(db_connection, "sp500")
        assert set(sp500_current) == {"AAPL", "MSFT"}


def test_save_and_get_earnings(db_connection):
    """Test saving and retrieving earnings data."""
    from stock_index_info.db import save_earnings, get_cached_earnings
    from stock_index_info.models import EarningsRecord

    records = [
        EarningsRecord(ticker="AAPL", fiscal_year=2024, eps=6.42),
        EarningsRecord(ticker="AAPL", fiscal_year=2023, eps=6.16),
        EarningsRecord(ticker="AAPL", fiscal_year=2022, eps=6.11),
    ]
    save_earnings(db_connection, "AAPL", records, "2025-01-15")

    cached = get_cached_earnings(db_connection, "AAPL")
    assert cached is not None
    assert cached.ticker == "AAPL"
    assert cached.last_updated == "2025-01-15"
    assert len(cached.annual_eps) == 3
    assert cached.annual_eps[0].fiscal_year == 2024
    assert cached.annual_eps[0].eps == 6.42


def test_get_cached_earnings_not_found(db_connection):
    """Test getting earnings for non-existent ticker returns None."""
    from stock_index_info.db import get_cached_earnings

    cached = get_cached_earnings(db_connection, "NOTFOUND")
    assert cached is None


def test_save_earnings_replaces_old_data(db_connection):
    """Test that saving earnings replaces existing data for ticker."""
    from stock_index_info.db import save_earnings, get_cached_earnings
    from stock_index_info.models import EarningsRecord

    # Save initial data
    old_records = [EarningsRecord(ticker="AAPL", fiscal_year=2023, eps=6.16)]
    save_earnings(db_connection, "AAPL", old_records, "2024-01-01")

    # Save new data
    new_records = [
        EarningsRecord(ticker="AAPL", fiscal_year=2024, eps=6.42),
        EarningsRecord(ticker="AAPL", fiscal_year=2023, eps=6.16),
    ]
    save_earnings(db_connection, "AAPL", new_records, "2025-01-15")

    cached = get_cached_earnings(db_connection, "AAPL")
    assert cached is not None
    assert cached.last_updated == "2025-01-15"
    assert len(cached.annual_eps) == 2
