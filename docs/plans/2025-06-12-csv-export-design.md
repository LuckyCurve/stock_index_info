# CSV Export with GitHub Action

## Overview

Create a Python script to export S&P 500 and NASDAQ 100 constituent data to CSV files, with GitHub Action for daily automated updates.

## File Structure

```
scripts/
  export_csv.py      # Export script
data/
  sp500.csv          # S&P 500 data
  nasdaq100.csv      # NASDAQ 100 data
.github/
  workflows/
    sync-data.yml    # GitHub Action config
```

## CSV Format

Each file contains 4 columns:

```csv
ticker,company_name,added_date,removed_date
AAPL,Apple Inc.,1982-01-01,
MSFT,Microsoft Corp.,1994-06-01,
XYZ,Some Company,2020-01-01,2023-06-15
```

- `removed_date` empty means current constituent
- Sorted by `ticker` alphabetically

## Script Logic

1. Call `SP500Scraper().fetch()` and `NASDAQ100Scraper().fetch()`
2. Convert `ConstituentRecord` list to CSV, write to `data/` directory
3. Script runs standalone, no database dependency

## GitHub Action

- **Trigger**: Daily UTC 2:00 + manual `workflow_dispatch`
- **Flow**: checkout -> setup python -> uv sync -> run script -> commit & push
- **Commit message**: `chore: update index data [skip ci]`
