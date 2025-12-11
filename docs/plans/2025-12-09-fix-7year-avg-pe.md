# Fix 7-Year Average P/E Calculation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 7 年平均 P/E 计算从 `股价 / 7年平均EPS` 改为 `市值 / 7年平均净利润`，符合格雷厄姆的投资理论。

**Architecture:** 替换 Alpha Vantage EARNINGS API 为 INCOME_STATEMENT API 获取净利润数据，使用 yfinance 获取市值，删除旧的 earnings 表并创建新的 income_statements 表，增加年份连续性验证。

**Tech Stack:** Python, Alpha Vantage API (INCOME_STATEMENT), yfinance, SQLite

---

## Task 1: 更新数据模型

**Files:**
- Modify: `src/stock_index_info/models.py:73-88`

**Step 1: 修改 EarningsRecord 为 IncomeRecord**

将 `EarningsRecord` 重命名为 `IncomeRecord`，字段 `eps` 改为 `net_income`：

```python
@dataclass
class IncomeRecord:
    """Annual net income record for a stock."""

    ticker: str
    fiscal_year: int
    net_income: float  # Net income in dollars (not millions)
```

**Step 2: 修改 CachedEarnings 为 CachedIncome**

```python
@dataclass
class CachedIncome:
    """Cached income statement data for a stock."""

    ticker: str
    last_updated: str  # ISO format date
    annual_income: list[IncomeRecord]
```

**Step 3: 运行类型检查确认修改**

Run: `uv run mypy src/stock_index_info/models.py`
Expected: PASS (模型文件本身应该通过，其他文件会报错但这是预期的)

**Step 4: Commit**

```bash
git add src/stock_index_info/models.py
git commit -m "refactor(models): rename EarningsRecord to IncomeRecord for net income storage"
```

---

## Task 2: 更新数据库 Schema 和操作

**Files:**
- Modify: `src/stock_index_info/db.py:16-40` (SCHEMA)
- Modify: `src/stock_index_info/db.py:134-182` (save/get functions)

**Step 1: 更新 SCHEMA 常量**

将 `earnings` 表替换为 `income_statements` 表：

```python
SCHEMA = """
CREATE TABLE IF NOT EXISTS constituents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    index_code TEXT NOT NULL CHECK (index_code IN ('sp500', 'nasdaq100')),
    added_date TEXT,
    removed_date TEXT,
    reason TEXT,
    UNIQUE(ticker, index_code, added_date)
);

CREATE INDEX IF NOT EXISTS idx_constituents_ticker ON constituents(ticker);
CREATE INDEX IF NOT EXISTS idx_constituents_index ON constituents(index_code);

CREATE TABLE IF NOT EXISTS income_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    net_income REAL NOT NULL,
    last_updated TEXT NOT NULL,
    UNIQUE(ticker, fiscal_year)
);

CREATE INDEX IF NOT EXISTS idx_income_statements_ticker ON income_statements(ticker);
"""
```

**Step 2: 更新 import 语句**

```python
from stock_index_info.models import (
    ConstituentRecord,
    IndexMembership,
    INDEX_NAMES,
    IncomeRecord,
    CachedIncome,
)
```

**Step 3: 重命名 save_earnings 为 save_income**

```python
def save_income(
    conn: sqlite3.Connection,
    ticker: str,
    records: list[IncomeRecord],
    last_updated: str,
) -> None:
    """Save income statement records for a ticker, replacing any existing data."""
    ticker_upper = ticker.upper()

    # Delete existing data for this ticker
    conn.execute("DELETE FROM income_statements WHERE ticker = ?", (ticker_upper,))

    # Insert new records
    for record in records:
        conn.execute(
            """
            INSERT INTO income_statements (ticker, fiscal_year, net_income, last_updated)
            VALUES (?, ?, ?, ?)
            """,
            (ticker_upper, record.fiscal_year, record.net_income, last_updated),
        )
    conn.commit()
```

**Step 4: 重命名 get_cached_earnings 为 get_cached_income**

