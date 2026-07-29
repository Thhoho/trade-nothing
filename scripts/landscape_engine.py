#!/usr/bin/env python3
"""Deterministic Landscape Map coverage for opportunity-oriented v2 research.

The Framer proposes entity-agnostic value-transfer paths. The engine assigns every
path to both research roles under a fixed budget, accepts only same-role structured
evidence, and keeps coverage separate from candidate promotion. A map is a search
plan and audit ledger, not evidence or a trade signal.
"""
from copy import deepcopy
import math

import crux_engine


ARCHETYPES = {
    "DIRECT_CAPTURE",
    "BOTTLENECK_OWNER",
    "ENABLER_OR_INPUT",
    "SUBSTITUTE_OR_AVOIDANCE",
    "ADVERSE_EXPOSURE",
}
PATH_STATES = {"UNPROBED", "SUPPORTED", "REJECTED", "UNKNOWN"}
FINDING_STATES = PATH_STATES - {"UNPROBED"}
ROLES = ("detective", "inquisitor")
MAX_PATHS_PER_ROLE_ROUND = 2


def _text(value):
    return " ".join(str(value or "").split())


def research_intent(frame_or_state):
    """Return explicit intent, with a conservative legacy inference."""
    explicit = _text(frame_or_state.get("research_intent")).upper()
    if not explicit:
        explicit = _text(
            (frame_or_state.get("frame_contract") or {}).get("research_intent")
        ).upper()
    if explicit in {"THESIS_CHALLENGE", "OPPORTUNITY_DISCOVERY", "HYBRID"}:
        return explicit
    cruxes = frame_or_state.get("candidate_cruxes")
    if cruxes is None:
        cruxes = [
            {"logic_role": item.get("logic_role")}
            for item in frame_or_state.get("cruxes", {}).values()
            if isinstance(item, dict)
        ]
    if any(
        _text(item.get("logic_role")).upper() == "OPPORTUNITY_PATH"
        for item in cruxes or [] if isinstance(item, dict)
    ):
        return "HYBRID"
    if isinstance(frame_or_state.get("landscape_map"), dict):
        return "HYBRID"
    if isinstance(frame_or_state.get("hypothesis_garden"), dict):
        return "HYBRID"
    return "THESIS_CHALLENGE"


def frame_paths(frame):
    """Read legacy Landscape paths or v0.10 Hypothesis Garden paths."""
    garden = frame.get("hypothesis_garden")
    if isinstance(garden, list):
        return garden
    if isinstance(garden, dict) and isinstance(garden.get("wild_hypotheses"), list):
        return garden["wild_hypotheses"]
    top_level = frame.get("wild_hypotheses")
    if isinstance(top_level, list):
        return top_level
    legacy = frame.get("landscape_map")
    if isinstance(legacy, dict) and isinstance(legacy.get("paths"), list):
        return legacy["paths"]
    return []


def is_required(frame_or_state):
    """Return whether the question explicitly asks for opportunity-path discovery."""
    if research_intent(frame_or_state) in {"OPPORTUNITY_DISCOVERY", "HYBRID"}:
        return True
    question_type = _text(frame_or_state.get("question_type")).upper()
    if question_type in {"UNIVERSE_SEARCH", "COMPARATIVE"}:
        return True
    cruxes = frame_or_state.get("candidate_cruxes")
    if cruxes is None:
        cruxes = [
            {"logic_role": item.get("logic_role")}
            for item in frame_or_state.get("cruxes", {}).values()
            if isinstance(item, dict)
        ]
    return any(
        _text(item.get("logic_role")).upper() == "OPPORTUNITY_PATH"
        for item in cruxes or [] if isinstance(item, dict)
    )


