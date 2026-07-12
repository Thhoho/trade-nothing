#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic OpportunitySeed harvesting for the v2 crux workflow.

The engine does not discover ideas itself. It only admits candidate seeds whose
citations can be traced back to structured evidence produced by the same agent,
for the same crux, in the same round. Seeds are a research queue, never a trade
signal, expected-return estimate, or position-sizing input.
"""
import hashlib
import re
from datetime import date

import crux_engine


RELATION_TYPES = {
    "DIRECT_WINNER",
    "SUBSTITUTE_WINNER",
    "COMPETITOR_WINNER",
    "BOTTLENECK_OWNER",
    "INFRA_ASSET_OWNER",
    "SECOND_ORDER",
    "SHORT_CANDIDATE",
}

ASSET_TYPES = {
    "LISTED_EQUITY",
    "PRIVATE_COMPANY",
    "COMMODITY",
    "TECHNOLOGY",
    "OTHER",
}

TEXT_FIELDS = (
    "causal_path",
    "economic_exposure",
    "why_market_may_miss",
    "catalyst",
    "falsifier",
)

READY = "READY_FOR_SCREENING"
EVIDENCE_BACKED = "EVIDENCE_BACKED"
BLOCKED_ORIGIN = "BLOCKED_ORIGIN_CRUX"
BLOCKED_ROOT = "BLOCKED_ROOT_UNCONVERGED"
NEEDS_CATALYST = "NEEDS_CATALYST_CHECK"
OUT_OF_HORIZON = "OUT_OF_HORIZON_LEAD"


def _text(value):
    return " ".join(str(value or "").split())


def _norm(value):
    return re.sub(r"[^\w一-龥]+", "", _text(value).lower())


def _ticker(value):
    return re.sub(r"\s+", "", _text(value).upper())


def _seed_key(seed):
    identity = _ticker(seed.get("ticker")) or _norm(seed.get("candidate"))
    return "|".join((identity, seed.get("relation_type", ""), seed.get("origin_crux", "")))


def entity_identity(seed):
    """Stable exact entity key used for display/screen de-duplication.

    Opportunity paths remain separate records. Evidence from two paths is never
    combined to promote either path.
    """
    ticker = _ticker(seed.get("ticker"))
    if ticker:
        return f"{_text(seed.get('asset_type') or 'OTHER').upper()}|TICKER|{ticker}"
    candidate = _norm(seed.get("candidate"))
    return f"{_text(seed.get('asset_type') or 'OTHER').upper()}|NAME|{candidate}"


def entity_id(seed):
    key = entity_identity(seed)
    return "OE-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:10].upper()


def _seed_id(key):
    return "OS-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:10].upper()


def _agent_evidence(payload, agent_name):
    """Return {crux_id: {citation_identity: citation}} for one agent."""
    payload = payload if isinstance(payload, dict) else {}
    out = {}
    if agent_name == "detective":
        groups, field = payload.get("crux_evidence", []), "evidence"
    else:
        groups, field = payload.get("crux_attacks", []), "attacks"
    for group in groups if isinstance(groups, list) else []:
        if not isinstance(group, dict) or not group.get("crux_id"):
            continue
        bucket = out.setdefault(group["crux_id"], {})
        items = group.get(field, [])
        for item in items if isinstance(items, list) else []:
            key = crux_engine.citation_identity(item)
            if key:
                bucket[key] = item
    return out


def _reason(audit, reason, amount=1):
    audit["rejected"] += amount
    reasons = audit.setdefault("rejected_reasons", {})
    reasons[reason] = reasons.get(reason, 0) + amount


def _normalize_seed(raw, state, agent_name, round_num, allowed, audit):
    if not isinstance(raw, dict):
        _reason(audit, "seed_not_object")
        return None

    candidate = _text(raw.get("candidate"))
    relation = _text(raw.get("relation_type")).upper()
    origin = _text(raw.get("origin_crux"))
    asset_type = _text(raw.get("asset_type") or "OTHER").upper()
    causal_path = _text(raw.get("causal_path"))
    if not candidate:
        _reason(audit, "missing_candidate")
        return None
    if relation not in RELATION_TYPES:
        _reason(audit, "invalid_relation_type")
        return None
    if origin not in state.get("cruxes", {}):
        _reason(audit, "unknown_origin_crux")
        return None
    if asset_type not in ASSET_TYPES:
        _reason(audit, "invalid_asset_type")
        return None
    if not causal_path:
        _reason(audit, "missing_causal_path")
        return None

    submitted = raw.get("evidence", [])
    submitted = submitted if isinstance(submitted, list) else []
    allowed_for_crux = allowed.get(origin, {})
    accepted, seen = [], set()
    for citation in submitted:
        key = crux_engine.citation_identity(citation)
        if not key or key not in allowed_for_crux:
            audit["dropped_citations"] += 1
            continue
        if key in seen:
            audit["dropped_citations"] += 1
            continue
        seen.add(key)
        # Store the agent's original evidence object, not a seed-side rewrite.
        accepted.append(dict(allowed_for_crux[key]))
    if not accepted:
        _reason(audit, "no_agent_backed_citation")
        return None

    seed = {
        "candidate": candidate,
        "ticker": _ticker(raw.get("ticker")) or None,
        "asset_type": asset_type,
        "relation_type": relation,
        "origin_crux": origin,
        "causal_path": causal_path,
        "economic_exposure": _text(raw.get("economic_exposure")),
        "why_market_may_miss": _text(raw.get("why_market_may_miss")),
        "catalyst": _text(raw.get("catalyst")),
        "catalyst_window": _normalize_catalyst_window(raw.get("catalyst_window")),
        "falsifier": _text(raw.get("falsifier")),
        "evidence": accepted,
        "first_seen_round": round_num,
        "last_seen_round": round_num,
        "source_agents": [agent_name],
    }
    key = _seed_key(seed)
    if not key.split("|", 1)[0]:
        _reason(audit, "invalid_candidate_identity")
        return None
    seed["seed_id"] = _seed_id(key)
    seed["entity_id"] = entity_id(seed)
    seed["maturity"] = evidence_maturity(seed)
    return seed


def _normalize_catalyst_window(value):
    if not isinstance(value, dict):
        return {}
    expected_by = _text(value.get("expected_by"))
    try:
        if expected_by:
            date.fromisoformat(expected_by)
    except ValueError:
        expected_by = ""
    status = _text(value.get("date_status")).upper()
    if status not in {"REVIEW_CHECKPOINT", "DATE_CLAIMED_UNVERIFIED"}:
        status = ""
    event = _text(value.get("event"))
    if not any((event, expected_by, status)):
        return {}
    return {"event": event, "expected_by": expected_by, "date_status": status}


def evidence_maturity(seed):
    sources = {
        crux_engine.citation_source_identity(c)
        for c in seed.get("evidence", [])
        if crux_engine.valid_citation(c)
    }
    if len(sources) >= 2 and _text(seed.get("economic_exposure")) and _text(seed.get("falsifier")):
        return READY
    return EVIDENCE_BACKED


def maturity(seed):
    """Compatibility projection: evidence maturity only, never screen eligibility."""
    return evidence_maturity(seed)


def _origin_gate(state, seed):
    origin = state.get("cruxes", {}).get(seed.get("origin_crux"))
    if not isinstance(origin, dict):
        return ["origin_crux_missing"]
    blockers = []
    if origin.get("first_contested") is None:
        blockers.append("origin_crux_never_contested")
    if origin.get("status") not in {"RESOLVED_BULL", "RESOLVED_BEAR", "MONITORABLE"}:
        blockers.append("origin_crux_unsettled")
    source_count = len({
        crux_engine.citation_source_identity(c)
        for c in origin.get("citations", [])
        if crux_engine.valid_citation(c)
    })
    if source_count < crux_engine.MIN_VALID_CITATIONS:
        blockers.append("origin_crux_insufficient_sources")
    return blockers


def _catalyst_gate(state, seed):
    window = seed.get("catalyst_window") if isinstance(seed.get("catalyst_window"), dict) else {}
    expected_by = _text(window.get("expected_by"))
    event = _text(window.get("event"))
    date_status = _text(window.get("date_status")).upper()
    if not expected_by or not event or date_status not in {
        "REVIEW_CHECKPOINT", "DATE_CLAIMED_UNVERIFIED"
    }:
        return NEEDS_CATALYST, ["catalyst_date_unverified"]
    try:
        catalyst_date = date.fromisoformat(expected_by)
        as_of = date.fromisoformat(_text(state.get("frame_contract", {}).get("as_of_date")))
    except ValueError:
        return NEEDS_CATALYST, ["catalyst_date_invalid"]
    days = (catalyst_date - as_of).days
    if days <= 0:
        return OUT_OF_HORIZON, ["catalyst_expired"]
    if str(state.get("horizon", "")).upper() == "3-6M" and days > 190:
        return OUT_OF_HORIZON, ["catalyst_outside_root_horizon"]
    return READY, []


def assess_seed(state, seed):
    """Stateful screen-eligibility projection for one evidence path."""
    evidence_state = evidence_maturity(seed)
    blockers = []
    if evidence_state != READY:
        return {
            "evidence_maturity": evidence_state,
            "screening_status": EVIDENCE_BACKED,
            "blockers": ["seed_evidence_incomplete"],
            "origin_status": state.get("cruxes", {}).get(seed.get("origin_crux"), {}).get("status"),
        }
    origin_blockers = _origin_gate(state, seed)
    if origin_blockers:
        return {
            "evidence_maturity": evidence_state,
            "screening_status": BLOCKED_ORIGIN,
            "blockers": origin_blockers,
            "origin_status": state.get("cruxes", {}).get(seed.get("origin_crux"), {}).get("status"),
        }
    if state.get("last_convergence", {}).get("decision") != "converge":
        return {
            "evidence_maturity": evidence_state,
            "screening_status": BLOCKED_ROOT,
            "blockers": ["root_thesis_unconverged"],
            "origin_status": state.get("cruxes", {}).get(seed.get("origin_crux"), {}).get("status"),
        }
    catalyst_state, catalyst_blockers = _catalyst_gate(state, seed)
    return {
        "evidence_maturity": evidence_state,
        "screening_status": catalyst_state,
        "blockers": catalyst_blockers,
        "origin_status": state.get("cruxes", {}).get(seed.get("origin_crux"), {}).get("status"),
    }


def entity_views(state):
    """Return one deterministic display/screen view per exact candidate identity."""
    groups = {}
    for seed in state.get("opportunity_seeds", []):
        if not isinstance(seed, dict) or not _text(seed.get("candidate")):
            continue
        groups.setdefault(entity_identity(seed), []).append(seed)
    priority = {
        READY: 0,
        NEEDS_CATALYST: 1,
        BLOCKED_ROOT: 2,
        BLOCKED_ORIGIN: 3,
        OUT_OF_HORIZON: 4,
        EVIDENCE_BACKED: 5,
    }
    out = []
    for identity, paths in groups.items():
        assessed = [(seed, assess_seed(state, seed)) for seed in paths]
        assessed.sort(key=lambda item: (
            priority.get(item[1]["screening_status"], 99),
            -len(item[0].get("evidence", [])),
            item[0].get("first_seen_round", 0),
            item[0].get("seed_id", ""),
        ))
        representative, assessment = assessed[0]
        out.append({
            "entity_id": entity_id(representative),
            "entity_identity": identity,
            "candidate": representative.get("candidate"),
            "ticker": representative.get("ticker"),
            "asset_type": representative.get("asset_type"),
            "screening_status": assessment["screening_status"],
            "representative_seed_id": representative.get("seed_id"),
            "representative_seed": representative,
            "paths": [
                {
                    "seed_id": seed.get("seed_id"),
                    "origin_crux": seed.get("origin_crux"),
                    "relation_type": seed.get("relation_type"),
                    "assessment": result,
                }
                for seed, result in assessed
            ],
        })
    out.sort(key=lambda item: (
        priority.get(item["screening_status"], 99),
        _norm(item.get("candidate")),
        item.get("entity_id", ""),
    ))
    return out


def _merge(existing, incoming):
    if incoming.get("candidate") and _norm(incoming["candidate"]) != _norm(existing.get("candidate")):
        aliases = existing.setdefault("candidate_aliases", [])
        if incoming["candidate"] not in aliases:
            aliases.append(incoming["candidate"])
    if not existing.get("ticker") and incoming.get("ticker"):
        existing["ticker"] = incoming["ticker"]
    if existing.get("asset_type") == "OTHER" and incoming.get("asset_type") != "OTHER":
        existing["asset_type"] = incoming["asset_type"]

    incoming_window = incoming.get("catalyst_window")
    current_window = existing.get("catalyst_window")
    if incoming_window and not current_window:
        existing["catalyst_window"] = incoming_window
    elif incoming_window and incoming_window != current_window:
        variants = existing.setdefault("field_variants", {}).setdefault("catalyst_window", [])
        for item in (current_window, incoming_window):
            if item and item not in variants:
                variants.append(item)

    for field in TEXT_FIELDS:
        value = _text(incoming.get(field))
        current = _text(existing.get(field))
        if value and not current:
            existing[field] = value
        elif value and _norm(value) != _norm(current):
            variants = existing.setdefault("field_variants", {}).setdefault(field, [])
            for item in (current, value):
                if item and item not in variants:
                    variants.append(item)

    evidence = existing.setdefault("evidence", [])
    evidence_keys = {crux_engine.citation_identity(c) for c in evidence}
    for citation in incoming.get("evidence", []):
        key = crux_engine.citation_identity(citation)
        if key and key not in evidence_keys:
            evidence.append(citation)
            evidence_keys.add(key)
    existing["source_agents"] = sorted(set(existing.get("source_agents", [])) | set(incoming.get("source_agents", [])))
    existing["last_seen_round"] = max(existing.get("last_seen_round", 0), incoming.get("last_seen_round", 0))
    existing["entity_id"] = entity_id(existing)
    existing["maturity"] = evidence_maturity(existing)


def harvest_round(state, round_num, detective=None, inquisitor=None):
    """Validate, de-duplicate, and merge one round's OpportunitySeeds into state."""
    audit = {
        "round": round_num,
        "submitted": 0,
        "accepted_new": 0,
        "merged_existing": 0,
        "rejected": 0,
        "dropped_citations": 0,
        "rejected_reasons": {},
    }
    seeds = state.setdefault("opportunity_seeds", [])
    existing = {_seed_key(seed): seed for seed in seeds if isinstance(seed, dict)}

    for agent_name, payload in (("detective", detective), ("inquisitor", inquisitor)):
        payload = payload if isinstance(payload, dict) else {}
        raw_seeds = payload.get("opportunity_seeds", [])
        raw_seeds = raw_seeds if isinstance(raw_seeds, list) else []
        audit["submitted"] += len(raw_seeds)
        if len(raw_seeds) > 3:
            _reason(audit, f"{agent_name}_round_limit_exceeded", len(raw_seeds) - 3)
        allowed = _agent_evidence(payload, agent_name)
        for raw in raw_seeds[:3]:
            seed = _normalize_seed(raw, state, agent_name, round_num, allowed, audit)
            if not seed:
                continue
            key = _seed_key(seed)
            if key in existing:
                _merge(existing[key], seed)
                audit["merged_existing"] += 1
            else:
                seeds.append(seed)
                existing[key] = seed
                audit["accepted_new"] += 1

    seeds.sort(key=lambda s: (
        0 if evidence_maturity(s) == READY else 1,
        s.get("first_seen_round", 0),
        _norm(s.get("candidate")),
        s.get("relation_type", ""),
    ))
    audit.update(summary(state))
    return audit


def summary(state):
    seeds = [s for s in state.get("opportunity_seeds", []) if isinstance(s, dict)]
    assessments = [assess_seed(state, seed) for seed in seeds]
    entities = entity_views(state)
    return {
        "opportunity_seed_count": len(seeds),
        "unique_candidate_count": len(entities),
        "duplicate_path_count": max(0, len(seeds) - len(entities)),
        "evidence_ready_count": sum(a["evidence_maturity"] == READY for a in assessments),
        "ready_for_screening_count": sum(e["screening_status"] == READY for e in entities),
        "blocked_origin_count": sum(e["screening_status"] == BLOCKED_ORIGIN for e in entities),
        "blocked_root_count": sum(e["screening_status"] == BLOCKED_ROOT for e in entities),
        "needs_catalyst_check_count": sum(e["screening_status"] == NEEDS_CATALYST for e in entities),
        "out_of_horizon_count": sum(e["screening_status"] == OUT_OF_HORIZON for e in entities),
    }
