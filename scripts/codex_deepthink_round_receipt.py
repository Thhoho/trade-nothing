#!/usr/bin/env python3
"""Bind the adaptively planned Codex agents to one deepthink2 round."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import execution_integrity


def _load(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--round", required=True, type=int)
    parser.add_argument("--dispatch", required=True, type=Path)
    parser.add_argument("--detective", type=Path)
    parser.add_argument("--inquisitor", type=Path)
    parser.add_argument("--judge", type=Path)
    parser.add_argument("--detective-agent-id", default="")
    parser.add_argument("--inquisitor-agent-id", default="")
    parser.add_argument("--judge-agent-id", default="")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    dispatch = _load(args.dispatch)
    planned_roles = execution_integrity.required_roles(dispatch)
    paths = {
        "detective": args.detective,
        "inquisitor": args.inquisitor,
        "judge": args.judge,
    }
    missing = [role for role in planned_roles if paths.get(role) is None]
    if missing:
        raise ValueError("missing payload paths for planned roles: " + ",".join(missing))
    payloads = {
        role: (
            _load(paths[role]) if paths.get(role) is not None
            else {"_execution": {"status": "SKIPPED", "role": role}}
        )
        for role in ("detective", "inquisitor", "judge")
    }
    receipt = execution_integrity.build_codex_receipt(
        args.round,
        dispatch,
        payloads,
        {
            "detective": args.detective_agent_id,
            "inquisitor": args.inquisitor_agent_id,
            "judge": args.judge_agent_id,
        },
    )
    validation = execution_integrity.validate_round_receipt(
        receipt, args.round, dispatch,
        payloads["detective"], payloads["inquisitor"], payloads["judge"],
    )
    if validation["status"] != "verified":
        raise ValueError("generated receipt is invalid: " + ",".join(validation["blockers"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": "receipt_written",
        "receipt_id": receipt["receipt_id"],
        "path": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
