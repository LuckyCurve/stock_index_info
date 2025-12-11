# Price to Tangible Book (P/TB) 功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 Bot 查询股票时，在底部显示该股票的 Price to Tangible Book (P/TB) 估值指标。

**Architecture:** 新增 `services/yahoo.py` 模块封装 yfinance 调用，在 `_query_ticker()` 函数中集成 P/TB 数据获取，采用优雅降级策略（yfinance 调用失败时显示 N/A）。

**Tech Stack:** yfinance (Yahoo Finance Python 库)

---

## Task 1: 添加 yfinance 依赖

**Files:**
- Modify: `pyproject.toml:7-13`

**Step 1: 编辑 pyproject.toml 添加 yfinance 依赖**

将 `dependencies` 数组修改为：

```toml
dependencies = [
    "curl_cffi>=0.7.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0.0",
    "pandas>=2.2.0",
    "python-telegram-bot[job-queue]>=21.0",
    "yfinance>=0.2.0",
]
```

**Step 2: 同步依赖**

Run: `uv sync`
Expected: 成功安装 yfinance 及其依赖

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add yfinance dependency for P/TB valuation"
```

---

## Task 2: 创建 Yahoo Finance 服务模块

**Files:**
- Create: `src/stock_index_info/services/__init__.py`
- Create: `src/stock_index_info/services/yahoo.py`
- Create: `tests/test_services/__init__.py`
- Create: `tests/test_services/test_yahoo.py`

**Step 1: 创建 services 包的 `__init__.py`**

```python
"""Services package for external API integrations."""
```

**Step 2: 创建 tests/test_services 包的 `__init__.py`**

```python
"""Tests for services package."""
```

**Step 3: 编写失败测试**

创建 `tests/test_services/test_yahoo.py`：

```python
"""Tests for Yahoo Finance service."""

from unittest.mock import MagicMock, patch

import pytest

from stock_index_info.services.yahoo import get_price_to_tangible_book


class TestGetPriceToTangibleBook:
    """Tests for get_price_to_tangible_book function."""

    def test_returns_ptb_when_available(self) -> None:
        """Should return P/TB value when yfinance provides it."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"priceToTangibleBook": 45.2}

        with patch("stock_index_info.services.yahoo.yf.Ticker", return_value=mock_ticker):
            result = get_price_to_tangible_book("AAPL")

        assert result == 45.2

    def test_returns_none_when_field_missing(self) -> None:
        """Should return None when priceToTangibleBook field is not in info."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"priceToBook": 30.0}  # Different field

        with patch("stock_index_info.services.yahoo.yf.Ticker", return_value=mock_ticker):
            result = get_price_to_tangible_book("AAPL")

        assert result is None

    def test_returns_none_when_field_is_none(self) -> None:
        """Should return None when priceToTangibleBook is explicitly None."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"priceToTangibleBook": None}

        with patch("stock_index_info.services.yahoo.yf.Ticker", return_value=mock_ticker):
            result = get_price_to_tangible_book("AAPL")

        assert result is None

    def test_returns_none_on_exception(self) -> None:
        """Should return None when yfinance raises an exception."""
        with patch("stock_index_info.services.yahoo.yf.Ticker", side_effect=Exception("API Error")):
            result = get_price_to_tangible_book("INVALID")

        assert result is None

    def test_ticker_is_uppercased(self) -> None:
        """Should uppercase the ticker symbol."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"priceToTangibleBook": 10.0}

        with patch("stock_index_info.services.yahoo.yf.Ticker", return_value=mock_ticker) as mock_yf:
            get_price_to_tangible_book("aapl")

        mock_yf.assert_called_once_with("AAPL")
```

**Step 4: 运行测试验证失败**

Run: `uv run pytest tests/test_services/test_yahoo.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'stock_index_info.services'"

**Step 5: 实现 yahoo.py 模块**

创建 `src/stock_index_info/services/yahoo.py`：

```python
"""Yahoo Finance service for fetching stock valuation data."""

import logging
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)


def get_price_to_tangible_book(ticker: str) -> Optional[float]:
    """Fetch Price to Tangible Book ratio for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        P/TB ratio as float, or None if unavailable or on error.
    """
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        ptb = info.get("priceToTangibleBook")
        if ptb is not None:
            return float(ptb)
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch P/TB for {ticker}: {e}")
        return None
```

