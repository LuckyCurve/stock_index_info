# CODEBUDDY.md

This file provides guidance to CodeBuddy Code when working with code in this repository.

## 项目结构

项目整体使用 src layout

## 依赖管理

使用 uv 进行依赖管理, 禁止使用 python 和 pip 命令, 包括 uv pip 和 uv python 等

## 常用命令

```bash
# 安装依赖
uv sync

# 运行 bot
TELEGRAM_BOT_TOKEN=<token> ALLOWED_USER_IDS=<id> uv run stock-index-bot

# 运行测试
uv run pytest -v

# 运行单个测试文件
uv run pytest tests/test_db.py -v

# 运行单个测试函数
uv run pytest tests/test_db.py::test_insert_constituent -v

# 类型检查
uv run mypy src/

# 代码检查
uv run ruff check src/ tests/
```

## 代码质量检查

每次修改代码后，必须运行以下检查：

```bash
# 代码格式和 lint 检查
uv run ruff check src/ tests/

# 类型检查
uv run mypy src/
```

## 代码架构

```
src/stock_index_info/
├── alpha_vantage.py  # Alpha Vantage API 客户端，获取历史年度净利润数据；使用 yfinance 获取市值；计算7年平均市盈率 (市值/7年平均净利润)
├── balance_sheet.py  # 资产负债表数据获取，计算 NTA (净有形资产) 和 NCAV (净流动资产价值) 估值指标
├── bot.py            # Telegram Bot 主入口和命令处理
├── config.py         # 环境变量和配置管理
├── db.py             # SQLite 数据库操作
├── exchange_rate.py  # 汇率转换工具，从 open.er-api.com 获取汇率，将外币净利润转换为 USD
├── models.py         # 数据模型 (ConstituentRecord, IndexMembership, SECFilingRecord, RecentFilings, IncomeRecord, CachedIncome, PEResult, BalanceSheetRecord, CachedBalanceSheet, AssetValuationResult)
├── sec_edgar.py      # SEC EDGAR API 客户端，获取 10-Q/10-K 报告链接
└── scrapers/         # 数据抓取模块
    ├── base.py       # BaseScraper 抽象基类
    ├── sp500.py      # S&P 500 Wikipedia 抓取器
    └── nasdaq100.py  # NASDAQ 100 Wikipedia 抓取器

scripts/
└── export_csv.py    # 导出成分股数据到 CSV 文件

data/
├── sp500.csv        # S&P 500 成分股 CSV 数据
└── nasdaq100.csv    # NASDAQ 100 成分股 CSV 数据
```

### 核心模块说明

