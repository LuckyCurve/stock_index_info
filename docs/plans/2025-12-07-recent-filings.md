# Recent SEC Filings Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend `/query` command to return the latest 4 quarterly reports (10-Q) and 1 annual report (10-K) for queried stocks.

**Architecture:** Add `RecentFilings` dataclass to group quarterly and annual filings. Create `get_recent_filings()` function in `sec_edgar.py` that fetches up to 4 10-Qs and 1 10-K in a single API call. Update `_query_ticker()` in `bot.py` to display filings only when available (silent skip if none found).

**Tech Stack:** `curl_cffi` (existing), SEC EDGAR REST API (no auth required)

---

## Task 1: Add RecentFilings Data Model

**Files:**
- Modify: `src/stock_index_info/models.py:54-62`
- Test: `tests/test_models.py`

**Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
class TestRecentFilings:
    def test_recent_filings_creation(self) -> None:
        """Test RecentFilings dataclass creation."""
        from stock_index_info.models import RecentFilings, SECFilingRecord

        quarterly = [
            SECFilingRecord(
                ticker="AAPL",
                form_type="10-Q",
                filing_date="2024-11-01",
                filing_url="https://www.sec.gov/example1",
            ),
            SECFilingRecord(
                ticker="AAPL",
                form_type="10-Q",
                filing_date="2024-08-02",
                filing_url="https://www.sec.gov/example2",
            ),
        ]
        annual = SECFilingRecord(
            ticker="AAPL",
            form_type="10-K",
            filing_date="2024-10-31",
            filing_url="https://www.sec.gov/example3",
        )

        filings = RecentFilings(quarterly=quarterly, annual=annual)
        assert len(filings.quarterly) == 2
        assert filings.quarterly[0].form_type == "10-Q"
        assert filings.annual is not None
        assert filings.annual.form_type == "10-K"

    def test_recent_filings_no_annual(self) -> None:
        """Test RecentFilings with no annual report."""
        from stock_index_info.models import RecentFilings

        filings = RecentFilings(quarterly=[], annual=None)
        assert len(filings.quarterly) == 0
        assert filings.annual is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py::TestRecentFilings -v`
Expected: FAIL with "cannot import name 'RecentFilings'"

**Step 3: Write minimal implementation**

Add to `src/stock_index_info/models.py` after `SECFilingRecord`:

```python
@dataclass
class RecentFilings:
    """Recent SEC filings for a stock."""

    quarterly: list[SECFilingRecord]  # Up to 4 10-Q filings, descending by date
    annual: Optional[SECFilingRecord]  # Latest 10-K filing, or None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py::TestRecentFilings -v`
Expected: PASS

**Step 5: Run code quality checks**

Run: `uv run ruff check src/ tests/ && uv run mypy src/`
Expected: No errors

**Step 6: Commit**

```bash
git add src/stock_index_info/models.py tests/test_models.py
git commit -m "feat(models): add RecentFilings dataclass for quarterly and annual reports"
```

---

## Task 2: Add get_recent_filings Function

**Files:**
- Modify: `src/stock_index_info/sec_edgar.py`
- Modify: `tests/test_sec_edgar.py`

**Step 1: Write the failing test**

Add to `tests/test_sec_edgar.py`:

```python
def test_get_recent_filings_valid_ticker():
    """Test getting recent filings for a valid ticker."""
    from stock_index_info.sec_edgar import get_recent_filings
    from stock_index_info.models import RecentFilings

    result = get_recent_filings("AAPL")

    assert result is not None
    assert isinstance(result, RecentFilings)
    # Should have up to 4 quarterly reports
    assert len(result.quarterly) <= 4
    assert len(result.quarterly) > 0  # AAPL should have at least one 10-Q
    for q in result.quarterly:
        assert q.form_type == "10-Q"
        assert q.ticker == "AAPL"
        assert q.filing_url.startswith("https://www.sec.gov")
    # Should have annual report
    assert result.annual is not None
    assert result.annual.form_type == "10-K"
    assert result.annual.ticker == "AAPL"


def test_get_recent_filings_invalid_ticker():
    """Test getting recent filings for invalid ticker returns None."""
    from stock_index_info.sec_edgar import get_recent_filings

    result = get_recent_filings("INVALIDTICKER123")
    assert result is None


def test_get_recent_filings_quarterly_order():
    """Test that quarterly filings are returned in descending date order."""
    from stock_index_info.sec_edgar import get_recent_filings

    result = get_recent_filings("AAPL")
    assert result is not None
    # Verify descending order by filing_date
    dates = [q.filing_date for q in result.quarterly]
    assert dates == sorted(dates, reverse=True)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sec_edgar.py::test_get_recent_filings_valid_ticker -v`
Expected: FAIL with "cannot import name 'get_recent_filings'"

**Step 3: Write minimal implementation**

Add to `src/stock_index_info/sec_edgar.py`:

