#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic, non-promotional exploration ledger.

This module preserves bold hypotheses before the evidence gate.  It can normalize
WildHypotheses, attach and de-duplicate ProxyTrails, compute a research-queue
priority, and derive a break-even threshold from explicitly supplied payoff
magnitudes.

The ledger has no authority to create an OpportunitySeed, invoke CandidateScreen,
recommend a trade, or size a position.  ``EVIDENCE_BACKED`` in this module means
only that two distinct ProxyTrails have structurally valid evidence from two
independent publisher domains and retain the strongest alternative explanation.
It is not an investability or promotion state.
"""

from copy import deepcopy
import calendar
from datetime import date
from decimal import Decimal, DecimalException, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import re
import unicodedata

try:
    from crux_engine import (
        citation_identity,
        citation_publisher_identity,
        citation_source_identity,
        valid_citation,
    )
except ImportError:  # pragma: no cover - package-style import compatibility
    from .crux_engine import (
        citation_identity,
        citation_publisher_identity,
        citation_source_identity,
        valid_citation,
    )


SCHEMA_VERSION = "trade-nothing.hypothesis-ledger.v1"
HYPOTHESIS_ONLY = "HYPOTHESIS_ONLY"
TRACED = "TRACED"
EVIDENCE_BACKED = "EVIDENCE_BACKED"
HYPOTHESIS_STATES = (HYPOTHESIS_ONLY, TRACED, EVIDENCE_BACKED)

THESIS_CHALLENGE = "THESIS_CHALLENGE"
OPPORTUNITY_DISCOVERY = "OPPORTUNITY_DISCOVERY"
HYBRID = "HYBRID"
RESEARCH_INTENTS = {THESIS_CHALLENGE, OPPORTUNITY_DISCOVERY, HYBRID}

PROXY_DIRECTIONS = {"SUPPORTS", "CONTRADICTS", "AMBIGUOUS"}
ROLES = ("detective", "inquisitor")
MAX_SPARKS_PER_ROLE_ROUND = 3
MAX_PROXY_TRAILS_PER_ROLE_ROUND = 3
ARCHETYPES = {
    "DIRECT_CAPTURE",
    "BOTTLENECK_OWNER",
    "ENABLER_OR_INPUT",
    "SUBSTITUTE_OR_AVOIDANCE",
    "ADVERSE_EXPOSURE",
}

PRIORITY_SEMANTICS = (
    "Deterministic exploration-queue heuristic only; not a probability, "
    "expected return, recommendation, trade instruction, or position-sizing input."
)
BREAK_EVEN_SEMANTICS = (
    "Threshold implied only by the explicitly supplied upside/downside magnitudes; "
    "not an estimated probability, expected return, recommendation, or sizing input."
)
CAPABILITY_BOUNDARY = {
    "mode": "EXPLORATION_ONLY",
    "promotion_authority": "NONE",
    "prohibited_transitions": [
        "CREATE_OPPORTUNITY_SEED",
        "RUN_CANDIDATE_SCREEN",
        "CREATE_TRADE",
        "SIZE_POSITION",
    ],
}
SMALL_RESEARCH_BUDGET = {
    "max_bounded_queries": 1,
    "max_documents_read": 3,
    "max_new_proxy_trails": 1,
    "max_new_publisher_domains": 1,
    "automatic_follow_on": False,
}
MAX_PAYOFF_MAGNITUDE = Decimal("1000000000000")
SCENARIO_PATH_TYPES = ("BULL_SURPRISE", "BASE", "BEAR_FAILURE")
UNKNOWN_PAYOFF_UNITS = {
    "",
    "unspecified_same_unit",
    "unknown",
    "tbd",
    "n/a",
    "na",
    "none",
    "null",
}
QUALITATIVE_UPSIDE = {"UNKNOWN", "MODEST", "MATERIAL", "OUTSIZED"}
QUALITATIVE_CONVEXITY = {"UNKNOWN", "LINEAR", "CONVEX", "OPTION_LIKE"}
QUALITATIVE_DOWNSIDE = {"UNKNOWN", "LIMITED", "MATERIAL", "SEVERE"}
QUALITATIVE_TIME_TO_SIGNAL = {"UNKNOWN", "NEAR", "MEDIUM", "LONG"}

# These fields would turn the exploration ledger into a promotion or execution
# surface.  Reject them rather than silently carrying privileged instructions.
FORBIDDEN_SPARK_FIELDS = {
    "opportunity_seed",
    "opportunity_seeds",
    "candidate_screen",
    "candidate_screens",
    "trade",
    "trade_action",
    "order",
    "position",
    "position_size",
    "sizing",
    "target_price",
    "expected_return",
}

_TEXT_FIELDS = (
    "observation",
    "why_nonconsensus",
    "surprise_if_true",
    "strongest_alternative_explanation",
    "value_transfer",
    "economic_capture_test",
    "pricing_question",
    "cheap_discriminating_test",
    "falsifier",
    "catalyst",
    "expiry_date",
)


def _text(value):
    return " ".join(str(value or "").split())


def _norm(value):
    """Identity normalization that preserves meaning-bearing operators."""
    normalized = unicodedata.normalize("NFKC", _text(value)).casefold()
    normalized = re.sub(
        r"""[\s,;!?，。；：！？'"“”‘’`]+""", "", normalized
    )
    # A decimal point changes numeric meaning (1.5% != 15%); sentence-ending
    # punctuation does not.
    normalized = re.sub(r"(?<!\d)\.|\.(?!\d)", "", normalized)
    return re.sub(r"(?<!\d):|:(?!\d)", "", normalized)


def _hash_id(prefix, value, length=12):
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:length].upper()
    return f"{prefix}-{digest}"


def _hypothesis_id(statement):
    return _hash_id("WH", _norm(statement))


def _proxy_id(
    hypothesis_id, proxy, causal_link, direction=None, origin_crux=None
):
    key = "|".join((
        hypothesis_id,
        _norm(proxy),
        _norm(causal_link),
    ))
    return _hash_id("PT", key)


def _proxy_maturity_key(proxy):
    """Identity of one planned causal diagnostic, not one observed value."""
    proxy = proxy if isinstance(proxy, dict) else {}
    return "|".join((
        _norm(proxy.get("planned_proxy") or proxy.get("proxy")),
        _norm(
            proxy.get("causal_link")
            or proxy.get("why_diagnostic")
        ),
    ))


def _evidence_id(citation):
    key = citation_identity(citation)
    return _hash_id("PE", key)


def _reason(audit, reason, amount=1):
    audit["rejected"] = audit.get("rejected", 0) + amount
    reasons = audit.setdefault("rejected_reasons", {})
    reasons[reason] = reasons.get(reason, 0) + amount


def _new_audit(round_num=None):
    audit = {
        "submitted_sparks": 0,
        "accepted_new_hypotheses": 0,
        "merged_hypotheses": 0,
        "submitted_proxy_trails": 0,
        "accepted_new_proxy_trails": 0,
        "duplicate_proxy_trails": 0,
        "submitted_evidence": 0,
        "accepted_evidence": 0,
        "merged_proxy_evidence": 0,
        "duplicate_evidence": 0,
        "rejected": 0,
        "rejected_reasons": {},
    }
    if round_num is not None:
        audit["round"] = int(round_num)
    return audit


def infer_research_intent(frame):
    """Return explicit intent or a backwards-compatible legacy inference."""
    frame = frame if isinstance(frame, dict) else {}
    explicit = _text(frame.get("research_intent")).upper()
    if explicit:
        return explicit

    if (
        isinstance(frame.get("hypothesis_garden"), (dict, list))
        or isinstance(frame.get("wild_hypotheses"), list)
    ):
        return HYBRID

    if isinstance(frame.get("landscape_map"), dict):
        return HYBRID

    cruxes = frame.get("candidate_cruxes")
    if cruxes is None and isinstance(frame.get("cruxes"), dict):
        cruxes = list(frame["cruxes"].values())
    for crux in cruxes or []:
        if (
            isinstance(crux, dict)
            and _text(crux.get("logic_role")).upper() == "OPPORTUNITY_PATH"
        ):
            return HYBRID
    return THESIS_CHALLENGE


def is_required(frame_or_state):
    """Whether the frame explicitly or implicitly requires an exploration track."""
    value = frame_or_state if isinstance(frame_or_state, dict) else {}
    ledger = value.get("hypothesis_ledger")
    if isinstance(ledger, dict):
        return ledger.get("research_intent") in {OPPORTUNITY_DISCOVERY, HYBRID}
    return infer_research_intent(value) in {OPPORTUNITY_DISCOVERY, HYBRID}


def _garden(frame):
    """Return (raw hypotheses, structural issue or None)."""
    if not isinstance(frame, dict):
        return [], "frame_must_be_object"
    if "hypothesis_garden" in frame:
        garden = frame.get("hypothesis_garden")
        if isinstance(garden, list):
            return garden, None
        if isinstance(garden, dict):
            raw = garden.get("wild_hypotheses")
            if raw is None:
                raw = garden.get("hypotheses")
            if isinstance(raw, list):
                return raw, None
            return [], "hypothesis_garden_wild_hypotheses_must_be_list"
        return [], "hypothesis_garden_must_be_list_or_object"
    if "wild_hypotheses" in frame:
        raw = frame.get("wild_hypotheses")
        if isinstance(raw, list):
            return raw, None
        return [], "wild_hypotheses_must_be_list"
    legacy = frame.get("landscape_map")
    if isinstance(legacy, dict) and isinstance(legacy.get("paths"), list):
        return legacy["paths"], None
    return [], None


def _garden_source(frame):
    if not isinstance(frame, dict):
        return "NONE"
    if "hypothesis_garden" in frame or "wild_hypotheses" in frame:
        return "HYPOTHESIS_GARDEN"
    legacy = frame.get("landscape_map")
    if isinstance(legacy, dict) and isinstance(legacy.get("paths"), list):
        return "LEGACY_LANDSCAPE_MAP"
    return "NONE"


def _statement(raw):
    if not isinstance(raw, dict):
        return ""
    return (
        _text(raw.get("hypothesis"))
        or _text(raw.get("statement"))
        or _text(raw.get("claim"))
    )


def _chain(raw):
    if not isinstance(raw, dict):
        return []
    value = raw.get("causal_chain")
    if value is None:
        value = raw.get("value_transfer_chain")
    if isinstance(value, str):
        parts = re.split(r"\s*(?:->|→)\s*", value)
        return [_text(item) for item in parts if _text(item)]
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value if _text(item)]


def _raw_proxy_list(raw):
    if not isinstance(raw, dict):
        return []
    value = raw.get("proxy_trails")
    if value is None:
        value = raw.get("proxy_trail")
    if value is None:
        return []
    return value if isinstance(value, list) else []


def _raw_proxy_plan(raw):
    if not isinstance(raw, dict):
        return []
    value = raw.get("proxy_plan")
    return value if isinstance(value, list) else []


def _date_text_is_valid(value):
    value = _text(value)
    if re.fullmatch(r"\d{4}-\d{2}", value):
        try:
            month = int(value[-2:])
        except ValueError:
            return False
        return 1 <= month <= 12
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return bool(value)


def _evidence_date_on_or_before_as_of(value, as_of_date):
    """Compare day-precise dates exactly and month buckets by YYYY-MM."""
    published = _text(value)
    cutoff = _text(as_of_date)
    if not cutoff:
        return True
    try:
        cutoff_day = date.fromisoformat(cutoff)
    except ValueError:
        return False
    if re.fullmatch(r"\d{4}-\d{2}", published):
        year, month = (int(part) for part in published.split("-"))
        published_upper_bound = date(
            year, month, calendar.monthrange(year, month)[1]
        )
        return published_upper_bound <= cutoff_day
    try:
        return date.fromisoformat(published) <= cutoff_day
    except ValueError:
        return False


def _canonical_url(value):
    return citation_source_identity({
        "claim": "_",
        "source": "_",
        "date": "_",
        "url": _text(value),
    })


def _normalize_evidence(raw, audit, as_of_date=None):
    if not isinstance(raw, dict):
        _reason(audit, "proxy_evidence_not_object")
        return None
    claim = _text(raw.get("claim"))
    source = _text(raw.get("source"))
    published = _text(raw.get("date"))
    if not claim:
        _reason(audit, "proxy_evidence_missing_claim")
        return None
    if not source:
        _reason(audit, "proxy_evidence_missing_source")
        return None
    if not _date_text_is_valid(published):
        _reason(audit, "proxy_evidence_invalid_date")
        return None
    if not _evidence_date_on_or_before_as_of(published, as_of_date):
        _reason(audit, "proxy_evidence_after_as_of")
        return None
    candidate = {
        **raw,
        "claim": claim,
        "source": source,
        "date": published,
        "url": _text(raw.get("url")),
    }
    if not valid_citation(candidate):
        _reason(audit, "proxy_evidence_invalid_url")
        return None
    url = citation_source_identity(candidate)
    citation = {
        "claim": claim,
        "source": source,
        "url": url,
        "date": published,
    }
    number = raw.get("number")
    if number is not None and _text(number):
        citation["number"] = _text(number)
    tier = _text(raw.get("source_tier")).lower()
    if tier:
        citation["source_tier"] = (
            tier if tier in {"primary", "secondary"} else "other"
        )
    citation["evidence_id"] = _evidence_id(citation)
    audit["accepted_evidence"] += 1
    return citation


def _evidence_list(raw, audit, as_of_date=None):
    value = raw.get("evidence") if isinstance(raw, dict) else None
    if value is None:
        return []
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        _reason(audit, "proxy_evidence_must_be_object_or_list")
        return []
    audit["submitted_evidence"] += len(value)
    accepted = {}
    for item in value:
        normalized = _normalize_evidence(
            item, audit, as_of_date=as_of_date
        )
        if not normalized:
            continue
        evidence_id = normalized["evidence_id"]
        if evidence_id in accepted:
            audit["duplicate_evidence"] += 1
            continue
        accepted[evidence_id] = normalized
    return [accepted[key] for key in sorted(accepted)]


def _normalize_proxy_plan(raw):
    """Normalize a Framer route without turning it into an observed ProxyTrail."""
    if not isinstance(raw, dict):
        return None
    proxy = _text(raw.get("proxy"))
    why_diagnostic = (
        _text(raw.get("why_diagnostic"))
        or _text(raw.get("causal_link"))
    )
    if not proxy or not why_diagnostic:
        return None
    return {
        "proxy": proxy,
        "why_diagnostic": why_diagnostic,
        "causal_link": why_diagnostic,
        "direction": (
            _text(raw.get("direction")).upper()
            if _text(raw.get("direction")).upper() in PROXY_DIRECTIONS
            else "AMBIGUOUS"
        ),
        "alternative_explanation": _text(
            raw.get("alternative_explanation")
        ),
        "checkpoint": _text(raw.get("checkpoint")),
        "origin_crux": _text(raw.get("origin_crux")) or None,
        "publisher_class": _text(raw.get("publisher_class")) or None,
        "next_source_class": (
            _text(raw.get("next_source_class"))
            or _text(raw.get("publisher_class"))
            or None
        ),
        "bounded_query": _text(raw.get("bounded_query")) or None,
        "stop_condition": _text(raw.get("stop_condition")) or None,
    }