- **bot.py**: 使用 python-telegram-bot 库，包含命令处理器 (`/query`, `/sync`, `/status` 等)、定时同步任务、和 `@restricted` 装饰器用于用户权限控制
- **scrapers/**: 继承 `BaseScraper` 抽象基类，使用 `curl_cffi` 抓取 Wikipedia 页面，`pandas` 解析 HTML 表格
- **db.py**: SQLite 数据库操作，constituents 表存储股票指数成分股历史记录
- **models.py**: `ConstituentRecord` 用于存储抓取数据，`IndexMembership` 用于查询结果展示 (包含 `is_current` 和 `years_in_index` 计算属性)，`SECFilingRecord` 和 `RecentFilings` 用于 SEC 报告查询结果，`IncomeRecord` 和 `CachedIncome` 用于净利润缓存，`PEResult` 用于7年平均市盈率计算结果
- **sec_edgar.py**: SEC EDGAR API 客户端，提供 `get_cik_from_ticker()`、`get_latest_10q()` 和 `get_recent_filings()` 函数，用于获取公司的季报(10-Q)和年报(10-K)链接
- **alpha_vantage.py**: Alpha Vantage API 客户端，获取历史年度净利润数据；使用 yfinance 获取市值；计算7年平均市盈率 (市值/7年平均净利润)。`get_7year_pe()` 函数使用缓存策略，当有新的 SEC filing 时自动刷新缓存
- **balance_sheet.py**: 资产负债表数据获取和估值计算。`fetch_balance_sheet()` 从 Alpha Vantage 获取资产负债表数据，`calculate_asset_valuation()` 计算 NTA 和 NCAV，`get_asset_valuation()` 是带缓存的入口函数。NTA = 总资产 - 总负债 - 商誉 - 无形资产；NCAV = 流动资产 - 总负债
- **exchange_rate.py**: 汇率转换工具，从 open.er-api.com 获取汇率 (24小时缓存)。用于将非 USD 报告的净利润转换为 USD。主要函数: `convert_to_usd()`、`get_exchange_rates()`

### 数据库 Schema

```sql
CREATE TABLE constituents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    index_code TEXT NOT NULL CHECK (index_code IN ('sp500', 'nasdaq100')),
    added_date TEXT,  -- 可为 NULL
    removed_date TEXT,
    reason TEXT,
    UNIQUE(ticker, index_code, added_date)
);
-- 索引: idx_constituents_ticker, idx_constituents_index

CREATE TABLE income_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    net_income REAL NOT NULL,  -- 净利润 (已转换为 USD)
    last_updated TEXT NOT NULL,
    UNIQUE(ticker, fiscal_year)
);
-- 索引: idx_income_statements_ticker

CREATE TABLE balance_sheets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    total_assets REAL NOT NULL,
    total_liabilities REAL NOT NULL,
    total_current_assets REAL NOT NULL,
    goodwill REAL NOT NULL,
    intangible_assets REAL NOT NULL,
    last_updated TEXT NOT NULL,
    UNIQUE(ticker, fiscal_year)
);
-- 索引: idx_balance_sheets_ticker
```

支持的 `index_code` 值定义在 `models.py` 的 `INDEX_NAMES` 字典中。

### 数据流

1. `Scraper.fetch()` -> 从 Wikipedia 抓取并解析数据，返回 `ConstituentRecord` 列表
2. `insert_constituent()` -> 存储到 SQLite (INSERT OR IGNORE 处理重复)
3. `get_stock_memberships()` / `get_index_constituents()` -> 查询数据返回给用户

**P/E 计算数据流:**
1. `get_recent_filings()` -> 获取最新 SEC filing 日期用于缓存失效判断
2. `get_7year_pe()` -> 检查缓存是否需要刷新，调用 `fetch_annual_net_income()` 获取数据
3. `fetch_annual_net_income()` -> 从 Alpha Vantage 获取净利润，使用 `convert_to_usd()` 转换货币
4. `get_market_cap()` -> 从 yfinance 获取市值 (失败时回退到 Alpha Vantage)
5. `calculate_7year_avg_pe()` -> 计算 P/E = 市值 / 7年平均净利润

**NTA/NCAV 计算数据流:**
1. `get_asset_valuation()` -> 带缓存入口，检查缓存是否过期 (基于 latest_filing_date)
2. `fetch_balance_sheet()` -> 从 Alpha Vantage BALANCE_SHEET API 获取资产负债表
3. `calculate_asset_valuation()` -> 计算 NTA 和 NCAV，以及 P/NTA 和 P/NCAV 比率

### 同步策略

同步采用 "全量更新" 策略：先删除该指数的所有数据 (`delete_index_data`)，再重新插入抓取的数据。这确保数据与 Wikipedia 保持一致，避免累积脏数据。

### 添加新指数

1. 在 `models.py` 的 `INDEX_NAMES` 添加新的 index_code 映射
2. 更新 `db.py` 中 `SCHEMA` 的 CHECK 约束
3. 创建新的 scraper 文件，继承 `BaseScraper` 并实现 `index_code`、`index_name`、`fetch()` 方法
4. 在 `bot.py` 的 `_do_sync()` 和 `/constituents` 命令中注册新 scraper

### 测试

测试使用 pytest-asyncio (异步测试) 和 pytest fixtures (`temp_db`, `db_connection`)。conftest.py 定义了共享 fixtures。

## 脚本工具

```bash
# 导出 S&P 500 和 NASDAQ 100 成分股数据到 CSV
uv run python scripts/export_csv.py
```

导出的 CSV 文件保存在 `data/` 目录，字段: `ticker`, `company_name`, `added_date`, `removed_date`

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `TELEGRAM_BOT_TOKEN` | 是 | BotFather 提供的 bot token |
| `ALLOWED_USER_IDS` | 是 | 允许使用的 Telegram 用户 ID (逗号分隔) |
| `SYNC_HOUR` | 否 | 每日同步时间 (0-23, 默认 2) |
| `SYNC_MINUTE` | 否 | 每日同步分钟 (0-59, 默认 0) |
| `ALPHA_VANTAGE_API_KEY` | 否 | Alpha Vantage API key (7年平均P/E功能需要) |
