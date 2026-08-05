#!/usr/bin/env python3
"""Bind a completed Codex agent output to a Claim Verifier dispatch."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import candidate_screen_engine
import claim_verification_engine


def _load(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def build_receipt(dispatch, verifier, agent_id):
    agent_id = str(agent_id or "").strip()
    if not agent_id:
        raise ValueError("a non-empty canonical Codex agent ID is required")
    prompt = str(dispatch.get("verifier_prompt") or "")
    if not prompt:
        raise ValueError("dispatch verifier_prompt is required")
    receipt = {
        "schema": "claim-verifier-isolation.v1",
        "runner_kind": "codex_collaboration_v1",
        "host_enforced": True,
        "dispatch_id": dispatch["dispatch_id"],
        "claim_ids": dispatch["claim_ids"],
        "snapshot_ids": dispatch["snapshot_ids"],
        "verifier": {
            "invocation_id": agent_id,
            "agent_id": agent_id,
            "context_isolation": "independent_agent_context",
            "status": "completed",
            "timed_out": False,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "payload_sha256": candidate_screen_engine.payload_sha256(verifier),
        },
    }
    receipt["receipt_id"] = claim_verification_engine.isolation_receipt_id(receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dispatch", required=True, type=Path)
    parser.add_argument("--verifier", required=True, type=Path)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = build_receipt(
        _load(args.dispatch), _load(args.verifier), args.agent_id
    )
    rendered = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "status": "receipt_written",
        "receipt_id": receipt["receipt_id"],
        "path": str(args.output),
        "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
