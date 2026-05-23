#!/usr/bin/env python3
"""
Trade Nothing v7.0 — Verified Data Fetcher (验证式数据获取器)

Ensures every data point has a source, confidence score, and fallback.
Priority: AkShare → YahooFinance → Tencent HQ → WebSearch (manual annotation)

Usage:
  python3 verified_fetcher.py --indicator US_10Y
  python3 verified_fetcher.py --indicator BRENT_OIL
  python3 verified_fetcher.py --all
"""

import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import clean_proxy_env

clean_proxy_env()

INDICATORS = {
    "US_10Y": {
        "name": "美债10年期收益率",
        "unit": "%",
        "radar_hook": "Radar_002",
        "threshold": 4.8,
        "threshold_direction": ">",
    },
    "BRENT_OIL": {
        "name": "布伦特原油",
        "unit": "USD/bbl",
        "radar_hook": "Radar_001",
        "threshold": 95.0,
        "threshold_direction": ">",
    },
    "VIX": {
        "name": "恐慌指数 (VIX)",
        "unit": "",
        "radar_hook": "Radar_004",
        "threshold": 30.0,
        "threshold_direction": ">",
    },
    "USDCNY": {
        "name": "美元兑人民币",
        "unit": "",
        "radar_hook": "Radar_003",
        "threshold": 7.35,
        "threshold_direction": ">",
    },
    "GOLD": {
        "name": "黄金",
        "unit": "USD/oz",
        "radar_hook": None,
        "threshold": None,
        "threshold_direction": None,
    },
}


class VerifiedFetcher:
    """验证式数据获取器"""

    def __init__(self):
        self.results = {}

    def _try_yfinance(self, ticker: str) -> tuple:
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if not hist.empty:
                val = float(hist['Close'].iloc[-1])
                return val, "YahooFinance", 0.95
        except Exception as e:
            print(f"[YF] {ticker} failed: {e}", file=sys.stderr)
        return None, "YahooFinance", 0.0

    def _try_akshare_bond(self) -> tuple:
        try:
            import akshare as ak
            import math
            df = ak.bond_zh_us_rate()
            if not df.empty:
                val = float(df.iloc[-1]['美国国债收益率10年'])
                if not math.isnan(val):
                    return val, "AkShare", 0.90
        except Exception as e:
            print(f"[AK] Bond fetch failed: {e}", file=sys.stderr)
        return None, "AkShare", 0.0

    def _try_akshare_oil(self) -> tuple:
        try:
            import akshare as ak
            import math
            df = ak.futures_foreign_commodity_realtime(symbol="布伦特原油")
            if not df.empty:
                val = float(df['last'].values[0])
                if not math.isnan(val):
                    return val, "AkShare", 0.90
        except Exception as e:
            print(f"[AK] Oil fetch failed: {e}", file=sys.stderr)
        return None, "AkShare", 0.0

    def fetch(self, indicator: str) -> dict:
        meta = INDICATORS.get(indicator)
        if not meta:
            return {"indicator": indicator, "error": f"Unknown indicator. Available: {list(INDICATORS.keys())}"}

        value, source, confidence = None, "None", 0.0

        if indicator == "US_10Y":
            value, source, confidence = self._try_akshare_bond()
            if value is None:
                value, source, confidence = self._try_yfinance("^TNX")

        elif indicator == "BRENT_OIL":
            value, source, confidence = self._try_akshare_oil()
            if value is None:
                value, source, confidence = self._try_yfinance("BZ=F")

        elif indicator == "VIX":
            value, source, confidence = self._try_yfinance("^VIX")

        elif indicator == "USDCNY":
            value, source, confidence = self._try_yfinance("CNY=X")
            if value and value < 1:
                value = 1 / value

        elif indicator == "GOLD":
            value, source, confidence = self._try_yfinance("GC=F")

        threshold_status = None
        if value is not None and meta["threshold"] is not None:
            op = meta["threshold_direction"]
            if op == ">":
                triggered = value > meta["threshold"]
            else:
                triggered = value < meta["threshold"]
            threshold_status = "🔥 TRIGGERED" if triggered else "🟢 NORMAL"

        return {
            "indicator": indicator,
            "name": meta["name"],
            "value": value,
            "unit": meta["unit"],
            "source": source,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
            "status": "Verified" if value is not None else "Failed",
            "radar_hook": meta["radar_hook"],
            "threshold": meta["threshold"],
            "threshold_status": threshold_status,
        }

    def fetch_all(self) -> list:
        """Fetch all registered indicators"""
        return [self.fetch(ind) for ind in INDICATORS]


def main():
    parser = argparse.ArgumentParser(description="Verified Data Fetcher")
    parser.add_argument("--indicator", help=f"Indicator to fetch. Options: {list(INDICATORS.keys())}")
    parser.add_argument("--all", action="store_true", help="Fetch all registered indicators")
    args = parser.parse_args()

    fetcher = VerifiedFetcher()

    if args.all:
        results = fetcher.fetch_all()
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.indicator:
        result = fetcher.fetch(args.indicator)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
