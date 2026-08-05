#!/usr/bin/env python3
"""Run Claim Verifier in one bounded isolated host process.

The deterministic verifier gate accepts decisive SUPPORTS/CONTRADICTS results
only when this runner's receipt matches the stored dispatch, exact prompt,
submitted payload, and snapshot-bound claim batch.  Failed invocations are not
retried and never fabricate a verifier payload.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import claim_verification_engine
import deepthink_host_runner
import deepthink_orchestrator_v2 as orchestrator
from utils import get_scratch_dir, save_json


def build_receipt(dispatch, result):
    runner_kind = {
        "antigravity": "agy_separate_process_v1",
        "claude-code": "claude_separate_process_v1",
    }[result["host_runtime"]]
    receipt = {
        "schema": "claim-verifier-isolation.v1",
        "runner_kind": runner_kind,
        "host_enforced": True,
        "dispatch_id": dispatch["dispatch_id"],
        "claim_ids": dispatch["claim_ids"],
        "snapshot_ids": dispatch["snapshot_ids"],
        "verifier": {
            key: result[key]
            for key in (
                "invocation_id", "process_id", "exit_code", "timed_out",
                "elapsed_seconds", "prompt_sha256", "payload_sha256", "parse_error",
            )
        },
    }
    receipt["receipt_id"] = claim_verification_engine.isolation_receipt_id(receipt)
    return receipt


def run(topic, snapshots, *, seed_id="", claim_id="", runtime="auto", host_bin="",
        timeout_seconds=480, allow_agent_tools=False):
    host_runtime = deepthink_host_runner._resolve_host_runtime(runtime, host_bin=host_bin)
    host_bin = host_bin or deepthink_host_runner._default_host_bin(host_runtime)
    dispatch = orchestrator.cmd_verify_claims(topic, snapshots, seed_id, claim_id)
    if dispatch.get("status") != "dispatch_claim_verifier":
        return dispatch

    workdir = os.path.join(
        get_scratch_dir(), "isolated-work", dispatch["dispatch_id"], "claim-verifier"
    )
    result = deepthink_host_runner._run_role(
        "claim_verifier",
        dispatch["verifier_prompt"],
        host_bin,
        timeout_seconds,
        allow_agent_tools=allow_agent_tools,
        workdir=workdir,
        host_runtime=host_runtime,
    )
    receipt = build_receipt(dispatch, result)
    receipt_path = os.path.join(
        get_scratch_dir(), "isolation-receipts", f"{receipt['receipt_id']}.json"
    )
    save_json(receipt_path, receipt)
    if result.get("payload") is None:
        return {
            "status": "blocked_isolated_verifier_failure",
            "topic": topic,
            "dispatch_id": dispatch["dispatch_id"],
            "receipt_path": receipt_path,
            "failure": {
                key: result.get(key)
                for key in (
                    "exit_code", "timed_out", "parse_error", "resource_exhausted",
                    "error_code", "host_runtime", "host_executable",
                )
            },
            "instruction": "Do not retry automatically or fabricate a verifier payload.",
        }

    outcome = orchestrator.cmd_submit_verification(
        topic,
        snapshots,
        result["payload"],
        seed_id,
        claim_id,
        isolation_status="verified",
        isolation_receipt=receipt,
    )
    outcome["receipt_path"] = receipt_path
    outcome["verifier_elapsed_seconds"] = result["elapsed_seconds"]
    outcome["host_runtime"] = host_runtime
    return outcome


def _load_json_arg(value):
    if value and os.path.exists(value):
        with open(value, encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(value) if value else {}


def main():
    parser = argparse.ArgumentParser(
        description="Run an isolated Claim Verifier and submit a bound receipt."
    )
    parser.add_argument("--topic", required=True)
    parser.add_argument("--snapshots", required=True)
    parser.add_argument("--seed-id", default="")
    parser.add_argument("--claim-id", default="")
    parser.add_argument(
        "--runtime", default="auto",
        choices=("auto", "antigravity", "claude-code"),
    )
    parser.add_argument("--host-bin", default="")
    parser.add_argument("--timeout-seconds", type=int, default=480)
    parser.add_argument("--allow-agent-tools", action="store_true")
    args = parser.parse_args()
    if args.timeout_seconds < 30 or args.timeout_seconds > 1800:
        raise SystemExit("--timeout-seconds must be between 30 and 1800")
    host_bin = args.host_bin
    if not host_bin and args.runtime == "antigravity":
        host_bin = shutil.which("agy") or "agy"
    elif not host_bin and args.runtime == "claude-code":
        host_bin = shutil.which("claude") or "claude"
    print(json.dumps(run(
        args.topic,
        _load_json_arg(args.snapshots),
        seed_id=args.seed_id,
        claim_id=args.claim_id,
        runtime=args.runtime,
        host_bin=host_bin,
        timeout_seconds=args.timeout_seconds,
        allow_agent_tools=args.allow_agent_tools,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
