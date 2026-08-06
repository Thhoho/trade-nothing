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
# A path may occupy a role's dispatch slot at most this many times.  Without this
# cap a path whose findings are never accepted is re-assigned every round, which
# starves later paths and makes coverage unreachable inside the round fuse.
MAX_PATH_ASSIGN_ATTEMPTS = 2
EXHAUSTED_PROBE_REASON = "ASSIGNMENT_EXHAUSTED_NO_ACCEPTED_EVIDENCE"


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
    """Read legacy Landscape paths or v0.10+ Hypothesis Garden paths."""
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
    # Coverage plus the harvest-dry window is only a floor, and it assumes
    # harvesting stops the moment the last path is probed. Real runs keep finding
    # seeds, which resets that window, so the fuse needs headroom or the run dies
    # before any crux can settle.
    minimum_rounds = (
        crux_engine.recommended_max_rounds(len(paths)) if paths else 0
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
            "assign_attempts": {},
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


def _attempts(path, role):
    attempts = path.get("assign_attempts")
    if not isinstance(attempts, dict):
        return 0
    try:
        return int(attempts.get(role) or 0)
    except (TypeError, ValueError):
        return 0


def _retire_exhausted_probes(landscape, round_num):
    """Close role slots that were dispatched their full budget without acceptance.

    The probe is recorded as UNKNOWN carrying an explicit exhaustion reason, so
    coverage reflects "probed and nothing established" rather than silently
    re-queueing the path forever.
    """
    for path in landscape.get("paths", []):
        if not isinstance(path, dict):
            continue
        probes = path.setdefault("probes", {})
        for role in ROLES:
            if role in probes or _attempts(path, role) < MAX_PATH_ASSIGN_ATTEMPTS:
                continue
            probes[role] = {
                "round": int(round_num),
                "state": "UNKNOWN",
                "rationale": EXHAUSTED_PROBE_REASON,
                "evidence": [],
                "exhausted": True,
            }
        path["state"] = _aggregate(path)


def _backfill_assignment_attempts(landscape):
    """Derive attempt counters from persisted plans in legacy resumable states."""
    paths = {
        item.get("path_id"): item
        for item in landscape.get("paths", [])
        if isinstance(item, dict) and item.get("path_id")
    }
    derived = {path_id: {role: 0 for role in ROLES} for path_id in paths}
    for plan in landscape.get("round_plans", []):
        assignments = plan.get("assignments") if isinstance(plan, dict) else {}
        assignments = assignments if isinstance(assignments, dict) else {}
        for role in ROLES:
            path_ids = assignments.get(role, [])
            for path_id in path_ids if isinstance(path_ids, list) else []:
                if path_id in derived:
                    derived[path_id][role] += 1
    repaired = 0
    for path_id, path in paths.items():
        counters = path.setdefault("assign_attempts", {})
        for role in ROLES:
            before = _attempts(path, role)
            after = max(before, derived[path_id][role])
            if after != before:
                counters[role] = after
                repaired += after - before
    return repaired


def ensure_round_plan(state, round_num, dispatch_cruxes=None):
    """Assign up to two still-open paths per role, deterministically and fairly."""
    landscape = state.get("landscape_map")
    if not isinstance(landscape, dict):
        return {"round": round_num, "assignments": {role: [] for role in ROLES}}
    _backfill_assignment_attempts(landscape)
    for plan in landscape.setdefault("round_plans", []):
        if int(plan.get("round") or 0) == int(round_num):
            return plan
    _retire_exhausted_probes(landscape, round_num)
    paths = sorted(landscape.get("paths", []), key=lambda item: item.get("path_id", ""))
    dispatch_cruxes = set(dispatch_cruxes or [])
    assignments = {}
    for role in ROLES:
        pending = [
            item for item in paths
            if role not in item.get("probes", {})
            and _attempts(item, role) < MAX_PATH_ASSIGN_ATTEMPTS
        ]
        # Fewest attempts first so a stalling path cannot starve untried paths.
        pending.sort(key=lambda item: (
            _attempts(item, role),
            0 if item.get("linked_crux_id") in dispatch_cruxes else 1,
            item.get("path_id", ""),
        ))
        selected = pending[:MAX_PATHS_PER_ROLE_ROUND]
        for item in selected:
            counters = item.setdefault("assign_attempts", {})
            counters[role] = _attempts(item, role) + 1
        assignments[role] = [item["path_id"] for item in selected]
    plan = {"round": int(round_num), "assignments": assignments}
    landscape["round_plans"].append(plan)
    landscape["round_plans"].sort(key=lambda item: int(item.get("round") or 0))
    return plan


def _agent_evidence(payload, role):
    """Index the agent's own crux evidence by exact identity and by source URL.

    Roles routinely paraphrase a claim between `crux_evidence` and the matching
    `landscape_findings` entry.  Exact-identity-only matching therefore dropped
    real, well-formed citations.  The URL is the stable field, so it backs a
    fallback index; the stored citation is always the parent copy, which keeps
    the "same agent, same round, same crux" admission rule intact.
    """
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
        bucket = out.setdefault(crux_id, {"exact": {}, "by_source": {}})
        for item in group.get(field, []) if isinstance(group.get(field), list) else []:
            if not crux_engine.valid_citation(item):
                continue
            key = crux_engine.citation_identity(item)
            if not key:
                continue
            bucket["exact"][key] = item
            bucket["by_source"].setdefault(
                crux_engine.citation_source_identity(item), item
            )
    return out


def _match_agent_citation(bucket, citation):
    """Resolve a finding citation to the agent's own parent citation."""
    if not isinstance(bucket, dict):
        return None
    return crux_engine.match_agent_citation(bucket.get("exact") or {}, citation)


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
        "omitted": 0, "rejected_reasons": {}, "omitted_reasons": {},
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

    def note(reason):
        """Record a tolerated protocol deviation without discarding the finding."""
        notes = audit.setdefault("repair_notes", {})
        notes[reason] = notes.get(reason, 0) + 1

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
            if path_id in seen:
                reject(f"{role}_duplicate_path_finding")
                continue
            path = paths.get(path_id)
            if not path:
                reject(f"{role}_unknown_path")
                continue
            # Assignment is a per-round budget, not a correctness constraint.  A
            # finding on an unassigned but still-unprobed path is real work and is
            # kept; only re-probing an already-probed path is refused.
            if path_id not in assigned:
                if role in (path.get("probes") or {}):
                    reject(f"{role}_finding_outside_assignment")
                    continue
                note(f"{role}_accepted_outside_assignment")
            seen.add(path_id)
            # The engine owns the path -> crux binding.  A role that echoes the
            # wrong crux gets corrected, not discarded.
            linked = path.get("linked_crux_id")
            claimed = _text(raw.get("linked_crux_id"))
            if claimed and claimed != linked:
                note(f"{role}_linked_crux_corrected")
            # An unparseable state is epistemically UNKNOWN, which is exactly what
            # the engine would record anyway; discarding the probe instead just
            # hides that the path was looked at.
            finding_state = _text(raw.get("state")).upper()
            if finding_state not in FINDING_STATES:
                note(f"{role}_unreadable_state_treated_as_unknown")
                finding_state = "UNKNOWN"
            accepted_evidence, evidence_seen = [], set()
            bucket = allowed.get(linked, {})
            for citation in raw.get("evidence", []) if isinstance(raw.get("evidence"), list) else []:
                matched = _match_agent_citation(bucket, citation)
                if matched is None:
                    continue
                key = crux_engine.citation_identity(matched)
                if key and key not in evidence_seen:
                    evidence_seen.add(key)
                    accepted_evidence.append(deepcopy(matched))
            probe = {
                "round": int(round_num),
                "state": finding_state,
                "rationale": _text(raw.get("rationale")),
                "evidence": accepted_evidence,
            }
            # An unsupported directional claim is downgraded to UNKNOWN rather than
            # dropped.  "Probed, nothing established" is the honest outcome; leaving
            # the path UNPROBED just burns budget and hides that a probe happened.
            if finding_state != "UNKNOWN" and not accepted_evidence:
                probe.update({
                    "state": "UNKNOWN",
                    "downgraded_from": finding_state,
                    "downgrade_reason": "NO_AGENT_EVIDENCE_BOUND_TO_CLAIM",
                })
                note(f"{role}_downgraded_unsupported_claim")
            if claimed and claimed != linked:
                probe["claimed_crux_id"] = claimed
            path.setdefault("probes", {})[role] = probe
            path["state"] = _aggregate(path)
            audit["accepted"] += 1
        # Never submitted is an omission, not a discarded submission; counting it
        # as a rejection makes the discard rate exceed 100%.
        for missing in sorted(assigned - seen):
            audit["omitted"] = audit.get("omitted", 0) + 1
            omissions = audit.setdefault("omitted_reasons", {})
            key = f"{role}_assigned_path_missing_finding"
            omissions[key] = omissions.get(key, 0) + 1
    audit.update(summary(state))
    return audit


def path_for_seed(state, path_id):
    return _path_by_id(state).get(_text(path_id))


# Seed relation types and path archetypes describe the same capture structures in
# two vocabularies. Only unambiguous correspondences are listed; SECOND_ORDER and
# COMPETITOR_WINNER are deliberately absent because they fit several archetypes.
RELATION_TO_ARCHETYPE = {
    "DIRECT_WINNER": "DIRECT_CAPTURE",
    "BOTTLENECK_OWNER": "BOTTLENECK_OWNER",
    "SUBSTITUTE_WINNER": "SUBSTITUTE_OR_AVOIDANCE",
    "SHORT_CANDIDATE": "ADVERSE_EXPOSURE",
    "INFRA_ASSET_OWNER": "ENABLER_OR_INPUT",
}


def paths_for_crux(state, origin_crux):
    origin = _text(origin_crux)
    return [
        item for item in state.get("landscape_map", {}).get("paths", [])
        if isinstance(item, dict) and item.get("linked_crux_id") == origin
    ]


def resolve_seed_path(state, path_id, origin_crux, relation_type=""):
    """Return (resolved_path_id, issues, repaired).

    The engine owns the crux -> path mapping, so a seed that omits the path is
    bound automatically when the origin crux — narrowed if needed by the
    relation/archetype correspondence — identifies exactly one path. Discarding
    real candidate evidence over an ID the engine can derive was destroying the
    primary output of opportunity runs.
    """
    if not isinstance(state.get("landscape_map"), dict):
        return _text(path_id), [], False
    path_id = _text(path_id)
    if not path_id:
        matches = paths_for_crux(state, origin_crux)
        if not matches:
            return "", ["missing_landscape_path_id"], False
        if len(matches) == 1:
            return matches[0].get("path_id"), [], True
        archetype = RELATION_TO_ARCHETYPE.get(_text(relation_type).upper())
        narrowed = [
            item for item in matches if item.get("archetype") == archetype
        ] if archetype else []
        if len(narrowed) == 1:
            return narrowed[0].get("path_id"), [], True
        return "", ["ambiguous_landscape_path_for_origin_crux"], False
    path = path_for_seed(state, path_id)
    if not path:
        return path_id, ["unknown_landscape_path_id"], False
    if path.get("linked_crux_id") != _text(origin_crux):
        return path_id, ["landscape_path_origin_mismatch"], False
    return path_id, [], False


def seed_binding_issues(state, path_id, origin_crux):
    return resolve_seed_path(state, path_id, origin_crux)[1]


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


def coverage_work_remaining(state):
    """Path/role slots that can still be probed inside the assignment budget.

    Coverage blocks convergence only while real work is still possible.  Once a
    path has spent its budget it retires as UNKNOWN, so an unreachable path can
    never deadlock the run.
    """
    remaining = []
    for path in state.get("landscape_map", {}).get("paths", []):
        if not isinstance(path, dict):
            continue
        probes = path.get("probes") if isinstance(path.get("probes"), dict) else {}
        for role in ROLES:
            if role not in probes and _attempts(path, role) < MAX_PATH_ASSIGN_ATTEMPTS:
                remaining.append(f"{path.get('path_id')}:{role}")
    return sorted(remaining)


def finalize_coverage(state, round_num):
    """Close out exhausted role slots so a finished run reports honest coverage."""
    landscape = state.get("landscape_map")
    if isinstance(landscape, dict):
        _retire_exhausted_probes(landscape, round_num)
    return summary(state)


def summary(state):
    paths = [
        item for item in state.get("landscape_map", {}).get("paths", [])
        if isinstance(item, dict)
    ]
    counts = {name: 0 for name in PATH_STATES}
    exhausted = []
    probe_slots_completed = 0
    partially_probed = 0
    for path in paths:
        counts[path.get("state") if path.get("state") in PATH_STATES else "UNPROBED"] += 1
        probes = path.get("probes") if isinstance(path.get("probes"), dict) else {}
        completed_for_path = sum(role in probes for role in ROLES)
        probe_slots_completed += completed_for_path
        if 0 < completed_for_path < len(ROLES):
            partially_probed += 1
        if any(
            isinstance(probe, dict) and probe.get("exhausted")
            for probe in probes.values()
        ):
            exhausted.append(path.get("path_id"))
    established = counts["SUPPORTED"] + counts["REJECTED"]
    probe_slots_total = len(paths) * len(ROLES)
    return {
        # Requirement comes from the declared research contract, not from the
        # accidental presence of path rows. Otherwise a missing Landscape map
        # makes its own coverage gate disappear.
        "required": is_required(state),
        "path_count": len(paths),
        "unprobed_count": counts["UNPROBED"],
        "supported_count": counts["SUPPORTED"],
        "rejected_count": counts["REJECTED"],
        "unknown_count": counts["UNKNOWN"],
        "exhausted_path_ids": sorted(item for item in exhausted if item),
        "coverage_complete": bool(paths) and counts["UNPROBED"] == 0,
        "established_count": established,
        "coverage_ratio": round(established / len(paths), 4) if paths else 0.0,
        "partially_probed_count": partially_probed,
        "probe_slots_completed": probe_slots_completed,
        "probe_slots_total": probe_slots_total,
        "probe_slot_coverage_ratio": (
            round(probe_slots_completed / probe_slots_total, 4)
            if probe_slots_total else 0.0
        ),
        "paths": deepcopy(paths),
        "round_plans": deepcopy(state.get("landscape_map", {}).get("round_plans", [])),
    }
