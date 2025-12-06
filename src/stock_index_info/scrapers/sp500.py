"""S&P 500 Wikipedia scraper."""

from datetime import datetime, date
from io import StringIO
from typing import Optional

import httpx
import pandas as pd
from bs4 import BeautifulSoup, Tag

from stock_index_info.models import ConstituentRecord
from stock_index_info.scrapers.base import BaseScraper


class SP500Scraper(BaseScraper):
    """Scrapes S&P 500 constituent data from Wikipedia."""

    WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    @property
    def index_code(self) -> str:
        return "sp500"

    @property
    def index_name(self) -> str:
        return "S&P 500"

    def fetch(self) -> list[ConstituentRecord]:
        """Fetch current constituents and historical changes."""
        response = httpx.get(self.WIKI_URL, headers=self.HEADERS, timeout=30.0)
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

    def _parse_current_table(self, table: Tag) -> list[ConstituentRecord]:
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

                # Try different column names for date
                added_str = ""
                for col_name in ["date_added", "date added"]:
                    if col_name in row.index:
                        added_str = str(row[col_name])
                        break
                
                try:
                    added_date = datetime.strptime(added_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    added_date = date(1957, 3, 4)  # S&P 500 inception

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

    def _parse_changes_table(self, table: Tag) -> list[ConstituentRecord]:
        """Parse the S&P 500 historical changes table."""
        records: list[ConstituentRecord] = []

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
            # Check for "removed" in column name or just "ticker" if first column is date
            if "removed" in col_lower:
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
            "%Y-%m-%d",   # 2024-12-22
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None
