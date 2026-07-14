#!/usr/bin/env python3
"""Bounded, resumable Antigravity host runner for deepthink2.

The deterministic orchestrator remains authoritative. This adapter owns process
dispatch, stage checkpoints, run identity, and fail-closed continuation.
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
import deepthink_orchestrator_v2 as orchestrator
import run_registry
from utils import get_skill_dir, load_json_safe


def _prompt_hash(prompt):
    return hashlib.sha256(str(prompt).encode("utf-8")).hexdigest()


def _parse_json_output(text):
    text = str(text or "").strip()
    if not text:
        raise ValueError("empty_role_output")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("role_output_must_be_exact_json") from exc
    if not isinstance(payload, dict):
        raise ValueError("role_output_must_be_json_object")
    return payload


def _command(agy_bin, prompt, timeout_seconds, allow_agent_tools=False):
    command = [agy_bin, "--print", prompt, "--print-timeout", f"{timeout_seconds}s"]
    if allow_agent_tools:
        command.append("--dangerously-skip-permissions")
    return command


def _run_role(role, prompt, agy_bin, timeout_seconds, allow_agent_tools=False, workdir=""):
    wrapped = (
        f"You are the isolated deepthink2 {role} role. Return exactly one JSON object and no "
        "markdown, commentary, progress notes, transcript, or file link. Do not read or infer "
        "another role's output.\n\n" + prompt
    )
    started = time.monotonic()
    if workdir:
        os.makedirs(workdir, exist_ok=True)
    process = subprocess.Popen(
        _command(agy_bin, wrapped, timeout_seconds, allow_agent_tools),
        cwd=workdir or get_skill_dir(),
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
    payload = None
    parse_error = ""
    if process.returncode == 0 and not timed_out:
        try:
            payload = _parse_json_output(stdout)
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
            "parse_error", "resource_exhausted", "error_code",
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


def _pause(context, stage_id, checkpoint, missing_roles, reason):
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
    }, context=context)


def execute_round(context, *, agy_bin, timeout_seconds, allow_agent_tools=False):
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
    if checkpoint["prompt_sha256"] != {
        role: _prompt_hash(prompt) for role, prompt in role_prompts.items()
    }:
        return _pause(
            context, stage_id, checkpoint, ["manual_review"], "checkpoint_prompt_hash_mismatch"
        )
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
                    _run_role, role, role_prompts[role], agy_bin, timeout_seconds,
                    allow_agent_tools, os.path.join(role_root, role),
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
        return _pause(context, stage_id, checkpoint, failed, reason)

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
            "judge", judge_prompt, agy_bin, timeout_seconds, allow_agent_tools,
            judge_workdir,
        ))
        checkpoint["judge"] = judge_record
        run_registry.save_checkpoint(context["run_id"], stage_id, checkpoint)
    if not _checkpoint_role_valid(judge_record, judge_prompt):
        reason = (
            "resource_exhausted_429"
            if judge_record.get("resource_exhausted") else "judge_failure"
        )
        return _pause(context, stage_id, checkpoint, ["judge"], reason)

    result = orchestrator.cmd_submit(
        context["topic"], detective, inquisitor, judge_record["payload"]
    )
    checkpoint["submitted"] = True
    checkpoint["submit_result"] = result
    checkpoint["status"] = result.get("status")
    run_registry.save_checkpoint(context["run_id"], stage_id, checkpoint)
    return run_registry.stage_envelope(result, context=context)


def continue_run(context, *, agy_bin, timeout_seconds, allow_agent_tools=False,
                 round_budget=1, continue_screen=True):
    run_registry.bind_context(context)
    last = None
    for completed in range(round_budget):
        state = load_json_safe(context["state_path"], default=None)
        if not isinstance(state, dict):
            break
        if (state.get("last_convergence") or {}).get("decision") == "converge":
            result = orchestrator.cmd_report(context["topic"])
            last = run_registry.stage_envelope(result, context=context, budget={
                "round_budget": round_budget, "rounds_used": completed,
            })
        else:
            last = execute_round(
                context, agy_bin=agy_bin, timeout_seconds=timeout_seconds,
                allow_agent_tools=allow_agent_tools,
            )
        status = last.get("status")
        raw = last.get("result", {})
        if status == "dispatch_subagents":
            continue
        if status == "dispatch_candidate_screeners" and continue_screen:
            screen = agy_candidate_screen_runner.run(
                context["topic"], raw.get("as_of_date", ""), agy_bin, timeout_seconds,
                allow_agent_tools=allow_agent_tools,
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
        return last
    if last and last.get("status") == "dispatch_subagents":
        result = dict(last.get("result", {}))
        result["status"] = "paused_round_budget"
        result["instruction"] = (
            f"本次 round budget 已用完；执行 resume --run-id {context['run_id']} 继续。"
        )
        return run_registry.stage_envelope(result, context=context, budget={
            "round_budget": round_budget, "rounds_used": round_budget,
        })
    return last or run_registry.stage_envelope({
        "status": "blocked_missing_state", "reason": "state_not_initialized"
    }, context=context)


def _read_json_arg(value):
    if value and os.path.exists(value):
        with open(value, encoding="utf-8") as fh:
            return json.load(fh)
    return json.loads(value) if value else {}


def _runner_args(parser):
    parser.add_argument("--agy-bin", default=shutil.which("agy") or "agy")
    parser.add_argument("--timeout-seconds", type=int, default=480)
    parser.add_argument("--round-budget", type=int, default=1)
    parser.add_argument("--allow-agent-tools", action="store_true")
    parser.add_argument("--stop-before-screen", action="store_true")


def main():
    parser = argparse.ArgumentParser(description="Resumable deepthink2 Antigravity host runner")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--topic", required=True)
    start.add_argument("--frame-json", required=True)
    start.add_argument("--runtime-isolation", default="verified")
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
        context = run_registry.load_manifest(args.run_id)
        state = load_json_safe(context["state_path"], default={})
        out = {
            "status": "run_status",
            "topic": context["topic"],
            "state_path": context["state_path"],
            "rounds_completed": len(state.get("rounds", [])) if isinstance(state, dict) else 0,
            "last_convergence": state.get("last_convergence", {}) if isinstance(state, dict) else {},
            "latest_envelope": context.get("latest_envelope", {}),
        }
        print(json.dumps(run_registry.stage_envelope(out, context=context),
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
            args.topic, runtime_isolation=args.runtime_isolation
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
        context = run_registry.load_manifest(args.run_id)

    if args.timeout_seconds < 30 or args.timeout_seconds > 1800:
        raise SystemExit("--timeout-seconds must be between 30 and 1800")
    if args.round_budget < 1 or args.round_budget > 12:
        raise SystemExit("--round-budget must be between 1 and 12")
    result = continue_run(
        context,
        agy_bin=args.agy_bin,
        timeout_seconds=args.timeout_seconds,
        allow_agent_tools=args.allow_agent_tools,
        round_budget=args.round_budget,
        continue_screen=not args.stop_before_screen,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
