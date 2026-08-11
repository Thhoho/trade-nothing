#!/usr/bin/env python3
"""Deterministic Research Agenda for topic-led, iterative deep research.

The agenda is the primary research object.  It records what the topic needs
answered, what each round actually answered, where the answer remains disputed,
and which blind spots should change the next round's priorities.  It does not
promote securities, alter crux signals, or authorize any downstream action.
"""
from copy import deepcopy
from datetime import date
import hashlib

import crux_engine
import research_kernel


SCHEMA_VERSION = "trade-nothing.research-agenda.v3"
QUESTION_STATUSES = {"OPEN", "PARTIAL", "ANSWERED", "DISPUTED"}
SUBMITTED_STATUSES = QUESTION_STATUSES | {"UNANSWERED"}
QUESTION_TYPES = {
    "FACT", "CAUSAL", "MARKET", "CANDIDATE", "PRICING", "RISK",
    "FORWARD_LOOKING", "OTHER",
}
MAX_QUESTION_UPDATES_PER_ROLE = 6
MAX_NEW_QUESTIONS_PER_ROUND = 2
MAX_BLIND_SPOTS_PER_ROUND = 2
MAX_DIRECTION_UPDATES_PER_ROLE = 6
MAX_NEW_DIRECTIONS_PER_ROLE = 1
MAX_EVIDENCE_ITEMS_PER_ROLE = 12
DECISION_IMPACTS = {"HIGH", "MEDIUM", "LOW"}
RESEARCH_COSTS = {"LOW", "MEDIUM", "HIGH"}
NEXT_TEST_AVAILABILITIES = {
    "SEARCH_NOW", "WAIT_FOR_DATE", "WAIT_FOR_EVENT", "NEEDS_USER_DATA", "UNKNOWN",
}
DIRECTION_KINDS = {
    "FACT_ROUTE", "CAUSAL_CLAIM", "MARKET_MECHANISM", "CANDIDATE_PATH",
    "PRICING_CLAIM", "RISK_PATH", "COMPARISON_AXIS", "CRUX", "OTHER",
}
DIRECTION_JUDGMENTS = {"UNRESOLVED", "SUPPORTED", "CHALLENGED"}
DIRECTION_NEXT_MOVES = {"ANSWER", "CONTINUE", "OPEN_NEW_DIRECTION"}
HOST_EVIDENCE_QUESTION_TYPES = {"MARKET", "PRICING", "CANDIDATE"}
HOST_EVIDENCE_DIRECTION_KINDS = {
    "MARKET_MECHANISM", "PRICING_CLAIM", "CANDIDATE_PATH", "COMPARISON_AXIS",
}
EVIDENCE_STANCES = {"SUPPORT", "CHALLENGE", "CONTEXT"}
BASELINE_DISPOSITIONS = {
    "UNREVIEWED", "REVERIFIED", "SUPERSEDED", "OUT_OF_SCOPE", "UNRESOLVED",
}
SUBMITTED_BASELINE_DISPOSITIONS = BASELINE_DISPOSITIONS - {"UNREVIEWED"}
MAX_BASELINE_FINDINGS = 8
MAX_BASELINE_UPDATES_PER_ROLE = 8


def _text(value):
    return " ".join(str(value or "").split())


def _norm(value):
    return _text(value).lower()


def _stable_id(prefix, text):
    digest = hashlib.sha256(_norm(text).encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}-{digest}"


def _workplan(frame):
    raw = frame.get("research_workplan") if isinstance(frame, dict) else None
    return raw if isinstance(raw, dict) else {}


def _enum(value, allowed, default):
    normalized = _text(value).upper()
    return normalized if normalized in allowed else default


def _default_impact(question_type):
    return (
        "HIGH"
        if _text(question_type).upper() in {
            "FACT", "CAUSAL", "MARKET", "CANDIDATE", "PRICING", "RISK"
        }
        else "MEDIUM"
    )


def _question_priority_fields(raw, question_type):
    return {
        "decision_impact": _enum(
            raw.get("decision_impact"),
            DECISION_IMPACTS,
            _default_impact(question_type),
        ),
        "research_cost": _enum(
            raw.get("research_cost"), RESEARCH_COSTS, "MEDIUM"
        ),
        "blocks_current_recommendation": (
            raw.get("blocks_current_recommendation") is True
        ),
    }


def _next_test_availability(value, default="UNKNOWN"):
    return _enum(value, NEXT_TEST_AVAILABILITIES, default)


def validate_frame(frame):
    """Validate an explicit workplan; archived frames may use derived compatibility."""
    workplan = _workplan(frame)
    if not workplan:
        return []
    issues = []
    if not _text(workplan.get("research_objective")):
        issues.append("research_workplan_missing_research_objective")
    questions = workplan.get("questions")
    if not isinstance(questions, list) or not 4 <= len(questions) <= 8:
        return issues + ["research_workplan_requires_4_to_8_questions"]
    crux_ids = {
        _text(item.get("id"))
        for item in frame.get("candidate_cruxes", [])
        if isinstance(item, dict) and _text(item.get("id"))
    }
    seen = set()
    for index, raw in enumerate(questions):
        prefix = f"research_question_{index + 1}"
        if not isinstance(raw, dict):
            issues.append(f"{prefix}_must_be_object")
            continue
        question_id = _text(raw.get("question_id"))
        if not question_id:
            issues.append(f"{prefix}_missing_question_id")
        elif question_id in seen:
            issues.append(f"{prefix}_duplicate_question_id")
        seen.add(question_id)
        for field in ("question", "why_it_matters", "success_condition"):
            if not _text(raw.get(field)):
                issues.append(f"{prefix}_missing_{field}")
        question_type = _text(raw.get("question_type")).upper()
        if question_type not in QUESTION_TYPES:
            issues.append(f"{prefix}_invalid_question_type")
        impact = _text(raw.get("decision_impact")).upper()
        if impact and impact not in DECISION_IMPACTS:
            issues.append(f"{prefix}_invalid_decision_impact")
        cost = _text(raw.get("research_cost")).upper()
        if cost and cost not in RESEARCH_COSTS:
            issues.append(f"{prefix}_invalid_research_cost")
        if (
            "blocks_current_recommendation" in raw
            and not isinstance(raw.get("blocks_current_recommendation"), bool)
        ):
            issues.append(f"{prefix}_invalid_blocks_current_recommendation")
        linked_crux_id = _text(raw.get("linked_crux_id"))
        if linked_crux_id and linked_crux_id not in crux_ids:
            issues.append(f"{prefix}_unknown_linked_crux_id")
        routes = raw.get("initial_search_routes")
        if not isinstance(routes, list) or not 1 <= len(routes) <= 3:
            issues.append(f"{prefix}_requires_1_to_3_initial_search_routes")
        elif any(not _text(route) for route in routes):
            issues.append(f"{prefix}_has_empty_initial_search_route")

    directions = workplan.get("research_directions", [])
    if directions is not None and not isinstance(directions, list):
        issues.append("research_workplan_research_directions_must_be_list")
        directions = []
    elif directions and not 2 <= len(directions) <= 8:
        issues.append("research_workplan_requires_2_to_8_research_directions")
    question_ids = {
        _text(item.get("question_id"))
        for item in questions if isinstance(item, dict)
    }
    baseline_findings = workplan.get("baseline_findings", [])
    if baseline_findings is not None and not isinstance(baseline_findings, list):
        issues.append("research_workplan_baseline_findings_must_be_list")
        baseline_findings = []
    elif len(baseline_findings or []) > MAX_BASELINE_FINDINGS:
        issues.append("research_workplan_baseline_findings_max_8")
    seen_baseline_ids = set()
    for index, raw in enumerate(baseline_findings or []):
        prefix = f"baseline_finding_{index + 1}"
        if not isinstance(raw, dict):
            issues.append(f"{prefix}_must_be_object")
            continue
        finding_id = _text(raw.get("finding_id"))
        if not finding_id:
            issues.append(f"{prefix}_missing_finding_id")
        elif finding_id in seen_baseline_ids:
            issues.append(f"{prefix}_duplicate_finding_id")
        seen_baseline_ids.add(finding_id)
        for field in ("claim", "why_it_matters", "source_url", "source_date"):
            if not _text(raw.get(field)):
                issues.append(f"{prefix}_missing_{field}")
        if _text(raw.get("source_url")) and not crux_engine.is_concrete_url(
            raw.get("source_url")
        ):
            issues.append(f"{prefix}_invalid_source_url")
        try:
            source_date = date.fromisoformat(_text(raw.get("source_date")))
        except ValueError:
            issues.append(f"{prefix}_invalid_source_date")
        else:
            try:
                frame_as_of = date.fromisoformat(_text(frame.get("as_of_date")))
            except ValueError:
                frame_as_of = None
            if frame_as_of and source_date > frame_as_of:
                issues.append(f"{prefix}_source_after_as_of")
        linked = raw.get("linked_question_ids")
        if not isinstance(linked, list) or not linked:
            issues.append(f"{prefix}_requires_linked_question_ids")
        elif any(_text(qid) not in question_ids for qid in linked):
            issues.append(f"{prefix}_unknown_linked_question_id")
        impact = _text(raw.get("decision_impact")).upper()
        if impact and impact not in DECISION_IMPACTS:
            issues.append(f"{prefix}_invalid_decision_impact")
    seen_directions = set()
    for index, raw in enumerate(directions or []):
        prefix = f"research_direction_{index + 1}"
        if not isinstance(raw, dict):
            issues.append(f"{prefix}_must_be_object")
            continue
        direction_id = _text(raw.get("direction_id"))
        if not direction_id:
            issues.append(f"{prefix}_missing_direction_id")
        elif direction_id in seen_directions:
            issues.append(f"{prefix}_duplicate_direction_id")
        seen_directions.add(direction_id)
        for field in ("proposition", "why_it_matters", "discriminating_test"):
            if not _text(raw.get(field)):
                issues.append(f"{prefix}_missing_{field}")
        if _text(raw.get("direction_kind")).upper() not in DIRECTION_KINDS:
            issues.append(f"{prefix}_invalid_direction_kind")
        linked = raw.get("linked_question_ids")
        if not isinstance(linked, list) or not linked:
            issues.append(f"{prefix}_requires_linked_question_ids")
        elif any(_text(qid) not in question_ids for qid in linked):
            issues.append(f"{prefix}_unknown_linked_question_id")
        linked_crux_id = _text(raw.get("linked_crux_id"))
        if linked_crux_id and linked_crux_id not in crux_ids:
            issues.append(f"{prefix}_unknown_linked_crux_id")
        impact = _text(raw.get("decision_impact")).upper()
        if impact and impact not in DECISION_IMPACTS:
            issues.append(f"{prefix}_invalid_decision_impact")
        cost = _text(raw.get("research_cost")).upper()
        if cost and cost not in RESEARCH_COSTS:
            issues.append(f"{prefix}_invalid_research_cost")
        if "load_bearing" in raw and not isinstance(raw.get("load_bearing"), bool):
            issues.append(f"{prefix}_invalid_load_bearing")
    return sorted(set(issues))


