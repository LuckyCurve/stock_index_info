# 股票指数成分股查询系统 - 方案设计文档

## 1. 项目概述

### 1.1 功能目标

根据股票代码查询该股票所属的美股两大指数（S&P 500、NASDAQ 100），以及在各指数中的加入时间和持续时长。

### 1.2 示例

```
输入: AAPL
输出:
┌─────────────┬────────────┬──────────┬─────────┐
│ Index       │ Added Date │ Removed  │ Years   │
├─────────────┼────────────┼──────────┼─────────┤
│ S&P 500     │ 1982-11-30 │ -        │ 43 年   │
│ NASDAQ 100  │ 1985-01-31 │ -        │ 40 年   │
└─────────────┴────────────┴──────────┴─────────┘
```

---

## 2. 数据源

### 2.1 数据源选型

| 指数 | 数据源 | 类型 | 历史深度 | 可靠性 |
|------|--------|------|---------|--------|
| **S&P 500** | [Wikipedia](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies) | 网页爬虫 | 1976年至今 | ⭐⭐⭐⭐⭐ |
| **NASDAQ 100** | [Wikipedia](https://en.wikipedia.org/wiki/Nasdaq-100) | 网页爬虫 | 2007年至今 | ⭐⭐⭐⭐ |

### 2.2 数据源详情

#### S&P 500 - Wikipedia 爬虫

**页面**: https://en.wikipedia.org/wiki/List_of_S%26P_500_companies

**需要爬取的表格**:

1. **S&P 500 Component Stocks 表** - 当前成分股列表（**含 Date added 字段**）
   - 字段: Symbol, Security, GICS Sector, GICS Sub-Industry, Headquarters Location, Date added, CIK, Founded
   - 约 503 条记录

2. **Selected Changes to the List of S&P 500 Components 表** - 历史变更记录
   - 字段: Effective Date, Added (Ticker + Security), Removed (Ticker + Security), Reason
   - 数据从 1976 年至今，记录了 1,186+ 次成分股替换

**数据格式示例**:

当前成分股表:
| Symbol | Security | Date added | GICS Sector |
|--------|----------|------------|-------------|
| AAPL | Apple Inc. | 1982-11-30 | Information Technology |
| MSFT | Microsoft Corp. | 1994-06-01 | Information Technology |
| NVDA | NVIDIA Corp. | 2001-11-30 | Information Technology |

历史变更表:
| Effective Date | Added Ticker | Added Security | Removed Ticker | Removed Security | Reason |
|----------------|--------------|----------------|----------------|------------------|--------|
| May 19, 2025 | COIN | Coinbase | DFS | Discover Financial | 收购 |
| December 22, 2025 | HOOD | Robinhood | PARA | Paramount Global | 市值变化 |

**特殊情况**:
- 部分公司有两个股票类别（如 Alphabet 有 GOOGL 和 GOOG）
- 日期格式: 成分股表为 YYYY-MM-DD，变更表为 "Month DD, YYYY"

---

#### NASDAQ 100 - Wikipedia 爬虫

**页面**: https://en.wikipedia.org/wiki/Nasdaq-100

**需要爬取的表格**:

1. **Current components 表** - 获取当前成分股列表
   - 字段: Ticker, Company, ICB Industry, ICB Subsector
   - 约 102 条记录（含多类别股票如 GOOGL/GOOG）
   - 注意: 此表**不含加入时间**

2. **Component changes 表** - 获取历史变更记录
   - 字段: Date, Added (Ticker + Security), Removed (Ticker + Security), Reason
   - 数据从 2007 年至今

**变更原因类型**:
- Annual index reconstitution（年度重组，每年12月）
- Did not meet minimum monthly weight requirements（未达权重要求）
- Was acquired by [Company]（被收购）
- Transferred listing from NASDAQ to NYSE（转板）
- Was taken private（私有化）
- Spun off from [Company]（分拆）

**数据处理逻辑**:
```
1. 解析 Component changes 表
2. 对于每次变更记录:
   - Added 的股票: 记录 (ticker, added_date)
   - Removed 的股票: 更新 removed_date
3. 反向推算每只股票的加入时间
```

**特殊情况**:
- 多类别股票: Alphabet (GOOGL/GOOG)、Liberty Media 等
- 9家非美国注册公司（加拿大、爱尔兰、荷兰、英国、开曼群岛）
- 自1985年持续在列的股票: Apple、Costco、Intel、PACCAR

---

## 3. 技术架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────┐
│                  数据采集层                       │
├────────────────────────┬────────────────────────┤
│   S&P 500              │   NASDAQ 100           │
│   (Wiki Scraper)       │   (Wiki Scraper)       │
└────────────┬───────────┴───────────┬────────────┘
             │                       │
             ▼                       ▼
┌─────────────────────────────────────────────────┐
│                    数据转换层                      │
│   统一格式: (ticker, index, added_date, removed_date) │
└────────────────────────┬────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────┐
│                    数据存储层                      │
│                  SQLite / PostgreSQL              │
│    ┌─────────────┐    ┌──────────────┐    ┌─────────┐  │
│    │   stocks    │◄───│ constituents │───►│ indices │  │
│    │ (yfinance)  │    │  (成员关系)  │    │(指数定义)│  │
│    └─────────────┘    └──────────────┘    └─────────┘  │
└────────────────────────┬────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌───────────────┐  ┌─────────────┐  ┌───────────────┐
│    yfinance   │  │ 查询服务层  │  │  定时同步服务  │
│(行业信息补充) │  │CLI / REST API│  │(Wikipedia 爬虫)│
└───────────────┘  └─────────────┘  └───────────────┘
```

### 3.2 技术栈选型

**推荐: Python**

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 语言 | Python 3.11+ | 爬虫生态成熟 |
| HTTP 客户端 | requests / httpx | 下载 CSV 和网页 |
| HTML 解析 | BeautifulSoup4 + lxml | Wikipedia 表格解析 |
| 数据处理 | pandas | CSV 解析和数据转换 |
| 数据库 | SQLite | 轻量级，无需额外服务 |
| ORM | SQLAlchemy (可选) | 或直接用 sqlite3 |
| CLI | click / typer | 命令行界面 |
| API (可选) | FastAPI | REST API 服务 |
| 定时任务 | schedule / APScheduler | 数据自动更新 |

**备选: Go**

如需与现有 lucky-go 项目集成:
| 组件 | 技术选型 |
|------|---------|
| HTTP | net/http |
| HTML 解析 | goquery |
| CSV | encoding/csv |
| 数据库 | mattn/go-sqlite3 |
| CLI | cobra (已有) |

---

## 4. 数据模型

### 4.1 设计原则

由于两个数据源的行业分类标准不一致（S&P 500 使用 GICS，NASDAQ 100 使用 ICB），采用以下策略：

1. **成分股表 (`constituents`)** - 专注于指数成员关系，不存储行业信息
2. **股票信息表 (`stocks`)** - 独立存储股票基本信息，行业数据统一从 yfinance 获取
3. **行业信息懒加载** - 首次查询时从 yfinance 获取并缓存，或定期批量更新

### 4.2 数据库 Schema

```sql
-- 指数定义表
CREATE TABLE indices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(20) UNIQUE NOT NULL,  -- sp500, nasdaq100
    name VARCHAR(100) NOT NULL,         -- S&P 500, NASDAQ 100
    description TEXT
);

