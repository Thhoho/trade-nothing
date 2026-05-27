"""
Trade Nothing v0.9.3 — Pluggable Global Data Provider Gateway

Provides an Object-Oriented, Open-Closed Principle (OCP) compliant architecture
allowing developers to easily plug in new domestic, global, or commercial data sources.
"""

import os
import re
import sys
import json
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

# Utility safe boundary parsers
def safe_float(val, default=None):
    if val is None:
        return default
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default

def safe_get(lst, idx, default=None):
    try:
        return lst[idx] if idx < len(lst) else default
    except (IndexError, TypeError):
        return default


class BaseDataProvider(ABC):
    """Abstract Base Class defining the standard interface for all data providers"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def fetch_quote(self, symbol: str) -> Optional[dict]:
        """
        Fetches real-time quote for a stock.
        Returns a standardized dictionary:
        {
            "symbol": str,
            "name": str,
            "price": float,
            "pe_dynamic": Optional[float],
            "turnover_rate": Optional[float],
            "market_cap_billions": Optional[float],
            "currency": str,
            "source": str
        }
        or None if failed.
        """
        pass

    def fetch_fundamental(self, symbol: str) -> Optional[dict]:
        """Optional: Fetches fundamental metrics (e.g. EPS forecasts)"""
        return None


# ─── Domestic A-Share Providers (Tencent, Sina, NetEase) ───

class TencentAShareProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "Tencent_HQ"

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        if not re.match(r"^\d{6}$", symbol):
            return None  # Only handles 6-digit A-share symbols
            
        full_symbol = f"sz{symbol}" if symbol.startswith(('00', '30')) else f"sh{symbol}"
        url = f"http://qt.gtimg.cn/q={full_symbol}"
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)"
        
        try:
            resp = requests.get(url, headers={"User-Agent": ua}, timeout=5)
            data = resp.text.split('~')
            if len(data) > 39:
                price = safe_float(safe_get(data, 3))
                if price is not None:
                    market_cap_raw = safe_float(safe_get(data, 45))
                    return {
                        "symbol": symbol,
                        "name": safe_get(data, 1, "Unknown"),
                        "price": price,
                        "pe_dynamic": safe_float(safe_get(data, 39)),
                        "turnover_rate": safe_float(safe_get(data, 38)),
                        "market_cap_billions": market_cap_raw / 10.0 if market_cap_raw is not None else None,
                        "currency": "CNY",
                        "source": self.name
                    }
        except Exception:
            pass
        return None


class SinaAShareProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "Sina_Finance"

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        if not re.match(r"^\d{6}$", symbol):
            return None
            
        full_symbol = f"sz{symbol}" if symbol.startswith(('00', '30')) else f"sh{symbol}"
        url = f"http://hq.sinajs.cn/list={full_symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X)",
            "Referer": "https://finance.sina.com.cn"
        }
        
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            match = re.search(r'="([^"]+)"', resp.text)
            if match:
                data = match.group(1).split(',')
                if len(data) > 10:
                    price = safe_float(safe_get(data, 3))
                    if price is not None:
                        return {
                            "symbol": symbol,
                            "name": safe_get(data, 0, "Unknown"),
                            "price": price,
                            "pe_dynamic": None,
                            "turnover_rate": None,
                            "market_cap_billions": None,
                            "currency": "CNY",
                            "source": self.name
                        }
        except Exception:
            pass
        return None


class NetEaseAShareProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "NetEase_Finance"

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        if not re.match(r"^\d{6}$", symbol):
            return None
            
        netease_symbol = ("1" if symbol.startswith(('00', '30')) else "0") + symbol
        url = f"http://api.money.126.net/data/feed/{netease_symbol},money.api"
        
        try:
            resp = requests.get(url, timeout=5)
            match = re.search(r'\{.*\}', resp.text)
            if match:
                json_data = json.loads(match.group(0))
                stock_data = json_data.get(netease_symbol, {})
                price = safe_float(stock_data.get("price"))
                if price is not None:
                    market_cap_raw = safe_float(stock_data.get("TCAP"))
                    return {
                        "symbol": symbol,
                        "name": stock_data.get("name", "Unknown"),
                        "price": price,
                        "pe_dynamic": safe_float(stock_data.get("pe")),
                        "turnover_rate": safe_float(stock_data.get("turnover")) * 100 if stock_data.get("turnover") is not None else None,
                        "market_cap_billions": market_cap_raw / 1e9 if market_cap_raw is not None else None,
                        "currency": "CNY",
                        "source": self.name
                    }
        except Exception:
            pass
        return None


# ─── Free Global Providers (Yahoo Finance) ───

class YahooFinanceGlobalProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "Yahoo_Finance"

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        # Formulate query symbol (Tencent/Sina needs 6 digits, Yahoo needs suffix, e.g. 300118.SZ or US tickers like AAPL)
        query_sym = symbol
        currency_default = "USD"
        if re.match(r"^\d{6}$", symbol):
            # A-shares fallback
            query_sym = f"{symbol}.SZ" if symbol.startswith(('00', '30')) else f"{symbol}.SS"
            currency_default = "CNY"
        elif re.match(r"^\d{4}$", symbol):
            # HK shares fallback (e.g. 0700 -> 0700.HK)
            query_sym = f"{symbol}.HK"
            currency_default = "HKD"

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{query_sym}"
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                json_data = resp.json()
                result = safe_get(json_data.get("chart", {}).get("result", []), 0)
                if result:
                    meta = result.get("meta", {})
                    price = safe_float(meta.get("regularMarketPrice"))
                    if price is not None:
                        currency = meta.get("currency", currency_default)
                        symbol_name = meta.get("symbol", symbol)
                        return {
                            "symbol": symbol,
                            "name": symbol_name,
                            "price": price,
                            "pe_dynamic": None, # /chart does not contain PE
                            "turnover_rate": None,
                            "market_cap_billions": None,
                            "currency": currency,
                            "source": self.name
                        }
        except Exception:
            pass
        return None


# ─── Commercial Global Providers (Alpha Vantage & Tiingo) ───

class AlphaVantageCommercialProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "Alpha_Vantage_Commercial"

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
        if not api_key:
            return None  # Bypass if no api key configured

        # Alpha Vantage uses standard tickers (e.g. AAPL, or 300118.SHZ)
        query_sym = symbol
        if re.match(r"^\d{6}$", symbol):
            query_sym = f"{symbol}.BJS" if symbol.startswith('8') else (f"{symbol}.SZS" if symbol.startswith(('00', '30')) else f"{symbol}.SHG")

        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={query_sym}&apikey={api_key}"
        
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                json_data = resp.json()
                quote = json_data.get("Global Quote", {})
                if quote:
                    price = safe_float(quote.get("05. price"))
                    if price is not None:
                        return {
                            "symbol": symbol,
                            "name": quote.get("01. symbol", symbol),
                            "price": price,
                            "pe_dynamic": None,
                            "turnover_rate": None,
                            "market_cap_billions": None,
                            "currency": "USD",  # Default US/global focus
                            "source": self.name
                        }
        except Exception:
            pass
        return None


class TiingoCommercialProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "Tiingo_Commercial"

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        api_key = os.environ.get("TIINGO_API_KEY", "").strip()
        if not api_key:
            return None

        # Tiingo is primarily focus on US/Global tickers
        url = f"https://api.tiingo.com/tiingo/daily/{symbol}/prices"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Token {api_key}"
        }
        
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                json_data = resp.json()
                latest = safe_get(json_data, 0)
                if latest:
                    # Tiingo returns close price
                    price = safe_float(latest.get("close"))
                    if price is not None:
                        return {
                            "symbol": symbol,
                            "name": symbol,
                            "price": price,
                            "pe_dynamic": None,
                            "turnover_rate": None,
                            "market_cap_billions": None,
                            "currency": "USD",
                            "source": self.name
                        }
        except Exception:
            pass
        return None


class AkShareProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "AkShare_Finance"

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        # AkShare handles A-shares 6-digit symbols
        if not re.match(r"^\d{6}$", symbol):
            return None

        try:
            # Inline import for soft-fail portability
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                row = df[df['代码'] == symbol]
                if not row.empty:
                    r = row.iloc[0]
                    price = safe_float(r.get("最新价"))
                    if price is not None:
                        market_cap_raw = safe_float(r.get("总市值"))
                        return {
                            "symbol": symbol,
                            "name": r.get("名称", "Unknown"),
                            "price": price,
                            "pe_dynamic": safe_float(r.get("市盈率-动态")),
                            "turnover_rate": safe_float(r.get("换手率")),
                            "market_cap_billions": market_cap_raw / 1e8 if market_cap_raw is not None else None,
                            "currency": "CNY",
                            "source": self.name
                        }
        except Exception:
            pass
        return None

    def fetch_fundamental(self, symbol: str) -> Optional[dict]:
        if not re.match(r"^\d{6}$", symbol):
            return None

        # Build EastMoney style symbol (e.g. 300118.SZ or 600000.SH)
        if symbol.startswith(("00", "30")):
            em_symbol = f"{symbol}.SZ"
        elif symbol.startswith(("60", "68")):
            em_symbol = f"{symbol}.SH"
        else:
            em_symbol = f"{symbol}.SZ"

        try:
            import akshare as ak
            df = ak.stock_financial_analysis_indicator_em(symbol=em_symbol, indicator="按报告期")
            if df is not None and not df.empty and "REPORT_DATE" in df.columns:
                df = df.sort_values("REPORT_DATE", ascending=False)
                r = df.iloc[0]
                
                def _fmt_date(v):
                    if v is None or str(v) == "nan":
                        return None
                    if hasattr(v, "strftime"):
                        return v.strftime("%Y-%m-%d")
                    return str(v)[:10]

                return {
                    "em_symbol": em_symbol,
                    "report_date": _fmt_date(r.get("REPORT_DATE")),
                    "notice_date": _fmt_date(r.get("NOTICE_DATE")),
                    "parent_net_profit": safe_float(r.get("PARENTNETPROFIT")),
                    "parent_net_profit_yoy_pct": safe_float(r.get("PARENTNETPROFITTZ")),
                    "total_operating_revenue": safe_float(r.get("TOTALOPERATEREVE")),
                    "revenue_yoy_pct": safe_float(r.get("TOTALOPERATEREVETZ")),
                    "basic_eps": safe_float(r.get("EPSJB")),
                    "roe_pct": safe_float(r.get("ROEJQ")),
                    "debt_to_asset_pct": safe_float(r.get("ZCFZL")),
                    "source": self.name
                }
        except Exception:
            pass
        return None


class PolymarketProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "Polymarket_Prediction_Market"

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        # Polymarket handles narrative/prediction markets. Bypass if A-share numeric symbol
        if re.match(r"^\d{6}$", symbol):
            return None

        query = symbol.replace("_", " ").strip()
        query_lower = query.lower()
        url = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=100"
        
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                events = resp.json()
                for event in events:
                    title = event.get('title', '')
                    if query_lower in title.lower():
                        markets = event.get('markets', [])
                        for market in markets:
                            if market.get('active'):
                                raw_prices = market.get('outcomePrices', '[]')
                                prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
                                try:
                                    prob = float(prices[0]) if prices else None
                                except Exception:
                                    prob = None
                                    
                                if prob is not None:
                                    volume = safe_float(market.get('volume', 0.0))
                                    return {
                                        "symbol": symbol,
                                        "name": title,
                                        "price": prob,
                                        "pe_dynamic": None,
                                        "turnover_rate": None,
                                        "market_cap_billions": volume / 1e9 if volume else None,
                                        "currency": "USD",
                                        "source": self.name
                                    }
        except Exception:
            pass
        return None


class GenericRestApiProvider(BaseDataProvider):
    """
    Generic REST API Provider.
    Enables developers to connect new HTTP REST data sources (JSON endpoints)
    simply by declaring a JSON configuration, requiring zero code modifications.
    """
    def __init__(self, config: dict):
        self._name = config.get("name", "Generic_REST_Provider")
        self.url_template = config.get("url_template", "")
        self.symbol_pattern = config.get("symbol_pattern", "")
        self.headers = config.get("headers", {})
        self.price_path = config.get("price_path", "price")
        self.currency = config.get("currency", "USD")
        self.method = config.get("method", "GET").upper()
        self.body_template = config.get("body_template", None)

    @property
    def name(self) -> str:
        return self._name

    def _resolve_json_path(self, data, path: str, symbol: str) -> Optional[float]:
        # Resolve dynamic placeholder {symbol} in path
        resolved_path = path.replace("{symbol}", symbol)
        parts = resolved_path.split('.')
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    idx = int(part)
                    current = current[idx]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return safe_float(current)

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        if self.symbol_pattern:
            if not re.match(self.symbol_pattern, symbol, re.IGNORECASE):
                return None

        url = self.url_template.replace("{symbol}", symbol)
        
        # Resolve environment variable placeholders in headers
        resolved_headers = {}
        for k, v in self.headers.items():
            val = str(v)
            matches = re.findall(r'\$(?:\{(\w+)\}|(\w+))', val)
            for m in matches:
                env_var = m[0] or m[1]
                env_val = os.environ.get(env_var, "")
                full_seq = f"${{{env_var}}}" if m[0] else f"${env_var}"
                val = val.replace(full_seq, env_val)
            resolved_headers[k] = val

        try:
            if self.method == "POST":
                body = None
                if self.body_template:
                    body_str = self.body_template.replace("{symbol}", symbol)
                    try:
                        body = json.loads(body_str)
                    except json.JSONDecodeError:
                        body = body_str
                resp = requests.post(url, headers=resolved_headers, json=body, timeout=5)
            else:
                resp = requests.get(url, headers=resolved_headers, timeout=5)

            if resp.status_code == 200:
                json_data = resp.json()
                price = self._resolve_json_path(json_data, self.price_path, symbol)
                if price is not None:
                    return {
                        "symbol": symbol,
                        "name": symbol,
                        "price": price,
                        "pe_dynamic": None,
                        "turnover_rate": None,
                        "market_cap_billions": None,
                        "currency": self.currency,
                        "source": self.name
                    }
        except Exception:
            pass
        return None


class EastMoneyConsensusProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "EastMoney_Analyst_Consensus"

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        # Only handle 6-digit A-share symbols
        if not re.match(r"^\d{6}$", symbol):
            return None
            
        suffix = "SH" if symbol.startswith(("6", "9")) else "SZ"
        seccode = f"{symbol}.{suffix}"
        
        # Public EastMoney F10 financial forecast Web API
        url = (
            f"https://datacenter.eastmoney.com/securities/api/data/v1/get?"
            f"reportName=RPT_F10_FN_FORECAST&"
            f"columns=SECUCODE%2CSECURITY_NAME_ABBR%2CREPORT_DATE%2CNOTICE_DATE%2CFORECAST_TYPE%2CFORECAST_CONTENT%2CYOY_MIN_PCT%2CYOY_MAX_PCT&"
            f"filter=(SECUCODE%3D%22{seccode}%22)&pageNumber=1&pageSize=1"
        )
        
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                res_json = resp.json()
                if res_json.get("success") and res_json.get("result"):
                    data_list = res_json["result"].get("data", [])
                    if data_list:
                        item = data_list[0]
                        yoy_min = safe_float(item.get("YOY_MIN_PCT", 0.0))
                        yoy_max = safe_float(item.get("YOY_MAX_PCT", 0.0))
                        avg_yoy = (yoy_min + yoy_max) / 2.0 if yoy_min and yoy_max else (yoy_min or yoy_max or 0.0)
                        
                        return {
                            "symbol": symbol,
                            "name": item.get("SECURITY_NAME_ABBR", symbol),
                            "price": avg_yoy,
                            "pe_dynamic": None,
                            "turnover_rate": None,
                            "market_cap_billions": None,
                            "currency": "CNY",
                            "source": self.name
                        }
        except Exception as e:
            print(f"[WARN] EastMoneyConsensusProvider failed: {e}", file=sys.stderr)
        return None


class YahooFinanceConsensusProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "Yahoo_Finance_Analyst_Consensus"

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        # Bypass A-share symbols
        if re.match(r"^\d{6}$", symbol):
            return None
            
        # Yahoo Finance quoteSummary endpoint
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}?modules=financialData,earningsTrend"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                res_json = resp.json()
                result = res_json.get("quoteSummary", {}).get("result", [])
                if result:
                    data = result[0]
                    financial_data = data.get("financialData", {})
                    target_price = safe_float(financial_data.get("targetMeanPrice", {}).get("raw"))
                    
                    earnings_trend = data.get("earningsTrend", {}).get("trend", [])
                    growth = 0.0
                    for trend in earnings_trend:
                        if trend.get("period") == "+1y":
                            growth = safe_float(trend.get("growth", {}).get("raw")) * 100
                            break
                            
                    if target_price or growth:
                        return {
                            "symbol": symbol,
                            "name": f"{symbol}_Consensus",
                            "price": growth if growth else target_price,
                            "pe_dynamic": safe_float(financial_data.get("recommendationMean", {}).get("raw")),
                            "turnover_rate": None,
                            "market_cap_billions": None,
                            "currency": "USD",
                            "source": self.name
                        }
        except Exception as e:
            print(f"[WARN] YahooFinanceConsensusProvider failed: {e}", file=sys.stderr)
        return None


class FREDMacroProvider(BaseDataProvider):
    @property
    def name(self) -> str:
        return "FRED_Macro_Federal_Reserve"

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        # Only handle macro query strings like "US10Y"
        if symbol != "US10Y":
            return None
            
        # Query US 10-Year Treasury Yield using Yahoo's ^TNX ticker
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/^TNX"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                meta = resp.json().get("chart", {}).get("result", [{}])[0].get("meta", {})
                yield_val = safe_float(meta.get("regularMarketPrice"))
                if yield_val:
                    return {
                        "symbol": symbol,
                        "name": "US 10-Year Treasury Yield",
                        "price": yield_val,
                        "pe_dynamic": None,
                        "turnover_rate": None,
                        "market_cap_billions": None,
                        "currency": "USD",
                        "source": self.name
                    }
            else:
                # Direct fallback query if chart endpoint fails
                url_fallback = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=^TNX"
                resp_fb = requests.get(url_fallback, headers=headers, timeout=5)
                if resp_fb.status_code == 200:
                    results = resp_fb.json().get("quoteResponse", {}).get("result", [])
                    if results:
                        yield_val = safe_float(results[0].get("regularMarketPrice"))
                        if yield_val:
                            return {
                                "symbol": symbol,
                                "name": "US 10-Year Treasury Yield",
                                "price": yield_val,
                                "pe_dynamic": None,
                                "turnover_rate": None,
                                "market_cap_billions": None,
                                "currency": "USD",
                                "source": self.name
                            }
        except Exception as e:
            print(f"[WARN] FREDMacroProvider (US10Y) failed: {e}", file=sys.stderr)
        return None


# ─── Unified Data Provider Registry Gateway ───

class DataProviderRegistry:
    def __init__(self):
        self._providers: List[BaseDataProvider] = []
        
        # 1. Base domestic A-share sources in priority order
        self._providers.append(TencentAShareProvider())
        self._providers.append(SinaAShareProvider())
        self._providers.append(NetEaseAShareProvider())
        self._providers.append(EastMoneyConsensusProvider())
        
        # 2. General free global fallback
        self._providers.append(YahooFinanceGlobalProvider())
        self._providers.append(YahooFinanceConsensusProvider())
        self._providers.append(FREDMacroProvider())
        self._providers.append(PolymarketProvider())
        
        # 3. Commercial sources (prepended, only executed if API keys are set)
        self._providers.insert(0, AlphaVantageCommercialProvider())
        self._providers.insert(0, TiingoCommercialProvider())

        # 4. Load from JSON configurations (custom_providers.json) and plugins/ directory
        self._load_dynamic_configurations()
        self._load_dynamic_plugins()

    def register(self, provider: BaseDataProvider):
        """Standard registry interface to plug in new custom providers (prepended for override priority)"""
        self._providers.insert(0, provider)

    def _load_dynamic_configurations(self):
        """Loads and registers custom JSON API configurations from scripts/custom_providers.json"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_config_path = os.path.join(current_dir, "custom_providers.json")
        if os.path.exists(json_config_path):
            try:
                with open(json_config_path, "r", encoding="utf-8") as f:
                    configs = json.load(f)
                    if isinstance(configs, list):
                        for cfg in configs:
                            if isinstance(cfg, dict) and "name" in cfg and "url_template" in cfg:
                                self.register(GenericRestApiProvider(cfg))
            except Exception as e:
                print(f"[WARN] Failed to load custom JSON providers from {json_config_path}: {e}", file=sys.stderr)

    def _load_dynamic_plugins(self):
        """Scans scripts/plugins/ and dynamically loads class definitions inheriting from BaseDataProvider"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        plugins_dir = os.path.join(current_dir, "plugins")
        
        # Self-healing auto-creation of plugins directory to guide developers
        if not os.path.exists(plugins_dir):
            try:
                os.makedirs(plugins_dir, exist_ok=True)
            except Exception:
                pass
            return
            
        if os.path.isdir(plugins_dir):
            import importlib.util
            for fn in os.listdir(plugins_dir):
                if fn.endswith(".py") and fn != "__init__.py":
                    module_path = os.path.join(plugins_dir, fn)
                    module_name = f"plugins.{fn[:-3]}"
                    try:
                        spec = importlib.util.spec_from_file_location(module_name, module_path)
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            sys.modules[module_name] = module
                            spec.loader.exec_module(module)
                            
                            # Inspect and register any class inheriting from BaseDataProvider
                            for attr_name in dir(module):
                                attr = getattr(module, attr_name)
                                if (
                                    isinstance(attr, type) 
                                    and issubclass(attr, BaseDataProvider) 
                                    and attr is not BaseDataProvider
                                    and attr is not GenericRestApiProvider
                                ):
                                    self.register(attr())
                    except Exception as e:
                        print(f"[WARN] Failed to load dynamic Python plugin {fn}: {e}", file=sys.stderr)

    def fetch_price(self, symbol: str) -> dict:
        """
        Unified routing price query. Runs cascading fallbacks
        based on symbol classification (A-Share vs Global)
        """
        is_a_share = re.match(r"^\d{6}$", symbol) is not None
        
        # Split custom vs built-in providers to ensure custom plugins always override defaults
        builtin_names = {
            "Tencent_HQ", "Sina_Finance", "NetEase_Finance", "AkShare_Finance",
            "Yahoo_Finance", "Polymarket_Prediction_Market",
            "Alpha_Vantage_Commercial", "Tiingo_Commercial"
        }
        custom_providers = [p for p in self._providers if p.name not in builtin_names]
        builtin_providers = [p for p in self._providers if p.name in builtin_names]
        
        providers_to_execute = list(custom_providers)
        
        if is_a_share:
            # For A-shares, execute local domestic built-in providers first
            domestic = [p for p in builtin_providers if "Finance" in p.name or "Tencent" in p.name or "AkShare" in p.name]
            providers_to_execute.extend(domestic)
            # Then execute global / commercial built-in fallbacks
            providers_to_execute.extend([p for p in builtin_providers if p not in domestic])
        else:
            # For US/Global stocks, execute global and commercial built-in providers first
            global_builtins = [p for p in builtin_providers if "Yahoo" in p.name or "Commercial" in p.name]
            providers_to_execute.extend(global_builtins)
            # Then execute A-Share built-in providers as final desperate fallback
            providers_to_execute.extend([p for p in builtin_providers if p not in global_builtins])

        # Execute cascading self-healing fallback
        for provider in providers_to_execute:
            try:
                res = provider.fetch_quote(symbol)
                if res and res.get("price") is not None:
                    return res
            except Exception as e:
                print(f"[WARN] Provider {provider.name} failed during cascade lookup: {e}", file=sys.stderr)
                
        return {}


# Singleton Unified Data Gateway Instance for the system
GLOBAL_DATA_GATEWAY = DataProviderRegistry()
