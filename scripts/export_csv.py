#!/usr/bin/env python3
"""Export S&P 500 and NASDAQ 100 constituent data to CSV files."""

import csv
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from stock_index_info.models import ConstituentRecord
from stock_index_info.scrapers.nasdaq100 import NASDAQ100Scraper
from stock_index_info.scrapers.sp500 import SP500Scraper


def export_to_csv(records: list[ConstituentRecord], output_path: Path) -> None:
    """Export constituent records to a CSV file.

    Args:
        records: List of ConstituentRecord to export
        output_path: Path to the output CSV file
    """
    # Sort by ticker alphabetically
    sorted_records = sorted(records, key=lambda r: r.ticker)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ticker", "company_name", "added_date", "removed_date"])

        for record in sorted_records:
            writer.writerow(
                [
                    record.ticker,
                    record.company_name or "",
                    record.added_date.isoformat() if record.added_date else "",
                    record.removed_date.isoformat() if record.removed_date else "",
                ]
            )


def main() -> None:
    """Main entry point."""
    # Determine output directory
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)

    # Export S&P 500
    print("Fetching S&P 500 data...")
    sp500_scraper = SP500Scraper()
    sp500_records = sp500_scraper.fetch()
    sp500_path = data_dir / "sp500.csv"
    export_to_csv(sp500_records, sp500_path)
    print(f"Exported {len(sp500_records)} S&P 500 records to {sp500_path}")

    # Export NASDAQ 100
    print("Fetching NASDAQ 100 data...")
    nasdaq_scraper = NASDAQ100Scraper()
    nasdaq_records = nasdaq_scraper.fetch()
    nasdaq_path = data_dir / "nasdaq100.csv"
    export_to_csv(nasdaq_records, nasdaq_path)
    print(f"Exported {len(nasdaq_records)} NASDAQ 100 records to {nasdaq_path}")

    print("Done!")


if __name__ == "__main__":
    main()
