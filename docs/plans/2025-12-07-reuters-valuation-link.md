# Reuters Valuation Link 功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 Bot 的 `/query` 查询结果中添加 Reuters Valuation 链接，方便用户点击查看 Price to Tangible Book 等估值数据。

**Architecture:** 在 `_query_ticker()` 函数中追加 Reuters 链接。由于 Reuters 使用 RIC (Reuters Instrument Code) 格式，不同交易所需要不同后缀（`.O` 为 NASDAQ，`.N` 为 NYSE，部分 NYSE 股票无后缀也可访问），因此同时提供三个链接让用户自行尝试。

**Tech Stack:** 无需新增依赖，仅修改 `bot.py`

---

## 背景知识

Reuters 链接格式：`https://www.reuters.com/markets/companies/{RIC}/key-metrics/valuation`

RIC 规则（经验证）：
- NASDAQ 股票：必须使用 `.O` 后缀（如 `AAPL.O`, `GOOGL.O`, `MSFT.O`）
- NYSE 股票：大部分无后缀可访问（如 `JPM`, `KO`），但部分必须使用 `.N` 后缀（如 `VICI.N`）
- 使用 `.N` 后缀对所有 NYSE 股票都有效

因此提供三个链接：`TICKER.O` | `TICKER.N` | `TICKER`，用户点击有效的那个即可。

---

## Task 1: 添加 Reuters 链接生成函数

**Files:**
- Modify: `src/stock_index_info/bot.py`

**Step 1: 编写失败测试**

由于这是一个纯字符串生成的简单函数，且会直接集成到 bot 中，我们跳过单独的测试文件，直接在集成后通过代码检查验证。

**Step 2: 在 bot.py 中添加辅助函数**

在 `_query_ticker` 函数之前（约第 213 行），添加以下函数：

```python
def _build_reuters_valuation_links(ticker: str) -> str:
    """Build Reuters valuation links for a ticker.

    Returns Markdown formatted links for NASDAQ (.O), NYSE (.N), and no-suffix variants.
    User can click each to find the working one.
    """
    base_url = "https://www.reuters.com/markets/companies"
    ticker_upper = ticker.upper()
    return (
        f"Reuters Valuation: "
        f"[{ticker_upper}.O]({base_url}/{ticker_upper}.O/key-metrics/valuation) | "
        f"[{ticker_upper}.N]({base_url}/{ticker_upper}.N/key-metrics/valuation) | "
        f"[{ticker_upper}]({base_url}/{ticker_upper}/key-metrics/valuation)"
    )
```

**Step 3: 运行代码检查**

Run: `uv run ruff check src/stock_index_info/bot.py`
Expected: No errors

Run: `uv run mypy src/stock_index_info/bot.py`
Expected: Success

**Step 4: Commit**

```bash
git add src/stock_index_info/bot.py
git commit -m "feat: add Reuters valuation link builder function"
```

---

## Task 2: 集成 Reuters 链接到查询响应

**Files:**
- Modify: `src/stock_index_info/bot.py:214-275` (`_query_ticker` 函数)

**Step 1: 修改 _query_ticker 函数**

在 `_query_ticker` 函数中，在 SEC Filings 部分之后、`await update.message.reply_text()` 之前，添加 Reuters 链接：

找到这段代码（约第 266-269 行）：

```python
            # Show annual report (10-K)
            if filings.annual:
                lines.append("Annual (10-K):")
                lines.append(f"  {filings.annual.filing_date}: {filings.annual.filing_url}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
```

修改为：

```python
            # Show annual report (10-K)
            if filings.annual:
                lines.append("Annual (10-K):")
                lines.append(f"  {filings.annual.filing_date}: {filings.annual.filing_url}")

        # Reuters Valuation link
        lines.append("")
        lines.append(_build_reuters_valuation_links(ticker))

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
```

**Step 2: 运行代码检查**

Run: `uv run ruff check src/stock_index_info/bot.py`
Expected: No errors

Run: `uv run mypy src/stock_index_info/bot.py`
Expected: Success

**Step 3: 运行全部测试**

Run: `uv run pytest -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add src/stock_index_info/bot.py
git commit -m "feat: display Reuters valuation links in ticker query response"
```

---

## Task 3: 最终验证

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

发送 `AAPL` 到 Bot，预期输出包含：

```
*AAPL*

Index Membership:
...

SEC Filings:
...

Reuters Valuation: [AAPL.O](https://...) | [AAPL.N](https://...) | [AAPL](https://...)
```

用户点击 `AAPL.O` 链接应该能访问 Reuters 页面查看 Price to Tangible Book 数据。

---

## 文件变更总结

| 操作 | 文件路径 |
|------|----------|
| Modify | `src/stock_index_info/bot.py` |

## 预期最终代码变更

### bot.py 完整修改

1. 在 `_query_ticker` 函数前添加 `_build_reuters_valuation_links` 函数
2. 在 `_query_ticker` 函数中调用该函数并追加到响应中

修改后的 `_query_ticker` 函数结构：

```python
def _build_reuters_valuation_links(ticker: str) -> str:
    """Build Reuters valuation links for a ticker."""
    base_url = "https://www.reuters.com/markets/companies"
    ticker_upper = ticker.upper()
    return (
        f"Reuters Valuation: "
        f"[{ticker_upper}.O]({base_url}/{ticker_upper}.O/key-metrics/valuation) | "
        f"[{ticker_upper}.N]({base_url}/{ticker_upper}.N/key-metrics/valuation) | "
        f"[{ticker_upper}]({base_url}/{ticker_upper}/key-metrics/valuation)"
    )


async def _query_ticker(update: Update, ticker: str) -> None:
    """Query and respond with ticker information."""
    # ... existing code ...

    # After SEC Filings section, before reply_text:
    
    # Reuters Valuation link
    lines.append("")
    lines.append(_build_reuters_valuation_links(ticker))

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    # ... rest of function ...
```
