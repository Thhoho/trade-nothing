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
import hypothesis_engine
import opportunity_engine
import report_v2
from version import __version__


REF_RE = re.compile(r"^- \[(\d+)\].*?(https?://\S+)\s*$")
BRACKET_REF_RE = re.compile(r"\[(\d+)\]")
VERDICT_LINE_RE = re.compile(
    r"Edge: \*\*([A-Z_]+)\*\* ｜ 证据方向: \*\*([A-Z_]+)\*\* ｜ "
    r"可行动性: \*\*([A-Z_]+)\*\*"
)
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
    has_decision_brief = "# Decision Brief" in md
    has_audit = "## A · 证明账本" in md
    has_insight_cards = "# Insight Cards" in md

    if "NO_EDGE / AVOID" in md:
        errors.append("Legacy NO_EDGE / AVOID semantic leak found; NO_EDGE must stand alone.")
    if has_decision_brief or has_audit:
        for required in ("Edge: **", "证据方向: **", "可行动性: **"):
            if required not in md:
                errors.append(f"Missing three-axis verdict field: {required}")
    if has_decision_brief:
        dual = ("## 正式晋级动作", "## 探索动作（无晋级与交易权限）")
        present = [required in md for required in dual]
        if any(present) and not all(present):
            errors.append("Dual-track action sections must appear together.")
        for required, found in zip(dual, present):
            if not found:
                errors.append(f"Missing dual-track report section: {required}")

    refs = _references(md)
    if has_audit and not refs:
        errors.append("No concrete References list found.")
    for n, url in refs.items():
        if not crux_engine.is_concrete_url(url):
            errors.append(f"Reference [{n}] is not a concrete URL: {url}")

    if state_path:
        with open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)
        state_bound_md = md.lstrip("\ufeff \t\r\n")
        official_view = None
        if (
            state_bound_md.startswith("# Decision Brief")
            and "# Audit Appendix" in state_bound_md
        ):
            official_view = "full"
        elif state_bound_md.startswith("# Decision Brief"):
            official_view = "brief"
        elif state_bound_md.startswith("# Candidate Cards"):
            official_view = "cards"
        elif (
            state_bound_md.startswith(f"# Trade Nothing v{__version__}")
            or state_bound_md.startswith("# Trade Nothing v0.10")
        ):
            official_view = "audit"
        if official_view:
            try:
                canonical = report_v2.render(state, view=official_view)
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(
                    "Cannot derive canonical report from state: "
                    f"{type(exc).__name__}: {exc}"
                )
                canonical = None
            if (
                canonical is not None
                and state_bound_md.replace("\r\n", "\n").rstrip()
                != canonical.rstrip()
            ):
                errors.append(
                    "Official deterministic report differs from the "
                    f"state-derived {official_view} rendering."
                )
        else:
            errors.append(
                "Cannot identify an official deterministic report view "
                "for the supplied state."
            )
        invalid = []
        for cid, cx in state.get("cruxes", {}).items():
            for cit in cx.get("citations", []):
                if not crux_engine.valid_citation(cit):
                    invalid.append((cid, cit.get("source", "?"), cit.get("url", "")))
        if invalid:
            warnings.append(f"State contains {len(invalid)} invalid citations filtered from report refs.")
        expected = crux_engine.report_data(state).get("research_verdict", {})
        expected_signature = (
            expected.get("edge_state"), expected.get("evidence_direction"),
            expected.get("actionability"),
        )
        rendered_signatures = set(VERDICT_LINE_RE.findall(md))
        if (has_decision_brief or has_audit) and not rendered_signatures:
            errors.append("Cannot parse rendered three-axis verdict for state consistency check.")
        elif rendered_signatures and rendered_signatures != {expected_signature}:
            errors.append(
                "Rendered verdict does not match the state-derived verdict: "
                f"rendered={sorted(rendered_signatures)} expected={expected_signature}"
            )
        if has_decision_brief:
            expected_model = report_v2.build_report_view_model(state)
            expected_formal = expected_model["formal_action"]["code"]
            formal_match = re.search(
                r"## 正式晋级动作\s*\n- `([^`]+)`", md
            )
            if not formal_match:
                errors.append("Cannot parse rendered formal action.")
            elif formal_match.group(1) != expected_formal:
                errors.append(
                    "Rendered formal action does not match state: "
                    f"rendered={formal_match.group(1)} expected={expected_formal}"
                )
            formal_section_match = re.search(
                r"## 正式晋级动作\s*\n(.*?)(?=\n## )",
                md,
                flags=re.DOTALL,
            )
            formal_section = (
                formal_section_match.group(1)
                if formal_section_match else ""
            )
            expected_target = expected_model["formal_action"].get("candidate")
            if expected_target and f"（{expected_target}）" not in formal_section:
                errors.append(
                    "Rendered formal action target does not match state: "
                    f"expected={expected_target}"
                )
            expected_instruction = expected_model["formal_action"].get(
                "instruction"
            )
            if expected_instruction and expected_instruction not in formal_section:
                errors.append(
                    "Rendered formal action instruction does not match state."
                )
            action_section_match = re.search(
                r"## 探索动作（无晋级与交易权限）\s*\n"
                r"(.*?)(?=\n## )",
                md,
                flags=re.DOTALL,
            )
            action_section = (
                action_section_match.group(1)
                if action_section_match else ""
            )
            expected_action = expected_model["exploration_action"]
            expected_budget = expected_action.get("budget_boundary", {})
            action_tokens = {
                "action_code": f"`{expected_action.get('action_code')}`",
                "hypothesis_id": (
                    f"（{expected_action.get('hypothesis_id') or '—'}）"
                ),
                "authorization_state": (
                    f"`{expected_action.get('authorization_state')}`"
                ),
                "executable_after_authorization": (
                    f"`{expected_action.get('executable_after_authorization')}`"
                ),
                "bounded_query": report_v2._clean(
                    expected_action.get("bounded_query")
                ),
                "query_budget": (
                    f"queries≤{expected_budget.get('max_bounded_queries', 0)}"
                ),
                "read_budget": (
                    f"documents≤{expected_budget.get('max_documents_read', 0)}"
                ),
                "execution_receipt": (
                    f"execution_receipt="
                    f"`{expected_action.get('execution_receipt')}`"
                ),
            }
            for field, token in action_tokens.items():
                if token not in action_section:
                    errors.append(
                        "Rendered exploration authorization does not match "
                        f"state: missing {field}={token}"
                    )
        if "# Candidate Cards" in md:
            cards_model = report_v2.build_report_view_model(state)
            cards_section = md.split("# Candidate Cards", 1)[1]
            cards_section = cards_section.split("# Audit Appendix", 1)[0]
            rendered_cards = re.findall(
                r"^- \*\*候选状态\*\*: `([^`]+)` ｜ "
                r"升级资格: `([^`]+)`",
                cards_section,
                flags=re.MULTILINE,
            )
            rendered_seed_ids = re.findall(
                r"^- \*\*Seed ID\*\*: `([^`]+)`",
                cards_section,
                flags=re.MULTILINE,
            )
            rendered_card_titles = re.findall(
                r"^## \d+\. (.+)$",
                cards_section,
                flags=re.MULTILINE,
            )
            expected_cards = [
                (
                    card["candidate_state"],
                    card["promotion_eligibility"],
                )
                for card in cards_model["candidate_cards"]
            ]
            expected_card_titles = [
                report_v2._clean(card["candidate"])
                + (
                    f" · {card['ticker']}"
                    if card.get("ticker") else ""
                )
                for card in cards_model["candidate_cards"]
            ]
            expected_seed_ids = [
                card["seed_id"] for card in cards_model["candidate_cards"]
            ]
            if rendered_cards != expected_cards:
                errors.append(
                    "Rendered candidate maturity does not match state: "
                    f"rendered={rendered_cards} expected={expected_cards}"
                )
            if expected_card_titles and (
                rendered_card_titles != expected_card_titles
            ):
                errors.append(
                    "Rendered candidate identity does not match state: "
                    f"rendered={rendered_card_titles} "
                    f"expected={expected_card_titles}"
                )
            if rendered_seed_ids != expected_seed_ids:
                errors.append(
                    "Rendered candidate seed IDs do not match state: "
                    f"rendered={rendered_seed_ids} expected={expected_seed_ids}"
                )
        exploration_action = hypothesis_engine.exploration_action(state)
        action_code = exploration_action.get("action_code")
        hypothesis_id = exploration_action.get("hypothesis_id")
        binds_exploration = (
            has_decision_brief or has_audit or has_insight_cards
        )
        if binds_exploration and action_code and f"`{action_code}`" not in md:
            errors.append(
                "Rendered exploration action does not match state: "
                f"missing action_code={action_code}"
            )
        if (
            binds_exploration
            and not has_decision_brief
            and hypothesis_id
            and f"`{hypothesis_id}`" not in md
        ):
            errors.append(
                "Rendered exploration action does not match state: "
                f"missing hypothesis_id={hypothesis_id}"
            )
        if has_insight_cards:
            rendered_hypotheses = {
                hypothesis_id: state_name
                for hypothesis_id, state_name in re.findall(
                    r"^## \d+\. (WH-[A-Z0-9]+) — `([A-Z_]+)`$",
                    md,
                    flags=re.MULTILINE,
                )
            }
            expected_hypotheses = {
                item["hypothesis_id"]: item["state"]
                for item in hypothesis_engine.report_view(
                    state, limit=7
                ).get("hypotheses", [])
            }
            if rendered_hypotheses != expected_hypotheses:
                errors.append(
                    "Rendered hypothesis states do not match state: "
                    f"rendered={rendered_hypotheses} "
                    f"expected={expected_hypotheses}"
                )

    battle = _battle_log(md) if has_audit else ""
    if has_audit and battle is None:
        errors.append("Missing BATTLE_LOG_START/END markers.")
        battle = ""
    elif has_audit and ("待 deep 模型写入" in battle or not battle.strip()):
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
    for crux_id, crux in state.get("cruxes", {}).items():
        source_count = len({
            crux_engine.citation_source_identity(citation)
            for citation in crux.get("citations", [])
            if crux_engine.valid_citation(citation)
        })
        if source_count < crux_engine.MIN_VALID_CITATIONS:
            result["state_errors"].append(
                f"{crux_id} has {source_count} valid unique formal sources; "
                f"minimum is {crux_engine.MIN_VALID_CITATIONS}."
            )
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