def validate_frame(frame):
    """Validate the entity-agnostic map without treating hypotheses as evidence."""
    if not is_required(frame):
        return []
    paths = frame_paths(frame)
    if not paths:
        if _text(frame.get("research_intent")).upper() in {
            "OPPORTUNITY_DISCOVERY", "HYBRID",
        }:
            return ["opportunity_intent_requires_hypothesis_garden_or_landscape_map"]
        return ["opportunity_question_requires_landscape_map"]
    issues = []
    if not 5 <= len(paths) <= 7:
        issues.append("landscape_requires_5_to_7_paths")
    try:
        suggested_rounds = int(frame.get("suggested_max_rounds"))
    except (TypeError, ValueError):
        suggested_rounds = 0
    # A Universe search may still harvest a new seed in the round that completes
    # Landscape coverage.  Reserve the full deterministic harvest-dry window
    # *after* the worst-case coverage round; otherwise a valid frame can hit the
    # fuse before convergence is even possible.
    minimum_rounds = (
        max(
            crux_engine.MIN_ROUNDS,
            math.ceil(len(paths) / MAX_PATHS_PER_ROLE_ROUND)
            + crux_engine.UNIVERSE_HARVEST_DRY_ROUNDS,
        )
        if paths else 0
    )
    if suggested_rounds < minimum_rounds:
        issues.append(f"landscape_requires_at_least_{minimum_rounds}_rounds")
    crux_ids = {
        _text(item.get("id")) for item in frame.get("candidate_cruxes", [])
        if isinstance(item, dict) and _text(item.get("id"))
    }
    seen_ids, seen_hypotheses = set(), set()
    present_archetypes = set()
    for index, path in enumerate(paths):
        prefix = f"landscape_path_{index + 1}"
        if not isinstance(path, dict):
            issues.append(f"{prefix}_must_be_object")
            continue
        path_id = _text(path.get("path_id"))
        if not path_id:
            issues.append(f"{prefix}_missing_path_id")
        elif path_id in seen_ids:
            issues.append(f"landscape_duplicate_path_id_{path_id}")
        seen_ids.add(path_id)
        linked = _text(path.get("linked_crux_id"))
        if linked not in crux_ids:
            issues.append(f"{prefix}_unknown_linked_crux_id")
        archetype = _text(path.get("archetype")).upper()
        if archetype not in ARCHETYPES:
            issues.append(f"{prefix}_invalid_archetype")
        else:
            present_archetypes.add(archetype)
        hypothesis = _text(path.get("hypothesis"))
        if not hypothesis:
            issues.append(f"{prefix}_missing_hypothesis")
        elif hypothesis.lower() in seen_hypotheses:
            issues.append(f"{prefix}_duplicate_hypothesis")
        seen_hypotheses.add(hypothesis.lower())
        if _text(path.get("hypothesis_status")).upper() not in {
            "HYPOTHESIS", "HYPOTHESIS_ONLY",
        }:
            issues.append(f"{prefix}_must_start_as_hypothesis")
        for field in ("economic_capture_test", "pricing_question", "falsifier"):
            if not _text(path.get(field)):
                issues.append(f"{prefix}_missing_{field}")
        chain = path.get("value_transfer_chain")
        if not isinstance(chain, list) or not 3 <= len(chain) <= 6:
            issues.append(f"{prefix}_value_transfer_chain_requires_3_to_6_nodes")
        elif any(not _text(node) for node in chain):
            issues.append(f"{prefix}_value_transfer_chain_has_empty_node")
        queries = path.get("search_queries")
        if not isinstance(queries, list) or len(queries) != 2:
            issues.append(f"{prefix}_requires_exactly_two_search_queries")
        elif any(not _text(query) for query in queries):
            issues.append(f"{prefix}_has_empty_search_query")
        elif len({_text(query).lower() for query in queries}) != 2:
            issues.append(f"{prefix}_search_queries_must_be_distinct")
    missing = sorted(ARCHETYPES - present_archetypes)
    if missing:
        issues.append("landscape_missing_archetypes:" + ",".join(missing))
    return sorted(set(issues))


