#!/usr/bin/env python3
"""
Trade Nothing v0.9 — Logic Radar Daemon (逻辑雷达常驻守护进程)

Checks all registered macro indicators at N-minute intervals.
Triggers cross-platform system notifications when thresholds are breached.

Usage: python3 logic_radar_daemon.py [--interval 300]
"""

import os
import sys
import time
import argparse
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import send_notification

ALERT_MESSAGES = {
    "BRENT_OIL": "原油价格触达阈值，中游制造业利润挤压逻辑激活！",
    "US_10Y": "美债收益率突破阈值，全球估值杀逻辑启动！",
    "USDCNY": "人民币汇率承压，北向资金流出风险上升！",
    "VIX": "恐慌指数飙升，全球 risk-off 模式开启！",
}


def check_and_alert():
    """Execute one full check cycle"""
    from verified_fetcher import VerifiedFetcher

    fetcher = VerifiedFetcher()
    all_data = fetcher.fetch_all()

    triggered = []
    for item in all_data:
        if item["threshold_status"] == "🔥 TRIGGERED":
            triggered.append(item)
            indicator = item["indicator"]
            msg = ALERT_MESSAGES.get(indicator, f"{item['name']} 触达阈值！")
            send_notification(
                f"🔥 逻辑雷达 [{indicator}]",
                f"{msg} (当前值: {item['value']} {item['unit']})"
            )

    status = {
        "timestamp": datetime.now().isoformat(),
        "checked": len(all_data),
        "successful": sum(1 for d in all_data if d["status"] == "Verified"),
        "triggered": [t["indicator"] for t in triggered],
        "values": {d["indicator"]: d["value"] for d in all_data if d["value"] is not None},
    }
    return status


def main_loop(interval: int):
    """Main monitoring loop"""
    print(f"🚀 逻辑雷达守护进程已启动。监控频率: {interval}s")
    send_notification("逻辑雷达", "常驻监测进程已启动...")

    while True:
        try:
            status = check_and_alert()
            ts = status["timestamp"][:19]
            print(f"[{ts}] Checked: {status['checked']} | OK: {status['successful']} | Triggered: {status['triggered']}")

            if status["triggered"]:
                try:
                    from logic_radar_v2 import run_radar
                    run_radar()
                except Exception as e:
                    print(f"[WARN] Evolution update failed: {e}", file=sys.stderr)

        except Exception as e:
            print(f"[ERROR] Loop error: {e}", file=sys.stderr)

        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Logic Radar Daemon")
    parser.add_argument("--interval", type=int, default=300, help="Check interval in seconds (default: 300)")
    args = parser.parse_args()
    try:
        main_loop(args.interval)
    except KeyboardInterrupt:
        print("\n🛑 逻辑雷达已停止。")
