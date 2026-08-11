#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lightweight discovery projection from a theme to concrete market carriers.

CandidateMap is intentionally not a lifecycle or promotion engine.  It accepts
explicitly labelled, concrete instruments early, keeps uncertainty visible, and
orders research attention by setup completeness.  It never estimates expected
return, recommends a trade, or mutates Thesis/Decision/order state.
"""
import copy
import hashlib
import re
from urllib.parse import urlparse

import crux_engine
import market_bridge_engine
import research_kernel


ASSET_TYPES = {
    "LISTED_EQUITY",
    "PRIVATE_COMPANY",
    "COMMODITY",
    "TECHNOLOGY",
    "OTHER",
}

MARKET_ROLES = {
    "EVENT_BETA",
    "ECONOMIC_CAPTURE",
    "BOTTLENECK",
    "SECOND_ORDER",
    "SUBSTITUTE",
    "FAILURE_HEDGE",
    "WATCH_ONLY",
}

SETUP_TYPES = {"EVENT_SETUP", "ECONOMIC_SETUP"}

COVERAGE_FIELDS = (
    "concrete_instrument_search",
    "alternative_paths",
    "price_and_crowding",
    "event_window",
)

COVERAGE_OUTCOMES = {"FOUND", "NO_RESULT", "INSUFFICIENT"}

# Search fields say *what was checked*; route kinds say *which causal branch of
# the opportunity universe was actually constructed*.  Both are projections
# over bounded research, not lifecycle states.
COVERAGE_ROUTE_KINDS = {
    "ECONOMIC_CHAIN",
    "MARKET_CARRIER",
    "COMPETITOR_OR_SUBSTITUTE",
    "FAILURE_OR_ADVERSE",
    "OWNERSHIP_OR_CAPITAL",
}
REQUIRED_COVERAGE_ROUTE_KINDS = tuple(sorted(COVERAGE_ROUTE_KINDS))

MECHANICS_FIELDS = (
    "event_change",
    "narrative",
    "capital_flow",
    "carrier_selection",
    "crowding_path",
    "realization_path",
    "strongest_alternative",
)

CANDIDATE_TEXT_FIELDS = (
    "candidate", "economic_exposure", "mechanism", "catalyst", "invalidation",
    "price_or_expectation", "crowding_or_position",
    "strongest_alternative_explanation", "cheap_discriminating_test",
)
FIELD_UPDATE_MODES = {"REFINE", "REPLACE", "CHALLENGE"}
MAX_CANDIDATES_TOTAL = 12
MAX_NEW_CANDIDATES_FIRST_ROUND_PER_ROLE = 6
MAX_NEW_CANDIDATES_LATER_ROUND_PER_ROLE = 1


def _state_as_of(state):
    return _text(
        state.get("frame_contract", {}).get("as_of_date")
        or state.get("research_agenda", {}).get("as_of_date")
    )


def _text(value):
    return " ".join(str(value or "").split())


def _ticker(value):
    return re.sub(r"\s+", "", _text(value).upper())


def _norm(value):
    return re.sub(r"[^\w一-龥]+", "", _text(value).lower())


def _identity(item):
    return research_kernel.instrument_identity(item)


def _candidate_id(identity):
    return "CM-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10].upper()


def _evidence(items, as_of_date=""):
    accepted = []
    rejected = []
    for item in items if isinstance(items, list) else []:
        normalized, reason = research_kernel.normalize_evidence(
            item, as_of_date
        )
        if reason:
            rejected.append(reason)
            continue
        accepted.append(normalized)
    return research_kernel.unique_evidence(accepted), rejected


def _evidence_boundary(evidence, mapping_is_inference=False):
    return research_kernel.evidence_boundary(
        evidence, is_inference=mapping_is_inference
    )


def _known(value):
    return research_kernel.known(value)


def _normalize_coverage_route(raw):
    """Keep zero-setup coverage inspectable without inventing another state."""
    if not isinstance(raw, dict):
        return None, "coverage_route_must_be_object"
    field = _text(raw.get("coverage_field"))
    if field not in COVERAGE_FIELDS:
        return None, "invalid_coverage_field"
    query = _text(raw.get("query"))
    if not query:
        return None, "coverage_query_required"
    outcome = _text(raw.get("outcome")).upper()
    if outcome not in COVERAGE_OUTCOMES:
        return None, "invalid_coverage_outcome"
    route_kind = _text(raw.get("route_kind")).upper()
    if route_kind not in COVERAGE_ROUTE_KINDS:
        return None, "invalid_or_missing_coverage_route_kind"
    urls = raw.get("checked_urls")
    if not isinstance(urls, list) or not urls:
        return None, "coverage_checked_url_required"
    checked_urls = []
    for value in urls:
        url = _text(value)
        parsed = urlparse(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not crux_engine.is_concrete_url(url)
        ):
            return None, "invalid_coverage_checked_url"
        if url not in checked_urls:
            checked_urls.append(url)
    return {
        "coverage_field": field,
        "route_kind": route_kind,
        "query": query,
        "checked_urls": checked_urls,
        "outcome": outcome,
    }, None


def _attention_band(item):
    return research_kernel.evaluate_setup(
        item, item.get("evidence_as_of_date", "")
    )["attention_band"]


def _normalize_candidate(
    raw, role, round_num, as_of_date="", evidence_items=None,
    require_canonical_field_evidence=False, evidence_aliases=None, state=None,
):
    if not isinstance(raw, dict):
        return None, "candidate_must_be_object"
    candidate = _text(raw.get("candidate"))
    if not candidate:
        return None, "candidate_identity_required"
    asset_type = _text(raw.get("asset_type") or "OTHER").upper()
    if asset_type not in ASSET_TYPES:
        return None, "invalid_asset_type"
    instrument, reason = research_kernel.normalize_instrument_identity(
        asset_type, raw.get("ticker"), raw.get("exchange")
    )
    if reason:
        return None, reason
    market_role = _text(raw.get("market_role") or "WATCH_ONLY").upper()
    if market_role not in MARKET_ROLES:
        return None, "invalid_market_role"
    mechanism = _text(raw.get("mechanism") or raw.get("causal_path"))
    if not mechanism:
        return None, "mechanism_required"
    declared_setups = raw.get("setup_types")
    if not isinstance(declared_setups, list):
        declared_setups = [raw.get("setup_type")] if raw.get("setup_type") else []
    setup_types = sorted({
        _text(value).upper() for value in declared_setups
        if _text(value).upper() in SETUP_TYPES
    })
    evidence, evidence_rejections = _evidence(
        raw.get("evidence"), as_of_date
    )
    inline_field_evidence, inline_field_evidence_rejections = (
        research_kernel.normalize_field_evidence(
            raw.get("field_evidence"), as_of_date
        )
    )
    field_values = {
        "mechanism": mechanism,
        "economic_exposure": _text(raw.get("economic_exposure")),
        "catalyst": _text(raw.get("catalyst")),
        "price_or_expectation": _text(
            raw.get("price_or_expectation") or raw.get("why_market_may_miss")
        ),
        "crowding_or_position": _text(raw.get("crowding_or_position")),
    }
    mapping_is_inference = bool(raw.get("mapping_is_inference"))
    raw_field_update_modes = (
        raw.get("field_update_modes")
        if isinstance(raw.get("field_update_modes"), dict)
        else {}
    )
    (
        canonical_field_evidence,
        field_evidence_ids,
        field_evidence_checks,
        canonical_field_rejections,
    ) = research_kernel.resolve_field_evidence_ids(
        raw.get("field_evidence_ids"),
        evidence_items or [],
        field_values,
        mapping_is_inference=mapping_is_inference,
        evidence_aliases=evidence_aliases,
    )
    has_canonical_bindings = any(field_evidence_ids.values())
    if require_canonical_field_evidence:
        field_evidence = canonical_field_evidence
        field_evidence_rejections = list(canonical_field_rejections)
        if any(inline_field_evidence.values()):
            field_evidence_rejections.append({
                "field": "*",
                "reason": "INLINE_FIELD_EVIDENCE_NOT_CANONICAL",
            })
    elif has_canonical_bindings:
        field_evidence = canonical_field_evidence
        field_evidence_rejections = list(canonical_field_rejections)
    else:
        field_evidence = inline_field_evidence
        field_evidence_rejections = list(inline_field_evidence_rejections)
    evidence = research_kernel.unique_evidence(
        evidence
        + [
            item
            for field in research_kernel.FIELD_EVIDENCE_NAMES
            for item in field_evidence.get(field, [])
        ]
    )
    item = {
        "candidate": candidate,
        "ticker": instrument.get("ticker", ""),
        "exchange": instrument.get("exchange", ""),
        "asset_type": asset_type,
        "market_role": market_role,
        "market_roles": [market_role],
        "setup_types": setup_types,
        "mechanism": mechanism,
        "economic_exposure": field_values["economic_exposure"],
        "catalyst": field_values["catalyst"],
        "catalyst_window": copy.deepcopy(
            raw.get("catalyst_window")
            if isinstance(raw.get("catalyst_window"), dict)
            else {}
        ),
        "invalidation": _text(raw.get("invalidation") or raw.get("falsifier")),
        "price_or_expectation": field_values["price_or_expectation"],
        "crowding_or_position": field_values["crowding_or_position"],
        "strongest_alternative_explanation": _text(
            raw.get("strongest_alternative_explanation")
        ),
        "cheap_discriminating_test": _text(raw.get("cheap_discriminating_test")),
        "scenario_fit": copy.deepcopy(
            raw.get("scenario_fit")
            if isinstance(raw.get("scenario_fit"), dict)
            else raw.get("scenario_paths")
            if isinstance(raw.get("scenario_paths"), dict)
            else {}
        ),
        "mapping_is_inference": mapping_is_inference,
        "evidence": evidence,
        "field_evidence": field_evidence,
        "field_evidence_ids": field_evidence_ids,
        "field_evidence_checks": field_evidence_checks,
        "evidence_boundary": _evidence_boundary(
            field_evidence.get("mechanism", []), mapping_is_inference
        ),
        "evidence_rejections": evidence_rejections + field_evidence_rejections,
        "evidence_as_of_date": _text(as_of_date),
        "source_agents": [role],
        "first_seen_round": int(round_num),
        "last_seen_round": int(round_num),
        "field_variants": {},
        "field_conflicts": {},
        "field_update_modes": {
            field: (
                _text(raw_field_update_modes.get(field)).upper()
                if _text(raw_field_update_modes.get(field)).upper()
                in FIELD_UPDATE_MODES
                else "REFINE"
            )
            for field in CANDIDATE_TEXT_FIELDS
        },
        "field_history": {
            field: [{
                "round": int(round_num),
                "role": role,
                "mode": (
                    _text(raw_field_update_modes.get(field)).upper()
                    if _text(raw_field_update_modes.get(field)).upper()
                    in FIELD_UPDATE_MODES
                    else "REFINE"
                ),
                "value": _text(field_values.get(field) if field in field_values else raw.get(field)),
            }]
            for field in CANDIDATE_TEXT_FIELDS
            if _text(field_values.get(field) if field in field_values else raw.get(field))
        },
    }
    identity = _identity(item)
    if identity.endswith("|NAME|"):
        return None, "candidate_identity_required"
    item["candidate_map_id"] = _candidate_id(identity)
    readiness = research_kernel.evaluate_setup(item, as_of_date)
    item.update(readiness)
    item["bridge"] = market_bridge_engine.normalize_candidate_bridge(
        state or {}, raw.get("bridge"), role, item
    )
    return item, None


def _field_value_rank(item, field):
    return (
        int(item.get("last_seen_round", 0) or 0),
        len((item.get("field_evidence_ids") or {}).get(field, [])),
        len(_text(item.get(field))),
        _norm(item.get(field)),
    )


def _merge_text(existing, incoming, field):
    new_value = _text(incoming.get(field))
    old_value = _text(existing.get(field))
    if not new_value:
        return
    mode = _text(
        (incoming.get("field_update_modes") or {}).get(field)
    ).upper()
    if mode not in FIELD_UPDATE_MODES:
        mode = "REFINE"
    history = existing.setdefault("field_history", {}).setdefault(field, [])
    for record in (incoming.get("field_history") or {}).get(field, []):
        if isinstance(record, dict) and record not in history:
            history.append(copy.deepcopy(record))
    if not old_value:
        existing[field] = new_value
        return
    if old_value == new_value:
        return
    if mode == "CHALLENGE":
        conflicts = existing.setdefault("field_conflicts", {}).setdefault(field, [])
        variants = existing.setdefault("field_variants", {}).setdefault(field, [])
        for values in (conflicts, variants):
            for value in (old_value, new_value):
                if value not in values:
                    values.append(value)
        return
    if mode == "REPLACE":
        existing[field] = new_value
        existing.setdefault("field_conflicts", {}).pop(field, None)
        existing.setdefault("field_variants", {}).pop(field, None)
        return
    # REFINE means a newer or better-supported snapshot, not a contradiction.
    # The tuple makes same-round role order irrelevant.
    if _field_value_rank(incoming, field) > _field_value_rank(existing, field):
        existing[field] = new_value


def _merge_candidate(existing, incoming):
    previous_round = int(existing.get("last_seen_round", 0) or 0)
    for field in CANDIDATE_TEXT_FIELDS:
        _merge_text(existing, incoming, field)
    existing["market_roles"] = sorted(set(
        existing.get("market_roles", []) + incoming.get("market_roles", [])
    ))
    existing["setup_types"] = sorted(set(
        existing.get("setup_types", []) + incoming.get("setup_types", [])
    ))
    existing["source_agents"] = sorted(set(
        existing.get("source_agents", []) + incoming.get("source_agents", [])
    ))
    existing["last_seen_round"] = max(
        int(existing.get("last_seen_round", 0) or 0),
        int(incoming.get("last_seen_round", 0) or 0),
    )
    incoming_catalyst_mode = _text(
        (incoming.get("field_update_modes") or {}).get("catalyst")
    ).upper()
    if incoming.get("catalyst_window") and (
        not existing.get("catalyst_window")
        or int(incoming.get("last_seen_round", 0) or 0) > previous_round
        or incoming_catalyst_mode == "REPLACE"
    ):
        existing["catalyst_window"] = copy.deepcopy(incoming["catalyst_window"])
    for key, value in incoming.get("scenario_fit", {}).items():
        if _known(value) and key not in existing.setdefault("scenario_fit", {}):
            existing["scenario_fit"][key] = copy.deepcopy(value)
    existing["evidence"] = research_kernel.unique_evidence(
        existing.get("evidence", []) + incoming.get("evidence", [])
    )
    field_evidence = existing.setdefault("field_evidence", {})
    for field in research_kernel.FIELD_EVIDENCE_NAMES:
        field_evidence[field] = research_kernel.unique_evidence(
            field_evidence.get(field, [])
            + incoming.get("field_evidence", {}).get(field, [])
        )
    field_evidence_ids = existing.setdefault("field_evidence_ids", {})
    for field in research_kernel.FIELD_EVIDENCE_NAMES:
        field_evidence_ids[field] = list(dict.fromkeys(
            field_evidence_ids.get(field, [])
            + incoming.get("field_evidence_ids", {}).get(field, [])
        ))
    known_checks = {
        (item.get("field"), item.get("evidence_id"), item.get("reason"))
        for item in existing.setdefault("field_evidence_checks", [])
        if isinstance(item, dict)
    }
    for check in incoming.get("field_evidence_checks", []):
        key = (check.get("field"), check.get("evidence_id"), check.get("reason"))
        if key not in known_checks:
            existing["field_evidence_checks"].append(copy.deepcopy(check))
            known_checks.add(key)
    existing.setdefault("evidence_rejections", []).extend(
        incoming.get("evidence_rejections", [])
    )
    existing["mapping_is_inference"] = bool(
        existing.get("mapping_is_inference") or incoming.get("mapping_is_inference")
    )
    existing["evidence_boundary"] = _evidence_boundary(
        field_evidence.get("mechanism", []), existing["mapping_is_inference"]
    )
    existing["bridge"] = market_bridge_engine.merge_candidate_bridge(
        existing.get("bridge", {}), incoming.get("bridge", {})
    )
    readiness = research_kernel.evaluate_setup(
        existing, existing.get("evidence_as_of_date", "")
    )
    existing.update(readiness)


def _candidate_gap_fields(item):
    gaps = set()
    for check in (item.get("setup_checks") or {}).values():
        if not isinstance(check, dict):
            continue
        gaps.update(check.get("missing_content", []))
        gaps.update(check.get("missing_evidence", []))
        gaps.update(check.get("conflicting_fields", []))
        if "INVALID_OR_STALE_CATALYST_WINDOW" in check.get("reason_codes", []):
            gaps.add("catalyst_window")
    bridge = item.get("bridge") if isinstance(item.get("bridge"), dict) else {}
    gaps.update(bridge.get("issues", []))
    if not bridge.get("value_path_ids"):
        gaps.add("value_path")
    if not bridge.get("horizon_fit"):
        gaps.add("horizon_comparison")
    if not _known(bridge.get("why_prefer_now")):
        gaps.add("why_prefer_now")
    if not _known(bridge.get("switch_condition")):
        gaps.add("switch_condition")
    return sorted(gaps)


def focus_candidates(state, limit=4):
    """Return a bounded completion queue, not a candidate ranking."""
    candidate_map = _ensure_map(state)
    rows = []
    boundary_rank = {"FACT": 0, "SINGLE_SOURCE": 1, "INFERENCE": 2, "HYPOTHESIS": 3}
    for item in candidate_map.get("candidates", []):
        if not isinstance(item, dict):
            continue
        gaps = _candidate_gap_fields(item)
        if not gaps:
            continue
        bridge = item.get("bridge") if isinstance(item.get("bridge"), dict) else {}
        economic = bridge.get("economic_exposure_strength", {}).get(
            "effective", "UNKNOWN"
        )
        recognition = bridge.get("market_recognition", {}).get(
            "effective", "UNKNOWN"
        )
        key = (
            {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNKNOWN": 3}.get(economic, 4),
            {"LEADER": 0, "CONFIRMED": 1, "EMERGING": 2,
             "WEAK": 3, "UNKNOWN": 4}.get(recognition, 5),
            len(gaps),
            boundary_rank.get(item.get("evidence_boundary"), 9),
            item.get("ticker") or item.get("candidate") or "",
        )
        rows.append((key, {
            "candidate_map_id": item.get("candidate_map_id"),
            "candidate": item.get("candidate"),
            "ticker": item.get("ticker"),
            "exchange": item.get("exchange"),
            "market_roles": copy.deepcopy(item.get("market_roles", [])),
            "setup_types": copy.deepcopy(item.get("setup_types", [])),
            "current_fields": {
                field: copy.deepcopy(item.get(field))
                for field in CANDIDATE_TEXT_FIELDS
                if field != "candidate"
            },
            "bridge": copy.deepcopy(bridge),
            "research_focus": gaps,
        }))
    rows.sort(key=lambda row: row[0])
    return [copy.deepcopy(item) for _, item in rows[:max(0, int(limit))]]


def _legacy_seed_candidate(seed):
    """Project an already-admitted OpportunitySeed into the discovery map."""
    relation_to_role = {
        "DIRECT_WINNER": "ECONOMIC_CAPTURE",
        "SUBSTITUTE_WINNER": "SUBSTITUTE",
        "COMPETITOR_WINNER": "SUBSTITUTE",
        "BOTTLENECK_OWNER": "BOTTLENECK",
        "INFRA_ASSET_OWNER": "SECOND_ORDER",
        "SECOND_ORDER": "SECOND_ORDER",
        "SHORT_CANDIDATE": "FAILURE_HEDGE",
    }
    legacy_asset_type = seed.get("asset_type")
    _, identity_reason = research_kernel.normalize_instrument_identity(
        legacy_asset_type, seed.get("ticker"), seed.get("exchange")
    )
    # Archived OpportunitySeeds predate exchange-qualified identity. Preserve
    # the named research lead, but do not misrepresent an unqualified symbol as
    # a currently validated listed-equity identity.
    if legacy_asset_type == "LISTED_EQUITY" and identity_reason:
        legacy_asset_type = "OTHER"
    raw = {
        "candidate": seed.get("candidate"),
        "ticker": seed.get("ticker"),
        "exchange": seed.get("exchange"),
        "asset_type": legacy_asset_type,
        "market_role": relation_to_role.get(seed.get("relation_type"), "WATCH_ONLY"),
        "setup_types": ["ECONOMIC_SETUP"],
        "mechanism": seed.get("causal_path"),
        "economic_exposure": seed.get("economic_exposure"),
        "catalyst": seed.get("catalyst"),
        "catalyst_window": seed.get("catalyst_window"),
        "invalidation": seed.get("falsifier"),
        "price_or_expectation": seed.get("why_market_may_miss"),
        "crowding_or_position": "UNKNOWN",
        "scenario_fit": seed.get("scenario_paths"),
        "evidence": seed.get("evidence"),
        # Legacy seeds did not bind every field separately. Preserve their
        # evidence without pretending that it establishes price or crowding.
        "field_evidence": {
            "mechanism": seed.get("evidence", []),
            "economic_exposure": seed.get("evidence", []),
            "catalyst": [],
            "price_or_expectation": [],
            "crowding_or_position": [],
        },
    }
    return raw


def _ensure_map(state):
    candidate_map = state.get("candidate_map")
    if not isinstance(candidate_map, dict):
        candidate_map = state["candidate_map"] = {
            "schema_version": "trade-nothing.candidate-map.v6",
            "candidates": [],
            "market_mechanics": [],
            "coverage": {field: False for field in COVERAGE_FIELDS},
            "coverage_claims": {field: False for field in COVERAGE_FIELDS},
            "coverage_routes": [],
            "coverage_notes": [],
            "ingest_audits": [],
        }
    candidate_map.setdefault("candidates", [])
    candidate_map.setdefault("market_mechanics", [])
    candidate_map.setdefault("coverage", {field: False for field in COVERAGE_FIELDS})
    candidate_map.setdefault(
        "coverage_claims", {field: False for field in COVERAGE_FIELDS}
    )
    candidate_map.setdefault("coverage_routes", [])
    candidate_map.setdefault("coverage_notes", [])
    candidate_map.setdefault("ingest_audits", [])
    return candidate_map


def harvest_round(state, round_num, detective=None, inquisitor=None):
    """Ingest a bounded, discovery-first map from both role payloads."""
    candidate_map = _ensure_map(state)
    as_of_date = _state_as_of(state)
    agenda = state.get("research_agenda", {})
    evidence_items = agenda.get("evidence_items", []) if isinstance(agenda, dict) else []
    evidence_aliases = agenda.get("evidence_aliases", {}) if isinstance(agenda, dict) else {}
    require_canonical_field_evidence = (
        state.get("frame_contract", {}).get("control_mode") == "AGENDA_NATIVE"
        or agenda.get("agenda_source") == "EXPLICIT_WORKPLAN"
    )
    by_identity = {
        _identity(item): item
        for item in candidate_map["candidates"]
        if isinstance(item, dict)
    }
    audit = {
        "round": int(round_num),
        "accepted": 0,
        "merged_existing": 0,
        "rejected": 0,
        "rejected_reasons": {},
        "evidence_rejections": [],
        "coverage_route_rejections": [],
    }
    for role, payload in (("detective", detective), ("inquisitor", inquisitor)):
        payload = payload if isinstance(payload, dict) else {}
        new_candidate_budget = (
            MAX_NEW_CANDIDATES_FIRST_ROUND_PER_ROLE
            if int(round_num) <= 1
            else MAX_NEW_CANDIDATES_LATER_ROUND_PER_ROLE
        )
        new_candidates_for_role = 0
        raw_candidates = payload.get("market_map_candidates", [])
        if not isinstance(raw_candidates, list):
            raw_candidates = []
        # Backward compatibility: an admitted seed is also a concrete discovery
        # carrier, but it retains its own stricter lifecycle outside this module.
        raw_candidates = list(raw_candidates) + [
            _legacy_seed_candidate(seed)
            for seed in payload.get("opportunity_seeds", [])
            if isinstance(seed, dict)
        ]
        for raw in raw_candidates[:9]:
            item, reason = _normalize_candidate(
                raw,
                role,
                round_num,
                as_of_date=as_of_date,
                evidence_items=evidence_items,
                require_canonical_field_evidence=require_canonical_field_evidence,
                evidence_aliases=evidence_aliases,
                state=state,
            )
            if reason:
                audit["rejected"] += 1
                audit["rejected_reasons"][reason] = (
                    audit["rejected_reasons"].get(reason, 0) + 1
                )
                continue
            if item.get("evidence_rejections"):
                audit["evidence_rejections"].extend(copy.deepcopy(
                    item["evidence_rejections"]
                ))
            identity = _identity(item)
            if identity in by_identity:
                _merge_candidate(by_identity[identity], item)
                audit["merged_existing"] += 1
            else:
                if new_candidates_for_role >= new_candidate_budget:
                    reason = "NEW_CANDIDATE_ROUND_BUDGET_EXHAUSTED"
                    audit["rejected"] += 1
                    audit["rejected_reasons"][reason] = (
                        audit["rejected_reasons"].get(reason, 0) + 1
                    )
                    continue
                if len(candidate_map["candidates"]) >= MAX_CANDIDATES_TOTAL:
                    reason = "CANDIDATE_MAP_CAPACITY_REACHED"
                    audit["rejected"] += 1
                    audit["rejected_reasons"][reason] = (
                        audit["rejected_reasons"].get(reason, 0) + 1
                    )
                    continue
                candidate_map["candidates"].append(item)
                by_identity[identity] = item
                audit["accepted"] += 1
                new_candidates_for_role += 1

        mechanics = payload.get("market_mechanics")
        if isinstance(mechanics, dict):
            normalized = {
                field: _text(mechanics.get(field)) for field in MECHANICS_FIELDS
            }
            if any(normalized.values()):
                normalized.update({"source_agent": role, "round": int(round_num)})
                if normalized not in candidate_map["market_mechanics"]:
                    candidate_map["market_mechanics"].append(normalized)

        coverage = payload.get("market_map_coverage")
        if isinstance(coverage, dict):
            for field in COVERAGE_FIELDS:
                candidate_map["coverage_claims"][field] = bool(
                    candidate_map["coverage_claims"].get(field)
                    or coverage.get(field)
                )
            routes = coverage.get("routes", [])
            if not isinstance(routes, list):
                routes = []
                audit["coverage_route_rejections"].append(
                    "coverage_routes_must_be_list"
                )
            for raw_route in routes:
                route, reason = _normalize_coverage_route(raw_route)
                if reason:
                    audit["coverage_route_rejections"].append(reason)
                    continue
                route_key = (
                    route["coverage_field"], route["route_kind"], route["query"],
                    tuple(route["checked_urls"]), route["outcome"],
                )
                known_route_keys = {
                    (
                        item.get("coverage_field"), item.get("route_kind"),
                        item.get("query"),
                        tuple(item.get("checked_urls", [])), item.get("outcome"),
                    )
                    for item in candidate_map["coverage_routes"]
                    if isinstance(item, dict)
                }
                if route_key not in known_route_keys:
                    route.update({"source_agent": role, "round": int(round_num)})
                    candidate_map["coverage_routes"].append(route)
                if route["outcome"] in {"FOUND", "NO_RESULT"}:
                    candidate_map["coverage"][route["coverage_field"]] = True
            note = _text(coverage.get("note") or coverage.get("no_setup_reason"))
            if note and note not in candidate_map["coverage_notes"]:
                candidate_map["coverage_notes"].append(note)

    candidate_map["ingest_audits"].append(copy.deepcopy(audit))
    audit["completion_focus"] = focus_candidates(state, limit=4)
    audit.update(summary(state))
    return audit


def _ordered(candidates):
    boundary_rank = {"FACT": 0, "SINGLE_SOURCE": 1, "INFERENCE": 2, "HYPOTHESIS": 3}
    return sorted(candidates, key=lambda item: (
        0 if item.get("attention_band") == "SETUP_CANDIDATE" else 1,
        boundary_rank.get(item.get("evidence_boundary"), 9),
        0 if item.get("ticker") else 1,
        item.get("ticker") or item.get("candidate") or "",
    ))


def report_view(state):
    candidate_map = _ensure_map(state)
    projected = [
        copy.deepcopy(item) for item in candidate_map.get("candidates", [])
        if isinstance(item, dict)
    ]
    for item in projected:
        # Recompute the view under the current semantic kernel. Historical v4
        # `field_variants` were generated from any wording change and therefore
        # cannot be treated as explicit conflicts in v5.
        item.setdefault("field_conflicts", {})
        item.update(research_kernel.evaluate_setup(
            item, item.get("evidence_as_of_date") or _state_as_of(state)
        ))
    # Archived runs predate CandidateMap. Project their already-admitted concrete
    # seeds at read time so a new report does not erase useful named carriers.
    by_identity = {_identity(item): item for item in projected}
    for seed in state.get("opportunity_seeds", []):
        if not isinstance(seed, dict):
            continue
        item, _ = _normalize_candidate(
            _legacy_seed_candidate(seed),
            "legacy_opportunity_seed",
            seed.get("last_seen_round") or seed.get("first_seen_round") or 0,
            as_of_date=_state_as_of(state),
            evidence_items=state.get("research_agenda", {}).get(
                "evidence_items", []
            ),
            require_canonical_field_evidence=False,
            state=state,
        )
        if not item:
            continue
        identity = _identity(item)
        if identity in by_identity:
            _merge_candidate(by_identity[identity], item)
        else:
            projected.append(item)
            by_identity[identity] = item
    bridge_view = market_bridge_engine.report_view(state, projected)
    candidates = _ordered(bridge_view["candidates"])
    for index, item in enumerate(candidates, 1):
        item["attention_order"] = index
    coverage = {
        field: bool(candidate_map.get("coverage", {}).get(field))
        for field in COVERAGE_FIELDS
    }
    coverage_notes = list(candidate_map.get("coverage_notes", []))
    coverage_routes = copy.deepcopy(candidate_map.get("coverage_routes", []))
    # Neither a checkbox nor a prose note establishes search coverage. Each
    # coverage dimension needs an inspectable query and concrete checked URL.
    effective_routes = [
        route for route in coverage_routes
        if isinstance(route, dict)
        and route.get("outcome") in {"FOUND", "NO_RESULT"}
    ]
    route_fields = {
        route.get("coverage_field") for route in coverage_routes
        if isinstance(route, dict)
        and route.get("outcome") in {"FOUND", "NO_RESULT"}
    }
    route_kinds = {
        route.get("route_kind") for route in effective_routes
        if route.get("route_kind") in COVERAGE_ROUTE_KINDS
    }
    missing_route_kinds = [
        kind for kind in REQUIRED_COVERAGE_ROUTE_KINDS if kind not in route_kinds
    ]
    coverage_complete = (
        all(coverage.values())
        and all(field in route_fields for field in COVERAGE_FIELDS)
        and not missing_route_kinds
        and bool(coverage_notes)
    )
    setups = [item for item in candidates if item.get("attention_band") == "SETUP_CANDIDATE"]
    if setups:
        result_type = "SETUP_READY"
    elif coverage_complete:
        result_type = "NO_USABLE_SETUP"
    else:
        result_type = "EXPLORE"
    cheapest_next_test = next((
        item.get("cheap_discriminating_test")
        for item in candidates if _known(item.get("cheap_discriminating_test"))
    ), "补齐候选的事件窗口、价格预期或拥挤度中成本最低的一项。")
    return {
        "schema_version": candidate_map.get("schema_version"),
        "result_type": result_type,
        "candidates": candidates,
        "event_setups": [
            item for item in candidates
            if "EVENT_SETUP" in item.get("ready_setup_types", [])
        ],
        "economic_setups": [
            item for item in candidates
            if "ECONOMIC_SETUP" in item.get("ready_setup_types", [])
        ],
        "market_mechanics": copy.deepcopy(candidate_map.get("market_mechanics", [])),
        "market_bridge": bridge_view,
        "coverage": coverage,
        "coverage_claims": copy.deepcopy(candidate_map.get("coverage_claims", {})),
        "coverage_routes": coverage_routes,
        "covered_route_kinds": sorted(route_kinds),
        "missing_route_kinds": missing_route_kinds,
        "coverage_complete": coverage_complete,
        "coverage_notes": coverage_notes,
        "cheapest_next_test": cheapest_next_test,
        "boundary": (
            "Research-attention input for conditional report advice; not expected return, "
            "position sizing, an order, or an automatic downstream workflow."
        ),
    }


def summary(state):
    view = report_view(state)
    return {
        "candidate_map_count": len(view["candidates"]),
        "event_setup_count": len(view["event_setups"]),
        "economic_setup_count": len(view["economic_setups"]),
        "setup_candidate_count": sum(
            item.get("attention_band") == "SETUP_CANDIDATE"
            for item in view["candidates"]
        ),
        "candidate_map_result_type": view["result_type"],
        "candidate_map_coverage_complete": view["coverage_complete"],
        "bridge_priority_count": view.get("market_bridge", {}).get(
            "priority_count", 0
        ),
    }
