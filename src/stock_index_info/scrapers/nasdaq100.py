"""NASDAQ 100 Wikipedia scraper."""

from datetime import datetime, date
from io import StringIO
from typing import Optional

import pandas as pd
from bs4 import BeautifulSoup, Tag
from curl_cffi import requests

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
        response = requests.get(self.WIKI_URL, impersonate="chrome", timeout=30.0)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        tables = soup.find_all("table", class_="wikitable")

        # First pass: parse changes table to collect all add/remove events
        # Each row is a time-point event, not a stock lifecycle
        added_dates: dict[str, date] = {}  # ticker -> added_date
        removed_dates: dict[str, date] = {}  # ticker -> removed_date

        for table in tables:
            added, removed = self._parse_changes_table(table)
            if added or removed:
                added_dates.update(added)
                removed_dates.update(removed)
                break

        # Second pass: parse current constituents
        records: list[ConstituentRecord] = []
        current_tickers: set[str] = set()

        for table in tables:
            current = self._parse_current_table(table, added_dates)
            if current:
                for r in current:
                    current_tickers.add(r.ticker)
                records.extend(current)
                break

        # Add removed stocks (not in current constituents)
        # Merge their added_date from the changes table
        for ticker, removed_date in removed_dates.items():
            if ticker not in current_tickers:
                records.append(
                    ConstituentRecord(
                        ticker=ticker,
                        index_code=self.index_code,
                        added_date=added_dates.get(ticker),  # None if not found
                        removed_date=removed_date,
                    )
                )

        return records

    def _parse_current_table(
        self, table: Tag, added_dates: dict[str, date]
    ) -> list[ConstituentRecord]:
        """Try to parse as current constituents table."""
        records: list[ConstituentRecord] = []

        try:
            df = pd.read_html(StringIO(str(table)))[0]
            df.columns = [str(c).lower() for c in df.columns]

            if "ticker" not in df.columns:
                return []

            for _, row in df.iterrows():
                ticker = str(row.get("ticker", "")).strip()
                if not ticker or ticker == "nan":
                    continue

                company = str(row.get("company", ""))

                # Use real added date from changes table, None if not found
                added_date = added_dates.get(ticker)

                records.append(
                    ConstituentRecord(
                        ticker=ticker,
                        index_code=self.index_code,
                        added_date=added_date,
                        removed_date=None,
                        company_name=company if company != "nan" else None,
                    )
                )
        except Exception:
            pass

        return records

    def _parse_changes_table(self, table: Tag) -> tuple[dict[str, date], dict[str, date]]:
        """Parse changes table to collect all add/remove events.

        Each row represents a time-point event where stocks are added/removed.
        A stock's full lifecycle spans multiple rows (one for add, one for remove).

        Returns:
            Tuple of (added_dates dict, removed_dates dict)
        """
        added_dates: dict[str, date] = {}
        removed_dates: dict[str, date] = {}

        try:
            df = pd.read_html(StringIO(str(table)))[0]

            # Flatten multi-level columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = ["_".join(map(str, col)).strip() for col in df.columns]

            # Normalize column names
            df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]

            # Check if this looks like a changes table
            cols_str = " ".join(str(c).lower() for c in df.columns)
            if "added" not in cols_str and "removed" not in cols_str:
                return {}, {}

            for _, row in df.iterrows():
                effective_date = self._find_date(row)
                if effective_date is None:
                    continue

                # Handle added stocks - record their add date
                added_ticker = self._find_added_ticker(row)
                if added_ticker:
                    added_dates[added_ticker] = effective_date

                # Handle removed stocks - record their remove date
                removed_ticker = self._find_removed_ticker(row)
                if removed_ticker:
                    removed_dates[removed_ticker] = effective_date

        except Exception:
            pass

        return added_dates, removed_dates

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
                if pd.notna(val) and str(val).strip() and str(val).strip() != "nan":
                    return str(val).strip()
        return None

    def _find_added_ticker(self, row: pd.Series) -> Optional[str]:
        """Find added ticker from row."""
        for col in row.index:
            col_lower = str(col).lower()
            if "added" in col_lower and "ticker" in col_lower:
                val = row[col]
                if pd.notna(val) and str(val).strip() and str(val).strip() != "nan":
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
