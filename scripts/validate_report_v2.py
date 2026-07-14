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
import opportunity_engine


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
    with open(path, encoding="utf-8") as handle:
        md = handle.read()
    errors = []
    warnings = []

    if "NO_EDGE / AVOID" in md:
        errors.append("Legacy NO_EDGE / AVOID semantic leak found; NO_EDGE must stand alone.")
    for required in ("Edge: **", "证据方向: **", "可行动性: **"):
        if required not in md:
            errors.append(f"Missing three-axis verdict field: {required}")

    refs = _references(md)
    if not refs:
        errors.append("No concrete References list found.")
    for n, url in refs.items():
        if not crux_engine.is_concrete_url(url):
            errors.append(f"Reference [{n}] is not a concrete URL: {url}")

    if state_path:
        with open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)
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


def validate_report_outcomes(path, state_path=""):
    """Separate Markdown validity, state consistency, and candidate promotion eligibility."""
    render_errors, warnings = validate_report(path, state_path)
    result = {
        "report_render_valid": not render_errors,
        "report_errors": render_errors,
        "research_state_valid": None,
        "state_errors": [],
        "promotion_eligibility": [],
        "warnings": warnings,
    }
    if not state_path:
        return result
    try:
        with open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        result["research_state_valid"] = False
        result["state_errors"].append(f"Cannot load state: {exc}")
        return result

    if state.get("last_convergence", {}).get("decision") != "converge":
        result["state_errors"].append("Formal report state is not converged.")
    for seed in state.get("opportunity_seeds", []):
        if not isinstance(seed, dict) or not seed.get("seed_id"):
            result["state_errors"].append("Opportunity seed is missing seed_id.")
            continue
        assessment = opportunity_engine.promotion_assessment(state, seed)
        stored_state = str(seed.get("candidate_state") or "")
        if stored_state and stored_state != assessment["candidate_state"]:
            result["state_errors"].append(
                f"{seed['seed_id']} candidate_state drift: stored={stored_state}, "
                f"derived={assessment['candidate_state']}"
            )
        stored_eligibility = str(seed.get("promotion_eligibility") or "")
        if stored_eligibility and stored_eligibility != assessment["promotion_eligibility"]:
            result["state_errors"].append(
                f"{seed['seed_id']} promotion eligibility drift: stored={stored_eligibility}, "
                f"derived={assessment['promotion_eligibility']}"
            )
        result["promotion_eligibility"].append({
            "seed_id": seed["seed_id"],
            "candidate": str(seed.get("candidate") or ""),
            **assessment,
        })
    result["research_state_valid"] = not result["state_errors"]
    return result


def main():
    ap = argparse.ArgumentParser(description="Validate Trade Nothing v2 report quality gates.")
    ap.add_argument("--report", required=True)
    ap.add_argument("--state", default="")
    args = ap.parse_args()

    outcome = validate_report_outcomes(args.report, args.state)
    for w in outcome["warnings"]:
        print(f"WARNING: {w}")
    print("REPORT_RENDER_VALID: " + ("PASS" if outcome["report_render_valid"] else "FAIL"))
    if outcome["research_state_valid"] is None:
        print("RESEARCH_STATE_VALID: NOT_EVALUATED (pass --state)")
    else:
        print("RESEARCH_STATE_VALID: " + ("PASS" if outcome["research_state_valid"] else "FAIL"))
    if outcome["promotion_eligibility"]:
        for item in outcome["promotion_eligibility"]:
            blockers = ",".join(item["blocking_reasons"]) or "none"
            print(
                f"PROMOTION_ELIGIBILITY {item['seed_id']} {item['candidate']}: "
                f"{item['promotion_eligibility']} | state={item['candidate_state']} | blockers={blockers}"
            )
    else:
        print("PROMOTION_ELIGIBILITY: NO_CANDIDATES")
    if outcome["report_errors"] or outcome["state_errors"]:
        print("FAILED")
        for e in outcome["report_errors"] + outcome["state_errors"]:
            print(f"- {e}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
