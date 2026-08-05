#!/usr/bin/env python3
"""Bounded, resumable host runner for deepthink2.

The deterministic orchestrator remains authoritative. This adapter owns process
dispatch, stage checkpoints, run identity, and fail-closed continuation. It can
use Antigravity or Claude Code as the isolated-process host.
"""
from __future__ import annotations

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

import agy_candidate_screen_runner
import crux_engine
import deepthink_orchestrator_v2 as orchestrator
import process_control
import run_registry
from utils import get_skill_dir, load_json_safe


def _prompt_hash(prompt):
    return hashlib.sha256(str(prompt).encode("utf-8")).hexdigest()


HOST_RUNTIMES = {"antigravity", "claude-code"}
CLAUDE_PARENT_ENV_MARKERS = (
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_SESSION_ID",
)


def _normalize_host_runtime(value):
    runtime = str(value or "").strip().lower().replace("_", "-")
    aliases = {
        "agy": "antigravity",
        "antigravity": "antigravity",
        "claude": "claude-code",
        "claude-code": "claude-code",
        "claudecode": "claude-code",
    }
    normalized = aliases.get(runtime, runtime)
    if normalized not in HOST_RUNTIMES:
        raise ValueError(f"unsupported_host_runtime:{value}")
    return normalized


def _resolve_host_runtime(value="auto", host_bin=""):
    """Resolve an explicit runtime, with conservative auto-detection.

    Backward compatibility prefers Antigravity when both CLIs are installed.
    Inside Claude Code, its exported environment markers take precedence. A
    caller can always force the adapter with ``--runtime claude-code``.
    """
    requested = str(value or "auto").strip().lower().replace("_", "-")
    if requested != "auto":
        return _normalize_host_runtime(requested)
    executable = os.path.basename(str(host_bin or "")).lower()
    if "claude" in executable:
        return "claude-code"
    if executable == "agy" or "antigravity" in executable:
        return "antigravity"
    if any(os.environ.get(name) for name in (
        "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID",
    )):
        return "claude-code"
    if shutil.which("agy"):
        return "antigravity"
    if shutil.which("claude"):
        return "claude-code"
    raise ValueError("no_supported_host_runtime_found")


def _default_host_bin(host_runtime):
    runtime = _normalize_host_runtime(host_runtime)
    executable = "agy" if runtime == "antigravity" else "claude"
    return shutil.which(executable) or executable


def _host_environment(host_runtime):
    """Build the child environment without inheriting Claude's parent lock.

    Claude Code marks its own process tree to prevent an accidental nested
    interactive session.  The host runner intentionally launches bounded,
    non-persistent role processes, so those parent-session markers must not be
    forwarded to the isolated child.  Authentication and all unrelated user
    environment variables are preserved.
    """
    child = os.environ.copy()
    if _normalize_host_runtime(host_runtime) == "claude-code":
        for name in CLAUDE_PARENT_ENV_MARKERS:
            child.pop(name, None)
    return child


def _parse_json_output(text, host_runtime="antigravity"):
    text = str(text or "").strip()
    if not text:
        raise ValueError("empty_role_output")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("role_output_must_be_exact_json") from exc
    if not isinstance(payload, dict):
        raise ValueError("role_output_must_be_json_object")
    if _normalize_host_runtime(host_runtime) == "claude-code" and (
        payload.get("type") == "result" or "structured_output" in payload
    ):
        if payload.get("is_error") is True:
            raise ValueError("claude_code_role_result_error")
        structured = payload.get("structured_output")
        if isinstance(structured, dict):
            return structured
        result = payload.get("result")
        if isinstance(result, dict):
            return result
        if isinstance(result, str):
            try:
                result_payload = json.loads(result)
            except json.JSONDecodeError as exc:
                raise ValueError("claude_code_result_must_contain_exact_json") from exc
            if isinstance(result_payload, dict):
                return result_payload
        raise ValueError("claude_code_result_missing_structured_output")
    return payload


