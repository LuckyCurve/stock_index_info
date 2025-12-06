# Stock Index Query Telegram Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Telegram Bot service that responds to authorized users with stock index membership information (S&P 500, NASDAQ 100), including join dates and duration.

**Architecture:** Wikipedia scraping → SQLite storage → Telegram Bot service (long-running). Single table `constituents` for index membership periods. Bot responds only to whitelisted user IDs. Uses `JobQueue` for scheduled daily data sync.

**Tech Stack:** Python 3.13, httpx, BeautifulSoup4, pandas, sqlite3, python-telegram-bot (with JobQueue), pytest

---

## Design Optimizations from Original Doc

| Original Design | Optimized | Rationale |
|-----------------|-----------|-----------|
| Flat project structure | src layout | Per project requirements |
| 4 tables (indices, stocks, constituents, sync_logs) | 1 table (constituents) | YAGNI - indices are string literals, stocks/yfinance removed |
| SQLAlchemy ORM | sqlite3 directly | Simple queries don't need ORM overhead |
| CLI interface (typer) | Telegram Bot | User requirement - build bot service not CLI |
| requests | httpx | Modern async-capable, better API |
| yfinance enricher | Removed | Not needed for MVP |
| Optional REST API | Removed | YAGNI - Bot is sufficient for stated requirements |
| schedule/APScheduler | python-telegram-bot JobQueue | Built-in scheduler, no extra dependency |

---

## Project Structure (src layout)

```
stock_index_info/
├── pyproject.toml
├── README.md
├── docs/
│   ├── stock-index-query-design.md
│   └── plans/
│       └── 2025-12-06-stock-index-query.md
├── src/
│   └── stock_index_info/
│       ├── __init__.py
│       ├── bot.py              # Telegram Bot handlers
│       ├── config.py           # Configuration (token, allowed users)
│       ├── db.py               # SQLite operations
│       ├── models.py           # Dataclasses
│       └── scrapers/
│           ├── __init__.py
│           ├── base.py         # Abstract scraper
│           ├── sp500.py        # S&P 500 Wikipedia scraper
│           └── nasdaq100.py    # NASDAQ 100 Wikipedia scraper
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_db.py
│   ├── test_models.py
│   └── test_scrapers/
│       ├── __init__.py
│       ├── test_sp500.py
│       └── test_nasdaq100.py
└── data/
    └── .gitkeep                # SQLite db goes here
```

---

## Simplified Schema

```sql
-- Index membership periods
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
```

---

## Task 1: Project Setup & Dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: `src/stock_index_info/__init__.py`
- Create: `src/stock_index_info/config.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `data/.gitkeep`

**Step 1: Update pyproject.toml with dependencies and src layout**

```toml
[project]
name = "stock-index-info"
version = "0.1.0"
description = "Telegram Bot to query which US stock indices a ticker belongs to"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "httpx>=0.28.0",
    "beautifulsoup4>=4.12.0",
    "pandas>=2.2.0",
    "python-telegram-bot>=21.0",
]

[project.scripts]
stock-index-bot = "stock_index_info.bot:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/stock_index_info"]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=6.0.0",
    "pytest-asyncio>=0.24.0",
    "mypy>=1.19.0",
    "ruff>=0.14.8",
]

[tool.ruff]
line-length = 100
src = ["src"]

[tool.mypy]
python_version = "3.13"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

**Step 2: Create src/stock_index_info/__init__.py**

```python
"""Stock Index Info - Telegram Bot to query US stock index membership."""

__version__ = "0.1.0"
```

**Step 3: Create src/stock_index_info/config.py**

```python
"""Configuration for the Stock Index Info Telegram Bot."""

import os
from pathlib import Path


# Telegram Bot Token - must be set via environment variable
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Allowed Telegram user IDs - comma-separated list in env var
# Example: ALLOWED_USER_IDS=123456789,987654321
_allowed_ids_str = os.environ.get("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: set[int] = {
    int(uid.strip()) for uid in _allowed_ids_str.split(",") if uid.strip()
}

# Database path
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DATA_DIR / "indices.db"

# Scheduled sync settings
# Hour of day to run sync (0-23), default 2 AM
SYNC_HOUR: int = int(os.environ.get("SYNC_HOUR", "2"))
SYNC_MINUTE: int = int(os.environ.get("SYNC_MINUTE", "0"))


def validate_config() -> list[str]:
    """Validate configuration and return list of errors."""
    errors: list[str] = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN environment variable is not set")
    if not ALLOWED_USER_IDS:
        errors.append("ALLOWED_USER_IDS environment variable is not set or empty")
    return errors
```

**Step 4: Create tests/__init__.py**

```python
"""Tests for stock_index_info."""
```

