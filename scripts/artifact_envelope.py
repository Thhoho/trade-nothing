#!/usr/bin/env python3
"""Content-addressed artifact envelopes for low-context orchestration.

The full artifact stays on disk. Parent contexts receive this bounded descriptor
and may load the artifact only through an explicit, hash-verifying call.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone


SCHEMA = "trade-nothing.artifact-envelope.v1"
MAX_ENVELOPE_BYTES = 16384
MAX_SUMMARY_BYTES = 8192
MAX_WARNINGS = 8
MAX_WARNING_CHARS = 500
FORBIDDEN_ENVELOPE_KEYS = {
    "payload", "raw", "raw_output", "stdout", "stderr", "transcript",
    "report_markdown", "synthesis_packet",
}


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _canonical_json_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _atomic_write_immutable(path, content):
    path = os.path.abspath(os.path.expanduser(str(path)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        with open(path, "rb") as handle:
            if handle.read() != content:
                raise ValueError("artifact_path_conflict")
        return path
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=os.path.dirname(path), prefix=".artifact-",
            suffix=".tmp", delete=False,
        ) as handle:
            tmp_path = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return path


def _bounded_summary(summary):
    if not isinstance(summary, dict):
        raise ValueError("artifact_summary_must_be_object")
    raw = _canonical_json_bytes(summary)
    if len(raw) > MAX_SUMMARY_BYTES:
        raise ValueError("artifact_summary_too_large")
    return summary


def _bounded_warnings(warnings):
    if warnings is None:
        return []
    if not isinstance(warnings, list):
        raise ValueError("artifact_warnings_must_be_list")
    return [str(item)[:MAX_WARNING_CHARS] for item in warnings[:MAX_WARNINGS]]


def _assert_no_raw_fields(value, path="envelope"):
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_ENVELOPE_KEYS:
                raise ValueError(f"raw_field_forbidden_in_envelope:{path}.{key}")
            _assert_no_raw_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_raw_fields(child, f"{path}[{index}]")


def create_bytes_artifact(
    content,
    *,
    artifact_path,
    artifact_kind,
    producer,
    media_type="application/octet-stream",
    status="READY",
    summary=None,
    warnings=None,
    next_action="",
    as_of="",
    usage=None,
):
    if not isinstance(content, bytes):
        raise ValueError("artifact_content_must_be_bytes")
    if status not in {"READY", "PARTIAL", "FAILED"}:
        raise ValueError("invalid_artifact_status")
    path = _atomic_write_immutable(artifact_path, content)
    envelope = {
        "schema": SCHEMA,
        "status": status,
        "artifact_kind": str(artifact_kind or "unknown")[:120],
        "producer": str(producer or "unknown")[:120],
        "artifact_path": path,
        "artifact_sha256": _sha256_bytes(content),
        "byte_size": len(content),
        "media_type": str(media_type or "application/octet-stream")[:160],
        "created_at": _now(),
        "as_of": str(as_of or "")[:120],
        "summary": _bounded_summary(summary or {}),
        "warnings": _bounded_warnings(warnings),
        "next_action": str(next_action or "")[:1000],
        "usage": usage if isinstance(usage, dict) else {},
        "read_policy": {
            "parent_context": "ENVELOPE_ONLY",
            "full_read_requires_explicit_verification": True,
            "prefer_exact_span": True,
        },
    }
    _assert_no_raw_fields(envelope)
    if len(_canonical_json_bytes(envelope)) > MAX_ENVELOPE_BYTES:
        raise ValueError("artifact_envelope_too_large")
    return envelope


def create_json_artifact(value, **kwargs):
    return create_bytes_artifact(
        _canonical_json_bytes(value), media_type="application/json", **kwargs
    )


def create_text_artifact(value, **kwargs):
    return create_bytes_artifact(
        str(value or "").encode("utf-8"), media_type="text/markdown; charset=utf-8",
        **kwargs,
    )


def verify(envelope, *, allowed_root=""):
    if not isinstance(envelope, dict) or envelope.get("schema") != SCHEMA:
        raise ValueError("invalid_artifact_envelope")
    _assert_no_raw_fields(envelope)
    if len(_canonical_json_bytes(envelope)) > MAX_ENVELOPE_BYTES:
        raise ValueError("artifact_envelope_too_large")
    path = os.path.abspath(os.path.expanduser(str(envelope.get("artifact_path") or "")))
    if allowed_root:
        root = os.path.abspath(os.path.expanduser(str(allowed_root)))
        if os.path.commonpath([path, root]) != root:
            raise ValueError("artifact_path_outside_allowed_root")
    if not os.path.isfile(path):
        raise ValueError("artifact_missing")
    with open(path, "rb") as handle:
        content = handle.read()
    if len(content) != int(envelope.get("byte_size", -1)):
        raise ValueError("artifact_size_mismatch")
    if _sha256_bytes(content) != envelope.get("artifact_sha256"):
        raise ValueError("artifact_hash_mismatch")
    return path


def load_json(envelope, *, allowed_root="", explicit=False):
    if not explicit:
        raise ValueError("explicit_artifact_read_required")
    path = verify(envelope, allowed_root=allowed_root)
    if envelope.get("media_type") != "application/json":
        raise ValueError("artifact_is_not_json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)

