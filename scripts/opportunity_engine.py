#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic OpportunitySeed harvesting for the v2 crux workflow.

The engine does not discover ideas itself. It only admits candidate seeds whose
citations can be traced back to structured evidence produced by the same agent,
for the same crux, in the same round. Seeds are a research queue, never a trade
signal, expected-return estimate, or position-sizing input.
"""
import copy
import hashlib
import re
from datetime import date

import crux_engine
import landscape_engine


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

PRICING_ANCHOR_TYPES = {
    "ABSOLUTE_VALUATION",
    "RELATIVE_VALUATION",
    "EMBEDDED_EXPECTATION",
    "CONTRACT_PRICE",
    "CAPACITY_OR_EARNINGS",
    "MARKET_PRICE",
}

READY = "READY_FOR_SCREENING"
EVIDENCE_BACKED = "EVIDENCE_BACKED"
BLOCKED_ORIGIN = "BLOCKED_ORIGIN_CRUX"
BLOCKED_ROOT = "BLOCKED_ROOT_UNCONVERGED"
NEEDS_CATALYST = "NEEDS_CATALYST_CHECK"
OUT_OF_HORIZON = "OUT_OF_HORIZON_LEAD"
WATCHLIST = "WATCHLIST"
REJECTED = "REJECTED"
THESIS_CANDIDATE = "THESIS_CANDIDATE"
VERIFIED_FOR_HUMAN = "VERIFIED_FOR_HUMAN"


def _text(value):
    return " ".join(str(value or "").split())


def _norm(value):
    return re.sub(r"[^\w一-龥]+", "", _text(value).lower())


def _ticker(value):
    return re.sub(r"\s+", "", _text(value).upper())


def _seed_key(seed):
    identity = _ticker(seed.get("ticker")) or _norm(seed.get("candidate"))
    return "|".join((
        identity,
        seed.get("relation_type", ""),
        seed.get("origin_crux", ""),
        seed.get("landscape_path_id") or "",
    ))


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


def _hypothesis_binding_issues(state, hypothesis_id, origin_crux):
    """Validate optional exploration lineage without granting promotion rights."""
    hypothesis_id = _text(hypothesis_id)
    if not hypothesis_id:
        return []
    ledger = state.get("hypothesis_ledger")
    hypotheses = ledger.get("hypotheses", []) if isinstance(ledger, dict) else []
    hypothesis = next(
        (
            item for item in hypotheses
            if isinstance(item, dict) and _text(item.get("hypothesis_id")) == hypothesis_id
        ),
        None,
    )
    if hypothesis is None:
        return ["unknown_origin_hypothesis"]
    context = hypothesis.get("context") or {}
    linked_cruxes = {
        _text(value)
        for value in (
            *(context.get("origin_cruxes") or []),
            context.get("origin_crux"),
        )
        if _text(value)
    }
    if linked_cruxes and origin_crux not in linked_cruxes:
        return ["origin_hypothesis_crux_mismatch"]
    return []


def _normalize_seed(raw, state, agent_name, round_num, allowed, audit):
    if not isinstance(raw, dict):
        _reason(audit, "seed_not_object")
        return None

    candidate = _text(raw.get("candidate"))
    relation = _text(raw.get("relation_type")).upper()
    origin = _text(raw.get("origin_crux"))
    origin_hypothesis_id = _text(raw.get("origin_hypothesis_id"))
    landscape_path_id = _text(raw.get("landscape_path_id"))
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
    hypothesis_issues = _hypothesis_binding_issues(
        state, origin_hypothesis_id, origin
    )
    if hypothesis_issues:
        for reason in hypothesis_issues:
            _reason(audit, reason)
        return None
    binding_issues = landscape_engine.seed_binding_issues(
        state, landscape_path_id, origin
    )
    if binding_issues:
        for reason in binding_issues:
            _reason(audit, reason)
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
        "origin_hypothesis_id": origin_hypothesis_id or None,
        "landscape_path_id": landscape_path_id or None,
        "causal_path": causal_path,
        "economic_exposure": _text(raw.get("economic_exposure")),
        "why_market_may_miss": _text(raw.get("why_market_may_miss")),
        "pricing_anchor": _normalize_pricing_anchor(raw.get("pricing_anchor"), accepted),
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


def _normalize_pricing_anchor(value, evidence=None):
    if not isinstance(value, dict):
        return {}
    as_of_date = _text(value.get("as_of_date"))
    try:
        if as_of_date:
            date.fromisoformat(as_of_date)
    except ValueError:
        as_of_date = ""
    anchor_type = _text(value.get("anchor_type")).upper()
    if anchor_type not in PRICING_ANCHOR_TYPES:
        anchor_type = ""
    source_url = _text(value.get("source_url"))
    evidence_urls = {
        crux_engine.citation_source_identity(item)
        for item in evidence or [] if crux_engine.valid_citation(item)
    }
    source_identity = crux_engine.citation_source_identity({
        "claim": value.get("source_claim") or "pricing anchor",
        "source": value.get("source") or "pricing anchor source",
        "date": as_of_date,
        "url": source_url,
    }) if source_url and as_of_date else ""
    if evidence is not None and source_identity not in evidence_urls:
        source_url = ""
    normalized = {
        "as_of_date": as_of_date,
        "anchor_type": anchor_type,
        "metric": _text(value.get("metric")),
        "current_value": _text(value.get("current_value")),
        "comparison_value": _text(value.get("comparison_value")),
        "source": _text(value.get("source")),
        "source_url": source_url,
        "source_claim": _text(value.get("source_claim")),
    }
    return normalized if any(normalized.values()) else {}


def pricing_anchor_blockers(seed):
    anchor = seed.get("pricing_anchor")
    if not isinstance(anchor, dict) or not anchor:
        return ["missing_structured_pricing_anchor"]
    blockers = []
    required = {
        "as_of_date": "pricing_anchor_missing_as_of",
        "anchor_type": "pricing_anchor_missing_type",
        "metric": "pricing_anchor_missing_metric",
        "current_value": "pricing_anchor_missing_current_value",
        "comparison_value": "pricing_anchor_missing_comparison_value",
        "source": "pricing_anchor_missing_source",
        "source_url": "pricing_anchor_missing_source_url",
        "source_claim": "pricing_anchor_missing_source_claim",
    }
    for field, reason in required.items():
        if not _text(anchor.get(field)):
            blockers.append(reason)
    if _text(anchor.get("anchor_type")).upper() not in PRICING_ANCHOR_TYPES:
        blockers.append("pricing_anchor_invalid_type")
    try:
        date.fromisoformat(_text(anchor.get("as_of_date")))
    except ValueError:
        blockers.append("pricing_anchor_invalid_as_of")
    if not crux_engine.is_concrete_url(_text(anchor.get("source_url"))):
        blockers.append("pricing_anchor_invalid_source_url")
    evidence_urls = {
        crux_engine.citation_source_identity(item)
        for item in seed.get("evidence", []) if crux_engine.valid_citation(item)
    }
    anchor_identity = ""
    if crux_engine.is_concrete_url(_text(anchor.get("source_url"))):
        anchor_identity = crux_engine.citation_source_identity({
            "claim": anchor.get("source_claim") or "pricing anchor",
            "source": anchor.get("source") or "pricing anchor source",
            "date": anchor.get("as_of_date"),
            "url": anchor.get("source_url"),
        })
    if anchor_identity and anchor_identity not in evidence_urls:
        blockers.append("pricing_anchor_source_not_seed_evidence")
    return blockers


def pricing_anchor_text(anchor):
    if not isinstance(anchor, dict) or not anchor:
        return "—"
    return (
        f"{_text(anchor.get('metric'))}: {_text(anchor.get('current_value'))} vs "
        f"{_text(anchor.get('comparison_value'))} | {_text(anchor.get('anchor_type'))} | "
        f"as-of {_text(anchor.get('as_of_date'))} | {_text(anchor.get('source'))} "
        f"{_text(anchor.get('source_url'))}"
    )


def effective_seed(state, seed):
    """Project immutable seed + verified append-only evidence supplements."""
    projected = copy.deepcopy(seed) if isinstance(seed, dict) else {}
    evidence = [
        copy.deepcopy(item)
        for item in projected.get("evidence", [])
        if crux_engine.valid_citation(item)
    ]
    seen = {crux_engine.citation_identity(item) for item in evidence}
    task_map = {
        str(task.get("task_id") or ""): task
        for task in state.get("candidate_gap_tasks", [])
        if isinstance(task, dict)
    } if isinstance(state, dict) else {}
    completed_supplements = {
        str(item.get("last_supplement_id") or "")
        for item in state.get("candidate_gap_resolutions", [])
        if isinstance(item, dict) and item.get("status") == "COMPLETED"
    } if isinstance(state, dict) else set()
    supplement_ids = []
    for item in state.get("candidate_evidence_supplements", []) if isinstance(state, dict) else []:
        if not isinstance(item, dict) or item.get("seed_id") != projected.get("seed_id"):
            continue
        task = task_map.get(str(item.get("task_id") or ""))
        if not task or task.get("seed_id") != projected.get("seed_id"):
            continue
        if item.get("origin_crux") != projected.get("origin_crux"):
            continue
        if item.get("claim_alignment") != "SUPPORTED":
            continue
        if str(item.get("supplement_id") or "") not in completed_supplements:
            continue
        citation = item.get("citation")
        key = crux_engine.citation_identity(citation) if isinstance(citation, dict) else ""
        if key and key not in seen and crux_engine.valid_citation(citation):
            evidence.append(copy.deepcopy(citation))
            seen.add(key)
        additions = item.get("field_additions")
        for field, value in (
            additions.items() if isinstance(additions, dict) else []
        ):
            if field in {
                "economic_exposure", "why_market_may_miss", "pricing_anchor",
                "catalyst", "catalyst_window", "falsifier",
            }:
                existing = projected.get(field)
                if field in {"pricing_anchor", "catalyst_window"} and isinstance(value, dict):
                    merged = copy.deepcopy(existing) if isinstance(existing, dict) else {}
                    for key, nested_value in value.items():
                        if merged.get(key) in (None, "", {}):
                            merged[key] = copy.deepcopy(nested_value)
                    projected[field] = merged
                elif existing in (None, "", {}):
                    projected[field] = copy.deepcopy(value)
        if item.get("supplement_id"):
            supplement_ids.append(item["supplement_id"])
    projected["evidence"] = evidence
    projected["evidence_supplement_ids"] = supplement_ids
    return projected


def _candidate_gap_blockers(state, seed_id):
    blockers = []
    tasks = {
        str(task.get("task_id") or ""): task
        for task in state.get("candidate_gap_tasks", [])
        if isinstance(task, dict) and task.get("seed_id") == seed_id
    }
    for item in state.get("candidate_evidence_supplements", []):
        if not isinstance(item, dict) or item.get("seed_id") != seed_id:
            continue
        if item.get("claim_alignment") == "CONTRADICTED":
            blockers.append("candidate_evidence_contradicted")
    for item in state.get("candidate_gap_resolutions", []):
        if not isinstance(item, dict) or item.get("task_id") not in tasks:
            continue
        if item.get("status") == "SOURCE_EXHAUSTED":
            blockers.append("candidate_gap_source_exhausted")
        elif item.get("status") == "WAITING_EVENT":
            blockers.append("candidate_gap_waiting_event")
    return list(dict.fromkeys(blockers))


def evidence_maturity(seed, state=None):
    seed = effective_seed(state, seed) if isinstance(state, dict) else seed
    sources = {
        _source_organization(c)
        for c in seed.get("evidence", [])
        if crux_engine.valid_citation(c) and _source_organization(c)
    }
    if len(sources) >= 2 and not seed_contract_blockers(seed):
        return READY
    return EVIDENCE_BACKED


def seed_contract_blockers(seed):
    """Return deterministic fields missing before CandidateScreen dispatch."""
    blockers = []
    required = {
        "economic_exposure": "missing_economic_exposure",
        "why_market_may_miss": "missing_expectation_gap",
        "catalyst": "missing_catalyst",
        "falsifier": "missing_falsifier",
    }
    for field, reason in required.items():
        if not _text(seed.get(field)):
            blockers.append(reason)
    blockers.extend(pricing_anchor_blockers(seed))
    window = seed.get("catalyst_window")
    window = window if isinstance(window, dict) else {}
    if not (_text(window.get("event")) and _text(window.get("expected_by"))
            and _text(window.get("date_status")).upper() in {
                "REVIEW_CHECKPOINT", "DATE_CLAIMED_UNVERIFIED"
            }):
        blockers.append("catalyst_window_incomplete")
    return blockers


def maturity(seed):
    """Compatibility projection: evidence maturity only, never screen eligibility."""
    return evidence_maturity(seed)


def _origin_gate(state, seed):
    origin = state.get("cruxes", {}).get(seed.get("origin_crux"))
    if not isinstance(origin, dict):
        return ["origin_crux_missing"]
    blockers = []
    blockers.extend(landscape_engine.seed_readiness_blockers(state, seed))
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
    effective = effective_seed(state, seed)
    evidence_state = evidence_maturity(effective)
    blockers = []
    if evidence_state != READY:
        seed_blockers = seed_contract_blockers(effective)
        sources = {
            _source_organization(c)
            for c in effective.get("evidence", [])
            if crux_engine.valid_citation(c) and _source_organization(c)
        }
        if len(sources) < 2:
            seed_blockers.append("insufficient_independent_seed_sources")
        seed_blockers.extend(_candidate_gap_blockers(state, seed.get("seed_id")))
        return {
            "evidence_maturity": evidence_state,
            "screening_status": EVIDENCE_BACKED,
            "blockers": list(dict.fromkeys(seed_blockers or ["seed_evidence_incomplete"])),
            "origin_status": state.get("cruxes", {}).get(seed.get("origin_crux"), {}).get("status"),
        }
    gap_blockers = _candidate_gap_blockers(state, seed.get("seed_id"))
    if gap_blockers:
        return {
            "evidence_maturity": evidence_state,
            "screening_status": EVIDENCE_BACKED,
            "blockers": gap_blockers,
            "origin_status": state.get("cruxes", {}).get(seed.get("origin_crux"), {}).get("status"),
        }
    origin_blockers = _origin_gate(state, effective)
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
    catalyst_state, catalyst_blockers = _catalyst_gate(state, effective)
    return {
        "evidence_maturity": evidence_state,
        "screening_status": catalyst_state,
        "blockers": catalyst_blockers,
        "origin_status": state.get("cruxes", {}).get(seed.get("origin_crux"), {}).get("status"),
    }


def _source_organization(citation):
    return crux_engine.citation_publisher_identity(citation) if isinstance(citation, dict) else ""


def _latest_screen(state, seed_id):
    latest = None
    for screen in state.get("candidate_screens", []):
        if not isinstance(screen, dict) or screen.get("seed_id") != seed_id:
            continue
        order = (str(screen.get("as_of_date") or ""), str(screen.get("screen_id") or ""))
        current = (
            str((latest or {}).get("as_of_date") or ""),
            str((latest or {}).get("screen_id") or ""),
        )
        if latest is None or order >= current:
            latest = screen
    return latest


def candidate_state(state, seed):
    """Project one non-inheritable candidate maturity state from engine evidence."""
    screen = _latest_screen(state, seed.get("seed_id"))
    if screen:
        screen_status = _text(screen.get("status")).upper()
        if screen_status == THESIS_CANDIDATE:
            packet = screen.get("promotion_packet") or {}
            if (screen.get("claim_verification_status") == "VERIFIED"
                    and packet.get("status") == "DRAFT_REQUIRES_HUMAN"):
                return VERIFIED_FOR_HUMAN
            return THESIS_CANDIDATE
        if screen_status in {WATCHLIST, REJECTED}:
            return screen_status
    assessment = assess_seed(state, seed)
    if assessment["screening_status"] == READY:
        return READY
    return EVIDENCE_BACKED


def promotion_assessment(state, seed):
    """Return the only cross-system Thesis-promotion contract."""
    state_name = candidate_state(state, seed)
    screen = _latest_screen(state, seed.get("seed_id"))
    blockers = list(seed_contract_blockers(effective_seed(state, seed)))
    if state_name == EVIDENCE_BACKED:
        blockers.extend(assess_seed(state, seed).get("blockers", []))
    elif state_name == READY:
        blockers.append("candidate_screen_required")
    elif state_name == WATCHLIST:
        blockers.append("candidate_screen_watchlist")
        blockers.extend((screen or {}).get("gaps", []))
    elif state_name == REJECTED:
        blockers.append("candidate_screen_rejected")
        blockers.extend((screen or {}).get("critical_rejections", []))
    elif state_name == THESIS_CANDIDATE:
        claim_status = (screen or {}).get("claim_verification_status", "PENDING")
        blockers.append(f"claim_verification_{str(claim_status).lower()}")
        blockers.extend((screen or {}).get("claim_verification_gaps", []))
        blockers.extend((screen or {}).get("claim_contradictions", []))
    if screen and screen.get("isolation_status") != "verified":
        blockers.append("candidate_screen_isolation_unverified")
    eligible = state_name == VERIFIED_FOR_HUMAN and not blockers
    if state_name == VERIFIED_FOR_HUMAN and not eligible:
        blockers.append("verified_candidate_contract_incomplete")
    return {
        "candidate_state": state_name,
        "promotion_eligibility": "VERIFIED_FOR_HUMAN" if eligible else "BLOCKED",
        "eligible": eligible,
        "blocking_reasons": list(dict.fromkeys(str(item) for item in blockers if item)),
        "screen_id": (screen or {}).get("screen_id"),
        "claim_verification_status": (screen or {}).get("claim_verification_status", "NOT_APPLICABLE"),
    }


def refresh_candidate_states(state):
    """Materialize current projections for portable artifacts without trusting LLM labels."""
    for seed in state.get("opportunity_seeds", []):
        if not isinstance(seed, dict) or not seed.get("seed_id"):
            continue
        promotion = promotion_assessment(state, seed)
        seed["maturity"] = evidence_maturity(seed, state)
        seed["candidate_state"] = promotion["candidate_state"]
        seed["promotion_eligibility"] = promotion["promotion_eligibility"]
        seed["promotion_blockers"] = promotion["blocking_reasons"]
    return state


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
            -len(effective_seed(state, item[0]).get("evidence", [])),
            item[0].get("first_seen_round", 0),
            item[0].get("seed_id", ""),
        ))
        representative_raw, assessment = assessed[0]
        representative = effective_seed(state, representative_raw)
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
                    "origin_hypothesis_id": seed.get("origin_hypothesis_id"),
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

    incoming_hypothesis = _text(incoming.get("origin_hypothesis_id"))
    existing_hypothesis = _text(existing.get("origin_hypothesis_id"))
    if incoming_hypothesis and not existing_hypothesis:
        existing["origin_hypothesis_id"] = incoming_hypothesis
    elif incoming_hypothesis and incoming_hypothesis != existing_hypothesis:
        variants = existing.setdefault("field_variants", {}).setdefault(
            "origin_hypothesis_id", []
        )
        for item in (existing_hypothesis, incoming_hypothesis):
            if item and item not in variants:
                variants.append(item)
        variants.sort()

    incoming_window = incoming.get("catalyst_window")
    current_window = existing.get("catalyst_window")
    if incoming_window and not current_window:
        existing["catalyst_window"] = incoming_window
    elif incoming_window and incoming_window != current_window:
        variants = existing.setdefault("field_variants", {}).setdefault("catalyst_window", [])
        for item in (current_window, incoming_window):
            if item and item not in variants:
                variants.append(item)

    incoming_anchor = incoming.get("pricing_anchor")
    current_anchor = existing.get("pricing_anchor")
    if incoming_anchor and not current_anchor:
        existing["pricing_anchor"] = incoming_anchor
    elif incoming_anchor and incoming_anchor != current_anchor:
        variants = existing.setdefault("field_variants", {}).setdefault("pricing_anchor", [])
        for item in (current_anchor, incoming_anchor):
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
    refresh_candidate_states(state)
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