```python
def get_cached_income(conn: sqlite3.Connection, ticker: str) -> Optional[CachedIncome]:
    """Get cached income statements for a ticker, or None if not cached."""
    ticker_upper = ticker.upper()

    cursor = conn.execute(
        """
        SELECT fiscal_year, net_income, last_updated
        FROM income_statements
        WHERE ticker = ?
        ORDER BY fiscal_year DESC
        """,
        (ticker_upper,),
    )

    rows = cursor.fetchall()
    if not rows:
        return None

    records = [
        IncomeRecord(ticker=ticker_upper, fiscal_year=row[0], net_income=row[1])
        for row in rows
    ]

    return CachedIncome(
        ticker=ticker_upper,
        last_updated=rows[0][2],  # All rows have same last_updated
        annual_income=records,
    )
```

**Step 5: 运行类型检查**

Run: `uv run mypy src/stock_index_info/db.py`
Expected: PASS

**Step 6: Commit**

```bash
git add src/stock_index_info/db.py
git commit -m "refactor(db): replace earnings table with income_statements for net income"
```

---

## Task 3: 编写 fetch_annual_net_income 函数的测试

**Files:**
- Modify: `tests/test_alpha_vantage.py`

**Step 1: 添加 fetch_annual_net_income 的测试**

在文件末尾添加新测试：

```python
def test_fetch_annual_net_income_valid_ticker():
    """Test fetching annual net income for a valid ticker."""
    from stock_index_info.config import ALPHA_VANTAGE_API_KEY
    from stock_index_info.alpha_vantage import fetch_annual_net_income

    if not ALPHA_VANTAGE_API_KEY:
        pytest.skip("ALPHA_VANTAGE_API_KEY not set")

    records = fetch_annual_net_income("IBM")

    assert records is not None
    assert len(records) >= 7  # Should have at least 7 years
    assert all(r.ticker == "IBM" for r in records)
    assert all(r.fiscal_year >= 2000 for r in records)
    # Net income should be in dollars (large numbers)
    assert all(abs(r.net_income) > 1_000_000 for r in records)
    # Should be sorted by year descending
    years = [r.fiscal_year for r in records]
    assert years == sorted(years, reverse=True)


def test_fetch_annual_net_income_invalid_ticker():
    """Test fetching net income for invalid ticker returns None."""
    from stock_index_info.config import ALPHA_VANTAGE_API_KEY
    from stock_index_info.alpha_vantage import fetch_annual_net_income

    if not ALPHA_VANTAGE_API_KEY:
        pytest.skip("ALPHA_VANTAGE_API_KEY not set")

    records = fetch_annual_net_income("INVALIDTICKER12345")
    assert records is None


def test_fetch_annual_net_income_no_api_key(monkeypatch):
    """Test that fetch returns None when API key not configured."""
    from stock_index_info import config
    from stock_index_info.alpha_vantage import fetch_annual_net_income

    monkeypatch.setattr(config, "ALPHA_VANTAGE_API_KEY", None)

    records = fetch_annual_net_income("AAPL")
    assert records is None
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_alpha_vantage.py::test_fetch_annual_net_income_no_api_key -v`
Expected: FAIL with "cannot import name 'fetch_annual_net_income'"

**Step 3: Commit**

```bash
git add tests/test_alpha_vantage.py
git commit -m "test(alpha_vantage): add tests for fetch_annual_net_income"
```

---

## Task 4: 实现 fetch_annual_net_income 函数

**Files:**
- Modify: `src/stock_index_info/alpha_vantage.py:15-76`

**Step 1: 更新 import 语句**

```python
from stock_index_info.db import get_cached_income, save_income
from stock_index_info.models import IncomeRecord
```

**Step 2: 替换 fetch_annual_eps 为 fetch_annual_net_income**

删除 `fetch_annual_eps` 函数，添加新函数：