def _initial_questions(frame):
    workplan = _workplan(frame)
    explicit = workplan.get("questions") if isinstance(workplan.get("questions"), list) else []
    questions = []
    for index, raw in enumerate(explicit):
        if not isinstance(raw, dict):
            continue
        question = _text(raw.get("question"))
        if not question:
            continue
        question_type = _text(raw.get("question_type")).upper() or "OTHER"
        questions.append({
            "question_id": _text(raw.get("question_id")) or f"RQ{index + 1}",
            "question": question,
            "question_type": question_type,
            "why_it_matters": _text(raw.get("why_it_matters")),
            "success_condition": _text(raw.get("success_condition")),
            "initial_search_routes": [
                _text(item) for item in raw.get("initial_search_routes", []) if _text(item)
            ],
            "linked_crux_id": _text(raw.get("linked_crux_id")),
            **_question_priority_fields(raw, question_type),
        })
    if questions:
        return questions, "EXPLICIT_WORKPLAN"

    # Archived frames remain readable.  New Framer output must emit an explicit
    # workplan, but old runs are projected into an agenda instead of being broken.
    for index, raw in enumerate(frame.get("candidate_cruxes", [])):
        if not isinstance(raw, dict):
            continue
        crux_id = _text(raw.get("id"))
        question = _text(raw.get("definition") or raw.get("label"))
        if not question:
            continue
        questions.append({
            "question_id": f"RQ-{crux_id or index + 1}",
            "question": question,
            "question_type": "OTHER",
            "why_it_matters": _text(raw.get("label")),
            "success_condition": _text(raw.get("monitor_anchor")),
            "initial_search_routes": [
                _text(item.get("search_query"))
                for item in raw.get("evidence_plan", [])
                if isinstance(item, dict) and _text(item.get("search_query"))
            ][:3],
            "linked_crux_id": crux_id,
            "decision_impact": "MEDIUM",
            "research_cost": "MEDIUM",
            "blocks_current_recommendation": False,
        })
    return questions, "DERIVED_COMPAT"


def _direction_kind_for_question(question_type):
    return {
        "FACT": "FACT_ROUTE",
        "CAUSAL": "CAUSAL_CLAIM",
        "MARKET": "MARKET_MECHANISM",
        "CANDIDATE": "CANDIDATE_PATH",
        "PRICING": "PRICING_CLAIM",
        "RISK": "RISK_PATH",
    }.get(_text(question_type).upper(), "OTHER")


def _initial_directions(frame, questions):
    """Build the proposition layer between questions and evidence.

    New frames may provide explicit propositions.  Legacy cruxes are projected
    as load-bearing directions, while uncovered questions receive a lightweight
    inquiry route so every agenda item can participate in the same loop.
    """
    workplan = _workplan(frame)
    explicit = (
        workplan.get("research_directions")
        if isinstance(workplan.get("research_directions"), list) else []
    )
    question_ids = {item.get("question_id") for item in questions}
    directions = []
    for index, raw in enumerate(explicit):
        if not isinstance(raw, dict):
            continue
        proposition = _text(raw.get("proposition"))
        if not proposition:
            continue
        linked = [
            _text(qid) for qid in raw.get("linked_question_ids", [])
            if _text(qid) in question_ids
        ]
        directions.append({
            "direction_id": _text(raw.get("direction_id")) or f"RD{index + 1}",
            "proposition": proposition,
            "direction_kind": _enum(
                raw.get("direction_kind"), DIRECTION_KINDS, "OTHER"
            ),
            "why_it_matters": _text(raw.get("why_it_matters")),
            "discriminating_test": _text(raw.get("discriminating_test")),
            "linked_question_ids": linked,
            "linked_crux_id": _text(raw.get("linked_crux_id")),
            "load_bearing": raw.get("load_bearing") is True,
            "decision_impact": _enum(
                raw.get("decision_impact"), DECISION_IMPACTS, "MEDIUM"
            ),
            "research_cost": _enum(
                raw.get("research_cost"), RESEARCH_COSTS, "MEDIUM"
            ),
            "origin": "FRAMER",
        })

    linked_cruxes = {
        item.get("linked_crux_id") for item in directions
        if item.get("linked_crux_id")
    }
    linked_by_question = {
        qid for item in directions for qid in item.get("linked_question_ids", [])
    }
    for raw in frame.get("candidate_cruxes", []):
        if not isinstance(raw, dict):
            continue
        crux_id = _text(raw.get("id"))
        if not crux_id or crux_id in linked_cruxes:
            continue
        linked = [
            item.get("question_id") for item in questions
            if item.get("linked_crux_id") == crux_id
        ]
        directions.append({
            "direction_id": f"RD-{crux_id}",
            "proposition": _text(raw.get("definition") or raw.get("label")),
            "direction_kind": "CRUX",
            "why_it_matters": _text(raw.get("label")),
            "discriminating_test": _text(
                raw.get("falsifier") or raw.get("monitor_anchor")
            ),
            "linked_question_ids": linked,
            "linked_crux_id": crux_id,
            "load_bearing": True,
            "decision_impact": "HIGH",
            "research_cost": "MEDIUM",
            "origin": "CRUX_COMPAT",
        })
        linked_by_question.update(linked)

    for item in questions:
        question_id = item.get("question_id")
        if question_id in linked_by_question:
            continue
        directions.append({
            "direction_id": f"RD-{question_id}",
            "proposition": f"研究并判别：{_text(item.get('question'))}",
            "direction_kind": _direction_kind_for_question(
                item.get("question_type")
            ),
            "why_it_matters": _text(item.get("why_it_matters")),
            "discriminating_test": _text(item.get("success_condition")),
            "linked_question_ids": [question_id],
            "linked_crux_id": _text(item.get("linked_crux_id")),
            "load_bearing": item.get("blocks_current_recommendation") is True,
            "decision_impact": item.get("decision_impact", "MEDIUM"),
            "research_cost": item.get("research_cost", "MEDIUM"),
            "origin": "QUESTION_ROUTE_COMPAT",
        })
    return directions


def initialize(frame):
    questions, source = _initial_questions(frame if isinstance(frame, dict) else {})
    directions = _initial_directions(
        frame if isinstance(frame, dict) else {}, questions
    )
    objective = _text(_workplan(frame).get("research_objective"))
    if not objective:
        objective = _text(frame.get("decision_question"))
    return {
        "schema_version": SCHEMA_VERSION,
        "research_objective": objective,
        "agenda_source": source,
        "as_of_date": _text(frame.get("as_of_date")),
        "questions": [
            {
                **item,
                "answer_status": "OPEN",
                "current_answer": "",
                "answer_variants": [],
                "answer_resolution": "NOT_RESEARCHED",
                "evidence": [],
                "evidence_boundary": "HYPOTHESIS",
                "strongest_challenge": "",
                "missing_information": "",
                "next_question": "",
                "next_test_availability": "SEARCH_NOW",
                "source_agents": [],
                "first_seen_round": 0,
                "last_seen_round": 0,
            }
            for item in questions
        ],
        "research_directions": [
            {
                **item,
                "research_judgment": "UNRESOLVED",
                "next_move": "CONTINUE",
                "rationale": "",
                "strongest_challenge": "",
                "unresolved_question": "",
                "evidence_ids": [],
                "evidence_boundary": "HYPOTHESIS",
                "judgment_history": [],
                "judgment_resolution": "NOT_RESEARCHED",
                "next_test_availability": "SEARCH_NOW",
                "source_agents": [],
                "first_seen_round": 0,
                "last_seen_round": 0,
            }
            for item in directions
        ],
        "evidence_items": [],
        "evidence_aliases": {},
        "baseline_findings": [
            {
                "finding_id": _text(raw.get("finding_id")),
                "claim": _text(raw.get("claim")),
                "why_it_matters": _text(raw.get("why_it_matters")),
                "source_url": _text(raw.get("source_url")),
                "source_date": _text(raw.get("source_date")),
                "linked_question_ids": list(dict.fromkeys(
                    _text(qid) for qid in raw.get("linked_question_ids", [])
                    if _text(qid)
                )),
                "decision_impact": _enum(
                    raw.get("decision_impact"), DECISION_IMPACTS, "HIGH"
                ),
                # Prior findings are routing leads, never inherited evidence.
                "disposition": "UNREVIEWED",
                "rationale": "",
                "evidence_ids": [],
                "disposition_history": [],
                "last_seen_round": 0,
            }
            for raw in _workplan(frame).get("baseline_findings", [])
            if isinstance(raw, dict) and _text(raw.get("finding_id"))
        ],
        "blind_spots": [],
        "round_summaries": [],
        "capability_boundary": {
            "may_change_next_research_priority": True,
            "may_record_crux_as_load_bearing_direction": True,
            "may_change_crux_signal": False,
            "may_promote_candidate": False,
            "may_authorize_execution": False,
        },
    }


def _accepted_citations(role_payload, as_of_date=""):
    accepted = {}

    def collect(value):
        if isinstance(value, dict):
            normalized, reason = research_kernel.normalize_evidence(
                value, as_of_date
            )
            if reason is None:
                accepted[research_kernel.evidence_identity(normalized)] = normalized
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for collection in ("evidence_items", "crux_evidence", "crux_attacks"):
        if isinstance(role_payload, dict):
            collect(role_payload.get(collection, []))
    return accepted


