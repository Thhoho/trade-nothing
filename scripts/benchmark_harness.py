#!/usr/bin/env python3
"""Deterministic, leakage-aware benchmark aggregation for Trade Nothing.

The research runner receives only a suite case and its frozen evidence packet.
Blind assessment is stored separately and must bind the exact artifact hash.
This module validates those contracts and aggregates quality/cost metrics; it
does not ask the research system to score itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path, PurePosixPath


SUITE_SCHEMA = "trade-nothing.benchmark-suite.v1"
RESULT_SCHEMA = "trade-nothing.benchmark-result.v1"
ASSESSMENT_SCHEMA = "trade-nothing.benchmark-assessment.v1"
SUMMARY_SCHEMA = "trade-nothing.benchmark-summary.v1"
QUESTION_TYPES = {
    "CONJUNCTIVE", "DISJUNCTIVE", "CAUSAL_CHAIN", "COMPARATIVE", "UNIVERSE_SEARCH"
}
STATUS_VALUES = {"COMPLETE", "FAILED", "PAUSED_BUDGET", "RUNTIME_FAILURE"}
LEAKAGE_KEYS = {
    "gold", "gold_answer", "expected_answer", "expected_outcome", "major_paths",
    "future_return", "post_as_of", "rubric", "assessment",
}
COUNT_METRICS = {
    "decisive_claim_total",
    "decisive_claim_correct",
    "false_source_count",
    "major_path_total",
    "major_path_found",
    "candidate_count",
    "effective_seed_count",
    "false_opportunity_count",
    "pricing_anchor_total",
    "pricing_anchor_valid",
    "maturity_misread_count",
    "comprehension_question_total",
    "comprehension_question_correct",
    "manual_edit_count",
}
BUDGET_FIELDS = {
    "max_tokens": "tokens_total",
    "max_searches": "search_count",
    "max_wall_seconds": "wall_seconds",
}


def _load_json(path):
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return value


def _require_text(value, field):
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _iso_date(value, field):
    text = _require_text(value, field)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc
    return text


def _positive_number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{field} must be positive")
    return value


def _nonnegative_number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def _sha256(value, field):
    text = _require_text(value, field).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ValueError(f"{field} must be a 64-character sha256")
    return text


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def validate_suite(suite):
    if suite.get("schema_version") != SUITE_SCHEMA:
        raise ValueError(f"schema_version must be {SUITE_SCHEMA}")
    suite_id = _require_text(suite.get("suite_id"), "suite_id")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,63}", suite_id):
        raise ValueError("suite_id has invalid format")
    variants = suite.get("variants")
    if not isinstance(variants, list) or len(variants) < 2:
        raise ValueError("variants must contain at least two comparison arms")
    variants = [_require_text(item, "variants[]") for item in variants]
    if len(set(variants)) != len(variants):
        raise ValueError("variants must be unique")
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,31}", item) for item in variants):
        raise ValueError("variants must use lowercase letters, numbers, underscores, or hyphens")
    evidence_manifest = suite.get("evidence_manifest")
    if not isinstance(evidence_manifest, dict) or not evidence_manifest:
        raise ValueError("evidence_manifest must bind every frozen evidence packet")
    normalized_manifest = {}
    for evidence_id, entry in evidence_manifest.items():
        evidence_id = _require_text(evidence_id, "evidence_manifest key")
        if not isinstance(entry, dict):
            raise ValueError(f"evidence_manifest.{evidence_id} must be an object")
        relative_path = _require_text(entry.get("path"), f"evidence_manifest.{evidence_id}.path")
        pure_path = PurePosixPath(relative_path)
        if pure_path.is_absolute() or ".." in pure_path.parts:
            raise ValueError(f"evidence_manifest.{evidence_id}.path must remain inside suite directory")
        normalized_manifest[evidence_id] = {
            "path": relative_path,
            "sha256": _sha256(
                entry.get("sha256"), f"evidence_manifest.{evidence_id}.sha256"
            ),
        }
    cases = suite.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a non-empty list")
    ids = set()
    normalized = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"cases[{index}] must be an object")
        leaked = sorted(LEAKAGE_KEYS.intersection(key.lower() for key in _walk_keys(case)))
        if leaked:
            raise ValueError(
                f"cases[{index}] contains evaluator-only leakage keys: {', '.join(leaked)}"
            )
        case_id = _require_text(case.get("case_id"), f"cases[{index}].case_id")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,63}", case_id):
            raise ValueError(f"cases[{index}].case_id has invalid format")
        if case_id in ids:
            raise ValueError(f"duplicate case_id: {case_id}")
        ids.add(case_id)
        question_type = _require_text(
            case.get("question_type"), f"cases[{index}].question_type"
        ).upper()
        if question_type not in QUESTION_TYPES:
            raise ValueError(f"cases[{index}].question_type is unsupported")
        budget = case.get("budget")
        if not isinstance(budget, dict):
            raise ValueError(f"cases[{index}].budget must be an object")
        normalized_budget = {
            field: _positive_number(budget.get(field), f"cases[{index}].budget.{field}")
            for field in BUDGET_FIELDS
        }
        frozen_evidence = case.get("frozen_evidence")
        if not isinstance(frozen_evidence, list) or not frozen_evidence:
            raise ValueError(f"cases[{index}].frozen_evidence must be a non-empty list")
        evidence_ids = [_require_text(item, "frozen_evidence[]") for item in frozen_evidence]
        missing_evidence = sorted(set(evidence_ids) - set(normalized_manifest))
        if missing_evidence:
            raise ValueError(
                f"cases[{index}] references evidence missing from manifest: "
                + ", ".join(missing_evidence)
            )
        normalized.append({
            **case,
            "case_id": case_id,
            "question_type": question_type,
            "as_of": _iso_date(case.get("as_of"), f"cases[{index}].as_of"),
            "prompt": _require_text(case.get("prompt"), f"cases[{index}].prompt"),
            "budget": normalized_budget,
            "frozen_evidence": evidence_ids,
        })
    unused_evidence = sorted(
        set(normalized_manifest)
        - {evidence_id for case in normalized for evidence_id in case["frozen_evidence"]}
    )
    if unused_evidence:
        raise ValueError("evidence_manifest contains unused packets: " + ", ".join(unused_evidence))
    contract = {
        "schema_version": SUITE_SCHEMA,
        "suite_id": suite_id,
        "variants": variants,
        "cases": normalized,
        "evidence_manifest": normalized_manifest,
    }
    suite_contract_sha256 = hashlib.sha256(
        json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return {
        **suite,
        "suite_id": suite_id,
        "variants": variants,
        "cases": normalized,
        "evidence_manifest": normalized_manifest,
        "suite_contract_sha256": suite_contract_sha256,
    }


def validate_evidence_files(suite, suite_path):
    suite = validate_suite(suite)
    root = Path(suite_path).resolve().parent
    packet_dates = {}
    for case in suite["cases"]:
        for evidence_id in case["frozen_evidence"]:
            previous = packet_dates.get(evidence_id)
            if previous is not None and previous != case["as_of"]:
                raise ValueError(f"evidence packet {evidence_id} is shared across different as_of dates")
            packet_dates[evidence_id] = case["as_of"]
    for evidence_id, entry in suite["evidence_manifest"].items():
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"evidence packet escapes suite directory: {evidence_id}")
        if not path.is_file():
            raise ValueError(f"evidence packet is missing: {evidence_id}")
        if _artifact_hash(path) != entry["sha256"]:
            raise ValueError(f"evidence packet hash mismatch: {evidence_id}")
        packet = _load_json(path)
        if packet.get("packet_id") != evidence_id:
            raise ValueError(f"evidence packet_id mismatch: {evidence_id}")
        packet_as_of = _iso_date(packet.get("as_of"), f"{evidence_id}.as_of")
        if packet_as_of != packet_dates[evidence_id]:
            raise ValueError(f"evidence packet as_of does not match suite case: {evidence_id}")
        for index, source in enumerate(packet.get("sources") or []):
            if not isinstance(source, dict):
                raise ValueError(f"{evidence_id}.sources[{index}] must be an object")
            source_date = _iso_date(
                source.get("date"), f"{evidence_id}.sources[{index}].date"
            )
            if source_date > packet_as_of:
                raise ValueError(f"post-as-of source in evidence packet: {evidence_id}")
    return suite


def validate_result(result, case, variants, suite_contract_sha256):
    if result.get("schema_version") != RESULT_SCHEMA:
        raise ValueError(f"result schema_version must be {RESULT_SCHEMA}")
    case_id = _require_text(result.get("case_id"), "result.case_id")
    variant = _require_text(result.get("variant"), "result.variant")
    if case_id != case["case_id"]:
        raise ValueError("result.case_id does not match suite case")
    if variant not in variants:
        raise ValueError(f"result.variant is not declared in suite: {variant}")
    bound_suite = _sha256(result.get("suite_contract_sha256"), "result.suite_contract_sha256")
    if bound_suite != suite_contract_sha256:
        raise ValueError("result is not bound to the exact suite/evidence contract")
    status = _require_text(result.get("completion_status"), "result.completion_status").upper()
    if status not in STATUS_VALUES:
        raise ValueError(f"unsupported completion_status: {status}")
    if "assessment" in result:
        raise ValueError("research result must not contain its own assessment")
    usage = result.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("result.usage must be an object")
    normalized_usage = {
        "tokens_total": _nonnegative_number(usage.get("tokens_total"), "usage.tokens_total"),
        "search_count": _nonnegative_number(usage.get("search_count"), "usage.search_count"),
        "wall_seconds": _nonnegative_number(usage.get("wall_seconds"), "usage.wall_seconds"),
    }
    return {
        **result,
        "case_id": case_id,
        "variant": variant,
        "suite_contract_sha256": bound_suite,
        "completion_status": status,
        "execution_id": _require_text(result.get("execution_id"), "result.execution_id"),
        "engine_version": _require_text(result.get("engine_version"), "result.engine_version"),
        "artifact_path": _require_text(result.get("artifact_path"), "result.artifact_path"),
        "artifact_sha256": _sha256(result.get("artifact_sha256"), "result.artifact_sha256"),
        "usage": normalized_usage,
        "recovery_count": int(_nonnegative_number(
            result.get("recovery_count", 0), "result.recovery_count"
        )),
    }


def validate_assessment(assessment, result):
    if assessment.get("schema_version") != ASSESSMENT_SCHEMA:
        raise ValueError(f"assessment schema_version must be {ASSESSMENT_SCHEMA}")
    if assessment.get("case_id") != result["case_id"]:
        raise ValueError("assessment.case_id does not match result")
    if assessment.get("variant") != result["variant"]:
        raise ValueError("assessment.variant does not match result")
    if assessment.get("blind") is not True:
        raise ValueError("assessment.blind must be true")
    _require_text(assessment.get("assessor_id"), "assessment.assessor_id")
    bound_hash = _sha256(assessment.get("artifact_sha256"), "assessment.artifact_sha256")
    if bound_hash != result["artifact_sha256"]:
        raise ValueError("assessment is not bound to the exact result artifact")
    metrics = assessment.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("assessment.metrics must be an object")
    normalized = {
        field: int(_nonnegative_number(metrics.get(field), f"assessment.metrics.{field}"))
        for field in COUNT_METRICS
    }
    pairs = (
        ("decisive_claim_correct", "decisive_claim_total"),
        ("major_path_found", "major_path_total"),
        ("effective_seed_count", "candidate_count"),
        ("false_opportunity_count", "candidate_count"),
        ("pricing_anchor_valid", "pricing_anchor_total"),
        ("comprehension_question_correct", "comprehension_question_total"),
    )
    for numerator, denominator in pairs:
        if normalized[numerator] > normalized[denominator]:
            raise ValueError(f"{numerator} cannot exceed {denominator}")
    return {**assessment, "artifact_sha256": bound_hash, "metrics": normalized}


def _ratio(numerator, denominator):
    return round(numerator / denominator, 6) if denominator else None


def _artifact_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def score_suite(suite, results_dir):
    suite = validate_suite(suite)
    root = Path(results_dir).resolve()
    rows = []
    errors = []
    case_map = {case["case_id"]: case for case in suite["cases"]}
    for case in suite["cases"]:
        for variant in suite["variants"]:
            stem = f"{case['case_id']}__{variant}"
            result_path = root / f"{stem}.result.json"
            assessment_path = root / f"{stem}.assessment.json"
            if not result_path.is_file() or not assessment_path.is_file():
                errors.append(f"missing result/assessment pair: {stem}")
                continue
            try:
                result = validate_result(
                    _load_json(result_path), case, suite["variants"],
                    suite["suite_contract_sha256"],
                )
                artifact_path = Path(result["artifact_path"])
                if not artifact_path.is_absolute():
                    artifact_path = result_path.parent / artifact_path
                artifact_path = artifact_path.resolve()
                if not artifact_path.is_relative_to(root):
                    raise ValueError("bound artifact must remain inside results-dir")
                if not artifact_path.is_file():
                    raise ValueError(f"bound artifact is missing: {artifact_path}")
                actual_artifact_hash = _artifact_hash(artifact_path)
                if actual_artifact_hash != result["artifact_sha256"]:
                    raise ValueError("result.artifact_sha256 does not match the bound artifact file")
                assessment = validate_assessment(_load_json(assessment_path), result)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                errors.append(f"{stem}: {exc}")
                continue
            budget_errors = []
            for cap_field, usage_field in BUDGET_FIELDS.items():
                if result["usage"][usage_field] > case["budget"][cap_field]:
                    budget_errors.append(
                        f"{usage_field}={result['usage'][usage_field]} exceeds "
                        f"{cap_field}={case['budget'][cap_field]}"
                    )
            if result["completion_status"] != "COMPLETE":
                errors.append(
                    f"{stem}: completion_status={result['completion_status']} is not comparable"
                )
            for budget_error in budget_errors:
                errors.append(f"{stem}: {budget_error}")
            rows.append({
                "case_id": case["case_id"],
                "question_type": case["question_type"],
                "variant": variant,
                "completion_status": result["completion_status"],
                "artifact_sha256": result["artifact_sha256"],
                "artifact_path": str(artifact_path),
                "usage": result["usage"],
                "recovery_count": result["recovery_count"],
                "metrics": assessment["metrics"],
                "within_budget": not budget_errors,
                "budget_errors": budget_errors,
                "comparable": result["completion_status"] == "COMPLETE" and not budget_errors,
            })

    aggregates = {}
    for variant in suite["variants"]:
        selected = [row for row in rows if row["variant"] == variant]
        totals = defaultdict(int)
        for row in selected:
            for field, value in row["metrics"].items():
                totals[field] += value
            for field, value in row["usage"].items():
                totals[field] += value
            totals["recovery_count"] += row["recovery_count"]
        effective = totals["effective_seed_count"]
        aggregates[variant] = {
            "case_count": len(selected),
            "complete_count": sum(row["completion_status"] == "COMPLETE" for row in selected),
            "comparable_count": sum(row["comparable"] for row in selected),
            "completion_rate": _ratio(
                sum(row["completion_status"] == "COMPLETE" for row in selected), len(selected)
            ),
            "claim_precision": _ratio(
                totals["decisive_claim_correct"], totals["decisive_claim_total"]
            ),
            "major_path_coverage": _ratio(
                totals["major_path_found"], totals["major_path_total"]
            ),
            "false_opportunity_rate": _ratio(
                totals["false_opportunity_count"], totals["candidate_count"]
            ),
            "pricing_anchor_valid_rate": _ratio(
                totals["pricing_anchor_valid"], totals["pricing_anchor_total"]
            ),
            "maturity_misread_rate": _ratio(
                totals["maturity_misread_count"], totals["candidate_count"]
            ),
            "comprehension_rate": _ratio(
                totals["comprehension_question_correct"],
                totals["comprehension_question_total"],
            ),
            "tokens_per_effective_seed": _ratio(totals["tokens_total"], effective),
            "wall_seconds_per_effective_seed": _ratio(totals["wall_seconds"], effective),
            "totals": dict(sorted(totals.items())),
        }
    expected_pairs = len(case_map) * len(suite["variants"])
    return {
        "schema_version": SUMMARY_SCHEMA,
        "suite_id": _require_text(suite.get("suite_id"), "suite_id"),
        "expected_case_variant_pairs": expected_pairs,
        "observed_case_variant_pairs": len(rows),
        "comparison_ready": (
            not errors
            and len(rows) == expected_pairs
            and all(row["comparable"] for row in rows)
        ),
        "errors": errors,
        "rows": rows,
        "aggregates": aggregates,
    }


def render_markdown(summary):
    lines = [
        f"# Benchmark Summary — {summary['suite_id']}",
        "",
        f"- Comparison ready: **{str(summary['comparison_ready']).upper()}**",
        f"- Complete pairs: {summary['observed_case_variant_pairs']} / "
        f"{summary['expected_case_variant_pairs']}",
        "- These metrics compare research process quality under frozen as-of evidence; they are not "
        "probabilities, expected returns, or trade signals.",
        "",
        "| Variant | Completion | Claim precision | Path coverage | False opportunity | "
        "Pricing valid | Maturity misread | 60s comprehension | Tokens / effective seed |",
        "|:---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def pct(value):
        return "—" if value is None else f"{value * 100:.1f}%"

    for variant, item in summary["aggregates"].items():
        tokens = item["tokens_per_effective_seed"]
        lines.append(
            f"| {variant} | {pct(item['completion_rate'])} | {pct(item['claim_precision'])} | "
            f"{pct(item['major_path_coverage'])} | {pct(item['false_opportunity_rate'])} | "
            f"{pct(item['pricing_anchor_valid_rate'])} | {pct(item['maturity_misread_rate'])} | "
            f"{pct(item['comprehension_rate'])} | {('—' if tokens is None else f'{tokens:.0f}')} |"
        )
    if summary["errors"]:
        lines.extend(["", "## Blocking errors"])
        lines.extend(f"- {error}" for error in summary["errors"])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Validate and score frozen Trade Nothing cases.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate_cmd = sub.add_parser("validate-suite")
    validate_cmd.add_argument("--suite", required=True)
    score_cmd = sub.add_parser("score")
    score_cmd.add_argument("--suite", required=True)
    score_cmd.add_argument("--results-dir", required=True)
    score_cmd.add_argument("--output-json", required=True)
    score_cmd.add_argument("--output-md", required=True)
    args = parser.parse_args()

    suite = validate_evidence_files(_load_json(args.suite), args.suite)
    if args.command == "validate-suite":
        print(json.dumps({
            "status": "VALID",
            "suite_id": suite.get("suite_id"),
            "case_count": len(suite["cases"]),
            "variants": suite["variants"],
            "suite_contract_sha256": suite["suite_contract_sha256"],
        }, ensure_ascii=False, indent=2))
        return
    summary = score_suite(suite, args.results_dir)
    with open(args.output_json, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with open(args.output_md, "w", encoding="utf-8") as handle:
        handle.write(render_markdown(summary))
    print(json.dumps({
        "status": "READY" if summary["comparison_ready"] else "BLOCKED",
        "output_json": args.output_json,
        "output_md": args.output_md,
        "errors": summary["errors"],
    }, ensure_ascii=False, indent=2))
    if not summary["comparison_ready"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
