#!/usr/bin/env python3
"""Gate Trade Nothing against a same-model single-agent product baseline.

This benchmark is intentionally separate from the historical closed-packet
reasoning suites.  It evaluates whether a finished research artifact found the
hidden material facts and helped a blind reader decide, at comparable cost.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


KEY_SCHEMA = "trade-nothing.product-value-key.v1"
ASSESSMENT_SCHEMA = "trade-nothing.product-value-assessment.v1"
SUMMARY_SCHEMA = "trade-nothing.product-value-summary.v1"


def _load(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value):
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text.lower())


def _is_concrete_url(value):
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and parsed.path not in {"", "/"}


def _nonnegative_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _nonnegative_integer(value):
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 and str(value).strip() == str(number) else None


def _iso_date(value):
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def _validate_key(key):
    issues = []
    if key.get("schema_version") != KEY_SCHEMA:
        issues.append("key_schema_invalid")
    if not _is_sha256(key.get("research_question_sha256")):
        issues.append("key_research_question_sha256_invalid")
    key_as_of = _iso_date(key.get("as_of_date"))
    if key_as_of is None:
        issues.append("key_as_of_date_invalid")
    facts = key.get("material_facts")
    if not isinstance(facts, list) or not facts:
        issues.append("material_facts_required")
        facts = []
    seen = set()
    for item in facts:
        if not isinstance(item, dict):
            issues.append("material_fact_must_be_object")
            continue
        fact_id = str(item.get("fact_id") or "")
        if not fact_id or fact_id in seen:
            issues.append("material_fact_id_missing_or_duplicate")
        seen.add(fact_id)
        try:
            weight = float(item.get("weight"))
        except (TypeError, ValueError):
            weight = 0
        if weight <= 0:
            issues.append(f"material_fact_weight_invalid:{fact_id}")
        for field in ("claim", "date", "decision_effect"):
            if not str(item.get(field) or "").strip():
                issues.append(f"material_fact_{field}_missing:{fact_id}")
        if not _is_concrete_url(item.get("source_url")):
            issues.append(f"material_fact_source_url_invalid:{fact_id}")
        fact_date = _iso_date(item.get("date"))
        if fact_date is None:
            issues.append(f"material_fact_date_invalid:{fact_id}")
        elif key_as_of is not None and fact_date > key_as_of:
            issues.append(f"material_fact_after_as_of:{fact_id}")
    return sorted(set(issues))


def _validate_assessment(value, expected_case):
    issues = []
    if value.get("schema_version") != ASSESSMENT_SCHEMA:
        issues.append("assessment_schema_invalid")
    if value.get("case_id") != expected_case:
        issues.append("assessment_case_mismatch")
    if value.get("blind") is not True:
        issues.append("assessment_not_blind")
    if not _is_sha256(value.get("artifact_sha256")):
        issues.append("assessment_artifact_sha256_invalid")
    if not str(value.get("assessor_id") or "").strip():
        issues.append("assessment_assessor_id_missing")
    comparison = value.get("comparison_contract")
    if not isinstance(comparison, dict):
        issues.append("comparison_contract_missing")
        comparison = {}
    else:
        for field in ("model", "as_of_date", "tool_profile"):
            if not str(comparison.get(field) or "").strip():
                issues.append(f"comparison_{field}_missing")
        if not _is_sha256(comparison.get("research_question_sha256")):
            issues.append("comparison_research_question_sha256_invalid")
        for field in ("max_tokens", "max_searches", "max_wall_seconds"):
            value_number = _nonnegative_integer(comparison.get(field))
            if value_number is None or (field != "max_searches" and value_number == 0):
                issues.append(f"comparison_{field}_invalid")
    usage = value.get("usage")
    if not isinstance(usage, dict):
        issues.append("usage_missing")
    else:
        for field in ("total_tokens", "search_count", "wall_seconds"):
            number = _nonnegative_number(usage.get(field))
            if number is None or (field == "total_tokens" and number == 0):
                issues.append(f"usage_{field}_invalid")
        budget_fields = (
            ("total_tokens", "max_tokens"),
            ("search_count", "max_searches"),
            ("wall_seconds", "max_wall_seconds"),
        )
        for usage_field, budget_field in budget_fields:
            actual = _nonnegative_number(usage.get(usage_field))
            budget = _nonnegative_number(comparison.get(budget_field))
            if actual is not None and budget is not None and actual > budget:
                issues.append(f"usage_exceeds_{budget_field}")
    metrics = value.get("metrics")
    if not isinstance(metrics, dict):
        issues.append("metrics_missing")
    else:
        for field in (
            "decision_usefulness_score", "false_source_count",
            "hypothesis_laundering_count", "material_omission_count",
        ):
            if field == "decision_usefulness_score":
                number = _nonnegative_number(metrics.get(field))
                if number is None or number > 100:
                    issues.append(f"metrics_{field}_invalid")
            elif _nonnegative_integer(metrics.get(field)) is None:
                issues.append(f"metrics_{field}_invalid")
        found = metrics.get("material_fact_ids_found")
        if not isinstance(found, list):
            issues.append("material_fact_ids_found_must_be_list")
        elif len(found) != len(set(found)) or any(not str(item).strip() for item in found):
            issues.append("material_fact_ids_found_invalid")
    return sorted(set(issues))


def _weighted_recall(key, assessment):
    found = set(assessment.get("metrics", {}).get("material_fact_ids_found", []))
    facts = key.get("material_facts", [])
    total = sum(float(item["weight"]) for item in facts)
    hit = sum(float(item["weight"]) for item in facts if item["fact_id"] in found)
    return hit / total if total else 0.0


def _contract_fingerprint(assessment):
    contract = assessment.get("comparison_contract", {})
    return {
        "case_id": assessment.get("case_id"),
        "model": contract.get("model"),
        "research_question_sha256": contract.get("research_question_sha256"),
        "as_of_date": contract.get("as_of_date"),
        "tool_profile": contract.get("tool_profile"),
        "max_tokens": contract.get("max_tokens"),
        "max_searches": contract.get("max_searches"),
        "max_wall_seconds": contract.get("max_wall_seconds"),
    }


def score(
    key, baseline, candidate, max_cost_ratio=1.5, observed_artifact_hashes=None
):
    issues = _validate_key(key)
    case_id = str(key.get("case_id") or "")
    if not case_id:
        issues.append("key_case_id_missing")
    issues.extend(f"baseline:{item}" for item in _validate_assessment(baseline, case_id))
    issues.extend(f"candidate:{item}" for item in _validate_assessment(candidate, case_id))
    baseline_contract = _contract_fingerprint(baseline)
    candidate_contract = _contract_fingerprint(candidate)
    if baseline_contract != candidate_contract:
        issues.append("comparison_contract_not_equal")
    if baseline_contract.get("research_question_sha256") != key.get(
        "research_question_sha256"
    ):
        issues.append("comparison_question_does_not_match_key")
    if baseline_contract.get("as_of_date") != key.get("as_of_date"):
        issues.append("comparison_as_of_does_not_match_key")
    if baseline.get("assessor_id") != candidate.get("assessor_id"):
        issues.append("blind_assessor_not_equal")
    if baseline.get("artifact_sha256") == candidate.get("artifact_sha256"):
        issues.append("comparison_artifacts_must_differ")
    if not isinstance(observed_artifact_hashes, dict):
        issues.append("artifact_files_not_verified")
    else:
        for label, assessment in (("baseline", baseline), ("candidate", candidate)):
            if observed_artifact_hashes.get(label) != assessment.get("artifact_sha256"):
                issues.append(f"{label}:artifact_sha256_mismatch")
    if baseline.get("variant") != "single_agent":
        issues.append("baseline_variant_must_be_single_agent")
    if candidate.get("variant") == "single_agent":
        issues.append("candidate_variant_must_differ")
    known_fact_ids = {
        str(item.get("fact_id") or "")
        for item in key.get("material_facts", []) if isinstance(item, dict)
    }
    for label, assessment in (("baseline", baseline), ("candidate", candidate)):
        metrics = assessment.get("metrics")
        metrics = metrics if isinstance(metrics, dict) else {}
        found_raw = metrics.get("material_fact_ids_found", [])
        found = set(found_raw) if isinstance(found_raw, list) else set()
        if found - known_fact_ids:
            issues.append(f"{label}:unknown_material_fact_ids")
        derived_omissions = len(known_fact_ids - found)
        declared_omissions = metrics.get("material_omission_count")
        if _nonnegative_integer(declared_omissions) != derived_omissions:
            issues.append(f"{label}:material_omission_count_mismatch")
    if issues:
        return {
            "schema_version": SUMMARY_SCHEMA,
            "case_id": case_id,
            "status": "INVALID_COMPARISON",
            "blockers": sorted(set(issues)),
        }

    baseline_recall = _weighted_recall(key, baseline)
    candidate_recall = _weighted_recall(key, candidate)
    baseline_tokens = float(baseline["usage"]["total_tokens"])
    candidate_tokens = float(candidate["usage"]["total_tokens"])
    cost_ratio = candidate_tokens / baseline_tokens if baseline_tokens else float("inf")
    baseline_usefulness = float(baseline["metrics"]["decision_usefulness_score"])
    candidate_usefulness = float(candidate["metrics"]["decision_usefulness_score"])
    blockers = []
    if candidate_recall < baseline_recall:
        blockers.append("MATERIAL_FACT_RECALL_BELOW_BASELINE")
    if candidate_usefulness <= baseline_usefulness:
        blockers.append("DECISION_USEFULNESS_NOT_IMPROVED")
    if cost_ratio > float(max_cost_ratio):
        blockers.append("COST_RATIO_EXCEEDS_UNPROVEN_METHOD_CAP")
    for field, code in (
        ("false_source_count", "FALSE_SOURCE_PRESENT"),
        ("hypothesis_laundering_count", "HYPOTHESIS_LAUNDERING_PRESENT"),
    ):
        if int(candidate["metrics"].get(field, 0) or 0) != 0:
            blockers.append(code)
    candidate_found = set(candidate["metrics"].get("material_fact_ids_found", []))
    if known_fact_ids - candidate_found:
        blockers.append("KNOWN_MATERIAL_OMISSION_PRESENT")
    return {
        "schema_version": SUMMARY_SCHEMA,
        "case_id": case_id,
        "status": "PRODUCT_VALUE_READY" if not blockers else "BLOCKED_PRODUCT_VALUE",
        "comparison_contract_sha256": _sha(baseline_contract),
        "baseline_variant": baseline.get("variant"),
        "candidate_variant": candidate.get("variant"),
        "baseline_artifact_sha256": baseline.get("artifact_sha256"),
        "candidate_artifact_sha256": candidate.get("artifact_sha256"),
        "blind_assessor_id": baseline.get("assessor_id"),
        "metrics": {
            "baseline_weighted_material_recall": round(baseline_recall, 6),
            "candidate_weighted_material_recall": round(candidate_recall, 6),
            "baseline_decision_usefulness": baseline_usefulness,
            "candidate_decision_usefulness": candidate_usefulness,
            "candidate_to_baseline_token_ratio": round(cost_ratio, 6),
            "max_cost_ratio": float(max_cost_ratio),
            "baseline_search_count": baseline["usage"]["search_count"],
            "candidate_search_count": candidate["usage"]["search_count"],
            "baseline_wall_seconds": baseline["usage"]["wall_seconds"],
            "candidate_wall_seconds": candidate["usage"]["wall_seconds"],
        },
        "blockers": blockers,
        "boundary": (
            "This gate measures material-fact recall, blind decision usefulness, safety, and "
            "cost for one comparable case. It does not measure alpha or investment returns."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--baseline-artifact", required=True, type=Path)
    parser.add_argument("--candidate-artifact", required=True, type=Path)
    parser.add_argument("--max-cost-ratio", type=float, default=1.5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.max_cost_ratio <= 0:
        raise SystemExit("--max-cost-ratio must be positive")
    result = score(
        _load(args.key), _load(args.baseline), _load(args.candidate),
        max_cost_ratio=args.max_cost_ratio,
        observed_artifact_hashes={
            "baseline": _file_sha256(args.baseline_artifact),
            "candidate": _file_sha256(args.candidate_artifact),
        },
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(0 if result["status"] == "PRODUCT_VALUE_READY" else 2)


if __name__ == "__main__":
    main()
