#!/usr/bin/env python3
"""Run Candidate Analyst and Skeptic in separate host processes.

Supports Antigravity and Claude Code CLIs. It never fabricates a payload or
retries a failed role. The deterministic engine verifies the dispatch, prompt,
payload, process, and invocation receipt before allowing verified isolation.
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
import process_control
from utils import get_scratch_dir, save_json


HOST_RUNTIMES = {"antigravity", "claude-code"}
CLAUDE_PARENT_ENV_MARKERS = (
    "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID",
)


def _normalize_runtime(value):
    runtime = str(value or "").strip().lower().replace("_", "-")
    runtime = {
        "agy": "antigravity",
        "claude": "claude-code",
        "claudecode": "claude-code",
    }.get(runtime, runtime)
    if runtime not in HOST_RUNTIMES:
        raise ValueError(f"unsupported_host_runtime:{value}")
    return runtime


def _resolve_runtime(value="auto", host_bin=""):
    requested = str(value or "auto").strip().lower().replace("_", "-")
    if requested != "auto":
        return _normalize_runtime(requested)
    executable = os.path.basename(str(host_bin or "")).lower()
    if "claude" in executable:
        return "claude-code"
    if executable == "agy" or "antigravity" in executable:
        return "antigravity"
    if any(os.environ.get(name) for name in CLAUDE_PARENT_ENV_MARKERS):
        return "claude-code"
    if shutil.which("agy"):
        return "antigravity"
    if shutil.which("claude"):
        return "claude-code"
    raise ValueError("no_supported_host_runtime_found")


def _host_environment(runtime):
    child = os.environ.copy()
    if _normalize_runtime(runtime) == "claude-code":
        for name in CLAUDE_PARENT_ENV_MARKERS:
            child.pop(name, None)
    return child


def _prompt_sha256(prompt):
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _parse_json_output(text, host_runtime="antigravity"):
    text = str(text or "").strip()
    if not text:
        raise ValueError("empty role output")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("role output must be one exact JSON object without commentary") from exc
    if not isinstance(payload, dict):
        raise ValueError("role output must be a JSON object")
    if _normalize_runtime(host_runtime) == "claude-code" and (
        payload.get("type") == "result" or "structured_output" in payload
    ):
        if payload.get("is_error") is True:
            raise ValueError("claude code role result error")
        structured = payload.get("structured_output")
        if isinstance(structured, dict):
            return structured
        result = payload.get("result")
        if isinstance(result, dict):
            return result
        if isinstance(result, str):
            try:
                nested = json.loads(result)
            except json.JSONDecodeError as exc:
                raise ValueError("claude code result must contain exact JSON") from exc
            if isinstance(nested, dict):
                return nested
        raise ValueError("claude code result missing structured output")
    return payload


def _build_command(host_bin, wrapped_prompt, timeout_seconds, allow_agent_tools=False,
                   host_runtime="antigravity"):
    runtime = _normalize_runtime(host_runtime)
    if runtime == "antigravity":
        command = [
            host_bin,
            "--print", wrapped_prompt,
            "--print-timeout", f"{timeout_seconds}s",
        ]
    else:
        schema = json.dumps(
            {"type": "object", "additionalProperties": True}, separators=(",", ":")
        )
        command = [
            host_bin,
            "--print", wrapped_prompt,
            "--output-format", "json",
            "--json-schema", schema,
            "--no-session-persistence",
        ]
    if allow_agent_tools:
        command.append("--dangerously-skip-permissions")
    return command


def _run_role(role, prompt, host_bin, timeout_seconds, workdir,
              allow_agent_tools=False, host_runtime="antigravity"):
    host_runtime = _normalize_runtime(host_runtime)
    invocation_id = f"{role}-{uuid.uuid4()}"
    wrapped_prompt = (
        "You are an isolated CandidateScreen role. Return exactly one JSON object and no "
        "commentary, markdown, progress notes, or file links. Do not read other role output.\n\n"
        + prompt
    )
    command = _build_command(
        host_bin, wrapped_prompt, timeout_seconds, allow_agent_tools=allow_agent_tools,
        host_runtime=host_runtime,
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
        env=_host_environment(host_runtime),
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds + 15)
    except subprocess.TimeoutExpired:
        timed_out = True
        process_control.kill_process_group(process)
        stdout, stderr = process.communicate()
    elapsed = round(time.monotonic() - started, 3)
    payload = None
    parse_error = ""
    if process.returncode == 0 and not timed_out:
        try:
            payload = _parse_json_output(stdout, host_runtime=host_runtime)
        except ValueError as exc:
            parse_error = str(exc)
    diagnostic = (str(stderr or "") + "\n" + str(stdout or ""))[-1000:]
    resource_exhausted = any(
        marker in diagnostic.upper()
        for marker in ("RESOURCE_EXHAUSTED", "CODE 429", "ERROR_CODE\":429", "QUOTA")
    )
    error_code = (
        "resource_exhausted_429" if resource_exhausted
        else "timeout" if timed_out
        else "invalid_json" if parse_error
        else "process_exit" if process.returncode != 0
        else ""
    )
    return {
        "role": role,
        "host_runtime": host_runtime,
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
        "resource_exhausted": resource_exhausted,
        "error_code": error_code,
    }


def build_receipt(dispatch, results):
    runtimes = {
        str(result.get("host_runtime") or "antigravity")
        for result in results.values()
    }
    if len(runtimes) != 1:
        raise ValueError("candidate screen roles must use the same host runtime")
    host_runtime = _normalize_runtime(runtimes.pop())
    receipt = {
        "schema": "candidate-screen-isolation.v1",
        "runner_kind": (
            "agy_separate_process_v1"
            if host_runtime == "antigravity" else "claude_separate_process_v1"
        ),
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


def run(topic, as_of_date, host_bin, timeout_seconds, allow_agent_tools=False,
        host_runtime="antigravity"):
    host_runtime = _normalize_runtime(host_runtime)
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
                _run_role, role, prompt, host_bin, timeout_seconds,
                os.path.join(role_root, role),
                allow_agent_tools, host_runtime
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
            for key in (
                "exit_code", "timed_out", "parse_error", "resource_exhausted", "error_code"
            )
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
        description="Run isolated CandidateScreen roles and submit a verified receipt."
    )
    parser.add_argument("--topic", required=True)
    parser.add_argument("--as-of", default="")
    parser.add_argument(
        "--runtime", default="auto",
        choices=("auto", "antigravity", "claude-code"),
    )
    parser.add_argument("--host-bin", default="")
    parser.add_argument("--agy-bin", default="", help="deprecated alias for --host-bin")
    parser.add_argument("--timeout-seconds", type=int, default=480)
    parser.add_argument(
        "--allow-agent-tools",
        action="store_true",
        help=(
            "explicitly pass the host CLI's permission-bypass flag to both isolated roles; "
            "use only when the caller has authorized non-interactive tool access"
        ),
    )
    args = parser.parse_args()
    if args.timeout_seconds < 30 or args.timeout_seconds > 1800:
        raise SystemExit("--timeout-seconds must be between 30 and 1800")
    if args.agy_bin and args.host_bin and args.agy_bin != args.host_bin:
        raise SystemExit("--agy-bin and --host-bin disagree")
    host_bin = args.host_bin or args.agy_bin
    runtime = _resolve_runtime(
        "antigravity" if args.agy_bin else args.runtime, host_bin=host_bin
    )
    host_bin = host_bin or (shutil.which("agy") or "agy" if runtime == "antigravity"
                            else shutil.which("claude") or "claude")
    print(json.dumps(
        run(
            args.topic, args.as_of, host_bin, args.timeout_seconds,
            allow_agent_tools=args.allow_agent_tools,
            host_runtime=runtime,
        ),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
