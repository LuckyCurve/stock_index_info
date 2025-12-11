"""Tests for balance sheet database operations."""

from stock_index_info.db import save_balance_sheet, get_cached_balance_sheet
from stock_index_info.models import BalanceSheetRecord


def test_save_and_get_balance_sheet(db_connection):
    """Test saving and retrieving balance sheet data."""
    records = [
        BalanceSheetRecord(
            ticker="TEST",
            fiscal_year=2024,
            total_assets=100_000_000,
            total_liabilities=50_000_000,
            total_current_assets=30_000_000,
            goodwill=5_000_000,
            intangible_assets=3_000_000,
        ),
        BalanceSheetRecord(
            ticker="TEST",
            fiscal_year=2023,
            total_assets=90_000_000,
            total_liabilities=45_000_000,
            total_current_assets=28_000_000,
            goodwill=5_000_000,
            intangible_assets=3_000_000,
        ),
    ]

    save_balance_sheet(db_connection, "TEST", records, "2025-01-15")
    cached = get_cached_balance_sheet(db_connection, "TEST")

    assert cached is not None
    assert cached.ticker == "TEST"
    assert cached.last_updated == "2025-01-15"
    assert len(cached.annual_records) == 2
    assert cached.annual_records[0].fiscal_year == 2024
    assert cached.annual_records[0].total_assets == 100_000_000


def test_get_cached_balance_sheet_not_found(db_connection):
    """Test getting balance sheet for non-existent ticker."""
    cached = get_cached_balance_sheet(db_connection, "NOTFOUND")
    assert cached is None


def test_save_balance_sheet_replaces_existing(db_connection):
    """Test that saving balance sheet replaces existing data."""
    old_records = [
        BalanceSheetRecord(
            ticker="TEST",
            fiscal_year=2023,
            total_assets=80_000_000,
            total_liabilities=40_000_000,
            total_current_assets=25_000_000,
            goodwill=4_000_000,
            intangible_assets=2_000_000,
        ),
    ]
    save_balance_sheet(db_connection, "TEST", old_records, "2024-01-01")

    new_records = [
        BalanceSheetRecord(
            ticker="TEST",
            fiscal_year=2024,
            total_assets=100_000_000,
            total_liabilities=50_000_000,
            total_current_assets=30_000_000,
            goodwill=5_000_000,
            intangible_assets=3_000_000,
        ),
    ]
    save_balance_sheet(db_connection, "TEST", new_records, "2025-01-15")

    cached = get_cached_balance_sheet(db_connection, "TEST")

    assert cached is not None
    assert len(cached.annual_records) == 1
    assert cached.annual_records[0].fiscal_year == 2024
    assert cached.last_updated == "2025-01-15"
