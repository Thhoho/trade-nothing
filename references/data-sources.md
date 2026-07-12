# Data Acquisition & Governance Protocol (v0.9)

Defines data acquisition paths and priorities for all research workflows.

## 1. Data Priority Matrix

| Data Type | Recommended Tool | Priority | Notes |
|-----------|-----------------|----------|-------|
| **Fact Anchors** | `Vault/Facts/*.md` | **P0** | Human-verified hard facts |
| **A-Share Quotes/Valuation** | `scripts/fetch_akshare.py --code XX` | **P1** | Tencent→AkShare multi-source fallback |
| **Macro Hard Constraints** | `scripts/verified_fetcher.py --all` | **P1** | Oil/Rates/VIX/FX |
| **Financial Data** | `scripts/fetch_akshare.py --code XX --financial` | **P1** | EM `stock_financial_analysis_indicator_em` sorted by latest report |
| **Consensus Distance** | `scripts/consensus_distance.py --code XX` | **P2** | Quantify deviation from market expectations |
| **Catalyst Calendar** | `scripts/catalyst_calendar.py --sector XX` | **P2** | Macro/sector event calendar |
| **Scenario Matrix** | `scripts/scenario_matrix.py --demo` | **P2** | Structured scenario analysis |
| **Company Filings** | Local Vault search → WebSearch | **P2** | Local first |
| **Industry News** | WebSearch | **P3** | Market sentiment |
| **Research Reports** | WebSearch | **P3** | For consensus alignment only |

## 2. Tool Quick Reference

```bash
# A-share real-time quotes
python3 scripts/fetch_akshare.py --code 300118

# A-share quotes + financial data
python3 scripts/fetch_akshare.py --code 300118 --financial

# A-share quotes + global macro linkage
python3 scripts/fetch_akshare.py --code 300118 --macro GC=F

# All macro indicators at once
python3 scripts/verified_fetcher.py --all

# Single macro indicator
python3 scripts/verified_fetcher.py --indicator BRENT_OIL

# Consensus distance calculation
python3 scripts/consensus_distance.py --code 300118 --target 25.0

# Catalyst calendar (sector-level)
python3 scripts/catalyst_calendar.py --sector solar

# Catalyst calendar (stock-level)
python3 scripts/catalyst_calendar.py --code 300118

# Catalyst calendar (global macro)
python3 scripts/catalyst_calendar.py --macro

# Scenario matrix demo
python3 scripts/scenario_matrix.py --demo

# Logic radar one-shot check
python3 scripts/logic_radar_v2.py

# Logic radar daemon
python3 scripts/logic_radar_daemon.py --interval 300

# DeepThink countdown timer
python3 scripts/deepthink_timer.py --duration 30

# Polymarket prediction market data
python3 scripts/fetch_polymarket.py --query "China"
```

## 3. Registered Macro Indicators

| Code | Name | Source | Radar Hook | Threshold |
|------|------|--------|------------|-----------|
| `US_10Y` | US 10Y Treasury Yield | AkShare → YahooFinance | Radar_002 | > 4.8% |
| `BRENT_OIL` | Brent Crude Oil | AkShare → YahooFinance | Radar_001 | > 95 USD |
| `VIX` | CBOE Volatility Index | YahooFinance | Radar_004 | > 30 |
| `USDCNY` | USD/CNY Exchange Rate | YahooFinance | Radar_003 | > 7.35 |
| `GOLD` | Gold Spot | YahooFinance | — | — |

## 4. Fallback & Circuit Breaker Logic

If a P1-level script fails (Exit Code != 0), **must** cascade:

1. **Fall back to local cache**: Search `Vault/Research_Log` for conclusions within 30 days.
2. **Fall back to structured search**:
   - **Never** ask "what is the stock price of XXX" directly.
   - **Must** use structured query templates (see below).
3. **Circuit breaker warning**: If ultimately using WebSearch for quantitative data, the report **must** include `[⚠️ Data Confidence Warning: Source is web search, not API-verified]`.

## 5. Structured Search Query Templates

| Scenario | Query Template |
|----------|---------------|
| Price/Valuation | `[code] 实时股价 估值 动态PE site:xueqiu.com` |
| Financial Summary | `[code] [year]年报 净利润 ROE site:dfcfw.com` |
| Production Capacity | `[code] [tech] 产能规划 投产进度 site:jiemian.com` |
| Consensus Estimates | `[code] 一致预期 目标价 EPS site:xueqiu.com` |
| Institutional Holdings | `[code] 机构持仓 基金重仓 site:eastmoney.com` |
| Insider Activity | `[code] 高管增减持 大股东质押 site:cninfo.com.cn` |