def _direction_by_id(agenda):
    return {
        item.get("direction_id"): item
        for item in agenda.get("research_directions", [])
        if isinstance(item, dict) and item.get("direction_id")
    }


def _evidence_by_id(agenda):
    return {
        item.get("evidence_id"): item
        for item in agenda.get("evidence_items", [])
        if isinstance(item, dict) and item.get("evidence_id")
    }


def _baseline_by_id(agenda):
    return {
        item.get("finding_id"): item
        for item in agenda.get("baseline_findings", [])
        if isinstance(item, dict) and item.get("finding_id")
    }


def _ingest_evidence_items(agenda, round_num, role, payload, audit):
    """Accept role-local evidence independently of crux payloads."""
    items = payload.get("evidence_items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        audit["rejected_evidence_items"].append({
            "role": role, "reason": "EVIDENCE_ITEMS_NOT_LIST",
        })
        return {}
    known_ids = set(_evidence_by_id(agenda))
    valid_question_ids = set(_question_by_id(agenda))
    valid_direction_ids = set(_direction_by_id(agenda))
    known_by_identity = {
        research_kernel.evidence_identity(item): item
        for item in agenda.get("evidence_items", [])
        if research_kernel.evidence_identity(item)
    }
    known_by_base_identity = {}
    for item in agenda.get("evidence_items", []):
        if not isinstance(item, dict):
            continue
        base_identity = crux_engine.citation_identity(item)
        if base_identity:
            known_by_base_identity.setdefault(base_identity, []).append(item)
    accepted = {}
    seen = set()
    for raw in items[:MAX_EVIDENCE_ITEMS_PER_ROLE]:
        if not isinstance(raw, dict):
            audit["rejected_evidence_items"].append({
                "role": role, "reason": "NOT_OBJECT",
            })
            continue
        evidence_id = _text(raw.get("evidence_id"))
        if not evidence_id or evidence_id in known_ids or evidence_id in seen:
            audit["rejected_evidence_items"].append({
                "role": role, "evidence_id": evidence_id,
                "reason": "MISSING_OR_DUPLICATE_EVIDENCE_ID",
            })
            continue
        normalized, reason = research_kernel.normalize_evidence(
            raw, agenda.get("as_of_date", "")
        )
        if reason:
            audit["rejected_evidence_items"].append({
                "role": role, "evidence_id": evidence_id,
                "reason": reason,
            })
            continue
        question_ids = [
            _text(qid) for qid in raw.get("question_ids", [])
            if _text(qid) in valid_question_ids
        ]
        direction_ids = [
            _text(did) for did in raw.get("direction_ids", [])
            if _text(did) in valid_direction_ids
        ]
        if not question_ids and not direction_ids:
            audit["rejected_evidence_items"].append({
                "role": role, "evidence_id": evidence_id,
                "reason": "EVIDENCE_REQUIRES_VALID_QUESTION_OR_DIRECTION",
            })
            continue
        identity = research_kernel.evidence_identity(normalized)
        base_identity = crux_engine.citation_identity(normalized)
        base_matches = known_by_base_identity.get(base_identity, [])
        existing = known_by_identity.get(identity)
        if existing is None and len(base_matches) == 1:
            # Backward-compatible repair for roles that copied an already
            # supplied host fact instead of referencing its canonical ID.
            existing = base_matches[0]
        if existing is not None:
            for field, values in (
                ("question_ids", question_ids), ("direction_ids", direction_ids)
            ):
                current = existing.setdefault(field, [])
                for value in values:
                    if value not in current:
                        current.append(value)
            roles = existing.setdefault("roles", [existing.get("role")])
            if role not in roles:
                roles.append(role)
            accepted[evidence_id] = existing
            agenda.setdefault("evidence_aliases", {})[evidence_id] = (
                existing.get("evidence_id")
            )
            seen.add(evidence_id)
            audit["duplicate_evidence_aliases"].append({
                "role": role,
                "submitted_evidence_id": evidence_id,
                "canonical_evidence_id": existing.get("evidence_id"),
                "identity": identity,
            })
            continue
        item = {
            "evidence_id": evidence_id,
            "question_ids": question_ids,
            "direction_ids": direction_ids,
            "stance": _enum(raw.get("stance"), EVIDENCE_STANCES, "CONTEXT"),
            "claim": normalized.get("claim"),
            "number": normalized.get("number"),
            "source": normalized.get("source"),
            "url": normalized.get("url"),
            "date": normalized.get("date"),
            "source_tier": normalized.get("source_tier"),
            "publisher_identity": normalized.get("publisher_identity"),
            "round": round_num,
            "role": role,
            "roles": [role],
        }
        agenda.setdefault("evidence_items", []).append(item)
        known_by_identity[identity] = item
        known_by_base_identity.setdefault(base_identity, []).append(item)
        accepted[evidence_id] = item
        seen.add(evidence_id)
        audit["accepted_evidence_ids"].append(evidence_id)
    return accepted


def _evidence_boundary(citations, answer_is_inference=False):
    return research_kernel.evidence_boundary(
        citations, is_inference=answer_is_inference
    )


def _host_evidence_for_question(agenda, evidence_id, question):
    item = _evidence_by_id(agenda).get(evidence_id)
    if not isinstance(item, dict) or item.get("origin") != "HOST_MARKET_SNAPSHOT":
        return None
    if _text(question.get("question_type")).upper() not in HOST_EVIDENCE_QUESTION_TYPES:
        return None
    return item


def _host_evidence_for_direction(agenda, evidence_id, direction):
    item = _evidence_by_id(agenda).get(evidence_id)
    if not isinstance(item, dict) or item.get("origin") != "HOST_MARKET_SNAPSHOT":
        return None
    if _text(direction.get("direction_kind")).upper() not in HOST_EVIDENCE_DIRECTION_KINDS:
        return None
    return item


def _question_by_id(agenda):
    return {
        item.get("question_id"): item
        for item in agenda.get("questions", [])
        if isinstance(item, dict) and item.get("question_id")
    }


def _ingest_role_updates(
    agenda, round_num, role, payload, audit, accepted_evidence=None
):
    by_id = _question_by_id(agenda)
    allowed_citations = _accepted_citations(
        payload, agenda.get("as_of_date", "")
    )
    accepted_evidence = accepted_evidence or {}
    updates = payload.get("question_updates", []) if isinstance(payload, dict) else []
    if not isinstance(updates, list):
        updates = []
    for raw in updates[:MAX_QUESTION_UPDATES_PER_ROLE]:
        if not isinstance(raw, dict):
            audit["rejected_updates"].append({"role": role, "reason": "NOT_OBJECT"})
            continue
        question_id = _text(raw.get("question_id"))
        question = by_id.get(question_id)
        status = _text(raw.get("answer_status")).upper()
        answer = _text(raw.get("answer"))
        if not question or status not in SUBMITTED_STATUSES:
            audit["rejected_updates"].append({
                "role": role, "question_id": question_id,
                "reason": "UNKNOWN_QUESTION_OR_INVALID_STATUS",
            })
            continue
        if status in {"ANSWERED", "PARTIAL", "DISPUTED"} and not answer:
            audit["rejected_updates"].append({
                "role": role, "question_id": question_id,
                "reason": "ANSWER_TEXT_REQUIRED_FOR_SUBMITTED_STATUS",
            })
            continue
        evidence_ids = raw.get("evidence_ids", [])
        if not isinstance(evidence_ids, list):
            evidence_ids = []
        evidence = []
        for evidence_id in evidence_ids:
            item = accepted_evidence.get(evidence_id)
            if not (
                isinstance(item, dict)
                and question_id in item.get("question_ids", [])
            ):
                item = _host_evidence_for_question(
                    agenda, _text(evidence_id), question
                )
            if isinstance(item, dict):
                evidence.append(deepcopy(item))
        evidence = research_kernel.unique_evidence(evidence)
        submitted_evidence = raw.get("evidence", [])
        if not isinstance(submitted_evidence, list):
            submitted_evidence = []
        for citation in submitted_evidence:
            if not isinstance(citation, dict) or not crux_engine.valid_citation(citation):
                continue
            key = crux_engine.citation_identity(citation)
            if key in allowed_citations:
                accepted = deepcopy(allowed_citations[key])
                if not any(
                    crux_engine.citation_identity(item) == key
                    for item in evidence if crux_engine.valid_citation(item)
                ):
                    evidence.append(accepted)
        current_boundary = None
        if answer:
            current_boundary = _evidence_boundary(
                evidence, raw.get("answer_is_inference") is True
            )
            normalized_status = research_kernel.normalize_answer_status(
                status, current_boundary, answer
            )
            variant = {
                "round": round_num,
                "role": role,
                "answer": answer,
                "submitted_answer_status": status,
                "answer_status": normalized_status,
                "evidence_boundary": current_boundary,
                "evidence": evidence,
                "strongest_challenge": _text(raw.get("strongest_challenge")),
                "missing_information": _text(raw.get("missing_information")),
                "next_question": _text(raw.get("next_question")),
                "next_test_availability": _next_test_availability(
                    raw.get("next_test_availability")
                ),
            }
            if not any(
                _norm(item.get("answer")) == _norm(answer)
                and item.get("round") == round_num
                and item.get("role") == role
                for item in question.get("answer_variants", [])
                if isinstance(item, dict)
            ):
                question.setdefault("answer_variants", []).append(variant)
        existing = {
            crux_engine.citation_identity(item)
            for item in question.get("evidence", [])
            if isinstance(item, dict) and crux_engine.valid_citation(item)
        }
        for citation in evidence:
            key = crux_engine.citation_identity(citation)
            if key not in existing:
                question.setdefault("evidence", []).append(citation)
                existing.add(key)
        question["last_seen_round"] = round_num
        if role not in question.setdefault("source_agents", []):
            question["source_agents"].append(role)
        audit["accepted_updates"].append({
            "role": role,
            "question_id": question_id,
            "submitted_answer_status": status,
            "answer_status": normalized_status if answer else "OPEN",
            "evidence_boundary": current_boundary or "HYPOTHESIS",
        })