-- 初始数据
INSERT INTO indices (code, name) VALUES
    ('sp500', 'S&P 500'),
    ('nasdaq100', 'NASDAQ 100');

-- 股票基本信息表 (行业信息统一从 yfinance 获取)
CREATE TABLE stocks (
    ticker VARCHAR(20) PRIMARY KEY,     -- 股票代码
    company_name VARCHAR(200),          -- 公司名称
    sector VARCHAR(100),                -- 行业大类 (来自 yfinance)
    industry VARCHAR(200),              -- 细分行业 (来自 yfinance)
    exchange VARCHAR(20),               -- 交易所 (NYSE/NASDAQ)
    country VARCHAR(50),                -- 注册国家
    yfinance_updated_at TIMESTAMP,      -- yfinance 数据更新时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 成分股历史表 (专注于指数成员关系)
CREATE TABLE constituents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker VARCHAR(20) NOT NULL,        -- 股票代码
    index_code VARCHAR(20) NOT NULL,    -- 所属指数
    added_date DATE NOT NULL,           -- 加入日期
    removed_date DATE,                  -- 移除日期 (NULL = 当前成分)
    reason TEXT,                        -- 变更原因 (可选)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (ticker) REFERENCES stocks(ticker),
    FOREIGN KEY (index_code) REFERENCES indices(code),
    UNIQUE(ticker, index_code, added_date)  -- 防止重复
);