**Step 5: Create tests/conftest.py**

```python
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
```

**Step 6: Create data/.gitkeep**

Empty file to ensure data directory is tracked.

**Step 7: Install dependencies**

Run: `uv sync`
Expected: Dependencies installed successfully

**Step 8: Commit**

```bash
git add pyproject.toml src/ tests/ data/
git commit -m "feat: project setup with src layout and Telegram bot dependencies"
```

---

## Task 2: Data Models

**Files:**
- Create: `src/stock_index_info/models.py`
- Create: `tests/test_models.py`

**Step 1: Write the failing test**

```python
"""Tests for data models."""

from datetime import date

import pytest

from stock_index_info.models import ConstituentRecord, IndexMembership


class TestConstituentRecord:
    def test_create_current_member(self) -> None:
        record = ConstituentRecord(
            ticker="AAPL",
            index_code="sp500",
            added_date=date(1982, 11, 30),
        )
        assert record.ticker == "AAPL"
        assert record.index_code == "sp500"
        assert record.added_date == date(1982, 11, 30)
        assert record.removed_date is None
        assert record.reason is None

    def test_create_former_member(self) -> None:
        record = ConstituentRecord(
            ticker="INTC",
            index_code="nasdaq100",
            added_date=date(1985, 1, 31),
            removed_date=date(2024, 11, 18),
            reason="Annual reconstitution",
        )
        assert record.removed_date == date(2024, 11, 18)
        assert record.reason == "Annual reconstitution"


class TestIndexMembership:
    def test_years_in_index_current(self) -> None:
        membership = IndexMembership(
            index_code="sp500",
            index_name="S&P 500",
            added_date=date(2020, 1, 1),
            removed_date=None,
        )
        # Should calculate years from added_date to today
        assert membership.years_in_index > 4.0
        assert membership.is_current is True

    def test_years_in_index_former(self) -> None:
        membership = IndexMembership(
            index_code="nasdaq100",
            index_name="NASDAQ 100",
            added_date=date(2010, 1, 1),
            removed_date=date(2020, 1, 1),
        )
        assert membership.years_in_index == pytest.approx(10.0, abs=0.1)
        assert membership.is_current is False
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'stock_index_info.models'"

**Step 3: Write minimal implementation**

```python
"""Data models for stock index information."""

from dataclasses import dataclass
from datetime import date
from typing import Optional


INDEX_NAMES: dict[str, str] = {
    "sp500": "S&P 500",
    "nasdaq100": "NASDAQ 100",
}


@dataclass
class ConstituentRecord:
    """A record of stock membership in an index."""

    ticker: str
    index_code: str
    added_date: date
    removed_date: Optional[date] = None
    company_name: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class IndexMembership:
    """Represents a stock's membership in an index with computed properties."""

    index_code: str
    index_name: str
    added_date: date
    removed_date: Optional[date] = None
    reason: Optional[str] = None

    @property
    def is_current(self) -> bool:
        """Whether the stock is currently in this index."""
        return self.removed_date is None

    @property
    def years_in_index(self) -> float:
        """Calculate years the stock has been/was in the index."""
        end_date = self.removed_date or date.today()
        delta = end_date - self.added_date
        return delta.days / 365.25
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/stock_index_info/models.py tests/test_models.py
git commit -m "feat: add data models for constituents and memberships"
```

---

## Task 3: Database Layer

**Files:**
- Create: `src/stock_index_info/db.py`
- Create: `tests/test_db.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL with "cannot import name 'init_db' from 'stock_index_info.db'"

**Step 3: Write minimal implementation**

```python
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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_db.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/stock_index_info/db.py tests/test_db.py
git commit -m "feat: add SQLite database layer for constituents"
```

---

## Task 4: Base Scraper Interface

**Files:**
- Create: `src/stock_index_info/scrapers/__init__.py`
- Create: `src/stock_index_info/scrapers/base.py`
- Create: `tests/test_scrapers/__init__.py`

**Step 1: Create scraper module init**

```python
"""Wikipedia scrapers for stock index data."""

from stock_index_info.scrapers.base import BaseScraper

__all__ = ["BaseScraper"]
```

**Step 2: Create base scraper**

```python
"""Abstract base class for index scrapers."""

from abc import ABC, abstractmethod

from stock_index_info.models import ConstituentRecord


class BaseScraper(ABC):
    """Base class for index data scrapers."""

    @property
    @abstractmethod
    def index_code(self) -> str:
        """Return the index code (e.g., 'sp500', 'nasdaq100')."""
        ...

    @property
    @abstractmethod
    def index_name(self) -> str:
        """Return the human-readable index name."""
        ...

    @abstractmethod
    def fetch(self) -> list[ConstituentRecord]:
        """Fetch and parse constituent data from source."""
        ...
```