```python
def fetch_annual_net_income(ticker: str) -> Optional[list[IncomeRecord]]:
    """Fetch annual net income data from Alpha Vantage INCOME_STATEMENT API.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        List of IncomeRecord sorted by fiscal_year descending,
        or None if API key not configured or ticker not found.
    """
    if not ALPHA_VANTAGE_API_KEY:
        return None

    url = "https://www.alphavantage.co/query"
    params = {
        "function": "INCOME_STATEMENT",
        "symbol": ticker.upper(),
        "apikey": ALPHA_VANTAGE_API_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Check for error responses
        if "Error Message" in data or "Note" in data:
            return None

        annual_reports = data.get("annualReports", [])
        if not annual_reports:
            return None

        records: list[IncomeRecord] = []
        ticker_upper = ticker.upper()

        for entry in annual_reports:
            fiscal_date = entry.get("fiscalDateEnding", "")
            net_income_str = entry.get("netIncome", "")

            # Skip entries with missing or invalid data
            if not fiscal_date or not net_income_str or net_income_str == "None":
                continue

            try:
                fiscal_year = int(fiscal_date[:4])
                net_income = float(net_income_str)
                records.append(
                    IncomeRecord(
                        ticker=ticker_upper,
                        fiscal_year=fiscal_year,
                        net_income=net_income,
                    )
                )
            except (ValueError, TypeError):
                continue

        if not records:
            return None

        # Sort by fiscal year descending
        records.sort(key=lambda r: r.fiscal_year, reverse=True)
        return records

    except Exception:
        return None
```

**Step 3: 运行测试验证通过**

Run: `uv run pytest tests/test_alpha_vantage.py::test_fetch_annual_net_income_no_api_key -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/stock_index_info/alpha_vantage.py
git commit -m "feat(alpha_vantage): add fetch_annual_net_income using INCOME_STATEMENT API"
```

---

## Task 5: 编写 get_market_cap 函数的测试

**Files:**
- Modify: `tests/test_alpha_vantage.py`

**Step 1: 添加 get_market_cap 的测试**

```python
def test_get_market_cap_valid_ticker():
    """Test getting market cap for a valid ticker."""
    from stock_index_info.alpha_vantage import get_market_cap

    market_cap = get_market_cap("AAPL")

    # May return None if rate limited by Yahoo Finance
    if market_cap is not None:
        # Apple's market cap should be in trillions
        assert market_cap > 1_000_000_000_000


def test_get_market_cap_invalid_ticker():
    """Test getting market cap for invalid ticker returns None."""
    from stock_index_info.alpha_vantage import get_market_cap

    market_cap = get_market_cap("INVALIDTICKER12345")
    assert market_cap is None
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_alpha_vantage.py::test_get_market_cap_invalid_ticker -v`
Expected: FAIL with "cannot import name 'get_market_cap'"

**Step 3: Commit**

```bash
git add tests/test_alpha_vantage.py
git commit -m "test(alpha_vantage): add tests for get_market_cap"
```

---

## Task 6: 实现 get_market_cap 函数

**Files:**
- Modify: `src/stock_index_info/alpha_vantage.py:79-104`

**Step 1: 修改 get_current_price 为 get_market_cap**

替换 `get_current_price` 函数：

```python
def get_market_cap(ticker: str) -> Optional[float]:
    """Get current market capitalization using yfinance.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Market cap in dollars as float, or None if not found.
    """
    try:
        stock = yf.Ticker(ticker.upper())
        # Try to get market cap from info
        info = stock.info
        if info and "marketCap" in info:
            market_cap = info["marketCap"]
            if market_cap is not None:
                return float(market_cap)
        return None
    except Exception:
        return None
```

**Step 2: 运行测试验证通过**

Run: `uv run pytest tests/test_alpha_vantage.py::test_get_market_cap_invalid_ticker -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/stock_index_info/alpha_vantage.py
git commit -m "feat(alpha_vantage): add get_market_cap using yfinance"
```

---

## Task 7: 编写 calculate_7year_avg_pe 新逻辑的测试

**Files:**
- Modify: `tests/test_alpha_vantage.py`

**Step 1: 更新 calculate_7year_avg_pe 测试使用新模型**

替换原有的 `test_calculate_7year_avg_pe` 相关测试：

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

    pe = calculate_7year_avg_pe(records, market_cap)

    assert pe is not None
    assert abs(pe - 20.0) < 0.01


def test_calculate_7year_avg_pe_insufficient_data():
    """Test that P/E returns None when less than 7 years of data."""
    from stock_index_info.alpha_vantage import calculate_7year_avg_pe
    from stock_index_info.models import IncomeRecord

    records = [
        IncomeRecord(ticker="TEST", fiscal_year=2024, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2023, net_income=90_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2022, net_income=80_000_000),
    ]
    market_cap = 2_000_000_000.0

    pe = calculate_7year_avg_pe(records, market_cap)

    assert pe is None