def _normalize_proxy(
    raw,
    hypothesis_id,
    source_agent,
    round_num,
    audit,
    as_of_date=None,
):
    audit["submitted_proxy_trails"] += 1
    if not isinstance(raw, dict):
        _reason(audit, "proxy_trail_not_object")
        return None
    proxy = (
        _text(raw.get("proxy"))
        or _text(raw.get("observation"))
        or _text(raw.get("signal"))
    )
    causal_link = (
        _text(raw.get("causal_link"))
        or _text(raw.get("why_diagnostic"))
        or _text(raw.get("inference"))
        or _text(raw.get("why_it_matters"))
    )
    direction = _text(raw.get("direction")).upper() or "AMBIGUOUS"
    if not proxy:
        _reason(audit, "proxy_trail_missing_proxy")
        return None
    if not causal_link:
        _reason(audit, "proxy_trail_missing_causal_link")
        return None
    if direction not in PROXY_DIRECTIONS:
        _reason(audit, "proxy_trail_invalid_direction")
        return None
    evidence = _evidence_list(raw, audit, as_of_date=as_of_date)
    supplied_trail_id = _text(raw.get("trail_id"))
    origin_crux = _text(raw.get("origin_crux")) or None
    item = {
        "proxy_id": _proxy_id(
            hypothesis_id, proxy, causal_link, direction, origin_crux
        ),
        "trail_id": supplied_trail_id or None,
        "trail_ids": [supplied_trail_id] if supplied_trail_id else [],
        "route_id": _text(raw.get("route_id")) or None,
        "planned_proxy": _text(raw.get("planned_proxy")) or None,
        "planned_direction": (
            _text(raw.get("planned_direction")).upper() or None
        ),
        "proxy": proxy,
        "causal_link": causal_link,
        "why_diagnostic": causal_link,
        "alternative_explanation": _text(
            raw.get("alternative_explanation")
        ),
        "direction": direction,
        "origin_crux": origin_crux,
        "origin_cruxes": [origin_crux] if origin_crux else [],
        "checkpoint": _text(raw.get("checkpoint")),
        "publisher_class": _text(raw.get("publisher_class")) or None,
        "next_source_class": _text(raw.get("next_source_class")) or None,
        "bounded_query": _text(raw.get("bounded_query")) or None,
        "stop_condition": _text(raw.get("stop_condition")) or None,
        "evidence": evidence,
        "source_agents": [source_agent],
        "first_seen_round": int(round_num),
        "last_seen_round": int(round_num),
    }
    item["direction_bindings"] = [{
        "direction": direction,
        "evidence_ids": sorted(
            citation["evidence_id"]
            for citation in evidence
            if citation.get("evidence_id")
        ),
        "source_agent": source_agent,
        "round": int(round_num),
        "trail_id": supplied_trail_id or None,
        "route_id": item.get("route_id"),
        "origin_crux": origin_crux,
        "authorized_action_id": None,
    }]
    return item


def _numeric_magnitude(value):
    if value is None or value == "":
        return None, "missing"
    if isinstance(value, bool):
        return None, "invalid"
    try:
        parsed = Decimal(str(value).strip())
    except (DecimalException, ValueError, TypeError):
        return None, "invalid"
    if not parsed.is_finite() or parsed < 0:
        return None, "invalid"
    # Payoff magnitudes are only relative research inputs. Bounding them keeps
    # hostile exponents from reaching Decimal.quantize and crashing a submit.
    if parsed != 0 and (
        parsed.adjusted() > MAX_PAYOFF_MAGNITUDE.adjusted()
        or parsed > MAX_PAYOFF_MAGNITUDE
    ):
        return None, "out_of_range"
    return parsed, None


def _decimal_output(value):
    try:
        quantized = value.quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        return float(quantized)
    except (DecimalException, OverflowError, ValueError):
        return None


def break_even_threshold(upside, downside):
    """Return p*=downside/(upside+downside), or an explicit UNKNOWN result.

    ``upside`` and ``downside`` are non-negative magnitudes in the same unit.
    The function estimates no success probability.
    """
    up, up_issue = _numeric_magnitude(upside)
    down, down_issue = _numeric_magnitude(downside)
    reasons = []
    if up_issue:
        reasons.append(f"{up_issue}_upside")
    if down_issue:
        reasons.append(f"{down_issue}_downside")
    if reasons:
        return {
            "status": "UNKNOWN",
            "p_star": None,
            "p_star_percent": None,
            "formula": "downside / (upside + downside)",
            "reason": ",".join(reasons),
            "semantics": BREAK_EVEN_SEMANTICS,
        }
    denominator = up + down
    if denominator == 0:
        return {
            "status": "UNKNOWN",
            "p_star": None,
            "p_star_percent": None,
            "formula": "downside / (upside + downside)",
            "reason": "zero_total_payoff_magnitude",
            "semantics": BREAK_EVEN_SEMANTICS,
        }
    try:
        p_star = down / denominator
    except DecimalException:
        return {
            "status": "UNKNOWN",
            "p_star": None,
            "p_star_percent": None,
            "formula": "downside / (upside + downside)",
            "reason": "decimal_arithmetic_invalid",
            "semantics": BREAK_EVEN_SEMANTICS,
        }
    return {
        "status": "KNOWN",
        "p_star": _decimal_output(p_star),
        "p_star_percent": _decimal_output(p_star * Decimal("100")),
        "formula": "downside / (upside + downside)",
        "inputs": {
            "upside": _decimal_output(up),
            "downside": _decimal_output(down),
        },
        "semantics": BREAK_EVEN_SEMANTICS,
    }


def normalize_scenario_paths(raw_paths, as_of_date=None):
    """Validate and type the Inquisitor's symmetric, non-probabilistic paths."""
    if raw_paths is None:
        return {
            "status": "MISSING",
            "issues": ["scenario_paths_missing"],
            "paths": [],
            "break_even_threshold": {
                "status": "UNKNOWN",
                "p_star": None,
                "p_star_percent": None,
                "formula": "downside / (upside + downside)",
                "reason": "scenario_paths_missing",
                "semantics": BREAK_EVEN_SEMANTICS,
            },
        }
    if not isinstance(raw_paths, list):
        return {
            "status": "INVALID",
            "issues": ["scenario_paths_must_be_list"],
            "paths": [],
            "break_even_threshold": {
                "status": "UNKNOWN",
                "p_star": None,
                "p_star_percent": None,
                "formula": "downside / (upside + downside)",
                "reason": "invalid_scenario_paths",
                "semantics": BREAK_EVEN_SEMANTICS,
            },
        }
    issues = []
    by_type = {}
    required = (
        "summary",
        "trigger_event",
        "transmission_chain",
        "timeline",
        "monitor_anchor",
        "falsifier",
    )
    for index, raw in enumerate(raw_paths):
        prefix = f"scenario_path_{index + 1}"
        if not isinstance(raw, dict):
            issues.append(f"{prefix}_must_be_object")
            continue
        path_type = _text(raw.get("path_type")).upper()
        if path_type not in SCENARIO_PATH_TYPES:
            issues.append(f"{prefix}_invalid_path_type")
            continue
        if path_type in by_type:
            issues.append(f"{prefix}_duplicate_path_type")
            continue
        missing = [field for field in required if not _text(raw.get(field))]
        issues.extend(f"{prefix}_missing_{field}" for field in missing)
        payoff, payoff_issue = _numeric_magnitude(raw.get("payoff_magnitude"))
        if raw.get("payoff_magnitude") not in (None, "") and payoff_issue:
            issues.append(f"{prefix}_{payoff_issue}_payoff_magnitude")
        evidence = raw.get("evidence", [])
        if evidence is None:
            evidence = []
        if not isinstance(evidence, list):
            issues.append(f"{prefix}_evidence_must_be_list")
            evidence = []
        valid_evidence = []
        for item in evidence:
            if not (
                isinstance(item, dict)
                and valid_citation(item)
                and _date_text_is_valid(item.get("date"))
            ):
                continue
            if not _evidence_date_on_or_before_as_of(
                item.get("date"), as_of_date
            ):
                issues.append(f"{prefix}_evidence_after_as_of")
                continue
            valid_evidence.append(deepcopy(item))
        if len(valid_evidence) != len(evidence):
            issues.append(f"{prefix}_contains_invalid_evidence")
        by_type[path_type] = {
            "path_type": path_type,
            **{field: _text(raw.get(field)) for field in required},
            "payoff_magnitude": (
                _decimal_output(payoff) if payoff is not None else None
            ),
            "payoff_unit": (
                _text(raw.get("payoff_unit"))
                or "UNSPECIFIED_SAME_UNIT"
            ),
            "evidence": valid_evidence,
        }
    for path_type in SCENARIO_PATH_TYPES:
        if path_type not in by_type:
            issues.append(f"scenario_paths_missing_{path_type.lower()}")
    paths = [by_type[path_type] for path_type in SCENARIO_PATH_TYPES if path_type in by_type]
    bull = by_type.get("BULL_SURPRISE", {})
    bear = by_type.get("BEAR_FAILURE", {})
    bull_unit = _text(bull.get("payoff_unit"))
    bear_unit = _text(bear.get("payoff_unit"))
    if (
        bull_unit
        and bear_unit
        and bull_unit.casefold() not in UNKNOWN_PAYOFF_UNITS
        and bull_unit.casefold() == bear_unit.casefold()
    ):
        threshold = break_even_threshold(
            bull.get("payoff_magnitude"), bear.get("payoff_magnitude")
        )
    else:
        threshold = {
            "status": "UNKNOWN",
            "p_star": None,
            "p_star_percent": None,
            "formula": "downside / (upside + downside)",
            "reason": "scenario_payoffs_missing_or_not_same_unit",
            "semantics": BREAK_EVEN_SEMANTICS,
        }
    return {
        "status": "VALID" if not issues else "INVALID",
        "issues": sorted(set(issues)),
        "paths": paths,
        "break_even_threshold": threshold,
        "semantics": (
            "Symmetric scenario audit only; no path probability, expected "
            "return, recommendation, trade, or sizing authority."
        ),
    }


def ingest_scenario_paths(state, round_num, inquisitor):
    """Persist a typed receipt without letting scenario prose affect scoring."""
    raw = inquisitor.get("scenario_paths") if isinstance(inquisitor, dict) else None
    receipt = normalize_scenario_paths(
        raw,
        as_of_date=state.get("frame_contract", {}).get("as_of_date"),
    )
    receipt["round"] = int(round_num)
    state.setdefault("scenario_path_ledger", []).append(deepcopy(receipt))
    return receipt


def scenario_view(state):
    records = state.get("scenario_path_ledger", []) if isinstance(state, dict) else []
    if records:
        return deepcopy(records[-1])
    return normalize_scenario_paths(None)


def _payoff(raw):
    raw = raw if isinstance(raw, dict) else {}
    nested = raw.get("payoff")
    nested = nested if isinstance(nested, dict) else {}
    upside = nested.get("upside") if "upside" in nested else raw.get("upside")
    downside = (
        nested.get("downside") if "downside" in nested else raw.get("downside")
    )
    unit = _text(nested.get("unit") if "unit" in nested else raw.get("payoff_unit"))
    up, _ = _numeric_magnitude(upside)
    down, _ = _numeric_magnitude(downside)
    return {
        "upside": _decimal_output(up) if up is not None else None,
        "downside": _decimal_output(down) if down is not None else None,
        "unit": unit or "UNSPECIFIED_SAME_UNIT",
    }


def _asymmetry_case(raw):
    raw = raw if isinstance(raw, dict) else {}
    nested = raw.get("asymmetry_case")
    if not isinstance(nested, dict):
        nested = raw.get("qualitative_asymmetry")
    nested = nested if isinstance(nested, dict) else {}

    def enum(field, allowed):
        value = _text(nested.get(field)).upper()
        return value if value in allowed else "UNKNOWN"

    return {
        "upside_shape": enum("upside_shape", QUALITATIVE_UPSIDE),
        "convexity": enum("convexity", QUALITATIVE_CONVEXITY),
        "downside_shape": enum("downside_shape", QUALITATIVE_DOWNSIDE),
        "time_to_signal": enum(
            "time_to_signal", QUALITATIVE_TIME_TO_SIGNAL
        ),
        "basis": _text(nested.get("basis")),
    }


def _asymmetry_case_is_substantive(value):
    if not isinstance(value, dict):
        return False
    return bool(
        _text(value.get("basis"))
        or any(
            _text(value.get(field)).upper() not in {"", "UNKNOWN"}
            for field in (
                "upside_shape",
                "convexity",
                "downside_shape",
                "time_to_signal",
            )
        )
    )


def _payoff_break_even(payoff):
    """Require an explicit common unit before using payoff asymmetry."""
    payoff = payoff if isinstance(payoff, dict) else {}
    threshold = break_even_threshold(
        payoff.get("upside"), payoff.get("downside")
    )
    unit = _text(payoff.get("unit"))
    if (
        threshold.get("status") == "KNOWN"
        and unit.casefold() in UNKNOWN_PAYOFF_UNITS
    ):
        return {
            **threshold,
            "status": "UNKNOWN",
            "p_star": None,
            "p_star_percent": None,
            "reason": "missing_explicit_same_unit",
        }
    return threshold


def _payoff_key(payoff):
    payoff = payoff if isinstance(payoff, dict) else {}
    return (
        _text(payoff.get("unit")).casefold(),
        str(payoff.get("upside")),
        str(payoff.get("downside")),
    )


def _maturity_basis(hypothesis):
    trails = [
        item for item in hypothesis.get("proxy_trails", [])
        if isinstance(item, dict)
    ]
    evidence_trails = [
        item for item in trails
        if any(
            valid_citation(citation)
            for citation in item.get("evidence", [])
            if isinstance(citation, dict)
        )
    ]
    evidence_maturity_keys = {
        _proxy_maturity_key(item) for item in evidence_trails
    }
    publisher_domains = sorted({
        publisher
        for item in evidence_trails
        for citation in item.get("evidence", [])
        if isinstance(citation, dict)
        for publisher in [citation_publisher_identity(citation)]
        if publisher
    })
    has_alternative = bool(
        _text(hypothesis.get("strongest_alternative_explanation"))
    ) and not hypothesis.get("strongest_alternative_explanation_contested")
    return {
        "proxy_trail_count": len(trails),
        "evidence_bearing_proxy_trail_count": len(
            evidence_maturity_keys
        ),
        "independent_publisher_domain_count": len(publisher_domains),
        "publisher_domains": publisher_domains,
        "strongest_alternative_explanation_preserved": has_alternative,
        "evidence_backed_requirements": {
            "minimum_distinct_evidence_bearing_proxy_trails": 2,
            "minimum_independent_publisher_domains": 2,
            "strongest_alternative_explanation_required": True,
        },
    }


def _maturity(hypothesis):
    basis = _maturity_basis(hypothesis)
    if basis["proxy_trail_count"] == 0:
        return HYPOTHESIS_ONLY
    if (
        basis["evidence_bearing_proxy_trail_count"] >= 2
        and basis["independent_publisher_domain_count"] >= 2
        and basis["strongest_alternative_explanation_preserved"]
    ):
        return EVIDENCE_BACKED
    return TRACED


