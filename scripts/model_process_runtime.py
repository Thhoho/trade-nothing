#!/usr/bin/env python3
"""Generic bounded JSON model-process adapter used by the research harness."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid

import process_control
import research_registry


RUNTIMES = {"antigravity", "claude-code"}
CLAUDE_PARENT_ENV_MARKERS = (
    "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID",
)
SANDBOX_MARKERS = (
    "operation not permitted", "failed to bind to address",
    "cannot assign requested address", "failed to create log file",
)
AUTH_MARKERS = (
    "authentication required", "waiting for authentication", "not logged in",
    "please run /login", "oauth-callback",
)
SECRET_ASSIGNMENT = re.compile(
    r"(?i)(token|api[_ -]?key|authorization|password|secret|bearer|credential)"
    r"([\"']?\s*[:=]\s*[\"']?|\s+)([^\s,;\]\}\"']+)"
)
SENSITIVE_QUERY = re.compile(
    r"(?i)([?&](?:client_id|code_challenge|state|access_token|refresh_token|"
    r"signature|credential)=)[^&\s]+"
)


def normalize_runtime(value):
    normalized = str(value or "").strip().lower().replace("_", "-")
    normalized = {
        "agy": "antigravity", "antigravity": "antigravity",
        "claude": "claude-code", "claudecode": "claude-code",
        "claude-code": "claude-code",
    }.get(normalized, normalized)
    if normalized not in RUNTIMES:
        raise ValueError(f"unsupported_host_runtime:{value}")
    return normalized


def default_binary(runtime):
    executable = "agy" if normalize_runtime(runtime) == "antigravity" else "claude"
    return shutil.which(executable) or executable


def _diagnostic(*parts, limit=1200):
    rendered = "\n".join(
        part.decode("utf-8", errors="replace") if isinstance(part, bytes) else str(part or "")
        for part in parts
    )
    rendered = SENSITIVE_QUERY.sub(r"\1[REDACTED]", rendered)
    rendered = SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", rendered)
    user_home = os.path.expanduser("~")
    if user_home and user_home != "/":
        rendered = rendered.replace(user_home, "[USER_HOME]")
    rendered = re.sub(r"\b[A-Za-z0-9_\-./+=]{64,}\b", "[REDACTED_OPAQUE]", rendered)
    rendered = "\n".join(line.strip() for line in rendered.splitlines() if line.strip())
    return rendered[-limit:]


def _error_code(diagnostic, *, timed_out=False, parse_error="", exit_code=0):
    value = str(diagnostic or "").lower()
    if any(marker in value for marker in SANDBOX_MARKERS):
        return "host_sandbox_denied"
    if any(marker in value for marker in AUTH_MARKERS):
        return "host_authentication_required"
    upper = value.upper()
    if any(marker in upper for marker in ("RESOURCE_EXHAUSTED", "CODE 429", "QUOTA")):
        return "resource_exhausted_429"
    if timed_out:
        return "timeout"
    if parse_error:
        return "invalid_json"
    if exit_code:
        return "process_exit"
    return ""


def child_environment(runtime):
    child = process_control.model_child_environment(exclude={
        "TRADE_NOTHING_STATE_PATH", "TRADE_NOTHING_RUN_ID",
        "TRADE_NOTHING_RUN_PURPOSE", "TRADE_NOTHING_SCRATCH_DIR",
    })
    if normalize_runtime(runtime) == "claude-code":
        for name in CLAUDE_PARENT_ENV_MARKERS:
            child.pop(name, None)
    return child


def command(binary, prompt, timeout_seconds, *, runtime, allow_tools):
    runtime = normalize_runtime(runtime)
    if runtime == "antigravity":
        result = [
            binary, "--print", prompt, "--print-timeout", f"{timeout_seconds}s",
            "--disable-slash-commands",
        ]
    else:
        schema = json.dumps(
            {"type": "object", "additionalProperties": True}, separators=(",", ":")
        )
        result = [
            binary, "--print", prompt, "--output-format", "json",
            "--json-schema", schema, "--no-session-persistence",
        ]
    if allow_tools:
        result.append("--dangerously-skip-permissions")
    return result


def parse_json_output(value, *, runtime):
    try:
        payload = json.loads(str(value or "").strip())
    except json.JSONDecodeError as exc:
        raise ValueError("model_output_must_be_exact_json") from exc
    if not isinstance(payload, dict):
        raise ValueError("model_output_must_be_json_object")
    if normalize_runtime(runtime) == "claude-code" and (
        payload.get("type") == "result" or "structured_output" in payload
    ):
        if payload.get("is_error") is True:
            raise ValueError("claude_code_result_error")
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
                raise ValueError("claude_code_result_missing_json") from exc
            if isinstance(nested, dict):
                return nested
        raise ValueError("claude_code_result_missing_structured_output")
    return payload


def run_json_call(role, prompt, *, runtime, binary="", timeout_seconds=480,
                  allow_tools=False, workdir=""):
    runtime = normalize_runtime(runtime)
    binary = binary or default_binary(runtime)
    started = time.monotonic()
    if workdir:
        os.makedirs(workdir, exist_ok=True)
    process = subprocess.Popen(
        command(binary, prompt, timeout_seconds, runtime=runtime, allow_tools=allow_tools),
        cwd=workdir or os.getcwd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True, env=child_environment(runtime),
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds + 15)
    except subprocess.TimeoutExpired:
        timed_out = True
        process_control.kill_process_group(process)
        stdout, stderr = process.communicate()
    payload = None
    parse_error = ""
    if process.returncode == 0 and not timed_out:
        try:
            payload = parse_json_output(stdout, runtime=runtime)
        except ValueError as exc:
            parse_error = str(exc)
    diagnostic = _diagnostic(stderr, stdout)
    error_code = _error_code(
        diagnostic, timed_out=timed_out, parse_error=parse_error,
        exit_code=process.returncode,
    )
    # This is a caller-observed process record, not an unforgeable host
    # attestation. The semantic layer labels it PROCESS_REPORTED accordingly.
    return {
        "role": str(role).upper(),
        "invocation_id": f"{str(role).lower()}-{uuid.uuid4()}",
        "host_runtime": runtime,
        "host_executable": os.path.basename(str(binary)),
        "process_id": process.pid,
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "payload": payload,
        "payload_sha256": research_registry.canonical_json_hash(payload) if payload else "",
        "external_tools_enabled": bool(allow_tools),
        "parse_error": parse_error,
        "error_code": error_code,
        "diagnostic_excerpt": diagnostic if error_code else "",
        "diagnostic_sha256": hashlib.sha256(diagnostic.encode("utf-8")).hexdigest()
        if error_code else "",
    }


def preflight(runtime, binary=""):
    """Resolve the executable without spending a model call.

    Authentication and permissions are observed by the one real request and are
    never probed through a second hidden model invocation.
    """
    runtime = normalize_runtime(runtime)
    binary = binary or default_binary(runtime)
    resolved = binary if os.path.isabs(binary) else shutil.which(binary)
    if not resolved or not os.path.isfile(resolved) or not os.access(resolved, os.X_OK):
        return {
            "status": "runtime_preflight_failed",
            "reason": "host_executable_not_found_or_not_executable",
            "host_runtime": runtime,
            "host_executable": binary,
        }
    return {
        "status": "runtime_preflight_ready",
        "host_runtime": runtime,
        "host_executable": resolved,
        "credential_probe_performed": False,
    }
