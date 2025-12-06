"""NASDAQ 100 Wikipedia scraper."""

from datetime import datetime, date
from io import StringIO
from typing import Optional

import httpx
import pandas as pd
from bs4 import BeautifulSoup, Tag

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

    def _try_parse_current_table(self, table: Tag) -> list[ConstituentRecord]:
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
        self, table: Tag, current_tickers: set[str]
    ) -> list[ConstituentRecord]:
        """Try to parse as changes table."""
        records: list[ConstituentRecord] = []

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
            if "removed" in col_lower:
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