def _ingest_baseline_updates(
    agenda, round_num, role, payload, audit, accepted_evidence=None
):
    """Dispose prior-run leads using only evidence observed in this role/round."""
    updates = (
        payload.get("baseline_finding_updates", [])
        if isinstance(payload, dict) else []
    )
    if not isinstance(updates, list):
        audit["rejected_baseline_updates"].append({
            "role": role, "reason": "BASELINE_UPDATES_NOT_LIST",
        })
        return
    by_id = _baseline_by_id(agenda)
    accepted_evidence = accepted_evidence or {}
    for raw in updates[:MAX_BASELINE_UPDATES_PER_ROLE]:
        if not isinstance(raw, dict):
            audit["rejected_baseline_updates"].append({
                "role": role, "reason": "NOT_OBJECT",
            })
            continue
        finding_id = _text(raw.get("finding_id"))
        finding = by_id.get(finding_id)
        disposition = _text(raw.get("disposition")).upper()
        rationale = _text(raw.get("rationale"))
        if (
            not finding
            or disposition not in SUBMITTED_BASELINE_DISPOSITIONS
            or not rationale
        ):
            audit["rejected_baseline_updates"].append({
                "role": role, "finding_id": finding_id,
                "reason": "UNKNOWN_FINDING_OR_INVALID_DISPOSITION",
            })
            continue
        if finding.get("disposition", "UNREVIEWED") != "UNREVIEWED":
            audit["rejected_baseline_updates"].append({
                "role": role, "finding_id": finding_id,
                "reason": "BASELINE_FINDING_ALREADY_DISPOSED",
            })
            continue
        submitted_ids = raw.get("evidence_ids", [])
        if not isinstance(submitted_ids, list):
            submitted_ids = []
        linked_questions = set(finding.get("linked_question_ids", []))
        evidence_ids = []
        for submitted_id in submitted_ids:
            evidence = accepted_evidence.get(submitted_id)
            if not isinstance(evidence, dict):
                continue
            if not linked_questions.intersection(evidence.get("question_ids", [])):
                continue
            canonical_id = evidence.get("evidence_id")
            if canonical_id and canonical_id not in evidence_ids:
                evidence_ids.append(canonical_id)
        if disposition in {"REVERIFIED", "SUPERSEDED"} and not evidence_ids:
            audit["rejected_baseline_updates"].append({
                "role": role, "finding_id": finding_id,
                "reason": "DISPOSITION_REQUIRES_CURRENT_LINKED_EVIDENCE",
            })
            continue
        record = {
            "round": int(round_num),
            "role": role,
            "disposition": disposition,
            "rationale": rationale,
            "evidence_ids": evidence_ids,
        }
        if record not in finding.setdefault("disposition_history", []):
            finding["disposition_history"].append(record)
        finding["last_seen_round"] = int(round_num)
        audit["accepted_baseline_updates"].append({
            "role": role,
            "finding_id": finding_id,
            "disposition": disposition,
            "evidence_ids": evidence_ids,
        })


def _reconcile_baseline_updates(agenda, round_num, audit):
    for finding in agenda.get("baseline_findings", []):
        if not isinstance(finding, dict):
            continue
        records = [
            item for item in finding.get("disposition_history", [])
            if isinstance(item, dict) and int(item.get("round", 0) or 0) == round_num
        ]
        if not records:
            continue
        evidence_statuses = {
            item.get("disposition") for item in records
            if item.get("disposition") in {"REVERIFIED", "SUPERSEDED"}
        }
        if len(evidence_statuses) > 1:
            disposition = "UNRESOLVED"
            rationale = "Current-round roles conflict on whether the prior finding still holds."
            evidence_ids = sorted({
                evidence_id for item in records
                for evidence_id in item.get("evidence_ids", [])
            })
        else:
            rank = {
                "SUPERSEDED": 0,
                "REVERIFIED": 1,
                "OUT_OF_SCOPE": 2,
                "UNRESOLVED": 3,
            }
            selected = sorted(
                records,
                key=lambda item: (
                    rank.get(item.get("disposition"), 9),
                    -len(item.get("evidence_ids", [])),
                    item.get("role", ""),
                ),
            )[0]
            disposition = selected.get("disposition", "UNRESOLVED")
            rationale = selected.get("rationale", "")
            evidence_ids = list(selected.get("evidence_ids", []))
        finding.update({
            "disposition": disposition,
            "rationale": rationale,
            "evidence_ids": evidence_ids,
        })
        audit["baseline_reconciliations"].append({
            "finding_id": finding.get("finding_id"),
            "disposition": disposition,
            "evidence_ids": evidence_ids,
        })


def _reconcile_question_updates(agenda, round_num, audit):
    for question in agenda.get("questions", []):
        if not isinstance(question, dict):
            continue
        variants = [
            item for item in question.get("answer_variants", [])
            if isinstance(item, dict)
        ]
        resolution = research_kernel.reconcile_answer_variants(variants)
        if not resolution:
            continue
        question.update({
            "answer_status": resolution["answer_status"],
            "current_answer": resolution["current_answer"],
            "evidence_boundary": resolution["evidence_boundary"],
            "strongest_challenge": resolution["strongest_challenge"],
            "missing_information": resolution["missing_information"],
            "next_question": resolution["next_question"],
            "next_test_availability": resolution.get(
                "next_test_availability", "UNKNOWN"
            ),
            "answer_resolution": resolution["resolution"],
        })
        audit["answer_reconciliations"].append({
            "question_id": question.get("question_id"),
            "answer_status": resolution["answer_status"],
            "resolution": resolution["resolution"],
            "selected_role": resolution["selected_role"],
        })


def _ingest_new_directions(agenda, round_num, role, payload, audit):
    items = (
        payload.get("new_research_directions", [])
        if isinstance(payload, dict) else []
    )
    if not isinstance(items, list):
        return
    by_id = _direction_by_id(agenda)
    known_text = {
        _norm(item.get("proposition")) for item in by_id.values()
    }
    valid_question_ids = set(_question_by_id(agenda))
    for raw in items[:MAX_NEW_DIRECTIONS_PER_ROLE]:
        if not isinstance(raw, dict):
            continue
        proposition = _text(raw.get("proposition"))
        why = _text(raw.get("why_it_matters"))
        test = _text(raw.get("discriminating_test"))
        origin_reason = _text(raw.get("origin_reason"))
        linked_question_ids = [
            _text(qid) for qid in raw.get("linked_question_ids", [])
            if _text(qid) in valid_question_ids
        ]
        parent_direction_ids = [
            _text(did) for did in raw.get("parent_direction_ids", [])
            if _text(did) in by_id
        ]
        if (
            not proposition or not why or not test or not origin_reason
            or not linked_question_ids or not parent_direction_ids
            or _norm(proposition) in known_text
        ):
            audit["rejected_new_directions"].append({
                "role": role,
                "direction_id": _text(raw.get("direction_id")),
                "reason": "MISSING_PROPOSITION_LINEAGE_OR_LINKED_QUESTION",
            })
            continue
        direction_id = (
            _text(raw.get("direction_id")) or _stable_id("RD", proposition)
        )
        if direction_id in by_id:
            continue
        item = {
            "direction_id": direction_id,
            "proposition": proposition,
            "direction_kind": _enum(
                raw.get("direction_kind"), DIRECTION_KINDS, "OTHER"
            ),
            "why_it_matters": why,
            "discriminating_test": test,
            "linked_question_ids": linked_question_ids,
            "linked_crux_id": _text(raw.get("linked_crux_id")),
            "load_bearing": raw.get("load_bearing") is True,
            "decision_impact": _enum(
                raw.get("decision_impact"), DECISION_IMPACTS, "MEDIUM"
            ),
            "research_cost": _enum(
                raw.get("research_cost"), RESEARCH_COSTS, "LOW"
            ),
            "origin": "ROUND_DISCOVERY",
            "origin_reason": origin_reason,
            "parent_direction_ids": parent_direction_ids,
            "research_judgment": "UNRESOLVED",
            "next_move": "CONTINUE",
            "rationale": "",
            "strongest_challenge": "",
            "unresolved_question": "",
            "evidence_ids": [],
            "evidence_boundary": "HYPOTHESIS",
            "judgment_history": [],
            "judgment_resolution": "NOT_RESEARCHED",
            "next_test_availability": _next_test_availability(
                raw.get("next_test_availability")
            ),
            "source_agents": [role],
            "first_seen_round": round_num,
            "last_seen_round": round_num,
        }
        agenda.setdefault("research_directions", []).append(item)
        by_id[direction_id] = item
        known_text.add(_norm(proposition))
        audit["new_direction_ids"].append(direction_id)