**Step 3: Create test module init**

```python
"""Tests for scrapers."""
```

**Step 4: Commit**

```bash
git add src/stock_index_info/scrapers/ tests/test_scrapers/
git commit -m "feat: add base scraper interface"
```

---

## Task 5: S&P 500 Scraper

**Files:**
- Create: `src/stock_index_info/scrapers/sp500.py`
- Create: `tests/test_scrapers/test_sp500.py`

**Step 1: Write the failing test**

```python
"""Tests for S&P 500 Wikipedia scraper."""

from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from stock_index_info.scrapers.sp500 import SP500Scraper


# Sample HTML fixture for testing (subset of actual Wikipedia table)
SAMPLE_CURRENT_TABLE_HTML = """
<table class="wikitable sortable">
<tr><th>Symbol</th><th>Security</th><th>GICS Sector</th><th>Date added</th></tr>
<tr><td>AAPL</td><td>Apple Inc.</td><td>Information Technology</td><td>1982-11-30</td></tr>
<tr><td>MSFT</td><td>Microsoft Corp</td><td>Information Technology</td><td>1994-06-01</td></tr>
</table>
"""

SAMPLE_CHANGES_TABLE_HTML = """
<table class="wikitable">
<tr><th>Date</th><th colspan="2">Added</th><th colspan="2">Removed</th><th>Reason</th></tr>
<tr><th></th><th>Ticker</th><th>Security</th><th>Ticker</th><th>Security</th><th></th></tr>
<tr><td>December 22, 2024</td><td>HOOD</td><td>Robinhood</td><td>PARA</td><td>Paramount</td><td>Market cap</td></tr>
</table>
"""


class TestSP500Scraper:
    def test_index_code(self) -> None:
        scraper = SP500Scraper()
        assert scraper.index_code == "sp500"
        assert scraper.index_name == "S&P 500"

    @patch("stock_index_info.scrapers.sp500.httpx.get")
    def test_fetch_current_constituents(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = f"<html><body>{SAMPLE_CURRENT_TABLE_HTML}{SAMPLE_CHANGES_TABLE_HTML}</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        scraper = SP500Scraper()
        records = scraper.fetch()

        # Should find AAPL and MSFT from current table
        tickers = {r.ticker for r in records}
        assert "AAPL" in tickers
        assert "MSFT" in tickers

        # Check AAPL details
        aapl = next(r for r in records if r.ticker == "AAPL" and r.removed_date is None)
        assert aapl.added_date == date(1982, 11, 30)
        assert aapl.index_code == "sp500"

    @patch("stock_index_info.scrapers.sp500.httpx.get")
    def test_fetch_parses_changes(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = f"<html><body>{SAMPLE_CURRENT_TABLE_HTML}{SAMPLE_CHANGES_TABLE_HTML}</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        scraper = SP500Scraper()
        records = scraper.fetch()

        # PARA should be marked as removed
        para_records = [r for r in records if r.ticker == "PARA"]
        assert len(para_records) >= 1
        removed_para = next((r for r in para_records if r.removed_date is not None), None)
        assert removed_para is not None
        assert removed_para.removed_date == date(2024, 12, 22)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scrapers/test_sp500.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
"""S&P 500 Wikipedia scraper."""

from datetime import datetime, date
from typing import Optional

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from stock_index_info.models import ConstituentRecord
from stock_index_info.scrapers.base import BaseScraper


class SP500Scraper(BaseScraper):
    """Scrapes S&P 500 constituent data from Wikipedia."""

    WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    @property
    def index_code(self) -> str:
        return "sp500"

    @property
    def index_name(self) -> str:
        return "S&P 500"

    def fetch(self) -> list[ConstituentRecord]:
        """Fetch current constituents and historical changes."""
        response = httpx.get(self.WIKI_URL, timeout=30.0)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        tables = soup.find_all("table", class_="wikitable")

        records: list[ConstituentRecord] = []

        # Parse current constituents (first table)
        if len(tables) >= 1:
            records.extend(self._parse_current_table(tables[0]))

        # Parse historical changes (second table)
        if len(tables) >= 2:
            records.extend(self._parse_changes_table(tables[1]))

        return records

    def _parse_current_table(self, table: BeautifulSoup) -> list[ConstituentRecord]:
        """Parse the current S&P 500 constituents table."""
        records: list[ConstituentRecord] = []

        try:
            df = pd.read_html(str(table))[0]
            # Normalize column names
            df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]

            for _, row in df.iterrows():
                ticker = str(row.get("symbol", "")).strip()
                if not ticker:
                    continue

                added_str = str(row.get("date_added", ""))
                try:
                    added_date = datetime.strptime(added_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    added_date = date(1957, 3, 4)  # S&P 500 inception

                records.append(
                    ConstituentRecord(
                        ticker=ticker,
                        index_code=self.index_code,
                        added_date=added_date,
                        removed_date=None,
                        company_name=str(row.get("security", "")),
                    )
                )
        except Exception:
            pass

        return records

    def _parse_changes_table(self, table: BeautifulSoup) -> list[ConstituentRecord]:
        """Parse the S&P 500 historical changes table."""
        records: list[ConstituentRecord] = []

        try:
            df = pd.read_html(str(table))[0]
            # Flatten multi-level columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = ["_".join(map(str, col)).strip() for col in df.columns]

            for _, row in df.iterrows():
                # Parse effective date
                date_str = self._find_date_column(row)
                if not date_str:
                    continue

                effective_date = self._parse_date(date_str)
                if effective_date is None:
                    continue

                # Parse removed stock
                removed_ticker = self._find_removed_ticker(row)
                if removed_ticker:
                    records.append(
                        ConstituentRecord(
                            ticker=removed_ticker,
                            index_code=self.index_code,
                            added_date=date(1957, 3, 4),  # Will be updated if found in current
                            removed_date=effective_date,
                        )
                    )
        except Exception:
            pass

        return records

    def _find_date_column(self, row: pd.Series) -> Optional[str]:
        """Find the date value in a row."""
        for col in row.index:
            col_lower = str(col).lower()
            if "date" in col_lower:
                val = row[col]
                if pd.notna(val):
                    return str(val)
        return None

    def _find_removed_ticker(self, row: pd.Series) -> Optional[str]:
        """Find the removed ticker in a row."""
        for col in row.index:
            col_lower = str(col).lower()
            if "removed" in col_lower and "ticker" in col_lower:
                val = row[col]
                if pd.notna(val) and str(val).strip():
                    return str(val).strip()
        return None

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse various date formats from Wikipedia."""
        date_str = date_str.strip()
        formats = [
            "%B %d, %Y",  # December 22, 2024
            "%b %d, %Y",  # Dec 22, 2024
            "%Y-%m-%d",   # 2024-12-22
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_scrapers/test_sp500.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/stock_index_info/scrapers/sp500.py tests/test_scrapers/test_sp500.py
git commit -m "feat: add S&P 500 Wikipedia scraper"
```