**Step 6: 运行测试验证通过**

Run: `uv run pytest tests/test_services/test_yahoo.py -v`
Expected: All 5 tests PASS

**Step 7: 运行代码检查**

Run: `uv run ruff check src/stock_index_info/services/ tests/test_services/`
Expected: No errors

Run: `uv run mypy src/stock_index_info/services/`
Expected: Success

**Step 8: Commit**

```bash
git add src/stock_index_info/services/ tests/test_services/
git commit -m "feat: add Yahoo Finance service for P/TB valuation"
```

---

## Task 3: 集成 P/TB 到 Bot 查询响应

**Files:**
- Modify: `src/stock_index_info/bot.py:213-253` (_query_ticker 函数)

**Step 1: 修改 bot.py 导入**

在 `bot.py` 顶部添加导入（在其他 import 之后）：

```python
from stock_index_info.services.yahoo import get_price_to_tangible_book
```

**Step 2: 修改 _query_ticker 函数**

将 `_query_ticker` 函数修改为：

```python
async def _query_ticker(update: Update, ticker: str) -> None:
    """Query and respond with ticker information."""
    if not update.message:
        return

    # Ensure data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not DB_PATH.exists():
        await update.message.reply_text(
            "Database not initialized. Please run /sync first or wait for auto-sync."
        )
        return

    conn = init_db(DB_PATH)
    try:
        memberships = get_stock_memberships(conn, ticker)

        if not memberships:
            await update.message.reply_text(f"{ticker} not found in any tracked index.")
            return

        # Build response
        lines: list[str] = [f"*{ticker}*", "", "Index Membership:", "```"]
        lines.append(f"{'Index':<12} {'Added':<12} {'Removed':<12} {'Years':>6}")
        lines.append("-" * 44)

        for m in memberships:
            added_str = m.added_date.isoformat() if m.added_date else "?"
            removed_str = m.removed_date.isoformat() if m.removed_date else "-"
            years_str = f"{m.years_in_index:>6.1f}" if m.years_in_index is not None else "     ?"
            lines.append(f"{m.index_name:<12} {added_str:<12} {removed_str:<12} {years_str}")

        lines.append("```")

        # Fetch and append P/TB valuation
        ptb = get_price_to_tangible_book(ticker)
        if ptb is not None:
            lines.append("")
            lines.append(f"P/TB: {ptb:.2f}")
        else:
            lines.append("")
            lines.append("P/TB: N/A")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error querying ticker {ticker}: {e}")
        await update.message.reply_text(f"Error querying {ticker}. Please try again.")
    finally:
        conn.close()
```

**Step 3: 运行代码检查**

Run: `uv run ruff check src/stock_index_info/bot.py`
Expected: No errors

Run: `uv run mypy src/stock_index_info/bot.py`
Expected: Success

**Step 4: 运行全部测试**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/stock_index_info/bot.py
git commit -m "feat: display P/TB valuation in ticker query response"
```

---

## Task 4: 最终验证

**Step 1: 运行完整代码检查**

Run: `uv run ruff check src/ tests/`
Expected: No errors

Run: `uv run mypy src/`
Expected: Success

**Step 2: 运行完整测试套件**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 3: 手动验证（可选）**

如果有配置好的 Bot Token，可以运行 Bot 进行手动测试：

```bash
TELEGRAM_BOT_TOKEN=<token> ALLOWED_USER_IDS=<id> uv run stock-index-bot
```

发送 `AAPL` 到 Bot，预期输出：

```
*AAPL*

Index Membership:
```
Index        Added        Removed       Years
--------------------------------------------
S&P 500      1982-01-01   -             43.2
NASDAQ 100   1985-01-01   -             40.1
```

P/TB: 45.20
```

---

## 文件变更总结

| 操作 | 文件路径 |
|------|----------|
| Modify | `pyproject.toml` |
| Create | `src/stock_index_info/services/__init__.py` |
| Create | `src/stock_index_info/services/yahoo.py` |
| Create | `tests/test_services/__init__.py` |
| Create | `tests/test_services/test_yahoo.py` |
| Modify | `src/stock_index_info/bot.py` |