def exploration_priority(hypothesis):
    """Compute a bounded research-queue heuristic, never an investment score."""
    hypothesis = hypothesis if isinstance(hypothesis, dict) else {}
    state_name = (
        hypothesis.get("state")
        if hypothesis.get("state") in HYPOTHESIS_STATES
        else _maturity(hypothesis)
    )
    trails = [
        item for item in hypothesis.get("proxy_trails", [])
        if isinstance(item, dict)
    ]

    # A traced-but-unverified idea has the highest immediate information value:
    # its test is specified and still unresolved.  Evidence-backed ideas remain
    # in the exploration ledger for disconfirmation, not automatic promotion.
    information_gap = {
        HYPOTHESIS_ONLY: 2,
        TRACED: 3,
        EVIDENCE_BACKED: 1,
    }[state_name]

    testability = 0
    reasons = []
    if len(hypothesis.get("causal_chain", [])) >= 2:
        testability += 1
        reasons.append("causal_chain_declared")
    if _text(hypothesis.get("falsifier")):
        testability += 1
        reasons.append("falsifier_declared")
    if trails:
        testability += 1
        reasons.append("proxy_trail_available")

    threshold = hypothesis.get("break_even_threshold")
    if not isinstance(threshold, dict):
        payoff = hypothesis.get("payoff") or {}
        threshold = _payoff_break_even(payoff)
    asymmetry_interest = 0
    if threshold.get("status") == "KNOWN":
        p_star = threshold["p_star"]
        if p_star <= 0.20:
            asymmetry_interest = 3
        elif p_star <= 0.35:
            asymmetry_interest = 2
        elif p_star <= 0.50:
            asymmetry_interest = 1
        reasons.append("explicit_break_even_threshold_available")

    qualitative = hypothesis.get("asymmetry_case") or {}
    qualitative_interest = 0
    time_to_signal = 0
    if (
        isinstance(qualitative, dict)
        and _text(qualitative.get("basis"))
        and not hypothesis.get("asymmetry_case_contested")
    ):
        upside = {
            "MODEST": 0,
            "MATERIAL": 1,
            "OUTSIZED": 2,
        }.get(_text(qualitative.get("upside_shape")).upper(), 0)
        convexity = (
            1
            if _text(qualitative.get("convexity")).upper()
            in {"CONVEX", "OPTION_LIKE"}
            else 0
        )
        downside_friction = {
            "LIMITED": 0,
            "MATERIAL": 1,
            "SEVERE": 2,
        }.get(_text(qualitative.get("downside_shape")).upper(), 0)
        qualitative_interest = max(
            0, min(3, upside + convexity - downside_friction)
        )
        if _text(qualitative.get("time_to_signal")).upper() == "NEAR":
            time_to_signal = 1
        if qualitative_interest:
            reasons.append(
                "declared_qualitative_upside_survives_downside_friction"
            )
        if time_to_signal:
            reasons.append("near_discriminating_signal_declared")
    asymmetry_interest = max(
        asymmetry_interest, qualitative_interest
    )

    nonconsensus = 1 if _text(hypothesis.get("why_nonconsensus")) else 0
    if nonconsensus:
        reasons.append("nonconsensus_claim_declared")
    score = (
        information_gap
        + testability
        + asymmetry_interest
        + time_to_signal
        + nonconsensus
    )
    band = "EXPLORE_NOW" if score >= 8 else "EXPLORE_NEXT" if score >= 5 else "PARK"
    return {
        "band": band,
        "score": score,
        "components": {
            "information_gap": information_gap,
            "testability": testability,
            "asymmetry_interest": asymmetry_interest,
            "qualitative_asymmetry_interest": qualitative_interest,
            "time_to_signal": time_to_signal,
            "nonconsensus": nonconsensus,
        },
        "reasons": reasons,
        "semantics": PRIORITY_SEMANTICS,
    }


def _refresh(hypothesis):
    hypothesis["proxy_trails"] = sorted(
        [
            item for item in hypothesis.get("proxy_trails", [])
            if isinstance(item, dict)
        ],
        key=lambda item: item.get("proxy_id", ""),
    )
    hypothesis["maturity_basis"] = _maturity_basis(hypothesis)
    hypothesis["state"] = _maturity(hypothesis)
    payoff = hypothesis.get("payoff") or {}
    if hypothesis.get("payoff_contested"):
        hypothesis["break_even_threshold"] = {
            "status": "UNKNOWN",
            "p_star": None,
            "p_star_percent": None,
            "formula": "downside / (upside + downside)",
            "reason": "conflicting_explicit_payoffs",
            "semantics": BREAK_EVEN_SEMANTICS,
        }
    else:
        hypothesis["break_even_threshold"] = _payoff_break_even(payoff)
    hypothesis["exploration_priority"] = exploration_priority(hypothesis)
    return hypothesis


def _forbidden_fields(raw):
    if not isinstance(raw, dict):
        return []
    return sorted(FORBIDDEN_SPARK_FIELDS & set(raw))


def _normalize_spark(
    raw,
    source_agent,
    round_num,
    audit,
    allow_embedded_proxy_trails=True,
    as_of_date=None,
):
    audit["submitted_sparks"] += 1
    if not isinstance(raw, dict):
        _reason(audit, "hypothesis_spark_not_object")
        return None
    forbidden = _forbidden_fields(raw)
    if forbidden:
        for field in forbidden:
            _reason(audit, f"hypothesis_spark_forbidden_field:{field}")
        return None
    statement = _statement(raw)
    if not statement:
        _reason(audit, "hypothesis_spark_missing_hypothesis")
        return None
    hypothesis_id = _hypothesis_id(statement)
    supplied_ids = sorted({
        value
        for value in (
            _text(raw.get("spark_id")),
            _text(raw.get("hypothesis_id")),
        )
        if value
    })
    primary_spark_id = (
        _text(raw.get("spark_id"))
        or _text(raw.get("hypothesis_id"))
        or hypothesis_id
    )
    context = {
        "subject": _text(raw.get("subject")) or None,
        "origin_crux": (
            _text(raw.get("origin_crux"))
            or _text(raw.get("linked_crux_id"))
            or None
        ),
        "landscape_path_id": (
            _text(raw.get("landscape_path_id"))
            or _text(raw.get("path_id"))
            or None
        ),
        "archetype": _text(raw.get("archetype")).upper() or None,
    }
    context["origin_cruxes"] = (
        [context["origin_crux"]] if context["origin_crux"] else []
    )
    context["landscape_path_ids"] = (
        [context["landscape_path_id"]]
        if context["landscape_path_id"]
        else []
    )
    observation_evidence = _evidence_list(
        raw, audit, as_of_date=as_of_date
    )
    item = {
        "hypothesis_id": hypothesis_id,
        "spark_id": primary_spark_id,
        "spark_ids": supplied_ids,
        "hypothesis": statement,
        "observation": _text(raw.get("observation")),
        "why_nonconsensus": (
            _text(raw.get("why_nonconsensus"))
            or _text(raw.get("surprise_if_true"))
        ),
        "surprise_if_true": _text(raw.get("surprise_if_true")),
        "strongest_alternative_explanation": _text(
            raw.get("strongest_alternative_explanation")
        ),
        "causal_chain": _chain(raw),
        "value_transfer": _text(raw.get("value_transfer")),
        "economic_capture_test": _text(raw.get("economic_capture_test")),
        "pricing_question": _text(raw.get("pricing_question")),
        "cheap_discriminating_test": _text(raw.get("cheap_discriminating_test")),
        "scenario_paths": deepcopy(
            raw.get("scenario_paths")
            if isinstance(raw.get("scenario_paths"), dict)
            else {}
        ),
        "falsifier": (
            _text(raw.get("falsifier"))
            or _text(raw.get("disconfirming_observation"))
        ),
        "catalyst": _text(raw.get("catalyst")),
        "expiry_date": _text(raw.get("expiry_date")),
        "context": context,
        "payoff": _payoff(raw),
        "asymmetry_case": _asymmetry_case(raw),
        "proxy_plan": [
            plan
            for plan in (
                _normalize_proxy_plan(item)
                for item in _raw_proxy_plan(raw)
            )
            if plan
        ],
        "observation_evidence": observation_evidence,
        "proxy_trails": [],
        "source_agents": [source_agent],
        "first_seen_round": int(round_num),
        "last_seen_round": int(round_num),
    }
    if context.get("origin_crux"):
        for plan in item["proxy_plan"]:
            if not plan.get("origin_crux"):
                plan["origin_crux"] = context["origin_crux"]
    embedded_proxy_trails = _raw_proxy_list(raw)
    if embedded_proxy_trails and not allow_embedded_proxy_trails:
        audit["submitted_proxy_trails"] += len(embedded_proxy_trails)
        _reason(
            audit,
            f"{source_agent}_embedded_proxy_trails_ignored",
            len(embedded_proxy_trails),
        )
        embedded_proxy_trails = []
    for raw_proxy in embedded_proxy_trails:
        proxy = _normalize_proxy(
            raw_proxy,
            hypothesis_id,
            source_agent,
            round_num,
            audit,
            as_of_date=as_of_date,
        )
        if proxy:
            _merge_or_add_proxy(item, proxy, audit, count_new=False)
    return _refresh(item)


def normalize_wild_hypothesis(
    raw,
    source_agent="frame",
    round_num=0,
    as_of_date=None,
    allow_embedded_proxy_trails=False,
):
    """Public one-item normalizer used by adapters and tests."""
    audit = _new_audit(round_num)
    item = _normalize_spark(
        raw,
        _text(source_agent) or "unknown",
        round_num,
        audit,
        allow_embedded_proxy_trails=allow_embedded_proxy_trails,
        as_of_date=as_of_date,
    )
    return {
        "hypothesis": deepcopy(item),
        "audit": audit,
    }


def _field_variant(existing, field, value):
    current = existing.get(field)
    if not value or value == current:
        return
    variants = existing.setdefault("field_variants", {}).setdefault(field, [])
    for item in (current, value):
        if item and item not in variants:
            variants.append(deepcopy(item))
    variants.sort(key=lambda item: str(item))


def _merge_contested_field(existing, field, incoming_value):
    """Preserve all incompatible risk narratives and choose no role winner."""
    current = existing.get(field)
    if not incoming_value:
        return
    if not current:
        existing[field] = deepcopy(incoming_value)
        return
    if incoming_value == current:
        return
    _field_variant(existing, field, incoming_value)
    variants = existing.get("field_variants", {}).get(field, [])
    if variants:
        existing[field] = deepcopy(
            sorted(variants, key=lambda item: str(item))[0]
        )
    existing[f"{field}_contested"] = True


