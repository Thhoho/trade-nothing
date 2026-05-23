#!/usr/bin/env python3
"""
Trade Nothing v0.9 — A-Share Stock Data Fetcher (A股行情与财务数据获取器)

Multi-source fallback: Tencent HQ (P0) → AkShare (P1) → YahooFinance (backup)

Financial data: Prioritizes EastMoney `stock_financial_analysis_indicator_em`
(sorted by REPORT_DATE for latest period).

Usage:
  python3 fetch_akshare.py --code 300118
  python3 fetch_akshare.py --code 300118 --financial
  python3 fetch_akshare.py --code 300118 --macro GC=F
"""

import os
import sys
import argparse
import json
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import clean_proxy_env

clean_proxy_env()


def to_em_symbol(code: str) -> str:
    """6-digit A-share code → EastMoney symbol, e.g. 300118 → 300118.SZ"""
    code = str(code).strip()
    if len(code) != 6 or not code.isdigit():
        raise ValueError(f"Invalid A-share code: {code}")
    if code.startswith(("00", "30")):
        return f"{code}.SZ"
    if code.startswith(("60", "68")):
        return f"{code}.SH"
    if code.startswith(("43", "83", "87", "92")):
        return f"{code}.BJ"
    return f"{code}.SZ"


class StockDataFetcher:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.em_symbol = to_em_symbol(symbol)
        self.full_symbol_szsh = f"sz{symbol}" if symbol.startswith(('00', '30')) else f"sh{symbol}"
        self.ua = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 "
            "Mobile/15E148 Safari/604.1"
        )

    def fetch_market_snapshot(self) -> dict:
        """[P0] Tencent HQ real-time quotes"""
        url = f"http://qt.gtimg.cn/q={self.full_symbol_szsh}"
        try:
            resp = requests.get(url, headers={"User-Agent": self.ua}, timeout=5)
            data = resp.text.split('~')
            if len(data) > 45:
                return {
                    "name": data[1],
                    "price": data[3],
                    "prev_close": data[4],
                    "open": data[5],
                    "volume": data[6],
                    "change_pct": data[32],
                    "high": data[33],
                    "low": data[34],
                    "turnover_rate": data[38],
                    "pe_dynamic": data[39],
                    "pb": data[46] if len(data) > 46 else None,
                    "market_cap": data[45],
                    "source": "Tencent_HQ",
                    "confidence": "high",
                }
        except Exception as e:
            print(f"[WARN] Tencent HQ failed: {e}", file=sys.stderr)

        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                row = df[df['代码'] == self.symbol]
                if not row.empty:
                    r = row.iloc[0]
                    return {
                        "name": r.get("名称", ""),
                        "price": str(r.get("最新价", "")),
                        "change_pct": str(r.get("涨跌幅", "")),
                        "pe_dynamic": str(r.get("市盈率-动态", "")),
                        "market_cap": str(r.get("总市值", "")),
                        "source": "AkShare_EM",
                        "confidence": "high",
                    }
        except Exception as e:
            print(f"[WARN] AkShare fallback failed: {e}", file=sys.stderr)

        return {"error": "All sources failed", "confidence": "none"}

    def _latest_em_financial_row(self) -> dict:
        """EastMoney financial analysis indicators: sorted by report date, latest row."""
        import akshare as ak
        df = ak.stock_financial_analysis_indicator_em(
            symbol=self.em_symbol, indicator="按报告期"
        )
        if df is None or df.empty:
            return {}
        if "REPORT_DATE" not in df.columns:
            return {}
        df = df.sort_values("REPORT_DATE", ascending=False)
        r = df.iloc[0]

        def _fmt_date(v):
            if v is None or (hasattr(v, "__float__") and str(v) == "nan"):
                return None
            if hasattr(v, "strftime"):
                return v.strftime("%Y-%m-%d")
            return str(v)[:10]

        out = {
            "em_symbol": self.em_symbol,
            "report_date": _fmt_date(r.get("REPORT_DATE")),
            "notice_date": _fmt_date(r.get("NOTICE_DATE")),
            "parent_net_profit": float(r["PARENTNETPROFIT"]) if r.get("PARENTNETPROFIT") is not None else None,
            "parent_net_profit_yoy_pct": float(r["PARENTNETPROFITTZ"]) if r.get("PARENTNETPROFITTZ") is not None else None,
            "total_operating_revenue": float(r["TOTALOPERATEREVE"]) if r.get("TOTALOPERATEREVE") is not None else None,
            "revenue_yoy_pct": float(r["TOTALOPERATEREVETZ"]) if r.get("TOTALOPERATEREVETZ") is not None else None,
            "basic_eps": float(r["EPSJB"]) if r.get("EPSJB") is not None else None,
            "roe_pct": float(r["ROEJQ"]) if r.get("ROEJQ") is not None else None,
            "debt_to_asset_pct": float(r["ZCFZL"]) if r.get("ZCFZL") is not None else None,
            "total_liabilities": float(r["LIABILITY"]) if r.get("LIABILITY") is not None else None,
        }
        return {k: v for k, v in out.items() if v is not None}

    def _latest_ths_financial_abstract(self) -> dict:
        """THS financial abstract: must sort by report date descending."""
        import akshare as ak
        df = ak.stock_financial_abstract_ths(symbol=self.symbol, indicator="按报告期")
        if df is None or df.empty:
            return {}
        if "报告期" not in df.columns:
            return {}
        df = df.sort_values("报告期", ascending=False)
        latest = df.iloc[0].to_dict()
        return {k: str(v) if v is not None else None for k, v in latest.items()}

    def fetch_financial_summary(self) -> dict:
        """[P1] Core financial indicators: EM first, THS fallback."""
        result: dict = {"source": "unavailable", "confidence": "none"}

        try:
            import akshare as ak
            df = ak.stock_individual_info_em(symbol=self.symbol)
            if df is not None and not df.empty:
                info = {}
                for _, row in df.iterrows():
                    info[row['item']] = row['value']
                result.update({
                    "total_market_cap": info.get("总市值"),
                    "circulating_cap": info.get("流通市值"),
                    "industry": info.get("行业"),
                    "pe_ttm": info.get("市盈率(动态)"),
                    "pb": info.get("市净率"),
                    "snapshot_source": "AkShare_EM_individual_info",
                })
        except Exception as e:
            result["individual_info_error"] = str(e)

        em_latest = {}
        try:
            em_latest = self._latest_em_financial_row()
            if em_latest:
                result["latest_report"] = em_latest
                result["financial_primary_source"] = "AkShare_EM_financial_analysis_indicator"
                result["confidence"] = "high"
        except Exception as e:
            result["em_financial_error"] = str(e)

        if not em_latest:
            try:
                ths = self._latest_ths_financial_abstract()
                if ths:
                    result["financial_abstract_ths_latest"] = ths
                    result["financial_primary_source"] = "AkShare_THS_abstract_sorted"
                    result["confidence"] = "medium"
            except Exception as e:
                result["ths_financial_error"] = str(e)

        if result.get("latest_report") or result.get("financial_abstract_ths_latest"):
            result["source"] = result.get("financial_primary_source", "partial")
        else:
            result["source"] = "unavailable"

        return result

    def fetch_global_macro(self, ticker: str) -> dict:
        """[P1] Global macro/commodity quotes via YahooFinance"""
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if not hist.empty:
                return {
                    "ticker": ticker,
                    "last_price": float(hist['Close'].iloc[-1]),
                    "prev_close": float(hist['Close'].iloc[-2]) if len(hist) > 1 else None,
                    "change_5d_pct": round(
                        (float(hist['Close'].iloc[-1]) / float(hist['Close'].iloc[0]) - 1) * 100, 2
                    ) if len(hist) > 1 else None,
                    "source": "Yahoo_Finance",
                    "confidence": "high",
                }
        except Exception as e:
            return {"ticker": ticker, "error": str(e), "confidence": "none"}