def _ingest_direction_updates(
    agenda, round_num, role, payload, audit, accepted_evidence=None
):
    items = payload.get("direction_updates", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        return
    by_id = _direction_by_id(agenda)
    accepted_evidence = accepted_evidence or {}
    for raw in items[:MAX_DIRECTION_UPDATES_PER_ROLE]:
        if not isinstance(raw, dict):
            audit["rejected_direction_updates"].append({
                "role": role, "reason": "NOT_OBJECT",
            })
            continue
        direction_id = _text(raw.get("direction_id"))
        direction = by_id.get(direction_id)
        judgment = _text(raw.get("research_judgment")).upper()
        next_move = _text(raw.get("next_move")).upper()
        rationale = _text(raw.get("rationale"))
        if (
            not direction or judgment not in DIRECTION_JUDGMENTS
            or next_move not in DIRECTION_NEXT_MOVES or not rationale
        ):
            audit["rejected_direction_updates"].append({
                "role": role, "direction_id": direction_id,
                "reason": "UNKNOWN_DIRECTION_OR_INVALID_RESEARCH_JUDGMENT",
            })
            continue
        submitted_ids = raw.get("evidence_ids", [])
        if not isinstance(submitted_ids, list):
            submitted_ids = []
        evidence_ids = []
        for submitted_id in submitted_ids:
            item = accepted_evidence.get(submitted_id)
            if not (
                isinstance(item, dict)
                and direction_id in item.get("direction_ids", [])
            ):
                item = _host_evidence_for_direction(
                    agenda, _text(submitted_id), direction
                )
            canonical_id = item.get("evidence_id") if isinstance(item, dict) else ""
            if canonical_id and canonical_id not in evidence_ids:
                evidence_ids.append(canonical_id)
        evidence_ids = list(dict.fromkeys(evidence_ids))
        evidence_by_id = _evidence_by_id(agenda)
        evidence = [
            evidence_by_id[evidence_id] for evidence_id in evidence_ids
            if evidence_id in evidence_by_id
        ]
        evidence_boundary = _evidence_boundary(
            evidence, raw.get("judgment_is_inference") is True
        )
        record = {
            "round": round_num,
            "role": role,
            "research_judgment": judgment,
            "next_move": next_move,
            "rationale": rationale,
            "evidence_ids": evidence_ids,
            "evidence_boundary": evidence_boundary,
            "strongest_challenge": _text(raw.get("strongest_challenge")),
            "unresolved_question": _text(raw.get("unresolved_question")),
            "next_test_availability": _next_test_availability(
                raw.get("next_test_availability")
            ),
        }
        direction["last_seen_round"] = round_num
        direction.setdefault("judgment_history", []).append(record)
        if role not in direction.setdefault("source_agents", []):
            direction["source_agents"].append(role)
        known_evidence = set(direction.setdefault("evidence_ids", []))
        for evidence_id in evidence_ids:
            if evidence_id not in known_evidence:
                direction["evidence_ids"].append(evidence_id)
                known_evidence.add(evidence_id)
        audit["accepted_direction_updates"].append({
            "role": role,
            "direction_id": direction_id,
            "research_judgment": judgment,
            "next_move": next_move,
        })


def _reconcile_direction_updates(agenda, round_num, audit):
    for direction in agenda.get("research_directions", []):
        if not isinstance(direction, dict):
            continue
        records = [
            item for item in direction.get("judgment_history", [])
            if isinstance(item, dict)
        ]
        resolution = research_kernel.reconcile_direction_records(records)
        if not resolution:
            continue
        direction.update({
            "research_judgment": resolution["research_judgment"],
            "next_move": resolution["next_move"],
            "rationale": resolution["rationale"],
            "evidence_boundary": resolution["evidence_boundary"],
            "strongest_challenge": resolution["strongest_challenge"],
            "unresolved_question": resolution["unresolved_question"],
            "evidence_ids": resolution["evidence_ids"],
            "judgment_resolution": resolution["resolution"],
            "next_test_availability": resolution.get(
                "next_test_availability", "UNKNOWN"
            ),
        })
        audit["direction_reconciliations"].append({
            "direction_id": direction.get("direction_id"),
            "research_judgment": resolution["research_judgment"],
            "next_move": resolution["next_move"],
            "resolution": resolution["resolution"],
        })


def _discovery_priority(raw, role):
    impact_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    cost_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    return (
        0 if raw.get("blocks_current_recommendation") is True else 1,
        impact_rank.get(_text(raw.get("decision_impact")).upper(), 1),
        cost_rank.get(_text(raw.get("research_cost")).upper(), 1),
        _norm(raw.get("question") or raw.get("statement")),
        role,
    )


def _ingest_new_questions(agenda, round_num, submissions, audit):
    by_id = _question_by_id(agenda)
    known_text = {_norm(item.get("question")) for item in by_id.values()}
    active_parent_ids = {
        _text(item.get("parent_question_id"))
        for item in by_id.values()
        if _text(item.get("parent_question_id"))
        and item.get("answer_status") != "ANSWERED"
    }
    candidates = []
    for role, payload in submissions:
        items = (
            payload.get("new_research_questions", [])
            if isinstance(payload, dict) else []
        )
        if not isinstance(items, list):
            continue
        for raw in items:
            if isinstance(raw, dict):
                candidates.append((_discovery_priority(raw, role), role, raw))
    candidates.sort(key=lambda row: row[0])
    accepted = 0
    for _, role, raw in candidates:
        if accepted >= MAX_NEW_QUESTIONS_PER_ROUND:
            audit["rejected_new_questions"].append({
                "role": role,
                "reason": "ROUND_DISCOVERY_BUDGET_EXHAUSTED",
                "question": _text(raw.get("question")),
            })
            continue
        if not isinstance(raw, dict):
            continue
        question_text = _text(raw.get("question"))
        why = _text(raw.get("why_it_matters"))
        success_condition = _text(raw.get("success_condition"))
        decision_change = _text(raw.get("decision_change"))
        parent_question_id = _text(raw.get("parent_question_id"))
        search_routes = [
            _text(route) for route in raw.get("search_routes", []) if _text(route)
        ][:3]
        if (
            not question_text or not why or not success_condition
            or not decision_change or not search_routes
            or parent_question_id not in by_id
        ):
            audit["rejected_new_questions"].append({
                "role": role,
                "reason": "MISSING_PARENT_TEST_OR_DECISION_CHANGE",
                "question": question_text,
            })
            continue
        if _norm(question_text) in known_text:
            audit["rejected_new_questions"].append({
                "role": role, "reason": "DUPLICATE_QUESTION", "question": question_text,
            })
            continue
        if parent_question_id in active_parent_ids:
            audit["rejected_new_questions"].append({
                "role": role,
                "reason": "ACTIVE_DERIVED_QUESTION_EXISTS",
                "question": question_text,
                "parent_question_id": parent_question_id,
            })
            continue
        question_id = _stable_id("RQ", question_text)
        if question_id in by_id:
            continue
        question_type = _text(raw.get("question_type")).upper() or "OTHER"
        parent = by_id[parent_question_id]
        priority = _question_priority_fields(raw, question_type)
        priority["blocks_current_recommendation"] = bool(
            priority["blocks_current_recommendation"]
            and parent.get("blocks_current_recommendation") is True
        )
        item = {
            "question_id": question_id,
            "question": question_text,
            "question_type": question_type,
            "why_it_matters": why,
            "success_condition": success_condition,
            "initial_search_routes": search_routes,
            "linked_crux_id": _text(raw.get("linked_crux_id")),
            "introduced_by_blind_spot": _text(raw.get("introduced_by_blind_spot")),
            "parent_question_id": parent_question_id,
            "decision_change": decision_change,
            "question_origin": "ROUND_DISCOVERY",
            **priority,
            "answer_status": "OPEN",
            "current_answer": "",
            "answer_variants": [],
            "answer_resolution": "NOT_RESEARCHED",
            "evidence": [],
            "evidence_boundary": "HYPOTHESIS",
            "strongest_challenge": "",
            "missing_information": "",
            "next_question": "",
            "next_test_availability": _next_test_availability(
                raw.get("next_test_availability")
            ),
            "source_agents": [role],
            "first_seen_round": round_num,
            "last_seen_round": round_num,
        }
        agenda.setdefault("questions", []).append(item)
        by_id[question_id] = item
        known_text.add(_norm(question_text))
        active_parent_ids.add(parent_question_id)
        audit["new_question_ids"].append(question_id)
        accepted += 1


def _ingest_blind_spots(agenda, round_num, submissions, audit):
    known = {
        _norm(item.get("statement"))
        for item in agenda.get("blind_spots", []) if isinstance(item, dict)
    }
    questions = _question_by_id(agenda)
    valid_question_ids = set(questions)
    candidates = []
    for role, payload in submissions:
        items = payload.get("new_blind_spots", []) if isinstance(payload, dict) else []
        if not isinstance(items, list):
            continue
        for raw in items:
            if isinstance(raw, dict):
                candidates.append((_discovery_priority(raw, role), role, raw))
    candidates.sort(key=lambda row: row[0])
    accepted = 0
    for _, role, raw in candidates:
        if accepted >= MAX_BLIND_SPOTS_PER_ROUND:
            audit["rejected_new_blind_spots"].append({
                "role": role,
                "reason": "ROUND_DISCOVERY_BUDGET_EXHAUSTED",
                "statement": _text(raw.get("statement")),
            })
            continue
        statement = _text(raw.get("statement"))
        impact = _text(raw.get("potential_impact"))
        why_missed = _text(raw.get("why_missed"))
        cheapest_test = _text(raw.get("cheapest_test"))
        linked_question_ids = [
            _text(qid) for qid in raw.get("linked_question_ids", [])
            if _text(qid) in valid_question_ids
        ]
        if (
            not statement or not impact or not why_missed or not cheapest_test
            or not linked_question_ids
        ):
            audit["rejected_new_blind_spots"].append({
                "role": role,
                "reason": "MISSING_LINEAGE_IMPACT_OR_CHEAP_TEST",
                "statement": statement,
            })
            continue
        if _norm(statement) in known:
            audit["rejected_new_blind_spots"].append({
                "role": role, "reason": "DUPLICATE_BLIND_SPOT", "statement": statement,
            })
            continue
        blind_id = _stable_id("BS", statement)
        decision_impact = _enum(
            raw.get("decision_impact"), DECISION_IMPACTS, "MEDIUM"
        )
        research_cost = _enum(
            raw.get("research_cost"), RESEARCH_COSTS, "LOW"
        )
        inherited_block = any(
            questions[qid].get("blocks_current_recommendation") is True
            for qid in linked_question_ids
        )
        item = {
            "blind_spot_id": blind_id,
            "statement": statement,
            "why_missed": why_missed,
            "potential_impact": impact,
            "linked_question_ids": linked_question_ids,
            "cheapest_test": cheapest_test,
            "next_test_availability": _next_test_availability(
                raw.get("next_test_availability")
            ),
            "decision_impact": decision_impact,
            "research_cost": research_cost,
            "blocks_current_recommendation": (
                raw.get("blocks_current_recommendation") is True
                and inherited_block
                and decision_impact == "HIGH"
                and research_cost == "LOW"
            ),
            "research_status": "OPEN",
            "first_seen_round": round_num,
            "source_agents": [role],
        }
        agenda.setdefault("blind_spots", []).append(item)
        known.add(_norm(statement))
        audit["new_blind_spot_ids"].append(blind_id)
        accepted += 1


def harvest_round(state, round_num, detective=None, inquisitor=None):
    agenda = state.get("research_agenda")
    if not isinstance(agenda, dict):
        agenda = initialize({
            "decision_question": state.get("decision_question"),
            "as_of_date": state.get("frame_contract", {}).get("as_of_date", ""),
            "candidate_cruxes": [
                {
                    "id": cid,
                    "label": item.get("label"),
                    "definition": item.get("definition"),
                    "monitor_anchor": item.get("monitor_anchor"),
                    "evidence_plan": item.get("evidence_plan", []),
                }
                for cid, item in state.get("cruxes", {}).items()
                if isinstance(item, dict)
            ],
        })
        state["research_agenda"] = agenda
    audit = {
        "round": round_num,
        "accepted_updates": [],
        "rejected_updates": [],
        "accepted_evidence_ids": [],
        "duplicate_evidence_aliases": [],
        "rejected_evidence_items": [],
        "accepted_direction_updates": [],
        "rejected_direction_updates": [],
        "accepted_baseline_updates": [],
        "rejected_baseline_updates": [],
        "answer_reconciliations": [],
        "direction_reconciliations": [],
        "baseline_reconciliations": [],
        "new_direction_ids": [],
        "rejected_new_directions": [],
        "new_question_ids": [],
        "new_blind_spot_ids": [],
        "rejected_new_questions": [],
        "rejected_new_blind_spots": [],
    }
    submissions = (("detective", detective or {}), ("inquisitor", inquisitor or {}))
    for role, payload in submissions:
        accepted_evidence = _ingest_evidence_items(
            agenda, round_num, role, payload, audit
        )
        _ingest_new_directions(agenda, round_num, role, payload, audit)
        _ingest_role_updates(
            agenda, round_num, role, payload, audit, accepted_evidence
        )
        _ingest_baseline_updates(
            agenda, round_num, role, payload, audit, accepted_evidence
        )
        _ingest_direction_updates(
            agenda, round_num, role, payload, audit, accepted_evidence
        )
    _ingest_blind_spots(agenda, round_num, submissions, audit)
    _ingest_new_questions(agenda, round_num, submissions, audit)
    _reconcile_question_updates(agenda, round_num, audit)
    _reconcile_direction_updates(agenda, round_num, audit)
    _reconcile_baseline_updates(agenda, round_num, audit)
    counts = summary(state)
    audit["counts"] = counts
    agenda.setdefault("round_summaries", []).append(deepcopy(audit))
    return audit


def _open_blind_spot_ids(agenda):
    questions = _question_by_id(agenda)
    promoted_origins = {
        _norm(item.get("introduced_by_blind_spot"))
        for item in questions.values()
        if _norm(item.get("introduced_by_blind_spot"))
    }
    open_ids = set()
    for item in agenda.get("blind_spots", []):
        if not isinstance(item, dict):
            continue
        # Once a blind spot has been promoted into a real Agenda question it
        # remains visible for audit, but it must not count as a second research
        # debt item.
        if _norm(item.get("statement")) in promoted_origins:
            continue
        linked = [
            questions.get(qid) for qid in item.get("linked_question_ids", [])
            if questions.get(qid)
        ]
        resolved = bool(linked) and all(
            question.get("answer_status") == "ANSWERED" for question in linked
        )
        if not resolved and item.get("research_status", "OPEN") != "RESOLVED":
            open_ids.add(item.get("blind_spot_id"))
    return open_ids


def _open_direction_ids(agenda):
    return {
        item.get("direction_id")
        for item in agenda.get("research_directions", [])
        if isinstance(item, dict)
        and item.get("direction_id")
        and item.get("next_move", "CONTINUE") != "ANSWER"
    }


def focus_directions(state, question_ids=None, limit=5):
    """Return the proposition directions with the highest research value."""
    agenda = state.get("research_agenda", {})
    selected_questions = set(question_ids or [])
    impact_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    cost_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    judgment_rank = {"CHALLENGED": 0, "UNRESOLVED": 1, "SUPPORTED": 2}
    active = []
    for item in projected_directions(state):
        if (
            not isinstance(item, dict)
            or item.get("next_move", "CONTINUE") == "ANSWER"
        ):
            continue
        linked = set(item.get("linked_question_ids", []))
        matches = not selected_questions or bool(linked & selected_questions)
        impact = _enum(item.get("decision_impact"), DECISION_IMPACTS, "MEDIUM")
        cost = _enum(item.get("research_cost"), RESEARCH_COSTS, "MEDIUM")
        judgment = _enum(
            item.get("research_judgment"), DIRECTION_JUDGMENTS, "UNRESOLVED"
        )
        next_move = _enum(
            item.get("next_move"), DIRECTION_NEXT_MOVES, "CONTINUE"
        )
        key = (
            0 if matches else 1,
            0 if next_move == "OPEN_NEW_DIRECTION" else 1,
            0 if item.get("load_bearing") is True else 1,
            impact_rank[impact],
            judgment_rank[judgment],
            cost_rank[cost],
            -int(item.get("first_seen_round", 0) or 0),
            item.get("direction_id", ""),
        )
        active.append((key, item))
    active.sort(key=lambda row: row[0])
    return [deepcopy(item) for _, item in active[:max(0, limit)]]


def _priority_projection(item, agenda, dispatch):
    status_rank = {"DISPUTED": 0, "OPEN": 1, "PARTIAL": 2}
    impact_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    cost_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    blind_spot_texts = {
        _norm(blind.get("statement"))
        for blind in agenda.get("blind_spots", [])
        if isinstance(blind, dict)
    }
    blind_spot_boost = (
        _norm(item.get("introduced_by_blind_spot")) in blind_spot_texts
        and bool(_norm(item.get("introduced_by_blind_spot")))
    )
    active_directions = [
        direction for direction in agenda.get("research_directions", [])
        if isinstance(direction, dict)
        and item.get("question_id") in direction.get("linked_question_ids", [])
        and direction.get("next_move", "CONTINUE") != "ANSWER"
    ]
    direction_boost = any(
        direction.get("decision_impact") == "HIGH"
        or direction.get("load_bearing") is True
        for direction in active_directions
    )
    pending_baseline = [
        finding for finding in agenda.get("baseline_findings", [])
        if isinstance(finding, dict)
        and item.get("question_id") in finding.get("linked_question_ids", [])
        and finding.get("disposition", "UNREVIEWED") == "UNREVIEWED"
    ]
    baseline_boost = bool(pending_baseline)
    impact = _enum(
        item.get("decision_impact"),
        DECISION_IMPACTS,
        _default_impact(item.get("question_type")),
    )
    cost = _enum(item.get("research_cost"), RESEARCH_COSTS, "MEDIUM")
    status = _text(item.get("answer_status")).upper()
    priority_key = (
        0 if item.get("blocks_current_recommendation") is True else 1,
        impact_rank[impact],
        0 if baseline_boost else 1,
        0 if blind_spot_boost else 1,
        0 if direction_boost else 1,
        status_rank.get(status, 3),
        cost_rank[cost],
        # Crux linkage is audit context only.  It may break a final tie but can
        # never outrank impact, uncertainty, or research cost.
        0 if item.get("linked_crux_id") in dispatch else 1,
        -int(item.get("first_seen_round", 0) or 0),
        item.get("question_id", ""),
    )
    reasons = [f"{impact}_IMPACT", f"{cost}_COST", status]
    if item.get("blocks_current_recommendation") is True:
        reasons.insert(0, "BLOCKS_RECOMMENDATION")
    if blind_spot_boost:
        reasons.insert(0, "NEW_BLIND_SPOT")
    if direction_boost:
        reasons.insert(0, "ACTIVE_RESEARCH_DIRECTION")
    if baseline_boost:
        reasons.insert(0, "UNDISPOSED_BASELINE_FINDING")
    return priority_key, {
        "decision_impact": impact,
        "research_cost": cost,
        "blind_spot_boost": blind_spot_boost,
        "direction_boost": direction_boost,
        "baseline_boost": baseline_boost,
        "baseline_finding_ids": [
            finding.get("finding_id") for finding in pending_baseline
        ],
        "reason_codes": reasons,
    }


def focus_questions(state, dispatch_cruxes=None, limit=5):
    agenda = state.get("research_agenda", {})
    dispatch = set(dispatch_cruxes or [])
    pending_baseline_question_ids = {
        question_id
        for finding in agenda.get("baseline_findings", [])
        if isinstance(finding, dict)
        and finding.get("disposition", "UNREVIEWED") == "UNREVIEWED"
        for question_id in finding.get("linked_question_ids", [])
    }
    questions = [
        item for item in projected_questions(state)
        if isinstance(item, dict)
        and (
            not research_kernel.answer_is_usable(item)
            or item.get("question_id") in pending_baseline_question_ids
        )
    ]
    ranked = [
        (*_priority_projection(item, agenda, dispatch), item)
        for item in questions
    ]
    ranked.sort(key=lambda row: row[0])
    return [
        {**deepcopy(item), "research_priority": deepcopy(priority)}
        for _, priority, item in ranked[:max(0, limit)]
    ]


def _clip(value, limit):
    value = _text(value)
    return value if len(value) <= limit else value[:max(0, limit - 1)] + "…"


def dispatch_questions(state, dispatch_cruxes=None, limit=5):
    """Project complete Agenda history into a bounded model work packet."""
    packets = []
    for raw in focus_questions(state, dispatch_cruxes, limit):
        item = deepcopy(raw)
        resolution = research_kernel.reconcile_answer_variants(
            item.get("answer_variants", [])
        )
        if resolution:
            item.update({
                "answer_status": resolution["answer_status"],
                "current_answer": resolution["current_answer"],
                "evidence_boundary": resolution["evidence_boundary"],
                "strongest_challenge": resolution["strongest_challenge"],
                "missing_information": resolution["missing_information"],
                "next_question": resolution["next_question"],
                "next_test_availability": resolution.get(
                    "next_test_availability", "UNKNOWN"
                ),
                "answer_resolution": resolution["resolution"],
            })
        evidence_refs = []
        seen = set()
        evidence_rows = [
            citation for citation in item.get("evidence", [])
            if isinstance(citation, dict)
        ]
        evidence_rows.sort(key=lambda citation: (
            _text(citation.get("date")), _text(citation.get("evidence_id"))
        ), reverse=True)
        for citation in evidence_rows:
            key = (
                _text(citation.get("evidence_id")),
                _text(citation.get("url")),
                _text(citation.get("claim")),
            )
            if key in seen:
                continue
            seen.add(key)
            evidence_refs.append({
                "evidence_id": citation.get("evidence_id"),
                "stance": citation.get("stance"),
                "claim": _clip(citation.get("claim"), 240),
                "source": _clip(citation.get("source"), 120),
                "url": citation.get("url"),
                "date": citation.get("date"),
            })
            if len(evidence_refs) >= 4:
                break
        packets.append({
            "question_id": item.get("question_id"),
            "question": _clip(item.get("question"), 500),
            "question_type": item.get("question_type"),
            "why_it_matters": _clip(item.get("why_it_matters"), 500),
            "success_condition": _clip(item.get("success_condition"), 500),
            "initial_search_routes": deepcopy(item.get("initial_search_routes", [])[:3]),
            "decision_impact": item.get("decision_impact"),
            "research_cost": item.get("research_cost"),
            "blocks_current_recommendation": item.get("blocks_current_recommendation") is True,
            "linked_crux_id": item.get("linked_crux_id"),
            "parent_question_id": item.get("parent_question_id", ""),
            "decision_change": _clip(item.get("decision_change"), 500),
            "answer_status": item.get("answer_status"),
            "current_answer": _clip(item.get("current_answer"), 650),
            "answer_resolution": item.get("answer_resolution"),
            "evidence_boundary": item.get("evidence_boundary"),
            "strongest_challenge": _clip(item.get("strongest_challenge"), 360),
            "missing_information": _clip(item.get("missing_information"), 360),
            "next_question": _clip(item.get("next_question"), 360),
            "next_test_availability": _next_test_availability(
                item.get("next_test_availability")
            ),
            "evidence_refs": evidence_refs,
            "history_summary": {
                "variant_count": len(item.get("answer_variants", [])),
                "rounds_touched": sorted({
                    int(variant.get("round", 0) or 0)
                    for variant in item.get("answer_variants", [])
                    if isinstance(variant, dict)
                }),
            },
            "research_priority": deepcopy(item.get("research_priority", {})),
        })
    return packets


def dispatch_directions(state, question_ids=None, limit=5):
    """Bound direction context while keeping every discriminating field."""
    return [{
        "direction_id": item.get("direction_id"),
        "proposition": _clip(item.get("proposition"), 450),
        "direction_kind": item.get("direction_kind"),
        "why_it_matters": _clip(item.get("why_it_matters"), 360),
        "discriminating_test": _clip(item.get("discriminating_test"), 450),
        "linked_question_ids": deepcopy(item.get("linked_question_ids", [])),
        "linked_crux_id": item.get("linked_crux_id"),
        "parent_direction_ids": deepcopy(item.get("parent_direction_ids", [])),
        "load_bearing": item.get("load_bearing") is True,
        "decision_impact": item.get("decision_impact"),
        "research_cost": item.get("research_cost"),
        "research_judgment": item.get("research_judgment"),
        "next_move": item.get("next_move"),
        "rationale": _clip(item.get("rationale"), 550),
        "evidence_boundary": item.get("evidence_boundary"),
        "evidence_ids": deepcopy(item.get("evidence_ids", [])[:8]),
        "strongest_challenge": _clip(item.get("strongest_challenge"), 420),
        "unresolved_question": _clip(item.get("unresolved_question"), 360),
        "next_test_availability": _next_test_availability(
            item.get("next_test_availability")
        ),
    } for item in focus_directions(state, question_ids, limit)]


def dispatch_baseline_findings(state, question_ids=None, limit=8):
    """Return only prior-run leads relevant to the selected work window."""
    selected = set(question_ids or [])
    items = []
    for raw in state.get("research_agenda", {}).get("baseline_findings", []):
        if not isinstance(raw, dict):
            continue
        if raw.get("disposition", "UNREVIEWED") != "UNREVIEWED":
            continue
        linked = set(raw.get("linked_question_ids", []))
        if selected and not linked.intersection(selected):
            continue
        items.append({
            "finding_id": raw.get("finding_id"),
            "claim": _clip(raw.get("claim"), 700),
            "why_it_matters": _clip(raw.get("why_it_matters"), 500),
            "source_url": raw.get("source_url"),
            "source_date": raw.get("source_date"),
            "linked_question_ids": deepcopy(raw.get("linked_question_ids", [])),
            "decision_impact": raw.get("decision_impact"),
            "disposition": raw.get("disposition", "UNREVIEWED"),
            "rationale": _clip(raw.get("rationale"), 500),
        })
    items.sort(key=lambda item: (
        {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(item.get("decision_impact"), 3),
        item.get("finding_id", ""),
    ))
    return items[:max(0, limit)]


def is_agenda_native(state):
    return (
        state.get("frame_contract", {}).get("control_mode") == "AGENDA_NATIVE"
        or state.get("research_agenda", {}).get("agenda_source") == "EXPLICIT_WORKPLAN"
    )


def _question_has_marginal_next_test(question, agenda, rounds_completed):
    """Whether one more cheap test is likely to add decision information."""
    if not isinstance(question, dict) or question.get("answer_status") == "ANSWERED":
        return False
    if _next_test_availability(
        question.get("next_test_availability")
    ) != "SEARCH_NOW":
        return False
    if _enum(question.get("research_cost"), RESEARCH_COSTS, "MEDIUM") != "LOW":
        return False
    if not any(_text(question.get(field)) for field in (
        "next_question", "missing_information", "success_condition"
    )):
        return False
    first_seen = int(question.get("first_seen_round", 0) or 0)
    # Old free-floating discoveries are useful report material, but without
    # lineage and a named decision change they cannot perpetually request work.
    if first_seen > 0 and (
        not _text(question.get("parent_question_id"))
        or not _text(question.get("decision_change"))
    ):
        return False
    question_id = question.get("question_id")
    touch_rounds = {
        int(summary_item.get("round", 0) or 0)
        for summary_item in agenda.get("round_summaries", [])
        if isinstance(summary_item, dict)
        for update in summary_item.get("accepted_updates", [])
        if isinstance(update, dict) and update.get("question_id") == question_id
    }
    variants = [
        item for item in question.get("answer_variants", [])
        if isinstance(item, dict)
    ]
    if question.get("answer_status") == "OPEN":
        return len(touch_rounds) < 2
    signatures_by_round = {}
    for item in variants:
        round_id = int(item.get("round", 0) or 0)
        signatures_by_round.setdefault(round_id, set()).add((
            _text(item.get("answer_status")).upper(),
            _text(item.get("evidence_boundary")).upper(),
        ))
    recent = [
        signatures_by_round[key] for key in sorted(signatures_by_round)[-2:]
    ]
    # Two attempted rounds with the same status/boundary are diminishing
    # returns. The unresolved item stays in the report; it no longer compels an
    # automatic recommendation for another round.
    if len(recent) == 2 and recent[0] == recent[1]:
        return False
    return bool(variants) and int(question.get("last_seen_round", 0) or 0) >= max(
        1, rounds_completed - 1
    )


def control_decision(state, round_num=None):
    """Decide research continuation from answerability, not crux convergence.

    A completed round is always report-deliverable.  This function only decides
    whether another round has enough expected information value to recommend.
    It never authorizes that round; the explicit runtime budget does.
    """
    rounds_completed = (
        int(round_num) if round_num is not None else len(state.get("rounds", []))
    )
    agenda = state.get("research_agenda", {})
    unresolved = focus_questions(state, limit=999)
    pending_baseline = [
        item for item in agenda.get("baseline_findings", [])
        if isinstance(item, dict)
        and item.get("disposition", "UNREVIEWED") == "UNREVIEWED"
    ]
    updates = [
        item
        for summary_item in agenda.get("round_summaries", [])
        if isinstance(summary_item, dict)
        for item in summary_item.get("accepted_updates", [])
        if isinstance(item, dict)
    ]
    baseline_updates = [
        item
        for summary_item in agenda.get("round_summaries", [])
        if isinstance(summary_item, dict)
        for item in summary_item.get("accepted_baseline_updates", [])
        if isinstance(item, dict)
    ]
    has_progress = bool(updates or baseline_updates)
    material = [
        item for item in unresolved
        if (
            item.get("blocks_current_recommendation") is True
            or item.get("research_priority", {}).get("decision_impact") == "HIGH"
            or (
                item.get("answer_status") == "DISPUTED"
                and item.get("research_priority", {}).get("decision_impact")
                in {"HIGH", "MEDIUM"}
            )
        )
        and _question_has_marginal_next_test(item, agenda, rounds_completed)
    ]
    active_directions = focus_directions(state, limit=999)
    material_question_ids = {item.get("question_id") for item in material}
    material_directions = [
        item for item in active_directions
        if (
            item.get("first_seen_round", 0) > 0
            or bool(item.get("judgment_history"))
        )
        and (
            (
                item.get("next_move") == "OPEN_NEW_DIRECTION"
                and int(item.get("last_seen_round", 0) or 0) >= rounds_completed
            )
            or (
                item.get("origin") == "ROUND_DISCOVERY"
                and int(item.get("first_seen_round", 0) or 0) >= rounds_completed
            )
        )
        and item.get("research_cost") == "LOW"
        and _next_test_availability(
            item.get("next_test_availability")
        ) == "SEARCH_NOW"
        and bool(set(item.get("linked_question_ids", [])) & material_question_ids)
    ]
    blind_spots = [
        item for item in agenda.get("blind_spots", [])
        if isinstance(item, dict)
        and item.get("blind_spot_id") in _open_blind_spot_ids(agenda)
        and item.get("blocks_current_recommendation") is True
        and item.get("decision_impact") == "HIGH"
        and item.get("research_cost") == "LOW"
        and _next_test_availability(
            item.get("next_test_availability")
        ) == "SEARCH_NOW"
        and bool(_text(item.get("cheapest_test")))
        and bool(set(item.get("linked_question_ids", [])) & material_question_ids)
    ]
    deferred_next_tests = []
    for item in unresolved:
        availability = _next_test_availability(
            item.get("next_test_availability")
        )
        if availability in {"WAIT_FOR_DATE", "WAIT_FOR_EVENT", "NEEDS_USER_DATA"}:
            deferred_next_tests.append({
                "kind": "QUESTION",
                "id": item.get("question_id"),
                "availability": availability,
                "test": _text(
                    item.get("next_question")
                    or item.get("missing_information")
                    or item.get("success_condition")
                ),
            })
    for item in agenda.get("blind_spots", []):
        if not isinstance(item, dict):
            continue
        availability = _next_test_availability(
            item.get("next_test_availability")
        )
        if availability in {"WAIT_FOR_DATE", "WAIT_FOR_EVENT", "NEEDS_USER_DATA"}:
            deferred_next_tests.append({
                "kind": "BLIND_SPOT",
                "id": item.get("blind_spot_id"),
                "availability": availability,
                "test": _text(item.get("cheapest_test")),
            })
    reasons = []
    if rounds_completed <= 0:
        reasons.append("NO_COMPLETED_ROUND")
    if rounds_completed > 0 and not has_progress:
        reasons.append("NO_AGENDA_PROGRESS")
    if material:
        reasons.append("MATERIAL_UNRESOLVED_QUESTIONS")
    if pending_baseline:
        reasons.append("UNDISPOSED_BASELINE_FINDINGS")
    if blind_spots:
        reasons.append("CHEAP_HIGH_IMPACT_BLIND_SPOT")
    if any(
        item.get("next_move") == "OPEN_NEW_DIRECTION"
        or item.get("origin") == "ROUND_DISCOVERY"
        for item in material_directions
    ):
        reasons.append("NEW_VIEWPOINT_OPENED")
    elif material_directions:
        reasons.append("RESEARCH_DIRECTION_REQUIRES_CONTINUATION")
    if deferred_next_tests and not (material or blind_spots or material_directions):
        reasons.append("DEFERRED_TESTS_NOT_SEARCHABLE_NOW")
    more_research_recommended = (
        rounds_completed <= 0
        or (
            bool(pending_baseline)
            or (
                has_progress
                and bool(material or blind_spots or material_directions)
            )
        )
    )
    runtime = state.get("research_runtime", {})
    try:
        authorized_rounds = int(runtime.get("authorized_rounds", 1))
    except (TypeError, ValueError):
        authorized_rounds = 1
    authorized_rounds = max(1, authorized_rounds)
    authorization_remaining = max(0, authorized_rounds - rounds_completed)
    report_deliverable = rounds_completed > 0
    if not report_deliverable:
        action = "CONTINUE_AUTHORIZED"
    elif more_research_recommended and authorization_remaining:
        action = "CONTINUE_AUTHORIZED"
    elif more_research_recommended:
        action = "RESEARCH_MORE_IF_AUTHORIZED"
    else:
        action = "DELIVER_REPORT"
    return {
        "schema_version": "trade-nothing.research-control.v1",
        "control_mode": "AGENDA_NATIVE",
        "rounds_completed": rounds_completed,
        "authorized_rounds": authorized_rounds,
        "authorization_remaining": authorization_remaining,
        "report_deliverable": report_deliverable,
        "product_readiness": (
            "NOT_STARTED"
            if not report_deliverable
            else "DELIVERABLE_LIMIT_REACHED_NO_PROGRESS"
            if not has_progress
            else "DELIVERABLE_MORE_RESEARCH_RECOMMENDED"
            if more_research_recommended
            else "DELIVERABLE_WAITING_FOR_NEW_INFORMATION"
            if deferred_next_tests
            else "DELIVERABLE_CURRENT_QUESTION_ANSWERABLE"
        ),
        "recommended_action": action,
        "more_research_recommended": more_research_recommended,
        "reason_codes": reasons or ["CURRENT_QUESTION_ANSWERABLE"],
        "open_question_ids": [item.get("question_id") for item in unresolved],
        "material_question_ids": [item.get("question_id") for item in material],
        "material_blind_spot_ids": [item.get("blind_spot_id") for item in blind_spots],
        "material_direction_ids": [
            item.get("direction_id") for item in material_directions
        ],
        "undisposed_baseline_finding_ids": [
            item.get("finding_id") for item in pending_baseline
        ],
        "next_questions": deepcopy(unresolved[:3]),
        "next_directions": deepcopy(material_directions[:3]),
        "next_test_mode": (
            "SEARCH_NOW" if more_research_recommended
            else deferred_next_tests[0]["availability"]
            if deferred_next_tests else "NONE"
        ),
        "deferred_next_tests": deepcopy(deferred_next_tests[:8]),
        "additional_rounds_recommended": 1 if more_research_recommended else 0,
        "boundary": (
            "This controls research attention and report timing only; it is not "
            "a probability, return estimate, trade instruction, or sizing input."
        ),
    }


def continuation_packet(state):
    control = control_decision(state)
    return {
        "schema_version": "trade-nothing.agenda-continuation.v1",
        "topic": state.get("topic", ""),
        "research_objective": state.get("research_agenda", {}).get(
            "research_objective", ""
        ),
        "recommended_extra_rounds": control["additional_rounds_recommended"],
        "reason_codes": control["reason_codes"],
        "focus_questions": deepcopy(control["next_questions"]),
        "material_blind_spot_ids": deepcopy(control["material_blind_spot_ids"]),
        "focus_directions": deepcopy(control["next_directions"]),
        "next_test_mode": control.get("next_test_mode", "NONE"),
        "deferred_next_tests": deepcopy(control.get("deferred_next_tests", [])),
        "authorization_required": (
            control["recommended_action"] == "RESEARCH_MORE_IF_AUTHORIZED"
        ),
    }


def summary(state):
    agenda = state.get("research_agenda", {})
    questions = projected_questions(state)
    counts = {status.lower() + "_count": 0 for status in QUESTION_STATUSES}
    for item in questions:
        key = _text(item.get("answer_status")).upper().lower() + "_count"
        if key in counts:
            counts[key] += 1
    usable_answer_count = sum(
        research_kernel.answer_is_usable(item) for item in questions
    )
    directions = projected_directions(state)
    baseline_findings = [
        item for item in agenda.get("baseline_findings", [])
        if isinstance(item, dict)
    ]
    direction_counts = {
        "supported_direction_count": 0,
        "challenged_direction_count": 0,
        "unresolved_direction_count": 0,
        "active_direction_count": 0,
    }
    for item in directions:
        judgment = _text(item.get("research_judgment")).lower()
        key = f"{judgment}_direction_count"
        if key in direction_counts:
            direction_counts[key] += 1
        if item.get("next_move", "CONTINUE") != "ANSWER":
            direction_counts["active_direction_count"] += 1
    return {
        "research_objective": _text(agenda.get("research_objective")),
        "agenda_source": _text(agenda.get("agenda_source")),
        "question_count": len(questions),
        "blind_spot_count": len(agenda.get("blind_spots", [])),
        "research_direction_count": len(directions),
        "evidence_item_count": len(agenda.get("evidence_items", [])),
        "baseline_finding_count": len(baseline_findings),
        "undisposed_baseline_finding_count": sum(
            item.get("disposition", "UNREVIEWED") == "UNREVIEWED"
            for item in baseline_findings
        ),
        "usable_answer_count": usable_answer_count,
        **direction_counts,
        **counts,
    }


def projected_questions(state):
    agenda = state.get("research_agenda", {})
    projected_questions = []
    for raw in agenda.get("questions", []):
        if not isinstance(raw, dict):
            continue
        item = deepcopy(raw)
        resolution = research_kernel.reconcile_answer_variants(
            item.get("answer_variants", [])
        )
        if resolution:
            item.update({
                "answer_status": resolution["answer_status"],
                "current_answer": resolution["current_answer"],
                "evidence_boundary": resolution["evidence_boundary"],
                "strongest_challenge": resolution["strongest_challenge"],
                "missing_information": resolution["missing_information"],
                "next_question": resolution["next_question"],
                "next_test_availability": resolution.get(
                    "next_test_availability", "UNKNOWN"
                ),
                "answer_resolution": resolution["resolution"],
            })
        projected_questions.append(item)
    return projected_questions


def projected_directions(state):
    agenda = state.get("research_agenda", {})
    projected = []
    for raw in agenda.get("research_directions", []):
        if not isinstance(raw, dict):
            continue
        item = deepcopy(raw)
        resolution = research_kernel.reconcile_direction_records(
            item.get("judgment_history", [])
        )
        if resolution:
            item.update({
                "research_judgment": resolution["research_judgment"],
                "next_move": resolution["next_move"],
                "rationale": resolution["rationale"],
                "evidence_boundary": resolution["evidence_boundary"],
                "strongest_challenge": resolution["strongest_challenge"],
                "unresolved_question": resolution["unresolved_question"],
                "evidence_ids": resolution["evidence_ids"],
                "next_test_availability": resolution.get(
                    "next_test_availability", "UNKNOWN"
                ),
                "judgment_resolution": resolution["resolution"],
            })
        projected.append(item)
    return projected


def report_view(state):
    agenda = state.get("research_agenda", {})
    question_view = projected_questions(state)
    research_control = (
        control_decision(state)
        if is_agenda_native(state)
        else {
            "control_mode": "LEGACY_CRUX",
            "product_readiness": "LEGACY_COMPATIBILITY_RUN",
            "recommended_action": "SEE_COMPATIBILITY_CONVERGENCE",
            "more_research_recommended": False,
            "reason_codes": ["AGENDA_NATIVE_CONTROL_NOT_APPLICABLE"],
        }
    )
    return {
        **summary(state),
        "questions": question_view,
        "research_directions": projected_directions(state),
        "evidence_items": deepcopy([
            item for item in agenda.get("evidence_items", [])
            if isinstance(item, dict)
        ]),
        "evidence_aliases": deepcopy(
            agenda.get("evidence_aliases", {})
            if isinstance(agenda.get("evidence_aliases"), dict) else {}
        ),
        "baseline_findings": deepcopy([
            item for item in agenda.get("baseline_findings", [])
            if isinstance(item, dict)
        ]),
        "blind_spots": deepcopy([
            item for item in agenda.get("blind_spots", []) if isinstance(item, dict)
        ]),
        "round_summaries": deepcopy(agenda.get("round_summaries", [])),
        "capability_boundary": deepcopy(agenda.get("capability_boundary", {})),
        "research_control": research_control,
    }
