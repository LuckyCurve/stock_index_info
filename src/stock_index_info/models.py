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