---

## Task 6: NASDAQ 100 Scraper

**Files:**
- Create: `src/stock_index_info/scrapers/nasdaq100.py`
- Create: `tests/test_scrapers/test_nasdaq100.py`

**Step 1: Write the failing test**

```python
"""Tests for NASDAQ 100 Wikipedia scraper."""

from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from stock_index_info.scrapers.nasdaq100 import NASDAQ100Scraper


SAMPLE_CURRENT_TABLE_HTML = """
<table class="wikitable sortable">
<tr><th>Ticker</th><th>Company</th><th>ICB Industry</th></tr>
<tr><td>AAPL</td><td>Apple Inc.</td><td>Technology</td></tr>
<tr><td>GOOGL</td><td>Alphabet Inc.</td><td>Technology</td></tr>
</table>
"""

SAMPLE_CHANGES_TABLE_HTML = """
<table class="wikitable">
<tr><th>Date</th><th colspan="2">Added</th><th colspan="2">Removed</th><th>Reason</th></tr>
<tr><th></th><th>Ticker</th><th>Security</th><th>Ticker</th><th>Security</th><th></th></tr>
<tr><td>December 23, 2024</td><td>PLTR</td><td>Palantir</td><td>SMCI</td><td>Super Micro</td><td>Annual reconstitution</td></tr>
</table>
"""


class TestNASDAQ100Scraper:
    def test_index_code(self) -> None:
        scraper = NASDAQ100Scraper()
        assert scraper.index_code == "nasdaq100"
        assert scraper.index_name == "NASDAQ 100"

    @patch("stock_index_info.scrapers.nasdaq100.httpx.get")
    def test_fetch_finds_current_constituents(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = f"<html><body>{SAMPLE_CURRENT_TABLE_HTML}{SAMPLE_CHANGES_TABLE_HTML}</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        scraper = NASDAQ100Scraper()
        records = scraper.fetch()

        tickers = {r.ticker for r in records}
        assert "AAPL" in tickers
        assert "GOOGL" in tickers

    @patch("stock_index_info.scrapers.nasdaq100.httpx.get")
    def test_fetch_parses_changes(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = f"<html><body>{SAMPLE_CURRENT_TABLE_HTML}{SAMPLE_CHANGES_TABLE_HTML}</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        scraper = NASDAQ100Scraper()
        records = scraper.fetch()

        # SMCI should be marked as removed
        smci_records = [r for r in records if r.ticker == "SMCI"]
        assert len(smci_records) >= 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scrapers/test_nasdaq100.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
"""NASDAQ 100 Wikipedia scraper."""

from datetime import datetime, date
from typing import Optional

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from stock_index_info.models import ConstituentRecord
from stock_index_info.scrapers.base import BaseScraper


class NASDAQ100Scraper(BaseScraper):
    """Scrapes NASDAQ 100 constituent data from Wikipedia."""

    WIKI_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"

    @property
    def index_code(self) -> str:
        return "nasdaq100"

    @property
    def index_name(self) -> str:
        return "NASDAQ 100"

    def fetch(self) -> list[ConstituentRecord]:
        """Fetch current constituents and historical changes."""
        response = httpx.get(self.WIKI_URL, timeout=30.0)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        tables = soup.find_all("table", class_="wikitable")

        records: list[ConstituentRecord] = []
        current_tickers: set[str] = set()

        # Parse current constituents table
        for table in tables:
            current = self._try_parse_current_table(table)
            if current:
                for r in current:
                    current_tickers.add(r.ticker)
                records.extend(current)
                break

        # Parse changes table
        for table in tables:
            changes = self._try_parse_changes_table(table, current_tickers)
            if changes:
                records.extend(changes)
                break

        return records

    def _try_parse_current_table(self, table: BeautifulSoup) -> list[ConstituentRecord]:
        """Try to parse as current constituents table."""
        records: list[ConstituentRecord] = []

        try:
            df = pd.read_html(str(table))[0]
            df.columns = [str(c).lower() for c in df.columns]

            if "ticker" not in df.columns:
                return []

            for _, row in df.iterrows():
                ticker = str(row.get("ticker", "")).strip()
                if not ticker or ticker == "nan":
                    continue

                company = str(row.get("company", ""))

                records.append(
                    ConstituentRecord(
                        ticker=ticker,
                        index_code=self.index_code,
                        added_date=date(1985, 1, 31),  # NASDAQ 100 inception
                        removed_date=None,
                        company_name=company if company != "nan" else None,
                    )
                )
        except Exception:
            pass

        return records

    def _try_parse_changes_table(
        self, table: BeautifulSoup, current_tickers: set[str]
    ) -> list[ConstituentRecord]:
        """Try to parse as changes table."""
        records: list[ConstituentRecord] = []

        try:
            df = pd.read_html(str(table))[0]

            # Flatten multi-level columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = ["_".join(map(str, col)).strip() for col in df.columns]

            # Check if this looks like a changes table
            cols_str = " ".join(str(c).lower() for c in df.columns)
            if "added" not in cols_str and "removed" not in cols_str:
                return []

            for _, row in df.iterrows():
                effective_date = self._find_date(row)
                if effective_date is None:
                    continue

                # Handle removed stocks
                removed_ticker = self._find_removed_ticker(row)
                if removed_ticker and removed_ticker not in current_tickers:
                    records.append(
                        ConstituentRecord(
                            ticker=removed_ticker,
                            index_code=self.index_code,
                            added_date=date(1985, 1, 31),
                            removed_date=effective_date,
                        )
                    )

                # Handle added stocks (update their add date)
                added_ticker = self._find_added_ticker(row)
                if added_ticker:
                    records.append(
                        ConstituentRecord(
                            ticker=added_ticker,
                            index_code=self.index_code,
                            added_date=effective_date,
                            removed_date=None,
                        )
                    )

        except Exception:
            pass

        return records

    def _find_date(self, row: pd.Series) -> Optional[date]:
        """Find and parse date from row."""
        for col in row.index:
            col_lower = str(col).lower()
            if "date" in col_lower:
                val = row[col]
                if pd.notna(val):
                    return self._parse_date(str(val))
        return None

    def _find_removed_ticker(self, row: pd.Series) -> Optional[str]:
        """Find removed ticker from row."""
        for col in row.index:
            col_lower = str(col).lower()
            if "removed" in col_lower and "ticker" in col_lower:
                val = row[col]
                if pd.notna(val) and str(val).strip():
                    return str(val).strip()
        return None

    def _find_added_ticker(self, row: pd.Series) -> Optional[str]:
        """Find added ticker from row."""
        for col in row.index:
            col_lower = str(col).lower()
            if "added" in col_lower and "ticker" in col_lower:
                val = row[col]
                if pd.notna(val) and str(val).strip():
                    return str(val).strip()
        return None

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string."""
        date_str = date_str.strip()
        formats = ["%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_scrapers/test_nasdaq100.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/stock_index_info/scrapers/nasdaq100.py tests/test_scrapers/test_nasdaq100.py
git commit -m "feat: add NASDAQ 100 Wikipedia scraper"
```