def _merge_or_add_proxy(hypothesis, incoming, audit, count_new=True):
    trails = hypothesis.setdefault("proxy_trails", [])
    existing = next(
        (
            item for item in trails
            if item.get("proxy_id") == incoming.get("proxy_id")
        ),
        None,
    )
    if existing is None:
        trails.append(deepcopy(incoming))
        if count_new:
            audit["accepted_new_proxy_trails"] += 1
        return
    audit["duplicate_proxy_trails"] += 1
    existing["trail_ids"] = sorted(set(
        existing.get("trail_ids", []) + incoming.get("trail_ids", [])
    ))
    if not existing.get("trail_id") and incoming.get("trail_id"):
        existing["trail_id"] = incoming["trail_id"]
    existing["last_seen_round"] = max(
        int(existing.get("last_seen_round") or 0),
        int(incoming.get("last_seen_round") or 0),
    )
    existing["source_agents"] = sorted(set(
        existing.get("source_agents", []) + incoming.get("source_agents", [])
    ))
    authorized_actions = {
        _text(value)
        for value in (
            *(existing.get("authorized_action_ids") or []),
            *(incoming.get("authorized_action_ids") or []),
            existing.get("authorized_action_id"),
            incoming.get("authorized_action_id"),
        )
        if _text(value)
    }
    existing["authorized_action_ids"] = sorted(authorized_actions)
    existing["authorized_action_id"] = (
        sorted(authorized_actions)[0] if authorized_actions else None
    )
    bindings = {
        (
            _text(item.get("action_id")),
            _text(item.get("route_id")),
            _text(item.get("planned_proxy")),
        )
        for item in (
            list(existing.get("authorized_route_bindings") or [])
            + list(incoming.get("authorized_route_bindings") or [])
        )
        if isinstance(item, dict) and _text(item.get("action_id"))
    }
    existing["authorized_route_bindings"] = [
        {
            "action_id": action_id,
            "route_id": route_id or None,
            "planned_proxy": planned_proxy or None,
        }
        for action_id, route_id, planned_proxy in sorted(bindings)
    ]
    origins = {
        _text(value)
        for value in (
            *(existing.get("origin_cruxes") or []),
            *(incoming.get("origin_cruxes") or []),
            existing.get("origin_crux"),
            incoming.get("origin_crux"),
        )
        if _text(value)
    }
    existing["origin_cruxes"] = sorted(origins)
    existing["origin_crux"] = sorted(origins)[0] if origins else None
    existing_bindings = list(existing.get("direction_bindings") or [])
    if not existing_bindings:
        existing_bindings = [{
            "direction": existing.get("direction", "AMBIGUOUS"),
            "evidence_ids": sorted(
                item.get("evidence_id")
                for item in existing.get("evidence", [])
                if isinstance(item, dict) and item.get("evidence_id")
            ),
            "source_agent": (
                sorted(existing.get("source_agents", []))[0]
                if existing.get("source_agents") else None
            ),
            "round": int(existing.get("first_seen_round") or 0),
            "trail_id": existing.get("trail_id"),
            "route_id": existing.get("route_id"),
            "origin_crux": existing.get("origin_crux"),
            "authorized_action_id": existing.get(
                "authorized_action_id"
            ),
        }]
    incoming_bindings = list(incoming.get("direction_bindings") or [])
    binding_map = {}
    for binding in existing_bindings + incoming_bindings:
        if not isinstance(binding, dict):
            continue
        normalized_binding = {
            "direction": _text(
                binding.get("direction")
            ).upper() or "AMBIGUOUS",
            "evidence_ids": sorted({
                _text(value)
                for value in binding.get("evidence_ids", [])
                if _text(value)
            }),
            "source_agent": _text(binding.get("source_agent")) or None,
            "round": int(binding.get("round") or 0),
            "trail_id": _text(binding.get("trail_id")) or None,
            "route_id": _text(binding.get("route_id")) or None,
            "origin_crux": _text(binding.get("origin_crux")) or None,
            "authorized_action_id": (
                _text(binding.get("authorized_action_id")) or None
            ),
        }
        key = json.dumps(
            normalized_binding,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        binding_map[key] = normalized_binding
    existing["direction_bindings"] = [
        binding_map[key] for key in sorted(binding_map)
    ]
    if incoming.get("direction") != existing.get("direction"):
        existing["direction_variants"] = sorted({
            value
            for value in (
                existing.get("direction"),
                incoming.get("direction"),
                *(existing.get("direction_variants") or []),
            )
            if value
        })
        existing["direction"] = "AMBIGUOUS"
        existing["direction_contested"] = True
    for field in (
        "route_id",
        "planned_proxy",
        "planned_direction",
        "alternative_explanation",
        "checkpoint",
        "publisher_class",
        "next_source_class",
        "bounded_query",
        "stop_condition",
    ):
        incoming_value = incoming.get(field)
        if incoming_value and not existing.get(field):
            existing[field] = incoming_value
        elif incoming_value and incoming_value != existing.get(field):
            variants = existing.setdefault("field_variants", {}).setdefault(
                field, []
            )
            for value in (existing.get(field), incoming_value):
                if value and value not in variants:
                    variants.append(value)
            variants.sort()
            if field in {
                "publisher_class",
                "next_source_class",
                "bounded_query",
                "stop_condition",
            }:
                existing[f"{field}_contested"] = True
    current_evidence = {
        item.get("evidence_id"): item
        for item in existing.get("evidence", [])
        if isinstance(item, dict) and item.get("evidence_id")
    }
    for citation in incoming.get("evidence", []):
        evidence_id = citation.get("evidence_id")
        if evidence_id in current_evidence:
            audit["duplicate_evidence"] += 1
            continue
        current_evidence[evidence_id] = deepcopy(citation)
        audit["merged_proxy_evidence"] += 1
    existing["evidence"] = [
        current_evidence[key] for key in sorted(current_evidence)
    ]


def _merge_hypothesis(existing, incoming, audit):
    audit["merged_hypotheses"] += 1
    existing["last_seen_round"] = max(
        int(existing.get("last_seen_round") or 0),
        int(incoming.get("last_seen_round") or 0),
    )
    existing["source_agents"] = sorted(set(
        existing.get("source_agents", []) + incoming.get("source_agents", [])
    ))
    existing["spark_ids"] = sorted(set(
        existing.get("spark_ids", []) + incoming.get("spark_ids", [])
    ))
    if not existing.get("spark_id") and incoming.get("spark_id"):
        existing["spark_id"] = incoming["spark_id"]
    for field in _TEXT_FIELDS:
        incoming_value = incoming.get(field)
        if field in {
            "strongest_alternative_explanation",
            "falsifier",
        }:
            _merge_contested_field(existing, field, incoming_value)
        elif incoming_value and not existing.get(field):
            existing[field] = incoming_value
        elif incoming_value and incoming_value != existing.get(field):
            _field_variant(existing, field, incoming_value)
    incoming_chain = incoming.get("causal_chain", [])
    _merge_contested_field(existing, "causal_chain", incoming_chain)

    incoming_scenarios = incoming.get("scenario_paths") or {}
    _merge_contested_field(existing, "scenario_paths", incoming_scenarios)
    incoming_asymmetry = incoming.get("asymmetry_case") or {}
    existing_asymmetry = existing.get("asymmetry_case") or {}
    if _asymmetry_case_is_substantive(incoming_asymmetry):
        if not _asymmetry_case_is_substantive(existing_asymmetry):
            existing["asymmetry_case"] = deepcopy(incoming_asymmetry)
        elif incoming_asymmetry != existing_asymmetry:
            _merge_contested_field(
                existing, "asymmetry_case", incoming_asymmetry
            )

    incoming_plan = incoming.get("proxy_plan") or []
    if incoming_plan and not existing.get("proxy_plan"):
        existing["proxy_plan"] = deepcopy(incoming_plan)
    elif incoming_plan and incoming_plan != existing.get("proxy_plan"):
        _field_variant(existing, "proxy_plan", incoming_plan)

    existing_context = existing.setdefault("context", {})
    incoming_context = incoming.get("context") or {}
    for field in (
        "subject",
        "origin_crux",
        "landscape_path_id",
        "archetype",
    ):
        value = incoming_context.get(field)
        current = existing_context.get(field)
        if value and not current:
            existing_context[field] = value
        elif value and value != current:
            variants = existing.setdefault("field_variants", {}).setdefault(
                f"context.{field}", []
            )
            for item in (current, value):
                if item and item not in variants:
                    variants.append(item)
            variants.sort()

    for singular, plural in (
        ("origin_crux", "origin_cruxes"),
        ("landscape_path_id", "landscape_path_ids"),
    ):
        values = {
            _text(value)
            for value in (
                *(existing_context.get(plural) or []),
                *(incoming_context.get(plural) or []),
                existing_context.get(singular),
                incoming_context.get(singular),
            )
            if _text(value)
        }
        existing_context[plural] = sorted(values)
        if values:
            existing_context[singular] = sorted(values)[0]

    current_payoff = existing.get("payoff") or {}
    incoming_payoff = incoming.get("payoff") or {}
    current_threshold = _payoff_break_even(current_payoff)
    incoming_threshold = _payoff_break_even(incoming_payoff)
    if existing.get("payoff_contested") and incoming_threshold["status"] == "KNOWN":
        variants = existing.setdefault("field_variants", {}).setdefault(
            "payoff", []
        )
        for item in (current_payoff, incoming_payoff):
            if item and item not in variants:
                variants.append(deepcopy(item))
        variants.sort(key=_payoff_key)
        existing["payoff"] = deepcopy(variants[0])
    elif (
        current_threshold["status"] == "UNKNOWN"
        and incoming_threshold["status"] == "KNOWN"
    ):
        existing["payoff"] = deepcopy(incoming_payoff)
    elif (
        incoming_threshold["status"] == "KNOWN"
        and _payoff_key(incoming_payoff) != _payoff_key(current_payoff)
    ):
        variants = existing.setdefault("field_variants", {}).setdefault(
            "payoff", []
        )
        for item in (current_payoff, incoming_payoff):
            if item and item not in variants:
                variants.append(deepcopy(item))
        variants.sort(key=_payoff_key)
        existing["payoff"] = deepcopy(variants[0])
        existing["payoff_contested"] = True

    current_observation_evidence = {
        item.get("evidence_id"): item
        for item in existing.get("observation_evidence", [])
        if isinstance(item, dict) and item.get("evidence_id")
    }
    for citation in incoming.get("observation_evidence", []):
        evidence_id = citation.get("evidence_id")
        if evidence_id in current_observation_evidence:
            audit["duplicate_evidence"] += 1
            continue
        current_observation_evidence[evidence_id] = deepcopy(citation)
        audit["merged_proxy_evidence"] += 1
    existing["observation_evidence"] = [
        current_observation_evidence[key]
        for key in sorted(current_observation_evidence)
    ]

    for proxy in incoming.get("proxy_trails", []):
        _merge_or_add_proxy(existing, proxy, audit)
    return _refresh(existing)


def _insert_hypothesis(ledger, incoming, audit):
    hypotheses = ledger.setdefault("hypotheses", [])
    existing = next(
        (
            item for item in hypotheses
            if item.get("hypothesis_id") == incoming.get("hypothesis_id")
        ),
        None,
    )
    if existing is None:
        hypotheses.append(deepcopy(incoming))
        audit["accepted_new_hypotheses"] += 1
        audit["accepted_new_proxy_trails"] += len(
            incoming.get("proxy_trails", [])
        )
    else:
        _merge_hypothesis(existing, incoming, audit)
    hypotheses.sort(key=lambda item: item.get("hypothesis_id", ""))


def _validate_proxy_shape(raw, prefix):
    if not isinstance(raw, dict):
        return [f"{prefix}_must_be_object"]
    issues = []
    if not (
        _text(raw.get("proxy"))
        or _text(raw.get("observation"))
        or _text(raw.get("signal"))
    ):
        issues.append(f"{prefix}_missing_proxy")
    if not (
        _text(raw.get("causal_link"))
        or _text(raw.get("why_diagnostic"))
        or _text(raw.get("inference"))
        or _text(raw.get("why_it_matters"))
    ):
        issues.append(f"{prefix}_missing_causal_link")
    direction = _text(raw.get("direction")).upper()
    if direction and direction not in PROXY_DIRECTIONS:
        issues.append(f"{prefix}_invalid_direction")
    evidence = raw.get("evidence")
    if evidence is not None and not isinstance(evidence, (dict, list)):
        issues.append(f"{prefix}_evidence_must_be_object_or_list")
    return issues


def _validate_proxy_plan_shape(raw, prefix):
    if not isinstance(raw, dict):
        return [f"{prefix}_must_be_object"]
    issues = []
    if not _text(raw.get("proxy")):
        issues.append(f"{prefix}_missing_proxy")
    if not (
        _text(raw.get("why_diagnostic"))
        or _text(raw.get("causal_link"))
    ):
        issues.append(f"{prefix}_missing_why_diagnostic")
    if not _text(raw.get("publisher_class")):
        issues.append(f"{prefix}_missing_publisher_class")
    if not _text(raw.get("bounded_query")):
        issues.append(f"{prefix}_missing_bounded_query")
    return issues


def _validate_asymmetry_case_shape(raw, prefix):
    if raw is None:
        return []
    if not isinstance(raw, dict):
        return [f"{prefix}_must_be_object"]
    issues = []
    for field, allowed in (
        ("upside_shape", QUALITATIVE_UPSIDE),
        ("convexity", QUALITATIVE_CONVEXITY),
        ("downside_shape", QUALITATIVE_DOWNSIDE),
        ("time_to_signal", QUALITATIVE_TIME_TO_SIGNAL),
    ):
        value = _text(raw.get(field)).upper()
        if value not in allowed:
            issues.append(f"{prefix}_invalid_{field}")
    if not _text(raw.get("basis")):
        issues.append(f"{prefix}_missing_basis")
    return issues


def validate_frame(frame):
    """Validate intent and the deterministic 5–7 path Framer garden contract."""
    if not isinstance(frame, dict):
        return ["frame_must_be_object"]
    issues = []
    explicit = _text(frame.get("research_intent")).upper()
    if explicit and explicit not in RESEARCH_INTENTS:
        issues.append("invalid_research_intent")
    intent = infer_research_intent(frame)
    hypotheses, garden_issue = _garden(frame)
    if garden_issue:
        issues.append(garden_issue)
    garden_source = _garden_source(frame)
    garden_declared = garden_source != "NONE"
    legacy_projection = garden_source == "LEGACY_LANDSCAPE_MAP"
    if intent in {OPPORTUNITY_DISCOVERY, HYBRID} and not hypotheses:
        issues.append("opportunity_intent_requires_hypothesis_garden")
    if garden_declared and not (5 <= len(hypotheses) <= 7):
        issues.append("hypothesis_garden_requires_5_to_7_hypotheses")

    cruxes = frame.get("candidate_cruxes")
    if cruxes is None and isinstance(frame.get("cruxes"), dict):
        cruxes = list(frame["cruxes"].values())
    crux_ids = {
        _text(crux.get("crux_id") or crux.get("id"))
        for crux in cruxes or []
        if isinstance(crux, dict)
    }
    crux_ids.discard("")

    seen = set()
    seen_declared_ids = set()
    seen_path_ids = set()
    archetypes_seen = set()
    for index, raw in enumerate(hypotheses):
        prefix = f"wild_hypothesis_{index + 1}"
        if not isinstance(raw, dict):
            issues.append(f"{prefix}_must_be_object")
            continue
        statement = _statement(raw)
        if not statement:
            issues.append(f"{prefix}_missing_hypothesis")
        elif _norm(statement) in seen:
            issues.append(f"{prefix}_duplicate_hypothesis")
        seen.add(_norm(statement))

        declared_id = _text(raw.get("hypothesis_id"))
        if not legacy_projection:
            if not declared_id:
                issues.append(f"{prefix}_missing_hypothesis_id")
            elif declared_id in seen_declared_ids:
                issues.append(f"{prefix}_duplicate_hypothesis_id")
            seen_declared_ids.add(declared_id)

        path_id = _text(raw.get("path_id"))
        if not path_id:
            issues.append(f"{prefix}_missing_path_id")
        elif path_id in seen_path_ids:
            issues.append(f"{prefix}_duplicate_path_id")
        seen_path_ids.add(path_id)

        linked_crux_id = _text(raw.get("linked_crux_id"))
        if not linked_crux_id:
            issues.append(f"{prefix}_missing_linked_crux_id")
        elif crux_ids and linked_crux_id not in crux_ids:
            issues.append(f"{prefix}_unknown_linked_crux_id")

        status = _text(raw.get("hypothesis_status")).upper()
        if legacy_projection:
            if status not in {"HYPOTHESIS", HYPOTHESIS_ONLY}:
                issues.append(f"{prefix}_status_must_be_hypothesis")
        elif status != HYPOTHESIS_ONLY:
            issues.append(f"{prefix}_status_must_be_hypothesis_only")

        archetype = _text(raw.get("archetype")).upper()
        if archetype not in ARCHETYPES:
            issues.append(f"{prefix}_invalid_archetype")
        else:
            archetypes_seen.add(archetype)

        if not legacy_projection and not _text(raw.get("surprise_if_true")):
            issues.append(f"{prefix}_missing_surprise_if_true")
        if (
            not legacy_projection
            and not _text(raw.get("strongest_alternative_explanation"))
        ):
            issues.append(f"{prefix}_missing_strongest_alternative_explanation")
        if not _text(raw.get("economic_capture_test")):
            issues.append(f"{prefix}_missing_economic_capture_test")
        if not _text(raw.get("pricing_question")):
            issues.append(f"{prefix}_missing_pricing_question")
        if (
            not legacy_projection
            and not _text(raw.get("cheap_discriminating_test"))
        ):
            issues.append(f"{prefix}_missing_cheap_discriminating_test")
        if not _text(raw.get("falsifier")):
            issues.append(f"{prefix}_missing_falsifier")
        issues.extend(_validate_asymmetry_case_shape(
            raw.get("asymmetry_case"),
            f"{prefix}_asymmetry_case",
        ))
        expiry_date = _text(raw.get("expiry_date"))
        if not legacy_projection:
            if not expiry_date:
                issues.append(f"{prefix}_missing_expiry_date")
            else:
                try:
                    expiry = date.fromisoformat(expiry_date)
                except ValueError:
                    issues.append(f"{prefix}_expiry_date_requires_iso_date")
                else:
                    try:
                        frame_as_of = date.fromisoformat(
                            _text(frame.get("as_of_date"))
                        )
                    except ValueError:
                        frame_as_of = None
                    if frame_as_of is not None and expiry <= frame_as_of:
                        issues.append(f"{prefix}_expiry_date_must_follow_as_of")

        if not legacy_projection and _raw_proxy_list(raw):
            issues.append(f"{prefix}_framer_proxy_trails_forbidden")

        scenarios = raw.get("scenario_paths")
        if not legacy_projection:
            if not isinstance(scenarios, dict):
                issues.append(f"{prefix}_scenario_paths_must_be_object")
            else:
                for scenario in ("bull", "base", "bear"):
                    if not _text(scenarios.get(scenario)):
                        issues.append(
                            f"{prefix}_scenario_paths_missing_{scenario}"
                        )

        for field in _forbidden_fields(raw):
            issues.append(f"{prefix}_forbidden_field:{field}")
        chain_value = raw.get("causal_chain")
        if chain_value is None:
            chain_value = raw.get("value_transfer_chain")
        if not isinstance(chain_value, list):
            issues.append(f"{prefix}_value_transfer_chain_must_be_list")
        elif not (3 <= len(chain_value) <= 6):
            issues.append(
                f"{prefix}_value_transfer_chain_requires_3_to_6_nodes"
            )
        elif any(not _text(item) for item in chain_value):
            issues.append(f"{prefix}_value_transfer_chain_has_empty_node")

        if not legacy_projection:
            proxy_plan = raw.get("proxy_plan")
            if not isinstance(proxy_plan, list):
                issues.append(f"{prefix}_proxy_plan_must_be_list")
                proxy_plan = []
            elif not (1 <= len(proxy_plan) <= 3):
                issues.append(f"{prefix}_proxy_plan_requires_1_to_3_routes")
            for proxy_index, proxy_item in enumerate(proxy_plan):
                issues.extend(_validate_proxy_plan_shape(
                    proxy_item, f"{prefix}_proxy_plan_{proxy_index + 1}"
                ))
                expected_origin = _text(
                    raw.get("origin_crux")
                    or raw.get("linked_crux_id")
                )
                route_origin = _text(
                    proxy_item.get("origin_crux")
                    if isinstance(proxy_item, dict)
                    else ""
                )
                if (
                    route_origin
                    and expected_origin
                    and route_origin != expected_origin
                ):
                    issues.append(
                        f"{prefix}_proxy_plan_{proxy_index + 1}"
                        "_origin_crux_mismatch"
                    )

        search_queries = raw.get("search_queries")
        if not isinstance(search_queries, list):
            issues.append(f"{prefix}_search_queries_must_be_list")
        else:
            normalized_queries = [
                _norm(query) for query in search_queries if _text(query)
            ]
            if (
                len(search_queries) != 2
                or len(normalized_queries) != 2
                or len(set(normalized_queries)) != 2
            ):
                issues.append(
                    f"{prefix}_search_queries_require_exactly_2_distinct"
                )

    if hypotheses:
        missing_archetypes = sorted(ARCHETYPES - archetypes_seen)
        if missing_archetypes:
            issues.append(
                "hypothesis_garden_missing_archetypes:"
                + ",".join(missing_archetypes)
            )
    return sorted(set(issues))


def initialize(frame):
    """Normalize the initial hypothesis garden into an independent ledger."""
    frame = frame if isinstance(frame, dict) else {}
    hypotheses, _ = _garden(frame)
    intent = infer_research_intent(frame)
    if not hypotheses:
        return None
    audit = _new_audit(round_num=0)
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "research_intent": intent if intent in RESEARCH_INTENTS else THESIS_CHALLENGE,
        "garden_source": _garden_source(frame),
        "as_of_date": _text(frame.get("as_of_date")) or None,
        "hypotheses": [],
        "round_audits": [],
        "capability_boundary": deepcopy(CAPABILITY_BOUNDARY),
    }
    for raw in hypotheses:
        item = _normalize_spark(
            raw,
            "frame",
            0,
            audit,
            allow_embedded_proxy_trails=False,
            as_of_date=ledger.get("as_of_date"),
        )
        if item:
            _insert_hypothesis(ledger, item, audit)
    ledger["initialization_audit"] = deepcopy(audit)
    return ledger


