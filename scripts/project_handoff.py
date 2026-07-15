#!/usr/bin/env python3
"""Export a compact, checksummed state for tradenothing-next.

The handoff deliberately excludes research rounds and raw role transcripts. It
does not promote a candidate, choose Lessons, or authenticate the publisher.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


HANDOFF_SCHEMA = "trade-nothing.deepthink2.project-handoff.v2"
INTEGRITY_SCHEMA = "trade-nothing.project-handoff-integrity.v1"
PREFLIGHT_SCHEMA = "trade-nothing.project-handoff-preflight.v1"
QUESTION_TYPES = {
    "CONJUNCTIVE",
    "DISJUNCTIVE",
    "CAUSAL_CHAIN",
    "COMPARATIVE",
    "UNIVERSE_SEARCH",
}
EDGE_STATES = {"EDGE_FOUND", "NO_EDGE", "INSUFFICIENT_EVIDENCE"}
EVIDENCE_DIRECTIONS = {"BULL", "BEAR", "MIXED", "UNDETERMINED"}
ACTIONABILITY_STATES = {"NONE", "MONITOR", "READY_FOR_SCREENING"}
STATE_FIELDS = (
    "topic",
    "decision_question",
    "question_type",
    "horizon",
    "logic_graph",
    "landscape_map",
    "frame_contract",
    "research_verdict",
    "last_convergence",
    "opportunity_seeds",
    "candidate_screens",
    "claim_verifications",
    "runtime_contract",
    "research_start_context",
    "method_identity",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_handoff(
    state: dict[str, Any],
    *,
    source_state_path: str = "",
    source_report_path: str = "",
) -> dict[str, Any]:
    preflight = preflight_handoff(state)
    if not preflight["exportable"]:
        details = "; ".join(
            f"{item['code']} ({item['path']}): {item['message']}"
            for item in preflight["blockers"]
        )
        raise ValueError(f"handoff preflight blocked: {details}")
    assert isinstance(state, dict)
    traces = [item for item in state.get("decision_trace", []) if isinstance(item, dict)]

    compact = {field: copy.deepcopy(state.get(field)) for field in STATE_FIELDS}
    compact["decision_trace"] = [_compact_trace(traces[-1])]
    compact["cruxes"] = _compact_cruxes(state["cruxes"])
    runtime = state.get("runtime") if isinstance(state.get("runtime"), dict) else {}
    run_id = str(runtime.get("run_id") or "")
    if not re.fullmatch(r"RUN-[0-9]{8}-[A-F0-9]{12}", run_id):
        raise ValueError("state.runtime.run_id is missing or invalid")
    compact["runtime"] = {"run_id": run_id}

    state_sha256 = hashlib.sha256(canonical_json(compact).encode("utf-8")).hexdigest()
    external_run_id = compact["runtime"]["run_id"]
    return {
        "source_system": "trade-nothing",
        "schema_version": HANDOFF_SCHEMA,
        "source_state_path": source_state_path,
        "source_report_path": source_report_path,
        "external_run_id": external_run_id,
        "lesson_injections": [],
        "state": compact,
        "handoff_integrity": {
            "schema_version": INTEGRITY_SCHEMA,
            "state_sha256": state_sha256,
            "excluded_fields": [
                "rounds",
                "candidate_screen_dispatches",
                "raw_role_payloads",
                "search_logs",
            ],
            "claim": "transfer_checksum_not_source_authentication",
        },
    }


def preflight_handoff(state: Any) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def block(code: str, path: str, message: str) -> None:
        blockers.append({"code": code, "path": path, "message": message})

    def warn(code: str, path: str, message: str) -> None:
        warnings.append({"code": code, "path": path, "message": message})

    if not isinstance(state, dict):
        block("STATE_NOT_OBJECT", "state", "state must be a JSON object")
        return _preflight_result(blockers, warnings)

    method = state.get("method_identity")
    if not isinstance(method, dict):
        block(
            "METHOD_IDENTITY_MISSING",
            "state.method_identity",
            "new effect samples require a method identity pinned when the run starts",
        )
    else:
        if method.get("schema_version") != "trade-nothing.method-identity.v1":
            block(
                "METHOD_IDENTITY_SCHEMA_INVALID",
                "state.method_identity.schema_version",
                "method identity schema is invalid",
            )
        if method.get("scope") != "operational-bundle.v1":
            block(
                "METHOD_IDENTITY_SCOPE_INVALID",
                "state.method_identity.scope",
                "method identity scope is invalid",
            )
        if not re.fullmatch(r"[0-9a-f]{64}", str(method.get("contract_sha256") or "")):
            block(
                "METHOD_CONTRACT_HASH_INVALID",
                "state.method_identity.contract_sha256",
                "method contract hash must be a lowercase SHA-256",
            )
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(method.get("method_version") or "")):
            block(
                "METHOD_VERSION_INVALID",
                "state.method_identity.method_version",
                "method version must be semantic x.y.z",
            )
        if not isinstance(method.get("file_count"), int) or method.get("file_count", 0) <= 0:
            block(
                "METHOD_FILE_COUNT_INVALID",
                "state.method_identity.file_count",
                "method identity must bind at least one operational file",
            )

    for field in ("topic", "decision_question"):
        if not str(state.get(field) or "").strip():
            block("REQUIRED_FIELD_MISSING", f"state.{field}", f"{field} is required")

    question_type = str(state.get("question_type") or "").upper()
    if question_type not in QUESTION_TYPES:
        block(
            "QUESTION_TYPE_INVALID",
            "state.question_type",
            "question_type must use the current question-aware contract",
        )

    logic_graph = state.get("logic_graph")
    if not isinstance(logic_graph, dict) or not str(logic_graph.get("root_id") or "").strip():
        block(
            "LOGIC_GRAPH_INVALID",
            "state.logic_graph",
            "logic_graph with root_id is required",
        )

    cruxes = state.get("cruxes")
    if not isinstance(cruxes, dict) or not cruxes:
        block("CRUX_LEDGER_INVALID", "state.cruxes", "cruxes must be a non-empty object")
    elif isinstance(logic_graph, dict):
        invalid_cruxes = sorted(
            str(crux_id) for crux_id, value in cruxes.items() if not isinstance(value, dict)
        )
        if invalid_cruxes:
            block(
                "CRUX_ENTRY_INVALID",
                "state.cruxes",
                "crux entries must be objects: " + ", ".join(invalid_cruxes),
            )
        graph_nodes = {
            str(item.get("id") or "")
            for item in logic_graph.get("nodes", [])
            if isinstance(item, dict)
        }
        missing_nodes = sorted(str(crux_id) for crux_id in cruxes if str(crux_id) not in graph_nodes)
        if missing_nodes:
            block(
                "CRUX_NODES_MISSING",
                "state.logic_graph.nodes",
                "logic_graph is missing crux nodes: " + ", ".join(missing_nodes),
            )

    traces = state.get("decision_trace")
    final_trace = traces[-1] if isinstance(traces, list) and traces else None
    if not isinstance(final_trace, dict):
        block(
            "FINAL_TRACE_MISSING",
            "state.decision_trace",
            "decision_trace with a final object is required",
        )
    else:
        decision = str(final_trace.get("decision") or "")
        if "AVOID" in decision.upper():
            block(
                "LEGACY_AVOID_SEMANTICS",
                "state.decision_trace[-1].decision",
                "NO_EDGE / AVOID is forbidden; NO_EDGE is not a short or avoidance signal",
            )
        expected_aggregation = (
            "WEAKEST_NECESSARY_CRUX"
            if question_type in {"CONJUNCTIVE", "CAUSAL_CHAIN"}
            else "LOGIC_GRAPH_MULTI_PATH"
        )
        if question_type in QUESTION_TYPES and str(final_trace.get("aggregation_rule") or "").upper() != expected_aggregation:
            block(
                "AGGREGATION_RULE_INVALID",
                "state.decision_trace[-1].aggregation_rule",
                f"aggregation_rule must be {expected_aggregation} for {question_type}",
            )
        verdict = final_trace.get("research_verdict") or state.get("research_verdict")
        if not isinstance(verdict, dict) or not all(
            str(verdict.get(field) or "").strip()
            for field in ("edge_state", "evidence_direction", "actionability")
        ):
            block(
                "THREE_AXIS_VERDICT_MISSING",
                "state.decision_trace[-1].research_verdict",
                "edge_state, evidence_direction, and actionability are required",
            )
        else:
            invalid_verdict_fields = []
            if str(verdict.get("edge_state") or "").upper() not in EDGE_STATES:
                invalid_verdict_fields.append("edge_state")
            if str(verdict.get("evidence_direction") or "").upper() not in EVIDENCE_DIRECTIONS:
                invalid_verdict_fields.append("evidence_direction")
            if str(verdict.get("actionability") or "").upper() not in ACTIONABILITY_STATES:
                invalid_verdict_fields.append("actionability")
            if invalid_verdict_fields:
                block(
                    "THREE_AXIS_VERDICT_INVALID",
                    "state.decision_trace[-1].research_verdict",
                    "invalid verdict fields: " + ", ".join(invalid_verdict_fields),
                )
            crux_roles = {
                str(value.get("logic_role") or "").upper()
                for value in (cruxes or {}).values()
                if isinstance(value, dict)
            }
            edge_state = str(verdict.get("edge_state") or "").upper()
            actionability = str(verdict.get("actionability") or "").upper()
            if edge_state == "EDGE_FOUND" and "PRICING" not in crux_roles:
                block(
                    "PRICING_CRUX_MISSING",
                    "state.cruxes",
                    "EDGE_FOUND requires an explicit PRICING crux",
                )
            if question_type == "UNIVERSE_SEARCH" and not {
                "OPPORTUNITY_PATH",
                "PRICING",
            }.issubset(crux_roles):
                block(
                    "UNIVERSE_CRUX_ROLES_MISSING",
                    "state.cruxes",
                    "UNIVERSE_SEARCH requires OPPORTUNITY_PATH and PRICING cruxes",
                )
            convergence = state.get("last_convergence")
            convergence_decision = (
                str(convergence.get("decision") or "").lower()
                if isinstance(convergence, dict)
                else ""
            )
            if actionability == "READY_FOR_SCREENING" and convergence_decision != "converge":
                block(
                    "SCREENING_WITHOUT_CONVERGENCE",
                    "state.last_convergence",
                    "READY_FOR_SCREENING requires a converged research run",
                )

    for field in ("opportunity_seeds", "candidate_screens", "claim_verifications"):
        if not isinstance(state.get(field, []), list):
            block(
                "COLLECTION_FIELD_INVALID",
                f"state.{field}",
                f"{field} must be a list",
            )
    for field in ("frame_contract", "last_convergence"):
        if state.get(field) is not None and not isinstance(state.get(field), dict):
            block(
                "OBJECT_FIELD_INVALID",
                f"state.{field}",
                f"{field} must be an object",
            )

    runtime = state.get("runtime") if isinstance(state.get("runtime"), dict) else {}
    run_id = str(runtime.get("run_id") or "")
    if not re.fullmatch(r"RUN-[0-9]{8}-[A-F0-9]{12}", run_id):
        block(
            "RUN_ID_INVALID",
            "state.runtime.run_id",
            "immutable run_id RUN-YYYYMMDD-XXXXXXXXXXXX is required",
        )

    runtime_contract = (
        state.get("runtime_contract")
        if isinstance(state.get("runtime_contract"), dict)
        else {}
    )
    if str(runtime_contract.get("isolation_status") or "").lower() != "verified":
        warn(
            "RUNTIME_ISOLATION_NOT_VERIFIED",
            "state.runtime_contract.isolation_status",
            "research may be imported for audit, but isolation-dependent candidate maturity remains blocked",
        )
    if question_type in {"UNIVERSE_SEARCH", "COMPARATIVE"} and not isinstance(
        state.get("landscape_map"), dict
    ):
        warn(
            "LANDSCAPE_MAP_MISSING",
            "state.landscape_map",
            "opportunity-oriented states should include the current Landscape Map coverage ledger",
        )
    return _preflight_result(blockers, warnings)


def _preflight_result(
    blockers: list[dict[str, str]], warnings: list[dict[str, str]]
) -> dict[str, Any]:
    return {
        "schema_version": PREFLIGHT_SCHEMA,
        "status": "PASSED" if not blockers else "BLOCKED",
        "exportable": not blockers,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "instruction": (
            "Export with --output; warnings remain visible to the product."
            if not blockers
            else "Do not patch historical evidence in place; rerun or explicitly preserve it as audit-only history."
        ),
    }


def _compact_trace(trace: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(trace.get(key))
        for key in (
            "round",
            "focus_crux",
            "weakest",
            "support_weakest",
            "support_mean",
            "decision",
            "aggregation_rule",
            "research_verdict",
        )
    }


def _compact_cruxes(raw_cruxes: Any) -> dict[str, Any]:
    if not isinstance(raw_cruxes, dict) or not raw_cruxes:
        raise ValueError("state.cruxes must be a non-empty object")
    result = {}
    for crux_id, raw in raw_cruxes.items():
        if not isinstance(raw, dict):
            raise ValueError(f"crux {crux_id} must be an object")
        history = raw.get("p_history") if isinstance(raw.get("p_history"), list) else []
        result[str(crux_id)] = {
            key: copy.deepcopy(raw.get(key))
            for key in (
                "label",
                "definition",
                "logic_role",
                "status",
                "monitor_anchor",
                "falsifier",
                "catalyst_window",
                "best_bull",
                "best_bear",
                "citations",
            )
        }
        result[str(crux_id)]["p_history"] = history[-1:] if history else []
    return result


def write_handoff(payload: dict[str, Any], output_path: Path, *, force: bool = False) -> None:
    requested_path = output_path.expanduser()
    if requested_path.is_symlink():
        raise ValueError("refusing to write through an output symlink")
    output_path = requested_path.parent.resolve() / requested_path.name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if force:
            if output_path.is_symlink():
                raise ValueError("refusing to replace an output symlink")
            os.replace(temporary, output_path)
        else:
            try:
                os.link(temporary, output_path)
            except FileExistsError as exc:
                raise ValueError(f"output already exists: {output_path}") from exc
            temporary.unlink()
            temporary = None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, help="Source deepthink2 state JSON")
    parser.add_argument("--output", help="New handoff JSON path")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Print all handoff blockers/warnings without writing an output",
    )
    parser.add_argument("--report-path", default="", help="Optional report path for audit only")
    parser.add_argument("--force", action="store_true", help="Replace an existing regular output file")
    args = parser.parse_args()

    state_path = Path(args.state).expanduser().resolve()
    if not state_path.is_file():
        raise ValueError(f"state file does not exist: {state_path}")

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assessment = preflight_handoff(state)
    if args.check:
        print(json.dumps(assessment, ensure_ascii=False, indent=2))
        return 0 if assessment["exportable"] else 2
    if not args.output:
        parser.error("--output is required unless --check is used")
    output_path = Path(args.output).expanduser().resolve()
    if output_path == state_path:
        raise ValueError("output must not overwrite the source state")
    payload = build_handoff(
        state,
        source_state_path=str(state_path),
        source_report_path=str(Path(args.report_path).expanduser().resolve()) if args.report_path else "",
    )
    write_handoff(payload, output_path, force=args.force)
    print(json.dumps({
        "status": "EXPORTED",
        "output": str(output_path),
        "state_sha256": payload["handoff_integrity"]["state_sha256"],
        "candidate_count": len(payload["state"].get("opportunity_seeds") or []),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