---

## Task 7: Telegram Bot Implementation with Scheduled Sync

**Files:**
- Create: `src/stock_index_info/bot.py`

**Step 1: Write the Telegram Bot implementation with JobQueue for scheduled sync**

```python
"""Telegram Bot for stock index queries with scheduled sync."""

import datetime
import logging
from functools import wraps
from typing import Callable, Coroutine, Any

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from stock_index_info.config import (
    TELEGRAM_BOT_TOKEN,
    ALLOWED_USER_IDS,
    DB_PATH,
    SYNC_HOUR,
    SYNC_MINUTE,
    validate_config,
)
from stock_index_info.db import (
    init_db,
    insert_constituent,
    get_stock_memberships,
    get_index_constituents,
)
from stock_index_info.scrapers.sp500 import SP500Scraper
from stock_index_info.scrapers.nasdaq100 import NASDAQ100Scraper

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def restricted(
    func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]
) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
    """Decorator to restrict bot access to allowed users only."""

    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if user is None or user.id not in ALLOWED_USER_IDS:
            logger.warning(f"Unauthorized access attempt by user {user}")
            if update.message:
                await update.message.reply_text(
                    "Sorry, you are not authorized to use this bot."
                )
            return
        return await func(update, context)

    return wrapped


async def _do_sync() -> list[str]:
    """Execute sync logic and return results."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = init_db(DB_PATH)

    scrapers = [SP500Scraper(), NASDAQ100Scraper()]
    results: list[str] = []

    for scraper in scrapers:
        try:
            records = scraper.fetch()
            for record in records:
                insert_constituent(conn, record)
            results.append(f"{scraper.index_name}: {len(records)} records")
        except Exception as e:
            results.append(f"{scraper.index_name}: Error - {e}")
            logger.error(f"Error syncing {scraper.index_name}: {e}")

    conn.close()
    return results


async def scheduled_sync(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Scheduled job to sync data from Wikipedia daily.
    
    This runs automatically at the configured time (default 2:00 AM).
    """
    logger.info("Starting scheduled sync...")
    
    try:
        results = await _do_sync()
        logger.info(f"Scheduled sync complete: {results}")
    except Exception as e:
        logger.error(f"Scheduled sync failed: {e}")


@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if update.message:
        await update.message.reply_text(
            "Welcome to Stock Index Info Bot!\n\n"
            "Commands:\n"
            "/query <TICKER> - Query which indices a stock belongs to\n"
            "/constituents <INDEX> - List constituents (sp500 or nasdaq100)\n"
            "/sync - Sync data from Wikipedia manually\n"
            "/status - Show bot status and next sync time\n"
            "/help - Show this help message\n\n"
            "You can also just send a ticker symbol directly!\n\n"
            f"Auto-sync runs daily at {SYNC_HOUR:02d}:{SYNC_MINUTE:02d}"
        )


@restricted
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if update.message:
        await update.message.reply_text(
            "Stock Index Info Bot\n\n"
            "Query which US stock indices (S&P 500, NASDAQ 100) a stock belongs to.\n\n"
            "Commands:\n"
            "/query <TICKER> - Query stock index membership\n"
            "  Example: /query AAPL\n\n"
            "/constituents <INDEX> - List current constituents\n"
            "  Example: /constituents sp500\n\n"
            "/sync - Sync data from Wikipedia manually\n\n"
            "/status - Show bot status\n\n"
            "Or just send a ticker symbol like: AAPL\n\n"
            f"Data is automatically synced daily at {SYNC_HOUR:02d}:{SYNC_MINUTE:02d}"
        )


@restricted
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - show bot status and next sync time."""
    if not update.message:
        return

    # Get next scheduled sync time
    jobs = context.job_queue.get_jobs_by_name("daily_sync") if context.job_queue else []
    next_sync = "Not scheduled"
    if jobs:
        next_run = jobs[0].next_t
        if next_run:
            next_sync = next_run.strftime("%Y-%m-%d %H:%M:%S %Z")

    # Check database status
    db_status = "Not initialized"
    if DB_PATH.exists():
        try:
            conn = init_db(DB_PATH)
            cursor = conn.execute("SELECT COUNT(*) FROM constituents")
            count = cursor.fetchone()[0]
            conn.close()
            db_status = f"{count} records"
        except Exception as e:
            db_status = f"Error: {e}"

    await update.message.reply_text(
        "*Bot Status*\n\n"
        f"Database: {db_status}\n"
        f"Next sync: {next_sync}\n"
        f"Sync schedule: Daily at {SYNC_HOUR:02d}:{SYNC_MINUTE:02d}",
        parse_mode="Markdown",
    )


@restricted
async def query_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /query command."""
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text("Usage: /query <TICKER>\nExample: /query AAPL")
        return

    ticker = context.args[0].upper()
    await _query_ticker(update, ticker)


@restricted
async def ticker_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle direct ticker messages."""
    if not update.message or not update.message.text:
        return

    ticker = update.message.text.strip().upper()
    # Basic validation: 1-5 uppercase letters
    if not ticker.isalpha() or len(ticker) > 5:
        return

    await _query_ticker(update, ticker)


async def _query_ticker(update: Update, ticker: str) -> None:
    """Query and respond with ticker information."""
    if not update.message:
        return

    # Ensure data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        await update.message.reply_text(
            "Database not initialized. Please run /sync first or wait for auto-sync."
        )
        return

    conn = init_db(DB_PATH)
    try:
        memberships = get_stock_memberships(conn, ticker)

        if not memberships:
            await update.message.reply_text(
                f"{ticker} not found in any tracked index."
            )
            return

        # Build response
        lines: list[str] = [f"*{ticker}*", "", "Index Membership:", "```"]
        lines.append(f"{'Index':<12} {'Added':<12} {'Removed':<12} {'Years':>6}")
        lines.append("-" * 44)

        for m in memberships:
            removed_str = m.removed_date.isoformat() if m.removed_date else "-"
            lines.append(
                f"{m.index_name:<12} {m.added_date.isoformat():<12} {removed_str:<12} {m.years_in_index:>6.1f}"
            )

        lines.append("```")

        await update.message.reply_text(
            "\n".join(lines), parse_mode="Markdown"
        )
    finally:
        conn.close()