## 6. Pluggable Global Data Provider Gateway (v6.0)

Trade Nothing v6.0 integrates an object-oriented, Open-Closed Principle (OCP) compliant global data gateway in [data_providers.py](file:///Users/xiaweiqi/Documents/trade-nothing/scripts/data_providers.py). This gateway dynamically routes queries to standard free sources (Yahoo Finance, Tencent, Sina, NetEase) or commercial APIs, and provides two highly convenient ways to plug in new custom data feeds.

### 6.1 Unified Data Interface (`BaseDataProvider`)
All data providers inherit from `BaseDataProvider` and return a standardized dictionary format:
```python
from data_providers import BaseDataProvider, GLOBAL_DATA_GATEWAY

class CustomProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "My_Custom_Source"

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        # Perform HTTP requests or API calls
        return {
            "symbol": symbol,
            "name": "Asset Name",
            "price": 123.45,
            "currency": "USD",
            "source": self.name
        }

# Programmatic registration
GLOBAL_DATA_GATEWAY.register(CustomProvider())
```

### 6.2 Zero-Code Custom REST APIs (`custom_providers.json`)
You can add any HTTP JSON API as a data source without writing a single line of Python code. Simply create `scripts/custom_providers.json` with the following structure:
```json
[
  {
    "name": "Coingecko_Crypto",
    "url_template": "https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd",
    "symbol_pattern": "^[a-z\\-]+$",
    "headers": {
      "Accept": "application/json",
      "Authorization": "Bearer ${COINGECKO_API_KEY}"
    },
    "price_path": "{symbol}.usd",
    "currency": "USD"
  }
]
```
- **`url_template`**: The URL endpoint containing `{symbol}` which is dynamically replaced at runtime.
- **`symbol_pattern`**: A regular expression determining which symbols are routed to this provider (e.g. only matching lowercase tickers for crypto).
- **`headers`**: Optional headers. Any string like `${ENV_VAR}` or `$ENV_VAR` will automatically resolve to the system environment variable at query time.
- **`price_path`**: A dotted path (e.g. `data.ticker.price` or `{symbol}.usd`) used to traverse the parsed JSON response and extract the float value.

### 6.3 Dynamic Python Plugins (`scripts/plugins/`)
For complex authentication or proprietary APIs, drop any `.py` file into the `scripts/plugins/` directory. 

The system automatically scans the directory on startup, dynamically imports the module, discovers any class inheriting from `BaseDataProvider`, instantiates it, and registers it.

Example dynamic plugin file `scripts/plugins/prop_api.py`:
```python
import requests
from data_providers import BaseDataProvider

class ProprietaryApiProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "Proprietary_Trading_API"

    def fetch_quote(self, symbol: str):
        # Implement proprietary socket/HTTP fetching logic
        ...
```


## 7. Autonomous Daemon REST API Specifications (v7.0)

Trade Nothing v7.0 introduces a standing, zero-dependency REST API daemon server running on port `8000`. This enables cloud deployment and automated TradingView webhook triggers.

### 7.1 GET `/api/status`
Returns server health status, current cash balances (CNY and USD), and all active or completed background research debate processes.
*   **Response Payload**:
    ```json
    {
      "status": "UP",
      "timestamp": 1716654812.23,
      "portfolio_summary": {
        "cash": {
          "CNY": 1000000.0,
          "USD": 100000.0
        },
        "holdings": {},
        "transactions": []
      },
      "active_research_sessions": {}
    }
    ```

### 7.2 POST `/api/research/start`
Triggers an asynchronous 3-round background research debate simulation, which automatically executes the Kelly Sizing order on the simulated portfolio ledger once it converges.
*   **Request Payload**:
    ```json
    {
      "symbol": "300118",
      "target_price": 25.0,
      "fractional": 0.25
    }
    ```

### 7.3 POST `/api/webhook/tradingview`
Standard webhook listener for automated alerts from TradingView charts or other screening engines.
*   **Dynamic Dual Mode**:
    *   **Direct Sizing Execution**: If `posterior` and `lfi` are passed in the JSON alert payload, the Kelly transaction is calculated and executed immediately.
    *   **Deferred Debate Verification**: If only `ticker` and `target_price` are sent, the server spawns an asynchronous background research debate thread first, executing Kelly order sizing once it successfully converges.
*   **Request Payload Example**:
    ```json
    {
      "ticker": "AAPL",
      "price": 182.50,
      "action": "BUY",
      "target_price": 220.0,
      "posterior": 0.85,
      "lfi": 0.08
    }
    ```
```
