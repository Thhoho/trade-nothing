#!/usr/bin/env python3
"""Deterministic execution truth for deepthink2.

This module is deliberately smaller than the research orchestrator.  It does not
schedule work or create another lifecycle.  It answers one question only: what
may a report truthfully claim about how its research payloads were produced?
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import method_identity


RECEIPT_SCHEMA = "trade-nothing.round-execution-receipt.v1"
AUDIT_SCHEMA = "trade-nothing.execution-integrity.v1"
MARKER_PREFIX = "<!-- TRADE_NOTHING_EXECUTION_INTEGRITY "
PROCESS_RUNNERS = {
    "antigravity": "agy_separate_process_v1",
    "claude-code": "claude_separate_process_v1",
}
SUPPORTED_RUNNERS = set(PROCESS_RUNNERS.values()) | {"codex_collaboration_v1"}


def canonical_json_hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def prompt_sha256(prompt):
    return hashlib.sha256(str(prompt or "").encode("utf-8")).hexdigest()


def judge_prompt(dispatch, detective, inquisitor):
    """Return the exact sealed Judge prompt used by supported hosts."""
    return (
        str(dispatch.get("judge_prompt") or "")
        + "\nOnly score evidence physically present in these exact payloads."
        + "\nDetective JSON:\n"
        + json.dumps(detective, ensure_ascii=False, sort_keys=True)
        + "\nInquisitor JSON:\n"
        + json.dumps(inquisitor, ensure_ascii=False, sort_keys=True)
    )


def receipt_id(receipt):
    content = dict(receipt) if isinstance(receipt, dict) else {}
    content.pop("receipt_id", None)
    return "RER-" + canonical_json_hash(content)[:12].upper()


def build_process_receipt(round_num, host_runtime, dispatch, payloads, records):
    runner_kind = PROCESS_RUNNERS.get(str(host_runtime or ""))
    if not runner_kind:
        raise ValueError("unsupported_process_receipt_runtime")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "round": int(round_num),
        "runner_kind": runner_kind,
        "host_enforced": True,
        "roles": {},
    }
    prompts = {
        "detective": dispatch.get("detective_prompt"),
        "inquisitor": dispatch.get("inquisitor_prompt"),
        "judge": judge_prompt(dispatch, payloads["detective"], payloads["inquisitor"]),
    }
    for role in ("detective", "inquisitor", "judge"):
        record = records.get(role) if isinstance(records.get(role), dict) else {}
        receipt["roles"][role] = {
            "invocation_id": str(record.get("invocation_id") or ""),
            "process_id": record.get("process_id"),
            "status": "completed" if record.get("exit_code") == 0 else "failed",
            "exit_code": record.get("exit_code"),
            "timed_out": record.get("timed_out"),
            "prompt_sha256": prompt_sha256(prompts[role]),
            "payload_sha256": canonical_json_hash(payloads[role]),
        }
    receipt["receipt_id"] = receipt_id(receipt)
    return receipt


def build_codex_receipt(round_num, dispatch, payloads, agent_ids):
    ids = [str(agent_ids.get(role) or "").strip() for role in (
        "detective", "inquisitor", "judge"
    )]
    if not all(ids) or len(set(ids)) != 3:
        raise ValueError("three distinct canonical Codex agent IDs are required")
    prompts = {
        "detective": dispatch.get("detective_prompt"),
        "inquisitor": dispatch.get("inquisitor_prompt"),
        "judge": judge_prompt(dispatch, payloads["detective"], payloads["inquisitor"]),
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "round": int(round_num),
        "runner_kind": "codex_collaboration_v1",
        "host_enforced": True,
        "roles": {},
    }
    for role, agent_id in zip(("detective", "inquisitor", "judge"), ids):
        receipt["roles"][role] = {
            "invocation_id": agent_id,
            "agent_id": agent_id,
            "context_isolation": "independent_agent_context",
            "status": "completed",
            "timed_out": False,
            "prompt_sha256": prompt_sha256(prompts[role]),
            "payload_sha256": canonical_json_hash(payloads[role]),
        }
    receipt["receipt_id"] = receipt_id(receipt)
    return receipt


def validate_round_receipt(receipt, round_num, dispatch, detective, inquisitor, judge):
    blockers = []
    receipt = receipt if isinstance(receipt, dict) else {}
    if receipt.get("schema") != RECEIPT_SCHEMA:
        blockers.append("round_receipt_schema_invalid")
    try:
        stored_round = int(receipt.get("round"))
    except (TypeError, ValueError):
        stored_round = -1
    if stored_round != int(round_num):
        blockers.append("round_receipt_round_mismatch")
    runner_kind = str(receipt.get("runner_kind") or "")
    if runner_kind not in SUPPORTED_RUNNERS:
        blockers.append("round_receipt_runner_invalid")
    if receipt.get("host_enforced") is not True:
        blockers.append("round_receipt_not_host_enforced")

    payloads = {"detective": detective, "inquisitor": inquisitor, "judge": judge}
    prompts = {
        "detective": dispatch.get("detective_prompt"),
        "inquisitor": dispatch.get("inquisitor_prompt"),
        "judge": judge_prompt(dispatch, detective, inquisitor),
    }
    roles = receipt.get("roles") if isinstance(receipt.get("roles"), dict) else {}
    invocation_ids = []
    isolation_ids = []
    process_runner = runner_kind in set(PROCESS_RUNNERS.values())
    for role in ("detective", "inquisitor", "judge"):
        item = roles.get(role) if isinstance(roles.get(role), dict) else {}
        invocation_id = str(item.get("invocation_id") or "").strip()
        if not invocation_id:
            blockers.append(f"round_receipt_{role}_invocation_missing")
        invocation_ids.append(invocation_id)
        if item.get("status") != "completed" or item.get("timed_out") is not False:
            blockers.append(f"round_receipt_{role}_not_completed")
        if process_runner:
            try:
                process_id = int(item.get("process_id"))
            except (TypeError, ValueError):
                process_id = 0
            if process_id <= 0 or item.get("exit_code") != 0:
                blockers.append(f"round_receipt_{role}_process_invalid")
            isolation_ids.append(str(process_id))
        elif runner_kind == "codex_collaboration_v1":
            agent_id = str(item.get("agent_id") or "").strip()
            if not agent_id:
                blockers.append(f"round_receipt_{role}_agent_missing")
            if item.get("context_isolation") != "independent_agent_context":
                blockers.append(f"round_receipt_{role}_context_not_isolated")
            isolation_ids.append(agent_id)
        if item.get("prompt_sha256") != prompt_sha256(prompts[role]):
            blockers.append(f"round_receipt_{role}_prompt_hash_mismatch")
        if item.get("payload_sha256") != canonical_json_hash(payloads[role]):
            blockers.append(f"round_receipt_{role}_payload_hash_mismatch")
    if len(set(invocation_ids)) != 3:
        blockers.append("round_receipt_invocations_not_distinct")
    if len(set(isolation_ids)) != 3:
        blockers.append("round_receipt_isolation_contexts_not_distinct")
    if receipt.get("receipt_id") != receipt_id(receipt):
        blockers.append("round_receipt_id_mismatch")
    unique = list(dict.fromkeys(blockers))
    return {
        "status": "verified" if not unique else "invalid",
        "receipt_id": str(receipt.get("receipt_id") or ""),
        "runner_kind": runner_kind,
        "blockers": unique,
    }


def _stored_round_receipt_status(round_record):
    if not isinstance(round_record, dict):
        return "missing"
    audit = round_record.get("execution_integrity")
    receipt = round_record.get("execution_receipt")
    if not isinstance(audit, dict) or audit.get("status") != "verified":
        return str((audit or {}).get("status") or "missing")
    if not isinstance(receipt, dict) or receipt.get("schema") != RECEIPT_SCHEMA:
        return "invalid"
    if audit.get("receipt_id") != receipt.get("receipt_id"):
        return "invalid"
    if audit.get("runner_kind") not in {None, "", receipt.get("runner_kind")}:
        return "invalid"
    if receipt.get("receipt_id") != receipt_id(receipt):
        return "invalid"
    try:
        if int(receipt.get("round")) != int(round_record.get("round")):
            return "invalid"
    except (TypeError, ValueError):
        return "invalid"
    roles = receipt.get("roles") if isinstance(receipt.get("roles"), dict) else {}
    raw_payloads = {
        "detective": round_record.get("detective_raw"),
        "inquisitor": round_record.get("inquisitor_raw"),
        "judge": round_record.get("judge_host_raw"),
    }
    invocation_ids = []
    isolation_ids = []
    runner_kind = str(receipt.get("runner_kind") or "")
    if runner_kind not in SUPPORTED_RUNNERS or receipt.get("host_enforced") is not True:
        return "invalid"
    for role in ("detective", "inquisitor", "judge"):
        item = roles.get(role) if isinstance(roles.get(role), dict) else {}
        payload = raw_payloads[role]
        if not isinstance(payload, dict):
            return "invalid"
        if item.get("status") != "completed" or item.get("timed_out") is not False:
            return "invalid"
        if item.get("payload_sha256") != canonical_json_hash(payload):
            return "invalid"
        prompt_hash = str(item.get("prompt_sha256") or "")
        if len(prompt_hash) != 64:
            return "invalid"
        invocation_ids.append(str(item.get("invocation_id") or ""))
        if runner_kind == "codex_collaboration_v1":
            if item.get("context_isolation") != "independent_agent_context":
                return "invalid"
            isolation_ids.append(str(item.get("agent_id") or ""))
        else:
            if item.get("exit_code") != 0:
                return "invalid"
            isolation_ids.append(str(item.get("process_id") or ""))
    if not all(invocation_ids) or len(set(invocation_ids)) != 3:
        return "invalid"
    if not all(isolation_ids) or len(set(isolation_ids)) != 3:
        return "invalid"
    return "verified"


def round_role_execution_verified(
    state, round_num, role, expected_payload_sha256=""
):
    """Verify one persisted role against the round's full host receipt.

    Market-facing authority must derive provenance from the immutable round
    record, never from a caller-supplied receipt ID or role label.
    """
    if role not in {"detective", "inquisitor", "judge"}:
        return False
    def same_round(item):
        try:
            return int(item.get("round", 0) or 0) == int(round_num)
        except (TypeError, ValueError):
            return False

    records = [
        item for item in (state or {}).get("rounds", [])
        if isinstance(item, dict) and same_round(item)
    ]
    if len(records) != 1 or _stored_round_receipt_status(records[0]) != "verified":
        return False
    if expected_payload_sha256:
        roles = records[0]["execution_receipt"].get("roles", {})
        role_receipt = roles.get(role) if isinstance(roles.get(role), dict) else {}
        if role_receipt.get("payload_sha256") != expected_payload_sha256:
            return False
    return isinstance(records[0].get(f"{role}_raw"), dict)


def audit_state(state):
    """Classify report claims from immutable state facts only."""
    state = state if isinstance(state, dict) else {}
    rounds = [item for item in state.get("rounds", []) if isinstance(item, dict)]
    stored_identity = state.get("method_identity")
    current_identity = method_identity.build_method_identity()
    identity_status = (
        "CURRENT" if stored_identity == current_identity
        else "UNPINNED" if not isinstance(stored_identity, dict)
        else "HISTORICAL"
    )
    statuses = [_stored_round_receipt_status(item) for item in rounds]
    verified = sum(status == "verified" for status in statuses)
    invalid = sum(status == "invalid" for status in statuses)
    missing = len(rounds) - verified - invalid
    run_id = str((state.get("runtime") or {}).get("run_id") or "")
    manifest_binding_status = "UNREGISTERED"
    manifest_method_status = "unavailable"
    if run_id:
        try:
            import run_registry
            manifest = run_registry.inspect_manifest(run_id)
            manifest_binding_status = "REGISTERED"
            manifest_method_status = str(
                (manifest.get("method_identity_check") or {}).get("status") or "unknown"
            )
            if str(manifest.get("state_path") or "") != str(
                (state.get("runtime") or {}).get("state_path") or ""
            ):
                manifest_binding_status = "STATE_PATH_MISMATCH"
        except (OSError, ValueError):
            manifest_binding_status = "MANIFEST_UNAVAILABLE"
    if identity_status == "HISTORICAL":
        mode = "HISTORICAL_REPLAY"
    elif (
        rounds and verified == len(rounds) and run_id
        and manifest_binding_status == "REGISTERED"
        and manifest_method_status == "match"
    ):
        mode = "ORCHESTRATED_VERIFIED"
    else:
        mode = "STATE_ONLY_UNVERIFIED"
    can_claim_rounds = bool(
        rounds and identity_status == "CURRENT" and verified == len(rounds)
        and mode == "ORCHESTRATED_VERIFIED"
    )
    return {
        "schema": AUDIT_SCHEMA,
        "execution_mode": mode,
        "method_identity_status": identity_status,
        "method_contract_sha256": (
            stored_identity.get("contract_sha256")
            if isinstance(stored_identity, dict) else ""
        ),
        "current_method_contract_sha256": current_identity["contract_sha256"],
        "run_id": run_id,
        "manifest_binding_status": manifest_binding_status,
        "manifest_method_identity_status": manifest_method_status,
        "state_round_records": len(rounds),
        "verified_round_receipts": verified,
        "invalid_round_receipts": invalid,
        "missing_round_receipts": missing,
        "can_claim_completed_rounds": can_claim_rounds,
        "can_claim_current_method_run": (
            identity_status == "CURRENT" and mode == "ORCHESTRATED_VERIFIED"
        ),
        "can_claim_isolated_roles": can_claim_rounds,
    }


def inline_audit(topic="", as_of_date=""):
    return {
        "schema": AUDIT_SCHEMA,
        "execution_mode": "INLINE_DEGRADED_RESEARCH",
        "method_identity_status": "CURRENT",
        "method_contract_sha256": method_identity.build_method_identity()[
            "contract_sha256"
        ],
        "topic": str(topic or ""),
        "as_of_date": str(as_of_date or ""),
        "run_id": "",
        "state_round_records": 0,
        "verified_round_receipts": 0,
        "invalid_round_receipts": 0,
        "missing_round_receipts": 0,
        "can_claim_completed_rounds": False,
        "can_claim_current_method_run": False,
        "can_claim_isolated_roles": False,
    }


def marker(audit):
    return MARKER_PREFIX + json.dumps(
        audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + " -->"


def parse_marker(markdown):
    for line in str(markdown or "").splitlines():
        stripped = line.strip()
        if stripped.startswith(MARKER_PREFIX) and stripped.endswith(" -->"):
            raw = stripped[len(MARKER_PREFIX):-4]
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                return None
            return value if isinstance(value, dict) else None
    return None


def round_label(audit):
    if audit.get("can_claim_completed_rounds"):
        return f"已验证研究轮次 {audit.get('verified_round_receipts', 0)}"
    if audit.get("execution_mode") == "HISTORICAL_REPLAY":
        return f"历史状态记录 {audit.get('state_round_records', 0)}（不得称为当前重跑）"
    if audit.get("execution_mode") == "INLINE_DEGRADED_RESEARCH":
        return "内联降级研究（无可声明轮次）"
    return (
        f"未验证状态更新 {audit.get('state_round_records', 0)}；"
        f"有效轮次收据 {audit.get('verified_round_receipts', 0)}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--state", required=True, type=Path)
    inline = sub.add_parser("inline-marker")
    inline.add_argument("--topic", default="")
    inline.add_argument("--as-of", default="")
    seal = sub.add_parser("seal-judge-prompt")
    seal.add_argument("--dispatch", required=True, type=Path)
    seal.add_argument("--detective", required=True, type=Path)
    seal.add_argument("--inquisitor", required=True, type=Path)
    seal.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "inspect":
        state = json.loads(args.state.read_text(encoding="utf-8"))
        result = audit_state(state)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "seal-judge-prompt":
        dispatch = json.loads(args.dispatch.read_text(encoding="utf-8"))
        detective = json.loads(args.detective.read_text(encoding="utf-8"))
        inquisitor = json.loads(args.inquisitor.read_text(encoding="utf-8"))
        sealed = judge_prompt(dispatch, detective, inquisitor)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(sealed, encoding="utf-8")
        print(json.dumps({
            "status": "judge_prompt_sealed",
            "path": str(args.output),
            "prompt_sha256": prompt_sha256(sealed),
        }, ensure_ascii=False))
        return
    result = inline_audit(args.topic, args.as_of)
    print(marker(result))


if __name__ == "__main__":
    main()