def test_calculate_7year_avg_pe_negative_average():
    """Test that P/E returns None when average net income is negative or zero."""
    from stock_index_info.alpha_vantage import calculate_7year_avg_pe
    from stock_index_info.models import IncomeRecord

    records = [
        IncomeRecord(ticker="TEST", fiscal_year=2024, net_income=-100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2023, net_income=-90_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2022, net_income=-80_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2021, net_income=-100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2020, net_income=-110_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2019, net_income=-120_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2018, net_income=-100_000_000),
    ]
    market_cap = 2_000_000_000.0

    pe = calculate_7year_avg_pe(records, market_cap)

    assert pe is None


def test_calculate_7year_avg_pe_non_consecutive_years():
    """Test that P/E returns None when years are not consecutive."""
    from stock_index_info.alpha_vantage import calculate_7year_avg_pe
    from stock_index_info.models import IncomeRecord

    # Missing 2021 - years are not consecutive
    records = [
        IncomeRecord(ticker="TEST", fiscal_year=2024, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2023, net_income=90_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2022, net_income=80_000_000),
        # 2021 is missing
        IncomeRecord(ticker="TEST", fiscal_year=2020, net_income=110_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2019, net_income=120_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2018, net_income=100_000_000),
        IncomeRecord(ticker="TEST", fiscal_year=2017, net_income=90_000_000),
    ]
    market_cap = 2_000_000_000.0

    pe = calculate_7year_avg_pe(records, market_cap)

    assert pe is None
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_alpha_vantage.py::test_calculate_7year_avg_pe_non_consecutive_years -v`
Expected: FAIL (测试应该失败，因为当前实现没有检查年份连续性)

**Step 3: Commit**

```bash
git add tests/test_alpha_vantage.py
git commit -m "test(alpha_vantage): update calculate_7year_avg_pe tests for net income and consecutive years"
```

---

## Task 8: 实现新的 calculate_7year_avg_pe 函数

**Files:**
- Modify: `src/stock_index_info/alpha_vantage.py:107-131`

**Step 1: 更新 calculate_7year_avg_pe 函数**

替换现有函数：

```python
def calculate_7year_avg_pe(
    income_records: list[IncomeRecord],
    market_cap: float,
) -> Optional[float]:
    """Calculate P/E ratio using 7-year average net income.

    Args:
        income_records: List of IncomeRecord, should be sorted by fiscal_year descending
        market_cap: Current market capitalization in dollars

    Returns:
        P/E ratio, or None if:
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

    return market_cap / avg_net_income
```

**Step 2: 运行测试验证通过**

Run: `uv run pytest tests/test_alpha_vantage.py::test_calculate_7year_avg_pe -v`
Expected: PASS

Run: `uv run pytest tests/test_alpha_vantage.py::test_calculate_7year_avg_pe_non_consecutive_years -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/stock_index_info/alpha_vantage.py
git commit -m "feat(alpha_vantage): update calculate_7year_avg_pe with market cap and consecutive year check"
```

---

## Task 9: 编写 get_7year_pe 新逻辑的测试

**Files:**
- Modify: `tests/test_alpha_vantage.py`

**Step 1: 更新 get_7year_pe 测试**

替换 `test_get_7year_pe_with_cache`：

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
    assert abs(result - 20.0) < 0.01
```

**Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_alpha_vantage.py::test_get_7year_pe_with_cache -v`
Expected: FAIL (参数名和函数签名已改变)

**Step 3: Commit**

```bash
git add tests/test_alpha_vantage.py
git commit -m "test(alpha_vantage): update get_7year_pe test for market cap parameter"
```

---

## Task 10: 实现新的 get_7year_pe 函数

**Files:**
- Modify: `src/stock_index_info/alpha_vantage.py:133-185`

**Step 1: 更新 get_7year_pe 函数**

替换现有函数：

```python
def get_7year_pe(
    conn: sqlite3.Connection,
    ticker: str,
    market_cap: Optional[float] = None,
    latest_filing_date: Optional[str] = None,
) -> Optional[float]:
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
        7-year average P/E ratio, or None if insufficient data.
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

**Step 2: 运行测试验证通过**

Run: `uv run pytest tests/test_alpha_vantage.py::test_get_7year_pe_with_cache -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/stock_index_info/alpha_vantage.py
git commit -m "feat(alpha_vantage): update get_7year_pe to use market cap and net income"
```

---

## Task 11: 删除旧的 EPS 相关测试

**Files:**
- Modify: `tests/test_alpha_vantage.py`

**Step 1: 删除不再需要的测试**

删除以下测试函数（它们测试的是已删除的 `fetch_annual_eps` 函数）：

- `test_fetch_annual_eps_valid_ticker`
- `test_fetch_annual_eps_invalid_ticker`
- `test_fetch_annual_eps_no_api_key`
- `test_get_current_price_valid_ticker`
- `test_get_current_price_invalid_ticker`

**Step 2: 运行所有 alpha_vantage 测试**

Run: `uv run pytest tests/test_alpha_vantage.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/test_alpha_vantage.py
git commit -m "test(alpha_vantage): remove obsolete EPS and current_price tests"
```

---

## Task 12: 运行完整测试和类型检查

**Files:**
- None (verification only)

**Step 1: 运行所有测试**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 2: 运行类型检查**

Run: `uv run mypy src/`
Expected: PASS with no errors

**Step 3: 运行代码检查**

Run: `uv run ruff check src/ tests/`
Expected: PASS with no errors

**Step 4: Commit**

如果有格式修复：
```bash
git add -A
git commit -m "chore: fix code style issues"
```

---

## Task 13: 更新 CODEBUDDY.md 文档

**Files:**
- Modify: `CODEBUDDY.md`

**Step 1: 更新代码架构描述**

将 `alpha_vantage.py` 的描述从：
```
├── alpha_vantage.py # Alpha Vantage API 客户端，获取历史年度 EPS 数据；使用 yfinance 获取当前股价；计算7年平均市盈率
```

改为：
```
├── alpha_vantage.py # Alpha Vantage API 客户端，获取历史年度净利润数据；使用 yfinance 获取市值；计算7年平均市盈率 (市值/7年平均净利润)
```

**Step 2: 更新数据库 Schema**

将 `earnings` 表替换为 `income_statements` 表：

```sql
CREATE TABLE income_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    net_income REAL NOT NULL,
    last_updated TEXT NOT NULL,
    UNIQUE(ticker, fiscal_year)
);
```

**Step 3: 更新模型说明**

将：
```
- **models.py**: `ConstituentRecord` 用于存储抓取数据，`IndexMembership` 用于查询结果展示，`SECFilingRecord` 和 `RecentFilings` 用于 SEC 报告查询结果
```

改为：
```
- **models.py**: `ConstituentRecord` 用于存储抓取数据，`IndexMembership` 用于查询结果展示，`SECFilingRecord` 和 `RecentFilings` 用于 SEC 报告查询结果，`IncomeRecord` 和 `CachedIncome` 用于净利润缓存
```

**Step 4: Commit**

```bash
git add CODEBUDDY.md
git commit -m "docs: update CODEBUDDY.md with income statement changes"
```

---

## Summary

| Task | Description | Files Modified |
|------|-------------|----------------|
| 1 | 更新数据模型 | models.py |
| 2 | 更新数据库 Schema | db.py |
| 3 | 编写 fetch_annual_net_income 测试 | test_alpha_vantage.py |
| 4 | 实现 fetch_annual_net_income | alpha_vantage.py |
| 5 | 编写 get_market_cap 测试 | test_alpha_vantage.py |
| 6 | 实现 get_market_cap | alpha_vantage.py |
| 7 | 编写 calculate_7year_avg_pe 新测试 | test_alpha_vantage.py |
| 8 | 实现新 calculate_7year_avg_pe | alpha_vantage.py |
| 9 | 编写 get_7year_pe 新测试 | test_alpha_vantage.py |
| 10 | 实现新 get_7year_pe | alpha_vantage.py |
| 11 | 删除旧测试 | test_alpha_vantage.py |
| 12 | 运行完整验证 | - |
| 13 | 更新文档 | CODEBUDDY.md |
