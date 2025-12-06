"""Integration tests for the full workflow."""

from datetime import date
from pathlib import Path


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