def initialize(frame):
    """Convert a valid Framer map into immutable hypotheses plus mutable probe state."""
    if not is_required(frame):
        return None
    paths = []
    for raw in frame_paths(frame):
        paths.append({
            "hypothesis_id": _text(raw.get("hypothesis_id")) or None,
            "path_id": _text(raw.get("path_id")),
            "archetype": _text(raw.get("archetype")).upper(),
            "linked_crux_id": _text(raw.get("linked_crux_id")),
            "hypothesis": _text(raw.get("hypothesis")),
            "hypothesis_status": "HYPOTHESIS_ONLY",
            "value_transfer_chain": [_text(item) for item in raw.get("value_transfer_chain", [])],
            "economic_capture_test": _text(raw.get("economic_capture_test")),
            "pricing_question": _text(raw.get("pricing_question")),
            "falsifier": _text(raw.get("falsifier")),
            "search_queries": [_text(item) for item in raw.get("search_queries", [])],
            "state": "UNPROBED",
            "probes": {},
        })
    paths.sort(key=lambda item: item["path_id"])
    return {
        "schema_version": "trade-nothing.landscape-map.v1",
        "required_roles": list(ROLES),
        "max_paths_per_role_round": MAX_PATHS_PER_ROLE_ROUND,
        "paths": paths,
        "round_plans": [],
    }


def _path_by_id(state):
    return {
        item.get("path_id"): item
        for item in state.get("landscape_map", {}).get("paths", [])
        if isinstance(item, dict) and item.get("path_id")
    }


def ensure_round_plan(state, round_num, dispatch_cruxes=None):
    """Assign the first two role-unprobed paths to each role, deterministically."""
    landscape = state.get("landscape_map")
    if not isinstance(landscape, dict):
        return {"round": round_num, "assignments": {role: [] for role in ROLES}}
    for plan in landscape.setdefault("round_plans", []):
        if int(plan.get("round") or 0) == int(round_num):
            return plan
    paths = sorted(landscape.get("paths", []), key=lambda item: item.get("path_id", ""))
    dispatch_cruxes = set(dispatch_cruxes or [])
    assignments = {}
    for role in ROLES:
        pending = [
            item for item in paths
            if role not in item.get("probes", {})
        ]
        pending.sort(key=lambda item: (
            0 if item.get("linked_crux_id") in dispatch_cruxes else 1,
            item.get("path_id", ""),
        ))
        assignments[role] = [
            item["path_id"] for item in pending[:MAX_PATHS_PER_ROLE_ROUND]
        ]
    plan = {"round": int(round_num), "assignments": assignments}
    landscape["round_plans"].append(plan)
    landscape["round_plans"].sort(key=lambda item: int(item.get("round") or 0))
    return plan


def _agent_evidence(payload, role):
    payload = payload if isinstance(payload, dict) else {}
    if role == "detective":
        groups, field = payload.get("crux_evidence", []), "evidence"
    else:
        groups, field = payload.get("crux_attacks", []), "attacks"
    out = {}
    for group in groups if isinstance(groups, list) else []:
        if not isinstance(group, dict):
            continue
        crux_id = _text(group.get("crux_id"))
        bucket = out.setdefault(crux_id, {})
        for item in group.get(field, []) if isinstance(group.get(field), list) else []:
            key = crux_engine.citation_identity(item)
            if key and crux_engine.valid_citation(item):
                bucket[key] = item
    return out


def _aggregate(path):
    probes = path.get("probes", {})
    if any(role not in probes for role in ROLES):
        return "UNPROBED"
    states = {probes[role].get("state") for role in ROLES}
    if states <= {"SUPPORTED", "UNKNOWN"} and "SUPPORTED" in states:
        return "SUPPORTED"
    if states <= {"REJECTED", "UNKNOWN"} and "REJECTED" in states:
        return "REJECTED"
    return "UNKNOWN"


