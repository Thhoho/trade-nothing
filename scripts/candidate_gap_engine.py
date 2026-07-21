#!/usr/bin/env python3
"""Deterministic candidate-evidence maturation after root convergence.

The gap loop converts a blocked OpportunitySeed into a bounded research task.
Original seeds are immutable. New evidence, including failed alignment attempts,
is appended as content-addressed supplements and task resolutions.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

import crux_engine
import opportunity_engine


TASK_SCHEMA = "trade-nothing.candidate-gap-task.v1"
SUPPLEMENT_SCHEMA = "trade-nothing.candidate-evidence-supplement.v1"
RESOLUTION_SCHEMA = "trade-nothing.candidate-gap-resolution.v1"

TASK_PLANNED = "PLANNED"
RESOLUTION_STATUSES = {"COMPLETED", "SOURCE_EXHAUSTED", "WAITING_EVENT"}
ALIGNMENTS = {"SUPPORTED", "CONTRADICTED", "NOT_ALIGNED"}
MAX_BATCH = 3
DEFAULT_SEARCH_BUDGET = 4

FIELD_TARGETS = {
    "missing_economic_exposure": "economic_exposure",
    "missing_expectation_gap": "why_market_may_miss",
    "missing_structured_pricing_anchor": "pricing_anchor",
    "pricing_anchor_missing_as_of": "pricing_anchor",
    "pricing_anchor_missing_type": "pricing_anchor",
    "pricing_anchor_missing_metric": "pricing_anchor",
    "pricing_anchor_missing_current_value": "pricing_anchor",
    "pricing_anchor_missing_comparison_value": "pricing_anchor",
    "pricing_anchor_missing_source": "pricing_anchor",
    "pricing_anchor_missing_source_url": "pricing_anchor",
    "pricing_anchor_missing_source_claim": "pricing_anchor",
    "pricing_anchor_invalid_type": "pricing_anchor",
    "pricing_anchor_invalid_as_of": "pricing_anchor",
    "pricing_anchor_invalid_source_url": "pricing_anchor",
    "pricing_anchor_source_not_seed_evidence": "pricing_anchor",
    "missing_catalyst": "catalyst",
    "catalyst_window_incomplete": "catalyst_window",
    "missing_falsifier": "falsifier",
}

BLOCKER_PRIORITY = {
    "missing_economic_exposure": 0,
    "missing_expectation_gap": 1,
    "missing_structured_pricing_anchor": 2,
    "insufficient_independent_seed_sources": 3,
    "missing_catalyst": 4,
    "catalyst_window_incomplete": 5,
    "missing_falsifier": 6,
}

ALLOWED_FIELD_ADDITIONS = {
    "economic_exposure",
    "why_market_may_miss",
    "pricing_anchor",
    "catalyst",
    "catalyst_window",
    "falsifier",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(prefix: str, value: Any, length: int = 12) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:length].upper()}"


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _state_lists(state: dict[str, Any]) -> None:
    state.setdefault("candidate_gap_tasks", [])
    state.setdefault("candidate_evidence_supplements", [])
    state.setdefault("candidate_gap_resolutions", [])


def _seed_by_id(state: dict[str, Any], seed_id: str) -> dict[str, Any] | None:
    return next(
        (
            seed
            for seed in state.get("opportunity_seeds", [])
            if isinstance(seed, dict) and seed.get("seed_id") == seed_id
        ),
        None,
    )


def _task_by_id(state: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    return next(
        (
            task
            for task in state.get("candidate_gap_tasks", [])
            if isinstance(task, dict) and task.get("task_id") == task_id
        ),
        None,
    )


def _resolution_for_task(state: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in state.get("candidate_gap_resolutions", [])
            if isinstance(item, dict) and item.get("task_id") == task_id
        ),
        None,
    )


def task_status(state: dict[str, Any], task: dict[str, Any]) -> str:
    resolution = _resolution_for_task(state, str(task.get("task_id") or ""))
    return str((resolution or {}).get("status") or TASK_PLANNED)


def open_task_for_seed(state: dict[str, Any], seed_id: str) -> dict[str, Any] | None:
    for task in state.get("candidate_gap_tasks", []):
        if not isinstance(task, dict) or task.get("seed_id") != seed_id:
            continue
        if task_status(state, task) == TASK_PLANNED:
            return task
    return None


def latest_resolution_for_seed(
    state: dict[str, Any], seed_id: str
) -> dict[str, Any] | None:
    task_ids = {
        str(task.get("task_id") or "")
        for task in state.get("candidate_gap_tasks", [])
        if isinstance(task, dict) and task.get("seed_id") == seed_id
    }
    matches = [
        item
        for item in state.get("candidate_gap_resolutions", [])
        if isinstance(item, dict) and item.get("task_id") in task_ids
    ]
    return matches[-1] if matches else None


def _blocker(seed_assessment: dict[str, Any]) -> str:
    blockers = [str(item) for item in seed_assessment.get("blockers", []) if item]
    def priority(item: str) -> int:
        if item.startswith("pricing_anchor"):
            return 2
        return BLOCKER_PRIORITY.get(item, 50)

    blockers.sort(key=lambda item: (priority(item), item))
    return blockers[0] if blockers else "seed_evidence_incomplete"


def _target_claim(seed: dict[str, Any], blocker: str) -> str:
    causal = _text(seed.get("causal_path"))
    candidate = _text(seed.get("candidate"))
    if blocker == "insufficient_independent_seed_sources":
        return f"由第二个独立来源直接验证或反驳同一价值路径：{causal}"
    field = FIELD_TARGETS.get(blocker)
    if field:
        return f"用具体来源补齐 {candidate} 的 {field}，并保持与该价值路径一致：{causal}"
    return f"关闭 {candidate} 的候选阻塞 {blocker}：{causal}"


def _task_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(record.get(key))
        for key in (
            "schema_version",
            "run_id",
            "seed_id",
            "entity_id",
            "entity_identity",
            "candidate",
            "ticker",
            "origin_crux",
            "relation_type",
            "causal_path",
            "blocker_code",
            "field_target",
            "target_claim",
            "required_source_types",
            "excluded_publishers",
            "as_of_date",
            "search_budget",
            "success_condition",
            "failure_condition",
            "status",
            "created_from_state_sha256",
        )
    }


def _required_source_types(seed: dict[str, Any], blocker: str) -> list[str]:
    if blocker.startswith("pricing_anchor") or blocker in {
        "missing_expectation_gap",
        "missing_structured_pricing_anchor",
    }:
        return ["MARKET_DATA", "CUSTOMER_OR_COMPARABLE", "REGULATOR_OR_FILING"]
    relation = str(seed.get("relation_type") or "").upper()
    if relation in {"BOTTLENECK_OWNER", "INFRA_ASSET_OWNER", "DIRECT_WINNER"}:
        return ["CUSTOMER", "REGULATOR", "PROJECT_OWNER"]
    if relation == "SHORT_CANDIDATE":
        return ["CUSTOMER", "REGULATOR", "CREDITOR_OR_COUNTERPARTY"]
    return ["CUSTOMER", "REGULATOR", "INDEPENDENT_INDUSTRY_SOURCE"]


def _candidate_rank(state: dict[str, Any], seed: dict[str, Any]) -> tuple[Any, ...]:
    effective = opportunity_engine.effective_seed(state, seed)
    assessment = opportunity_engine.assess_seed(state, seed)
    blockers = assessment.get("blockers", [])
    sources = {
        crux_engine.citation_publisher_identity(item)
        for item in effective.get("evidence", [])
        if crux_engine.valid_citation(item)
    }
    window = effective.get("catalyst_window")
    expected_by = str((window or {}).get("expected_by") or "9999-12-31")
    return (
        len(blockers),
        -len(sources),
        expected_by,
        str(seed.get("seed_id") or ""),
    )


def plan_tasks(state: dict[str, Any], max_batch: int = MAX_BATCH) -> dict[str, Any]:
    """Append at most one bounded gap task per entity and return task packets."""
    _state_lists(state)
    if state.get("last_convergence", {}).get("decision") != "converge":
        return {
            "status": "blocked_unconverged",
            "tasks": [],
            "instruction": "根研究尚未收敛，禁止候选补证任务。",
        }
    max_batch = max(1, min(int(max_batch or MAX_BATCH), MAX_BATCH))
    groups: dict[str, list[dict[str, Any]]] = {}
    for seed in state.get("opportunity_seeds", []):
        if not isinstance(seed, dict) or not seed.get("seed_id"):
            continue
        if opportunity_engine.candidate_state(state, seed) != opportunity_engine.EVIDENCE_BACKED:
            continue
        # Candidate supplements can only append seed evidence or fill an empty
        # seed-contract field.  They cannot rewrite a converged root crux or a
        # Landscape path, so do not manufacture tasks for immutable origin
        # blockers that no legal supplement could ever clear.
        effective = opportunity_engine.effective_seed(state, seed)
        if opportunity_engine._origin_gate(state, effective):
            continue
        if opportunity_engine._candidate_gap_blockers(state, str(seed["seed_id"])):
            continue
        if open_task_for_seed(state, str(seed["seed_id"])):
            continue
        groups.setdefault(opportunity_engine.entity_identity(seed), []).append(seed)

    selected = []
    for identity, paths in groups.items():
        paths.sort(key=lambda seed: _candidate_rank(state, seed))
        selected.append((identity, paths[0]))
    selected.sort(key=lambda item: _candidate_rank(state, item[1]))

    new_tasks = []
    as_of = str((state.get("frame_contract") or {}).get("as_of_date") or "")
    run_id = str((state.get("runtime") or {}).get("run_id") or "")
    origin_state_sha256 = hashlib.sha256(
        canonical_json(state).encode("utf-8")
    ).hexdigest()
    for identity, seed in selected[:max_batch]:
        assessment = opportunity_engine.assess_seed(state, seed)
        blocker = _blocker(assessment)
        effective = opportunity_engine.effective_seed(state, seed)
        excluded_publishers = sorted(
            {
                crux_engine.citation_publisher_identity(item)
                for item in effective.get("evidence", [])
                if crux_engine.valid_citation(item)
                and crux_engine.citation_publisher_identity(item)
            }
        )
        task = {
            "schema_version": TASK_SCHEMA,
            "run_id": run_id,
            "seed_id": seed.get("seed_id"),
            "entity_id": opportunity_engine.entity_id(seed),
            "entity_identity": identity,
            "candidate": seed.get("candidate"),
            "ticker": seed.get("ticker"),
            "origin_crux": seed.get("origin_crux"),
            "relation_type": seed.get("relation_type"),
            "causal_path": seed.get("causal_path"),
            "blocker_code": blocker,
            "field_target": FIELD_TARGETS.get(blocker),
            "target_claim": _target_claim(seed, blocker),
            "required_source_types": _required_source_types(seed, blocker),
            "excluded_publishers": excluded_publishers,
            "as_of_date": as_of,
            "search_budget": DEFAULT_SEARCH_BUDGET,
            "success_condition": (
                "新来源必须来自未使用的独立 publisher，并直接支持或反驳同一 seed、"
                "origin crux 与 causal path。"
            ),
            "failure_condition": "搜索预算耗尽后仍无 claim-aligned 独立来源。",
            "status": TASK_PLANNED,
            "created_from_state_sha256": origin_state_sha256,
        }
        task["task_sha256"] = hashlib.sha256(
            canonical_json(_task_payload(task)).encode("utf-8")
        ).hexdigest()
        task["task_id"] = _digest("CGT", {"task_sha256": task["task_sha256"]})
        if not _task_by_id(state, task["task_id"]):
            state["candidate_gap_tasks"].append(task)
            new_tasks.append(task)

    return {
        "status": "candidate_gap_tasks_planned" if new_tasks else "no_candidate_gap_tasks",
        "tasks": copy.deepcopy(new_tasks),
        "task_count": len(new_tasks),
        "instruction": (
            "逐个执行有界候选补证任务；不得修改原 seed。"
            if new_tasks
            else "没有新的可调度候选补证任务。"
        ),
    }


def _validate_field_additions(
    task: dict[str, Any], seed: dict[str, Any], additions: Any
) -> dict[str, Any]:
    if additions in (None, {}):
        return {}
    if not isinstance(additions, dict) or not set(additions).issubset(ALLOWED_FIELD_ADDITIONS):
        raise ValueError("field_additions contains unsupported fields")
    target = task.get("field_target")
    if set(additions) != {target}:
        raise ValueError("field_additions must fill only the task field_target")
    value = additions[target]
    if target in {"pricing_anchor", "catalyst_window"}:
        if not isinstance(value, dict) or not value:
            raise ValueError(f"field_additions.{target} must be a non-empty object")
        existing = seed.get(target)
        existing = existing if isinstance(existing, dict) else {}
        if any(existing.get(key) not in (None, "", {}) for key in value):
            raise ValueError("field_additions cannot overwrite an existing seed field")
    elif not _text(value):
        raise ValueError(f"field_additions.{target} must be non-empty")
    elif seed.get(target) not in (None, "", {}):
        raise ValueError("field_additions cannot overwrite an existing seed field")
    return copy.deepcopy(additions)


def _supplement_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(record.get(key))
        for key in (
            "schema_version",
            "task_id",
            "seed_id",
            "origin_crux",
            "claim_alignment",
            "source_identity",
            "source_type",
            "citation",
            "field_additions",
            "alignment_rationale",
        )
    }


def _resolution_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(record.get(key))
        for key in (
            "schema_version",
            "task_id",
            "seed_id",
            "status",
            "reason",
            "last_supplement_id",
        )
    }


def _append_resolution(
    state: dict[str, Any], task: dict[str, Any], status: str, reason: str,
    last_supplement_id: str = "",
) -> dict[str, Any]:
    if _resolution_for_task(state, task["task_id"]):
        raise ValueError("candidate gap task is already resolved")
    record = {
        "schema_version": RESOLUTION_SCHEMA,
        "task_id": task["task_id"],
        "seed_id": task["seed_id"],
        "status": status,
        "reason": _text(reason),
        "last_supplement_id": last_supplement_id or None,
    }
    record["submission_sha256"] = hashlib.sha256(
        canonical_json(_resolution_payload(record)).encode("utf-8")
    ).hexdigest()
    record["resolution_id"] = _digest(
        "CGR", {"task_id": task["task_id"], "submission_sha256": record["submission_sha256"]}
    )
    state["candidate_gap_resolutions"].append(record)
    return record


def submit_supplement(
    state: dict[str, Any], task_id: str, raw: dict[str, Any]
) -> dict[str, Any]:
    """Validate and append one evidence attempt without mutating the seed."""
    _state_lists(state)
    task = _task_by_id(state, task_id)
    if task is None:
        raise ValueError("candidate gap task not found")
    if task_status(state, task) != TASK_PLANNED:
        raise ValueError("candidate gap task is already resolved")
    seed = _seed_by_id(state, str(task.get("seed_id") or ""))
    if seed is None:
        raise ValueError("candidate gap task references an unknown seed")
    raw = raw if isinstance(raw, dict) else {}
    alignment = _text(raw.get("claim_alignment")).upper()
    if alignment not in ALIGNMENTS:
        raise ValueError("claim_alignment is invalid")
    if not _text(raw.get("alignment_rationale")):
        raise ValueError("alignment_rationale is required")
    citation = raw.get("citation")
    if not isinstance(citation, dict) or not crux_engine.valid_citation(citation):
        raise ValueError("candidate evidence supplement requires a valid concrete citation")
    source_identity = crux_engine.citation_publisher_identity(citation)
    if not source_identity:
        raise ValueError("candidate evidence supplement has no publisher identity")
    existing_publishers = set(task.get("excluded_publishers") or [])
    if alignment in {"SUPPORTED", "CONTRADICTED"} and source_identity in existing_publishers:
        raise ValueError("candidate evidence supplement publisher is not independent")
    additions = _validate_field_additions(
        task,
        opportunity_engine.effective_seed(state, seed),
        raw.get("field_additions"),
    )
    if alignment != "SUPPORTED" and additions:
        raise ValueError("only SUPPORTED evidence may fill a missing seed field")
    source_type = _text(raw.get("source_type")).upper()
    if source_type not in set(task.get("required_source_types") or []):
        raise ValueError("candidate evidence supplement source_type is not allowed by task")
    record = {
        "schema_version": SUPPLEMENT_SCHEMA,
        "task_id": task["task_id"],
        "seed_id": task["seed_id"],
        "origin_crux": task["origin_crux"],
        "claim_alignment": alignment,
        "source_identity": source_identity,
        "source_type": source_type,
        "citation": copy.deepcopy(citation),
        "field_additions": additions,
        "alignment_rationale": _text(raw.get("alignment_rationale")),
    }
    record["submission_sha256"] = hashlib.sha256(
        canonical_json(_supplement_payload(record)).encode("utf-8")
    ).hexdigest()
    supplied_hash = str(raw.get("submission_sha256") or "").lower()
    if supplied_hash and supplied_hash != record["submission_sha256"]:
        raise ValueError("candidate evidence supplement submission_sha256 mismatch")
    record["supplement_id"] = _digest(
        "CES", {"task_id": task["task_id"], "submission_sha256": record["submission_sha256"]}
    )
    existing = next(
        (
            item
            for item in state["candidate_evidence_supplements"]
            if isinstance(item, dict) and item.get("supplement_id") == record["supplement_id"]
        ),
        None,
    )
    if existing is not None:
        if existing != record:
            raise ValueError("candidate evidence supplement identity conflict")
        return {"status": "candidate_gap_evidence_replay", "supplement": existing}
    if any(
        isinstance(item, dict)
        and item.get("task_id") == task_id
        and item.get("source_identity") == source_identity
        for item in state["candidate_evidence_supplements"]
    ):
        raise ValueError("candidate gap task cannot reuse a previously attempted publisher")
    attempts = sum(
        1
        for item in state["candidate_evidence_supplements"]
        if isinstance(item, dict) and item.get("task_id") == task_id
    )
    if attempts >= int(task.get("search_budget") or DEFAULT_SEARCH_BUDGET):
        raise ValueError("candidate gap task search budget is exhausted")
    state["candidate_evidence_supplements"].append(record)
    resolution = None
    if alignment in {"SUPPORTED", "CONTRADICTED"}:
        resolution_reason = (
            "claim-aligned independent support recorded"
            if alignment == "SUPPORTED"
            else "claim-aligned independent contradiction recorded"
        )
        resolution = _append_resolution(
            state,
            task,
            "COMPLETED",
            resolution_reason,
            record["supplement_id"],
        )
    elif attempts + 1 >= int(task.get("search_budget") or DEFAULT_SEARCH_BUDGET):
        resolution = _append_resolution(
            state,
            task,
            "SOURCE_EXHAUSTED",
            "search budget exhausted without claim-aligned independent evidence",
            record["supplement_id"],
        )
    opportunity_engine.refresh_candidate_states(state)
    updated = _seed_by_id(state, task["seed_id"])
    return {
        "status": "candidate_gap_evidence_recorded",
        "supplement": copy.deepcopy(record),
        "resolution": copy.deepcopy(resolution),
        "candidate_state": opportunity_engine.candidate_state(state, updated or seed),
        "promotion": opportunity_engine.promotion_assessment(state, updated or seed),
    }


def close_task(
    state: dict[str, Any], task_id: str, status: str, reason: str
) -> dict[str, Any]:
    _state_lists(state)
    task = _task_by_id(state, task_id)
    if task is None:
        raise ValueError("candidate gap task not found")
    status = _text(status).upper()
    if status not in {"SOURCE_EXHAUSTED", "WAITING_EVENT"}:
        raise ValueError("manual gap closure must be SOURCE_EXHAUSTED or WAITING_EVENT")
    if not _text(reason):
        raise ValueError("candidate gap closure reason is required")
    resolution = _append_resolution(state, task, status, reason)
    opportunity_engine.refresh_candidate_states(state)
    return {"status": "candidate_gap_task_closed", "resolution": copy.deepcopy(resolution)}


def gap_blockers(state: dict[str, Any], seed_id: str) -> list[str]:
    blockers = []
    for supplement in state.get("candidate_evidence_supplements", []):
        if not isinstance(supplement, dict) or supplement.get("seed_id") != seed_id:
            continue
        if supplement.get("claim_alignment") == "CONTRADICTED":
            blockers.append("candidate_evidence_contradicted")
    resolution = latest_resolution_for_seed(state, seed_id)
    if resolution and resolution.get("status") == "SOURCE_EXHAUSTED":
        blockers.append("candidate_gap_source_exhausted")
    if resolution and resolution.get("status") == "WAITING_EVENT":
        blockers.append("candidate_gap_waiting_event")
    return list(dict.fromkeys(blockers))


def summary(state: dict[str, Any]) -> dict[str, int]:
    tasks = [item for item in state.get("candidate_gap_tasks", []) if isinstance(item, dict)]
    resolutions = {
        item.get("task_id"): item
        for item in state.get("candidate_gap_resolutions", [])
        if isinstance(item, dict)
    }
    return {
        "candidate_gap_task_count": len(tasks),
        "candidate_gap_open_count": sum(task.get("task_id") not in resolutions for task in tasks),
        "candidate_gap_completed_count": sum(
            item.get("status") == "COMPLETED" for item in resolutions.values()
        ),
        "candidate_gap_source_exhausted_count": sum(
            item.get("status") == "SOURCE_EXHAUSTED" for item in resolutions.values()
        ),
        "candidate_gap_waiting_event_count": sum(
            item.get("status") == "WAITING_EVENT" for item in resolutions.values()
        ),
        "candidate_evidence_supplement_count": len(
            [
                item
                for item in state.get("candidate_evidence_supplements", [])
                if isinstance(item, dict)
            ]
        ),
    }


def validate_histories(state: dict[str, Any]) -> list[str]:
    """Return deterministic validation blockers for v4 transfer preflight."""
    blockers = []
    for field in (
        "candidate_gap_tasks",
        "candidate_evidence_supplements",
        "candidate_gap_resolutions",
    ):
        if not isinstance(state.get(field), list):
            blockers.append(f"{field}_not_list")
    if blockers:
        return blockers
    seed_ids = {
        str(seed.get("seed_id") or "")
        for seed in state.get("opportunity_seeds", [])
        if isinstance(seed, dict)
    }
    task_ids = set()
    tasks_by_id = {}
    for task in state["candidate_gap_tasks"]:
        if not isinstance(task, dict) or task.get("schema_version") != TASK_SCHEMA:
            blockers.append("candidate_gap_task_invalid")
            continue
        task_id = str(task.get("task_id") or "")
        if not re.fullmatch(r"CGT-[A-F0-9]{12}", task_id) or task_id in task_ids:
            blockers.append("candidate_gap_task_identity_invalid")
        task_ids.add(task_id)
        tasks_by_id[task_id] = task
        if task.get("seed_id") not in seed_ids:
            blockers.append("candidate_gap_task_unknown_seed")
        if task.get("status") != TASK_PLANNED:
            blockers.append("candidate_gap_task_status_invalid")
        expected = hashlib.sha256(
            canonical_json(_task_payload(task)).encode("utf-8")
        ).hexdigest()
        if task.get("task_sha256") != expected:
            blockers.append("candidate_gap_task_hash_invalid")
        if task_id != _digest("CGT", {"task_sha256": expected}):
            blockers.append("candidate_gap_task_identity_invalid")
    supplement_ids = set()
    supplements_by_id = {}
    supplement_counts = {}
    for item in state["candidate_evidence_supplements"]:
        if not isinstance(item, dict) or item.get("schema_version") != SUPPLEMENT_SCHEMA:
            blockers.append("candidate_evidence_supplement_invalid")
            continue
        supplement_id = str(item.get("supplement_id") or "")
        if not re.fullmatch(r"CES-[A-F0-9]{12}", supplement_id) or supplement_id in supplement_ids:
            blockers.append("candidate_evidence_supplement_identity_invalid")
        supplement_ids.add(supplement_id)
        supplements_by_id[supplement_id] = item
        task = tasks_by_id.get(item.get("task_id"))
        if not task or item.get("seed_id") not in seed_ids:
            blockers.append("candidate_evidence_supplement_reference_invalid")
        elif (
            item.get("seed_id") != task.get("seed_id")
            or item.get("origin_crux") != task.get("origin_crux")
        ):
            blockers.append("candidate_evidence_supplement_binding_invalid")
        if item.get("claim_alignment") not in ALIGNMENTS:
            blockers.append("candidate_evidence_supplement_alignment_invalid")
        if not _text(item.get("alignment_rationale")):
            blockers.append("candidate_evidence_supplement_rationale_missing")
        citation = item.get("citation")
        source_identity = (
            crux_engine.citation_publisher_identity(citation)
            if isinstance(citation, dict) and crux_engine.valid_citation(citation)
            else ""
        )
        if not source_identity or item.get("source_identity") != source_identity:
            blockers.append("candidate_evidence_supplement_source_invalid")
        if task and item.get("source_type") not in set(task.get("required_source_types") or []):
            blockers.append("candidate_evidence_supplement_source_type_invalid")
        task_id = item.get("task_id")
        supplement_counts[task_id] = supplement_counts.get(task_id, 0) + 1
        if task and supplement_counts[task_id] > int(task.get("search_budget") or 0):
            blockers.append("candidate_gap_search_budget_exceeded")
        expected = hashlib.sha256(
            canonical_json(_supplement_payload(item)).encode("utf-8")
        ).hexdigest()
        if item.get("submission_sha256") != expected:
            blockers.append("candidate_evidence_supplement_hash_invalid")
        if supplement_id != _digest(
            "CES", {"task_id": item.get("task_id"), "submission_sha256": expected}
        ):
            blockers.append("candidate_evidence_supplement_identity_invalid")
    resolution_ids = set()
    resolved_tasks = set()
    for item in state["candidate_gap_resolutions"]:
        if not isinstance(item, dict) or item.get("schema_version") != RESOLUTION_SCHEMA:
            blockers.append("candidate_gap_resolution_invalid")
            continue
        resolution_id = str(item.get("resolution_id") or "")
        if not re.fullmatch(r"CGR-[A-F0-9]{12}", resolution_id) or resolution_id in resolution_ids:
            blockers.append("candidate_gap_resolution_identity_invalid")
        resolution_ids.add(resolution_id)
        task_id = item.get("task_id")
        if task_id not in task_ids or task_id in resolved_tasks:
            blockers.append("candidate_gap_resolution_reference_invalid")
        resolved_tasks.add(task_id)
        if item.get("status") not in RESOLUTION_STATUSES:
            blockers.append("candidate_gap_resolution_status_invalid")
        expected = hashlib.sha256(
            canonical_json(_resolution_payload(item)).encode("utf-8")
        ).hexdigest()
        if item.get("submission_sha256") != expected:
            blockers.append("candidate_gap_resolution_hash_invalid")
        if resolution_id != _digest(
            "CGR", {"task_id": task_id, "submission_sha256": expected}
        ):
            blockers.append("candidate_gap_resolution_identity_invalid")
        last_id = item.get("last_supplement_id")
        last = supplements_by_id.get(last_id) if last_id else None
        if last_id and (not last or last.get("task_id") != task_id):
            blockers.append("candidate_gap_resolution_last_supplement_invalid")
        if item.get("status") == "COMPLETED" and (
            not last or last.get("claim_alignment") not in {"SUPPORTED", "CONTRADICTED"}
        ):
            blockers.append("candidate_gap_completed_without_aligned_evidence")
    resolutions_by_task = {
        item.get("task_id"): item
        for item in state["candidate_gap_resolutions"]
        if isinstance(item, dict)
    }
    for item in state["candidate_evidence_supplements"]:
        if not isinstance(item, dict) or item.get("claim_alignment") not in {
            "SUPPORTED", "CONTRADICTED"
        }:
            continue
        resolution = resolutions_by_task.get(item.get("task_id"))
        if (
            not resolution
            or resolution.get("status") != "COMPLETED"
            or resolution.get("last_supplement_id") != item.get("supplement_id")
        ):
            blockers.append("candidate_gap_aligned_evidence_not_terminal")
    return list(dict.fromkeys(blockers))
