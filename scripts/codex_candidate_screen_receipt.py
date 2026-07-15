#!/usr/bin/env python3
"""Bind completed Codex collaboration-agent outputs to a CandidateScreen dispatch.

This helper does not launch agents and cannot prove host events occurred.  The caller
must pass the canonical agent IDs returned by the Codex collaboration host.  It only
builds the deterministic, hash-bound receipt consumed by candidate_screen_engine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import candidate_screen_engine


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def build_receipt(dispatch: dict, analyst: dict, skeptic: dict, analyst_agent_id: str,
                  skeptic_agent_id: str) -> dict:
    agent_ids = [analyst_agent_id.strip(), skeptic_agent_id.strip()]
    if not all(agent_ids) or len(set(agent_ids)) != 2:
        raise ValueError("two distinct non-empty canonical agent IDs are required")
    receipt = {
        "schema": "candidate-screen-isolation.v1",
        "runner_kind": "codex_collaboration_v1",
        "host_enforced": True,
        "dispatch_id": dispatch["dispatch_id"],
        "as_of_date": dispatch["as_of_date"],
        "candidate_seed_ids": dispatch["candidate_seed_ids"],
        "roles": {},
    }
    for role, payload, agent_id in (
        ("analyst", analyst, agent_ids[0]),
        ("skeptic", skeptic, agent_ids[1]),
    ):
        prompt = dispatch[f"{role}_prompt"]
        receipt["roles"][role] = {
            "invocation_id": agent_id,
            "agent_id": agent_id,
            "context_isolation": "independent_agent_context",
            "status": "completed",
            "timed_out": False,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "payload_sha256": candidate_screen_engine.payload_sha256(payload),
        }
    receipt["receipt_id"] = candidate_screen_engine.isolation_receipt_id(receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dispatch", required=True, type=Path)
    parser.add_argument("--analyst", required=True, type=Path)
    parser.add_argument("--skeptic", required=True, type=Path)
    parser.add_argument("--analyst-agent-id", required=True)
    parser.add_argument("--skeptic-agent-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    receipt = build_receipt(
        _load(args.dispatch), _load(args.analyst), _load(args.skeptic),
        args.analyst_agent_id, args.skeptic_agent_id,
    )
    rendered = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    raw = rendered.encode("utf-8")
    print(json.dumps({
        "status": "receipt_written",
        "receipt_id": receipt["receipt_id"],
        "path": str(args.output),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