def _ledger(state):
    if not isinstance(state, dict):
        return None
    if state.get("schema_version") == SCHEMA_VERSION:
        return state
    value = state.get("hypothesis_ledger")
    return value if isinstance(value, dict) else None


def _hypothesis_lookup(ledger):
    canonical = {}
    aliases = {}
    hypotheses = sorted(
        [
            item for item in ledger.get("hypotheses", [])
            if isinstance(item, dict) and item.get("hypothesis_id")
        ],
        key=lambda item: item.get("hypothesis_id", ""),
    )
    for item in hypotheses:
        hypothesis_id = _text(item.get("hypothesis_id"))
        canonical[hypothesis_id] = item
        item_aliases = [
            item.get("spark_id"),
            *(item.get("spark_ids") or []),
        ]
        for alias in item_aliases:
            alias = _text(alias)
            if alias:
                aliases.setdefault(alias, set()).add(hypothesis_id)
    return {"canonical": canonical, "aliases": aliases}


def _resolve_hypothesis(proxy, lookup):
    canonical = lookup.get("canonical", {})
    aliases = lookup.get("aliases", {})
    candidate_sets = []
    for field in ("hypothesis_id", "spark_id"):
        submitted_id = _text(proxy.get(field))
        if not submitted_id:
            continue
        matches = set()
        if submitted_id in canonical:
            matches.add(submitted_id)
        matches.update(aliases.get(submitted_id, set()))
        if not matches:
            return None, "unknown_hypothesis"
        candidate_sets.append(matches)
    statement = _text(proxy.get("hypothesis")) or _text(proxy.get("statement"))
    if statement:
        statement_id = _hypothesis_id(statement)
        if statement_id not in canonical:
            return None, "unknown_hypothesis"
        candidate_sets.append({statement_id})
    if not candidate_sets:
        return None, "unknown_hypothesis"
    candidates = set.intersection(*candidate_sets)
    if not candidates:
        return None, "hypothesis_reference_mismatch"
    if len(candidates) != 1:
        return None, "ambiguous_hypothesis_alias"
    hypothesis_id = next(iter(candidates))
    return canonical[hypothesis_id], None


def _ingest_payload(
    ledger,
    payload,
    role,
    round_num,
    audit,
    valid_crux_ids=None,
    scope_enforced=False,
    as_of_date=None,
):
    payload = payload if isinstance(payload, dict) else {}
    valid_crux_ids = set(valid_crux_ids or [])
    sparks = payload.get("hypothesis_sparks", [])
    if sparks is None:
        sparks = []
    if not isinstance(sparks, list):
        _reason(audit, f"{role}_hypothesis_sparks_must_be_list")
        sparks = []
    if len(sparks) > MAX_SPARKS_PER_ROLE_ROUND:
        overflow = len(sparks) - MAX_SPARKS_PER_ROLE_ROUND
        audit["submitted_sparks"] += overflow
        _reason(audit, f"{role}_hypothesis_sparks_round_limit_exceeded", overflow)
    for raw in sparks[:MAX_SPARKS_PER_ROLE_ROUND]:
        if isinstance(raw, dict):
            raw_origin = _text(
                raw.get("origin_crux") or raw.get("linked_crux_id")
            )
            if not raw_origin and len(valid_crux_ids) == 1:
                raw = {**raw, "origin_crux": next(iter(valid_crux_ids))}
                raw_origin = _text(raw.get("origin_crux"))
            if scope_enforced and not raw_origin:
                audit["submitted_sparks"] += 1
                _reason(audit, f"{role}_hypothesis_spark_missing_origin_crux")
                continue
            if (
                raw_origin
                and scope_enforced
                and raw_origin not in valid_crux_ids
            ):
                audit["submitted_sparks"] += 1
                _reason(audit, f"{role}_hypothesis_spark_unknown_origin_crux")
                continue
        item = _normalize_spark(
            raw,
            role,
            round_num,
            audit,
            allow_embedded_proxy_trails=False,
            as_of_date=as_of_date,
        )
        if item:
            _insert_hypothesis(ledger, item, audit)

    lookup = _hypothesis_lookup(ledger)
    proxy_trails = payload.get("proxy_trails", [])
    if proxy_trails is None:
        proxy_trails = []
    if not isinstance(proxy_trails, list):
        _reason(audit, f"{role}_proxy_trails_must_be_list")
        return
    if len(proxy_trails) > MAX_PROXY_TRAILS_PER_ROLE_ROUND:
        overflow = len(proxy_trails) - MAX_PROXY_TRAILS_PER_ROLE_ROUND
        audit["submitted_proxy_trails"] += overflow
        _reason(audit, f"{role}_proxy_trails_round_limit_exceeded", overflow)
    for raw in proxy_trails[:MAX_PROXY_TRAILS_PER_ROLE_ROUND]:
        if not isinstance(raw, dict):
            audit["submitted_proxy_trails"] += 1
            _reason(audit, "proxy_trail_not_object")
            continue
        hypothesis, resolution_issue = _resolve_hypothesis(raw, lookup)
        if hypothesis is None:
            audit["submitted_proxy_trails"] += 1
            _reason(
                audit,
                f"{role}_proxy_trail_{resolution_issue}",
            )
            continue
        allowed_cruxes = {
            _text(value)
            for value in (
                *(hypothesis.get("context", {}).get("origin_cruxes") or []),
                hypothesis.get("context", {}).get("origin_crux"),
            )
            if _text(value)
        }
        supplied_origin = _text(raw.get("origin_crux"))
        if not supplied_origin and len(allowed_cruxes) == 1:
            raw = {**raw, "origin_crux": next(iter(allowed_cruxes))}
            supplied_origin = _text(raw.get("origin_crux"))
        if (
            not supplied_origin
            and not allowed_cruxes
            and len(valid_crux_ids) == 1
        ):
            raw = {**raw, "origin_crux": next(iter(valid_crux_ids))}
            supplied_origin = _text(raw.get("origin_crux"))
        if allowed_cruxes and not supplied_origin:
            audit["submitted_proxy_trails"] += 1
            _reason(audit, f"{role}_proxy_trail_missing_origin_crux")
            continue
        if supplied_origin and allowed_cruxes and supplied_origin not in allowed_cruxes:
            audit["submitted_proxy_trails"] += 1
            _reason(audit, f"{role}_proxy_trail_origin_crux_mismatch")
            continue
        if scope_enforced and not supplied_origin:
            audit["submitted_proxy_trails"] += 1
            _reason(audit, f"{role}_proxy_trail_missing_origin_crux")
            continue
        if (
            supplied_origin
            and scope_enforced
            and supplied_origin not in valid_crux_ids
        ):
            audit["submitted_proxy_trails"] += 1
            _reason(audit, f"{role}_proxy_trail_unknown_origin_crux")
            continue
        item = _normalize_proxy(
            raw,
            hypothesis["hypothesis_id"],
            role,
            round_num,
            audit,
            as_of_date=as_of_date,
        )
        if item:
            _merge_or_add_proxy(hypothesis, item, audit)
            _refresh(hypothesis)


def ingest_round(
    state,
    round_num,
    detective=None,
    inquisitor=None,
    allowed_crux_ids=None,
):
    """Append hypothesis sparks and ProxyTrails from one bounded research round."""
    if (
        isinstance(round_num, bool)
        or not isinstance(round_num, int)
        or round_num < 1
    ):
        raise ValueError("round_num must be a positive integer")
    audit = _new_audit(round_num)
    ledger = _ledger(state)
    if ledger is None:
        audit["enabled"] = False
        audit["reason"] = "hypothesis_track_not_initialized"
        audit.update(summary(state))
        return audit
    audit["enabled"] = True
    as_of_date = (
        _text(ledger.get("as_of_date"))
        or _text(state.get("frame_contract", {}).get("as_of_date"))
    )
    if as_of_date and not ledger.get("as_of_date"):
        ledger["as_of_date"] = as_of_date
    if any(
        int(item.get("round") or 0) == round_num
        for item in ledger.get("round_audits", [])
        if isinstance(item, dict)
    ):
        _reason(audit, "duplicate_round_ingest_rejected")
        audit["reason"] = "round_already_ingested"
        audit.update(summary(state))
        return audit
    state_crux_ids = set(
        state.get("cruxes", {})
        if isinstance(state.get("cruxes"), dict)
        else []
    )
    valid_crux_ids = (
        state_crux_ids & {
            _text(value) for value in allowed_crux_ids if _text(value)
        }
        if allowed_crux_ids is not None
        else state_crux_ids
    )
    scope_enforced = allowed_crux_ids is not None
    audit["allowed_crux_ids"] = sorted(valid_crux_ids)
    audit["crux_scope_enforced"] = scope_enforced
    for role, payload in (("detective", detective), ("inquisitor", inquisitor)):
        _ingest_payload(
            ledger,
            payload,
            role,
            round_num,
            audit,
            valid_crux_ids=valid_crux_ids,
            scope_enforced=scope_enforced,
            as_of_date=as_of_date,
        )
    ledger.setdefault("round_audits", []).append(deepcopy(audit))
    ledger["round_audits"].sort(key=lambda item: int(item.get("round") or 0))
    audit.update(summary(state))
    return audit


def _authorization_receipt_is_valid(action_id, receipt):
    return bool(
        action_id
        and isinstance(receipt, dict)
        and receipt.get("action_id") == action_id
        and receipt.get("explicit_user_authorization") is True
        and receipt.get("authorization_scope")
        == "ONE_BOUNDED_EXPLORATION_ACTION"
        and _text(receipt.get("authorization_note"))
    )


def _stored_authorized_action(state, action_record):
    """Resolve an authorized, uncompleted action from the host-owned ledger."""
    if not isinstance(action_record, dict):
        raise ValueError("authorized_action_record_required")
    action_id = _text(action_record.get("action_id"))
    if not action_id:
        raise ValueError("authorized_action_id_required")
    stored = next(
        (
            item
            for item in state.get("exploration_actions", [])
            if isinstance(item, dict) and item.get("action_id") == action_id
        ),
        None,
    )
    if stored is None:
        raise ValueError("authorized_action_not_in_host_ledger")
    if stored.get("status") != "AUTHORIZED_NOT_EXECUTED":
        raise ValueError("authorized_action_not_open_for_result")
    if not _authorization_receipt_is_valid(
        action_id, stored.get("authorization_receipt")
    ):
        raise ValueError("authorized_action_receipt_invalid")
    if stored.get("proposal") != action_record.get("proposal"):
        raise ValueError("authorized_action_proposal_mismatch")
    return stored


def _action_route_key(proposal):
    proposal = proposal if isinstance(proposal, dict) else {}
    route_spec = proposal.get("route_spec")
    if isinstance(route_spec, dict) and _text(route_spec.get("route_id")):
        return _text(route_spec.get("route_id"))
    return "|".join((
        _text(proposal.get("hypothesis_id")),
        _norm(proposal.get("source_class")),
        _norm(proposal.get("bounded_query")),
    ))


def exploration_route_id(
    hypothesis_id, source_class, bounded_query, proxy, causal_link
):
    """Return the immutable identity of one planned diagnostic route."""
    return _hash_id(
        "XR",
        "|".join((
            _text(hypothesis_id),
            _norm(source_class),
            _norm(bounded_query),
            _norm(proxy),
            _norm(causal_link),
        )),
    )


def _upsert_authorized_action_audit(ledger, audit):
    audits = ledger.setdefault("authorized_action_audits", [])
    action_id = audit.get("action_id")
    existing = next(
        (
            item for item in audits
            if isinstance(item, dict) and item.get("action_id") == action_id
        ),
        None,
    )
    if existing is None:
        audits.append(deepcopy(audit))
    else:
        existing.clear()
        existing.update(deepcopy(audit))
    audits.sort(key=lambda item: (
        int(item.get("sequence") or 0),
        _text(item.get("action_id")),
    ))


def ingest_authorized_action_result(state, action_record, proxy_trail):
    """Apply one explicitly authorized ProxyTrail without touching formal state.

    Query/read budgets and exact document binding belong to the orchestrator.
    This lower-level write still fails closed unless the action exists in the
    host ledger with an exact, explicit, one-action authorization receipt.
    """
    ledger = _ledger(state)
    if ledger is None:
        raise ValueError("hypothesis_track_not_initialized")
    stored = _stored_authorized_action(state, action_record)
    if stored.get("engine_result_ingested"):
        raise ValueError("authorized_action_result_already_ingested")
    action_id = _text(stored.get("action_id"))
    proposal = stored.get("proposal")
    proposal = proposal if isinstance(proposal, dict) else {}
    hypothesis_id = _text(proposal.get("hypothesis_id"))
    hypothesis = next(
        (
            item
            for item in ledger.get("hypotheses", [])
            if isinstance(item, dict)
            and item.get("hypothesis_id") == hypothesis_id
        ),
        None,
    )
    if not hypothesis:
        raise ValueError("authorized_action_hypothesis_not_found")
    if not isinstance(proxy_trail, dict):
        raise ValueError("authorized_action_proxy_trail_required")
    raw = {
        **proxy_trail,
        "hypothesis_id": hypothesis_id,
    }
    allowed_origins = {
        _text(value)
        for value in (
            *(hypothesis.get("context", {}).get("origin_cruxes") or []),
            hypothesis.get("context", {}).get("origin_crux"),
        )
        if _text(value)
    }
    origin = _text(raw.get("origin_crux"))
    if not origin and len(allowed_origins) == 1:
        raw["origin_crux"] = next(iter(allowed_origins))
        origin = _text(raw.get("origin_crux"))
    if allowed_origins and origin not in allowed_origins:
        raise ValueError("authorized_action_proxy_origin_crux_mismatch")
    if not origin:
        raise ValueError("authorized_action_proxy_origin_crux_required")
    audit = _new_audit()
    proxy = _normalize_proxy(
        raw,
        hypothesis_id,
        "authorized_exploration",
        len(state.get("rounds", [])),
        audit,
        as_of_date=proposal.get("as_of_date"),
    )
    if not proxy:
        raise ValueError(
            "authorized_action_proxy_invalid:"
            + ",".join(sorted(audit.get("rejected_reasons", {})))
        )
    if (
        proposal.get("action_code") == "SEEK_DISCONFIRMING_PROXY"
        and proxy.get("direction") != "CONTRADICTS"
    ):
        raise ValueError("authorized_disconfirming_action_requires_contradiction")
    proxy["authorized_action_id"] = action_id
    proxy["authorized_action_ids"] = [action_id]
    for binding in proxy.get("direction_bindings", []):
        if isinstance(binding, dict):
            binding["authorized_action_id"] = action_id
    proxy["authorized_route_bindings"] = [{
        "action_id": action_id,
        "route_id": proxy.get("route_id"),
        "planned_proxy": proxy.get("planned_proxy"),
    }]
    _merge_or_add_proxy(hypothesis, proxy, audit)
    _refresh(hypothesis)
    receipt = {
        "action_id": action_id,
        "hypothesis_id": hypothesis_id,
        "execution_status": "OBSERVATION_RECORDED",
        "proxy_id": proxy.get("proxy_id"),
        "route_id": proxy.get("route_id"),
        "planned_proxy": proxy.get("planned_proxy"),
        "observation": proxy.get("proxy"),
        "accepted_new_proxy_trails": audit[
            "accepted_new_proxy_trails"
        ],
        "duplicate_proxy_trails": audit["duplicate_proxy_trails"],
        "accepted_evidence": audit["accepted_evidence"],
        "state_after": hypothesis["state"],
        "authority": "EXPLORATION_ONLY_NO_PROMOTION",
    }
    stored["engine_result_ingested"] = True
    _upsert_authorized_action_audit(
        ledger,
        {
            **receipt,
            "sequence": int(stored.get("sequence") or 0),
            "status": "INGESTED_PENDING_HOST_RECEIPT",
            "source_class": proposal.get("source_class"),
            "bounded_query": proposal.get("bounded_query"),
            "authorization_receipt": deepcopy(
                stored.get("authorization_receipt")
            ),
        },
    )
    return receipt


