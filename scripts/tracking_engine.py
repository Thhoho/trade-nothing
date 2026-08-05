#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic tracking-track engine for the v0.12 path-led research upgrade.

The tracking track answers a second, independent question per research path:
"even though the formal evidence gates are not passed, is the payoff structure
good enough that this path deserves continued tracking?"

It runs in parallel with the fail-closed evidence track. Tracking NEVER changes
crux scores, convergence, screening, promotion, or the validator contracts. A
tracked candidate is explicitly not promotable and never a recommendation; the
tracking ledger is a research state, not a probability, expected-return, or
position-sizing input.
"""
import copy
from datetime import date

import opportunity_engine


ACTIVE = "ACTIVE"
ESCALATED = "ESCALATED"
CLOSED = "CLOSED"

MIN_CHAIN_NODES = 3


def _has_named_checkpoints(seed):
    return bool(
        opportunity_engine._text(seed.get("catalyst"))
        and opportunity_engine._text(seed.get("falsifier"))
    )


def _chain_nodes(seed):
    chain = seed.get("causal_chain")
    if isinstance(chain, list) and chain:
        nodes = [opportunity_engine._text(n) for n in chain]
    else:
        nodes = opportunity_engine._split_causal_path(seed.get("causal_path"))
    return [n for n in nodes if n]


def tracking_assessment(state, seed):
    """Deterministic admission check for the tracking ledger.

    Returns {"admitted": bool, "reasons": [str]}. A seed is admitted when it is
    formally blocked (not yet ready for screening), not rejected, and all three
    hold: substantive odds declaration, a complete causal chain, and named
    upgrade/abandon checkpoints.
    """
    reasons = []
    if not isinstance(seed, dict) or not seed.get("seed_id"):
        reasons.append("missing_seed_id")
        return {"admitted": False, "reasons": reasons}
    promotion = opportunity_engine.promotion_assessment(state, seed)
    candidate_state = promotion["candidate_state"]
    if candidate_state == opportunity_engine.REJECTED:
        reasons.append("rejected_by_screen")
        return {"admitted": False, "reasons": reasons}
    if candidate_state in (
        opportunity_engine.READY,
        opportunity_engine.WATCHLIST,
        opportunity_engine.THESIS_CANDIDATE,
        opportunity_engine.VERIFIED_FOR_HUMAN,
    ):
        reasons.append("already_on_formal_track")
        return {"admitted": False, "reasons": reasons}
    # Primary odds path: linked hypothesis asymmetry_case.
    odds = opportunity_engine.odds_summary(seed)
    # Fallback: seed has chain + checkpoints but no formal odds declaration.
    if not odds:
        odds = _odds_fallback(seed)
    if not odds:
        reasons.append("no_substantive_odds")
    if len(_chain_nodes(seed)) < MIN_CHAIN_NODES:
        reasons.append("chain_too_short")
    if not _has_named_checkpoints(seed):
        reasons.append("missing_checkpoints")
    return {"admitted": not reasons, "reasons": reasons}


def _ledger_entry(seed, round_num, failure_signal=None):
    return {
        "seed_id": seed.get("seed_id"),
        "candidate": opportunity_engine._text(seed.get("candidate")),
        "entered_round": int(round_num or 0),
        "entered_decision_question": "",
        "status": ACTIVE,
        "close_reason": None,
        "failure_signal": failure_signal or None,
        "tracking_until": None,
        "odds_posture": _odds_posture(seed),
    }


def _prune_closed_entries(state, current_round, max_age=6):
    """Move stale CLOSED entries to an archive key so the ledger doesn't grow unbounded."""
    ledger = state.get("tracking_ledger", {})
    archive = state.setdefault("tracking_ledger_archive", {})
    for seed_id, entry in list(ledger.items()):
        if entry.get("status") != CLOSED:
            continue
        age = int(current_round or 0) - int(entry.get("entered_round", current_round) or 0)
        if age >= max_age:
            archive[seed_id] = ledger.pop(seed_id)


def _odds_fallback(seed):
    """Return a degraded odds posture when the linked hypothesis has no asymmetry_case.

    A seed with named checkpoints and a non-trivial causal chain still represents a
    monitorable path even without a formal odds declaration. The fallback posture is
    explicitly labelled as degraded so the report can distinguish it.
    """
    nodes = _chain_nodes(seed)
    if len(nodes) >= MIN_CHAIN_NODES and _has_named_checkpoints(seed):
        return {
            "qualitative": "退化赔率(假设未声明非对称结构)",
            "basis": "仅逻辑链+检查点,待补充asymmetry_case",
            "break_even": None,
            "has_numeric_payoff": False,
        }
    return None


def _odds_posture(seed):
    odds = opportunity_engine.odds_summary(seed) or _odds_fallback(seed)
    if not odds:
        return None
    if odds.get("has_numeric_payoff"):
        be = odds.get("break_even") or {}
        return f"break-even {be.get('p_star_percent')}%"
    return odds.get("qualitative") or "已声明"


