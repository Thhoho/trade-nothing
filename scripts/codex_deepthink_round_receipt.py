#!/usr/bin/env python3
"""Bind three completed Codex collaboration agents to one deepthink2 round."""
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
    parser.add_argument("--detective", required=True, type=Path)
    parser.add_argument("--inquisitor", required=True, type=Path)
    parser.add_argument("--judge", required=True, type=Path)
    parser.add_argument("--detective-agent-id", required=True)
    parser.add_argument("--inquisitor-agent-id", required=True)
    parser.add_argument("--judge-agent-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    dispatch = _load(args.dispatch)
    payloads = {
        "detective": _load(args.detective),
        "inquisitor": _load(args.inquisitor),
        "judge": _load(args.judge),
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