def record_exploration_design(state, design):
    """Apply one caller-reviewed, non-executing hypothesis-ledger design.

    This endpoint only changes an alternative explanation or ProxyTrail plan.
    It performs no search and has no seed, candidate, trade, or sizing authority.
    """
    ledger = _ledger(state)
    if ledger is None:
        raise ValueError("hypothesis_track_not_initialized")
    if not isinstance(design, dict):
        raise ValueError("exploration_design_must_be_object")
    if (
        design.get("design_reviewed") is not True
        or design.get("design_scope") != "ONE_EXPLORATION_LEDGER_DESIGN"
        or not _text(design.get("design_note"))
    ):
        raise ValueError("exploration_design_review_receipt_required")
    current = exploration_action(state, include_host_state=False)
    if design.get("design_target_id") != current.get("design_target_id"):
        raise ValueError("exploration_design_target_mismatch")
    expected_revision = design.get("expected_state_revision")
    current_revision = state.get("runtime", {}).get("state_revision", 0)
    if (
        isinstance(expected_revision, bool)
        or not isinstance(expected_revision, int)
        or expected_revision != current_revision
    ):
        raise ValueError("exploration_design_state_revision_mismatch")
    hypothesis_id = _text(design.get("hypothesis_id"))
    action_code = _text(design.get("action_code")).upper()
    if (
        hypothesis_id != current.get("hypothesis_id")
        or action_code != current.get("action_code")
    ):
        raise ValueError("exploration_design_current_action_mismatch")
    hypothesis = next(
        (
            item
            for item in ledger.get("hypotheses", [])
            if isinstance(item, dict)
            and item.get("hypothesis_id") == hypothesis_id
        ),
        None,
    )
    if hypothesis is None:
        raise ValueError("exploration_design_hypothesis_not_found")
    state_before = hypothesis.get("state")
    if action_code == "ARTICULATE_STRONGEST_ALTERNATIVE":
        alternative = _text(
            design.get("strongest_alternative_explanation")
        )
        discriminator = _text(design.get("cheap_discriminating_test"))
        if not alternative:
            raise ValueError("exploration_design_alternative_required")
        if not discriminator:
            raise ValueError("exploration_design_discriminator_required")
        contested = bool(hypothesis.get(
            "strongest_alternative_explanation_contested"
        ))
        resolution = None
        if contested:
            variants = hypothesis.get("field_variants", {}).get(
                "strongest_alternative_explanation", []
            )
            if (
                design.get("resolve_contested") is not True
                or alternative not in variants
                or not _text(design.get("resolution_rationale"))
            ):
                raise ValueError(
                    "exploration_design_contested_resolution_required"
                )
            resolution = {
                "field": "strongest_alternative_explanation",
                "selected_value": alternative,
                "preserved_variants": deepcopy(variants),
                "rationale": _text(design.get("resolution_rationale")),
                "authority": "CALLER_REVIEWED_EXPLORATION_DESIGN",
            }
            hypothesis[
                "strongest_alternative_explanation_contested"
            ] = False
            hypothesis.setdefault("field_resolutions", []).append(
                deepcopy(resolution)
            )
        hypothesis["strongest_alternative_explanation"] = alternative
        hypothesis["cheap_discriminating_test"] = discriminator
        applied = {
            "strongest_alternative_explanation": alternative,
            "cheap_discriminating_test": discriminator,
            "contested_resolution": resolution,
        }
    else:
        raw_routes = design.get("proxy_plan")
        if not isinstance(raw_routes, list):
            raise ValueError("exploration_design_proxy_plan_required")
        required_count = 2 if action_code == "DESIGN_PROXY_TRAIL" else 1
        if len(raw_routes) != required_count:
            raise ValueError(
                f"exploration_design_requires_{required_count}_routes"
            )
        normalized = []
        allowed_origins = {
            _text(value)
            for value in (
                *(hypothesis.get("context", {}).get("origin_cruxes") or []),
                hypothesis.get("context", {}).get("origin_crux"),
            )
            if _text(value)
        }
        for index, raw in enumerate(raw_routes, 1):
            route = _normalize_proxy_plan(raw)
            if not route:
                raise ValueError(
                    f"exploration_design_route_{index}_invalid"
                )
            if not route.get("publisher_class"):
                raise ValueError(
                    f"exploration_design_route_{index}_publisher_class_required"
                )
            if not route.get("bounded_query"):
                raise ValueError(
                    f"exploration_design_route_{index}_bounded_query_required"
                )
            if not route.get("stop_condition"):
                raise ValueError(
                    f"exploration_design_route_{index}_stop_condition_required"
                )
            origin = _text(route.get("origin_crux"))
            if not origin and len(allowed_origins) == 1:
                origin = next(iter(allowed_origins))
                route["origin_crux"] = origin
            if not origin:
                raise ValueError(
                    f"exploration_design_route_{index}_origin_crux_required"
                )
            if allowed_origins and origin not in allowed_origins:
                raise ValueError(
                    f"exploration_design_route_{index}_origin_crux_mismatch"
                )
            normalized.append(route)
        directions = {item["direction"] for item in normalized}
        diagnostic_keys = {
            "|".join((
                _norm(item.get("proxy")),
                _norm(item.get("why_diagnostic")),
                _norm(item.get("publisher_class")),
                _norm(item.get("bounded_query")),
            ))
            for item in normalized
        }
        maturity_keys = {
            _proxy_maturity_key(item) for item in normalized
        }
        if len(diagnostic_keys) != len(normalized):
            raise ValueError(
                "exploration_design_requires_distinct_diagnostic_routes"
            )
        if len(maturity_keys) != len(normalized):
            raise ValueError(
                "exploration_design_requires_distinct_maturity_proxies"
            )
        existing_maturity_keys = {
            _proxy_maturity_key(item)
            for item in hypothesis.get("proxy_trails", [])
            if isinstance(item, dict)
        }
        if (
            action_code == "COLLECT_SECOND_PROXY_EVIDENCE"
            and maturity_keys & existing_maturity_keys
        ):
            raise ValueError(
                "exploration_design_second_proxy_must_be_distinct"
            )
        if (
            action_code == "DESIGN_PROXY_TRAIL"
            and directions != {"SUPPORTS", "CONTRADICTS"}
        ):
            raise ValueError(
                "exploration_design_requires_support_and_contradict_routes"
            )
        if (
            action_code == "SEEK_DISCONFIRMING_PROXY"
            and directions != {"CONTRADICTS"}
        ):
            raise ValueError(
                "exploration_design_disconfirming_route_required"
            )
        existing = [
            item
            for item in hypothesis.get("proxy_plan", [])
            if isinstance(item, dict)
        ]
        existing_keys = {
            "|".join((
                _norm(item.get("proxy")),
                _norm(item.get("why_diagnostic")),
                _norm(item.get("publisher_class")),
                _norm(item.get("bounded_query")),
            ))
            for item in existing
        }
        if diagnostic_keys <= existing_keys:
            raise ValueError("exploration_design_no_new_route")
        by_key = {
            "|".join((
                _norm(item.get("proxy")),
                _norm(item.get("why_diagnostic")),
                _norm(item.get("publisher_class")),
                _norm(item.get("bounded_query")),
            )): item
            for item in existing + normalized
        }
        hypothesis["proxy_plan"] = [
            deepcopy(by_key[key]) for key in sorted(by_key)
        ]
        applied = {"proxy_plan": deepcopy(normalized)}
    _refresh(hypothesis)
    payload = {
        "hypothesis_id": hypothesis_id,
        "action_code": action_code,
        "design_target_id": current.get("design_target_id"),
        "expected_state_revision": expected_revision,
        "design_note": _text(design.get("design_note")),
        "applied": applied,
    }
    design_id = _hash_id(
        "HD",
        repr(sorted(payload.items(), key=lambda item: item[0])),
    )
    audit = {
        "design_id": design_id,
        **payload,
        "state_before": state_before,
        "state_after": hypothesis.get("state"),
        "authority": "EXPLORATION_DESIGN_ONLY_NO_EXECUTION_OR_PROMOTION",
    }
    audits = ledger.setdefault("design_audits", [])
    if not any(
        isinstance(item, dict) and item.get("design_id") == design_id
        for item in audits
    ):
        audits.append(deepcopy(audit))
    return audit


def record_authorized_action_outcome(
    state, action_record, execution_receipt, result_audit
):
    """Persist a bounded action outcome and close its exact route.

    Exhaustion and falsification are first-class negative knowledge. The route
    closure prevents the same query from being silently proposed again while
    retaining enough bounded receipts for later audit.
    """
    ledger = _ledger(state)
    if ledger is None:
        raise ValueError("hypothesis_track_not_initialized")
    stored = _stored_authorized_action(state, action_record)
    action_id = stored["action_id"]
    receipt = (
        execution_receipt if isinstance(execution_receipt, dict) else {}
    )
    if (
        receipt.get("action_id") != action_id
        or receipt.get("execution_status")
        not in {
            "OBSERVATION_RECORDED",
            "EXHAUSTED",
            "FALSIFIED_ROUTE",
            "EXECUTION_FAILED_NO_SEARCH",
            "EXECUTION_FAILED_DURING_QUERY",
        }
        or receipt.get("automatic_follow_on") is not False
        or not _text(receipt.get("result_sha256"))
        or not _text(receipt.get("stop_reason"))
    ):
        raise ValueError("authorized_action_execution_receipt_invalid")
    proposal = stored.get("proposal") or {}
    hypothesis_id = _text(proposal.get("hypothesis_id"))
    if (
        receipt["execution_status"] in {
            "OBSERVATION_RECORDED",
            "FALSIFIED_ROUTE",
        }
        and not stored.get("engine_result_ingested")
    ):
        raise ValueError("authorized_action_observation_not_ingested")
    outcome = {
        "action_id": action_id,
        "sequence": int(stored.get("sequence") or 0),
        "hypothesis_id": hypothesis_id,
        "action_code": proposal.get("action_code"),
        "route_id": (
            proposal.get("route_spec", {}).get("route_id")
            if isinstance(proposal.get("route_spec"), dict)
            else None
        ),
        "planned_proxy": (
            proposal.get("route_spec", {}).get("proxy")
            if isinstance(proposal.get("route_spec"), dict)
            else None
        ),
        "proxy_id": result_audit.get("proxy_id"),
        "observation": result_audit.get("observation"),
        "execution_status": receipt["execution_status"],
        "status": {
            "EXECUTION_FAILED_NO_SEARCH": "FAILED_NO_SEARCH",
            "EXECUTION_FAILED_DURING_QUERY": "FAILED_DURING_QUERY",
        }.get(receipt["execution_status"], "COMPLETED"),
        "source_class": proposal.get("source_class"),
        "bounded_query": proposal.get("bounded_query"),
        "success_condition": proposal.get("success_condition"),
        "stop_condition": proposal.get("stop_condition"),
        "authorization_receipt": deepcopy(
            stored.get("authorization_receipt")
        ),
        "authorization_assurance": stored.get(
            "authorization_assurance",
            "CALLER_ATTESTED_NOT_HOST_VERIFIED",
        ),
        "execution_receipt": deepcopy(receipt),
        "result_audit": deepcopy(result_audit),
        "negative_knowledge": (
            receipt["stop_reason"]
            if receipt["execution_status"]
            in {"EXHAUSTED", "FALSIFIED_ROUTE"}
            else None
        ),
        "authority": "EXPLORATION_ONLY_NO_PROMOTION",
    }
    _upsert_authorized_action_audit(ledger, outcome)
    route_key = (
        None
        if receipt["execution_status"] in {
            "EXECUTION_FAILED_NO_SEARCH",
            "EXECUTION_FAILED_DURING_QUERY",
        }
        else _action_route_key(proposal)
    )
    if route_key:
        closed = ledger.setdefault("closed_routes", [])
        route_record = {
            "route_id": (
                _text(proposal.get("route_spec", {}).get("route_id"))
                if isinstance(proposal.get("route_spec"), dict)
                else ""
            ) or _hash_id("ER", route_key),
            "route_key": route_key,
            "action_id": action_id,
            "sequence": int(stored.get("sequence") or 0),
            "hypothesis_id": hypothesis_id,
            "source_class": proposal.get("source_class"),
            "bounded_query": proposal.get("bounded_query"),
            "execution_status": receipt["execution_status"],
            "stop_reason": receipt["stop_reason"],
            "execution_receipt": deepcopy(receipt),
        }
        existing = next(
            (
                item for item in closed
                if isinstance(item, dict)
                and item.get("route_key") == route_key
            ),
            None,
        )
        if existing is None:
            closed.append(route_record)
        else:
            existing.clear()
            existing.update(route_record)
        closed.sort(key=lambda item: (
            int(item.get("sequence") or 0),
            _text(item.get("route_id")),
        ))
    return deepcopy(outcome)


def _ranked_hypotheses(ledger):
    hypotheses = []
    for item in ledger.get("hypotheses", []):
        if not isinstance(item, dict):
            continue
        _refresh(item)
        hypotheses.append(item)
    return sorted(
        hypotheses,
        key=lambda item: (
            -int((item.get("exploration_priority") or {}).get("score") or 0),
            item.get("hypothesis_id", ""),
        ),
    )


def summary(state):
    """Return compact exploration maturity and queue counts."""
    ledger = _ledger(state)
    if ledger is None:
        return {
            "exploration_enabled": False,
            "research_intent": THESIS_CHALLENGE,
            "hypothesis_count": 0,
            "state_counts": {
                HYPOTHESIS_ONLY: 0,
                TRACED: 0,
                EVIDENCE_BACKED: 0,
            },
            "proxy_trail_count": 0,
            "evidence_backed_proxy_count": 0,
            "known_break_even_count": 0,
            "authorized_action_count": 0,
            "design_audit_count": 0,
            "completed_action_count": 0,
            "exhausted_route_count": 0,
            "falsified_route_count": 0,
            "closed_route_count": 0,
            "priority_counts": {
                "EXPLORE_NOW": 0,
                "EXPLORE_NEXT": 0,
                "PARK": 0,
            },
            "highest_priority_hypothesis_id": None,
            "priority_semantics": PRIORITY_SEMANTICS,
            "capability_boundary": deepcopy(CAPABILITY_BOUNDARY),
        }
    ranked = _ranked_hypotheses(ledger)
    state_counts = {name: 0 for name in HYPOTHESIS_STATES}
    priority_counts = {"EXPLORE_NOW": 0, "EXPLORE_NEXT": 0, "PARK": 0}
    proxy_count = 0
    evidence_proxy_count = 0
    known_break_even_count = 0
    action_audits = [
        item
        for item in ledger.get("authorized_action_audits", [])
        if isinstance(item, dict)
    ]
    closed_routes = [
        item
        for item in ledger.get("closed_routes", [])
        if isinstance(item, dict)
    ]
    for item in ranked:
        state_counts[item["state"]] += 1
        band = item["exploration_priority"]["band"]
        priority_counts[band] += 1
        trails = item.get("proxy_trails", [])
        proxy_count += len(trails)
        evidence_proxy_count += sum(bool(proxy.get("evidence")) for proxy in trails)
        known_break_even_count += (
            item.get("break_even_threshold", {}).get("status") == "KNOWN"
        )
    return {
        "exploration_enabled": True,
        "research_intent": ledger.get("research_intent", THESIS_CHALLENGE),
        "hypothesis_count": len(ranked),
        "state_counts": state_counts,
        "proxy_trail_count": proxy_count,
        "evidence_backed_proxy_count": evidence_proxy_count,
        "known_break_even_count": int(known_break_even_count),
        "authorized_action_count": len(action_audits),
        "design_audit_count": len([
            item for item in ledger.get("design_audits", [])
            if isinstance(item, dict)
        ]),
        "completed_action_count": sum(
            item.get("status") == "COMPLETED" for item in action_audits
        ),
        "exhausted_route_count": sum(
            item.get("execution_status") == "EXHAUSTED"
            for item in action_audits
        ),
        "falsified_route_count": sum(
            item.get("execution_status") == "FALSIFIED_ROUTE"
            for item in action_audits
        ),
        "closed_route_count": len(closed_routes),
        "priority_counts": priority_counts,
        "highest_priority_hypothesis_id": (
            ranked[0]["hypothesis_id"] if ranked else None
        ),
        "priority_semantics": PRIORITY_SEMANTICS,
        "capability_boundary": deepcopy(CAPABILITY_BOUNDARY),
    }


