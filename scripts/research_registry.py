#!/usr/bin/env python3
"""Minimal v0.18 run registry with content-addressed derived artifacts."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

import method_identity
import research_io


SCHEMA = "trade-nothing.research-manifest.v2"
MANIFEST_FIELDS = {
    "schema_version", "run_id", "topic", "question_sha256", "as_of_date",
    "state_path", "created_at", "requested_execution_mode", "run_purpose",
    "method_identity",
}
RUN_ID_RE = re.compile(r"^RUN-[0-9]{8}-[A-F0-9]{12}$")
SAFE_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
RUN_PURPOSES = {
    "UNSPECIFIED", "PRODUCTION_RESEARCH", "LIVE_DISCOVERY_BENCHMARK",
    "CLOSED_PACKET_BENCHMARK", "HISTORICAL_REPLAY", "CONTROLLED_FIXTURE",
}


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_json_hash(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_run_purpose(value):
    value = str(value or "UNSPECIFIED").strip().upper()
    if value not in RUN_PURPOSES:
        raise ValueError("run_purpose_invalid")
    return value


def _run_id(value):
    value = str(value or "")
    if not RUN_ID_RE.fullmatch(value):
        raise ValueError("invalid_run_id")
    return value


def new_run_id():
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"RUN-{day}-{uuid.uuid4().hex[:12].upper()}"


def runs_dir():
    return research_io.scratch_dir() / "research-runs"


def run_dir(run_id):
    return runs_dir() / _run_id(run_id)


def manifest_path(run_id):
    return str(run_dir(run_id) / "manifest.json")


def state_path(run_id):
    return str(run_dir(run_id) / "state.json")


def checkpoint_path(run_id, stage_id):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(stage_id or "unknown"))[:120]
    if not safe or safe in {".", ".."}:
        raise ValueError("checkpoint_stage_id_invalid")
    return str(run_dir(run_id) / "checkpoints" / f"{safe}.json")


def create_manifest(topic, *, as_of_date="", requested_execution_mode="UNVERIFIED",
                    run_purpose="UNSPECIFIED"):
    topic = " ".join(str(topic or "").split())
    if not topic:
        raise ValueError("topic_required")
    run_id = new_run_id()
    purpose = normalize_run_purpose(run_purpose)
    identity = method_identity.build_method_identity()
    manifest = {
        "schema_version": SCHEMA,
        "run_id": run_id,
        "topic": topic,
        "question_sha256": hashlib.sha256(topic.encode("utf-8")).hexdigest(),
        "as_of_date": str(as_of_date or ""),
        "state_path": str(state_path(run_id)),
        "created_at": _now(),
        "requested_execution_mode": str(
            requested_execution_mode or "UNVERIFIED"
        ).upper(),
        "run_purpose": purpose,
        "method_identity": identity,
    }
    research_io.save_json(manifest_path(run_id), manifest, create_only=True)
    return manifest


def _load_structural(run_id):
    run_id = _run_id(run_id)
    manifest = research_io.load_json(manifest_path(run_id), default=None)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA:
        raise ValueError("research_manifest_not_found_or_invalid")
    if set(manifest) != MANIFEST_FIELDS:
        raise ValueError("research_manifest_fields_invalid")
    if manifest.get("run_id") != run_id:
        raise ValueError("research_manifest_id_mismatch")
    expected_question_hash = hashlib.sha256(
        str(manifest.get("topic") or "").encode("utf-8")
    ).hexdigest()
    if manifest.get("question_sha256") != expected_question_hash:
        raise ValueError("research_manifest_question_drift")
    if manifest.get("state_path") != str(state_path(run_id)):
        raise ValueError("research_manifest_state_path_drift")
    manifest["run_purpose"] = normalize_run_purpose(manifest.get("run_purpose"))
    return manifest


def inspect_manifest(run_id):
    manifest = _load_structural(run_id)
    current = method_identity.build_method_identity()
    manifest["method_identity_check"] = {
        "status": "match" if manifest.get("method_identity") == current else "drift",
        "pinned": manifest.get("method_identity"),
        "current": current,
    }
    return manifest


def load_manifest(run_id):
    manifest = _load_structural(run_id)
    method_identity.validate_method_identity(manifest.get("method_identity"))
    return manifest


def bind_context(manifest):
    if not isinstance(manifest, dict):
        raise ValueError("research_manifest_required")
    os.environ["TRADE_NOTHING_STATE_PATH"] = manifest["state_path"]
    os.environ["TRADE_NOTHING_RUN_ID"] = manifest["run_id"]
    os.environ["TRADE_NOTHING_RUN_PURPOSE"] = manifest["run_purpose"]


def save_checkpoint(run_id, stage_id, payload):
    body = dict(payload or {})
    body.update({
        "schema_version": "trade-nothing.research-checkpoint.v1",
        "run_id": _run_id(run_id),
        "stage_id": str(stage_id),
        "updated_at": _now(),
    })
    research_io.save_json(checkpoint_path(run_id, stage_id), body)
    return body


def load_checkpoint(run_id, stage_id):
    value = research_io.load_json(checkpoint_path(run_id, stage_id), default={})
    return value if isinstance(value, dict) else {}


def save_derived_artifact(run_id, name, content, *, suffix=".md"):
    if not SAFE_NAME_RE.fullmatch(str(name or "")):
        raise ValueError("artifact_name_invalid")
    if suffix not in {".md", ".json"}:
        raise ValueError("artifact_suffix_invalid")
    rendered = content if isinstance(content, str) else canonical_json(content) + "\n"
    encoded = rendered.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    destination = run_dir(run_id) / "artifacts" / f"{name}-{digest[:16]}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != encoded:
            raise ValueError("artifact_content_address_collision")
        destination.chmod(0o444)
        return {
            "path": str(destination), "sha256": digest, "bytes": len(encoded)
        }
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        destination.chmod(0o444)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"path": str(destination), "sha256": digest, "bytes": len(encoded)}