def _command(host_bin, prompt, timeout_seconds, allow_agent_tools=False,
             host_runtime="antigravity"):
    runtime = _normalize_host_runtime(host_runtime)
    if runtime == "antigravity":
        command = [host_bin, "--print", prompt, "--print-timeout", f"{timeout_seconds}s"]
    else:
        # --json-schema asks Claude Code to return a machine-readable
        # `structured_output` object inside its --output-format json envelope.
        schema = json.dumps(
            {"type": "object", "additionalProperties": True},
            separators=(",", ":"),
        )
        command = [
            host_bin,
            "--print", prompt,
            "--output-format", "json",
            "--json-schema", schema,
            "--no-session-persistence",
        ]
    if allow_agent_tools:
        command.append("--dangerously-skip-permissions")
    return command


def _run_role(role, prompt, host_bin, timeout_seconds, allow_agent_tools=False,
              workdir="", host_runtime="antigravity"):
    host_runtime = _normalize_host_runtime(host_runtime)
    wrapped = (
        f"You are the isolated deepthink2 {role} role. Return exactly one JSON object and no "
        "markdown, commentary, progress notes, transcript, or file link. Do not read or infer "
        "another role's output.\n\n" + prompt
    )
    started = time.monotonic()
    if workdir:
        os.makedirs(workdir, exist_ok=True)
    process = subprocess.Popen(
        _command(
            host_bin, wrapped, timeout_seconds, allow_agent_tools,
            host_runtime=host_runtime,
        ),
        cwd=workdir or get_skill_dir(),
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
        "host_executable": os.path.basename(str(host_bin or "")),
        "invocation_id": f"{role}-{uuid.uuid4()}",
        "process_id": process.pid,
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "prompt_sha256": _prompt_hash(prompt),
        "payload": payload,
        "payload_sha256": run_registry.canonical_json_hash(payload) if payload else "",
        "parse_error": parse_error,
        "resource_exhausted": resource_exhausted,
        "error_code": error_code,
    }


def _public_result(result):
    return {
        key: result.get(key)
        for key in (
            "role", "invocation_id", "process_id", "exit_code", "timed_out",
            "elapsed_seconds", "prompt_sha256", "payload", "payload_sha256",
            "parse_error", "resource_exhausted", "error_code", "host_runtime",
            "host_executable",
        )
    }


def _checkpoint_role_valid(record, prompt):
    return bool(
        isinstance(record, dict)
        and isinstance(record.get("payload"), dict)
        and record.get("exit_code") == 0
        and not record.get("timed_out")
        and record.get("prompt_sha256") == _prompt_hash(prompt)
        and record.get("payload_sha256")
        == run_registry.canonical_json_hash(record.get("payload"))
    )


def _pause(context, stage_id, checkpoint, missing_roles, reason, budget=None):
    checkpoint["status"] = "paused_runtime_failure"
    checkpoint["missing_roles"] = missing_roles
    checkpoint["reason"] = reason
    run_registry.save_checkpoint(context["run_id"], stage_id, checkpoint)
    return run_registry.stage_envelope({
        "status": "paused_runtime_failure",
        "topic": context["topic"],
        "stage_id": stage_id,
        "missing_roles": missing_roles,
        "reason": reason,
        "formal_report_allowed": False,
        "state_path": context["state_path"],
        "checkpoint_path": run_registry.checkpoint_path(context["run_id"], stage_id),
        "instruction": (
            f"保留成功角色，仅重跑 {', '.join(missing_roles)}；"
            f"额度或运行时恢复后执行 resume --run-id {context['run_id']}。"
        ),
    }, context=context, budget=budget)


