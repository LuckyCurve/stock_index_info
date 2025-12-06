"""Pytest fixtures for stock_index_info tests."""

import sqlite3
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_db(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary database file."""
    db_path = tmp_path / "test.db"
    yield db_path
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def db_connection(temp_db: Path) -> Generator[sqlite3.Connection, None, None]:
    """Create a database connection with the schema initialized."""
    from stock_index_info.db import init_db

    conn = init_db(temp_db)
    yield conn
    conn.close()