def _overlay_host_action_state(state, action):
    """Make the single frozen host action authoritative over recomputation."""
    open_records = [
        record
        for record in state.get("exploration_actions", [])
        if isinstance(record, dict)
        and record.get("status") in {
            "PLANNED_NOT_AUTHORIZED",
            "AUTHORIZED_NOT_EXECUTED",
        }
    ]
    if not open_records:
        return action
    record = sorted(
        open_records,
        key=lambda item: (
            int(item.get("sequence") or 0),
            _text(item.get("action_id")),
        ),
    )[-1]
    frozen = (
        deepcopy(record.get("proposal"))
        if isinstance(record.get("proposal"), dict)
        else {}
    )
    frozen_route_id = (
        frozen.get("route_spec", {}).get("route_id")
        if isinstance(frozen.get("route_spec"), dict)
        else None
    )
    computed_route_id = (
        action.get("route_spec", {}).get("route_id")
        if isinstance(action.get("route_spec"), dict)
        else None
    )
    proposal_drifted = any((
        frozen.get("hypothesis_id") != action.get("hypothesis_id"),
        frozen.get("action_code") != action.get("action_code"),
        frozen.get("source_class") != action.get("source_class"),
        frozen.get("bounded_query") != action.get("bounded_query"),
        frozen_route_id != computed_route_id,
    ))
    status = record.get("status")
    projected = {
        **frozen,
        "action_id": record.get("action_id"),
        "host_action_status": status,
        "proposal_drifted": proposal_drifted,
        "recomputed_action": (
            {
                "action_code": action.get("action_code"),
                "hypothesis_id": action.get("hypothesis_id"),
                "source_class": action.get("source_class"),
                "bounded_query": action.get("bounded_query"),
                "route_id": computed_route_id,
            }
            if proposal_drifted
            else None
        ),
        "authorization_assurance": record.get(
            "authorization_assurance"
        ),
        "execution_receipt": deepcopy(record.get("execution_receipt")),
    }
    if status == "PLANNED_NOT_AUTHORIZED":
        projected["authorization_state"] = "PLANNED_NOT_AUTHORIZED"
        projected["authorization_ready"] = True
        projected["instruction"] = (
            "This frozen action is the only open exploration plan. "
            "Authorize or explicitly cancel this exact action_id before "
            "planning another action."
        )
        return projected
    if status == "AUTHORIZED_NOT_EXECUTED":
        projected.update({
            "planned_action_code": frozen.get("action_code"),
            "action_code": "AUTHORIZED_ACTION_IN_FLIGHT",
            "action_type": "AUTHORIZED_ACTION_IN_FLIGHT",
            "instruction": (
                "This exact action is already authorized and dispatched; "
                "await or submit its bounded receipt. Do not plan it again."
            ),
            "requires_human_authorization": False,
            "authorization_state": "AUTHORIZED_NOT_EXECUTED",
            "authorization_ready": False,
            "executable_after_authorization": False,
            "budget_boundary": {
                **SMALL_RESEARCH_BUDGET,
                "max_bounded_queries": 0,
                "max_documents_read": 0,
                "max_new_proxy_trails": 0,
                "max_new_publisher_domains": 0,
            },
            "dispatch_receipt": {
                "action_id": record.get("action_id"),
                "authorization_assurance": record.get(
                    "authorization_assurance"
                ),
                "dispatch_contract_frozen": isinstance(
                    record.get("dispatch_contract"), dict
                ),
            },
        })
        return projected
    return projected


def exploration_action(state, include_host_state=True):
    """Return one next research action without creating a promotion side effect."""
    ledger = _ledger(state)
    if ledger is None:
        return {
            "action_code": "NO_EXPLORATION_TRACK",
            "action_type": "NO_EXPLORATION_TRACK",
            "hypothesis_id": None,
            "reason": "hypothesis_track_not_initialized",
            "requires_human_authorization": False,
            "authorization_state": "NOT_REQUIRED",
            "execution_receipt": None,
            "budget_boundary": {
                **SMALL_RESEARCH_BUDGET,
                "max_bounded_queries": 0,
                "max_documents_read": 0,
                "max_new_proxy_trails": 0,
                "max_new_publisher_domains": 0,
            },
            "authority": "RESEARCH_ONLY_NO_PROMOTION",
            "capability_boundary": deepcopy(CAPABILITY_BOUNDARY),
        }
    ranked = _ranked_hypotheses(ledger)
    if not ranked:
        return {
            "action_code": "NO_HYPOTHESIS_AVAILABLE",
            "action_type": "NO_HYPOTHESIS_AVAILABLE",
            "hypothesis_id": None,
            "reason": "hypothesis_garden_is_empty",
            "requires_human_authorization": False,
            "authorization_state": "NOT_REQUIRED",
            "execution_receipt": None,
            "budget_boundary": {
                **SMALL_RESEARCH_BUDGET,
                "max_bounded_queries": 0,
                "max_documents_read": 0,
                "max_new_proxy_trails": 0,
                "max_new_publisher_domains": 0,
            },
            "authority": "RESEARCH_ONLY_NO_PROMOTION",
            "capability_boundary": deepcopy(CAPABILITY_BOUNDARY),
        }
    def classify(hypothesis):
        if hypothesis["state"] == HYPOTHESIS_ONLY:
            planned_routes = [
                item
                for item in hypothesis.get("proxy_plan", [])
                if isinstance(item, dict)
                and _text(item.get("publisher_class"))
                and _text(item.get("bounded_query"))
            ]
            if planned_routes:
                return (
                    "COLLECT_FIRST_PROXY_EVIDENCE",
                    "Test the cheapest declared ProxyTrail route against one "
                    "bounded publisher query; preserve ambiguous or negative results.",
                )
            return (
                "DESIGN_PROXY_TRAIL",
                "Define one observable supporting proxy and one observable "
                "disconfirming proxy before seeking promotion evidence.",
            )
        if hypothesis["state"] == TRACED:
            basis = hypothesis.get("maturity_basis") or {}
            if not basis.get("strongest_alternative_explanation_preserved"):
                return (
                    "ARTICULATE_STRONGEST_ALTERNATIVE",
                    "State the strongest ordinary alternative explanation before "
                    "interpreting proxy observations.",
                )
            if basis.get("evidence_bearing_proxy_trail_count", 0) < 2:
                return (
                    "COLLECT_SECOND_PROXY_EVIDENCE",
                    "Test a distinct causal proxy against a concrete dated "
                    "publisher source; preserve contradictory or ambiguous results.",
                )
            if basis.get("independent_publisher_domain_count", 0) < 2:
                return (
                    "SEEK_INDEPENDENT_PUBLISHER",
                    "Replicate the trace through a second publisher domain; agent "
                    "source labels do not establish independence.",
                )
            return (
                "COLLECT_PROXY_EVIDENCE",
                "Test the highest-priority ProxyTrail against a concrete dated "
                "publisher source; preserve contradictions.",
            )
        directions = {
            item.get("direction")
            for item in hypothesis.get("proxy_trails", [])
        }
        if "CONTRADICTS" not in directions:
            return (
                "SEEK_DISCONFIRMING_PROXY",
                "Seek an independent disconfirming proxy; evidence-backed "
                "exploration does not authorize candidate promotion.",
            )
        return (
            "TEST_INDEPENDENT_REPLICATION",
            "Test whether an independent publisher reproduces the decisive "
            "proxy relationship; do not convert it into a candidate here.",
        )

    def route_pool_for(hypothesis, action_code):
        candidates = [
            item
            for item in (
                list(hypothesis.get("proxy_trails", []))
                + list(hypothesis.get("proxy_plan", []))
            )
            if isinstance(item, dict)
        ]
        planned_items = [
            item for item in candidates if not item.get("evidence")
        ]
        evidenced_items = [
            item for item in candidates if item.get("evidence")
        ]
        contradicting_items = [
            item for item in candidates
            if _text(item.get("direction")).upper() == "CONTRADICTS"
        ]
        if action_code == "COLLECT_FIRST_PROXY_EVIDENCE":
            return planned_items
        if action_code == "COLLECT_SECOND_PROXY_EVIDENCE":
            evidenced_maturity_keys = {
                _proxy_maturity_key(item)
                for item in hypothesis.get("proxy_trails", [])
                if isinstance(item, dict) and item.get("evidence")
            }
            return [
                item for item in planned_items
                if _proxy_maturity_key(item)
                not in evidenced_maturity_keys
            ]
        if action_code in {
            "SEEK_INDEPENDENT_PUBLISHER",
            "TEST_INDEPENDENT_REPLICATION",
        }:
            return evidenced_items + planned_items
        if action_code == "SEEK_DISCONFIRMING_PROXY":
            return contradicting_items
        if action_code == "COLLECT_PROXY_EVIDENCE":
            return planned_items + evidenced_items
        return []

    closed_key_by_hypothesis = {}
    for item in ledger.get("closed_routes", []):
        if not isinstance(item, dict) or not item.get("route_key"):
            continue
        closed_key_by_hypothesis.setdefault(
            item.get("hypothesis_id"), set()
        ).add(item["route_key"])

    def has_open_executable_route(hypothesis):
        action_code, _ = classify(hypothesis)
        for candidate in route_pool_for(hypothesis, action_code):
            if any(
                candidate.get(f"{field}_contested")
                for field in (
                    "publisher_class",
                    "next_source_class",
                    "bounded_query",
                    "stop_condition",
                )
            ):
                continue
            source = (
                candidate.get("next_source_class")
                or candidate.get("publisher_class")
            )
            query = candidate.get("bounded_query")
            if not _text(source) or not _text(query):
                continue
            key = _action_route_key({
                "hypothesis_id": hypothesis["hypothesis_id"],
                "source_class": source,
                "bounded_query": query,
                "route_spec": {
                    "route_id": exploration_route_id(
                        hypothesis["hypothesis_id"],
                        source,
                        query,
                        candidate.get("proxy"),
                        (
                            candidate.get("causal_link")
                            or candidate.get("why_diagnostic")
                        ),
                    )
                },
            })
            if key not in closed_key_by_hypothesis.get(
                hypothesis["hypothesis_id"], set()
            ):
                return True
        return False

    selected = next(
        (
            item for item in ranked
            if has_open_executable_route(item)
        ),
        ranked[0],
    )
    code, instruction = classify(selected)
    routes = [
        item
        for item in (
            list(selected.get("proxy_trails", []))
            + list(selected.get("proxy_plan", []))
        )
        if isinstance(item, dict)
    ]

    def route_ready(item):
        return bool(
            _text(item.get("next_source_class") or item.get("publisher_class"))
            and _text(item.get("bounded_query"))
            and not any(
                item.get(f"{field}_contested")
                for field in (
                    "publisher_class",
                    "next_source_class",
                    "bounded_query",
                    "stop_condition",
                )
            )
        )

    closed_routes = [
        item
        for item in ledger.get("closed_routes", [])
        if isinstance(item, dict)
        and item.get("hypothesis_id") == selected["hypothesis_id"]
    ]
    closed_keys = {
        item.get("route_key") for item in closed_routes if item.get("route_key")
    }

    def route_key(item):
        source = (
            item.get("next_source_class")
            or item.get("publisher_class")
        )
        query = item.get("bounded_query")
        return _action_route_key({
            "hypothesis_id": selected["hypothesis_id"],
            "source_class": source,
            "bounded_query": query,
            "route_spec": {
                "route_id": exploration_route_id(
                    selected["hypothesis_id"],
                    source,
                    query,
                    item.get("proxy"),
                    (
                        item.get("causal_link")
                        or item.get("why_diagnostic")
                    ),
                )
            },
        })

    planned = [item for item in routes if not item.get("evidence")]
    evidenced = [item for item in routes if item.get("evidence")]
    contradicting = [
        item for item in routes
        if _text(item.get("direction")).upper() == "CONTRADICTS"
    ]
    if code == "COLLECT_FIRST_PROXY_EVIDENCE":
        route_pool = planned
    elif code == "COLLECT_SECOND_PROXY_EVIDENCE":
        evidenced_maturity_keys = {
            _proxy_maturity_key(item)
            for item in selected.get("proxy_trails", [])
            if isinstance(item, dict) and item.get("evidence")
        }
        route_pool = [
            item for item in planned
            if _proxy_maturity_key(item) not in evidenced_maturity_keys
        ]
    elif code in {"SEEK_INDEPENDENT_PUBLISHER", "TEST_INDEPENDENT_REPLICATION"}:
        route_pool = evidenced + planned
    elif code == "SEEK_DISCONFIRMING_PROXY":
        route_pool = contradicting
    elif code == "COLLECT_PROXY_EVIDENCE":
        route_pool = planned + evidenced
    else:
        route_pool = []
    ready_routes = [item for item in route_pool if route_ready(item)]
    open_routes = [
        item for item in ready_routes if route_key(item) not in closed_keys
    ]
    if ready_routes and not open_routes:
        last_closed = next(
            (
                item for item in reversed(closed_routes)
                if item.get("route_key") in {
                    route_key(route) for route in ready_routes
                }
            ),
            closed_routes[-1] if closed_routes else {},
        )
        zero_budget = {
            **SMALL_RESEARCH_BUDGET,
            "max_bounded_queries": 0,
            "max_documents_read": 0,
            "max_new_proxy_trails": 0,
            "max_new_publisher_domains": 0,
        }
        return {
            "action_code": "NO_FOLLOW_ON_AFTER_BOUNDED_ACTION",
            "action_type": "NO_FOLLOW_ON_AFTER_BOUNDED_ACTION",
            "hypothesis_id": selected["hypothesis_id"],
            "hypothesis_state": selected["state"],
            "priority": deepcopy(selected["exploration_priority"]),
            "break_even_threshold": deepcopy(
                selected["break_even_threshold"]
            ),
            "reason": (
                "The exact bounded route is closed after "
                f"{last_closed.get('execution_status', 'COMPLETED')}; "
                "design a materially different route before any new plan."
            ),
            "instruction": (
                "Preserve the completed receipt as negative knowledge; do not "
                "repeat or automatically broaden the closed route."
            ),
            "question": None,
            "source_class": None,
            "bounded_query": None,
            "success_condition": None,
            "stop_condition": None,
            "requires_human_authorization": False,
            "authorization_state": "ROUTE_CLOSED_REQUIRES_NEW_PLAN",
            "authorization_ready": False,
            "executable_after_authorization": False,
            "execution_receipt": deepcopy(
                last_closed.get("execution_receipt")
            ),
            "budget_boundary": zero_budget,
            "authority": "RESEARCH_ONLY_NO_PROMOTION",
            "capability_boundary": deepcopy(CAPABILITY_BOUNDARY),
        }
    route = open_routes[0] if open_routes else {}
    question = (
        _text(selected.get("cheap_discriminating_test"))
        or _text(selected.get("pricing_question"))
        or instruction
    )
    source_class = (
        _text(route.get("next_source_class"))
        or _text(route.get("publisher_class"))
        or None
    )
    bounded_query = _text(route.get("bounded_query")) or None
    if code == "ARTICULATE_STRONGEST_ALTERNATIVE":
        success_condition = (
            "One explicit ordinary alternative explanation and one observable "
            "discriminator are written into the ledger without changing evidence state."
        )
    elif code == "DESIGN_PROXY_TRAIL":
        success_condition = (
            "One SUPPORTS and one CONTRADICTS observable route each specify a "
            "publisher class, bounded query, and stop condition."
        )
    else:
        success_condition = (
            "One dated, admissible observation changes the hypothesis information "
            "state while preserving its alternative explanation and direction."
        )
    stop_condition = (
        _text(route.get("stop_condition"))
        or "Stop when the requested one-query budget is exhausted without one "
        "new admissible observation."
    )
    executable = bool(source_class and bounded_query) and code not in {
        "DESIGN_PROXY_TRAIL",
        "ARTICULATE_STRONGEST_ALTERNATIVE",
    }
    route_spec = None
    if route:
        route_spec = {
            "proxy": _text(route.get("proxy")),
            "causal_link": (
                _text(route.get("causal_link"))
                or _text(route.get("why_diagnostic"))
            ),
            "direction": (
                _text(route.get("direction")).upper() or "AMBIGUOUS"
            ),
            "alternative_explanation": _text(
                route.get("alternative_explanation")
            ),
            "checkpoint": _text(route.get("checkpoint")),
            "origin_crux": (
                _text(route.get("origin_crux"))
                or _text(selected.get("context", {}).get("origin_crux"))
                or None
            ),
        }
        route_spec["route_id"] = exploration_route_id(
            selected["hypothesis_id"],
            source_class,
            bounded_query,
            route_spec["proxy"],
            route_spec["causal_link"],
        )
    design_target_payload = {
        "hypothesis_id": selected["hypothesis_id"],
        "hypothesis_state": selected["state"],
        "action_code": code,
        "question": question,
        "proxy_plan": selected.get("proxy_plan", []),
        "proxy_routes": [
            {
                "proxy_id": item.get("proxy_id"),
                "route_id": item.get("route_id"),
                "route_field_variants": item.get("field_variants", {}),
                "route_contested": {
                    field: bool(item.get(f"{field}_contested"))
                    for field in (
                        "publisher_class",
                        "next_source_class",
                        "bounded_query",
                        "stop_condition",
                    )
                },
            }
            for item in selected.get("proxy_trails", [])
            if isinstance(item, dict)
        ],
        "alternative_variants": selected.get(
            "field_variants", {}
        ).get("strongest_alternative_explanation", []),
    }
    design_target_id = _hash_id(
        "DT",
        repr(sorted(
            design_target_payload.items(), key=lambda item: item[0]
        )),
    )
    action = {
        "action_code": code,
        "action_type": code,
        "hypothesis_id": selected["hypothesis_id"],
        "hypothesis_state": selected["state"],
        "priority": deepcopy(selected["exploration_priority"]),
        "break_even_threshold": deepcopy(selected["break_even_threshold"]),
        "instruction": instruction,
        "question": question,
        "source_class": source_class,
        "bounded_query": bounded_query,
        "success_condition": success_condition,
        "stop_condition": stop_condition,
        "route_spec": route_spec,
        "excluded_existing_domains": (
            deepcopy(
                selected.get("maturity_basis", {}).get(
                    "publisher_domains", []
                )
            )
            if code in {
                "SEEK_INDEPENDENT_PUBLISHER",
                "TEST_INDEPENDENT_REPLICATION",
            }
            else []
        ),
        "design_target_id": design_target_id,
        "design_state_revision": int(
            state.get("runtime", {}).get("state_revision", 0) or 0
        ),
        "requires_human_authorization": executable,
        "authorization_state": (
            "PROPOSED_NOT_AUTHORIZED"
            if executable
            else "NEEDS_ACTION_DESIGN"
        ),
        "authorization_ready": executable,
        "executable_after_authorization": executable,
        "execution_receipt": None,
        "budget_boundary": deepcopy(SMALL_RESEARCH_BUDGET),
        "authority": "RESEARCH_ONLY_NO_PROMOTION",
        "capability_boundary": deepcopy(CAPABILITY_BOUNDARY),
    }
    return (
        _overlay_host_action_state(state, action)
        if include_host_state
        else action
    )