def execute_round(context, *, agy_bin="", host_bin="", host_runtime="antigravity",
                  timeout_seconds, judge_timeout_seconds=240,
                  allow_agent_tools=False, budget=None):
    host_runtime = _normalize_host_runtime(host_runtime)
    host_bin = host_bin or agy_bin or _default_host_bin(host_runtime)
    run_registry.bind_context(context)
    state = load_json_safe(context["state_path"], default=None)
    if not isinstance(state, dict):
        return run_registry.stage_envelope({
            "status": "blocked_missing_state",
            "reason": "state_not_initialized",
            "state_path": context["state_path"],
        }, context=context)
    round_num = len(state.get("rounds", [])) + 1
    stage_id = f"round-{round_num}"
    prompts = orchestrator.dispatch_prompts(state, round_num)
    role_prompts = {
        "detective": prompts["detective_prompt"],
        "inquisitor": prompts["inquisitor_prompt"],
    }
    checkpoint = run_registry.load_checkpoint(context["run_id"], stage_id)
    if checkpoint.get("submitted"):
        return run_registry.stage_envelope(
            checkpoint.get("submit_result") or {
                "status": "checkpoint_already_submitted",
                "topic": context["topic"],
                "round_completed": round_num,
            },
            context=context,
        )
    checkpoint.setdefault("prompt_sha256", {
        role: _prompt_hash(prompt) for role, prompt in role_prompts.items()
    })
    expected_prompt_hashes = {
        role: _prompt_hash(prompt) for role, prompt in role_prompts.items()
    }
    if checkpoint["prompt_sha256"] != expected_prompt_hashes:
        old_records = checkpoint.get("roles") if isinstance(checkpoint.get("roles"), dict) else {}
        records_to_check = list(old_records.values())
        if isinstance(checkpoint.get("judge"), dict):
            records_to_check.append(checkpoint["judge"])
        has_successful_payload = any(
            isinstance(record, dict)
            and isinstance(record.get("payload"), dict)
            and record.get("exit_code") == 0
            and record.get("payload_sha256")
            == run_registry.canonical_json_hash(record.get("payload"))
            for record in records_to_check
        )
        if checkpoint.get("submitted") or has_successful_payload:
            return _pause(
                context, stage_id, checkpoint, ["manual_review"],
                "checkpoint_prompt_hash_mismatch", budget
            )
        checkpoint = {
            "prompt_sha256": expected_prompt_hashes,
            "superseded_prompt_sha256": checkpoint.get("prompt_sha256", {}),
            "roles": {},
            "status": "restarted_after_failed_prompt_drift",
        }
    records = checkpoint.setdefault("roles", {})
    missing = [
        role for role, prompt in role_prompts.items()
        if not _checkpoint_role_valid(records.get(role), prompt)
    ]
    if missing:
        role_root = os.path.join(
            run_registry.checkpoint_dir(context["run_id"]), stage_id + "-work"
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(missing)) as pool:
            futures = {
                role: pool.submit(
                    _run_role, role, role_prompts[role], host_bin, timeout_seconds,
                    allow_agent_tools, os.path.join(role_root, role), host_runtime,
                )
                for role in missing
            }
            for role, future in futures.items():
                records[role] = _public_result(future.result())
        run_registry.save_checkpoint(context["run_id"], stage_id, checkpoint)
    failed = [
        role for role, prompt in role_prompts.items()
        if not _checkpoint_role_valid(records.get(role), prompt)
    ]
    if failed:
        reason = (
            "resource_exhausted_429"
            if any(records.get(role, {}).get("resource_exhausted") for role in failed)
            else "isolated_role_failure"
        )
        return _pause(context, stage_id, checkpoint, failed, reason, budget)

    detective = records["detective"]["payload"]
    inquisitor = records["inquisitor"]["payload"]
    judge_prompt = (
        prompts["judge_prompt"]
        + "\nOnly score evidence physically present in these exact payloads.\nDetective JSON:\n"
        + json.dumps(detective, ensure_ascii=False, sort_keys=True)
        + "\nInquisitor JSON:\n"
        + json.dumps(inquisitor, ensure_ascii=False, sort_keys=True)
    )
    judge_record = checkpoint.get("judge")
    if not _checkpoint_role_valid(judge_record, judge_prompt):
        judge_workdir = os.path.join(
            run_registry.checkpoint_dir(context["run_id"]), stage_id + "-work", "judge"
        )
        os.makedirs(judge_workdir, exist_ok=True)
        judge_record = _public_result(_run_role(
            "judge", judge_prompt, host_bin,
            min(timeout_seconds, judge_timeout_seconds), allow_agent_tools,
            judge_workdir, host_runtime,
        ))
        checkpoint["judge"] = judge_record
        run_registry.save_checkpoint(context["run_id"], stage_id, checkpoint)
    if not _checkpoint_role_valid(judge_record, judge_prompt):
        reason = (
            "resource_exhausted_429"
            if judge_record.get("resource_exhausted") else "judge_failure"
        )
        return _pause(context, stage_id, checkpoint, ["judge"], reason, budget)

    result = orchestrator.cmd_submit(
        context["topic"], detective, inquisitor, judge_record["payload"]
    )
    checkpoint["submitted"] = True
    checkpoint["submit_result"] = result
    checkpoint["status"] = result.get("status")
    run_registry.save_checkpoint(context["run_id"], stage_id, checkpoint)
    return run_registry.stage_envelope(result, context=context, budget=budget)