@restricted
async def constituents_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /constituents command."""
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /constituents <INDEX>\n"
            "Example: /constituents sp500\n"
            "Available indices: sp500, nasdaq100"
        )
        return

    index_code = context.args[0].lower()
    if index_code not in ("sp500", "nasdaq100"):
        await update.message.reply_text(
            "Invalid index. Available indices: sp500, nasdaq100"
        )
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        await update.message.reply_text(
            "Database not initialized. Please run /sync first or wait for auto-sync."
        )
        return

    conn = init_db(DB_PATH)
    try:
        tickers = get_index_constituents(conn, index_code)

        if not tickers:
            await update.message.reply_text(f"No constituents found for {index_code}")
            return

        index_name = "S&P 500" if index_code == "sp500" else "NASDAQ 100"
        await update.message.reply_text(
            f"*{index_name}* constituents ({len(tickers)}):\n\n"
            f"{', '.join(tickers)}",
            parse_mode="Markdown",
        )
    finally:
        conn.close()


@restricted
async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sync command - manual sync."""
    if not update.message:
        return

    await update.message.reply_text("Starting data sync from Wikipedia...")

    results = await _do_sync()

    await update.message.reply_text(
        "Sync complete!\n\n" + "\n".join(results)
    )


def main() -> None:
    """Start the Telegram bot with scheduled sync."""
    errors = validate_config()
    if errors:
        for error in errors:
            logger.error(error)
        raise SystemExit(1)

    logger.info(f"Starting bot with {len(ALLOWED_USER_IDS)} allowed users")
    logger.info(f"Scheduled sync at {SYNC_HOUR:02d}:{SYNC_MINUTE:02d} daily")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("query", query_command))
    application.add_handler(CommandHandler("constituents", constituents_command))
    application.add_handler(CommandHandler("sync", sync_command))

    # Handle direct ticker messages (text messages that look like tickers)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, ticker_message)
    )

    # Schedule daily sync using JobQueue
    job_queue = application.job_queue
    if job_queue:
        sync_time = datetime.time(hour=SYNC_HOUR, minute=SYNC_MINUTE)
        job_queue.run_daily(
            scheduled_sync,
            time=sync_time,
            name="daily_sync",
        )
        logger.info(f"Scheduled daily sync job at {sync_time}")

    # Start the bot (runs forever)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
