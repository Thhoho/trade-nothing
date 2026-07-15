#!/usr/bin/env python3
"""Validate a human-gated tradenothing-next research-start packet."""

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "trade-nothing.research-start-packet.v1"
INTEGRITY_SCHEMA = "trade-nothing.research-start-integrity.v1"
QUESTION_TYPES = {
    "CONJUNCTIVE",
    "DISJUNCTIVE",
    "CAUSAL_CHAIN",
    "COMPARATIVE",
    "UNIVERSE_SEARCH",
}
DENIED_KEYS = (
    "prior_verdict",
    "support_scores",
    "candidate_state",
    "actionability",
    "prior_evidence",
)
TOP_LEVEL_KEYS = {
    "schema_version",
    "packet_id",
    "source_system",
    "created_at",
    "question",
    "lesson_context",
    "inheritance_policy",
    "integrity",
}


class PacketValidationError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_packet(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise PacketValidationError("packet must be a JSON object")
    unknown = sorted(set(raw) - TOP_LEVEL_KEYS)
    if unknown:
        raise PacketValidationError(f"unexpected top-level fields: {', '.join(unknown)}")
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise PacketValidationError("unsupported research-start packet schema")
    if raw.get("source_system") != "tradenothing-next":
        raise PacketValidationError("source_system must be tradenothing-next")
    if not re.fullmatch(r"RSP-\d{8}-[A-F0-9]{12}", str(raw.get("packet_id") or "")):
        raise PacketValidationError("packet_id is invalid")

    question = raw.get("question")
    if not isinstance(question, dict):
        raise PacketValidationError("question contract is required")
    for key in ("topic", "decision_question", "horizon", "as_of_date"):
        if not str(question.get(key) or "").strip():
            raise PacketValidationError(f"question.{key} is required")
    if question.get("question_type") not in QUESTION_TYPES:
        raise PacketValidationError("question.question_type is invalid")
    try:
        date.fromisoformat(str(question.get("as_of_date") or ""))
    except ValueError:
        raise PacketValidationError("question.as_of_date must use YYYY-MM-DD")

    lessons = raw.get("lesson_context")
    if not isinstance(lessons, list) or not 1 <= len(lessons) <= 10:
        raise PacketValidationError("lesson_context must contain 1-10 items")
    seen = set()
    for index, item in enumerate(lessons):
        if not isinstance(item, dict):
            raise PacketValidationError(f"lesson_context[{index}] must be an object")
        lesson_id = item.get("lesson_id")
        if isinstance(lesson_id, bool) or not isinstance(lesson_id, int) or lesson_id <= 0:
            raise PacketValidationError(f"lesson_context[{index}].lesson_id is invalid")
        if lesson_id in seen:
            raise PacketValidationError("lesson_context contains duplicate lesson_id")
        seen.add(lesson_id)
        for key in (
            "source_review_id",
            "title_snapshot",
            "body_snapshot",
            "activation_reason_snapshot",
            "selection_reason",
        ):
            if not item.get(key):
                raise PacketValidationError(f"lesson_context[{index}].{key} is required")

    policy = raw.get("inheritance_policy")
    if not isinstance(policy, dict):
        raise PacketValidationError("inheritance_policy is required")
    for key in DENIED_KEYS:
        if policy.get(key) is not False:
            raise PacketValidationError(f"inheritance_policy.{key} must be false")
    if policy.get("allowed_context") != [
        "question_contract",
        "human_selected_active_lesson_snapshots",
    ]:
        raise PacketValidationError("inheritance_policy.allowed_context is invalid")

    integrity = raw.get("integrity")
    if not isinstance(integrity, dict):
        raise PacketValidationError("integrity block is required")
    if integrity.get("schema_version") != INTEGRITY_SCHEMA:
        raise PacketValidationError("integrity schema is invalid")
    if integrity.get("algorithm") != "sha256":
        raise PacketValidationError("integrity algorithm must be sha256")
    if integrity.get("claim") != "human_selected_active_lessons_only_no_state_inheritance":
        raise PacketValidationError("integrity claim is invalid")
    payload = {key: value for key, value in raw.items() if key != "integrity"}
    expected = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    if integrity.get("payload_sha256") != expected:
        raise PacketValidationError("research-start packet checksum mismatch")
    return raw


def framing_context(packet: dict[str, Any]) -> dict[str, Any]:
    validated = validate_packet(packet)
    return {
        "packet_id": validated["packet_id"],
        "payload_sha256": validated["integrity"]["payload_sha256"],
        "question": validated["question"],
        "lesson_constraints": [
            {
                "lesson_id": item["lesson_id"],
                "title": item["title_snapshot"],
                "body": item["body_snapshot"],
                "applies_to": item.get("applies_to_snapshot", ""),
                "selection_reason": item["selection_reason"],
            }
            for item in validated["lesson_context"]
        ],
        "use_policy": (
            "Treat Lessons only as human-selected framing constraints. They are not facts, "
            "evidence, verdicts, scores, candidate states, or actionability signals."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", help="path to research-start packet JSON")
    args = parser.parse_args()
    try:
        raw = json.loads(Path(args.packet).read_text(encoding="utf-8"))
        context = framing_context(raw)
        print(json.dumps({"status": "accepted", "framing_context": context}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, PacketValidationError) as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
