"""Tests for database operations."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

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
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
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
