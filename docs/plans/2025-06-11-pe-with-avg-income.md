# P/E 显示同时输出七年平均利润 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在输出 P/E 时同时显示七年平均净利润（美元），格式为 `P/E (7Y Avg): 15.2 | Avg Income: $12.5B`

**Architecture:** 修改 `get_7year_pe()` 返回包含 PE 和平均利润的数据类 `PEResult`，新增 `format_currency()` 函数将金额格式化为简洁格式（B/M/K），更新 bot 显示逻辑。

**Tech Stack:** Python dataclasses, 现有 alpha_vantage 模块

---

### Task 1: 在 models.py 添加 PEResult 数据类

**Files:**
- Modify: `src/stock_index_info/models.py:88` (文件末尾)

**Step 1: 添加 PEResult 数据类**

在 `models.py` 文件末尾添加：

```python
@dataclass
class PEResult:
    """7-year average P/E calculation result."""

    pe: float  # P/E ratio
    avg_income: float  # 7-year average net income in USD
```

**Step 2: 运行类型检查确认无错误**

Run: `uv run mypy src/stock_index_info/models.py`
Expected: Success, no errors

**Step 3: Commit**

```bash
git add src/stock_index_info/models.py
git commit -m "feat(models): add PEResult dataclass for PE with avg income"
```

---

### Task 2: 在 alpha_vantage.py 添加 format_currency 函数

**Files:**
- Modify: `src/stock_index_info/alpha_vantage.py:17` (在 logger 定义后)
- Test: `tests/test_alpha_vantage.py`

**Step 1: 写失败的测试**

在 `tests/test_alpha_vantage.py` 文件末尾添加：

```python
def test_format_currency_billions():
    """Test formatting large numbers in billions."""
    from stock_index_info.alpha_vantage import format_currency

    assert format_currency(12_500_000_000) == "$12.5B"
    assert format_currency(1_000_000_000) == "$1.0B"
    assert format_currency(100_000_000_000) == "$100.0B"


def test_format_currency_millions():
    """Test formatting numbers in millions."""
    from stock_index_info.alpha_vantage import format_currency

    assert format_currency(500_000_000) == "$500.0M"
    assert format_currency(50_000_000) == "$50.0M"
    assert format_currency(1_000_000) == "$1.0M"


def test_format_currency_thousands():
    """Test formatting numbers in thousands."""
    from stock_index_info.alpha_vantage import format_currency

    assert format_currency(500_000) == "$500.0K"
    assert format_currency(50_000) == "$50.0K"


def test_format_currency_small():
    """Test formatting small numbers."""
    from stock_index_info.alpha_vantage import format_currency

    assert format_currency(5_000) == "$5000"
    assert format_currency(500) == "$500"


def test_format_currency_negative():
    """Test formatting negative numbers."""
    from stock_index_info.alpha_vantage import format_currency

    assert format_currency(-12_500_000_000) == "-$12.5B"
    assert format_currency(-500_000_000) == "-$500.0M"
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_alpha_vantage.py::test_format_currency_billions -v`
Expected: FAIL with "cannot import name 'format_currency'"

**Step 3: 实现 format_currency 函数**

在 `src/stock_index_info/alpha_vantage.py` 的 `logger = logging.getLogger(__name__)` 之后（第17行后）添加：

```python
def format_currency(amount: float) -> str:
    """Format a dollar amount in a compact human-readable format.

    Args:
        amount: Dollar amount (can be negative)

    Returns:
        Formatted string like "$12.5B", "$500.0M", "$50.0K", or "$5000"
    """
    negative = amount < 0
    abs_amount = abs(amount)
    prefix = "-" if negative else ""

    if abs_amount >= 1_000_000_000:
        return f"{prefix}${abs_amount / 1_000_000_000:.1f}B"
    elif abs_amount >= 1_000_000:
        return f"{prefix}${abs_amount / 1_000_000:.1f}M"
    elif abs_amount >= 10_000:
        return f"{prefix}${abs_amount / 1_000:.1f}K"
    else:
        return f"{prefix}${int(abs_amount)}"
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_alpha_vantage.py -k "format_currency" -v`
Expected: All 5 format_currency tests PASS

**Step 5: 运行类型检查**

Run: `uv run mypy src/stock_index_info/alpha_vantage.py`
Expected: Success, no errors

**Step 6: Commit**

```bash
git add src/stock_index_info/alpha_vantage.py tests/test_alpha_vantage.py
git commit -m "feat(alpha_vantage): add format_currency function for compact money display"
```

---

### Task 3: 修改 calculate_7year_avg_pe 返回 PEResult

