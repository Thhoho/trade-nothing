#!/usr/bin/env python3
"""Build a hash-bound caller report for a Codex Lead or Challenger payload.

The harness-subagent form records IDs supplied by the caller.  It is useful
provenance, but it is not an application-side attestation of context separation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid

import research_core


def _load(value):
    if os.path.isfile(value):
        with open(value, encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(value)


def build(dispatch, payload, *, agent_id, isolation, parent_agent_id="",
          harness_subagent=False):
    if not isinstance(dispatch, dict) or dispatch.get("status") != "dispatch_model":
        raise ValueError("dispatch_model_envelope_required")
    if not isinstance(payload, dict):
        raise ValueError("payload_object_required")
    prompt = str(dispatch.get("prompt") or "")
    prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    if prompt_sha256 != dispatch.get("prompt_sha256"):
        raise ValueError("dispatch_prompt_hash_mismatch")
    if harness_subagent:
        if not str(parent_agent_id or "").strip():
            raise ValueError("harness_parent_agent_id_required")
        if str(parent_agent_id).strip() == str(agent_id or "").strip():
            raise ValueError("harness_subagent_must_be_distinct")
        if str(dispatch.get("role") or "").upper() != "CHALLENGER":
            raise ValueError("harness_subagent_only_for_challenger")
        return {
            "receipt_id": f"codex-subagent-{uuid.uuid4()}",
            "status": "SUCCEEDED",
            "agent_id": str(agent_id or "").strip(),
            "parent_agent_id": str(parent_agent_id).strip(),
            "isolation": "SEPARATE_CONTEXT_REPORTED",
            "receipt_provenance": "HARNESS_SUBAGENT",
            "attestation_level": "HARNESS_REPORTED",
            "process_id": 0,
            "host_runtime": "codex-harness",
            "external_tools_enabled": False,
            "prompt_sha256": prompt_sha256,
            "payload_sha256": research_core.stable_hash(payload),
        }
    if str(isolation or "UNVERIFIED").upper() != "UNVERIFIED":
        raise ValueError("codex_manual_receipt_cannot_attest_isolation")
    return {
        "receipt_id": f"codex-{uuid.uuid4()}",
        "status": "SUCCEEDED",
        "agent_id": str(agent_id or "").strip(),
        "parent_agent_id": "",
        "isolation": "UNVERIFIED",
        "receipt_provenance": "SELF_DECLARED",
        "attestation_level": "UNVERIFIED",
        "process_id": 0,
        "host_runtime": "codex",
        "external_tools_enabled": False,
        "prompt_sha256": prompt_sha256,
        "payload_sha256": research_core.stable_hash(payload),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dispatch", required=True)
    parser.add_argument("--payload", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument(
        "--isolation", default="UNVERIFIED",
        choices=["UNVERIFIED"],
    )
    parser.add_argument("--parent-agent-id", default="")
    parser.add_argument("--harness-subagent", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    receipt = build(
        _load(args.dispatch), _load(args.payload), agent_id=args.agent_id,
        isolation=args.isolation, parent_agent_id=args.parent_agent_id,
        harness_subagent=args.harness_subagent,
    )
    rendered = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
