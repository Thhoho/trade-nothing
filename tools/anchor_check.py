#!/usr/bin/env python3
"""Deterministic anchor-trigger check — no LLM, no network, no writes.

Parses the `更新触发器` lines of anchors/*.md for dates, finds each theme's
next trigger, and sends a macOS notification when a trigger is due or within
WINDOW days. Event-based triggers without a date (e.g. "朱雀三号发射窗口")
are skipped by design — they surface in the weekly review instead.

Exit 0 always (a check with nothing due is success, not failure).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANCHORS = ROOT / "anchors"

DATE_PATTERNS = [
    re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})"),
    re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日"),
    re.compile(r"(?<![0-9])(\d{1,2})/(\d{1,2})(?![0-9/])"),
]


def parse_dates(text: str, today: date) -> list[date]:
    found = []
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            if pattern is DATE_PATTERNS[2]:
                month, day = int(match.group(1)), int(match.group(2))
                year = today.year if (month, day) >= (today.month, today.day) else today.year + 1
            else:
                year, month, day = (int(g) for g in match.groups())
            try:
                parsed = date(year, month, day)
            except ValueError:
                continue
            if parsed >= today:
                found.append(parsed)
    return found


def next_trigger(anchor_file: Path, today: date) -> tuple[str, date] | None:
    text = anchor_file.read_text(encoding="utf-8")
    blocks = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    dates = []
    for block in blocks:
        header = block.splitlines()[0] if block.splitlines() else ""
        if "失效" in header:
            continue
        match = re.search(r"更新触发器[:：]([^\n]*)", block)
        if not match:
            continue
        dates.extend(parse_dates(match.group(1), today))
    if not dates:
        return None
    return anchor_file.stem, min(dates)


def notify(message: str) -> None:
    script = f'display notification "{message}" with title "⚓ 锚体检"'
    subprocess.run(["osascript", "-e", script], check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", type=int, default=3, help="days before trigger to start reminding")
    parser.add_argument("--no-notify", action="store_true", help="print only, no notification")
    args = parser.parse_args()

    today = date.today()
    due, near = [], []
    for anchor_file in sorted(ANCHORS.glob("*.md")):
        if anchor_file.name in {"README.md", "index.md"}:
            continue
        hit = next_trigger(anchor_file, today)
        if not hit:
            continue
        theme, when = hit
        days = (when - today).days
        if days <= 0:
            due.append((theme, when, days))
        elif days <= args.window:
            near.append((theme, when, days))

    lines = []
    for theme, when, days in due:
        lines.append(f"{theme}：锚触发已到（{when.isoformat()}）——说「更新锚」即可")
    for theme, when, days in near:
        lines.append(f"{theme}：锚触发临近（{when.isoformat()}，还有 {days} 天）")

    if lines:
        message = "；".join(lines)
        print(message)
        if not args.no_notify:
            notify(message)
    else:
        print("⚓ 锚体检：无到期触发器")
    return 0


if __name__ == "__main__":
    sys.exit(main())