**Files:**
- Modify: `src/stock_index_info/alpha_vantage.py:14` (imports)
- Modify: `src/stock_index_info/alpha_vantage.py:160-193` (calculate_7year_avg_pe 函数)
- Test: `tests/test_alpha_vantage.py`

**Step 1: 更新 import 语句**

在 `src/stock_index_info/alpha_vantage.py:14`，修改：

```python
# 原来:
from stock_index_info.models import IncomeRecord

# 改为:
from stock_index_info.models import IncomeRecord, PEResult
```

**Step 2: 更新现有测试以期望 PEResult**

修改 `tests/test_alpha_vantage.py` 中的 `test_calculate_7year_avg_pe` 函数（约第70-91行）：

```python
def test_calculate_7year_avg_pe():
    """Test calculating 7-year average P/E using market cap and net income."""
    from stock_index_info.alpha_vantage import calculate_7year_avg_pe
    from stock_index_info.models import IncomeRecord

    records = [
        IncomeRecord(ticker="TEST", fiscal_year=2024, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2023, net_income=90_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2022, net_income=80_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2021, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2020, net_income=110_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2019, net_income=120_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2018, net_income=100_000_000),
    ]
    # Average net income = 700_000_000 / 7 = 100_000_000
    # P/E = 2_000_000_000 / 100_000_000 = 20.0
    market_cap = 2_000_000_000.0

    result = calculate_7year_avg_pe(records, market_cap)

    assert result is not None
    assert abs(result.pe - 20.0) < 0.01
    assert abs(result.avg_income - 100_000_000) < 0.01
```

**Step 3: 运行测试确认失败**

Run: `uv run pytest tests/test_alpha_vantage.py::test_calculate_7year_avg_pe -v`
Expected: FAIL with AttributeError (result has no attribute 'pe')

**Step 4: 修改 calculate_7year_avg_pe 函数**

在 `src/stock_index_info/alpha_vantage.py`，替换 `calculate_7year_avg_pe` 函数（约第178-211行）：

```python
def calculate_7year_avg_pe(
    income_records: list[IncomeRecord],
    market_cap: float,
) -> Optional[PEResult]:
    """Calculate P/E ratio using 7-year average net income.

    Args:
        income_records: List of IncomeRecord, should be sorted by fiscal_year descending
        market_cap: Current market capitalization in dollars

    Returns:
        PEResult with P/E ratio and average income, or None if:
        - Less than 7 years of data
        - Years are not consecutive
        - Average net income <= 0
    """
    if len(income_records) < 7:
        return None

    # Take the 7 most recent years
    recent_7 = income_records[:7]

    # Check for consecutive years
    years = [r.fiscal_year for r in recent_7]
    for i in range(len(years) - 1):
        if years[i] - years[i + 1] != 1:
            return None

    avg_net_income = sum(r.net_income for r in recent_7) / 7

    if avg_net_income <= 0:
        return None

    pe = market_cap / avg_net_income
    return PEResult(pe=pe, avg_income=avg_net_income)
```

**Step 5: 运行测试确认通过**

Run: `uv run pytest tests/test_alpha_vantage.py::test_calculate_7year_avg_pe -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/stock_index_info/alpha_vantage.py tests/test_alpha_vantage.py
git commit -m "refactor(alpha_vantage): calculate_7year_avg_pe returns PEResult with avg_income"
```

---

### Task 4: 修改 get_7year_pe 返回 PEResult

**Files:**
- Modify: `src/stock_index_info/alpha_vantage.py:214-266` (get_7year_pe 函数)
- Test: `tests/test_alpha_vantage.py`

**Step 1: 更新测试 test_get_7year_pe_with_cache**

修改 `tests/test_alpha_vantage.py` 中的 `test_get_7year_pe_with_cache` 函数（约第155-178行）：

```python
def test_get_7year_pe_with_cache(db_connection):
    """Test getting 7-year P/E uses cache when available."""
    from stock_index_info.alpha_vantage import get_7year_pe
    from stock_index_info.db import save_income
    from stock_index_info.models import IncomeRecord

    # Pre-populate cache with 7 consecutive years of data
    records = [
        IncomeRecord(ticker="TEST", fiscal_year=2024, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2023, net_income=90_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2022, net_income=80_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2021, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2020, net_income=110_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2019, net_income=120_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2018, net_income=100_000_000),
    ]
    save_income(db_connection, "TEST", records, "2025-01-15")

    # Average net income = 700_000_000 / 7 = 100_000_000
    # P/E = 2_000_000_000 / 100_000_000 = 20.0
    result = get_7year_pe(db_connection, "TEST", market_cap=2_000_000_000.0)

    assert result is not None
    assert abs(result.pe - 20.0) < 0.01
    assert abs(result.avg_income - 100_000_000) < 0.01
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_alpha_vantage.py::test_get_7year_pe_with_cache -v`
Expected: FAIL with AttributeError (result has no attribute 'pe')

