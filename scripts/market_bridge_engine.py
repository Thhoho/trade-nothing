#!/usr/bin/env python3
"""Deterministic projection from industry value transfer to market expression.

Market Bridge is deliberately not a workflow, score, or promotion engine.  It
normalizes value-transfer paths, preserves competing market-phase readings, and
checks whether a named carrier has enough cross-sectional context to support a
time-bounded conditional priority in the report.
"""
from copy import deepcopy
from datetime import date
import hashlib
import json
import math
import re

import execution_integrity
import market_snapshot_adapter
import research_kernel


SCHEMA_VERSION = "trade-nothing.market-bridge.v1"
HORIZONS = {
    "EVENT_DAYS",
    "TACTICAL_WEEKS",
    "EARNINGS_QUARTERS",
    "STRUCTURAL_YEARS",
}
PHASES = {
    "LATENT",
    "IGNITION",
    "DIFFUSION",
    "VERIFICATION",
    "DIVERGENCE",
    "CROWDING_RESET",
    "UNRESOLVED",
}
ECONOMIC_STRENGTHS = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}
MARKET_RECOGNITIONS = {"LEADER", "CONFIRMED", "EMERGING", "WEAK", "UNKNOWN"}
UNIVERSE_TYPES = {"ECONOMIC_EXPOSURE", "MARKET_TRADING"}
MARKET_METRICS = (
    "return_5d",
    "return_20d",
    "return_60d",
    "excess_5d",
    "excess_20d",
    "excess_60d",
    "drawdown_60d",
    "volume_ratio_20d",
    "turnover_rate",
    "provider_volume_ratio",
    "pe_ttm",
    "pb",
    "total_market_cap_cny",
    "float_market_cap_cny",
)
COUNTEREXAMPLE_ROLES = {"WATCH_ONLY", "FAILURE_HEDGE"}
RELATIVE_STRENGTH_METRICS = {"excess_5d", "excess_20d", "excess_60d"}
MARKET_ACTIVITY_METRICS = {
    "volume_ratio_20d", "turnover_rate", "provider_volume_ratio",
}


def _text(value):
    return " ".join(str(value or "").split())


def _norm(value):
    return re.sub(r"[^\w一-龥]+", "", _text(value).lower())


def _stable_id(prefix, payload):
    material = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return prefix + hashlib.sha256(material.encode("utf-8")).hexdigest()[:10].upper()


def _as_of(state):
    return _text(
        state.get("frame_contract", {}).get("as_of_date")
        or state.get("research_agenda", {}).get("as_of_date")
        or state.get("as_of_date")
    )


def _parse_date(value):
    try:
        return date.fromisoformat(_text(value))
    except (TypeError, ValueError):
        return None


def _agenda(state):
    value = state.get("research_agenda")
    return value if isinstance(value, dict) else {}


def _evidence_index(state):
    return {
        _text(item.get("evidence_id")): item
        for item in _agenda(state).get("evidence_items", [])
        if isinstance(item, dict) and _text(item.get("evidence_id"))
    }


def _resolve_evidence_ids(state, raw_ids):
    index = _evidence_index(state)
    aliases = _agenda(state).get("evidence_aliases", {})
    aliases = aliases if isinstance(aliases, dict) else {}
    accepted = []
    accepted_ids = []
    rejected = []
    if not isinstance(raw_ids, list):
        return accepted, accepted_ids, ["EVIDENCE_IDS_NOT_LIST"]
    for raw_id in raw_ids:
        evidence_id = _text(raw_id)
        canonical_id = _text(aliases.get(evidence_id) or evidence_id)
        item = index.get(canonical_id)
        if item is None:
            rejected.append(f"UNKNOWN_EVIDENCE_ID:{evidence_id or 'EMPTY'}")
            continue
        if canonical_id not in accepted_ids:
            accepted_ids.append(canonical_id)
            accepted.append(deepcopy(item))
    return accepted, accepted_ids, rejected


def _ensure(state):
    bridge = state.get("market_bridge")
    if not isinstance(bridge, dict):
        bridge = state["market_bridge"] = {
            "schema_version": SCHEMA_VERSION,
            "value_paths": [],
            "path_aliases": {},
            "phase_snapshots": [],
            "universe_snapshots": [],
            "ingest_audits": [],
            "host_market_snapshots": [],
            "host_snapshot_audits": [],
        }
    bridge.setdefault("schema_version", SCHEMA_VERSION)
    bridge.setdefault("value_paths", [])
    bridge.setdefault("path_aliases", {})
    bridge.setdefault("phase_snapshots", [])
    bridge.setdefault("universe_snapshots", [])
    bridge.setdefault("ingest_audits", [])
    bridge.setdefault("host_market_snapshots", [])
    bridge.setdefault("host_snapshot_audits", [])
    return bridge


def _known_question_ids(state):
    return {
        _text(item.get("question_id"))
        for item in _agenda(state).get("questions", [])
        if isinstance(item, dict) and _text(item.get("question_id"))
    }


def _known_direction_ids(state):
    return {
        _text(item.get("direction_id"))
        for item in _agenda(state).get("research_directions", [])
        if isinstance(item, dict) and _text(item.get("direction_id"))
    }


def _path_semantic_grounding(item):
    evidence = item.get("evidence", []) if isinstance(item, dict) else []
    mechanism_text = " -> ".join(filter(None, (
        _text(item.get("state_change")),
        _text(item.get("constraint_change")),
    )))
    economic_text = _text(item.get("profit_pool_shift"))
    mechanism_bound = any(
        research_kernel.claim_supports_field(
            "mechanism", mechanism_text, citation, mapping_is_inference=False
        )[0]
        for citation in evidence
    )
    economics_bound = any(
        research_kernel.claim_supports_field(
            "economic_exposure", economic_text, citation, mapping_is_inference=False
        )[0]
        for citation in evidence
    )
    issues = []
    if not mechanism_bound:
        issues.append("VALUE_PATH_MECHANISM_EVIDENCE_REQUIRED")
    if not economics_bound:
        issues.append("VALUE_PATH_ECONOMIC_EVIDENCE_REQUIRED")
    grounded = bool(
        mechanism_bound
        and economics_bound
        and item.get("evidence_ids")
        and _text(item.get("evidence_boundary")).upper() != "HYPOTHESIS"
    )
    return grounded, issues


def _normalize_path(state, raw, role, round_num):
    if not isinstance(raw, dict):
        return None, ["VALUE_PATH_MUST_BE_OBJECT"]
    issues = []
    question_ids = sorted(set(
        _text(value) for value in raw.get("origin_question_ids", [])
        if _text(value)
    )) if isinstance(raw.get("origin_question_ids"), list) else []
    if not question_ids:
        issues.append("VALUE_PATH_QUESTION_LINK_REQUIRED")
    unknown_questions = sorted(set(question_ids) - _known_question_ids(state))
    issues.extend(f"UNKNOWN_QUESTION_ID:{value}" for value in unknown_questions)

    direction_ids = sorted(set(
        _text(value) for value in raw.get("origin_direction_ids", [])
        if _text(value)
    )) if isinstance(raw.get("origin_direction_ids"), list) else []
    unknown_directions = sorted(set(direction_ids) - _known_direction_ids(state))
    issues.extend(f"UNKNOWN_DIRECTION_ID:{value}" for value in unknown_directions)

    horizon = _text(raw.get("realization_horizon")).upper()
    if horizon not in HORIZONS:
        issues.append("VALUE_PATH_HORIZON_REQUIRED")
    fields = {
        "state_change": _text(raw.get("state_change")),
        "constraint_change": _text(raw.get("constraint_change")),
        "profit_pool_shift": _text(raw.get("profit_pool_shift")),
        "falsifier": _text(raw.get("falsifier")),
    }
    for field, value in fields.items():
        if not research_kernel.known(value):
            issues.append(f"VALUE_PATH_{field.upper()}_REQUIRED")
    if issues:
        return None, issues
    evidence, evidence_ids, evidence_issues = _resolve_evidence_ids(
        state, raw.get("evidence_ids", [])
    )
    economic_winners = [
        _text(value) for value in raw.get("economic_winners", []) if _text(value)
    ] if isinstance(raw.get("economic_winners"), list) else []
    economic_losers = [
        _text(value) for value in raw.get("economic_losers", []) if _text(value)
    ] if isinstance(raw.get("economic_losers"), list) else []
    identity = {
        "origin_question_ids": question_ids,
        "origin_direction_ids": direction_ids,
        "state_change": _norm(fields["state_change"]),
        "constraint_change": _norm(fields["constraint_change"]),
        "profit_pool_shift": _norm(fields["profit_pool_shift"]),
        "realization_horizon": horizon,
    }
    path_id = _stable_id("VT-", identity)
    path_key = _text(raw.get("path_key"))
    item = {
        "path_id": path_id,
        "path_key": path_key,
        "origin_question_ids": question_ids,
        "origin_direction_ids": direction_ids,
        **fields,
        "economic_winners": list(dict.fromkeys(economic_winners)),
        "economic_losers": list(dict.fromkeys(economic_losers)),
        "realization_horizon": horizon,
        "evidence_ids": evidence_ids,
        "evidence": evidence,
        "evidence_boundary": research_kernel.evidence_boundary(evidence),
        "evidence_issues": evidence_issues,
        "source_agents": [role],
        "first_seen_round": int(round_num),
        "last_seen_round": int(round_num),
    }
    item["grounded"], semantic_issues = _path_semantic_grounding(item)
    item["evidence_issues"] = sorted(set(item["evidence_issues"] + semantic_issues))
    return item, []


