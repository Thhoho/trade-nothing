# -*- coding: utf-8 -*-
"""
Trade Nothing v0.13.0 — Crux Engine  (parallel to deepthink_engine.py; -deepthink2)

Replaces the degenerate single-posterior + LFI layer with a per-CRUX ledger:

  * Each load-bearing crux carries a bounded debate-support score. It is a
    deterministic debate-control heuristic, not a calibrated market probability.
  * Per evidence-bearing round, ONE decorrelated update per crux (judge signal),
    with mean-reversion decay and a hard clamp |L| <= ln(L_MAX_ODDS) -> a single
    crux can never exceed ~80/20 from debate alone. A zero signal carries support
    forward unchanged because missing evidence is not contrary evidence.
  * Convergence = decision-readiness: stop when every crux is RESOLVED or converted
    to a MONITORABLE watch-item AND the decision is stable. Achievable (unlike
    "no attack survives", which never converged: open_attacks went 2->30).
  * Crux-scoping: a RESOLVED crux is RETIRED -> no more sub-agents fired on it ->
    fewer searches per round + faster convergence (the cost win).
  * Citations live on the ledger per crux (verifiability).

All scores are computed here from judge-supplied signals; the LLM never writes the
resulting score. Determinism of control flow is preserved; the Judge only supplies a
bounded signal in [-1,1] + rationale + citations per crux per round. Repeated evidence
is de-duplicated per crux and cannot move the score twice.
"""
import math
import json
import re
from urllib.parse import urlparse

# ── tunables (configurable; defaults from the 绿色算力 PoC) ──
K            = 0.9              # per-round gain. strong evidence (|s|=1) -> ±0.9 log-odds
DECAY        = 0.88             # mean-reversion applied only on evidence-bearing updates
L_MAX        = math.log(4.0)    # clamp -> single-crux prob bounded to [0.20, 0.80]
MIN_ROUNDS   = 3
MAX_ROUNDS   = 12               # hard fuse (should rarely be hit now)
EPS_STABLE   = 0.03             # |Δp| below this over a touch = "settled"
OPEN_PATIENCE = 3               # legacy compatibility; no longer forces MONITORABLE
MIN_CONTESTED = 3               # min contested rounds before a crux is eligible for retirement
DRY_ROUNDS   = 3                # no NEW crux introduced for this many rounds = adversary went dry
MIN_VALID_CITATIONS = 2         # a crux needs real source anchors before it may retire
EVIDENCE_EXHAUSTION_DRY_ROUNDS = 2
                                # consecutive bilateral probes with no NEW valid evidence
UNIVERSE_HARVEST_DRY_ROUNDS = 2 # two dry harvests; coverage round counts only when itself dry

MONITORABLE_EXHAUSTION_REASON = "EVIDENCE_EXHAUSTED_AFTER_BILATERAL_PROBES"
MONITORABLE_SEMANTICS = "RESEARCH_EXHAUSTION_ONLY_NOT_TRUTH_OR_PROBABILITY"

QUESTION_TYPES = {
    "CONJUNCTIVE", "DISJUNCTIVE", "CAUSAL_CHAIN", "COMPARATIVE", "UNIVERSE_SEARCH",
}
CRUX_ROLES = {
    "THESIS_HINGE", "OPPORTUNITY_PATH", "PRICING", "COMPARISON_AXIS",
}

def _sig(x):   return 1.0 / (1.0 + math.exp(-x))
def _clamp(x, lo, hi): return max(lo, min(hi, x))


def is_concrete_url(url):
    """Reject homepage/domain-only citations; accept URLs with a real path/query."""
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        p = urlparse(url.strip())
    except Exception:
        return False
    if p.scheme not in ("http", "https") or not p.netloc:
        return False
    if is_placeholder_url(url) or is_redirect_wrapper_url(url):
        return False
    return bool((p.path and p.path != "/") or p.query)


def is_placeholder_url(url):
    """Reject IANA-reserved examples and local/test hosts from research evidence."""
    try:
        host = (urlparse(str(url or "").strip()).hostname or "").lower().rstrip(".")
    except Exception:
        return True
    if not host:
        return True
    reserved = {"example.com", "example.org", "example.net", "localhost", "0.0.0.0"}
    if (host in reserved
            or any(host.endswith(f".{item}") for item in {
                "example.com", "example.org", "example.net",
            })
            or host.startswith("127.")):
        return True
    return any(host.endswith(suffix) for suffix in (
        ".example", ".invalid", ".localhost", ".test",
    ))


def is_redirect_wrapper_url(url):
    """Reject search/grounding redirect wrappers that hide the actual publisher URL."""
    try:
        parsed = urlparse(str(url or "").strip())
    except Exception:
        return True
    host = (parsed.hostname or "").lower().rstrip(".")
    path = parsed.path or ""
    return (
        (host == "vertexaisearch.cloud.google.com" and path.startswith("/grounding-api-redirect"))
        or (host in {"google.com", "www.google.com"} and path == "/url")
        or (host in {"bing.com", "www.bing.com"} and path.startswith("/ck/"))
    )


def valid_citation(c):
    """Minimum citable anchor for engine scoring and report references."""
    if not isinstance(c, dict):
        return False
    return bool(c.get("claim") and c.get("source") and c.get("date") and is_concrete_url(c.get("url", "")))


def citation_source_identity(c):
    """Normalize a concrete source URL for source-diversity checks."""
    if not valid_citation(c):
        return ""
    p = urlparse(c.get("url", "").strip())
    path = re.sub(r"/+", "/", p.path or "/").rstrip("/") or "/"
    normalized_url = f"{p.scheme.lower()}://{p.netloc.lower()}{path}"
    if p.query:
        normalized_url += f"?{p.query}"
    return normalized_url


