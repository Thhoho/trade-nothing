#!/usr/bin/env python3
"""Confine the retired crux control model to an explicit audit adapter.

Agenda-native frames no longer need to invent a second ontology of cruxes and
logic-graph edges.  The legacy engine still expects at least one crux for
historical report compatibility, so this module derives one inert audit anchor
from the highest-impact Agenda item.  It is never dispatched as research work
and never controls scheduling, stopping, setup readiness, or the report.
"""
from copy import deepcopy
from datetime import date, timedelta
import hashlib


def _text(value):
    return " ".join(str(value or "").split())


def _checkpoint(frame):
    as_of = date.fromisoformat(_text(frame.get("as_of_date")))
    explicit = _text(frame.get("forecast_target_date"))
    if explicit:
        try:
            target = date.fromisoformat(explicit)
        except ValueError:
            target = None
        if target and target > as_of:
            return target.isoformat()
    return (as_of + timedelta(days=90)).isoformat()


def _audit_source(frame):
    workplan = frame.get("research_workplan", {})
    directions = [
        item for item in workplan.get("research_directions", [])
        if isinstance(item, dict)
    ]
    directions.sort(key=lambda item: (
        0 if item.get("load_bearing") is True else 1,
        {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(
            _text(item.get("decision_impact")).upper(), 3
        ),
        _text(item.get("direction_id")),
    ))
    if directions:
        item = directions[0]
        return {
            "source_id": _text(item.get("direction_id")) or "DIRECTION",
            "label": _text(item.get("proposition")) or "Agenda 承重方向",
            "monitor": _text(item.get("discriminating_test")) or "核对 Research Agenda 证据",
            "falsifier": _text(item.get("strongest_alternative"))
            or "若证据不满足判别条件，则保留为未决。",
        }
    questions = [
        item for item in workplan.get("questions", []) if isinstance(item, dict)
    ]
    questions.sort(key=lambda item: (
        0 if item.get("blocks_current_recommendation") is True else 1,
        {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(
            _text(item.get("decision_impact")).upper(), 3
        ),
        _text(item.get("question_id")),
    ))
    item = questions[0]
    return {
        "source_id": _text(item.get("question_id")) or "QUESTION",
        "label": _text(item.get("question")) or _text(frame.get("decision_question")),
        "monitor": _text(item.get("success_condition")) or "核对 Research Agenda 证据",
        "falsifier": "若成功条件未满足，则保留为 OPEN/PARTIAL，不阻止报告交付。",
    }


def adapt(frame):
    """Return an engine-compatible frame plus transparent adapter metadata."""
    copied = deepcopy(frame)
    declared = copied.get("candidate_cruxes")
    if isinstance(declared, list) and declared:
        return copied, {
            "applied": False,
            "mode": "DECLARED_LEGACY_AUDIT",
            "audit_only_crux_ids": [],
        }
    source = _audit_source(copied)
    digest = hashlib.sha256(source["source_id"].encode("utf-8")).hexdigest()[:8].upper()
    crux_id = f"AUDIT-{digest}"
    root_id = "AGENDA-ROOT"
    copied["candidate_cruxes"] = [{
        "id": crux_id,
        "label": f"兼容审计：{source['label']}",
        "logic_role": "THESIS_HINGE",
        "definition": (
            "仅为旧 crux 账本和归档报告提供结构锚；Research Agenda 才拥有调度与停止控制。"
        ),
        "monitor_anchor": source["monitor"],
        "falsifier": source["falsifier"],
        "evidence_plan": [],
        "catalyst_window": {
            "event": "兼容审计检查点",
            "expected_by": _checkpoint(copied),
            "date_status": "REVIEW_CHECKPOINT",
            "basis_claim_id": "",
        },
    }]
    copied["logic_graph"] = {
        "root_id": root_id,
        "nodes": [
            {"id": root_id, "node_type": "QUESTION", "label": "Research Agenda"},
            {"id": crux_id, "node_type": "CRUX", "label": source["label"]},
        ],
        "edges": [{
            "from": crux_id,
            "to": root_id,
            "relation": "REQUIRED_FOR",
        }],
    }
    return copied, {
        "applied": True,
        "mode": "DERIVED_AUDIT_ONLY",
        "source_agenda_id": source["source_id"],
        "audit_only_crux_ids": [crux_id],
        "boundary": (
            "Compatibility audit only; does not schedule research, gate report delivery, "
            "or create candidate authority."
        ),
    }
