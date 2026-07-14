#!/usr/bin/env python3
"""Immutable run identity, manifest, checkpoints, and stage envelopes for deepthink2."""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone

from utils import get_scratch_dir, load_json_safe, save_json


SCHEMA = "trade-nothing.run-manifest.v1"
ENVELOPE_SCHEMA = "trade-nothing.stage-envelope.v1"
RUN_ID_RE = re.compile(r"^RUN-[0-9]{8}-[A-F0-9]{12}$")


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_text(value):
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def runs_dir():
    return os.path.join(get_scratch_dir(), "v2-runs")


def manifest_path(run_id):
    if not RUN_ID_RE.fullmatch(str(run_id or "")):
        raise ValueError("invalid_run_id")
    return os.path.join(runs_dir(), f"{run_id}.json")


def checkpoint_dir(run_id):
    manifest_path(run_id)
    return os.path.join(runs_dir(), run_id, "checkpoints")


def checkpoint_path(run_id, stage_id):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(stage_id or "unknown"))[:120]
    return os.path.join(checkpoint_dir(run_id), f"{safe}.json")


def _validated_state_path(path):
    if not path:
        raise ValueError("state_path_required")
    expanded = os.path.abspath(os.path.expanduser(str(path)))
    scratch = os.path.abspath(os.path.expanduser(get_scratch_dir()))
    if os.path.commonpath([expanded, scratch]) != scratch:
        raise ValueError("state_path_outside_scratch")
    if not expanded.endswith(".json"):
        raise ValueError("state_path_must_be_json")
    return expanded


def new_run_id():
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"RUN-{day}-{uuid.uuid4().hex[:12].upper()}"


def create_manifest(topic, *, state_path="", as_of_date="", runtime_isolation="unverified",
                    adopted=False):
    topic = str(topic or "").strip()
    if not topic:
        raise ValueError("topic_required")
    run_id = new_run_id()
    state_path = _validated_state_path(state_path) if state_path else _validated_state_path(
        os.path.join(get_scratch_dir(), "v2-state", f"{run_id}_v2_state.json")
    )
    manifest = {
        "schema": SCHEMA,
        "run_id": run_id,
        "topic": topic,
        "question_sha256": _sha256_text(topic),
        "as_of_date": str(as_of_date or ""),
        "state_path": state_path,
        "created_at": _now(),
        "updated_at": _now(),
        "stage": "adopted" if adopted else "created",
        "status": "active",
        "runtime_isolation": str(runtime_isolation or "unverified"),
        "latest_envelope": {},
        "failure_count": 0,
    }
    save_json(manifest_path(run_id), manifest)
    return manifest


def adopt_manifest(topic, state_path):
    path = _validated_state_path(state_path)
    state = load_json_safe(path, default=None)
    if not isinstance(state, dict):
        raise ValueError("state_path_not_valid_state")
    state_topic = str(state.get("topic") or "").strip()
    topic = str(topic or state_topic).strip()
    if state_topic and topic != state_topic:
        raise ValueError("topic_state_mismatch")
    return create_manifest(
        topic,
        state_path=path,
        as_of_date=(state.get("frame_contract") or {}).get("as_of_date", ""),
        runtime_isolation=(state.get("runtime_contract") or {}).get(
            "isolation_status", "unverified"
        ),
        adopted=True,
    )


def load_manifest(run_id):
    data = load_json_safe(manifest_path(run_id), default=None)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ValueError("run_manifest_not_found_or_invalid")
    if data.get("run_id") != run_id:
        raise ValueError("run_manifest_id_mismatch")
    data["state_path"] = _validated_state_path(data.get("state_path"))
    return data


def resolve_context(*, run_id="", state_path="", topic=""):
    if run_id and state_path:
        raise ValueError("run_id_and_state_path_are_mutually_exclusive")
    if run_id:
        manifest = load_manifest(run_id)
        supplied_topic = str(topic or "").strip()
        if supplied_topic and supplied_topic != manifest["topic"]:
            raise ValueError("topic_run_mismatch")
        return manifest
    if state_path:
        path = _validated_state_path(state_path)
        state = load_json_safe(path, default=None)
        if not isinstance(state, dict):
            raise ValueError("state_path_not_valid_state")
        state_topic = str(state.get("topic") or "").strip()
        supplied_topic = str(topic or "").strip()
        if supplied_topic and state_topic and supplied_topic != state_topic:
            raise ValueError("topic_state_mismatch")
        return {
            "run_id": "",
            "topic": state_topic or supplied_topic,
            "state_path": path,
            "schema": "state-path-only",
        }
    return None