def _proxy_report_view(proxy):
    evidence = [
        citation for citation in proxy.get("evidence", [])
        if isinstance(citation, dict) and valid_citation(citation)
    ]
    publishers = sorted({
        publisher
        for citation in evidence
        for publisher in [citation_publisher_identity(citation)]
        if publisher
    })
    proxy_id = proxy.get("proxy_id")
    causal_link = proxy.get("causal_link") or proxy.get("why_diagnostic")
    return {
        "proxy_id": proxy_id,
        "id": proxy_id,
        "trail_ids": deepcopy(proxy.get("trail_ids", [])),
        "route_id": proxy.get("route_id"),
        "planned_proxy": proxy.get("planned_proxy"),
        "planned_direction": proxy.get("planned_direction"),
        "authorized_action_id": proxy.get("authorized_action_id"),
        "authorized_action_ids": deepcopy(
            proxy.get("authorized_action_ids", [])
        ),
        "authorized_route_bindings": deepcopy(
            proxy.get("authorized_route_bindings", [])
        ),
        "proxy": proxy.get("proxy"),
        "causal_link": causal_link,
        "why_diagnostic": causal_link,
        "alternative_explanation": proxy.get("alternative_explanation"),
        "direction": proxy.get("direction", "AMBIGUOUS"),
        "direction_variants": deepcopy(
            proxy.get("direction_variants", [])
        ),
        "direction_contested": bool(
            proxy.get("direction_contested")
        ),
        "direction_bindings": deepcopy(
            proxy.get("direction_bindings", [])
        ),
        "origin_crux": proxy.get("origin_crux"),
        "origin_cruxes": deepcopy(proxy.get("origin_cruxes", [])),
        "checkpoint": proxy.get("checkpoint"),
        "publisher_class": proxy.get("publisher_class"),
        "next_source_class": proxy.get("next_source_class"),
        "bounded_query": proxy.get("bounded_query"),
        "stop_condition": proxy.get("stop_condition"),
        "route_contested_fields": [
            field
            for field in (
                "publisher_class",
                "next_source_class",
                "bounded_query",
                "stop_condition",
            )
            if proxy.get(f"{field}_contested")
        ],
        "route_field_variants": deepcopy({
            field: values
            for field, values in proxy.get("field_variants", {}).items()
            if field in {
                "publisher_class",
                "next_source_class",
                "bounded_query",
                "stop_condition",
            }
        }),
        "evidence_count": len(evidence),
        "publisher_domains": publishers,
        "evidence": deepcopy(evidence),
    }


def _terminal_exploration_action_view(record):
    """Return a sanitized, durable view of one closed host action."""
    proposal = (
        record.get("proposal")
        if isinstance(record.get("proposal"), dict)
        else {}
    )
    execution_receipt = (
        record.get("execution_receipt")
        if isinstance(record.get("execution_receipt"), dict)
        else {}
    )
    stale_result = (
        record.get("stale_result_receipt")
        if isinstance(record.get("stale_result_receipt"), dict)
        else {}
    )
    stale_plan = (
        record.get("stale_receipt")
        if isinstance(record.get("stale_receipt"), dict)
        else {}
    )
    cancellation = (
        record.get("cancellation_receipt")
        if isinstance(record.get("cancellation_receipt"), dict)
        else {}
    )
    status = _text(record.get("status"))
    route_spec = (
        proposal.get("route_spec")
        if isinstance(proposal.get("route_spec"), dict)
        else {}
    )
    result_sha256 = (
        _text(stale_result.get("result_sha256"))
        or _text(execution_receipt.get("result_sha256"))
        or None
    )
    reason = (
        _text(stale_result.get("reason"))
        or _text(stale_plan.get("reason"))
        or _text(cancellation.get("reason"))
        or _text(execution_receipt.get("failure_reason"))
        or _text(execution_receipt.get("stop_reason"))
        or None
    )
    return {
        "action_id": record.get("action_id"),
        "sequence": int(record.get("sequence") or 0),
        "status": status,
        "hypothesis_id": proposal.get("hypothesis_id"),
        "action_code": proposal.get("action_code"),
        "as_of_date": proposal.get("as_of_date"),
        "route_id": route_spec.get("route_id"),
        "source_class": proposal.get("source_class"),
        "bounded_query": proposal.get("bounded_query"),
        "authorization_assurance": record.get(
            "authorization_assurance"
        ),
        "authorization_occurred": bool(
            record.get("authorization_receipt")
        ),
        "execution_occurred": bool(execution_receipt),
        "execution_status": execution_receipt.get(
            "execution_status"
        ),
        "reason": reason,
        "result_sha256": result_sha256,
        "result_ingested": (
            False
            if status == "STALE_RESULT_NOT_RECORDED"
            else bool(execution_receipt)
        ),
        "proxy_ingested": bool(record.get("engine_result_ingested")),
        "automatic_retry": False,
        "execution_receipt": deepcopy(execution_receipt) or None,
        "authority": "EXPLORATION_LIFECYCLE_AUDIT_NO_PROMOTION",
    }


def report_view(state, limit=5):
    """Return a compact, normalized report projection.

    The projection exposes research priorities, observation/inference
    boundaries, and only citations that still pass the shared evidence gate. It
    excludes raw role payloads, OpportunitySeeds, CandidateScreens, trade
    instructions, promotion commands, and position-sizing inputs.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be a non-negative integer")
    ledger = _ledger(state)
    ranked = _ranked_hypotheses(ledger) if ledger is not None else []
    terminal_actions = [
        _terminal_exploration_action_view(item)
        for item in state.get("exploration_actions", [])
        if isinstance(item, dict)
        and item.get("status") in {
            "CANCELLED_NOT_EXECUTED",
            "STALE_NOT_AUTHORIZED",
            "STALE_RESULT_NOT_RECORDED",
            "FAILED_NO_SEARCH",
            "FAILED_DURING_QUERY",
            "COMPLETED",
        }
    ]
    terminal_actions.sort(key=lambda item: (
        int(item.get("sequence") or 0),
        _text(item.get("action_id")),
    ))
    hypotheses = []
    for item in ranked[:limit]:
        hypothesis_id = item.get("hypothesis_id")
        break_even = deepcopy(item.get("break_even_threshold", {}))
        priority = deepcopy(item.get("exploration_priority", {}))
        observation_evidence = [
            citation
            for citation in item.get("observation_evidence", [])
            if isinstance(citation, dict) and valid_citation(citation)
        ]
        proxy_views = [
            _proxy_report_view(proxy)
            for proxy in item.get("proxy_trails", [])
            if isinstance(proxy, dict)
        ]
        proxy_evidence_count = sum(
            1
            for proxy in proxy_views
            for citation in proxy.get("evidence", [])
            if isinstance(citation, dict) and valid_citation(citation)
        )
        hypotheses.append({
            "hypothesis_id": hypothesis_id,
            "id": hypothesis_id,
            "spark_ids": deepcopy(item.get("spark_ids", [])),
            "state": item.get("state"),
            "hypothesis": item.get("hypothesis"),
            "observation": item.get("observation"),
            "observation_status": (
                "CITED_OBSERVATION"
                if observation_evidence
                else "CITED_PROXY_TRAIL"
                if proxy_evidence_count
                else "UNVERIFIED_CLUE"
            ),
            "observation_evidence": deepcopy(observation_evidence),
            "proxy_evidence_count": proxy_evidence_count,
            "inference": item.get("value_transfer"),
            "context": deepcopy(item.get("context", {})),
            "causal_chain": deepcopy(item.get("causal_chain", [])),
            "why_nonconsensus": item.get("why_nonconsensus"),
            "surprise_if_true": item.get("surprise_if_true"),
            "strongest_alternative_explanation": item.get(
                "strongest_alternative_explanation"
            ),
            "value_transfer": item.get("value_transfer"),
            "economic_capture_test": item.get("economic_capture_test"),
            "pricing_question": item.get("pricing_question"),
            "cheap_discriminating_test": item.get(
                "cheap_discriminating_test"
            ),
            "scenario_paths": deepcopy(item.get("scenario_paths", {})),
            "falsifier": item.get("falsifier"),
            "catalyst": item.get("catalyst"),
            "expiry_date": item.get("expiry_date"),
            "payoff": deepcopy(item.get("payoff", {})),
            "asymmetry_case": deepcopy(
                item.get("asymmetry_case", {})
            ),
            "break_even_threshold": break_even,
            "break_even": deepcopy(break_even),
            "exploration_priority": priority,
            "priority": deepcopy(priority),
            "contested_fields": sorted(
                field
                for field in (
                    "strongest_alternative_explanation",
                    "falsifier",
                    "causal_chain",
                    "scenario_paths",
                    "asymmetry_case",
                    "payoff",
                )
                if item.get(f"{field}_contested")
            ),
            "field_variants": deepcopy(item.get("field_variants", {})),
            "proxy_trails": proxy_views,
        })
    current_action = exploration_action(state)
    research_allocation = []
    for rank, item in enumerate(hypotheses, 1):
        asymmetry = (
            item.get("asymmetry_case")
            if isinstance(item.get("asymmetry_case"), dict)
            else {}
        )
        priority = (
            item.get("exploration_priority")
            if isinstance(item.get("exploration_priority"), dict)
            else {}
        )
        components = (
            priority.get("components")
            if isinstance(priority.get("components"), dict)
            else {}
        )
        selected = (
            current_action.get("hypothesis_id") == item.get("hypothesis_id")
        )
        research_allocation.append({
            "rank": rank,
            "hypothesis_id": item.get("hypothesis_id"),
            "hypothesis": item.get("hypothesis"),
            "attention_band": priority.get("band", "PARK"),
            "information_gap": components.get("information_gap"),
            "testability": components.get("testability"),
            "asymmetry_case": deepcopy(asymmetry),
            "minimum_test": item.get("cheap_discriminating_test"),
            "selected_next_action": selected,
            "validation_budget": (
                deepcopy(current_action.get("budget_boundary", {}))
                if selected
                else {}
            ),
            "stop_condition": (
                current_action.get("stop_condition")
                if selected
                else item.get("falsifier")
            ),
            "semantics": (
                "Research attention and validation-cost comparison only; "
                "not probability, expected return, trade ranking, or sizing."
            ),
        })
    return {
        "summary": summary(state),
        "exploration_action": current_action,
        "research_allocation": research_allocation,
        "authorized_action_history": deepcopy(
            [
                item
                for item in (
                    ledger.get("authorized_action_audits", [])
                    if ledger is not None
                    else []
                )
                if isinstance(item, dict)
            ][-10:]
        ),
        "design_history": deepcopy(
            [
                item
                for item in (
                    ledger.get("design_audits", [])
                    if ledger is not None
                    else []
                )
                if isinstance(item, dict)
            ][-10:]
        ),
        "closed_routes": deepcopy(
            [
                item
                for item in (
                    ledger.get("closed_routes", [])
                    if ledger is not None
                    else []
                )
                if isinstance(item, dict)
            ][-10:]
        ),
        "terminal_action_history": terminal_actions[-10:],
        "hypotheses": hypotheses,
        "projection_semantics": (
            "Compact exploration report only; no raw role payload, candidate "
            "promotion, trade execution, or position-sizing authority."
        ),
    }