def _failure_signals_from_payload(payload, state):
    """Extract Inquisitor odds-calibration failure signals, matched by seed_id.

    Matching by candidate name string is fragile (Inquisitor may reword the name).
    We resolve each Inquisitor-submitted seed through the same entity-identity key
    so the signal reaches the correct tracking ledger entry even when names differ.
    """
    if not isinstance(payload, dict):
        return {}
    # Build a lookup from entity_identity to seed_id for existing seeds so we can
    # match Inquisitor payload seeds even when the raw candidate name varies.
    existing_by_entity = {}
    for seed in state.get("opportunity_seeds", []):
        if not isinstance(seed, dict) or not seed.get("seed_id"):
            continue
        identity = opportunity_engine.entity_identity(seed)
        if identity:
            existing_by_entity[identity] = seed["seed_id"]
    signals = {}
    for raw in payload.get("opportunity_seeds", []) or []:
        if not isinstance(raw, dict):
            continue
        calibration = raw.get("odds_calibration")
        if not isinstance(calibration, dict):
            continue
        signal = opportunity_engine._text(calibration.get("failure_signal"))
        if not signal:
            continue
        # Resolve by entity identity first (robust to name rewording), then fall
        # back to candidate name for seeds not yet in the ledger.
        entity_key = opportunity_engine.entity_identity(raw)
        seed_id = existing_by_entity.get(entity_key) if entity_key else None
        if seed_id:
            signals[seed_id] = signal
        else:
            name = opportunity_engine._text(raw.get("candidate"))
            if name:
                signals[name] = signal
    return signals


def sync_tracking_ledger(state, round_num=0, odds_payload=None):
    """Reconcile the tracking ledger with the current seed set.

    - Newly blocked seeds that satisfy admission enter as ACTIVE.
    - ACTIVE entries whose seed escalated to the formal track become ESCALATED.
    - ACTIVE entries whose seed was rejected are closed with a reason.
    - Existing ACTIVE entries are never re-entered or downgraded.
    - Inquisitor odds-calibration failure signals are attached at admission.
    """
    ledger = state.setdefault("tracking_ledger", {})
    signals = _failure_signals_from_payload(odds_payload, state)
    for seed in state.get("opportunity_seeds", []):
        if not isinstance(seed, dict) or not seed.get("seed_id"):
            continue
        entry = ledger.get(seed["seed_id"])
        if entry:
            if entry.get("status") != ACTIVE:
                continue
            promotion = opportunity_engine.promotion_assessment(state, seed)
            if promotion["candidate_state"] == opportunity_engine.REJECTED:
                entry["status"] = CLOSED
                entry["close_reason"] = "rejected_by_screen"
            elif promotion["candidate_state"] in (
                opportunity_engine.READY,
                opportunity_engine.WATCHLIST,
                opportunity_engine.THESIS_CANDIDATE,
                opportunity_engine.VERIFIED_FOR_HUMAN,
            ):
                entry["status"] = ESCALATED
            # Attach/refresh failure_signal from later Inquisitor rounds.
            fresh_signal = signals.get(seed["seed_id"])
            if fresh_signal:
                entry["failure_signal"] = fresh_signal
            continue
        assessment = tracking_assessment(state, seed)
        if assessment["admitted"]:
            entry = _ledger_entry(seed, round_num)
            # Match by seed_id first, then by candidate name (legacy fallback).
            entry["failure_signal"] = signals.get(
                seed["seed_id"]
            ) or signals.get(
                opportunity_engine._text(seed.get("candidate"))
            )
            ledger[seed["seed_id"]] = entry
    # Prune CLOSED entries older than 6 rounds to bound state growth.
    _prune_closed_entries(state, round_num)
    return ledger


def active_tracked(state):
    """List ACTIVE ledger entries joined with their seed and tracking analysis."""
    ledger = state.get("tracking_ledger", {})
    seeds = {
        s.get("seed_id"): s
        for s in state.get("opportunity_seeds", [])
        if isinstance(s, dict) and s.get("seed_id")
    }
    rows = []
    for seed_id, entry in ledger.items():
        if entry.get("status") != ACTIVE:
            continue
        seed = seeds.get(seed_id)
        if not seed:
            continue
        path = opportunity_engine.path_analysis(state, seed)
        odds = opportunity_engine.odds_summary(seed)
        rows.append({
            "seed_id": seed_id,
            "candidate": entry.get("candidate") or opportunity_engine._text(seed.get("candidate")),
            "ticker": seed.get("ticker") or "",
            "entered_round": entry.get("entered_round"),
            "odds_posture": entry.get("odds_posture") or (odds or {}).get("qualitative") or "未声明",
            "chain": (path or {}).get("chain", []),
            "chain_counts": {
                "confirmed": (path or {}).get("confirmed", 0),
                "unverified": (path or {}).get("unverified", 0),
                "observed": (path or {}).get("observed", 0),
            },
            "upgrade_checkpoint": opportunity_engine._text(seed.get("catalyst")),
            "abandon_checkpoint": opportunity_engine._text(seed.get("falsifier")),
            "failure_signal": entry.get("failure_signal"),
            "tracking_until": entry.get("tracking_until"),
            "gap_next_action": _next_action_text(state, seed),
        })
    rows.sort(key=lambda r: (str(r["candidate"]), str(r["seed_id"])))
    return rows


def _next_action_text(state, seed):
    gap_task = None
    try:
        import candidate_gap_engine

        gap_task = candidate_gap_engine.open_task_for_seed(
            state, str(seed.get("seed_id") or "")
        )
    except Exception:
        pass
    if gap_task:
        return f"执行 {gap_task.get('task_id')}: {gap_task.get('target_claim')}"
    blockers = opportunity_engine.promotion_assessment(state, seed).get("blocking_reasons", [])
    if blockers:
        return f"缺 {'、'.join(blockers[:2])}"
    return "—"
