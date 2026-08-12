#!/usr/bin/env python3
"""Value-first material-change register and delivery gate.

This module is deliberately not a workflow engine.  It owns three small,
deterministic questions that the language-model layer cannot answer reliably by
wording alone:

1. Did the research scan the subject's current official fact surface?
2. Which newly observed events can change a load-bearing conclusion?
3. Is a known material lead still unresolved at delivery time?

The register sits before the Research Agenda conceptually and beside it in
state.  It never promotes a security or creates a trade action.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib

import crux_engine


SCHEMA_VERSION = "trade-nothing.material-change-register.v1"
EVENT_TYPES = {
    "PERIODIC_REPORT", "CONTRACT_CUSTOMER", "OPERATING_METRIC",
    "FINANCING_CAPITAL", "OWNERSHIP_GOVERNANCE", "REGULATORY_LEGAL",
    "PROJECT_TECHNICAL", "POLICY_INDUSTRY", "MARKET_STRUCTURE", "OTHER",
}
ENTITY_TYPES = {
    "LISTED_COMPANY", "PRIVATE_COMPANY", "PROJECT", "EVENT", "INDUSTRY",
    "TECHNOLOGY", "ASSET", "OTHER",
}
DECISION_IMPACTS = {"HIGH", "MEDIUM", "LOW"}
ITEM_STATUSES = {"VERIFIED", "SINGLE_SOURCE", "UNRESOLVED", "REJECTED"}
LEAD_STATUSES = {"OPEN", "VERIFIED", "REJECTED"}
COVERAGE_OUTCOMES = {"FOUND", "NO_RESULT", "INSUFFICIENT"}

COMPANY_ROUTES = (
    "OFFICIAL_DISCLOSURE_INDEX",
    "LATEST_PERIODIC_REPORT",
    "COMMERCIAL_MILESTONES",
    "CAPITAL_REGULATORY",
)
PROJECT_ROUTES = (
    "OFFICIAL_EVENT_STATUS",
    "TECHNICAL_MILESTONES",
    "COMMERCIAL_MILESTONES",
    "CAPITAL_REGULATORY",
)
THEME_ROUTES = (
    "OFFICIAL_POLICY_DATA",
    "SUPPLY_DEMAND_REALITY",
    "MARKET_CARRIER_CHANGES",
    "RISKS_ALTERNATIVES",
)
ALL_ROUTE_KINDS = set(COMPANY_ROUTES + PROJECT_ROUTES + THEME_ROUTES)


def _text(value):
    return " ".join(str(value or "").split())


def _norm(value):
    return _text(value).lower()


def _stable_id(prefix, *parts):
    raw = "|".join(_norm(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12].upper()}"


def _enum(value, allowed, default):
    normalized = _text(value).upper()
    return normalized if normalized in allowed else default


def _routes_for(entity):
    entity_type = _enum(entity.get("entity_type"), ENTITY_TYPES, "OTHER")
    if entity_type in {"LISTED_COMPANY", "PRIVATE_COMPANY"}:
        return list(COMPANY_ROUTES)
    if entity_type in {"PROJECT", "EVENT", "TECHNOLOGY"}:
        return list(PROJECT_ROUTES)
    return list(THEME_ROUTES)


def _frame_entities(frame, topic=""):
    workplan = frame.get("research_workplan") if isinstance(frame, dict) else {}
    workplan = workplan if isinstance(workplan, dict) else {}
    raw_entities = workplan.get("primary_entities", [])
    raw_entities = raw_entities if isinstance(raw_entities, list) else []
    entities = []
    seen = set()
    for index, raw in enumerate(raw_entities[:4], start=1):
        if not isinstance(raw, dict) or not _text(raw.get("name")):
            continue
        entity_id = _text(raw.get("entity_id")) or f"E{index}"
        if entity_id in seen:
            continue
        seen.add(entity_id)
        entity = {
            "entity_id": entity_id,
            "name": _text(raw.get("name")),
            "entity_type": _enum(raw.get("entity_type"), ENTITY_TYPES, "OTHER"),
            "ticker": _text(raw.get("ticker")),
            "exchange": _text(raw.get("exchange")),
        }
        entity["required_route_kinds"] = _routes_for(entity)
        entities.append(entity)
    if not entities:
        name = _text(frame.get("unit_of_analysis") if isinstance(frame, dict) else "")
        name = name or _text(topic) or "research subject"
        fallback = {
            "entity_id": "E1",
            "name": name,
            "entity_type": "OTHER",
            "ticker": "",
            "exchange": "",
        }
        fallback["required_route_kinds"] = _routes_for(fallback)
        entities.append(fallback)
    return entities


def validate_frame(frame):
    """Validate explicit entity scope without breaking archived frame.v2 inputs."""
    workplan = frame.get("research_workplan") if isinstance(frame, dict) else None
    if not isinstance(workplan, dict) or "primary_entities" not in workplan:
        return []
    raw_entities = workplan.get("primary_entities")
    if not isinstance(raw_entities, list) or not 1 <= len(raw_entities) <= 4:
        return ["research_workplan_primary_entities_requires_1_to_4"]
    issues = []
    seen = set()
    for index, raw in enumerate(raw_entities, start=1):
        prefix = f"primary_entity_{index}"
        if not isinstance(raw, dict):
            issues.append(f"{prefix}_must_be_object")
            continue
        entity_id = _text(raw.get("entity_id"))
        if not entity_id:
            issues.append(f"{prefix}_missing_entity_id")
        elif entity_id in seen:
            issues.append(f"{prefix}_duplicate_entity_id")
        seen.add(entity_id)
        if not _text(raw.get("name")):
            issues.append(f"{prefix}_missing_name")
        entity_type = _text(raw.get("entity_type")).upper()
        if entity_type not in ENTITY_TYPES:
            issues.append(f"{prefix}_invalid_entity_type")
        if entity_type == "LISTED_COMPANY" and (
            not _text(raw.get("ticker")) or not _text(raw.get("exchange"))
        ):
            issues.append(f"{prefix}_listed_company_requires_ticker_exchange")
    return sorted(set(issues))


def initialize(frame, topic=""):
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of_date": _text((frame or {}).get("as_of_date")),
        "entities": _frame_entities(frame or {}, topic),
        "coverage": [],
        "items": [],
        "leads": [],
        "round_audits": [],
    }


def _agenda_evidence(state):
    agenda = state.get("research_agenda", {})
    items = agenda.get("evidence_items", []) if isinstance(agenda, dict) else []
    return {
        _text(item.get("evidence_id")): item
        for item in items
        if isinstance(item, dict) and _text(item.get("evidence_id"))
    }


def _canonical_evidence(state, round_num, role, evidence_ids):
    agenda = state.get("research_agenda", {})
    aliases = agenda.get("evidence_aliases", {}) if isinstance(agenda, dict) else {}
    aliases = aliases if isinstance(aliases, dict) else {}
    evidence = _agenda_evidence(state)
    accepted = []
    for submitted in evidence_ids if isinstance(evidence_ids, list) else []:
        submitted = _text(submitted)
        canonical_id = _text(aliases.get(submitted)) or submitted
        item = evidence.get(canonical_id)
        if not isinstance(item, dict):
            continue
        if int(item.get("round", 0) or 0) != int(round_num):
            continue
        if role not in item.get("roles", [item.get("role")]):
            continue
        if canonical_id not in accepted:
            accepted.append(canonical_id)
    return accepted


def _valid_iso_on_or_before(value, cutoff):
    try:
        observed = date.fromisoformat(_text(value))
        boundary = date.fromisoformat(_text(cutoff))
    except ValueError:
        return False
    return observed <= boundary


def _entity_by_id(register):
    return {
        item.get("entity_id"): item
        for item in register.get("entities", [])
        if isinstance(item, dict) and item.get("entity_id")
    }


def _question_ids(state):
    return {
        item.get("question_id")
        for item in state.get("research_agenda", {}).get("questions", [])
        if isinstance(item, dict) and item.get("question_id")
    }


def _ingest_coverage(register, round_num, role, payload, audit):
    entities = _entity_by_id(register)
    rows = payload.get("material_change_coverage", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []
    for raw in rows[:32]:
        if not isinstance(raw, dict):
            continue
        entity_id = _text(raw.get("entity_id"))
        route_kind = _text(raw.get("route_kind")).upper()
        outcome = _text(raw.get("outcome")).upper()
        query = _text(raw.get("query"))
        urls = raw.get("checked_urls", [])
        urls = urls if isinstance(urls, list) else []
        urls = list(dict.fromkeys(
            _text(url) for url in urls if crux_engine.is_concrete_url(url)
        ))[:8]
        if (
            entity_id not in entities
            or route_kind not in ALL_ROUTE_KINDS
            or route_kind not in entities[entity_id]["required_route_kinds"]
            or outcome not in COVERAGE_OUTCOMES
            or not query
            or not urls
        ):
            audit["rejected_coverage"].append({
                "role": role,
                "entity_id": entity_id,
                "route_kind": route_kind,
                "reason": "COVERAGE_REQUIRES_SCOPED_ROUTE_QUERY_AND_CHECKED_URL",
            })
            continue
        record = {
            "round": int(round_num),
            "role": role,
            "entity_id": entity_id,
            "route_kind": route_kind,
            "outcome": outcome,
            "query": query,
            "checked_urls": urls,
            "note": _text(raw.get("note")),
        }
        register.setdefault("coverage", []).append(record)
        audit["accepted_coverage"].append({
            "entity_id": entity_id, "route_kind": route_kind, "outcome": outcome,
        })


def _ingest_items(state, register, round_num, role, payload, audit):
    entities = _entity_by_id(register)
    valid_questions = _question_ids(state)
    rows = payload.get("material_change_items", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []
    known_keys = {
        (_norm(item.get("entity_id")), _norm(item.get("event_type")), _norm(item.get("claim")))
        for item in register.get("items", []) if isinstance(item, dict)
    }
    for raw in rows[:16]:
        if not isinstance(raw, dict):
            continue
        entity_id = _text(raw.get("entity_id"))
        event_type = _text(raw.get("event_type")).upper()
        claim = _text(raw.get("claim"))
        impact = _enum(raw.get("decision_impact"), DECISION_IMPACTS, "MEDIUM")
        evidence_ids = _canonical_evidence(
            state, round_num, role, raw.get("evidence_ids", [])
        )
        affected_questions = list(dict.fromkeys(
            _text(qid) for qid in raw.get("affected_question_ids", [])
            if _text(qid) in valid_questions
        ))
        published_date = _text(raw.get("published_date"))
        effective_date = _text(raw.get("effective_date")) or published_date
        if (
            entity_id not in entities or event_type not in EVENT_TYPES or not claim
            or not _text(raw.get("materiality_rationale"))
            or not _valid_iso_on_or_before(published_date, register.get("as_of_date"))
            or not _valid_iso_on_or_before(effective_date, register.get("as_of_date"))
            or not affected_questions or not evidence_ids
        ):
            audit["rejected_items"].append({
                "role": role,
                "entity_id": entity_id,
                "claim": claim,
                "reason": "ITEM_REQUIRES_ENTITY_DATE_MATERIALITY_QUESTION_AND_CURRENT_EVIDENCE",
            })
            continue
        key = (_norm(entity_id), _norm(event_type), _norm(claim))
        if key in known_keys:
            continue
        evidence_by_id = _agenda_evidence(state)
        primary = any(
            str(evidence_by_id[eid].get("source_tier") or "").lower() == "primary"
            for eid in evidence_ids if eid in evidence_by_id
        )
        submitted_status = _enum(raw.get("status"), ITEM_STATUSES, "UNRESOLVED")
        status = (
            "VERIFIED" if primary and submitted_status not in {"REJECTED", "UNRESOLVED"}
            else "SINGLE_SOURCE" if submitted_status != "REJECTED"
            else "REJECTED"
        )
        event_id = _text(raw.get("event_id")) or _stable_id(
            "MC", entity_id, event_type, claim, published_date
        )
        record = {
            "event_id": event_id,
            "entity_id": entity_id,
            "event_type": event_type,
            "published_date": published_date,
            "effective_date": effective_date,
            "claim": claim,
            "materiality_rationale": _text(raw.get("materiality_rationale")),
            "decision_impact": impact,
            "affected_question_ids": affected_questions,
            "affected_conclusion_keys": list(dict.fromkeys(
                _text(value) for value in raw.get("affected_conclusion_keys", [])
                if _text(value)
            ))[:8],
            "evidence_ids": evidence_ids,
            "status": status,
            "supersedes_event_ids": list(dict.fromkeys(
                _text(value) for value in raw.get("supersedes_event_ids", [])
                if _text(value)
            ))[:8],
            "resolves_lead_ids": list(dict.fromkeys(
                _text(value) for value in raw.get("resolves_lead_ids", [])
                if _text(value)
            ))[:8],
            "round": int(round_num),
            "role": role,
        }
        register.setdefault("items", []).append(record)
        known_keys.add(key)
        audit["accepted_item_ids"].append(event_id)


def _ingest_leads(register, round_num, role, payload, audit):
    entities = _entity_by_id(register)
    rows = payload.get("material_change_leads", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []
    known = {_norm(item.get("claim")): item for item in register.get("leads", [])}
    for raw in rows[:12]:
        if not isinstance(raw, dict):
            continue
        entity_id = _text(raw.get("entity_id"))
        claim = _text(raw.get("claim"))
        source_url = _text(raw.get("source_url"))
        if (
            entity_id not in entities or not claim
            or not _text(raw.get("why_it_may_matter"))
            or not crux_engine.is_concrete_url(source_url)
        ):
            audit["rejected_leads"].append({
                "role": role, "entity_id": entity_id, "claim": claim,
                "reason": "LEAD_REQUIRES_ENTITY_CLAIM_MATERIALITY_AND_CONCRETE_URL",
            })
            continue
        key = _norm(claim)
        if key in known:
            continue
        lead_id = _text(raw.get("lead_id")) or _stable_id(
            "ML", entity_id, claim, source_url
        )
        record = {
            "lead_id": lead_id,
            "entity_id": entity_id,
            "claim": claim,
            "why_it_may_matter": _text(raw.get("why_it_may_matter")),
            "decision_impact": _enum(
                raw.get("decision_impact"), DECISION_IMPACTS, "MEDIUM"
            ),
            "source_url": source_url,
            "observed_date": _text(raw.get("observed_date")),
            "status": "OPEN",
            "resolution_rationale": "",
            "resolution_evidence_ids": [],
            "first_seen_round": int(round_num),
            "role": role,
        }
        register.setdefault("leads", []).append(record)
        known[key] = record
        audit["accepted_lead_ids"].append(lead_id)


def _resolve_leads(state, register, round_num, role, payload, audit):
    by_id = {
        item.get("lead_id"): item
        for item in register.get("leads", [])
        if isinstance(item, dict) and item.get("lead_id")
    }
    rows = payload.get("material_change_lead_updates", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []
    for raw in rows[:12]:
        if not isinstance(raw, dict):
            continue
        lead = by_id.get(_text(raw.get("lead_id")))
        status = _text(raw.get("status")).upper()
        rationale = _text(raw.get("rationale"))
        evidence_ids = _canonical_evidence(
            state, round_num, role, raw.get("evidence_ids", [])
        )
        if (
            not lead or lead.get("status") != "OPEN"
            or status not in {"VERIFIED", "REJECTED"} or not rationale
            or not evidence_ids
        ):
            audit["rejected_lead_updates"].append({
                "role": role, "lead_id": _text(raw.get("lead_id")),
                "reason": "LEAD_UPDATE_REQUIRES_OPEN_LEAD_STATUS_RATIONALE_AND_EVIDENCE",
            })
            continue
        lead.update({
            "status": status,
            "resolution_rationale": rationale,
            "resolution_evidence_ids": evidence_ids,
            "resolved_round": int(round_num),
            "resolved_by": role,
        })
        audit["accepted_lead_updates"].append({
            "lead_id": lead.get("lead_id"), "status": status,
        })
    resolved_by_items = {
        lead_id
        for item in register.get("items", [])
        if isinstance(item, dict) and int(item.get("round", 0) or 0) == int(round_num)
        for lead_id in item.get("resolves_lead_ids", [])
    }
    for lead_id in resolved_by_items:
        lead = by_id.get(lead_id)
        if lead and lead.get("status") == "OPEN":
            lead.update({
                "status": "VERIFIED",
                "resolution_rationale": "Resolved by a current-round material-change item.",
                "resolved_round": int(round_num),
                "resolved_by": role,
            })


def harvest_round(state, round_num, **role_payloads):
    register = state.setdefault(
        "material_change_register",
        initialize({"as_of_date": state.get("frame_contract", {}).get("as_of_date", "")}, state.get("topic", "")),
    )
    audit = {
        "round": int(round_num),
        "accepted_coverage": [], "rejected_coverage": [],
        "accepted_item_ids": [], "rejected_items": [],
        "accepted_lead_ids": [], "rejected_leads": [],
        "accepted_lead_updates": [], "rejected_lead_updates": [],
    }
    for role, payload in role_payloads.items():
        if not isinstance(payload, dict) or payload.get("_execution", {}).get("status") == "SKIPPED":
            continue
        _ingest_coverage(register, round_num, role, payload, audit)
        _ingest_items(state, register, round_num, role, payload, audit)
        _ingest_leads(register, round_num, role, payload, audit)
        _resolve_leads(state, register, round_num, role, payload, audit)
    register.setdefault("round_audits", []).append(deepcopy(audit))
    return audit


def _latest_coverage(register):
    latest = {}
    for item in register.get("coverage", []):
        if not isinstance(item, dict):
            continue
        key = (item.get("entity_id"), item.get("route_kind"))
        previous = latest.get(key)
        if previous is None or int(item.get("round", 0) or 0) >= int(previous.get("round", 0) or 0):
            latest[key] = item
    return latest


def delivery_gate(state):
    register = state.get("material_change_register", {})
    entities = register.get("entities", []) if isinstance(register, dict) else []
    latest = _latest_coverage(register if isinstance(register, dict) else {})
    blockers = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        entity_id = entity.get("entity_id")
        for route_kind in entity.get("required_route_kinds", []):
            coverage = latest.get((entity_id, route_kind))
            if not coverage or coverage.get("outcome") == "INSUFFICIENT":
                blockers.append({
                    "code": "MATERIAL_COVERAGE_GAP",
                    "entity_id": entity_id,
                    "route_kind": route_kind,
                    "impact": "HIGH",
                    "searchable_now": True,
                })
    for lead in register.get("leads", []) if isinstance(register, dict) else []:
        if (
            isinstance(lead, dict) and lead.get("status") == "OPEN"
            and lead.get("decision_impact") == "HIGH"
        ):
            blockers.append({
                "code": "KNOWN_MATERIAL_LEAD_OPEN",
                "lead_id": lead.get("lead_id"),
                "entity_id": lead.get("entity_id"),
                "impact": "HIGH",
                "searchable_now": True,
            })
    for item in register.get("items", []) if isinstance(register, dict) else []:
        if (
            isinstance(item, dict) and item.get("decision_impact") == "HIGH"
            and item.get("status") in {"UNRESOLVED", "SINGLE_SOURCE"}
        ):
            blockers.append({
                "code": "HIGH_IMPACT_CHANGE_NOT_PRIMARY_VERIFIED",
                "event_id": item.get("event_id"),
                "entity_id": item.get("entity_id"),
                "impact": "HIGH",
                "searchable_now": True,
            })
    return {
        "schema_version": "trade-nothing.material-delivery-gate.v1",
        "status": "MATERIAL_FACT_GAP" if blockers else "CURRENT_TRUTH_BOUNDED",
        "decision_ready": not bool(blockers),
        "blockers": blockers,
        "blocker_count": len(blockers),
        "boundary": (
            "This gate prevents a known material omission from being presented as a current, "
            "decision-ready view. It does not prove exhaustive discovery or alpha."
        ),
    }


def challenge_targets(state):
    """Return load-bearing answers that have not received an independent challenge."""
    targets = []
    questions = state.get("research_agenda", {}).get("questions", [])
    for item in questions if isinstance(questions, list) else []:
        if not isinstance(item, dict):
            continue
        impact = _text(item.get("decision_impact")).upper()
        if impact != "HIGH" and item.get("blocks_current_recommendation") is not True:
            continue
        if item.get("answer_status") not in {"ANSWERED", "PARTIAL", "DISPUTED"}:
            continue
        roles = {
            _text(variant.get("role"))
            for variant in item.get("answer_variants", [])
            if isinstance(variant, dict) and _text(variant.get("answer"))
        }
        if "detective" in roles and "inquisitor" not in roles:
            targets.append({
                "question_id": item.get("question_id"),
                "question": item.get("question"),
                "current_answer": item.get("current_answer"),
                "evidence_boundary": item.get("evidence_boundary"),
                "strongest_challenge": item.get("strongest_challenge"),
                "decision_impact": impact or "MEDIUM",
            })
    return targets[:4]


def augment_research_control(state, control):
    """Overlay value readiness on Agenda timing without creating new lifecycle state."""
    result = deepcopy(control) if isinstance(control, dict) else {}
    gate = delivery_gate(state)
    targets = challenge_targets(state)
    rounds_completed = int(result.get("rounds_completed", len(state.get("rounds", []))) or 0)
    authorized = int(result.get("authorized_rounds", 1) or 1)
    remaining = max(0, authorized - rounds_completed)
    needs_search = bool(gate.get("blockers"))
    needs_challenge = bool(targets)
    if needs_search or needs_challenge:
        reasons = list(result.get("reason_codes", []))
        if needs_search and "MATERIAL_FACT_GAP" not in reasons:
            reasons.insert(0, "MATERIAL_FACT_GAP")
        if needs_challenge and "LOAD_BEARING_CLAIMS_UNCHALLENGED" not in reasons:
            reasons.append("LOAD_BEARING_CLAIMS_UNCHALLENGED")
        result["reason_codes"] = reasons
        result["more_research_recommended"] = True
        result["recommended_action"] = (
            "CONTINUE_AUTHORIZED" if remaining else "RESEARCH_MORE_IF_AUTHORIZED"
        )
        result["additional_rounds_recommended"] = 1
        result["next_test_mode"] = "SEARCH_NOW"
    result["product_readiness"] = (
        "DELIVERABLE_MATERIAL_FACT_GAP"
        if gate["status"] == "MATERIAL_FACT_GAP"
        else "DELIVERABLE_TARGETED_CHALLENGE_OPTIONAL"
        if targets
        else result.get("product_readiness", "DELIVERABLE_CURRENT_QUESTION_ANSWERABLE")
    )
    result["material_change_gate"] = gate
    result["challenge_targets"] = targets
    return result


def report_view(state):
    register = deepcopy(state.get("material_change_register", {}))
    if not isinstance(register, dict):
        register = {}
    entities = _entity_by_id(register)
    superseded = {
        event_id
        for item in register.get("items", [])
        if isinstance(item, dict)
        for event_id in item.get("supersedes_event_ids", [])
    }
    current_items = [
        deepcopy(item) for item in register.get("items", [])
        if isinstance(item, dict) and item.get("event_id") not in superseded
        and item.get("status") != "REJECTED"
    ]
    current_items.sort(
        key=lambda item: (item.get("effective_date", ""), item.get("event_id", "")),
        reverse=True,
    )
    current_items.sort(key=lambda item: (
        {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(item.get("decision_impact"), 3)
    ))
    for item in current_items:
        entity = entities.get(item.get("entity_id"), {})
        item["entity_name"] = entity.get("name", item.get("entity_id"))
    latest = _latest_coverage(register)
    coverage_rows = []
    for entity in register.get("entities", []):
        for route_kind in entity.get("required_route_kinds", []):
            coverage = deepcopy(latest.get((entity.get("entity_id"), route_kind), {}))
            coverage_rows.append({
                "entity_id": entity.get("entity_id"),
                "entity_name": entity.get("name"),
                "route_kind": route_kind,
                "outcome": coverage.get("outcome", "MISSING"),
                "round": coverage.get("round"),
                "checked_urls": coverage.get("checked_urls", []),
            })
    return {
        "schema_version": SCHEMA_VERSION,
        "entities": deepcopy(register.get("entities", [])),
        "current_items": current_items,
        "open_leads": [
            deepcopy(item) for item in register.get("leads", [])
            if isinstance(item, dict) and item.get("status") == "OPEN"
        ],
        "coverage": coverage_rows,
        "delivery_gate": delivery_gate(state),
        "challenge_targets": challenge_targets(state),
    }
