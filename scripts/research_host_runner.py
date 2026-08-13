#!/usr/bin/env python3
"""Execute exactly one v0.18.0 external-process request and submit its result."""
from __future__ import annotations

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import model_process_runtime
import research_core
import research_loop
import research_registry


def _receipt(record):
    return {
        "receipt_id": record["invocation_id"],
        "status": "SUCCEEDED",
        "agent_id": record["invocation_id"],
        "parent_agent_id": "",
        "isolation": "PROCESS_CONTEXT_REPORTED",
        "receipt_provenance": "HOST_PROCESS",
        "attestation_level": "PROCESS_REPORTED",
        "process_id": record["process_id"],
        "host_runtime": record["host_runtime"],
        "external_tools_enabled": record.get("external_tools_enabled") is True,
        "prompt_sha256": record["prompt_sha256"],
        "payload_sha256": record["payload_sha256"],
    }


def _checkpoint(run_id, call_mode, record, submitted=False, contract_errors=None):
    stage_id = f"{call_mode.lower()}-{record['invocation_id']}"
    contract_errors = list(contract_errors or [])
    return research_registry.save_checkpoint(run_id, stage_id, {
        "status": (
            "contract_rejected" if contract_errors
            else "submitted" if submitted
            else "model_call_completed"
        ),
        "call_mode": call_mode,
        "role": record.get("role"),
        "invocation_id": record.get("invocation_id"),
        "exit_code": record.get("exit_code"),
        "timed_out": record.get("timed_out"),
        "elapsed_seconds": record.get("elapsed_seconds"),
        "prompt_sha256": record.get("prompt_sha256"),
        "payload_sha256": record.get("payload_sha256"),
        "error_code": record.get("error_code"),
        "diagnostic_excerpt": record.get("diagnostic_excerpt"),
        "submitted": submitted,
        "contract_errors": contract_errors,
    })


def run_one_request(run_id, *, runtime, binary="", timeout_seconds=480,
                    allow_tools=False, workdir=""):
    """One dispatch, at most one process call, one submission, then return."""
    dispatched = research_loop.cmd_dispatch(run_id)
    if dispatched["status"] == "ready_for_report":
        return dispatched
    prompt = dispatched["prompt"]
    call_mode = dispatched["call_mode"]
    role = dispatched["role"]
    record = model_process_runtime.run_json_call(
        role, prompt, runtime=runtime, binary=binary,
        timeout_seconds=timeout_seconds,
        allow_tools=(allow_tools and call_mode in {"LEAD_RESEARCH", "CHALLENGER"}),
        workdir=workdir,
    )
    _checkpoint(run_id, call_mode, record)
    public = {
        key: record.get(key) for key in (
            "role", "invocation_id", "host_runtime", "host_executable",
            "exit_code", "timed_out", "elapsed_seconds", "prompt_sha256",
            "payload_sha256", "error_code", "diagnostic_excerpt",
            "external_tools_enabled",
        )
    }
    calls = [public]
    if record.get("error_code") or not isinstance(record.get("payload"), dict):
        failure = research_loop.cmd_runtime_failure(
            run_id, role, record.get("error_code") or "missing_json_payload",
            record.get("invocation_id"),
        )
        failure["model_calls"] = calls
        return failure
    research_loop.cmd_register_host_invocation(run_id, record)
    receipt = _receipt(record)
    try:
        if call_mode == "CHALLENGER":
            result = research_loop.cmd_submit_challenge(
                run_id, record["payload"], receipt
            )
        else:
            result = research_loop.cmd_submit_lead(
                run_id, record["payload"], receipt
            )
    except research_core.ResearchContractError as exc:
        _checkpoint(run_id, call_mode, record, contract_errors=exc.errors)
        return {
            "status": "contract_rejected",
            "run_id": run_id,
            "call_mode": call_mode,
            "errors": exc.errors,
            "model_calls": calls,
            "instruction": (
                "Repair the packet or prompt, then explicitly resume. "
                "The rejected model call was not consumed or retried."
            ),
        }
    _checkpoint(run_id, call_mode, record, submitted=True)
    result["model_calls"] = calls
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--topic", required=True)
    start.add_argument("--task-spec-json", default="")
    start.add_argument("--frame-json", default="")
    start.add_argument("--round-budget", type=int, default=1)
    start.add_argument("--run-purpose", default="PRODUCTION_RESEARCH",
                       choices=sorted(research_registry.RUN_PURPOSES))
    resume = sub.add_parser("resume")
    resume.add_argument("--run-id", required=True)
    status = sub.add_parser("status")
    status.add_argument("--run-id", required=True)
    for command in (start, resume):
        command.add_argument("--runtime", required=True,
                             choices=sorted(model_process_runtime.RUNTIMES))
        command.add_argument("--host-bin", default="")
        command.add_argument("--timeout-seconds", type=int, default=480)
        command.add_argument("--allow-agent-tools", action="store_true")
        command.add_argument("--workdir", default="")
        command.add_argument("--skip-preflight", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "status":
            result = research_loop.cmd_status(args.run_id)
        else:
            if not 30 <= args.timeout_seconds <= 1800:
                raise ValueError("timeout_seconds_requires_30_to_1800")
            if not args.skip_preflight:
                preflight = model_process_runtime.preflight(args.runtime, args.host_bin)
                if preflight["status"] != "runtime_preflight_ready":
                    print(json.dumps(preflight, ensure_ascii=False, indent=2))
                    return
                host_bin = preflight["host_executable"]
            else:
                host_bin = args.host_bin
            if args.command == "start":
                raw_spec = research_loop._json_load(args.task_spec_json) if args.task_spec_json else {}
                frame = research_loop._json_load(args.frame_json) if args.frame_json else None
                started = research_loop.cmd_start(
                    args.topic, raw_spec, frame=frame,
                    round_budget=args.round_budget, run_purpose=args.run_purpose,
                    execution_mode="EXTERNAL_PROCESS_REPORTED",
                )
                run_id = started["run_id"]
            else:
                run_id = args.run_id
            result = run_one_request(
                run_id, runtime=args.runtime, binary=host_bin,
                timeout_seconds=args.timeout_seconds,
                allow_tools=args.allow_agent_tools, workdir=args.workdir,
            )
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        result = {
            "status": "runner_error",
            "reason": str(exc),
            "instruction": "Repair configuration; do not auto-retry.",
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