```

**Step 2: Test the bot manually**

Run: `TELEGRAM_BOT_TOKEN=your_token ALLOWED_USER_IDS=your_user_id uv run stock-index-bot`
Expected: Bot starts, logs scheduled sync time, and responds to commands

**Step 3: Commit**

```bash
git add src/stock_index_info/bot.py
git commit -m "feat: add Telegram bot with scheduled daily sync via JobQueue"
```

---

## Task 8: Integration Test & Verification

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

```python
"""Integration tests for the full workflow."""

from datetime import date
from pathlib import Path

import pytest

from stock_index_info.db import init_db, insert_constituent, get_stock_memberships
from stock_index_info.models import ConstituentRecord


class TestFullWorkflow:
    def test_insert_and_query_multiple_indices(self, temp_db: Path) -> None:
        """Test inserting and querying a stock in multiple indices."""
        conn = init_db(temp_db)

        # Insert AAPL in both indices
        records = [
            ConstituentRecord(
                ticker="AAPL",
                index_code="sp500",
                added_date=date(1982, 11, 30),
                company_name="Apple Inc.",
            ),
            ConstituentRecord(
                ticker="AAPL",
                index_code="nasdaq100",
                added_date=date(1985, 1, 31),
            ),
        ]

        for r in records:
            insert_constituent(conn, r)

        # Query
        memberships = get_stock_memberships(conn, "AAPL")

        assert len(memberships) == 2
        index_codes = {m.index_code for m in memberships}
        assert index_codes == {"sp500", "nasdaq100"}

        # Verify years calculation
        sp500_membership = next(m for m in memberships if m.index_code == "sp500")
        assert sp500_membership.years_in_index > 40

        conn.close()
