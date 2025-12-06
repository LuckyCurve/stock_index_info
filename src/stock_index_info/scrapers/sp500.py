"""S&P 500 Wikipedia scraper."""

from datetime import datetime, date
from io import StringIO
from typing import Optional

import pandas as pd
from bs4 import BeautifulSoup, Tag
from curl_cffi import requests

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
        response = requests.get(self.WIKI_URL, impersonate="chrome", timeout=30.0)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        tables = soup.find_all("table", class_="wikitable")

        # First pass: parse changes table to collect all add/remove events
        # Each row is a time-point event, not a stock lifecycle
        added_dates: dict[str, date] = {}  # ticker -> added_date
        removed_dates: dict[str, date] = {}  # ticker -> removed_date

        if len(tables) >= 2:
            added, removed = self._parse_changes_table(tables[1])
            added_dates.update(added)
            removed_dates.update(removed)

        records: list[ConstituentRecord] = []
        current_tickers: set[str] = set()

        # Parse current constituents (first table)
        if len(tables) >= 1:
            current_records = self._parse_current_table(tables[0], added_dates)
            for r in current_records:
                current_tickers.add(r.ticker)
            records.extend(current_records)

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
        """Parse the current S&P 500 constituents table."""
        records: list[ConstituentRecord] = []

        try:
            df = pd.read_html(StringIO(str(table)))[0]
            # Normalize column names
            df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]

            for _, row in df.iterrows():
                # Try different column names for ticker
                ticker = None
                for col_name in ["symbol", "ticker"]:
                    if col_name in row.index:
                        ticker = str(row[col_name]).strip()
                        if ticker and ticker != "nan":
                            break

                if not ticker or ticker == "nan":
                    continue

                # Try to get date from current table first, then from changes table
                added_date = None

                # Try different column names for date in current table
                for col_name in ["date_added", "date added"]:
                    if col_name in row.index:
                        added_str = str(row[col_name])
                        try:
                            added_date = datetime.strptime(added_str, "%Y-%m-%d").date()
                            break
                        except (ValueError, TypeError):
                            pass

                # Fall back to changes table if not found in current table
                if added_date is None:
                    added_date = added_dates.get(ticker)

                company_name = ""
                for col_name in ["security", "company"]:
                    if col_name in row.index:
                        company_name = str(row[col_name])
                        break

                records.append(
                    ConstituentRecord(
                        ticker=ticker,
                        index_code=self.index_code,
                        added_date=added_date,
                        removed_date=None,
                        company_name=company_name if company_name != "nan" else None,
                    )
                )
        except Exception:
            pass

        return records

    def _parse_changes_table(self, table: Tag) -> tuple[dict[str, date], dict[str, date]]:
        """Parse the S&P 500 historical changes table.

        Each row represents a time-point event where stocks are added/removed.
        A stock's full lifecycle spans multiple rows (one for add, one for remove).

        Returns:
            Tuple of (added_dates dict, removed_dates dict)
        """
        added_dates: dict[str, date] = {}
        removed_dates: dict[str, date] = {}

        try:
            df = pd.read_html(StringIO(str(table)))[0]
            # Flatten multi-level columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = ["_".join(map(str, col)).strip() for col in df.columns]

            # Normalize column names
            df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]

            for _, row in df.iterrows():
                # Parse effective date
                date_str = self._find_date_column(row)
                if not date_str:
                    continue

                effective_date = self._parse_date(date_str)
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

    def _find_date_column(self, row: pd.Series) -> Optional[str]:
        """Find the date value in a row."""
        for col in row.index:
            col_lower = str(col).lower()
            if "date" in col_lower:
                val = row[col]
                if pd.notna(val):
                    return str(val)
        return None

    def _find_added_ticker(self, row: pd.Series) -> Optional[str]:
        """Find the added ticker in a row."""
        for col in row.index:
            col_lower = str(col).lower()
            if "added" in col_lower and ("ticker" in col_lower or "symbol" in col_lower):
                val = row[col]
                if pd.notna(val) and str(val).strip() and str(val).strip() != "nan":
                    return str(val).strip()
        return None

    def _find_removed_ticker(self, row: pd.Series) -> Optional[str]:
        """Find the removed ticker in a row."""
        for col in row.index:
            col_lower = str(col).lower()
            if "removed" in col_lower and ("ticker" in col_lower or "symbol" in col_lower):
                val = row[col]
                if pd.notna(val) and str(val).strip() and str(val).strip() != "nan":
                    return str(val).strip()
        return None

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse various date formats from Wikipedia."""
        date_str = date_str.strip()
        formats = [
            "%B %d, %Y",  # December 22, 2024
            "%b %d, %Y",  # Dec 22, 2024
            "%Y-%m-%d",  # 2024-12-22
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None