-- 索引优化
CREATE INDEX idx_constituents_ticker ON constituents(ticker);
CREATE INDEX idx_constituents_index_code ON constituents(index_code);
CREATE INDEX idx_constituents_current ON constituents(index_code, removed_date);
CREATE INDEX idx_stocks_sector ON stocks(sector);

-- 数据更新记录表
CREATE TABLE sync_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_code VARCHAR(20) NOT NULL,
    sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    records_count INTEGER,
    status VARCHAR(20),  -- success, failed
    error_message TEXT
);
```

### 4.3 yfinance 行业信息获取

```python
import yfinance as yf
from datetime import datetime
from typing import Optional, Tuple

def fetch_stock_info(ticker: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    从 yfinance 获取股票的行业信息
    
    Returns:
        (sector, industry, company_name) 或 (None, None, None) 如果获取失败
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return (
            info.get('sector'),        # 如: "Technology"
            info.get('industry'),      # 如: "Consumer Electronics"
            info.get('longName') or info.get('shortName')  # 公司全名
        )
    except Exception as e:
        print(f"Failed to fetch info for {ticker}: {e}")
        return (None, None, None)

def batch_update_stock_info(tickers: list[str], batch_size: int = 50, delay: float = 1.0):
    """
    批量更新股票行业信息
    
    Args:
        tickers: 股票代码列表
        batch_size: 每批处理数量
        delay: 批次间延迟（秒），避免触发速率限制
    """
    import time
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        for ticker in batch:
            sector, industry, name = fetch_stock_info(ticker)
            if sector or industry:
                # 更新数据库
                update_stock_in_db(ticker, sector, industry, name)
        
        if i + batch_size < len(tickers):
            time.sleep(delay)
```

### 4.4 数据示例

```
stocks 表:
┌────────┬──────────────────────┬─────────────────────┬──────────────────────────┬──────────┐
│ ticker │ company_name         │ sector              │ industry                 │ exchange │
├────────┼──────────────────────┼─────────────────────┼──────────────────────────┼──────────┤
│ AAPL   │ Apple Inc.           │ Technology          │ Consumer Electronics     │ NASDAQ   │
│ MSFT   │ Microsoft Corp.      │ Technology          │ Software-Infrastructure  │ NASDAQ   │
│ JPM    │ JPMorgan Chase & Co. │ Financial Services  │ Banks-Diversified        │ NYSE     │
│ JNJ    │ Johnson & Johnson    │ Healthcare          │ Drug Manufacturers       │ NYSE     │
└────────┴──────────────────────┴─────────────────────┴──────────────────────────┴──────────┘

constituents 表:
┌────┬────────┬────────────┬────────────┬──────────────┬─────────────────────┐
│ id │ ticker │ index_code │ added_date │ removed_date │ reason              │
├────┼────────┼────────────┼────────────┼──────────────┼─────────────────────┤
│ 1  │ AAPL   │ sp500      │ 1982-11-30 │ NULL         │ NULL                │
│ 2  │ AAPL   │ nasdaq100  │ 1985-01-31 │ NULL         │ NULL                │
│ 3  │ INTC   │ sp500      │ 1976-12-31 │ NULL         │ NULL                │
│ 4  │ INTC   │ nasdaq100  │ 1985-01-31 │ 2024-11-18   │ Annual reconstitution │
└────┴────────┴────────────┴────────────┴──────────────┴─────────────────────┘
```

### 4.5 查询示例

```sql
-- 查询某股票所属的所有指数及行业信息
SELECT 
    s.ticker,
    s.company_name,
    s.sector,
    s.industry,
    i.name AS index_name,
    c.added_date,
    c.removed_date,
    CASE WHEN c.removed_date IS NULL THEN 'Current' ELSE 'Former' END AS status,
    ROUND((JULIANDAY(COALESCE(c.removed_date, DATE('now'))) - JULIANDAY(c.added_date)) / 365.25, 1) AS years_in_index
FROM constituents c
JOIN stocks s ON c.ticker = s.ticker
JOIN indices i ON c.index_code = i.code
WHERE c.ticker = 'AAPL'
ORDER BY c.added_date;

-- 查询某行业在 S&P 500 中的所有当前成分股
SELECT s.ticker, s.company_name, s.industry, c.added_date
FROM constituents c
JOIN stocks s ON c.ticker = s.ticker
WHERE c.index_code = 'sp500' 
  AND c.removed_date IS NULL
  AND s.sector = 'Technology'
ORDER BY c.added_date;
```

---

## 5. 核心模块设计

### 5.1 项目结构

```
stock-index-query/
├── README.md
├── requirements.txt
├── config.py                 # 配置管理
├── main.py                   # 入口文件
│
├── scrapers/                 # 数据采集模块
│   ├── __init__.py
│   ├── base.py              # 基类定义
│   ├── sp500.py             # S&P 500 Wikipedia 爬虫
│   └── nasdaq100.py         # NASDAQ 100 Wikipedia 爬虫
│
├── enrichers/                # 数据补充模块
│   ├── __init__.py
│   └── yfinance_client.py   # yfinance 行业信息获取
│
├── models/                   # 数据模型
│   ├── __init__.py
│   └── database.py          # SQLite 操作
│
├── services/                 # 业务逻辑
│   ├── __init__.py
│   ├── sync.py              # 数据同步服务
│   └── query.py             # 查询服务
│
├── cli/                      # 命令行界面
│   ├── __init__.py
│   └── commands.py
│
├── api/                      # REST API (可选)
│   ├── __init__.py
│   └── routes.py
│
├── data/                     # 数据目录
│   └── indices.db           # SQLite 数据库文件
│
└── tests/                    # 测试
    ├── test_scrapers.py
    ├── test_yfinance.py
    └── test_query.py
```

### 5.2 核心类设计

```python
# scrapers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

@dataclass
class ConstituentRecord:
    """成分股记录"""
    ticker: str
    index_code: str
    added_date: date
    removed_date: Optional[date] = None
    company_name: Optional[str] = None
    reason: Optional[str] = None

class BaseScraper(ABC):
    """爬虫基类"""
    
    @property
    @abstractmethod
    def index_code(self) -> str:
        """指数代码"""
        pass
    
    @abstractmethod
    def fetch(self) -> List[ConstituentRecord]:
        """获取数据"""
        pass
```

```python
# scrapers/sp500.py
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from .base import BaseScraper, ConstituentRecord

class SP500Scraper(BaseScraper):
    """S&P 500 Wikipedia 爬虫"""
    
    WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    
    @property
    def index_code(self) -> str:
        return "sp500"
    
    def fetch(self) -> List[ConstituentRecord]:
        response = requests.get(self.WIKI_URL)
        soup = BeautifulSoup(response.text, 'lxml')
        records = []
        
        # 1. 解析当前成分股表格 (第一个wikitable)
        tables = soup.find_all('table', class_='wikitable')
        if tables:
            current_df = pd.read_html(str(tables[0]))[0]
            for _, row in current_df.iterrows():
                records.append(ConstituentRecord(
                    ticker=row['Symbol'],
                    index_code=self.index_code,
                    added_date=pd.to_datetime(row['Date added']).date(),
                    removed_date=None,
                    company_name=row['Security']
                ))
        
        # 2. 解析历史变更表格 (第二个wikitable)
        if len(tables) > 1:
            changes_df = pd.read_html(str(tables[1]))[0]
            for _, row in changes_df.iterrows():
                # 处理移除的股票
                if pd.notna(row.get('Removed', {}).get('Ticker')):
                    removed_date = self._parse_date(row['Date'])
                    # 更新或添加移除记录
                    # ... 具体实现
        
        return records
    
    def _parse_date(self, date_str: str) -> date:
        """解析 'Month DD, YYYY' 格式的日期"""
        return datetime.strptime(date_str, '%B %d, %Y').date()
```

```python
# scrapers/nasdaq100.py
import requests
from bs4 import BeautifulSoup
from .base import BaseScraper, ConstituentRecord

class NASDAQ100Scraper(BaseScraper):
    """NASDAQ 100 Wikipedia 爬虫"""
    
    WIKI_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
    
    @property
    def index_code(self) -> str:
        return "nasdaq100"
    
    def fetch(self) -> List[ConstituentRecord]:
        response = requests.get(self.WIKI_URL)
        soup = BeautifulSoup(response.text, 'lxml')
        
        records = []
        # 1. 解析 Component changes 表格
        # 2. 构建每只股票的加入/移除时间
        # ... 具体实现
        return records
```

```python
# services/query.py
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

@dataclass
class IndexMembership:
    """指数成员信息"""
    index_name: str
    index_code: str
    added_date: date
    removed_date: Optional[date]
    is_current: bool
    years_in_index: float

class QueryService:
    """查询服务"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def get_stock_indices(self, ticker: str) -> List[IndexMembership]:
        """查询股票所属的所有指数"""
        # SQL 查询实现
        pass
    
    def get_index_constituents(self, index_code: str, 
                                as_of_date: Optional[date] = None) -> List[str]:
        """查询指数在指定日期的成分股"""
        pass
```

---

## 6. API 设计

### 6.1 CLI 命令

```bash
# 同步数据
stock-index sync              # 同步所有指数
stock-index sync --index sp500  # 只同步 S&P 500

# 查询股票
stock-index query AAPL        # 查询 AAPL 所属指数
stock-index query AAPL --json # JSON 格式输出

# 查询指数成分
stock-index constituents sp500           # 当前成分股
stock-index constituents sp500 --date 2020-01-01  # 历史成分股
```

### 6.2 REST API (可选)

```
# 查询股票所属指数
GET /api/v1/stock/{ticker}/indices

Response:
{
  "ticker": "AAPL",
  "company_name": "Apple Inc.",
  "indices": [
    {
      "index_code": "sp500",
      "index_name": "S&P 500",
      "added_date": "1982-11-30",
      "removed_date": null,
      "is_current": true,
      "years_in_index": 43.0
    },
    {
      "index_code": "nasdaq100",
      "index_name": "NASDAQ 100",
      "added_date": "1985-01-31",
      "removed_date": null,
      "is_current": true,
      "years_in_index": 40.0
    }
  ]
}

# 查询指数当前成分股
GET /api/v1/index/{index_code}/constituents

# 查询指数历史成分股
GET /api/v1/index/{index_code}/constituents?date=2020-01-01

# 数据同步状态
GET /api/v1/sync/status
```

---

## 7. 实现步骤

### Phase 1: 基础框架 (Day 1)

| 步骤 | 任务 | 预计时间 |
|------|------|---------|
| 1.1 | 初始化项目结构，安装依赖 | 30 min |
| 1.2 | 实现数据库 Schema 和基础操作（含 stocks 表） | 1 hour |
| 1.3 | 实现 S&P 500 Wikipedia 爬虫 | 1.5 hours |
| 1.4 | 测试 S&P 500 数据入库和查询 | 30 min |

### Phase 2: NASDAQ 100 爬虫 (Day 1-2)

| 步骤 | 任务 | 预计时间 |
|------|------|---------|
| 2.1 | 实现 NASDAQ 100 Wikipedia 爬虫 | 3 hours |
| 2.2 | 数据清洗和验证 | 1 hour |

### Phase 3: yfinance 集成 (Day 2)

| 步骤 | 任务 | 预计时间 |
|------|------|---------|
| 3.1 | 实现 yfinance 行业信息获取模块 | 1 hour |
| 3.2 | 实现批量更新和缓存机制 | 1 hour |
| 3.3 | 测试行业信息获取（处理异常情况） | 30 min |

### Phase 4: 查询服务 (Day 2-3)

| 步骤 | 任务 | 预计时间 |
|------|------|---------|
| 4.1 | 实现 CLI 查询命令 | 1 hour |
| 4.2 | 实现格式化输出（表格/JSON） | 1 hour |
| 4.3 | 实现 REST API (可选) | 2 hours |

### Phase 5: 完善 (Day 3)

| 步骤 | 任务 | 预计时间 |
|------|------|---------|
| 5.1 | 添加定时同步机制 | 1 hour |
| 5.2 | 错误处理和日志 | 1 hour |
| 5.3 | 编写测试 | 2 hours |
| 5.4 | 文档完善 | 1 hour |

---

## 8. 依赖清单

### requirements.txt

```
# HTTP & Scraping
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.0.0

# Data Processing
pandas>=2.0.0

# Stock Data (行业信息)
yfinance>=0.2.40

# Database
# SQLite 内置，无需额外依赖

# CLI
click>=8.1.0
rich>=13.0.0  # 美化终端输出

# API (可选)
fastapi>=0.109.0
uvicorn>=0.27.0

# Scheduling (可选)
schedule>=1.2.0

# Development
pytest>=8.0.0
black>=24.0.0
```

---

## 9. 注意事项

### 9.1 数据局限性

| 指数 | 局限性 |
|------|--------|
| S&P 500 | Wikipedia 变更记录从 1976 年开始，更早的历史数据不完整；当前成分股表有完整的 Date added 字段 |
| NASDAQ 100 | Wikipedia 变更记录从 2007 年开始，更早数据需要反推；当前成分股表不含加入时间 |

### 9.2 股票代码变更

部分公司可能经历过代码变更（如 Facebook → Meta: FB → META），需要考虑:
- 维护代码映射表
- 或在查询时支持历史代码

### 9.3 爬虫礼仪

- 设置合理的请求间隔
- 添加 User-Agent 标识
- 缓存页面内容，避免频繁请求

### 9.4 数据更新频率

| 指数 | 建议更新频率 |
|------|-------------|
| S&P 500 | 每周一次 |
| NASDAQ 100 | 每月一次（年度重组在 12 月） |

---

## 10. 扩展可能

1. **支持更多指数**: Russell 1000/2000, FTSE 100, 沪深 300 等
2. **公司信息补充**: 集成 Yahoo Finance API 获取公司详情
3. **历史价格关联**: 记录加入/移除时的股价表现
4. **通知功能**: 成分股变更时推送通知
5. **可视化**: Web 界面展示指数成分变化历史

---

## 附录 A: Wikipedia 表格解析示例

### S&P 500 Wikipedia 表解析

```python
def parse_sp500_current_components(soup: BeautifulSoup) -> List[dict]:
    """解析 S&P 500 当前成分股表格"""
    tables = soup.find_all('table', class_='wikitable')
    
    # 第一个表格是当前成分股
    if not tables:
        return []
    
    # 使用 pandas 解析表格更方便
    df = pd.read_html(str(tables[0]))[0]
    results = []
    for _, row in df.iterrows():
        results.append({
            'symbol': row['Symbol'],
            'security': row['Security'],
            'gics_sector': row['GICS Sector'],
            'date_added': row['Date added'],  # 格式: YYYY-MM-DD
            'cik': row['CIK'],
        })
    return results

def parse_sp500_changes(soup: BeautifulSoup) -> List[dict]:
    """解析 S&P 500 历史变更表格"""
    tables = soup.find_all('table', class_='wikitable')
    
    # 第二个表格是变更记录
    if len(tables) < 2:
        return []
    
    df = pd.read_html(str(tables[1]))[0]
    changes = []
    for _, row in df.iterrows():
        changes.append({
            'effective_date': row[('Date', 'Date')],  # 格式: "Month DD, YYYY"
            'added_ticker': row[('Added', 'Ticker')],
            'added_security': row[('Added', 'Security')],
            'removed_ticker': row[('Removed', 'Ticker')],
            'removed_security': row[('Removed', 'Security')],
            'reason': row[('Reason', 'Reason')],
        })
    return changes
```

### NASDAQ 100 Component Changes 表解析

```python
def parse_nasdaq100_changes(soup: BeautifulSoup) -> List[dict]:
    """解析 NASDAQ 100 变更历史表格"""
    # 找到 "Component changes" 或 "Historical changes" 表格
    # 表格结构: Date | Added | Removed | Reason
    
    changes = []
    # ... 具体解析逻辑
    return changes
```

---

## 附录 B: 数据验证检查清单

- [ ] AAPL 在两大指数中都有记录
- [ ] VICI 在 S&P 500 中，加入时间为 2022-06-08
- [ ] 当前 S&P 500 成分股数量约 500
- [ ] 当前 NASDAQ 100 成分股数量约 100