def main():
    parser = argparse.ArgumentParser(description="Stock Data Fetcher")
    parser.add_argument("--code", help="A-share stock code (e.g. 300212)")
    parser.add_argument("--symbol", help="Alias for --code")
    parser.add_argument("--stock", help="Alias for --code")
    parser.add_argument("--ticker", help="Alias for --code")
    parser.add_argument("--macro", help="Global ticker for macro linkage (e.g. GC=F, BZ=F)")
    parser.add_argument("--financial", action="store_true", help="Include financial summary")
    parser.add_argument("--indicator", help="Alias for --financial (if value contains 'financial')")
    args = parser.parse_args()

    code = args.code or args.symbol or args.stock or args.ticker
    if not code:
        parser.error("Stock code is required. Use --code, --symbol, --stock, or --ticker.")

    if args.indicator and "financial" in args.indicator.lower():
        args.financial = True

    fetcher = StockDataFetcher(code)
    result = {
        "symbol": code,
        "em_symbol": fetcher.em_symbol,
        "timestamp": datetime.now().isoformat(),
        "data": {}
    }

    result["data"]["market"] = fetcher.fetch_market_snapshot()

    if args.financial:
        result["data"]["financial"] = fetcher.fetch_financial_summary()

    if args.macro:
        result["data"]["macro"] = fetcher.fetch_global_macro(args.macro)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