def _merge_path(existing, incoming):
    existing["last_seen_round"] = max(
        int(existing.get("last_seen_round", 0) or 0),
        int(incoming.get("last_seen_round", 0) or 0),
    )
    existing["source_agents"] = sorted(set(
        existing.get("source_agents", []) + incoming.get("source_agents", [])
    ))
    existing["economic_winners"] = sorted(set(
        existing.get("economic_winners", []) + incoming.get("economic_winners", [])
    ))
    existing["economic_losers"] = sorted(set(
        existing.get("economic_losers", []) + incoming.get("economic_losers", [])
    ))
    existing["evidence"] = research_kernel.unique_evidence(
        existing.get("evidence", []) + incoming.get("evidence", [])
    )
    existing["evidence_ids"] = list(dict.fromkeys(
        existing.get("evidence_ids", []) + incoming.get("evidence_ids", [])
    ))
    existing["evidence_boundary"] = research_kernel.evidence_boundary(
        existing["evidence"]
    )
    existing["grounded"], semantic_issues = _path_semantic_grounding(existing)
    existing["evidence_issues"] = sorted(set(
        existing.get("evidence_issues", []) + semantic_issues
    ))


def _normalize_phase(state, raw, role, round_num):
    if not isinstance(raw, dict) or not raw:
        return None, []
    issues = []
    horizon = _text(raw.get("horizon")).upper()
    phase = _text(raw.get("phase")).upper()
    if horizon not in HORIZONS:
        issues.append("MARKET_PHASE_HORIZON_REQUIRED")
    if phase not in PHASES:
        issues.append("MARKET_PHASE_INVALID")
    snapshot_date = _text(raw.get("as_of_date") or _as_of(state))
    parsed = _parse_date(snapshot_date)
    cutoff = _parse_date(_as_of(state))
    if parsed is None:
        issues.append("MARKET_PHASE_AS_OF_INVALID")
    elif cutoff is not None and parsed > cutoff:
        issues.append("MARKET_PHASE_AFTER_AS_OF")
    required = {
        "dominant_pricing_variable": _text(raw.get("dominant_pricing_variable")),
        "industry_clock": _text(raw.get("industry_clock")),
        "market_clock": _text(raw.get("market_clock")),
        "strongest_alternative_phase": _text(raw.get("strongest_alternative_phase")),
        "falsifier": _text(raw.get("falsifier")),
    }
    for field, value in required.items():
        if not research_kernel.known(value):
            issues.append(f"MARKET_PHASE_{field.upper()}_REQUIRED")
    if issues:
        return None, issues
    evidence, evidence_ids, evidence_issues = _resolve_evidence_ids(
        state, raw.get("evidence_ids", [])
    )
    identity = {
        "as_of_date": snapshot_date,
        "horizon": horizon,
        "phase": phase,
        "dominant_pricing_variable": _norm(required["dominant_pricing_variable"]),
        "source_agent": role,
        "round": int(round_num),
    }
    return {
        "phase_snapshot_id": _stable_id("MP-", identity),
        "as_of_date": snapshot_date,
        "is_current_as_of": snapshot_date == _as_of(state),
        "horizon": horizon,
        "phase": phase,
        **required,
        "evidence_ids": evidence_ids,
        "evidence": evidence,
        "evidence_boundary": research_kernel.evidence_boundary(evidence),
        "evidence_issues": evidence_issues,
        "source_agent": role,
        "round": int(round_num),
    }, []


def _normalize_universe_member(state, raw):
    if not isinstance(raw, dict):
        return None, ["UNIVERSE_MEMBER_MUST_BE_OBJECT"]
    candidate = _text(raw.get("candidate"))
    asset_type = _text(raw.get("asset_type") or "LISTED_EQUITY").upper()
    instrument, reason = research_kernel.normalize_instrument_identity(
        asset_type, raw.get("ticker"), raw.get("exchange")
    )
    if reason or not candidate:
        return None, [reason or "UNIVERSE_MEMBER_NAME_REQUIRED"]
    evidence, evidence_ids, evidence_issues = _resolve_evidence_ids(
        state, raw.get("evidence_ids", [])
    )
    if not evidence_ids:
        evidence_issues.append("UNIVERSE_MEMBER_EVIDENCE_REQUIRED")
    item = {
        "candidate": candidate,
        "asset_type": asset_type,
        "ticker": instrument.get("ticker", ""),
        "exchange": instrument.get("exchange", ""),
        "role_in_universe": _text(raw.get("role_in_universe")),
        "evidence_ids": evidence_ids,
        "evidence": evidence,
        "evidence_boundary": research_kernel.evidence_boundary(evidence),
    }
    item["identity"] = research_kernel.instrument_identity(item)
    return item, evidence_issues