def citation_publisher_identity(c):
    """Conservative publisher identity derived from URL, not agent-supplied labels."""
    if not valid_citation(c):
        return ""
    host = (urlparse(c.get("url", "").strip()).hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    multi_label_suffixes = {"co.uk", "com.au", "co.jp", "com.cn", "com.hk"}
    suffix = ".".join(labels[-2:]) if len(labels) >= 2 else host
    if suffix in multi_label_suffixes and len(labels) >= 3:
        return ".".join(labels[-3:])
    return suffix


def is_primary_citation(c):
    """Conservatively identify declared primary sources and official US records."""
    if not valid_citation(c):
        return False
    if str(c.get("source_tier", "")).lower() in {"primary", "tier-1", "tier1"}:
        return True
    try:
        host = (urlparse(c.get("url", "")).hostname or "").lower().rstrip(".")
    except Exception:
        return False
    return host.endswith(".gov")


def citation_identity(c):
    """Stable per-claim evidence identity used to prevent repeated scoring."""
    normalized_url = citation_source_identity(c)
    if not normalized_url:
        return ""
    claim = " ".join(str(c.get("claim", "")).lower().split())
    number = " ".join(str(c.get("number", "")).lower().split())
    return f"{normalized_url}|{claim}|{number}"


def _numbered_citation(c):
    return valid_citation(c) and bool(str(c.get("number", "")).strip())


def _valid_citation_count(cx):
    return len({citation_source_identity(c) for c in cx.get("citations", []) if valid_citation(c)})


def _append_new_citations(cx, citations, round_num, support_effect):
    """Persist normalized citations even when their net Judge signal is zero."""
    seen = set(cx.get("seen_evidence_keys", []))
    appended = 0
    for citation in citations if isinstance(citations, list) else []:
        key = citation_identity(citation)
        if not key or key in seen:
            continue
        stored = {**citation, "round": int(round_num)}
        if support_effect:
            stored["support_effect"] = support_effect
        cx.setdefault("citations", []).append(stored)
        cx.setdefault("seen_evidence_keys", []).append(key)
        seen.add(key)
        appended += 1
    return appended


def _probe_audit_item(round_context, crux_id):
    """Normalize caller-computed role probes; never infer them from Judge prose."""
    if not isinstance(round_context, dict):
        return None
    raw_map = round_context.get("crux_probe_audit")
    if not isinstance(raw_map, dict) or crux_id not in raw_map:
        return None
    raw = raw_map.get(crux_id)
    if not isinstance(raw, dict):
        return {
            "detective_probed": False,
            "inquisitor_probed": False,
            "new_valid_evidence_count": None,
            "valid": False,
        }
    count = raw.get("new_valid_evidence_count")
    valid_count = type(count) is int and count >= 0
    if not valid_count:
        count = None
    return {
        "detective_probed": raw.get("detective_probed") is True,
        "inquisitor_probed": raw.get("inquisitor_probed") is True,
        "new_valid_evidence_count": count,
        "valid": valid_count,
    }


def _configured_exhaustion_dry_rounds(state):
    raw = state.get("config", {}).get(
        "EVIDENCE_EXHAUSTION_DRY_ROUNDS",
        EVIDENCE_EXHAUSTION_DRY_ROUNDS,
    )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = EVIDENCE_EXHAUSTION_DRY_ROUNDS
    # "Consecutive" must mean more than one independently dispatched probe.
    return int(_clamp(value, 2, MAX_ROUNDS))


def _apply_evidence_exhaustion(state, round_num, round_context, accepted_citations):
    """Retire evidence-exhausted OPEN cruxes without changing support semantics.

    ``round_context["crux_probe_audit"]`` is computed by the orchestration layer
    from the isolated Detective/Inquisitor payloads:

        {
          "C1": {
            "detective_probed": true,
            "inquisitor_probed": true,
            "new_valid_evidence_count": 0
          }
        }

    A missing crux entry means "not dispatched" and leaves its per-crux streak
    unchanged.  An explicit partial/malformed probe resets the streak fail-closed.
    Judge rationale and self-reported role labels are never used to establish
    bilateral coverage.
    """
    required_dry = _configured_exhaustion_dry_rounds(state)
    try:
        max_introduced_round = int(state.get("max_introduced_round", 0) or 0)
    except (TypeError, ValueError):
        max_introduced_round = int(round_num)
    global_adversary_dry = int(round_num) - max_introduced_round >= DRY_ROUNDS
    audits = {}
    for cid, cx in state.get("cruxes", {}).items():
        if cx.get("retired") or cx.get("status") not in {"PENDING", "OPEN"}:
            continue
        probe = _probe_audit_item(round_context, cid)
        try:
            before = int(cx.get("evidence_exhaustion_dry_streak", 0) or 0)
        except (TypeError, ValueError):
            before = 0
        accepted_count = int(accepted_citations.get(cid, 0) or 0)

        # A crux absent from the caller audit was not dispatched. It neither
        # advances nor breaks a consecutive sequence of *its own* probe attempts.
        if probe is None:
            audit = {
                "round": int(round_num),
                "probe_audit_present": False,
                "dry_streak_before": before,
                "dry_streak_after": before,
                "transitioned": False,
                "transition_reason": None,
                "semantics": MONITORABLE_SEMANTICS,
                "blocking_reasons": ["PROBE_AUDIT_MISSING_OR_CRUX_NOT_DISPATCHED"],
            }
            audits[cid] = audit
            cx["evidence_exhaustion"] = dict(audit)
            continue

        both_probed = (
            probe["detective_probed"] and probe["inquisitor_probed"] and probe["valid"]
        )
        declared_new = probe["new_valid_evidence_count"]
        # Newly accepted normalized citations are a fail-closed override. This
        # prevents a malformed caller count from treating wash evidence as dry.
        effective_new = max(int(declared_new or 0), accepted_count)
        if both_probed:
            if cx.get("first_bilateral_probe_round") is None:
                cx["first_bilateral_probe_round"] = int(round_num)
            after = before + 1 if effective_new == 0 else 0
        else:
            after = 0
        cx["evidence_exhaustion_dry_streak"] = after

        # A zero-signal evidence wash is still an examined OPEN question once
        # both isolated roles have probed it and valid evidence exists.
        if (
            cx.get("status") == "PENDING"
            and both_probed
            and _valid_citation_count(cx) > 0
        ):
            cx["status"] = "OPEN"

        try:
            introduced_round = int(cx.get("introduced", 0) or 0)
        except (TypeError, ValueError):
            introduced_round = int(round_num)
        crux_old_enough = int(round_num) - introduced_round >= DRY_ROUNDS
        valid_count = _valid_citation_count(cx)
        blockers = []
        if cx.get("status") != "OPEN":
            blockers.append("STATUS_NOT_OPEN")
        if int(round_num) < MIN_ROUNDS:
            blockers.append("MINIMUM_ROUNDS_NOT_MET")
        if not both_probed or cx.get("first_bilateral_probe_round") is None:
            blockers.append("BILATERAL_PROBE_NOT_ESTABLISHED")
        if valid_count < MIN_VALID_CITATIONS:
            blockers.append("MINIMUM_VALID_CITATIONS_NOT_MET")
        if after < required_dry:
            blockers.append("CONSECUTIVE_DRY_PROBES_NOT_MET")
        if not global_adversary_dry:
            blockers.append("ADVERSARY_NOT_DRY")
        if not crux_old_enough:
            blockers.append("CRUX_RECENTLY_INTRODUCED")
        if not probe["valid"]:
            blockers.append("PROBE_AUDIT_INVALID")

        transitioned = not blockers
        transition_reason = None
        if transitioned:
            transition_reason = MONITORABLE_EXHAUSTION_REASON
            cx["status"] = "MONITORABLE"
            cx["retired"] = True
            cx["monitorable_reason"] = transition_reason
            cx["monitorable_round"] = int(round_num)
            cx["monitorable_semantics"] = MONITORABLE_SEMANTICS
            cx["transition_reason"] = transition_reason

        audit = {
            "round": int(round_num),
            "probe_audit_present": True,
            "detective_probed": probe["detective_probed"],
            "inquisitor_probed": probe["inquisitor_probed"],
            "both_roles_probed": both_probed,
            "declared_new_valid_evidence_count": declared_new,
            "accepted_new_citation_count": accepted_count,
            "effective_new_valid_evidence_count": effective_new,
            "valid_citation_count": valid_count,
            "minimum_valid_citations": MIN_VALID_CITATIONS,
            "dry_streak_before": before,
            "dry_streak_after": after,
            "required_dry_streak": required_dry,
            "adversary_dry": global_adversary_dry,
            "crux_old_enough": crux_old_enough,
            "support_score_unchanged_by_transition": True,
            "transitioned": transitioned,
            "transition_reason": transition_reason,
            "semantics": MONITORABLE_SEMANTICS,
            "blocking_reasons": blockers,
        }
        audits[cid] = audit
        cx["evidence_exhaustion"] = dict(audit)
    return audits


def _normalize_signal(js, seen_evidence_keys=None):
    """Make the evidence gate physical: unsupported/repeated signals cannot move scores."""
    if not isinstance(js, dict):
        js = {}
    out = dict(js)
    try:
        s = float(out.get("signal", 0.0))
    except Exception:
        s = 0.0
    s = _clamp(s, -1.0, 1.0)
    citations = out.get("citations", []) if isinstance(out.get("citations", []), list) else []
    seen = set(seen_evidence_keys or [])
    valid = []
    invalid_count = 0
    duplicates = 0
    batch_keys = set()
    for c in citations:
        if not valid_citation(c):
            invalid_count += 1
            continue
        key = citation_identity(c)
        if key in seen or key in batch_keys:
            duplicates += 1
            continue
        batch_keys.add(key)
        valid.append(c)
    flags = list(out.get("quality_flags", [])) if isinstance(out.get("quality_flags", []), list) else []
    if invalid_count:
        flags.append(f"dropped_invalid_citations:{invalid_count}")
    if duplicates:
        flags.append(f"dropped_duplicate_evidence:{duplicates}")
    if s != 0.0 and not valid:
        s = 0.0
        flags.append("signal_zeroed_no_valid_citation")
    elif abs(s) > 0.5 and not any(_numbered_citation(c) for c in valid):
        s = 0.5 if s > 0 else -0.5
        flags.append("signal_capped_no_numbered_citation")
    out["signal"] = s
    out["citations"] = valid
    if flags:
        out["quality_flags"] = sorted(set(flags))
    return out


def new_state(topic, decision_question, horizon, cruxes,
              question_type="CONJUNCTIVE", logic_graph=None):
    """cruxes: list of {id, label, definition, monitor_anchor, falsifier, catalyst_window}"""
    normalized_type = str(question_type or "CONJUNCTIVE").upper()
    if normalized_type not in QUESTION_TYPES:
        raise ValueError(f"unsupported question_type: {question_type}")
    return {
        "topic": topic,
        "decision_question": decision_question,
        "question_type": normalized_type,
        "logic_graph": logic_graph or {},
        "horizon": horizon,
        "score_semantics": "debate_support_score_not_calibrated_probability",
        "config": {
            "K": K,
            "DECAY": DECAY,
            "L_MAX_ODDS": 4.0,
            "MAX_ROUNDS": MAX_ROUNDS,
            "EVIDENCE_EXHAUSTION_DRY_ROUNDS": EVIDENCE_EXHAUSTION_DRY_ROUNDS,
        },
        "cruxes": {c["id"]: {
            "label": c["label"],
            "definition": c.get("definition", ""),
            "logic_role": str(c.get("logic_role", "THESIS_HINGE")).upper(),
            "monitor_anchor": c.get("monitor_anchor", ""),
            "falsifier": c.get("falsifier", ""),
            "catalyst_window": c.get("catalyst_window", {}),
            "evidence_plan": c.get("evidence_plan", []),
            "L": 0.0, "p_history": [0.5], "contested_history": [], "status": "PENDING",
            "retired": False, "first_contested": None, "last_signal": 0.0,
            "introduced": 0,
            "best_bull": None, "best_bear": None, "citations": [],
            "seen_evidence_keys": [],
            "first_bilateral_probe_round": None,
            "evidence_exhaustion_dry_streak": 0,
        } for c in cruxes},
        "max_introduced_round": 0,
        "rounds": [],
        "decision_trace": [],
        "opportunity_seeds": [],
        "candidate_gap_tasks": [],
        "candidate_evidence_supplements": [],
        "candidate_gap_resolutions": [],
        "candidate_screens": [],
        "source_snapshots": [],
        "claim_verifications": [],
    }


def add_crux(state, crux, round_num):
    """Adversary discovered a new attack surface mid-debate. Resets the dry-round clock."""
    if crux["id"] in state["cruxes"]:
        return
    state["cruxes"][crux["id"]] = {
        "label": crux["label"], "definition": crux.get("definition", ""),
        "logic_role": str(crux.get("logic_role", "THESIS_HINGE")).upper(),
        "monitor_anchor": crux.get("monitor_anchor", ""),
        "falsifier": crux.get("falsifier", ""),
        "catalyst_window": crux.get("catalyst_window", {}),
        "L": 0.0, "p_history": [0.5], "contested_history": [], "status": "PENDING",
        "retired": False, "first_contested": None, "last_signal": 0.0,
        "introduced": round_num,
        "best_bull": None, "best_bear": None, "citations": [],
        "seen_evidence_keys": [],
        "first_bilateral_probe_round": None,
        "evidence_exhaustion_dry_streak": 0,
    }
    state["max_introduced_round"] = max(state["max_introduced_round"], round_num)


def _update_status(cx, r):
    """Classify a crux. Only evaluated on rounds where the crux was contested."""
    if cx["first_contested"] is None:
        return "PENDING"                           # never examined -> blocks convergence
    ch = cx["contested_history"]
    if len(ch) < MIN_CONTESTED:
        return "OPEN"                              # insufficient contested rounds for resolution
    if _valid_citation_count(cx) < MIN_VALID_CITATIONS:
        return "OPEN"                              # stable rhetoric is not evidentiary convergence
    p = ch[-1]
    settled = abs(ch[-1] - ch[-2]) < EPS_STABLE    # stable across last 2 *contested* rounds
    if settled:
        if p >= 0.55:  return "RESOLVED_BULL"
        if p <= 0.45:  return "RESOLVED_BEAR"
        return "OPEN"                              # neutral support is not a truth verdict
    return "OPEN"


def submit_round(state, round_num, judge_signals, round_context=None):
    """
    judge_signals: { crux_id: {
        "signal": float in [-1,1],            # +bull / -bear, |0.5|=weak |1|=strong
        "rationale": str,
        "citations": [ {claim,number,source,url,date} ],
        "best_bull": str|None, "best_bear": str|None,
    } }
    Signals for RETIRED cruxes are ignored (crux-scoping: we didn't fire agents on them).

    ``round_context`` may include an orchestration-computed probe audit:
      {"crux_probe_audit": {
          "C1": {"detective_probed": bool, "inquisitor_probed": bool,
                 "new_valid_evidence_count": int}
      }}
    The engine never infers bilateral probing from Judge text.
    """
    fired = []
    normalized_signals = {}
    accepted_citations = {}
    for cid, cx in state["cruxes"].items():
        js = _normalize_signal(judge_signals.get(cid, {}), cx.get("seen_evidence_keys", []))
        probe = _probe_audit_item(round_context, cid)
        wash_is_role_traceable = bool(
            probe
            and probe.get("detective_probed")
            and probe.get("inquisitor_probed")
        )
        if float(js.get("signal", 0.0)) == 0.0 and js.get("citations") and not wash_is_role_traceable:
            dropped = len(js["citations"])
            js["citations"] = []
            flags = list(js.get("quality_flags", []))
            flags.append(f"dropped_zero_signal_citations_without_bilateral_probe_audit:{dropped}")
            js["quality_flags"] = sorted(set(flags))
        normalized_signals[cid] = js
        s = float(js.get("signal", 0.0))
        # a strong NEW attack re-opens a previously settled/retired crux (forced-novelty)
        if cx["retired"] and s <= -0.5:
            cx["retired"] = False
            cx["status"] = "OPEN"
        if cx["retired"]:
            cx["p_history"].append(_sig(cx["L"]))   # carry forward; not re-debated
            continue
        if s != 0.0:
            cx["L"] = _clamp(DECAY * cx["L"] + K * s, -L_MAX, L_MAX)
        cx["p_history"].append(_sig(cx["L"]))
        cx["last_signal"] = s
        support_effect = "NONE_ZERO_SIGNAL_WASH" if s == 0.0 else "DEBATE_SUPPORT_UPDATE"
        accepted_citations[cid] = _append_new_citations(
            cx, js.get("citations", []), round_num, support_effect
        )
        if s != 0.0:                                # contested this round
            fired.append(cid)
            if cx["first_contested"] is None:
                cx["first_contested"] = round_num
            cx["contested_history"].append(_sig(cx["L"]))
            if js.get("best_bull"): cx["best_bull"] = js["best_bull"]
            if js.get("best_bear"): cx["best_bear"] = js["best_bear"]
            cx["status"] = _update_status(cx, round_num)   # re-evaluate only on contest
            if cx["status"] in ("RESOLVED_BULL", "RESOLVED_BEAR", "MONITORABLE") and round_num >= MIN_ROUNDS:
                cx["retired"] = True                # crux-scoping: stop firing agents on it

    probs = {cid: cx["p_history"][-1] for cid, cx in state["cruxes"].items()}
    weakest = min(probs, key=probs.get)
    mean_L = sum(math.log(p/(1-p)) for p in probs.values()) / len(probs)
    verdict = research_verdict(state, probs)
    decision = _legacy_decision(verdict)
    aggregation_rule = ("WEAKEST_NECESSARY_CRUX"
                        if state.get("question_type") in {"CONJUNCTIVE", "CAUSAL_CHAIN"}
                        else "LOGIC_GRAPH_MULTI_PATH")
    round_record = {"round": round_num, "fired_cruxes": fired, "signals": normalized_signals}
    if isinstance(round_context, dict):
        for key in (
            "landscape_audit",
            "opportunity_harvest",
            "crux_probe_audit",
            "hypothesis_audit",
            "hypothesis_escalation",
        ):
            if isinstance(round_context.get(key), dict):
                round_record[key] = round_context[key]
    state["rounds"].append(round_record)
    state["decision_trace"].append({
        "round": round_num, "weakest": weakest,
        "p_weakest": round(probs[weakest], 4), "p_mean": round(_sig(mean_L), 4),
        "support_weakest": round(probs[weakest], 4), "support_mean": round(_sig(mean_L), 4),
        "decision": decision, "research_verdict": verdict,
        "focus_crux": weakest, "aggregation_rule": aggregation_rule,
    })
    round_record["evidence_exhaustion"] = _apply_evidence_exhaustion(
        state, round_num, round_context, accepted_citations
    )
    conv = convergence(state, round_num)
    if conv.get("decision") == "converge" and verdict.get("edge_state") == "EDGE_FOUND":
        verdict["actionability"] = "READY_FOR_SCREENING"
    return conv


def _legacy_decision(verdict):
    """Compatibility projection. Never translate NO_EDGE into AVOID or SHORT."""
    if verdict.get("edge_state") == "EDGE_FOUND":
        return "RESEARCH_READY"
    if verdict.get("edge_state") == "NO_EDGE":
        return "NO_EDGE"
    return "MONITOR"


def safe_decision_label(value):
    """Remove the legacy NO_EDGE -> AVOID semantic leak from old saved states."""
    label = str(value or "")
    if label.startswith("NO_EDGE"):
        return "NO_EDGE"
    return label


def _direction(values):
    bull = any(value >= 0.60 for value in values)
    bear = any(value <= 0.40 for value in values)
    if bull and bear:
        return "MIXED"
    if bull:
        return "BULL"
    if bear:
        return "BEAR"
    return "UNDETERMINED"


def research_verdict(state, probs=None):
    """Project crux support into question-aware research semantics.

    This is deliberately conservative. Debate support schedules research; it is not a
    calibrated probability. In particular, one failed path cannot negate a disjunctive
    or universe-search question, and NO_EDGE never implies a short.
    """
    if probs is None:
        probs = {
            cid: cx.get("p_history", [0.5])[-1]
            for cid, cx in state.get("cruxes", {}).items()
        }
    qtype = str(state.get("question_type", "CONJUNCTIVE")).upper()
    if qtype not in QUESTION_TYPES:
        qtype = "CONJUNCTIVE"

    roles = {
        cid: str(state.get("cruxes", {}).get(cid, {}).get("logic_role", "THESIS_HINGE")).upper()
        for cid in probs
    }
    pricing = [probs[cid] for cid, role in roles.items() if role == "PRICING"]
    paths = [
        probs[cid] for cid, role in roles.items()
        if role in {"OPPORTUNITY_PATH", "THESIS_HINGE"}
    ]
    axes = [probs[cid] for cid, role in roles.items() if role == "COMPARISON_AXIS"]
    if not paths:
        paths = [value for cid, value in probs.items() if roles.get(cid) != "PRICING"]
    all_values = list(probs.values())
    direction = _direction(all_values)

    edge_state = "INSUFFICIENT_EVIDENCE"
    actionability = "MONITOR" if any(value != 0.5 for value in all_values) else "NONE"
    reason_code = "UNRESOLVED_CRUXES"

    if qtype in {"CONJUNCTIVE", "CAUSAL_CHAIN"}:
        necessary = paths or all_values
        if necessary and any(value <= 0.40 for value in necessary):
            edge_state, actionability, reason_code = "NO_EDGE", "NONE", "NECESSARY_CRUX_CONTRADICTED"
        elif necessary and all(value >= 0.60 for value in necessary):
            if pricing and all(value >= 0.55 for value in pricing):
                edge_state, actionability, reason_code = "EDGE_FOUND", "MONITOR", "THESIS_SUPPORTED_WITH_PRICING_GAP"
            elif pricing and all(value <= 0.40 for value in pricing):
                edge_state, actionability, reason_code = "NO_EDGE", "NONE", "THESIS_SUPPORTED_BUT_PRICING_GAP_REJECTED"
            elif not pricing:
                reason_code = "PRICING_NOT_ASSESSED"
            else:
                reason_code = "PRICING_GAP_UNRESOLVED"
    elif qtype == "DISJUNCTIVE":
        pricing_supports_gap = bool(pricing) and any(value >= 0.55 for value in pricing)
        pricing_rejects_gap = bool(pricing) and all(value <= 0.40 for value in pricing)
        if paths and any(value >= 0.60 for value in paths) and pricing_supports_gap:
            edge_state, actionability, reason_code = "EDGE_FOUND", "MONITOR", "SUPPORTED_PATH_WITH_PRICING_GAP"
        elif paths and all(value <= 0.40 for value in paths) and pricing_rejects_gap:
            edge_state, actionability, reason_code = "NO_EDGE", "NONE", "ALL_PATHS_AND_PRICING_GAP_REJECTED"
        else:
            reason_code = "PATH_OR_PRICING_COVERAGE_INCOMPLETE"
    elif qtype == "UNIVERSE_SEARCH":
        # A universe contains heterogeneous entities and adverse as well as positive
        # paths. Pooling their evidence into one directional support score creates a
        # category error: failure by one candidate can cancel success by another, and
        # a negative screen can be misreported as a bearish universe call. Root-level
        # completion is therefore coverage-only; direction and edge live on each seed.
        direction = "UNDETERMINED"
        actionability = "MONITOR"
        reason_code = "UNIVERSE_COVERAGE_COMPLETE_CANDIDATE_LEVEL_ASSESSMENT"
    elif qtype == "COMPARATIVE":
        compared = axes or paths
        if (len(compared) >= 2 and max(compared) >= 0.60 and min(compared) <= 0.40
                and pricing and any(value >= 0.55 for value in pricing)):
            edge_state, actionability, reason_code = "EDGE_FOUND", "MONITOR", "RELATIVE_WINNER_SEPARATED"
            direction = "MIXED"
        elif len(compared) >= 2 and max(compared) >= 0.60 and min(compared) <= 0.40 and not pricing:
            reason_code = "RELATIVE_WINNER_FOUND_BUT_PRICING_NOT_ASSESSED"
        else:
            reason_code = "NO_DECISIVE_RELATIVE_SEPARATION"

    landscape_paths = [
        item for item in state.get("landscape_map", {}).get("paths", [])
        if isinstance(item, dict)
    ]
    if qtype == "UNIVERSE_SEARCH" and not landscape_paths:
        edge_state = "INSUFFICIENT_EVIDENCE"
        actionability = "NONE"
        reason_code = "UNIVERSE_LANDSCAPE_MISSING"
    if any(item.get("state", "UNPROBED") == "UNPROBED" for item in landscape_paths):
        edge_state = "INSUFFICIENT_EVIDENCE"
        actionability = "NONE"
        reason_code = "LANDSCAPE_PATHS_UNPROBED"
    if (edge_state == "EDGE_FOUND"
            and state.get("last_convergence", {}).get("decision") == "converge"):
        actionability = "READY_FOR_SCREENING"
    return {
        "edge_state": edge_state,
        "evidence_direction": direction,
        "actionability": actionability,
        "question_type": qtype,
        "reason_code": reason_code,
    }


def _universe_coverage_round(state):
    """Derive the first round in which both roles had probed every Landscape path."""
    probe_rounds = []
    for item in state.get("landscape_map", {}).get("paths", []):
        if not isinstance(item, dict):
            continue
        probes = item.get("probes", {}) if isinstance(item.get("probes"), dict) else {}
        for role in ("detective", "inquisitor"):
            try:
                probe_rounds.append(int(probes.get(role, {}).get("round") or 0))
            except (TypeError, ValueError):
                return None
    if not probe_rounds or any(round_num <= 0 for round_num in probe_rounds):
        return None
    return max(probe_rounds)


def _universe_harvest_dry_rounds(state, coverage_round):
    """Count consecutive dry harvests beginning no earlier than full coverage."""
    dry = 0
    for item in reversed(state.get("rounds", [])):
        try:
            item_round = int(item.get("round") or 0)
        except (AttributeError, TypeError, ValueError):
            break
        if item_round < coverage_round:
            break
        harvest = item.get("opportunity_harvest") if isinstance(item, dict) else None
        if not isinstance(harvest, dict):
            break
        if int(harvest.get("accepted_new") or 0) or int(harvest.get("merged_existing") or 0):
            break
        dry += 1
    return dry


def _discovery_required(state):
    """Whether opportunity discovery gates apply independently of logic type."""
    frame_contract = (
        state.get("frame_contract")
        if isinstance(state.get("frame_contract"), dict)
        else {}
    )
    intent = str(
        frame_contract.get("research_intent")
        or state.get("research_intent")
        or ""
    ).strip().upper()
    if intent in {"OPPORTUNITY_DISCOVERY", "HYBRID"}:
        return True
    if str(state.get("question_type") or "").upper() in {
        "UNIVERSE_SEARCH",
        "COMPARATIVE",
    }:
        return True
    return any(
        isinstance(crux, dict)
        and str(crux.get("logic_role") or "").upper() == "OPPORTUNITY_PATH"
        for crux in state.get("cruxes", {}).values()
    )


def _discovery_convergence_issue(state):
    """Require bilateral Landscape coverage plus a post-coverage dry window."""
    paths = [
        item
        for item in state.get("landscape_map", {}).get("paths", [])
        if isinstance(item, dict)
    ]
    if not paths:
        return "机会发现意图缺少 Landscape Map，不能声明搜索完成。"
    unprobed = [
        item.get("path_id")
        for item in paths
        if item.get("state", "UNPROBED") == "UNPROBED"
    ]
    if unprobed:
        return f"Landscape Map 仍有未质证路径: {unprobed}；机会型研究不得收敛。"
    missing_roles = []
    for item in paths:
        probes = (
            item.get("probes", {})
            if isinstance(item.get("probes"), dict)
            else {}
        )
        for role in ("detective", "inquisitor"):
            if role not in probes:
                missing_roles.append(f"{item.get('path_id')}:{role}")
    if missing_roles:
        return f"Landscape Map 缺少双边探测记录: {missing_roles}。"
    coverage_round = _universe_coverage_round(state)
    if coverage_round is None:
        return "Landscape Map 双边探测缺少有效轮次，不能建立覆盖完成时间。"
    dry_rounds = _universe_harvest_dry_rounds(state, coverage_round)
    if dry_rounds < UNIVERSE_HARVEST_DRY_ROUNDS:
        return (
            f"Landscape 于 R{coverage_round} 完成后，候选收割仅连续静默 "
            f"{dry_rounds} 轮；需 {UNIVERSE_HARVEST_DRY_ROUNDS} 轮无新 seed "
            "或既有 seed 证据增长。"
        )
    return None


def _universe_convergence_issue(state, round_num):
    """Return the deterministic reason a broad search is not coverage-complete yet."""
    discovery_issue = _discovery_convergence_issue(state)
    if discovery_issue:
        return discovery_issue

    unexamined = [
        cid for cid, cx in state.get("cruxes", {}).items()
        if cx.get("first_contested") is None
    ]
    if unexamined:
        return f"仍有从未被有效证据质证的 crux: {unexamined}。"
    under_sourced = [
        cid for cid, cx in state.get("cruxes", {}).items()
        if _valid_citation_count(cx) < MIN_VALID_CITATIONS
    ]
    if under_sourced:
        return f"仍有证据锚点不足的 crux: {under_sourced}。"
    if round_num - state.get("max_introduced_round", 0) < DRY_ROUNDS:
        return (
            f"R{state.get('max_introduced_round', 0)} 才引入新 crux，"
            f"需再质证 {DRY_ROUNDS} 轮确认无新攻击面。"
        )
    if len(state.get("decision_trace", [])) < 2:
        return "覆盖完成后仍需一轮确认根层 edge/actionability 状态稳定。"
    a, b = state["decision_trace"][-1], state["decision_trace"][-2]
    signature = lambda item: (
        item.get("research_verdict", {}).get("edge_state"),
        item.get("research_verdict", {}).get("actionability"),
    )
    if signature(a) != signature(b):
        return "UNIVERSE_SEARCH 根层 edge/actionability 状态尚未稳定。"
    return None


def _settle_universe_cruxes(state, round_num):
    """Close global cruxes as monitors without inventing a universe direction."""
    for cx in state.get("cruxes", {}).values():
        if cx.get("status") in {"PENDING", "OPEN"}:
            cx["status"] = "MONITORABLE"
            cx["retired"] = True
            cx["monitorable_reason"] = "UNIVERSE_COVERAGE_COMPLETE_DIRECTION_NOT_AGGREGATED"
            cx["monitorable_round"] = int(round_num)
            cx["monitorable_semantics"] = MONITORABLE_SEMANTICS
            cx["transition_reason"] = "UNIVERSE_COVERAGE_AND_HARVEST_DRY"


def convergence(state, round_num):
    try:
        configured_max = int(state.get("config", {}).get("MAX_ROUNDS", MAX_ROUNDS))
    except (TypeError, ValueError):
        configured_max = MAX_ROUNDS
    configured_max = int(_clamp(configured_max, MIN_ROUNDS, MAX_ROUNDS))
    if round_num < MIN_ROUNDS:
        return {"decision": "continue", "round": round_num,
                "reason": f"轮次 {round_num} < 最低 {MIN_ROUNDS}。"}

    def not_ready(reason, open_cruxes=None):
        if round_num >= configured_max:
            out = {"decision": "fuse_break", "round": round_num,
                   "reason": f"达本次最大轮次 {configured_max}，仍未满足正式报告闸门。{reason}"}
            if open_cruxes is not None:
                out["open_cruxes"] = open_cruxes
            return out
        out = {"decision": "continue", "round": round_num, "reason": reason}
        if open_cruxes is not None:
            out["open_cruxes"] = open_cruxes
        return out

    if state.get("question_type") == "UNIVERSE_SEARCH":
        issue = _universe_convergence_issue(state, round_num)
        if issue:
            return not_ready(issue)
        _settle_universe_cruxes(state, round_num)
        return {
            "decision": "converge", "round": round_num,
            "reason": (
                "UNIVERSE_SEARCH 已完成双边 Landscape 覆盖，所有 crux 有有效证据锚点，"
                "且连续两轮无候选或候选证据增长。根层方向保持 UNDETERMINED；"
                "候选错价与方向留给 CandidateScreen。"
            ),
            "convergence_basis": "UNIVERSE_COVERAGE_AND_HARVEST_DRY",
        }

    # every crux must be examined and settled or converted to a monitorable watch-item
    unsettled = [cid for cid, cx in state["cruxes"].items()
                 if cx["status"] in ("PENDING", "OPEN")]
    if unsettled:
        return not_ready(f"仍有未检验/活跃 crux: {unsettled}（继续，且仅对这些派子智能体）。",
                         unsettled)
    if _discovery_required(state):
        discovery_issue = _discovery_convergence_issue(state)
        if discovery_issue:
            return not_ready(discovery_issue)
    else:
        unprobed_paths = [
            item.get("path_id")
            for item in state.get("landscape_map", {}).get("paths", [])
            if isinstance(item, dict)
            and item.get("state", "UNPROBED") == "UNPROBED"
        ]
        if unprobed_paths:
            return not_ready(
                f"Landscape Map 仍有未质证路径: {unprobed_paths}；"
                "机会型研究不得收敛或声明 EDGE。"
            )
    # completeness guard: adversary must have gone "dry" (no new crux for DRY_ROUNDS)
    if round_num - state["max_introduced_round"] < DRY_ROUNDS:
        return not_ready(f"R{state['max_introduced_round']} 才引入新 crux，需再质证 {DRY_ROUNDS} 轮确认审问者已无新攻击面。")
    # decision stability over last 2 rounds
    if len(state["decision_trace"]) >= 2:
        a, b = state["decision_trace"][-1], state["decision_trace"][-2]
        if a["decision"] != b["decision"]:
            return not_ready("研究状态尚未稳定。")
        if state.get("question_type") in {"CONJUNCTIVE", "CAUSAL_CHAIN"}:
            if abs(a["p_weakest"] - b["p_weakest"]) > EPS_STABLE:
                return not_ready("必要条件的最弱支持度尚未稳定。")
        else:
            av = a.get("research_verdict", {})
            bv = b.get("research_verdict", {})
            signature = lambda item: (
                item.get("edge_state"), item.get("evidence_direction"), item.get("actionability")
            )
            if signature(av) != signature(bv):
                return not_ready("多路径逻辑图的三维 verdict 尚未稳定。")
    return {"decision": "converge", "round": round_num,
            "reason": "每条 crux 已 RESOLVED 或转为可监控，且决策稳定。逻辑就绪。"}


def report_data(state):
    """Crux-organized ledger for the two-layer report (Layer A = proof ledger)."""
    cruxes = []
    for cid, cx in state["cruxes"].items():
        valid = [c for c in cx["citations"] if valid_citation(c)]
        unique_sources = sorted({citation_source_identity(c) for c in valid})
        cruxes.append({
            "id": cid, "label": cx["label"], "p": round(cx["p_history"][-1], 3),
            "support_score": round(cx["p_history"][-1], 3),
            "logic_role": cx.get("logic_role", "THESIS_HINGE"),
            "status": cx["status"], "best_bull": cx["best_bull"], "best_bear": cx["best_bear"],
            "monitor_anchor": cx["monitor_anchor"], "falsifier": cx.get("falsifier", ""),
            "evidence_plan": cx.get("evidence_plan", []),
            "catalyst_window": cx.get("catalyst_window", {}), "citations": cx["citations"],
            "valid_citations": valid,
            "unique_source_urls": unique_sources,
            "evidence_exhaustion": cx.get("evidence_exhaustion"),
            "transition_reason": cx.get("transition_reason"),
            "monitorable_semantics": cx.get("monitorable_semantics"),
        })
    cruxes.sort(key=lambda c: c["p"])              # weakest (binding) first
    last = state["decision_trace"][-1] if state["decision_trace"] else {}
    all_valid = [c for cx in cruxes for c in cx["valid_citations"]]
    unique_sources = {citation_source_identity(c) for c in all_valid}
    primary_sources = {citation_source_identity(c) for c in all_valid if is_primary_citation(c)}
    question_type = state.get("question_type", "CONJUNCTIVE")
    focus_crux = last.get("focus_crux", last.get("weakest"))
    binding_crux = (focus_crux
                    if question_type in {"CONJUNCTIVE", "CAUSAL_CHAIN"} else None)
    derived_verdict = research_verdict(state)
    stored_verdict = last.get("research_verdict") or {}
    report_verdict = (
        derived_verdict if question_type == "UNIVERSE_SEARCH"
        else stored_verdict or derived_verdict
    )
    return {
        "decision": safe_decision_label(last.get("decision")),
        "research_verdict": report_verdict,
        "stored_research_verdict": stored_verdict,
        "verdict_drift": bool(stored_verdict and stored_verdict != report_verdict),
        "question_type": question_type,
        "logic_graph": state.get("logic_graph", {}),
        "binding_crux": binding_crux,
        "focus_crux": focus_crux,
        "aggregation_rule": last.get("aggregation_rule", "WEAKEST_NECESSARY_CRUX"),
        "p_weakest": last.get("p_weakest"), "p_mean": last.get("p_mean"),
        "support_weakest": last.get("support_weakest", last.get("p_weakest")),
        "support_mean": last.get("support_mean", last.get("p_mean")),
        "cruxes": cruxes,
        "n_citations_raw": sum(len(c["citations"]) for c in cruxes),
        "n_unique_sources": len(unique_sources),
        "n_primary_sources": len(primary_sources),
        "n_citations": len(unique_sources),
    }


# ─────────────────────────── self-test: replay REAL 绿色算力 ───────────────────────────
if __name__ == "__main__":
    # Faithful to the real run: C1/C2/C3 framed up front; adversary discovers C4@R5, C5@R6, C6@R9.
    INIT = [
        {"id": "C1", "label": "时空错配/储能成本",  "monitor_anchor": "西部到户综合电价(含储能), 储能EPC元/Wh"},
        {"id": "C2", "label": "液冷/PFAS介质",     "monitor_anchor": "冷板式市占率, 巨化/新宙邦氟化液产能"},
        {"id": "C3", "label": "WUE水资源红线",     "monitor_anchor": "西部干冷器节点实测WUE, 水预算配额"},
    ]
    LATE = {5: {"id": "C4", "label": "电网零惯量/RoCoF",  "monitor_anchor": "GFM-BESS循环寿命@阶跃负荷, RoCoF实测"},
            6: {"id": "C5", "label": "变压器/GOES产能墙", "monitor_anchor": "0.18mm取向硅钢良率, 变压器交付周期"},
            9: {"id": "C6", "label": "需求/供给过剩/绿证","monitor_anchor": "智算上架率, 绿证均价, 训练/推理结构占比"}}
    SIG = {
        "C1": {1:-0.5,3:0.5,4:0.5,5:0.5,7:0.5,8:0.5,9:1.0,10:0.5,11:0.5,12:-0.5},
        "C2": {2:-0.5,3:0.5,4:0.5,5:1.0,6:0.5,8:0.5,9:1.0,11:0.5,12:0.5},
        "C3": {1:-0.5,2:0.5,3:0.5,4:1.0,7:0.5,11:-0.5},
        "C4": {5:-0.5,7:0.5,8:0.5,9:1.0,10:0.5,12:-1.0},
        "C5": {6:-0.5,8:0.5,11:1.0,12:-0.3},
        "C6": {9:-1.0,10:-0.5,11:0.2},
    }
    st = new_state("绿色算力景气度与产业链", "绿色算力产业链是否值得做多(3-6月)", "3-6M", INIT)
    OLD = [33.33,24.53,12.4,6.61,3.42,1.14,0.29,0.07,0.0,0.0,0.0,0.0]
    stop_round, active_per_round = None, []
    print("旧引擎单一后验:  " + " → ".join(f"{p:.1f}" for p in OLD) + "   (撞0钉死, 跑满12轮)\n")
    print("新引擎每轮快照 (辩论支持度/100；R=已退休不再派agent):")
    for r in range(1, 13):
        if r in LATE: add_crux(st, LATE[r], r)
        active = [cid for cid, cx in st["cruxes"].items() if not cx["retired"]]
        active_per_round.append(len(active))
        js = {cid: {"signal": SIG[cid].get(r, 0.0), "best_bull": "(略)", "best_bear": "(略)",
                    "citations": ([{"claim": f"demo-{cid}-r{r}", "number": "1", "source": "demo", "url": f"https://fixture-research.org/source/{cid}/{r}", "date": "2026"}]
                                  if SIG[cid].get(r, 0.0) != 0 else [])}
              for cid in st["cruxes"]}
        conv = submit_round(st, r, js)
        line = " ".join(f"{cid}:{int(round(st['cruxes'][cid]['p_history'][-1]*100)):>3}"
                        + ("R" if st['cruxes'][cid]['retired'] else " ") for cid in st["cruxes"])
        dt = st["decision_trace"][-1]
        print(f"  R{r:<2}[{len(active)}活跃] {line.ljust(48)} | 弱={dt['weakest']}({int(dt['p_weakest']*100)}/100) {dt['decision']:<22} {conv['decision']}")
        if conv["decision"] in ("converge", "fuse_break") and stop_round is None:
            stop_round = r; break
    old_calls = 12 * 6 * 2                     # 12 rounds × 6 cruxes × 2 agents (no scoping)
    new_calls = sum(active_per_round) * 2      # only active cruxes × 2 agents
    stop_label = "收敛" if conv["decision"] == "converge" else f"停止({conv['decision']})"
    print(f"\n→ 新引擎 R{stop_round} {stop_label}, 且正确暴露了 C6(旧引擎在 R6 的 buggy 版本会漏掉它)。")
    print(f"  子智能体调用(crux×agent): 旧≈{old_calls} 次 → 新≈{new_calls} 次  (省 ~{round((1-new_calls/old_calls)*100)}%, 主要来自 crux 收窄)")
    print(f"  平均每轮活跃 crux: {sum(active_per_round)/len(active_per_round):.1f} / 6\n")
    rd = report_data(st)
    print(f"研究状态: {rd['decision']}  | binding crux: {rd['binding_crux']} "
          f"(辩论支持度 {int(rd['support_weakest']*100)}) | 命题均值支持度 {int(rd['support_mean']*100)}")
    print("每条 crux 终局 (弱→强, 自动带监控锚点+引用计数):")
    for c in rd["cruxes"]:
        print(f"  {c['id']} {c['label'].ljust(18)} {int(c['support_score']*100):>3}/100  {c['status']:<14} "
              f"引用×{len(c['citations'])}  盯: {c['monitor_anchor']}")
