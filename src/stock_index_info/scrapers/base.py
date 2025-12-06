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
