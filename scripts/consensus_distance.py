#!/usr/bin/env python3
"""
Trade Nothing v7.0 — Consensus Distance Calculator (共识距离计算器)

Quantifies deviation between your analysis conclusion and market consensus.
Too close = mundane (no alpha); Too far without evidence = dangerous contrarianism.

Usage:
  python3 consensus_distance.py --code 300118 --target 25.0
  python3 consensus_distance.py --code 300118 --target 25.0 --eps 0.8
"""

import argparse
import json
import os
import sys
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import clean_proxy_env
clean_proxy_env()


class ConsensusDistanceCalculator:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.full_symbol_szsh = f"sz{symbol}" if symbol.startswith(('00', '30')) else f"sh{symbol}"
        self.ua = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 "
            "Mobile/15E148 Safari/604.1"
        )

    def fetch_current_price(self) -> dict:
        """Fetch current price via Tencent HQ API."""
        url = f"http://qt.gtimg.cn/q={self.full_symbol_szsh}"
        try:
            resp = requests.get(url, headers={"User-Agent": self.ua}, timeout=5)
            data = resp.text.split('~')
            if len(data) > 39:
                return {
                    "name": data[1],
                    "price": float(data[3]) if data[3] else None,
                    "pe_dynamic": float(data[39]) if data[39] else None,
                    "turnover_rate": float(data[38]) if data[38] else None,
                    "market_cap_billions": float(data[45]) / 1e8 if len(data) > 45 and data[45] else None,
                }
        except Exception as e:
            print(f"[WARN] Tencent HQ fetch failed: {e}", file=sys.stderr)
        return {}

    def fetch_analyst_consensus(self) -> dict:
        """Attempt to fetch analyst consensus. Free sources are limited."""
        consensus = {
            "eps_consensus": None,
            "target_price_consensus": None,
            "rating_distribution": {"buy": 0, "hold": 0, "sell": 0},
            "source": "manual_input_required",
            "note": "Free API limitations — use WebSearch: '[code] consensus target price site:xueqiu.com'"
        }

        try:
            import akshare as ak
            df = ak.stock_profit_forecast_em(symbol=self.symbol)
            if df is not None and not df.empty:
                latest = df.iloc[0]
                eps_val = latest.get("预测年报每股收益", 0) or 0
                consensus["eps_consensus"] = float(eps_val)
                consensus["source"] = "AkShare_EastMoney"
                consensus["note"] = "EPS forecast retrieved successfully"
        except Exception as e:
            consensus["fallback_note"] = f"AkShare forecast unavailable: {e}"

        return consensus

    def calculate_distance(self, your_target: float = None, your_eps: float = None) -> dict:
        current = self.fetch_current_price()
        consensus = self.fetch_analyst_consensus()

        result = {
            "symbol": self.symbol,
            "timestamp": datetime.now().isoformat(),
            "current_market": current,
            "analyst_consensus": consensus,
            "distance_analysis": {}
        }

        if current.get("price") and your_target:
            price = current["price"]
            price_distance_pct = ((your_target - price) / price) * 100
            result["distance_analysis"]["your_target"] = your_target
            result["distance_analysis"]["current_price"] = price
            result["distance_analysis"]["price_distance_pct"] = round(price_distance_pct, 2)

            abs_dist = abs(price_distance_pct)
            if abs_dist < 10:
                verdict = "MUNDANE — <10% deviation from current price, likely no alpha"
            elif abs_dist < 25:
                verdict = "MODERATE — Meaningful expectation gap exists"
            elif abs_dist < 50:
                verdict = "STRONG — Significant variant perception, needs solid evidence chain"
            else:
                verdict = "EXTREME — Contrarian view, verify hard evidence or check for cognitive bias"
            result["distance_analysis"]["verdict"] = verdict

        if consensus.get("eps_consensus") and your_eps:
            eps_dist = ((your_eps - consensus["eps_consensus"]) / abs(consensus["eps_consensus"])) * 100
            result["distance_analysis"]["eps_consensus"] = consensus["eps_consensus"]
            result["distance_analysis"]["your_eps"] = your_eps
            result["distance_analysis"]["eps_distance_pct"] = round(eps_dist, 2)

        return result


def main():
    parser = argparse.ArgumentParser(description="Consensus Distance Calculator v7.0")
    parser.add_argument("--code", required=True, help="Stock code (e.g. 300118)")
    parser.add_argument("--target", type=float, help="Your target price")
    parser.add_argument("--eps", type=float, help="Your EPS estimate")
    args = parser.parse_args()

    calc = ConsensusDistanceCalculator(args.code)
    result = calc.calculate_distance(your_target=args.target, your_eps=args.eps)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
