#!/usr/bin/env python3
"""
Trade Nothing v0.9 — Logic Radar v2 (逻辑雷达)

Reads Radar Hooks and Assertions from Evolution.md,
fetches current market data, updates status and performs calibration.

Usage: python3 logic_radar_v2.py [--evolution-path PATH]
"""

import os
import re
import json
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import get_evolution_path


def get_current_values() -> dict:
    """Fetch all registered indicator values via VerifiedFetcher"""
    from verified_fetcher import VerifiedFetcher

    fetcher = VerifiedFetcher()
    all_data = fetcher.fetch_all()

    values = {}
    for item in all_data:
        if item["value"] is not None:
            values[item["indicator"]] = {
                "value": item["value"],
                "source": item["source"],
                "threshold_status": item["threshold_status"],
            }
    return values


def update_radar_hooks(content: str, current_data: dict) -> str:
    """Update Radar Hook status in Evolution.md"""

    indicator_to_radar = {
        "BRENT_OIL": "Radar_001",
        "US_10Y": "Radar_002",
        "USDCNY": "Radar_003",
        "VIX": "Radar_004",
    }

    for indicator, radar_id in indicator_to_radar.items():
        if indicator in current_data:
            data = current_data[indicator]
            status = data["threshold_status"] or "🟢 监控中"
            value = data["value"]

            old_status_pattern = rf"(### \[{radar_id}\].*?- \*\*状态\*\*: ).*?\n"
            new_status = f"\\g<1>{status} (当前值: {value}, 更新: {datetime.now().strftime('%Y-%m-%d %H:%M')})\n"
            content = re.sub(old_status_pattern, new_status, content, flags=re.DOTALL)

    return content


def calibrate_assertions(content: str, current_data: dict) -> tuple:
    """
    Calibrate assertions in Evolution.md.
    Format: [ASSERTION: indicator operator value by date]
    """
    new_log_entries = []
    assertions = re.findall(r"\[ASSERTION: (\w+) ([<>=!]+) ([\d.]+) by (\d{4}-\d{2}-\d{2})\]", content)

    for target, op, val_str, date_str in assertions:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
            if datetime.now() >= target_date:
                current_val = current_data.get(target, {}).get("value")
                if current_val is not None:
                    val = float(val_str)
                    if op == ">":
                        passed = current_val > val
                    elif op == "<":
                        passed = current_val < val
                    elif op == ">=":
                        passed = current_val >= val
                    elif op == "<=":
                        passed = current_val <= val
                    elif op == "==":
                        passed = abs(current_val - val) < val * 0.05
                    else:
                        continue

                    result = "✅正确" if passed else "❌错误"
                    log_entry = (
                        f"- *{datetime.now().strftime('%Y-%m-%d')}*: **校准 [{result}]**: \n"
                        f"  - 断言: {target} {op} {val_str} by {date_str}\n"
                        f"  - 实际: {target} = {current_val}\n"
                        f"  - 归因: [待人工补充]\n"
                        f"  - 方法论修正: [待人工补充]"
                    )
                    new_log_entries.append(log_entry)
                    content = content.replace(
                        f"[ASSERTION: {target} {op} {val_str} by {date_str}]",
                        f"[CALIBRATED {result}: {target} {op} {val_str} by {date_str} | actual={current_val}]"
                    )
        except (ValueError, TypeError) as e:
            print(f"[WARN] Calibration error for {target}: {e}", file=sys.stderr)

    if new_log_entries:
        cal_marker = "## 4. 校准日志 (Calibration Log)"
        if cal_marker in content:
            insert_point = content.index(cal_marker) + len(cal_marker)
            rest = content[insert_point:]
            entry_marker = "（暂无条目"
            if entry_marker in rest:
                content = content.replace(
                    f"{cal_marker}\n\n记录过去分析的事后验证。对了为什么对，错了为什么错。这是系统学会自我校正的关键。\n\n（暂无条目——首次使用 `-calibrate` 模式后将自动填充）",
                    f"{cal_marker}\n\n记录过去分析的事后验证。对了为什么对，错了为什么错。这是系统学会自我校正的关键。\n\n" + "\n\n".join(new_log_entries)
                )
            else:
                next_section = rest.find("\n## ")
                if next_section > 0:
                    insert_pos = insert_point + next_section
                    content = content[:insert_pos] + "\n\n" + "\n\n".join(new_log_entries) + content[insert_pos:]

    return content, new_log_entries


def run_radar(evolution_path: str = None):
    """Main flow: fetch data → update hooks → calibrate assertions"""
    path = evolution_path or get_evolution_path()

    if not os.path.exists(path):
        print(f"[ERROR] Evolution file not found: {path}", file=sys.stderr)
        print(json.dumps({"status": "error", "message": f"File not found: {path}"}))
        return

    current_data = get_current_values()
    print(f"[INFO] Fetched {len(current_data)} indicators:", file=sys.stderr)
    for k, v in current_data.items():
        print(f"  {k}: {v['value']} ({v['threshold_status']})", file=sys.stderr)

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    content = update_radar_hooks(content, current_data)
    content, calibrations = calibrate_assertions(content, current_data)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

    result = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "indicators_fetched": len(current_data),
        "indicators": {k: v["value"] for k, v in current_data.items()},
        "triggered_hooks": [k for k, v in current_data.items() if v["threshold_status"] == "🔥 TRIGGERED"],
        "calibrations_performed": len(calibrations),
        "evolution_path": path,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Logic Radar v2 — Hook Monitor & Calibrator")
    parser.add_argument("--evolution-path", help="Path to Evolution.md")
    args = parser.parse_args()
    run_radar(args.evolution_path)
