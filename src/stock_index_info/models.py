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
    added_date: Optional[date] = None
    removed_date: Optional[date] = None
    company_name: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class IndexMembership:
    """Represents a stock's membership in an index with computed properties."""

    index_code: str
    index_name: str
    added_date: Optional[date] = None
    removed_date: Optional[date] = None
    reason: Optional[str] = None

    @property
    def is_current(self) -> bool:
        """Whether the stock is currently in this index."""
        return self.removed_date is None

    @property
    def years_in_index(self) -> Optional[float]:
        """Calculate years the stock has been/was in the index.

        Returns None if added_date is unknown.
        """
        if self.added_date is None:
            return None
        end_date = self.removed_date or date.today()
        delta = end_date - self.added_date
        return delta.days / 365.25


@dataclass
class SECFilingRecord:
    """A record of SEC filing for a stock."""

    ticker: str
    form_type: str
    filing_date: str
    filing_url: str


@dataclass
class RecentFilings:
    """Recent SEC filings for a stock."""

    quarterly: list[SECFilingRecord]  # Up to 4 10-Q filings, descending by date
    annual: Optional[SECFilingRecord]  # Latest 10-K filing, or None


@dataclass
class IncomeRecord:
    """Annual net income record for a stock."""

    ticker: str
    fiscal_year: int
    net_income: float  # Net income in dollars (not millions)


@dataclass
class CachedIncome:
    """Cached income statement data for a stock."""

    ticker: str
    last_updated: str  # ISO format date
    annual_income: list[IncomeRecord]


@dataclass
class BalanceSheetRecord:
    """Annual balance sheet record for a stock."""

    ticker: str
    fiscal_year: int
    total_assets: float
    total_liabilities: float
    total_current_assets: float
    goodwill: float
    intangible_assets: float


@dataclass
class CachedBalanceSheet:
    """Cached balance sheet data for a stock."""

    ticker: str
    last_updated: str  # ISO format date
    annual_records: list["BalanceSheetRecord"]


@dataclass
class AssetValuationResult:
    """NTA and NCAV calculation result."""

    nta: float  # Net Tangible Assets
    ncav: float  # Net Current Asset Value
    p_nta: Optional[float]  # P/NTA ratio, None if NTA <= 0
    p_ncav: Optional[float]  # P/NCAV ratio, None if NCAV <= 0


@dataclass
class PEResult:
    """7-year average P/E calculation result."""

    pe: float  # P/E ratio
    avg_income: float  # 7-year average net income in USD