```

**Step 2: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test for full workflow"
```

---

## Task 9: Final Cleanup & Documentation

**Files:**
- Modify: `README.md`
- Remove: `main.py` (no longer needed)

**Step 1: Update README**

```markdown
# Stock Index Info Telegram Bot

A Telegram Bot to query which US stock indices (S&P 500, NASDAQ 100) a stock belongs to.

## Setup

### 1. Create a Telegram Bot

1. Talk to [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token

### 2. Get Your Telegram User ID

1. Talk to [@userinfobot](https://t.me/userinfobot) on Telegram
2. Copy your user ID

### 3. Install Dependencies

```bash
uv sync
```

### 4. Run the Bot

```bash
TELEGRAM_BOT_TOKEN=your_bot_token ALLOWED_USER_IDS=your_user_id uv run stock-index-bot
```

For multiple allowed users, separate IDs with commas:
```bash
ALLOWED_USER_IDS=123456789,987654321
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and command list |
| `/help` | Show help message |
| `/query <TICKER>` | Query which indices a stock belongs to |
| `/constituents <INDEX>` | List current constituents (sp500 or nasdaq100) |
| `/sync` | Sync data from Wikipedia manually |
| `/status` | Show bot status and next sync time |

## Auto-Sync

The bot automatically syncs data from Wikipedia daily at 2:00 AM (configurable via `SYNC_HOUR` and `SYNC_MINUTE` env vars).

You can also send a ticker symbol directly (e.g., `AAPL`) without any command.

## Example Output

```
AAPL

Index Membership:
Index        Added        Removed      Years
--------------------------------------------
S&P 500      1982-11-30   -            43.0
NASDAQ 100   1985-01-31   -            40.0
```

## Development

```bash
# Run tests
uv run pytest -v

# Type check
uv run mypy src/

# Lint
uv run ruff check src/ tests/
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from BotFather |
| `ALLOWED_USER_IDS` | Yes | Comma-separated Telegram user IDs |
| `SYNC_HOUR` | No | Hour for daily sync (0-23, default: 2) |
| `SYNC_MINUTE` | No | Minute for daily sync (0-59, default: 0) |

## Running in Background

### Using nohup
```bash
nohup uv run stock-index-bot > bot.log 2>&1 &
```

### Using screen
```bash
screen -S stock-bot
uv run stock-index-bot
# Press Ctrl+A, then D to detach
```

### Using systemd (recommended for production)

Create `/etc/systemd/system/stock-index-bot.service`:
```ini
[Unit]
Description=Stock Index Info Telegram Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/stock_index_info
Environment=TELEGRAM_BOT_TOKEN=your_token
Environment=ALLOWED_USER_IDS=your_user_id
ExecStart=/path/to/.local/bin/uv run stock-index-bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable stock-index-bot
sudo systemctl start stock-index-bot
```
```

**Step 2: Remove main.py**

```bash
git rm main.py
```

**Step 3: Final commit**

```bash
git add README.md
git commit -m "docs: update README with Telegram bot setup instructions"
```

---

## Summary

| Task | Description | Est. Time |
|------|-------------|-----------|
| 1 | Project setup & dependencies | 15 min |
| 2 | Data models | 15 min |
| 3 | Database layer | 25 min |
| 4 | Base scraper interface | 10 min |
| 5 | S&P 500 scraper | 40 min |
| 6 | NASDAQ 100 scraper | 30 min |
| 7 | Telegram Bot with scheduled sync | 50 min |
| 8 | Integration test | 15 min |
| 9 | Cleanup & docs | 10 min |

**Total: ~3.5 hours**