def _report_terminal(context, terminal_envelope, *, budget, stopped_reason):
    """Always materialize the graded report when a research loop stops."""
    terminal_result = (
        terminal_envelope.get("result", {})
        if isinstance(terminal_envelope, dict) else {}
    )
    terminal_status = str(
        (terminal_envelope or {}).get("status")
        or terminal_result.get("status")
        or "unknown"
    )
    terminal_instruction = str(
        (terminal_envelope or {}).get("next_action")
        or terminal_result.get("instruction")
        or ""
    )
    report = orchestrator.cmd_report(context["topic"])
    report["runner_terminal_status"] = terminal_status
    report["runner_terminal_instruction"] = terminal_instruction
    report["stopped_reason"] = stopped_reason
    if terminal_status != "ready_for_report" and terminal_instruction:
        report["instruction"] = terminal_instruction
    return run_registry.stage_envelope(report, context=context, budget=budget)


def continue_run(context, *, agy_bin="", host_bin="", host_runtime="antigravity",
                 timeout_seconds, judge_timeout_seconds=240,
                 allow_agent_tools=False, round_budget=1,
                 continue_screen=True, stop_after_dry_rounds=0):
    """Run rounds until convergence, exhaustion, or the safety fuse.

    A round count is a poor budget unit: one round may add five citations and the
    next may add nothing. When `stop_after_dry_rounds` is set, `round_budget`
    becomes a safety fuse and the operative stop condition is "this many
    consecutive rounds added no evidence, probe, or seed progress".
    """
    host_runtime = _normalize_host_runtime(host_runtime)
    host_bin = host_bin or agy_bin or _default_host_bin(host_runtime)
    run_registry.bind_context(context)
    last = None
    for completed in range(round_budget):
        state = load_json_safe(context["state_path"], default=None)
        if not isinstance(state, dict):
            break
        if stop_after_dry_rounds:
            dry = crux_engine.consecutive_unproductive_rounds(state)
            if dry >= stop_after_dry_rounds:
                result = orchestrator.cmd_report(context["topic"])
                result["stopped_reason"] = "EVIDENCE_EXHAUSTED"
                result["consecutive_dry_rounds"] = dry
                return run_registry.stage_envelope(result, context=context, budget={
                    "round_budget": round_budget, "rounds_used": completed,
                    "stop_after_dry_rounds": stop_after_dry_rounds,
                })
        if (state.get("last_convergence") or {}).get("decision") == "converge":
            result = orchestrator.cmd_report(context["topic"])
            last = run_registry.stage_envelope(result, context=context, budget={
                "round_budget": round_budget, "rounds_used": completed,
            })
        else:
            last = execute_round(
                context, host_bin=host_bin, host_runtime=host_runtime,
                timeout_seconds=timeout_seconds,
                judge_timeout_seconds=judge_timeout_seconds,
                allow_agent_tools=allow_agent_tools,
                budget={"round_budget": round_budget, "rounds_used": completed},
            )
        status = last.get("status")
        raw = last.get("result", {})
        if status == "dispatch_subagents":
            continue
        if status == "dispatch_candidate_screeners" and continue_screen:
            screen = agy_candidate_screen_runner.run(
                context["topic"], raw.get("as_of_date", ""), host_bin, timeout_seconds,
                allow_agent_tools=allow_agent_tools,
                host_runtime=host_runtime,
            )
            last = run_registry.stage_envelope(screen, context=context, budget={
                "round_budget": round_budget, "rounds_used": completed + 1,
            })
            if last["status"] == "candidate_screen_complete":
                report = orchestrator.cmd_report(context["topic"])
                last = run_registry.stage_envelope(report, context=context, budget={
                    "round_budget": round_budget, "rounds_used": completed + 1,
                })
            return last
        if status in {
            "ready_for_report",
            "blocked_max_rounds",
            "candidate_gap_tasks_planned",
            "dispatch_candidate_screeners",
            "no_screenable_candidates",
        }:
            reasons = {
                "ready_for_report": "CONVERGED",
                "blocked_max_rounds": "MAX_ROUNDS_REACHED",
                "candidate_gap_tasks_planned": "CANDIDATE_GAPS_PENDING",
                "dispatch_candidate_screeners": "CANDIDATE_SCREEN_PENDING",
                "no_screenable_candidates": "NO_SCREENABLE_CANDIDATES",
            }
            return _report_terminal(
                context,
                last,
                budget={
                    "round_budget": round_budget,
                    "rounds_used": completed + 1,
                    "stop_after_dry_rounds": stop_after_dry_rounds,
                },
                stopped_reason=reasons[status],
            )
        return last
    if last and last.get("status") == "dispatch_subagents":
        result = dict(last.get("result", {}))
        result["status"] = "paused_round_budget"
        result["instruction"] = (
            f"本次 round budget 已用完；执行 resume --run-id {context['run_id']} 继续。"
        )
        terminal = run_registry.stage_envelope(result, context=context, budget={
            "round_budget": round_budget, "rounds_used": round_budget,
        })
        return _report_terminal(
            context,
            terminal,
            budget={
                "round_budget": round_budget,
                "rounds_used": round_budget,
                "stop_after_dry_rounds": stop_after_dry_rounds,
            },
            stopped_reason="ROUND_BUDGET_EXHAUSTED",
        )
    return last or run_registry.stage_envelope({
        "status": "blocked_missing_state", "reason": "state_not_initialized"
    }, context=context)