def bind_context(context):
    if not context:
        return
    os.environ["TRADE_NOTHING_STATE_PATH"] = context["state_path"]
    if context.get("run_id"):
        os.environ["TRADE_NOTHING_RUN_ID"] = context["run_id"]


def save_checkpoint(run_id, stage_id, payload):
    body = dict(payload or {})
    body.setdefault("schema", "trade-nothing.host-checkpoint.v1")
    body.setdefault("run_id", run_id)
    body.setdefault("stage_id", stage_id)
    body["updated_at"] = _now()
    save_json(checkpoint_path(run_id, stage_id), body)
    return body


def load_checkpoint(run_id, stage_id):
    data = load_json_safe(checkpoint_path(run_id, stage_id), default={})
    return data if isinstance(data, dict) else {}


def _stage_for_status(status):
    status = str(status or "unknown")
    if "frame" in status or status == "need_framing":
        return "framing"
    if status in {"dispatch_subagents", "paused_runtime_failure"}:
        return "debate"
    if "screen" in status:
        return "candidate_screen"
    if "verification" in status or "snapshot" in status:
        return "claim_verification"
    if "report" in status or status == "resolution_memo_ready":
        return "report"
    return "control"


def stage_envelope(result, *, context=None, budget=None, persist=True):
    result = dict(result or {})
    context = context or {}
    status = str(result.get("status") or "unknown")
    blockers = []
    for key in ("issues", "blockers", "unresolved_cruxes", "missing_roles"):
        value = result.get(key)
        if isinstance(value, list):
            blockers.extend(str(item) for item in value if item)
    if result.get("reason"):
        blockers.append(str(result["reason"]))
    artifact_paths = {}
    for key in (
        "audit_state_path", "receipt_path", "report_path", "state_path", "checkpoint_path"
    ):
        if result.get(key):
            artifact_paths[key] = result[key]
    envelope = {
        "schema": ENVELOPE_SCHEMA,
        "run_id": context.get("run_id", ""),
        "topic": context.get("topic") or result.get("topic", ""),
        "stage": _stage_for_status(status),
        "status": status,
        "next_action": result.get("instruction", ""),
        "blockers": list(dict.fromkeys(blockers)),
        "artifact_paths": artifact_paths,
        "budget": budget or {},
        "result": result,
    }
    run_id = context.get("run_id")
    if run_id and persist:
        manifest = load_manifest(run_id)
        manifest["updated_at"] = _now()
        manifest["stage"] = envelope["stage"]
        manifest["latest_envelope"] = {
            key: envelope[key]
            for key in (
                "schema", "run_id", "stage", "status", "next_action", "blockers",
                "artifact_paths", "budget",
            )
        }
        if status.startswith("paused_") or status.startswith("blocked_runtime"):
            manifest["failure_count"] = int(manifest.get("failure_count", 0)) + 1
        save_json(manifest_path(run_id), manifest)
    return envelope


def execution_summary(run_id):
    root = checkpoint_dir(run_id)
    summary = {
        "checkpoint_count": 0,
        "submitted_rounds": 0,
        "role_attempts": 0,
        "role_successes": 0,
        "elapsed_seconds": 0.0,
        "last_error_code": "",
    }
    if not os.path.isdir(root):
        return summary
    for name in sorted(os.listdir(root)):
        if not name.endswith(".json"):
            continue
        checkpoint = load_json_safe(os.path.join(root, name), default={})
        if not isinstance(checkpoint, dict):
            continue
        summary["checkpoint_count"] += 1
        if checkpoint.get("submitted"):
            summary["submitted_rounds"] += 1
        records = list((checkpoint.get("roles") or {}).values())
        if isinstance(checkpoint.get("judge"), dict):
            records.append(checkpoint["judge"])
        for record in records:
            if not isinstance(record, dict):
                continue
            summary["role_attempts"] += 1
            summary["elapsed_seconds"] += float(record.get("elapsed_seconds") or 0)
            if record.get("exit_code") == 0 and record.get("payload_sha256"):
                summary["role_successes"] += 1
            if record.get("error_code"):
                summary["last_error_code"] = str(record["error_code"])
    summary["elapsed_seconds"] = round(summary["elapsed_seconds"], 3)
    return summary


def canonical_json_hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
