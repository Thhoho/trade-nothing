#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validate a completed Trade Nothing v2 report.

Checks:
  - References are concrete URLs, not homepage/domain-only anchors.
  - BATTLE_LOG was filled.
  - B layer does not cite missing reference numbers.
  - B layer data-like numbers are cited on the same line.
"""
import argparse
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import crux_engine


REF_RE = re.compile(r"^- \[(\d+)\].*?(https?://\S+)\s*$")
BRACKET_REF_RE = re.compile(r"\[(\d+)\]")
DATA_NUMBER_RE = re.compile(
    r"(\$\s*\d+(?:\.\d+)?)|"
    r"(\d+(?:\.\d+)?\s*(?:%|元|亿元|亿|万元|万|MW|GW|GWh|Wh|℃|°C|美元|颗|吨|μm|um|cm2|倍|股|亿元?))|"
    r"(\d{4}年(?:\d{1,2}月(?:\d{1,2}日)?)?)|"
    r"(\d{4}-\d{2}(?:-\d{2})?)"
)


def _battle_log(md):
    start = "<!-- BATTLE_LOG_START -->"
    end = "<!-- BATTLE_LOG_END -->"
    a = md.find(start)
    b = md.find(end)
    if a == -1 or b == -1 or b <= a:
        return None
    return md[a + len(start):b]


def _references(md):
    refs = {}
    for line in md.splitlines():
        m = REF_RE.match(line.strip())
        if m:
            refs[int(m.group(1))] = m.group(2)
    return refs


def _ignore_numeric_line(line):
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith(("### 模块", "<!--", "|:---", "| 场景", "```")):
        return True
    # Markdown structure numbers, not research data.
    if re.match(r"^(#{1,6}\s*)?(模块\s*)?\d+[.、]\s*", stripped):
        return True
    return False


def validate_report(path, state_path=""):
    md = open(path, encoding="utf-8").read()
    errors = []
    warnings = []

    refs = _references(md)
    if not refs:
        errors.append("No concrete References list found.")
    for n, url in refs.items():
        if not crux_engine.is_concrete_url(url):
            errors.append(f"Reference [{n}] is not a concrete URL: {url}")

    if state_path:
        state = json.load(open(state_path, encoding="utf-8"))
        invalid = []
        for cid, cx in state.get("cruxes", {}).items():
            for cit in cx.get("citations", []):
                if not crux_engine.valid_citation(cit):
                    invalid.append((cid, cit.get("source", "?"), cit.get("url", "")))
        if invalid:
            warnings.append(f"State contains {len(invalid)} invalid citations filtered from report refs.")

    battle = _battle_log(md)
    if battle is None:
        errors.append("Missing BATTLE_LOG_START/END markers.")
        battle = ""
    elif "待 deep 模型写入" in battle or not battle.strip():
        errors.append("BATTLE_LOG is still a placeholder.")

    max_ref = max(refs) if refs else 0
    for i, line in enumerate(battle.splitlines(), 1):
        for ref in BRACKET_REF_RE.findall(line):
            if int(ref) > max_ref:
                errors.append(f"B line {i}: cites missing reference [{ref}].")
        if _ignore_numeric_line(line):
            continue
        if DATA_NUMBER_RE.search(line) and not BRACKET_REF_RE.search(line):
            errors.append(f"B line {i}: data-like number without [n] citation: {line.strip()[:160]}")

    return errors, warnings


def main():
    ap = argparse.ArgumentParser(description="Validate Trade Nothing v2 report quality gates.")
    ap.add_argument("--report", required=True)
    ap.add_argument("--state", default="")
    args = ap.parse_args()

    errors, warnings = validate_report(args.report, args.state)
    for w in warnings:
        print(f"WARNING: {w}")
    if errors:
        print("FAILED")
        for e in errors:
            print(f"- {e}")
        raise SystemExit(2)
    print("PASSED")


if __name__ == "__main__":
    main()