**Step 3: 修改 get_7year_pe 函数返回类型**

在 `src/stock_index_info/alpha_vantage.py`，修改 `get_7year_pe` 函数的返回类型和返回语句（约第214-266行）：

```python
def get_7year_pe(
    conn: sqlite3.Connection,
    ticker: str,
    market_cap: Optional[float] = None,
    latest_filing_date: Optional[str] = None,
) -> Optional[PEResult]:
    """Get 7-year average P/E ratio for a ticker.

    Uses cached net income data if available and not stale. Fetches from Alpha Vantage
    if cache is empty or if latest_filing_date is newer than cache.

    Args:
        conn: Database connection
        ticker: Stock ticker symbol
        market_cap: Current market cap (fetched via yfinance if not provided)
        latest_filing_date: Latest SEC filing date (ISO format). If newer than
                           cache last_updated, triggers cache refresh.

    Returns:
        PEResult with 7-year average P/E ratio and average income, or None if insufficient data.
    """
    ticker_upper = ticker.upper()

    # Get cached data
    cached = get_cached_income(conn, ticker_upper)

    # Determine if we need to refresh cache
    need_refresh = False
    if cached is None:
        need_refresh = True
    elif latest_filing_date and latest_filing_date > cached.last_updated:
        need_refresh = True

    # Refresh cache if needed
    if need_refresh:
        new_records = fetch_annual_net_income(ticker_upper)
        if new_records:
            today = date.today().isoformat()
            save_income(conn, ticker_upper, new_records, today)
            cached = get_cached_income(conn, ticker_upper)

    # Check if we have enough data
    if cached is None or len(cached.annual_income) < 7:
        return None

    # Get market cap if not provided
    if market_cap is None:
        market_cap = get_market_cap(ticker_upper)
        if market_cap is None:
            return None

    return calculate_7year_avg_pe(cached.annual_income, market_cap)
```

**Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_alpha_vantage.py::test_get_7year_pe_with_cache -v`
Expected: PASS

**Step 5: 运行所有 alpha_vantage 测试**

Run: `uv run pytest tests/test_alpha_vantage.py -v`
Expected: All tests PASS

**Step 6: 运行类型检查**

Run: `uv run mypy src/stock_index_info/alpha_vantage.py`
Expected: Success, no errors

**Step 7: Commit**

```bash
git add src/stock_index_info/alpha_vantage.py tests/test_alpha_vantage.py
git commit -m "refactor(alpha_vantage): get_7year_pe returns PEResult"
```

---

### Task 5: 更新 bot.py 显示逻辑

**Files:**
- Modify: `src/stock_index_info/bot.py:35` (imports)
- Modify: `src/stock_index_info/bot.py:264-268` (_query_ticker 函数中的 PE 显示)

**Step 1: 更新 import 语句**

在 `src/stock_index_info/bot.py:35`，修改：

```python
# 原来:
from stock_index_info.alpha_vantage import get_7year_pe

# 改为:
from stock_index_info.alpha_vantage import get_7year_pe, format_currency
```

**Step 2: 更新 PE 显示逻辑**

在 `src/stock_index_info/bot.py`，修改 `_query_ticker` 函数中的 PE 显示部分（约第264-268行）：

```python
        # Calculate and display 7-year average P/E (at the top)
        pe_result = get_7year_pe(conn, ticker, latest_filing_date=latest_filing_date)
        if pe_result is not None:
            lines.append(
                f"P/E (7Y Avg): {pe_result.pe:.1f} | Avg Income: {format_currency(pe_result.avg_income)}"
            )
            lines.append("")
```

**Step 3: 运行类型检查**

Run: `uv run mypy src/stock_index_info/bot.py`
Expected: Success, no errors

**Step 4: 运行代码检查**

Run: `uv run ruff check src/`
Expected: No errors

**Step 5: Commit**

```bash
git add src/stock_index_info/bot.py
git commit -m "feat(bot): display 7-year avg income alongside PE ratio"
```

---

### Task 6: 运行完整测试套件验证

**Files:** None (verification only)

**Step 1: 运行所有测试**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 2: 运行类型检查**

Run: `uv run mypy src/`
Expected: Success, no errors

**Step 3: 运行代码检查**

Run: `uv run ruff check src/ tests/`
Expected: No errors

---

## 最终结果

完成后，查询股票时 P/E 行将显示为：

```
P/E (7Y Avg): 15.2 | Avg Income: $12.5B
```

而不是原来的：

```
P/E (7Y Avg): 15.2
```