def _normalize_universe(state, raw, role, round_num):
    if not isinstance(raw, dict):
        return None, ["UNIVERSE_SNAPSHOT_MUST_BE_OBJECT"]
    issues = []
    universe_type = _text(raw.get("universe_type")).upper()
    if universe_type not in UNIVERSE_TYPES:
        issues.append("UNIVERSE_TYPE_INVALID")
    horizon = _text(raw.get("horizon")).upper()
    if horizon not in HORIZONS:
        issues.append("UNIVERSE_HORIZON_REQUIRED")
    snapshot_date = _text(raw.get("as_of_date") or _as_of(state))
    parsed = _parse_date(snapshot_date)
    cutoff = _parse_date(_as_of(state))
    if parsed is None:
        issues.append("UNIVERSE_AS_OF_INVALID")
    elif cutoff is not None and parsed > cutoff:
        issues.append("UNIVERSE_AFTER_AS_OF")
    elif cutoff is not None and (cutoff - parsed).days > 3:
        issues.append("UNIVERSE_STALE")
    elif snapshot_date != _as_of(state) and raw.get(
        "latest_observed_session_on_or_before_as_of"
    ) is not True:
        issues.append("UNIVERSE_LATEST_SESSION_UNCONFIRMED")
    universe_name = _text(raw.get("universe_name"))
    construction_rule = _text(raw.get("construction_rule"))
    if not universe_name:
        issues.append("UNIVERSE_NAME_REQUIRED")
    if not research_kernel.known(construction_rule):
        issues.append("UNIVERSE_CONSTRUCTION_RULE_REQUIRED")
    benchmark = _text(raw.get("benchmark"))
    if universe_type == "MARKET_TRADING" and not research_kernel.known(benchmark):
        issues.append("MARKET_UNIVERSE_BENCHMARK_REQUIRED")
    members = []
    for raw_member in raw.get("members", []) if isinstance(raw.get("members"), list) else []:
        member, member_issues = _normalize_universe_member(state, raw_member)
        issues.extend(member_issues)
        if member and member["identity"] not in {item["identity"] for item in members}:
            members.append(member)
    if len(members) < 2:
        issues.append("UNIVERSE_REQUIRES_TWO_MEMBERS")
    evidence, evidence_ids, evidence_issues = _resolve_evidence_ids(
        state, raw.get("evidence_ids", [])
    )
    issues.extend(evidence_issues)
    if not evidence_ids:
        issues.append("UNIVERSE_CONSTRUCTION_EVIDENCE_REQUIRED")
    if universe_type not in UNIVERSE_TYPES or horizon not in HORIZONS:
        return None, issues
    identity = {
        "universe_type": universe_type,
        "horizon": horizon,
        "as_of_date": snapshot_date,
        "universe_name": _norm(universe_name),
        "member_identities": sorted(item["identity"] for item in members),
        "source_agent": role,
        "round": int(round_num),
    }
    structural_blockers = {
        "UNIVERSE_AS_OF_INVALID",
        "UNIVERSE_AFTER_AS_OF",
        "UNIVERSE_STALE",
        "UNIVERSE_LATEST_SESSION_UNCONFIRMED",
        "UNIVERSE_NAME_REQUIRED",
        "UNIVERSE_CONSTRUCTION_RULE_REQUIRED",
        "MARKET_UNIVERSE_BENCHMARK_REQUIRED",
        "UNIVERSE_REQUIRES_TWO_MEMBERS",
        "UNIVERSE_CONSTRUCTION_EVIDENCE_REQUIRED",
        "UNIVERSE_MEMBER_EVIDENCE_REQUIRED",
    }
    return {
        "universe_snapshot_id": _stable_id("MU-", identity),
        "universe_key": _text(raw.get("universe_key")),
        "universe_type": universe_type,
        "horizon": horizon,
        "as_of_date": snapshot_date,
        "universe_name": universe_name,
        "construction_rule": construction_rule,
        "benchmark": benchmark or "UNKNOWN",
        "latest_observed_session_on_or_before_as_of": bool(
            raw.get("latest_observed_session_on_or_before_as_of")
        ),
        "members": members,
        "member_count": len(members),
        "evidence_ids": evidence_ids,
        "evidence": evidence,
        "evidence_boundary": research_kernel.evidence_boundary(evidence),
        "grounded": not any(
            issue.split(":", 1)[0] in structural_blockers for issue in issues
        ),
        "issues": sorted(set(issues)),
        "source_agent": role,
        "round": int(round_num),
    }, []


def harvest_context(state, round_num, detective=None, inquisitor=None):
    """Ingest paths and phase readings before CandidateMap resolves path refs."""
    bridge = _ensure(state)
    by_id = {
        item.get("path_id"): item for item in bridge["value_paths"]
        if isinstance(item, dict) and item.get("path_id")
    }
    audit = {
        "round": int(round_num),
        "paths_accepted": 0,
        "paths_merged": 0,
        "phases_accepted": 0,
        "universes_accepted": 0,
        "rejections": [],
    }
    for role, payload in (("detective", detective), ("inquisitor", inquisitor)):
        payload = payload if isinstance(payload, dict) else {}
        raw_paths = payload.get("value_transfer_paths", [])
        raw_paths = raw_paths if isinstance(raw_paths, list) else []
        for raw in raw_paths[:3]:
            path, issues = _normalize_path(state, raw, role, round_num)
            if path is None:
                audit["rejections"].extend({"role": role, "reason": value} for value in issues)
                continue
            path_id = path["path_id"]
            if path_id in by_id:
                _merge_path(by_id[path_id], path)
                audit["paths_merged"] += 1
            else:
                bridge["value_paths"].append(path)
                by_id[path_id] = path
                audit["paths_accepted"] += 1
            if path.get("path_key"):
                bridge["path_aliases"][f"{role}:{path['path_key']}"] = path_id

        phase, issues = _normalize_phase(
            state, payload.get("market_phase_snapshot"), role, round_num
        )
        if phase is not None:
            phase["source_payload_sha256"] = (
                execution_integrity.canonical_json_hash(payload)
            )
            if phase["phase_snapshot_id"] not in {
                item.get("phase_snapshot_id") for item in bridge["phase_snapshots"]
                if isinstance(item, dict)
            }:
                bridge["phase_snapshots"].append(phase)
                audit["phases_accepted"] += 1
        else:
            audit["rejections"].extend({"role": role, "reason": value} for value in issues)

        raw_universes = payload.get("carrier_universe_snapshots", [])
        raw_universes = raw_universes if isinstance(raw_universes, list) else []
        for raw_universe in raw_universes[:4]:
            universe, issues = _normalize_universe(
                state, raw_universe, role, round_num
            )
            if universe is None:
                audit["rejections"].extend(
                    {"role": role, "reason": value} for value in issues
                )
                continue
            if universe["universe_snapshot_id"] not in {
                item.get("universe_snapshot_id")
                for item in bridge["universe_snapshots"] if isinstance(item, dict)
            }:
                bridge["universe_snapshots"].append(universe)
                audit["universes_accepted"] += 1
    bridge["ingest_audits"].append(deepcopy(audit))
    return audit


def resolve_path_refs(state, role, refs):
    bridge = _ensure(state)
    known_ids = {
        item.get("path_id") for item in bridge.get("value_paths", [])
        if isinstance(item, dict)
    }
    aliases = bridge.get("path_aliases", {})
    accepted = []
    rejected = []
    if not isinstance(refs, list):
        return [], ["VALUE_PATH_REFS_NOT_LIST"]
    for raw_ref in refs:
        ref = _text(raw_ref)
        resolved = ref if ref in known_ids else aliases.get(f"{role}:{ref}")
        if not resolved:
            rejected.append(f"UNKNOWN_VALUE_PATH_REF:{ref or 'EMPTY'}")
            continue
        if resolved not in accepted:
            accepted.append(resolved)
    return accepted, rejected