def _read_json_arg(value):
    if value and os.path.exists(value):
        with open(value, encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(value) if value else {}


def _runner_args(parser):
    parser.add_argument(
        "--runtime", default="auto",
        choices=("auto", "antigravity", "claude-code"),
        help="isolated-process host; use claude-code when running from Claude Code",
    )
    parser.add_argument(
        "--host-bin", default="",
        help="explicit host CLI path (defaults to agy or claude for --runtime)",
    )
    parser.add_argument(
        "--agy-bin", default="",
        help="deprecated compatibility alias for --host-bin with Antigravity",
    )
    parser.add_argument("--timeout-seconds", type=int, default=480)
    parser.add_argument(
        "--judge-timeout-seconds", type=int, default=240,
        help="bounded Judge timeout; capped by --timeout-seconds",
    )
    parser.add_argument("--round-budget", type=int, default=1,
                        help="safety fuse on rounds; with --stop-after-dry-rounds this "
                             "is an upper bound, not the operative stop condition")
    parser.add_argument("--stop-after-dry-rounds", type=int, default=0,
                        help="stop when this many consecutive rounds add no evidence, "
                             "probe, or seed progress (0 disables outcome-based stopping)")
    parser.add_argument("--allow-agent-tools", action="store_true")
    parser.add_argument("--stop-before-screen", action="store_true")


def _method_drift_status(run_id):
    context = run_registry.inspect_manifest(run_id)
    check = context.get("method_identity_check", {})
    state = load_json_safe(context["state_path"], default={})
    out = {
        "status": "paused_method_contract_drift",
        "topic": context["topic"],
        "state_path": context["state_path"],
        "rounds_completed": len(state.get("rounds", [])) if isinstance(state, dict) else 0,
        "last_convergence": (
            state.get("last_convergence", {}) if isinstance(state, dict) else {}
        ),
        "resumable": False,
        "reason": "method_contract_drift",
        "pinned_method_identity": check.get("pinned"),
        "current_method_identity": check.get("current"),
        "instruction": (
            "该 run 仍可只读审计，但不能在不同 method contract 下续跑或改写。"
            "如需继续研究，请用当前方法创建新 run，并把旧结论仅作为显式输入。"
        ),
    }
    return run_registry.stage_envelope(out, context=context, persist=False)


def main():
    parser = argparse.ArgumentParser(description="Resumable multi-runtime deepthink2 host runner")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--topic", required=True)
    start.add_argument("--frame-json", required=True)
    start.add_argument("--runtime-isolation", default="verified")
    start.add_argument(
        "--run-purpose", required=True, choices=sorted(run_registry.RUN_PURPOSES - {"UNSPECIFIED"})
    )
    _runner_args(start)
    adopt = sub.add_parser("adopt")
    adopt.add_argument("--topic", default="")
    adopt.add_argument("--state-path", required=True)
    resume = sub.add_parser("resume")
    resume.add_argument("--run-id", required=True)
    _runner_args(resume)
    status = sub.add_parser("status")
    status.add_argument("--run-id", required=True)
    args = parser.parse_args()

    if args.command == "status":
        try:
            context = run_registry.load_manifest(args.run_id)
        except ValueError as exc:
            if "method_contract_drift" in str(exc):
                print(json.dumps(_method_drift_status(args.run_id),
                                 ensure_ascii=False, indent=2))
            else:
                print(json.dumps({
                    "status": "run_status_error", "run_id": args.run_id,
                    "reason": str(exc),
                }, ensure_ascii=False, indent=2))
            return
        state = load_json_safe(context["state_path"], default={})
        out = {
            "status": "run_status",
            "topic": context["topic"],
            "state_path": context["state_path"],
            "rounds_completed": len(state.get("rounds", [])) if isinstance(state, dict) else 0,
            "last_convergence": state.get("last_convergence", {}) if isinstance(state, dict) else {},
            "latest_envelope": context.get("latest_envelope", {}),
            "execution_summary": run_registry.execution_summary(context["run_id"]),
            "instruction": (
                (context.get("latest_envelope") or {}).get("next_action")
                or f"执行 resume --run-id {context['run_id']} 继续。"
            ),
        }
        print(json.dumps(run_registry.stage_envelope(out, context=context, persist=False),
                         ensure_ascii=False, indent=2))
        return
    if args.command == "adopt":
        context = run_registry.adopt_manifest(args.topic, args.state_path)
        print(json.dumps(run_registry.stage_envelope({
            "status": "run_adopted", "topic": context["topic"],
            "state_path": context["state_path"],
            "instruction": f"执行 resume --run-id {context['run_id']} 继续。",
        }, context=context), ensure_ascii=False, indent=2))
        return
    if args.command == "start":
        context = run_registry.create_manifest(
            args.topic,
            runtime_isolation=args.runtime_isolation,
            run_purpose=args.run_purpose,
        )
        run_registry.bind_context(context)
        initialized = orchestrator.cmd_init(
            context["topic"], _read_json_arg(args.frame_json), args.runtime_isolation
        )
        if initialized.get("status") != "dispatch_subagents":
            print(json.dumps(run_registry.stage_envelope(initialized, context=context),
                             ensure_ascii=False, indent=2))
            return
    else:
        try:
            context = run_registry.load_manifest(args.run_id)
        except ValueError as exc:
            if "method_contract_drift" in str(exc):
                print(json.dumps(_method_drift_status(args.run_id),
                                 ensure_ascii=False, indent=2))
            else:
                print(json.dumps({
                    "status": "run_resume_error", "run_id": args.run_id,
                    "reason": str(exc),
                }, ensure_ascii=False, indent=2))
            return

    if args.agy_bin and args.host_bin and args.agy_bin != args.host_bin:
        raise SystemExit("--agy-bin and --host-bin disagree")
    host_bin = args.host_bin or args.agy_bin
    host_runtime = _resolve_host_runtime(
        "antigravity" if args.agy_bin else args.runtime,
        host_bin=host_bin,
    )
    host_bin = host_bin or _default_host_bin(host_runtime)
    if args.timeout_seconds < 30 or args.timeout_seconds > 1800:
        raise SystemExit("--timeout-seconds must be between 30 and 1800")
    if args.judge_timeout_seconds < 30 or args.judge_timeout_seconds > 1800:
        raise SystemExit("--judge-timeout-seconds must be between 30 and 1800")
    if args.round_budget < 1 or args.round_budget > 12:
        raise SystemExit("--round-budget must be between 1 and 12")
    result = continue_run(
        context,
        host_bin=host_bin,
        host_runtime=host_runtime,
        timeout_seconds=args.timeout_seconds,
        judge_timeout_seconds=args.judge_timeout_seconds,
        allow_agent_tools=args.allow_agent_tools,
        round_budget=args.round_budget,
        continue_screen=not args.stop_before_screen,
        stop_after_dry_rounds=args.stop_after_dry_rounds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
