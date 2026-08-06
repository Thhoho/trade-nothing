#!/usr/bin/env python3
"""Deterministic feasibility checks for a research frame.

Framing may not browse, so this module does not pretend that a source exists. It
does require every researchable crux to freeze two genuinely different source
routes and verifies that the proposed round fuse can accommodate deterministic
crux rotation, Landscape coverage, and the post-coverage dry window.
"""
from __future__ import annotations

import math
from typing import Any

import crux_engine
import landscape_engine


PUBLISHER_CLASSES = {
    "ISSUER_OR_FILING",
    "CUSTOMER_OR_COUNTERPARTY",
    "REGULATOR_OR_OFFICIAL_DATASET",
    "EXCHANGE_OR_MARKET_DATA",
    "PROJECT_OWNER",
    "CREDITOR_OR_FINANCING_COUNTERPARTY",
    "INDEPENDENT_INDUSTRY_SOURCE",
}
MIN_EVIDENCE_ROUTES = crux_engine.MIN_VALID_CITATIONS
MAX_EVIDENCE_ROUTES = 3
MAX_CRUXES_PER_ROUND = crux_engine.MAX_CRUXES_PER_ROUND


def settlement_touches_per_crux(frame: dict[str, Any]) -> int:
    """Minimum scheduled touches that make a complete settlement route possible.

    A directional root crux needs three evidence-bearing contested touches. An
    unresolved crux may settle sooner because source acquisition and bilateral
    decision-dry probing can occur in the same touch; they must not be summed as
    if the engine required two serial phases. UNIVERSE_SEARCH has separate
    coverage semantics, but still needs one directional touch and the source
    minimum.
    """
    question_type = _text(frame.get("question_type")).upper()
    if question_type == "UNIVERSE_SEARCH":
        return max(1, crux_engine.MIN_VALID_CITATIONS)
    return max(
        crux_engine.MIN_CONTESTED,
        crux_engine.MIN_VALID_CITATIONS,
        crux_engine.EVIDENCE_EXHAUSTION_DRY_ROUNDS,
    )


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _researchable(frame: dict[str, Any]) -> bool:
    precheck = frame.get("no_edge_precheck")
    return isinstance(precheck, dict) and precheck.get("is_researchable") is True


def validate_evidence_plans(frame: dict[str, Any]) -> list[str]:
    """Require bounded, publisher-diverse routes for every initial crux."""
    if not isinstance(frame, dict) or not _researchable(frame):
        return []
    issues: list[str] = []
    for index, crux in enumerate(frame.get("candidate_cruxes") or []):
        if not isinstance(crux, dict):
            continue
        crux_id = _text(crux.get("id")) or str(index + 1)
        prefix = f"crux_{crux_id}_evidence_plan"
        plan = crux.get("evidence_plan")
        if not isinstance(plan, list):
            issues.append(f"{prefix}_required")
            continue
        if not MIN_EVIDENCE_ROUTES <= len(plan) <= MAX_EVIDENCE_ROUTES:
            issues.append(
                f"{prefix}_requires_{MIN_EVIDENCE_ROUTES}_to_{MAX_EVIDENCE_ROUTES}_routes"
            )
        seen_ids: set[str] = set()
        publisher_classes: set[str] = set()
        queries: list[str] = []
        for route_index, route in enumerate(plan):
            route_prefix = f"{prefix}_{route_index + 1}"
            if not isinstance(route, dict):
                issues.append(f"{route_prefix}_must_be_object")
                continue
            plan_id = _text(route.get("plan_id"))
            if not plan_id:
                issues.append(f"{route_prefix}_missing_plan_id")
            elif plan_id in seen_ids:
                issues.append(f"{prefix}_duplicate_plan_id_{plan_id}")
            seen_ids.add(plan_id)
            publisher_class = _text(route.get("publisher_class")).upper()
            if publisher_class not in PUBLISHER_CLASSES:
                issues.append(f"{route_prefix}_invalid_publisher_class")
            else:
                publisher_classes.add(publisher_class)
            if not _text(route.get("target_claim")):
                issues.append(f"{route_prefix}_missing_target_claim")
            query = _text(route.get("search_query"))
            if not query:
                issues.append(f"{route_prefix}_missing_search_query")
            queries.append(query.lower())
        if len(publisher_classes) < MIN_EVIDENCE_ROUTES:
            issues.append(f"{prefix}_requires_two_publisher_classes")
        nonempty_queries = [query for query in queries if query]
        if len(set(nonempty_queries)) != len(nonempty_queries):
            issues.append(f"{prefix}_search_queries_must_be_distinct")
    return sorted(set(issues))


def _simulated_active_rounds(frame: dict[str, Any]) -> int:
    """Simulate fair crux rotation until every crux gets settlement capacity."""
    crux_ids = sorted(
        _text(item.get("id"))
        for item in frame.get("candidate_cruxes") or []
        if isinstance(item, dict) and _text(item.get("id"))
    )
    remaining = {
        crux_id: settlement_touches_per_crux(frame) for crux_id in crux_ids
    }
    last_scored = {crux_id: 0 for crux_id in crux_ids}
    round_num = 0
    hard_limit = crux_engine.MAX_ROUNDS * 2
    while any(value > 0 for value in remaining.values()) and round_num < hard_limit:
        round_num += 1
        ranked = sorted(
            (crux_id for crux_id in crux_ids if remaining[crux_id] > 0),
            key=lambda crux_id: (
                -remaining[crux_id],
                last_scored[crux_id],
                crux_id,
            ),
        )
        dispatched = ranked[:MAX_CRUXES_PER_ROUND]
        for crux_id in dispatched:
            remaining[crux_id] -= 1
            last_scored[crux_id] = round_num
    return round_num


def minimum_rounds(frame: dict[str, Any]) -> int:
    """Return a conservative fuse that leaves room for post-work stability."""
    if not isinstance(frame, dict) or not _researchable(frame):
        return crux_engine.MIN_ROUNDS
    active_rounds = _simulated_active_rounds(frame)
    if landscape_engine.is_required(frame):
        coverage_rounds = math.ceil(
            len(landscape_engine.frame_paths(frame))
            / landscape_engine.MAX_PATHS_PER_ROLE_ROUND
        )
        # Harvest-dry rounds may overlap later crux rotation. Adding them after
        # every crux settles would over-budget the frame; adding them only after
        # bilateral Landscape coverage preserves the actual convergence rule.
        return max(
            crux_engine.MIN_ROUNDS,
            active_rounds,
            coverage_rounds + crux_engine.UNIVERSE_HARVEST_DRY_ROUNDS,
        )
    return max(crux_engine.MIN_ROUNDS, active_rounds)


def validate_round_budget(frame: dict[str, Any]) -> list[str]:
    if not isinstance(frame, dict) or not _researchable(frame):
        return []
    try:
        suggested = int(frame.get("suggested_max_rounds"))
    except (TypeError, ValueError):
        suggested = 0
    minimum = minimum_rounds(frame)
    if suggested < minimum:
        return [f"framing_feasibility_requires_at_least_{minimum}_rounds"]
    return []


def validate_frame(frame: dict[str, Any]) -> list[str]:
    return sorted(set(validate_evidence_plans(frame) + validate_round_budget(frame)))