def _metric(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _recognition_matches_snapshot(recognition, snapshot):
    if recognition not in {"LEADER", "CONFIRMED", "EMERGING"}:
        return True
    excess = [
        snapshot.get(name) for name in RELATIVE_STRENGTH_METRICS
        if snapshot.get(name) is not None
    ]
    return bool(excess and max(excess) > 0)


def _path_grounding(state, path_ids):
    index = {
        _text(item.get("path_id")): item
        for item in _ensure(state).get("value_paths", [])
        if isinstance(item, dict) and _text(item.get("path_id"))
    }
    grounded = []
    ungrounded = []
    for path_id in path_ids if isinstance(path_ids, list) else []:
        item = index.get(_text(path_id))
        if (
            item
            and item.get("grounded") is True
        ):
            grounded.append(_text(path_id))
        else:
            ungrounded.append(_text(path_id))
    return grounded, ungrounded


def _normalize_market_snapshot(
    state, raw, trusted_receipt_verified=False, authoritative_evidence=None,
):
    if not isinstance(raw, dict):
        return {}, False, ["MARKET_SNAPSHOT_REQUIRED"]
    issues = []
    snapshot_date = _text(raw.get("as_of_date"))
    parsed = _parse_date(snapshot_date)
    cutoff = _parse_date(_as_of(state))
    if parsed is None:
        issues.append("MARKET_SNAPSHOT_AS_OF_INVALID")
    elif cutoff is not None and parsed > cutoff:
        issues.append("MARKET_SNAPSHOT_AFTER_AS_OF")
    elif cutoff is not None and (cutoff - parsed).days > 3:
        issues.append("MARKET_SNAPSHOT_STALE")
    elif snapshot_date != _as_of(state) and raw.get(
        "latest_observed_session_on_or_before_as_of"
    ) is not True:
        issues.append("MARKET_SNAPSHOT_LATEST_SESSION_UNCONFIRMED")
    benchmark = _text(raw.get("benchmark"))
    if not research_kernel.known(benchmark):
        issues.append("MARKET_SNAPSHOT_BENCHMARK_REQUIRED")
    metrics = {name: _metric(raw.get(name)) for name in MARKET_METRICS}
    if not any(value is not None for value in metrics.values()):
        issues.append("MARKET_SNAPSHOT_METRIC_REQUIRED")
    if not any(metrics.get(name) is not None for name in RELATIVE_STRENGTH_METRICS):
        issues.append("MARKET_SNAPSHOT_RELATIVE_STRENGTH_REQUIRED")
    if not any(metrics.get(name) is not None for name in MARKET_ACTIVITY_METRICS):
        issues.append("MARKET_SNAPSHOT_ACTIVITY_REQUIRED")
    if authoritative_evidence is not None:
        evidence = research_kernel.unique_evidence(authoritative_evidence)
        evidence_ids = list(dict.fromkeys(
            _text(item.get("evidence_id")) for item in evidence
            if _text(item.get("evidence_id"))
        ))
        evidence_issues = []
    else:
        evidence, evidence_ids, evidence_issues = _resolve_evidence_ids(
            state, raw.get("evidence_ids", [])
        )
    if not evidence_ids:
        issues.append("MARKET_SNAPSHOT_EVIDENCE_REQUIRED")
    if not any(
        research_kernel.claim_matches_field_category("price_or_expectation", item)
        for item in evidence
    ):
        issues.append("MARKET_SNAPSHOT_PRICE_EVIDENCE_REQUIRED")
    if not any(
        research_kernel.claim_matches_field_category("crowding_or_position", item)
        for item in evidence
    ):
        issues.append("MARKET_SNAPSHOT_ACTIVITY_EVIDENCE_REQUIRED")
    if trusted_receipt_verified is not True:
        issues.append("MARKET_SNAPSHOT_HOST_RECEIPT_REQUIRED")
    snapshot = {
        "as_of_date": snapshot_date,
        "benchmark": benchmark,
        "theme_basket": _text(raw.get("theme_basket")) or "UNKNOWN",
        "latest_observed_session_on_or_before_as_of": bool(
            raw.get("latest_observed_session_on_or_before_as_of")
        ),
        "adapter_receipt": deepcopy(raw.get("adapter_receipt"))
        if isinstance(raw.get("adapter_receipt"), dict) else {},
        **metrics,
        "evidence_ids": evidence_ids,
        "evidence": evidence,
        "evidence_boundary": research_kernel.evidence_boundary(evidence),
        "evidence_issues": evidence_issues,
        "authority": (
            "HOST_INGESTED_RECEIPT_BOUND"
            if trusted_receipt_verified else "MODEL_CONTEXT_ONLY"
        ),
    }
    grounding_blockers = {
        "MARKET_SNAPSHOT_AS_OF_INVALID",
        "MARKET_SNAPSHOT_AFTER_AS_OF",
        "MARKET_SNAPSHOT_STALE",
        "MARKET_SNAPSHOT_LATEST_SESSION_UNCONFIRMED",
        "MARKET_SNAPSHOT_BENCHMARK_REQUIRED",
        "MARKET_SNAPSHOT_METRIC_REQUIRED",
        "MARKET_SNAPSHOT_RELATIVE_STRENGTH_REQUIRED",
        "MARKET_SNAPSHOT_ACTIVITY_REQUIRED",
        "MARKET_SNAPSHOT_EVIDENCE_REQUIRED",
        "MARKET_SNAPSHOT_PRICE_EVIDENCE_REQUIRED",
        "MARKET_SNAPSHOT_ACTIVITY_EVIDENCE_REQUIRED",
        "MARKET_SNAPSHOT_HOST_RECEIPT_REQUIRED",
    }
    grounded = not any(issue in grounding_blockers for issue in issues)
    return snapshot, grounded, issues + evidence_issues


def _candidate_source_identity(raw):
    if not isinstance(raw, dict):
        return "", "MARKET_SNAPSHOT_CANDIDATE_REQUIRED"
    instrument, reason = research_kernel.normalize_instrument_identity(
        "LISTED_EQUITY", raw.get("ticker"), raw.get("exchange")
    )
    if reason:
        return "", f"MARKET_SNAPSHOT_{reason.upper()}"
    item = {
        "candidate": _text(raw.get("name")),
        "asset_type": "LISTED_EQUITY",
        "ticker": instrument.get("ticker", ""),
        "exchange": instrument.get("exchange", ""),
    }
    return research_kernel.instrument_identity(item), ""


def _host_market_evidence_items(state, artifact, receipt, identity):
    """Mint candidate-bound canonical facts from a verified host snapshot.

    Host data is itself the evidence source.  Requiring a model-created Agenda
    citation before this point created a circular trust dependency and allowed
    unrelated company evidence IDs to be reused merely to open the gate.
    """
    snapshot = artifact.get("market_snapshot", {})
    candidate = artifact.get("candidate", {})
    sources = [
        item for item in artifact.get("sources", []) if isinstance(item, dict)
    ] if isinstance(artifact.get("sources"), list) else []
    candidate_url = _text(candidate.get("source_url"))
    benchmark_url = next((
        _text(item.get("source_url")) for item in sources
        if _text(item.get("source_url")) and _text(item.get("source_url")) != candidate_url
    ), _text(snapshot.get("adapter_receipt", {}).get("benchmark_source_url")))
    source = _text(candidate.get("source")) or "structured market data"
    name = _text(candidate.get("name")) or _text(candidate.get("ticker"))
    session = _text(snapshot.get("as_of_date"))

    def metric_text(names):
        values = []
        for field in names:
            value = snapshot.get(field)
            if value is not None:
                values.append(f"{field}={value}")
        return "；".join(values)

    price_numbers = metric_text((
        "return_5d", "return_20d", "return_60d",
        "excess_5d", "excess_20d", "excess_60d", "drawdown_60d",
        "pe_ttm", "pb", "total_market_cap_cny", "float_market_cap_cny",
    ))
    activity_numbers = metric_text((
        "volume_ratio_20d", "turnover_rate", "provider_volume_ratio",
    ))
    common = {
        "source": source,
        "url": candidate_url,
        "date": session,
        "source_tier": "structured_market_data",
        "question_ids": [],
        "direction_ids": [],
        "stance": "CONTEXT",
        "origin": "HOST_MARKET_SNAPSHOT",
        "binding": {
            "binding_type": "CANDIDATE_MARKET_SNAPSHOT",
            "candidate_identity": identity,
            "market_session_date": receipt.get("market_session_date"),
        },
        "supporting_urls": [benchmark_url] if benchmark_url else [],
        "receipt_id": receipt.get("receipt_id"),
    }
    raw_items = [
        {
            **common,
            "claim": (
                f"{name}截至{session}的冻结股价、相对基准收益、回撤与估值观测："
                f"{price_numbers}"
            ),
            "number": price_numbers,
            "axis": "PRICE_OR_EXPECTATION",
        },
        {
            **common,
            "claim": (
                f"{name}截至{session}的换手率、成交量与市场活动度观测："
                f"{activity_numbers}"
            ),
            "number": activity_numbers,
            "axis": "CROWDING_OR_POSITION",
        },
    ]
    agenda = state.get("research_agenda")
    if not isinstance(agenda, dict):
        return [], ["RESEARCH_AGENDA_REQUIRED_FOR_HOST_EVIDENCE"]
    items = []
    issues = []
    for raw in raw_items:
        if not raw.get("number"):
            continue
        stable = {
            "receipt_id": receipt.get("receipt_id"),
            "candidate_identity": identity,
            "axis": raw.get("axis"),
        }
        item, status = research_kernel.upsert_canonical_evidence(
            agenda, raw, _as_of(state), stable_material=stable
        )
        if item is None:
            issues.append(status)
        else:
            items.append(item)
    return items, issues


def refresh_host_market_evidence(state):
    """Upgrade accepted legacy snapshots to candidate-bound host evidence.

    Older v0.15 artifacts were accepted only after borrowing model evidence
    IDs.  The receipt-bound snapshot already contains enough source lineage to
    derive the correct canonical facts, so the repair is deterministic and
    does not fetch or reinterpret external data.
    """
    refreshed = 0
    issues = []
    for entry in _ensure(state).get("host_market_snapshots", []):
        if not isinstance(entry, dict):
            continue
        identity = _text(entry.get("candidate_identity"))
        artifact = {
            "candidate": deepcopy(entry.get("candidate", {})),
            "market_snapshot": deepcopy(entry.get("market_snapshot", {})),
            "sources": deepcopy(entry.get("sources", [])),
        }
        receipt = {
            "receipt_id": _text(entry.get("receipt_id")),
            "market_session_date": _text(entry.get("market_session_date")),
        }
        evidence, evidence_issues = _host_market_evidence_items(
            state, artifact, receipt, identity
        )
        issues.extend(evidence_issues)
        if not evidence:
            continue
        snapshot = entry.setdefault("market_snapshot", {})
        canonical_ids = list(dict.fromkeys(
            _text(item.get("evidence_id")) for item in evidence
            if _text(item.get("evidence_id"))
        ))
        if snapshot.get("evidence_ids") != canonical_ids:
            refreshed += 1
        snapshot["evidence_ids"] = canonical_ids
        snapshot["evidence"] = deepcopy(evidence)
        snapshot["evidence_boundary"] = research_kernel.evidence_boundary(evidence)
        snapshot["evidence_issues"] = []
        entry["canonical_evidence_ids"] = canonical_ids
    return {"refreshed": refreshed, "issues": sorted(set(issues))}


def ingest_host_market_snapshot(state, artifact):
    """Ingest one explicitly host-approved, receipt-bound market projection.

    This is an append-only data plane under Market Bridge, not a lifecycle
    transition.  Model payloads cannot write to it through ``--submit``.
    """
    bridge = _ensure(state)
    audit = {"status": "REJECTED", "reason": "", "receipt_id": ""}
    try:
        receipt = market_snapshot_adapter.validate_snapshot_artifact(
            artifact, require_upstream_receipt=True
        )
    except ValueError as exc:
        audit["reason"] = str(exc)
        bridge["host_snapshot_audits"].append(deepcopy(audit))
        return audit
    identity, identity_issue = _candidate_source_identity(artifact.get("candidate"))
    if identity_issue:
        audit.update({"reason": identity_issue, "receipt_id": receipt["receipt_id"]})
        bridge["host_snapshot_audits"].append(deepcopy(audit))
        return audit
    host_evidence, host_evidence_issues = _host_market_evidence_items(
        state, artifact, receipt, identity
    )
    snapshot, grounded, issues = _normalize_market_snapshot(
        state,
        artifact.get("market_snapshot"),
        trusted_receipt_verified=True,
        authoritative_evidence=host_evidence,
    )
    issues.extend(host_evidence_issues)
    audit.update({
        "receipt_id": receipt["receipt_id"],
        "candidate_identity": identity,
        "market_session_date": receipt["market_session_date"],
        "issues": sorted(set(issues)),
    })
    if not grounded:
        audit["reason"] = "MARKET_SNAPSHOT_NOT_RECOMMENDATION_GRADE"
        bridge["host_snapshot_audits"].append(deepcopy(audit))
        return audit
    existing = [
        item for item in bridge["host_market_snapshots"]
        if isinstance(item, dict)
        and item.get("candidate_identity") == identity
        and item.get("market_session_date") == receipt["market_session_date"]
    ]
    if any(item.get("receipt_id") == receipt["receipt_id"] for item in existing):
        refresh_host_market_evidence(state)
        audit.update({"status": "IDEMPOTENT", "reason": ""})
        bridge["host_snapshot_audits"].append(deepcopy(audit))
        return audit
    if existing:
        audit["reason"] = "MARKET_SNAPSHOT_CONFLICT_FOR_CANDIDATE_SESSION"
        bridge["host_snapshot_audits"].append(deepcopy(audit))
        return audit
    entry = {
        "candidate_identity": identity,
        "candidate": deepcopy(artifact.get("candidate")),
        "market_session_date": receipt["market_session_date"],
        "receipt_id": receipt["receipt_id"],
        "upstream_acquisition_receipt_id": receipt[
            "upstream_acquisition_receipt_id"
        ],
        "market_snapshot": snapshot,
        "canonical_evidence_ids": list(snapshot.get("evidence_ids", [])),
        "sources": deepcopy(artifact.get("sources", [])),
    }
    bridge["host_market_snapshots"].append(entry)
    audit.update({"status": "ACCEPTED", "reason": ""})
    bridge["host_snapshot_audits"].append(deepcopy(audit))
    return audit


def _trusted_snapshot_for_candidate(state, candidate_item, requested_receipt_id=""):
    refresh_host_market_evidence(state)
    identity = research_kernel.instrument_identity(candidate_item or {})
    requested_receipt_id = _text(requested_receipt_id)
    matches = [
        item for item in _ensure(state).get("host_market_snapshots", [])
        if isinstance(item, dict) and item.get("candidate_identity") == identity
    ]
    if not matches:
        return {}, False, ["TRUSTED_MARKET_SNAPSHOT_NOT_INGESTED"]
    if requested_receipt_id:
        requested = [
            item for item in matches
            if item.get("receipt_id") == requested_receipt_id
        ]
        if not requested:
            return {}, False, ["TRUSTED_MARKET_SNAPSHOT_RECEIPT_MISMATCH"]
        matches = requested
    selected = sorted(
        matches,
        key=lambda item: (
            item.get("market_session_date", ""), item.get("receipt_id", "")
        ),
        reverse=True,
    )[0]
    snapshot = deepcopy(selected.get("market_snapshot", {}))
    snapshot["receipt_id"] = selected.get("receipt_id")
    snapshot["upstream_acquisition_receipt_id"] = selected.get(
        "upstream_acquisition_receipt_id"
    )
    return snapshot, True, []


def _normalize_alternative(raw):
    if not isinstance(raw, dict):
        return {}, ["CLOSEST_ALTERNATIVE_REQUIRED"]
    candidate = _text(raw.get("candidate"))
    asset_type = _text(raw.get("asset_type") or "LISTED_EQUITY").upper()
    instrument, reason = research_kernel.normalize_instrument_identity(
        asset_type, raw.get("ticker"), raw.get("exchange")
    )
    if reason or not candidate:
        return {}, [reason or "CLOSEST_ALTERNATIVE_NAME_REQUIRED"]
    item = {
        "candidate": candidate,
        "asset_type": asset_type,
        "ticker": instrument.get("ticker", ""),
        "exchange": instrument.get("exchange", ""),
    }
    item["identity"] = research_kernel.instrument_identity(item)
    return item, []


def normalize_candidate_bridge(state, raw, role, candidate_item):
    """Normalize one candidate bridge after core candidate evidence is resolved."""
    raw = raw if isinstance(raw, dict) else {}
    issues = []
    path_ids, path_issues = resolve_path_refs(
        state, role, raw.get("value_path_refs", [])
    )
    issues.extend(path_issues)
    declared_economic = _text(raw.get("economic_exposure_strength") or "UNKNOWN").upper()
    if declared_economic not in ECONOMIC_STRENGTHS:
        declared_economic = "UNKNOWN"
        issues.append("INVALID_ECONOMIC_EXPOSURE_STRENGTH")
    declared_market = _text(raw.get("market_recognition") or "UNKNOWN").upper()
    if declared_market not in MARKET_RECOGNITIONS:
        declared_market = "UNKNOWN"
        issues.append("INVALID_MARKET_RECOGNITION")
    horizons = sorted(set(
        _text(value).upper() for value in raw.get("horizon_fit", [])
        if _text(value).upper() in HORIZONS
    )) if isinstance(raw.get("horizon_fit"), list) else []
    if raw.get("horizon_fit") and not horizons:
        issues.append("INVALID_HORIZON_FIT")
    snapshot, market_grounded, snapshot_issues = _trusted_snapshot_for_candidate(
        state, candidate_item, raw.get("trusted_market_snapshot_receipt_id")
    )
    issues.extend(snapshot_issues)
    if isinstance(raw.get("market_snapshot"), dict) and raw.get("market_snapshot"):
        issues.append("MODEL_MARKET_SNAPSHOT_IGNORED_FOR_AUTHORITY")
    alternative, alternative_issues = _normalize_alternative(
        raw.get("closest_alternative")
    )
    issues.extend(alternative_issues)

    economic_field_evidence = (
        candidate_item.get("field_evidence", {}).get("economic_exposure", [])
        if isinstance(candidate_item, dict) else []
    )
    grounded_path_ids, ungrounded_path_ids = _path_grounding(state, path_ids)
    economic_rationale = _text(raw.get("economic_rationale"))
    market_rationale = _text(raw.get("market_selection_rationale"))
    economic_grounded = bool(
        grounded_path_ids
        and research_kernel.known(candidate_item.get("economic_exposure"))
        and economic_field_evidence
        and research_kernel.known(economic_rationale)
    )
    market_grounded = bool(
        market_grounded and research_kernel.known(market_rationale)
    )
    if market_grounded and not _recognition_matches_snapshot(
        declared_market, snapshot
    ):
        market_grounded = False
        issues.append("MARKET_RECOGNITION_CONTRADICTS_RELATIVE_STRENGTH")
    issues.extend(
        f"VALUE_PATH_NOT_GROUNDED:{path_id}" for path_id in ungrounded_path_ids
    )
    effective_economic = declared_economic if economic_grounded else "UNKNOWN"
    effective_market = declared_market if market_grounded else "UNKNOWN"
    if declared_economic != "UNKNOWN" and not economic_grounded:
        issues.append("ECONOMIC_STRENGTH_NOT_GROUNDED")
    if declared_market != "UNKNOWN" and not market_grounded:
        issues.append("MARKET_RECOGNITION_NOT_GROUNDED")
    return {
        "value_path_ids": path_ids,
        "grounded_value_path_ids": grounded_path_ids,
        "economic_exposure_strength": {
            "declared": declared_economic,
            "effective": effective_economic,
            "grounded": economic_grounded,
            "rationale": economic_rationale,
        },
        "market_recognition": {
            "declared": declared_market,
            "effective": effective_market,
            "grounded": market_grounded,
            "rationale": market_rationale,
        },
        "horizon_fit": horizons,
        "market_snapshot": snapshot,
        "trusted_market_snapshot_receipt_id": snapshot.get("receipt_id", ""),
        "closest_alternative": alternative,
        "why_prefer_now": _text(raw.get("why_prefer_now")),
        "switch_condition": _text(raw.get("switch_condition")),
        "source_agents": [role],
        "issues": sorted(set(issues)),
    }


def refresh_candidate_bridge(state, candidate_item, bridge=None):
    """Recompute authority-bearing bridge facts from current canonical state.

    Persisted bridge records retain what roles declared.  Snapshot attachment,
    grounding and issue codes are derived facts and must never be append-only.
    """
    bridge = bridge if isinstance(bridge, dict) else {}
    raw = {
        "value_path_refs": list(bridge.get("value_path_ids", [])),
        "economic_exposure_strength": bridge.get(
            "economic_exposure_strength", {}
        ).get("declared", "UNKNOWN"),
        "economic_rationale": bridge.get(
            "economic_exposure_strength", {}
        ).get("rationale", ""),
        "market_recognition": bridge.get(
            "market_recognition", {}
        ).get("declared", "UNKNOWN"),
        "market_selection_rationale": bridge.get(
            "market_recognition", {}
        ).get("rationale", ""),
        "horizon_fit": list(bridge.get("horizon_fit", [])),
        # Snapshot selection is centralized by exact instrument identity.  A
        # role never has to repeat a receipt ID to make already-ingested host
        # data visible to the current projection.
        "trusted_market_snapshot_receipt_id": "",
        "closest_alternative": deepcopy(bridge.get("closest_alternative", {})),
        "why_prefer_now": bridge.get("why_prefer_now", ""),
        "switch_condition": bridge.get("switch_condition", ""),
    }
    refreshed = normalize_candidate_bridge(
        state, raw, "canonical_projection", candidate_item
    )
    refreshed["source_agents"] = sorted(set(bridge.get("source_agents", [])))
    # These two codes describe real, grounded role disagreement.  Other issue
    # codes are current-state derivations and are deliberately recomputed.
    for issue in bridge.get("issues", []):
        if issue in {
            "ECONOMIC_STRENGTH_ROLE_CONFLICT",
            "MARKET_RECOGNITION_ROLE_CONFLICT",
        }:
            refreshed.setdefault("issues", []).append(issue)
        elif issue == "CLOSEST_ALTERNATIVE_ROLE_CONFLICT":
            refreshed.setdefault("audit_notes", []).append(
                "ALTERNATIVE_SET_DIVERGED"
            )
    refreshed["issues"] = sorted(set(refreshed.get("issues", [])))
    refreshed["audit_notes"] = sorted(set(refreshed.get("audit_notes", [])))
    return refreshed


def _bridge_quality(item):
    return (
        int(item.get("economic_exposure_strength", {}).get("grounded") is True)
        + int(item.get("market_recognition", {}).get("grounded") is True),
        len(item.get("value_path_ids", [])),
        len(item.get("horizon_fit", [])),
        len(_text(item.get("why_prefer_now"))),
        len(_text(item.get("switch_condition"))),
        _norm(item.get("market_recognition", {}).get("rationale")),
    )


def merge_candidate_bridge(existing, incoming):
    """Merge role views without making role arrival order authoritative."""
    if not isinstance(existing, dict) or not existing:
        return deepcopy(incoming)
    if not isinstance(incoming, dict) or not incoming:
        return deepcopy(existing)
    winner, loser = (
        (incoming, existing)
        if _bridge_quality(incoming) > _bridge_quality(existing)
        else (existing, incoming)
    )
    merged = deepcopy(winner)
    merged["value_path_ids"] = sorted(set(
        existing.get("value_path_ids", []) + incoming.get("value_path_ids", [])
    ))
    merged["grounded_value_path_ids"] = sorted(set(
        existing.get("grounded_value_path_ids", [])
        + incoming.get("grounded_value_path_ids", [])
    ))
    merged["horizon_fit"] = sorted(set(
        existing.get("horizon_fit", []) + incoming.get("horizon_fit", [])
    ))
    merged["source_agents"] = sorted(set(
        existing.get("source_agents", []) + incoming.get("source_agents", [])
    ))
    # Issue codes are a projection of current facts, not an append-only event
    # log.  Start from the selected current view and add only conflicts derived
    # from the two role declarations below.
    merged["issues"] = sorted(set(winner.get("issues", [])))
    if (
        existing.get("economic_exposure_strength", {}).get("effective")
        != incoming.get("economic_exposure_strength", {}).get("effective")
        and all(
            item.get("economic_exposure_strength", {}).get("grounded") is True
            for item in (existing, incoming)
        )
    ):
        merged["issues"].append("ECONOMIC_STRENGTH_ROLE_CONFLICT")
    if (
        existing.get("market_recognition", {}).get("effective")
        != incoming.get("market_recognition", {}).get("effective")
        and all(
            item.get("market_recognition", {}).get("grounded") is True
            for item in (existing, incoming)
        )
    ):
        merged["issues"].append("MARKET_RECOGNITION_ROLE_CONFLICT")
    existing_alternative = existing.get("closest_alternative", {}).get("identity")
    incoming_alternative = incoming.get("closest_alternative", {}).get("identity")
    if (
        existing_alternative
        and incoming_alternative
        and existing_alternative != incoming_alternative
    ):
        merged.setdefault("audit_notes", []).append("ALTERNATIVE_SET_DIVERGED")
    merged["issues"] = sorted(set(merged["issues"]))
    merged["audit_notes"] = sorted(set(merged.get("audit_notes", [])))
    return merged


def _projection(economic, market):
    if economic in {"HIGH", "MEDIUM"} and market in {"LEADER", "CONFIRMED"}:
        return "CONFIRMED_LEADER"
    if economic in {"HIGH", "MEDIUM"}:
        return "LATENT_ECONOMIC"
    if economic == "LOW" and market in {"LEADER", "CONFIRMED", "EMERGING"}:
        return "EVENT_BETA"
    if economic == "LOW" and market in {"WEAK", "UNKNOWN"}:
        return "LOW_PRIORITY"
    if economic == "UNKNOWN" and market in {"LEADER", "CONFIRMED", "EMERGING"}:
        return "MARKET_ONLY_UNRESOLVED"
    return "UNRESOLVED"


def _universe_view(state):
    bridge = _ensure(state)
    result = {}
    for horizon in HORIZONS:
        horizon_view = {
            "types": {},
            "complete": False,
            "all_member_identities": [],
        }
        all_members = set()
        for universe_type in UNIVERSE_TYPES:
            snapshots = [
                deepcopy(item) for item in bridge.get("universe_snapshots", [])
                if isinstance(item, dict)
                and item.get("horizon") == horizon
                and item.get("universe_type") == universe_type
            ]
            if not snapshots:
                continue
            latest_round = max(int(item.get("round", 0) or 0) for item in snapshots)
            latest = [
                item for item in snapshots
                if int(item.get("round", 0) or 0) == latest_round
            ]
            grounded = [item for item in latest if item.get("grounded") is True]
            members = sorted({
                member.get("identity")
                for item in grounded
                for member in item.get("members", [])
                if isinstance(member, dict) and member.get("identity")
            })
            all_members.update(members)
            horizon_view["types"][universe_type] = {
                "status": "GROUNDED" if grounded else "INSUFFICIENT",
                "member_identities": members,
                "snapshots": latest,
            }
        horizon_view["complete"] = all(
            horizon_view["types"].get(kind, {}).get("status") == "GROUNDED"
            for kind in UNIVERSE_TYPES
        )
        horizon_view["all_member_identities"] = sorted(all_members)
        if horizon_view["types"]:
            result[horizon] = horizon_view
    return result


def _eligible_phase_horizons(phase_by_horizon):
    eligible = set()
    for horizon, phase in (phase_by_horizon or {}).items():
        if (
            phase.get("status") == "CONSENSUS"
            and phase.get("phase") != "UNRESOLVED"
            and len(phase.get("grounded_source_agents", [])) >= 2
        ):
            eligible.add(horizon)
    return eligible


def finalize_candidates(
    candidates, phase_by_horizon=None, universe_by_horizon=None, value_paths=None,
):
    """Derive report authority after every alternative identity is visible."""
    identities = {
        research_kernel.instrument_identity(item)
        for item in candidates if isinstance(item, dict)
    }
    eligible_phase_horizons = _eligible_phase_horizons(phase_by_horizon)
    grounded_paths = {
        _text(path.get("path_id"))
        for path in value_paths if isinstance(path, dict)
        and _text(path.get("path_id"))
        and path.get("grounded") is True
    } if isinstance(value_paths, list) else set()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        bridge = item.get("bridge") if isinstance(item.get("bridge"), dict) else {}
        economic = bridge.get("economic_exposure_strength", {}).get("effective", "UNKNOWN")
        market = bridge.get("market_recognition", {}).get("effective", "UNKNOWN")
        projection = _projection(economic, market)
        alternative_identity = bridge.get("closest_alternative", {}).get("identity")
        own_identity = research_kernel.instrument_identity(item)
        alternative_valid = bool(
            alternative_identity
            and alternative_identity != own_identity
            and alternative_identity in identities
        )
        if alternative_identity and not alternative_valid:
            bridge.setdefault("issues", []).append("CLOSEST_ALTERNATIVE_NOT_IN_CANDIDATE_MAP")
        bridge_conflict = any(issue in {
            "ECONOMIC_STRENGTH_ROLE_CONFLICT",
            "MARKET_RECOGNITION_ROLE_CONFLICT",
        } for issue in bridge.get("issues", []))
        path_ids = set(bridge.get("value_path_ids", []))
        recommendation_path_ids = sorted(path_ids & grounded_paths)
        value_paths_grounded = bool(recommendation_path_ids)
        if path_ids - grounded_paths:
            bridge.setdefault("issues", []).append("VALUE_PATH_NOT_GROUNDED")
        comparison_ready = bool(
            value_paths_grounded
            and bridge.get("horizon_fit")
            and alternative_valid
            and research_kernel.known(bridge.get("why_prefer_now"))
            and research_kernel.known(bridge.get("switch_condition"))
            and not bridge_conflict
        )
        recommendation_horizons = []
        for horizon in bridge.get("horizon_fit", []):
            phase = (phase_by_horizon or {}).get(horizon)
            if not phase:
                bridge.setdefault("issues", []).append(
                    f"MARKET_PHASE_MISSING:{horizon}"
                )
            elif phase.get("status") == "SINGLE_VIEW":
                bridge.setdefault("issues", []).append(
                    f"MARKET_PHASE_SINGLE_VIEW:{horizon}"
                )
            elif phase.get("status") == "UNVERIFIED_CONSENSUS":
                bridge.setdefault("issues", []).append(
                    f"MARKET_PHASE_EXECUTION_UNVERIFIED:{horizon}"
                )
            elif phase.get("status") != "CONSENSUS":
                bridge.setdefault("issues", []).append(
                    f"MARKET_PHASE_DISPUTED:{horizon}"
                )
            elif horizon not in eligible_phase_horizons:
                bridge.setdefault("issues", []).append(
                    f"MARKET_PHASE_NOT_GROUNDED:{horizon}"
                )
            universe = (universe_by_horizon or {}).get(horizon)
            if not universe or not universe.get("complete"):
                bridge.setdefault("issues", []).append(
                    f"DUAL_UNIVERSE_INCOMPLETE:{horizon}"
                )
                continue
            economic_members = set(
                universe.get("types", {}).get("ECONOMIC_EXPOSURE", {}).get(
                    "member_identities", []
                )
            )
            market_members = set(
                universe.get("types", {}).get("MARKET_TRADING", {}).get(
                    "member_identities", []
                )
            )
            if economic in {"HIGH", "MEDIUM"} and own_identity not in economic_members:
                bridge.setdefault("issues", []).append(
                    f"CANDIDATE_NOT_IN_ECONOMIC_UNIVERSE:{horizon}"
                )
                continue
            if market != "UNKNOWN" and own_identity not in market_members:
                bridge.setdefault("issues", []).append(
                    f"CANDIDATE_NOT_IN_MARKET_UNIVERSE:{horizon}"
                )
                continue
            if alternative_identity not in set(universe.get("all_member_identities", [])):
                bridge.setdefault("issues", []).append(
                    f"ALTERNATIVE_NOT_IN_DUAL_UNIVERSE:{horizon}"
                )
                continue
            if horizon in eligible_phase_horizons:
                recommendation_horizons.append(horizon)
        recommendation_horizons = sorted(set(recommendation_horizons))
        roles = set(item.get("market_roles") or [item.get("market_role")])
        if roles and not (roles - COUNTEREXAMPLE_ROLES):
            recommendation_level = "COUNTEREXAMPLE"
        elif not comparison_ready or not recommendation_horizons:
            recommendation_level = "RESEARCH_PRIORITY"
        elif projection == "CONFIRMED_LEADER":
            recommendation_level = "CROSS_SECTIONAL_PRIORITY"
        elif projection == "LATENT_ECONOMIC":
            recommendation_level = "INDUSTRIAL_PRIORITY"
        elif projection == "EVENT_BETA":
            recommendation_level = "EVENT_PRIORITY"
        else:
            recommendation_level = "RESEARCH_PRIORITY"
        bridge["projection"] = projection
        bridge["recommendation_path_ids"] = recommendation_path_ids
        bridge["alternative_valid"] = alternative_valid
        bridge["comparison_ready"] = comparison_ready
        bridge["recommendation_horizons"] = recommendation_horizons
        bridge["recommendation_level"] = recommendation_level
        bridge["issues"] = sorted(set(bridge.get("issues", [])))
        item["bridge"] = bridge
    return candidates


def _phase_view(state):
    bridge = _ensure(state)
    result = {}
    for horizon in HORIZONS:
        snapshots = [
            deepcopy(item) for item in bridge.get("phase_snapshots", [])
            if isinstance(item, dict) and item.get("horizon") == horizon
        ]
        if not snapshots:
            continue
        latest_round = max(int(item.get("round", 0) or 0) for item in snapshots)
        latest = [item for item in snapshots if int(item.get("round", 0) or 0) == latest_round]
        phases = sorted(set(item.get("phase") for item in latest))
        source_agents = sorted(set(
            _text(item.get("source_agent")) for item in latest
            if _text(item.get("source_agent"))
        ))
        verified_source_agents = sorted(set(
            _text(item.get("source_agent")) for item in latest
            if _text(item.get("source_agent"))
            and execution_integrity.round_role_execution_verified(
                state,
                item.get("round", 0),
                item.get("source_agent"),
                item.get("source_payload_sha256", ""),
            )
        ))
        grounded_source_agents = sorted(set(
            _text(item.get("source_agent")) for item in latest
            if _text(item.get("source_agent"))
            and item.get("is_current_as_of") is True
            and item.get("evidence_boundary") != "HYPOTHESIS"
            and execution_integrity.round_role_execution_verified(
                state,
                item.get("round", 0),
                item.get("source_agent"),
                item.get("source_payload_sha256", ""),
            )
        ))
        status = (
            "DISPUTED" if len(phases) > 1
            else "CONSENSUS" if len(verified_source_agents) >= 2
            else "UNVERIFIED_CONSENSUS" if len(source_agents) >= 2
            else "SINGLE_VIEW"
        )
        result[horizon] = {
            "status": status,
            "phase": phases[0] if len(phases) == 1 else "UNRESOLVED",
            "competing_phases": phases,
            "source_agents": source_agents,
            "verified_source_agents": verified_source_agents,
            "grounded_source_agents": grounded_source_agents,
            "snapshots": latest,
        }
    return result


def report_view(state, candidates):
    refresh_host_market_evidence(state)
    phase_by_horizon = _phase_view(state)
    universe_by_horizon = _universe_view(state)
    projected = finalize_candidates(
        deepcopy(candidates or []),
        phase_by_horizon=phase_by_horizon,
        universe_by_horizon=universe_by_horizon,
        value_paths=_ensure(state).get("value_paths", []),
    )
    priorities = {horizon: [] for horizon in HORIZONS}
    unresolved = []
    priority_levels = {
        "CROSS_SECTIONAL_PRIORITY",
        "INDUSTRIAL_PRIORITY",
        "EVENT_PRIORITY",
    }
    for item in projected:
        bridge = item.get("bridge", {})
        if bridge.get("recommendation_level") in priority_levels:
            for horizon in bridge.get("recommendation_horizons", []):
                priorities[horizon].append(deepcopy(item))
        else:
            unresolved.append(deepcopy(item))
    lane_order = {
        "CROSS_SECTIONAL_PRIORITY": 0,
        "INDUSTRIAL_PRIORITY": 1,
        "EVENT_PRIORITY": 2,
    }
    for horizon, rows in priorities.items():
        rows.sort(key=lambda item: (
            lane_order.get(item.get("bridge", {}).get("recommendation_level"), 9),
            item.get("ticker") or item.get("candidate") or "",
        ))
    bridge = _ensure(state)
    priority_count = sum(len(rows) for rows in priorities.values())
    return {
        "schema_version": bridge.get("schema_version", SCHEMA_VERSION),
        "result_type": (
            "CONDITIONAL_PRIORITIES"
            if priority_count else "BRIDGE_INCOMPLETE"
            if projected else "NO_CANDIDATE_MAP"
        ),
        "value_paths": deepcopy(bridge.get("value_paths", [])),
        "host_market_snapshots": deepcopy(
            bridge.get("host_market_snapshots", [])
        ),
        "phase_by_horizon": phase_by_horizon,
        "universe_by_horizon": universe_by_horizon,
        "candidates": projected,
        "priorities_by_horizon": priorities,
        "priority_count": priority_count,
        "unresolved_candidates": unresolved,
        "boundary": (
            "Time-bounded cross-sectional research judgment only; not expected return, "
            "position sizing, an order, or a candidate lifecycle state."
        ),
    }


def dispatch_context(state, max_paths=4, candidate_tickers=None):
    """Return compact bridge context for the next model work window."""
    refresh_host_market_evidence(state)
    bridge = _ensure(state)
    paths = sorted(
        [item for item in bridge.get("value_paths", []) if isinstance(item, dict)],
        key=lambda item: (-int(item.get("last_seen_round", 0) or 0), item.get("path_id", "")),
    )[:max(0, int(max_paths))]
    trusted_snapshots = sorted(
        [
            item for item in bridge.get("host_market_snapshots", [])
            if isinstance(item, dict)
        ],
        key=lambda item: (
            item.get("market_session_date", ""), item.get("candidate_identity", "")
        ),
        reverse=True,
    )
    selected_tickers = {
        _text(value) for value in (candidate_tickers or []) if _text(value)
    }
    if selected_tickers:
        trusted_snapshots = [
            item for item in trusted_snapshots
            if _text((item.get("candidate") or {}).get("ticker"))
            in selected_tickers
        ]
    return {
        "value_paths": [{
            "path_id": item.get("path_id"),
            "origin_question_ids": item.get("origin_question_ids", []),
            "origin_direction_ids": item.get("origin_direction_ids", []),
            "state_change": item.get("state_change"),
            "constraint_change": item.get("constraint_change"),
            "profit_pool_shift": item.get("profit_pool_shift"),
            "realization_horizon": item.get("realization_horizon"),
            "falsifier": item.get("falsifier"),
            "evidence_boundary": item.get("evidence_boundary"),
        } for item in paths],
        "phase_by_horizon": {
            horizon: {
                "status": value.get("status"),
                "phase": value.get("phase"),
                "competing_phases": value.get("competing_phases", []),
                "verified_source_agents": value.get("verified_source_agents", []),
                "grounded_source_agents": value.get("grounded_source_agents", []),
            }
            for horizon, value in _phase_view(state).items()
        },
        "universe_by_horizon": {
            horizon: {
                "complete": value.get("complete"),
                "economic_member_count": len(
                    value.get("types", {}).get("ECONOMIC_EXPOSURE", {}).get(
                        "member_identities", []
                    )
                ),
                "market_member_count": len(
                    value.get("types", {}).get("MARKET_TRADING", {}).get(
                        "member_identities", []
                    )
                ),
            }
            for horizon, value in _universe_view(state).items()
        },
        "trusted_market_snapshots": [{
            "candidate_identity": item.get("candidate_identity"),
            "candidate": (item.get("candidate") or {}).get("name"),
            "ticker": (item.get("candidate") or {}).get("ticker"),
            "exchange": (item.get("candidate") or {}).get("exchange"),
            "market_session_date": item.get("market_session_date"),
            "receipt_id": item.get("receipt_id"),
            "benchmark": (item.get("market_snapshot") or {}).get("benchmark"),
            "excess_5d": (item.get("market_snapshot") or {}).get("excess_5d"),
            "excess_20d": (item.get("market_snapshot") or {}).get("excess_20d"),
            "excess_60d": (item.get("market_snapshot") or {}).get("excess_60d"),
            "volume_ratio_20d": (
                item.get("market_snapshot") or {}
            ).get("volume_ratio_20d"),
            "turnover_rate": (item.get("market_snapshot") or {}).get("turnover_rate"),
            "provider_volume_ratio": (
                item.get("market_snapshot") or {}
            ).get("provider_volume_ratio"),
            "evidence_ids": (item.get("market_snapshot") or {}).get(
                "evidence_ids", []
            ),
            "authority": "HOST_INGESTED_RECEIPT_BOUND",
        } for item in trusted_snapshots],
    }


def summary(state, candidates):
    view = report_view(state, candidates)
    return {
        "value_path_count": len(view["value_paths"]),
        "market_phase_horizon_count": len(view["phase_by_horizon"]),
        "dual_universe_horizon_count": sum(
            item.get("complete") is True
            for item in view.get("universe_by_horizon", {}).values()
        ),
        "bridge_priority_count": view["priority_count"],
        "bridge_unresolved_candidate_count": len(view["unresolved_candidates"]),
    }
