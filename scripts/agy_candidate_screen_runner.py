#!/usr/bin/env python3
"""Run Candidate Analyst and Skeptic in separate agy processes.

This is an optional host adapter for Antigravity CLI. It never fabricates a
payload or retries a failed role. The deterministic engine verifies the
dispatch, prompt, payload, process, and invocation receipt before allowing
verified CandidateScreen isolation.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import candidate_screen_engine
import deepthink_orchestrator_v2 as orchestrator
from utils import get_scratch_dir, save_json


def _prompt_sha256(prompt):
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _parse_json_output(text):
    text = str(text or "").strip()
    if not text:
        raise ValueError("empty role output")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("role output must be one exact JSON object without commentary") from exc
    if not isinstance(payload, dict):
        raise ValueError("role output must be a JSON object")
    return payload


def _build_command(agy_bin, wrapped_prompt, timeout_seconds, allow_agent_tools=False):
    command = [
        agy_bin,
        "--print", wrapped_prompt,
        "--print-timeout", f"{timeout_seconds}s",
    ]
    if allow_agent_tools:
        command.append("--dangerously-skip-permissions")
    return command


def _run_role(role, prompt, agy_bin, timeout_seconds, workdir, allow_agent_tools=False):
    invocation_id = f"{role}-{uuid.uuid4()}"
    wrapped_prompt = (
        "You are an isolated CandidateScreen role. Return exactly one JSON object and no "
        "commentary, markdown, progress notes, or file links. Do not read other role output.\n\n"
        + prompt
    )
    command = _build_command(
        agy_bin, wrapped_prompt, timeout_seconds, allow_agent_tools=allow_agent_tools
    )
    started = time.monotonic()
    os.makedirs(workdir, exist_ok=True)
    process = subprocess.Popen(
        command,
        cwd=workdir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds + 15)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate()
    elapsed = round(time.monotonic() - started, 3)
    payload = None
    parse_error = ""
    if process.returncode == 0 and not timed_out:
        try:
            payload = _parse_json_output(stdout)
        except ValueError as exc:
            parse_error = str(exc)
    return {
        "role": role,
        "invocation_id": invocation_id,
        "process_id": process.pid,
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "elapsed_seconds": elapsed,
        "prompt_sha256": _prompt_sha256(prompt),
        "payload": payload,
        "payload_sha256": (
            candidate_screen_engine.payload_sha256(payload) if payload is not None else ""
        ),
        "parse_error": parse_error,
        "stderr_tail": str(stderr or "")[-500:],
    }


def build_receipt(dispatch, results):
    receipt = {
        "schema": "candidate-screen-isolation.v1",
        "runner_kind": "agy_separate_process_v1",
        "host_enforced": True,
        "dispatch_id": dispatch["dispatch_id"],
        "as_of_date": dispatch["as_of_date"],
        "candidate_seed_ids": dispatch["candidate_seed_ids"],
        "roles": {},
    }
    for role in ("analyst", "skeptic"):
        result = results[role]
        receipt["roles"][role] = {
            key: result[key]
            for key in (
                "invocation_id", "process_id", "exit_code", "timed_out",
                "elapsed_seconds", "prompt_sha256", "payload_sha256", "parse_error",
            )
        }
    receipt["receipt_id"] = candidate_screen_engine.isolation_receipt_id(receipt)
    return receipt


def run(topic, as_of_date, agy_bin, timeout_seconds, allow_agent_tools=False):
    dispatch = orchestrator.cmd_screen(topic, as_of_date)
    if dispatch.get("status") != "dispatch_candidate_screeners":
        return dispatch
    prompts = {
        "analyst": dispatch["analyst_prompt"],
        "skeptic": dispatch["skeptic_prompt"],
    }
    role_root = os.path.join(
        get_scratch_dir(), "isolated-work", dispatch["dispatch_id"]
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            role: pool.submit(
                _run_role, role, prompt, agy_bin, timeout_seconds,
                os.path.join(role_root, role),
                allow_agent_tools
            )
            for role, prompt in prompts.items()
        }
        results = {role: future.result() for role, future in futures.items()}

    receipt = build_receipt(dispatch, results)
    receipt_dir = os.path.join(get_scratch_dir(), "isolation-receipts")
    receipt_path = os.path.join(receipt_dir, f"{receipt['receipt_id']}.json")
    save_json(receipt_path, receipt)
    failures = {
        role: {
            key: result[key]
            for key in ("exit_code", "timed_out", "parse_error", "stderr_tail")
            if result.get(key)
        }
        for role, result in results.items()
        if result["payload"] is None
    }
    if failures:
        return {
            "status": "blocked_isolated_role_failure",
            "topic": topic,
            "dispatch_id": dispatch["dispatch_id"],
            "receipt_path": receipt_path,
            "failures": failures,
            "instruction": "Do not retry automatically or fabricate the missing role payload.",
        }

    outcome = orchestrator.cmd_submit_screen(
        topic,
        results["analyst"]["payload"],
        results["skeptic"]["payload"],
        dispatch["as_of_date"],
        isolation_status="verified",
        isolation_receipt=receipt,
    )
    outcome["receipt_path"] = receipt_path
    outcome["role_elapsed_seconds"] = {
        role: results[role]["elapsed_seconds"] for role in results
    }
    return outcome


def main():
    parser = argparse.ArgumentParser(
        description="Run isolated agy CandidateScreen roles and submit a verified receipt."
    )
    parser.add_argument("--topic", required=True)
    parser.add_argument("--as-of", default="")
    parser.add_argument("--agy-bin", default=shutil.which("agy") or "agy")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument(
        "--allow-agent-tools",
        action="store_true",
        help=(
            "explicitly pass agy's --dangerously-skip-permissions to both isolated roles; "
            "use only when the caller has authorized non-interactive tool access"
        ),
    )
    args = parser.parse_args()
    if args.timeout_seconds < 30 or args.timeout_seconds > 1800:
        raise SystemExit("--timeout-seconds must be between 30 and 1800")
    print(json.dumps(
        run(
            args.topic, args.as_of, args.agy_bin, args.timeout_seconds,
            allow_agent_tools=args.allow_agent_tools,
        ),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
