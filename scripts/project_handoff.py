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


HANDOFF_SCHEMA = "trade-nothing.deepthink2.project-handoff.v1"
INTEGRITY_SCHEMA = "trade-nothing.project-handoff-integrity.v1"
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
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_handoff(
    state: dict[str, Any],
    *,
    source_state_path: str = "",
    source_report_path: str = "",
) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise ValueError("state must be a JSON object")
    for field in ("topic", "decision_question", "question_type", "logic_graph", "cruxes"):
        if not state.get(field):
            raise ValueError(f"state.{field} is required")
    traces = [item for item in state.get("decision_trace", []) if isinstance(item, dict)]
    if not traces:
        raise ValueError("state.decision_trace with a final entry is required")

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
    parser.add_argument("--output", required=True, help="New handoff JSON path")
    parser.add_argument("--report-path", default="", help="Optional report path for audit only")
    parser.add_argument("--force", action="store_true", help="Replace an existing regular output file")
    args = parser.parse_args()

    state_path = Path(args.state).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if not state_path.is_file():
        raise ValueError(f"state file does not exist: {state_path}")
    if output_path == state_path:
        raise ValueError("output must not overwrite the source state")

    state = json.loads(state_path.read_text(encoding="utf-8"))
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
