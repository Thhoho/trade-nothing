# Data Acquisition & Governance Protocol (v7.0)

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