```python
from stock_index_info.models import SECFilingRecord, RecentFilings


def get_recent_filings(ticker: str) -> Optional[RecentFilings]:
    """Get the latest 4 quarterly (10-Q) and 1 annual (10-K) filings for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        RecentFilings with quarterly and annual filings, or None if ticker not found
    """
    cik = get_cik_from_ticker(ticker)
    if cik is None:
        return None

    # Pad CIK to 10 digits for API
    cik_padded = cik.zfill(10)

    # Query company submissions endpoint
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"

    try:
        response = requests.get(
            url,
            headers={"User-Agent": SEC_USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        # Extract filing arrays
        recent_filings = data.get("filings", {}).get("recent", {})
        forms = recent_filings.get("form", [])
        accession_numbers = recent_filings.get("accessionNumber", [])
        filing_dates = recent_filings.get("filingDate", [])
        primary_documents = recent_filings.get("primaryDocument", [])

        quarterly: list[SECFilingRecord] = []
        annual: Optional[SECFilingRecord] = None

        for i, form in enumerate(forms):
            accession = accession_numbers[i].replace("-", "")
            filing_date = filing_dates[i]
            primary_doc = primary_documents[i]

            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}"
            )

            if form == "10-Q" and len(quarterly) < 4:
                quarterly.append(
                    SECFilingRecord(
                        ticker=ticker.upper(),
                        form_type="10-Q",
                        filing_date=filing_date,
                        filing_url=filing_url,
                    )
                )
            elif form == "10-K" and annual is None:
                annual = SECFilingRecord(
                    ticker=ticker.upper(),
                    form_type="10-K",
                    filing_date=filing_date,
                    filing_url=filing_url,
                )

            # Early exit if we have all we need
            if len(quarterly) == 4 and annual is not None:
                break

        return RecentFilings(quarterly=quarterly, annual=annual)
    except Exception:
        return None
```

**Step 4: Update import in sec_edgar.py**

Change the import at line 7 from:

```python
from stock_index_info.models import SECFilingRecord
```

to:

```python
from stock_index_info.models import SECFilingRecord, RecentFilings
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_sec_edgar.py -v`
Expected: PASS

**Step 6: Run code quality checks**

Run: `uv run ruff check src/ tests/ && uv run mypy src/`
Expected: No errors

**Step 7: Commit**

```bash
git add src/stock_index_info/sec_edgar.py tests/test_sec_edgar.py
git commit -m "feat(sec_edgar): add get_recent_filings for 4 quarterly and 1 annual report"
```

---

## Task 3: Integrate Recent Filings into Bot

**Files:**
- Modify: `src/stock_index_info/bot.py:34,253-260`

**Step 1: Update import**

Change line 34 from:

```python
from stock_index_info.sec_edgar import get_latest_10q
```

to:

```python
from stock_index_info.sec_edgar import get_recent_filings
```

**Step 2: Replace SEC filing display logic in `_query_ticker()`**

Replace lines 253-260 (the SEC 10-Q section):

```python
        # Fetch SEC 10-Q report
        lines.append("")
        sec_filing = get_latest_10q(ticker)
        if sec_filing:
            lines.append(f"Latest 10-Q ({sec_filing.filing_date}):")
            lines.append(sec_filing.filing_url)
        else:
            lines.append("10-Q Report: Not found")
```

with:

```python
        # Fetch SEC filings (silent skip if not found)
        filings = get_recent_filings(ticker)
        if filings and (filings.quarterly or filings.annual):
            lines.append("")
            lines.append("SEC Filings:")

            # Show quarterly reports (10-Q)
            if filings.quarterly:
                lines.append("Quarterly (10-Q):")
                for q in filings.quarterly:
                    lines.append(f"  {q.filing_date}: {q.filing_url}")

            # Show annual report (10-K)
            if filings.annual:
                lines.append("Annual (10-K):")
                lines.append(f"  {filings.annual.filing_date}: {filings.annual.filing_url}")
```

**Step 3: Run code quality checks**

Run: `uv run ruff check src/ tests/ && uv run mypy src/`
Expected: No errors

**Step 4: Commit**

```bash
git add src/stock_index_info/bot.py
git commit -m "feat(bot): display recent quarterly and annual SEC filings in query response"
```

---

## Task 4: Manual Integration Test

**Step 1: Run the bot locally**

```bash
TELEGRAM_BOT_TOKEN=<your-token> ALLOWED_USER_IDS=<your-id> uv run stock-index-bot
```

**Step 2: Test via Telegram**

Send `/query AAPL` to your bot and verify:
1. Index membership info displays correctly
2. Up to 4 quarterly (10-Q) links appear with filing dates
3. 1 annual (10-K) link appears with filing date
4. All links are clickable and lead to SEC EDGAR

**Step 3: Test edge cases**

- `/query INVALIDTICKER` - should show "Not found in any tracked index" with NO SEC filings section (silent skip)
- `/query MSFT` - should show both index membership and filings
- Direct message `GOOGL` - should also show filings

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add RecentFilings model | models.py, test_models.py |
| 2 | Add get_recent_filings function | sec_edgar.py, test_sec_edgar.py |
| 3 | Bot integration with silent skip | bot.py |
| 4 | Manual testing | - |

**Total estimated time:** 20-30 minutes