def ingest_round(state, round_num, detective=None, inquisitor=None):
    """Accept only assigned, same-agent, same-crux evidence-backed path findings."""
    landscape = state.get("landscape_map")
    audit = {
        "round": int(round_num), "submitted": 0, "accepted": 0, "rejected": 0,
        "rejected_reasons": {},
    }
    if not isinstance(landscape, dict):
        audit.update(summary(state))
        return audit
    plan = ensure_round_plan(state, round_num)
    paths = _path_by_id(state)

    def reject(reason):
        audit["rejected"] += 1
        reasons = audit["rejected_reasons"]
        reasons[reason] = reasons.get(reason, 0) + 1

    for role, payload in (("detective", detective), ("inquisitor", inquisitor)):
        payload = payload if isinstance(payload, dict) else {}
        findings = payload.get("landscape_findings", [])
        findings = findings if isinstance(findings, list) else []
        audit["submitted"] += len(findings)
        assigned = set(plan.get("assignments", {}).get(role, []))
        allowed = _agent_evidence(payload, role)
        seen = set()
        for raw in findings:
            if not isinstance(raw, dict):
                reject(f"{role}_finding_not_object")
                continue
            path_id = _text(raw.get("path_id"))
            if path_id not in assigned:
                reject(f"{role}_finding_outside_assignment")
                continue
            if path_id in seen:
                reject(f"{role}_duplicate_path_finding")
                continue
            seen.add(path_id)
            path = paths.get(path_id)
            if not path:
                reject(f"{role}_unknown_path")
                continue
            linked = path.get("linked_crux_id")
            if _text(raw.get("linked_crux_id")) != linked:
                reject(f"{role}_linked_crux_mismatch")
                continue
            finding_state = _text(raw.get("state")).upper()
            if finding_state not in FINDING_STATES:
                reject(f"{role}_invalid_finding_state")
                continue
            accepted_evidence, evidence_seen = [], set()
            for citation in raw.get("evidence", []) if isinstance(raw.get("evidence"), list) else []:
                key = crux_engine.citation_identity(citation)
                if key and key in allowed.get(linked, {}) and key not in evidence_seen:
                    evidence_seen.add(key)
                    accepted_evidence.append(deepcopy(allowed[linked][key]))
            if finding_state != "UNKNOWN" and not accepted_evidence:
                reject(f"{role}_non_unknown_requires_agent_evidence")
                continue
            path.setdefault("probes", {})[role] = {
                "round": int(round_num),
                "state": finding_state,
                "rationale": _text(raw.get("rationale")),
                "evidence": accepted_evidence,
            }
            path["state"] = _aggregate(path)
            audit["accepted"] += 1
        for missing in sorted(assigned - seen):
            reject(f"{role}_assigned_path_missing_finding")
    audit.update(summary(state))
    return audit


def path_for_seed(state, path_id):
    return _path_by_id(state).get(_text(path_id))


def seed_binding_issues(state, path_id, origin_crux):
    if not isinstance(state.get("landscape_map"), dict):
        return []
    if not _text(path_id):
        return ["missing_landscape_path_id"]
    path = path_for_seed(state, path_id)
    if not path:
        return ["unknown_landscape_path_id"]
    if path.get("linked_crux_id") != _text(origin_crux):
        return ["landscape_path_origin_mismatch"]
    return []


def seed_readiness_blockers(state, seed):
    issues = seed_binding_issues(state, seed.get("landscape_path_id"), seed.get("origin_crux"))
    if issues:
        return issues
    if not isinstance(state.get("landscape_map"), dict):
        return []
    path = path_for_seed(state, seed.get("landscape_path_id"))
    if path and path.get("state") != "SUPPORTED":
        return ["landscape_path_not_supported"]
    return []


def summary(state):
    paths = [
        item for item in state.get("landscape_map", {}).get("paths", [])
        if isinstance(item, dict)
    ]
    counts = {name: 0 for name in PATH_STATES}
    for path in paths:
        counts[path.get("state") if path.get("state") in PATH_STATES else "UNPROBED"] += 1
    return {
        "required": bool(paths),
        "path_count": len(paths),
        "unprobed_count": counts["UNPROBED"],
        "supported_count": counts["SUPPORTED"],
        "rejected_count": counts["REJECTED"],
        "unknown_count": counts["UNKNOWN"],
        "coverage_complete": bool(paths) and counts["UNPROBED"] == 0,
        "paths": deepcopy(paths),
        "round_plans": deepcopy(state.get("landscape_map", {}).get("round_plans", [])),
    }
