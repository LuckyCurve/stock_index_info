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
├── bot.py           # Telegram Bot 主入口和命令处理
├── config.py        # 环境变量和配置管理
├── db.py            # SQLite 数据库操作
├── models.py        # 数据模型 (ConstituentRecord, IndexMembership)
└── scrapers/        # 数据抓取模块
    ├── base.py      # BaseScraper 抽象基类
    ├── sp500.py     # S&P 500 Wikipedia 抓取器
    └── nasdaq100.py # NASDAQ 100 Wikipedia 抓取器
```

### 核心模块说明

- **bot.py**: 使用 python-telegram-bot 库，包含命令处理器 (`/query`, `/sync`, `/status` 等)、定时同步任务、和 `@restricted` 装饰器用于用户权限控制
- **scrapers/**: 继承 `BaseScraper` 抽象基类，使用 `curl_cffi` 抓取 Wikipedia 页面，`pandas` 解析 HTML 表格
- **db.py**: SQLite 数据库操作，constituents 表存储股票指数成分股历史记录
- **models.py**: `ConstituentRecord` 用于存储抓取数据，`IndexMembership` 用于查询结果展示

### 数据流

1. `Scraper.fetch()` -> 从 Wikipedia 抓取并解析数据，返回 `ConstituentRecord` 列表
2. `insert_constituent()` -> 存储到 SQLite (INSERT OR IGNORE 处理重复)
3. `get_stock_memberships()` / `get_index_constituents()` -> 查询数据返回给用户

### 测试

测试使用 pytest-asyncio (异步测试) 和 pytest fixtures (`temp_db`, `db_connection`)。conftest.py 定义了共享 fixtures。
