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


class TestSECFilingRecord:
    def test_sec_filing_record_creation(self) -> None:
        """Test SECFilingRecord dataclass creation."""
        from stock_index_info.models import SECFilingRecord

        record = SECFilingRecord(
            ticker="AAPL",
            form_type="10-Q",
            filing_date="2024-11-01",
            filing_url="https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm",
        )
        assert record.ticker == "AAPL"
        assert record.form_type == "10-Q"
        assert record.filing_date == "2024-11-01"
        assert record.filing_url.startswith("https://www.sec.gov")
