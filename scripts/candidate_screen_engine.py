#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic, two-sided screening for OpportunitySeeds.

Candidate Analyst and Candidate Skeptic answer the same fixed questions in
isolated contexts. This engine validates citation shape/freshness, preserves
disagreement, and computes categorical workflow status. It never estimates
returns, ranks positions, or promotes a candidate into a live thesis.
"""
import calendar
import datetime as dt
import hashlib
import re

import crux_engine
import opportunity_engine


DIMENSIONS = (
    "ECONOMIC_EXPOSURE",
    "EXPECTATION_GAP",
    "VALUATION_CONTEXT",
    "TRADABILITY",
    "GOVERNANCE",
    "CROWDING",
    "CATALYST",
    "FALSIFIER",
)

QUESTIONS = {
    "ECONOMIC_EXPOSURE": "候选是否能直接且实质地承接该价值转移，而不是只有主题相关性？",
    "EXPECTATION_GAP": "是否有证据表明可观察预期尚未充分反映该价值传导？",
    "VALUATION_CONTEXT": "当前估值与隐含预期是否有足够证据可被独立质证？",
    "TRADABILITY": "是否存在用户可实际研究或交易的表达，且没有明显准入/流动性硬障碍？",
    "GOVERNANCE": "是否没有证据支持的治理、关联交易或资本配置致命问题？",
    "CROWDING": "是否没有证据支持的拥挤、反身性或持仓结构致命问题？",
    "CATALYST": "研究视野内是否存在日期或条件明确、可观察的催化？",
    "FALSIFIER": "是否存在具体、可观察且有固定监控源的证伪条件？",
}

ANSWERS = {"YES", "NO", "UNKNOWN"}
MARKET_SENSITIVE = {"VALUATION_CONTEXT", "TRADABILITY", "CROWDING", "CATALYST"}
FRESHNESS_DAYS = {dimension: (120 if dimension in MARKET_SENSITIVE else 550)
                  for dimension in DIMENSIONS}
CRITICAL_REJECT = {
    "ECONOMIC_EXPOSURE",
    "EXPECTATION_GAP",
    "TRADABILITY",
    "GOVERNANCE",
    "CROWDING",
}

MIN_TOTAL_URLS = 6
MIN_PRIMARY_URLS = 2
MIN_SOURCE_ORGS = 4
MIN_URLS_PER_AGENT = 3
MAX_BATCH = 3

RELATION_DIRECTNESS = {
    "DIRECT_WINNER": 3,
    "BOTTLENECK_OWNER": 3,
    "INFRA_ASSET_OWNER": 3,
    "SUBSTITUTE_WINNER": 2,
    "COMPETITOR_WINNER": 2,
    "SHORT_CANDIDATE": 2,
    "SECOND_ORDER": 1,
}


def _text(value):
    return " ".join(str(value or "").split())


def _norm(value):
    return re.sub(r"[^\w一-龥]+", "", _text(value).lower())


def _parse_date(value):
    value = _text(value)
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            parsed = dt.datetime.strptime(value, fmt).date()
            if fmt == "%Y-%m":
                parsed = parsed.replace(day=calendar.monthrange(parsed.year, parsed.month)[1])
            return parsed
        except ValueError:
            continue
    return None


def normalize_as_of(value):
    parsed = _parse_date(value) if value else dt.date.today()
    if not parsed:
        raise ValueError("as_of_date must be YYYY-MM-DD or YYYY-MM")
    return parsed.isoformat()


def _is_fresh(citation, dimension, as_of):
    source_date = _parse_date(citation.get("date"))
    if not source_date or source_date > as_of:
        return False
    return (as_of - source_date).days <= FRESHNESS_DAYS[dimension]


def _evidence_list(items):
    out, seen = [], set()
    for citation in items if isinstance(items, list) else []:
        if not crux_engine.valid_citation(citation):
            continue
        key = crux_engine.citation_identity(citation)
        if key and key not in seen:
            out.append(dict(citation))
            seen.add(key)
    return out


def _assessment(raw, dimension, as_of):
    raw = raw if isinstance(raw, dict) else {}
    submitted = _text(raw.get("answer")).upper()
    answer = submitted if submitted in ANSWERS else "UNKNOWN"
    finding = _text(raw.get("finding"))
    evidence = _evidence_list(raw.get("evidence", []))
    fresh = [c for c in evidence if _is_fresh(c, dimension, as_of)]
    flags = []
    if submitted not in ANSWERS:
        flags.append("invalid_answer")
    if answer != "UNKNOWN" and not finding:
        answer = "UNKNOWN"
        flags.append("answer_zeroed_missing_finding")
    if answer != "UNKNOWN" and not fresh:
        answer = "UNKNOWN"
        flags.append("answer_zeroed_no_fresh_valid_evidence")
    return {
        "submitted_answer": submitted or "UNKNOWN",
        "answer": answer,
        "finding": finding,
        "evidence": evidence,
        "fresh_evidence": fresh,
        "quality_flags": flags,
    }


def _screen_map(payload):
    payload = payload if isinstance(payload, dict) else {}
    screens = payload.get("candidate_screens", [])
    screens = screens if isinstance(screens, list) else []
    out = {}
    for screen in screens[:MAX_BATCH]:
        if isinstance(screen, dict) and screen.get("seed_id") and screen["seed_id"] not in out:
            out[screen["seed_id"]] = screen
    return out


def _question_map(screen):
    out = {}
    questions = screen.get("questions", []) if isinstance(screen, dict) else []
    for item in questions if isinstance(questions, list) else []:
        if not isinstance(item, dict):
            continue
        dimension = _text(item.get("dimension")).upper()
        if dimension in DIMENSIONS and dimension not in out:
            out[dimension] = item
    return out


def _source_org(citation):
    return _norm(citation.get("source"))


def _primary(citation):
    return _text(citation.get("source_tier")).lower() in {"primary", "tier-1", "tier1"}


def _combine_dimension(analyst, skeptic):
    answers = {analyst["answer"], skeptic["answer"]}
    fresh = analyst["fresh_evidence"] + skeptic["fresh_evidence"]
    urls = {crux_engine.citation_source_identity(c) for c in fresh}
    orgs = {_source_org(c) for c in fresh if _source_org(c)}
    corroborated = len(urls) >= 2 and len(orgs) >= 2
    if analyst["answer"] == skeptic["answer"] == "YES" and corroborated:
        state = "SUPPORTED"
    elif analyst["answer"] == skeptic["answer"] == "NO" and corroborated:
        state = "REJECTED"
    elif answers == {"YES", "NO"}:
        state = "CONTESTED"
    else:
        state = "INCOMPLETE"
    return {
        "state": state,
        "analyst": analyst,
        "skeptic": skeptic,
        "unique_fresh_urls": sorted(urls),
        "independent_source_orgs": sorted(orgs),
    }


def _all_screen_evidence(dimensions):
    out, seen = [], set()
    for combined in dimensions.values():
        for side in ("analyst", "skeptic"):
            for citation in combined[side]["fresh_evidence"]:
                key = crux_engine.citation_identity(citation)
                if key and key not in seen:
                    out.append(citation)
                    seen.add(key)
    return out


def _source_gate(dimensions):
    evidence = _all_screen_evidence(dimensions)
    urls = {crux_engine.citation_source_identity(c) for c in evidence}
    primary = {crux_engine.citation_source_identity(c) for c in evidence if _primary(c)}
    orgs = {_source_org(c) for c in evidence if _source_org(c)}
    per_agent = {}
    for side in ("analyst", "skeptic"):
        per_agent[side] = len({
            crux_engine.citation_source_identity(c)
            for dimension in dimensions.values()
            for c in dimension[side]["evidence"]
        })
    checks = {
        "total_unique_urls": len(urls) >= MIN_TOTAL_URLS,
        "primary_unique_urls": len(primary) >= MIN_PRIMARY_URLS,
        "independent_source_orgs": len(orgs) >= MIN_SOURCE_ORGS,
        "analyst_source_breadth": per_agent["analyst"] >= MIN_URLS_PER_AGENT,
        "skeptic_source_breadth": per_agent["skeptic"] >= MIN_URLS_PER_AGENT,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "n_unique_urls": len(urls),
        "n_primary_urls": len(primary),
        "n_source_orgs": len(orgs),
        "unique_urls_per_agent": per_agent,
    }


def _promotion_packet(state, seed):
    return {
        "status": "DRAFT_REQUIRES_SOURCE_VERIFICATION",
        "seed_id": seed.get("seed_id"),
        "candidate": seed.get("candidate"),
        "proposed_topic": f"{seed.get('candidate')} — {seed.get('relation_type')} from {seed.get('origin_crux')}",
        "decision_question_seed": (
            f"在 {state.get('horizon', '3-6M')} 内，{seed.get('candidate')} 是否能通过“"
            f"{seed.get('causal_path')}”形成可证伪的非共识研究机会？"
        ),
        "thesis_seed": (
            f"{seed.get('causal_path')}；经济暴露：{seed.get('economic_exposure')}；"
            f"市场可能漏看：{seed.get('why_market_may_miss')}。"
        ),
        "required_next_step": "先完成页面快照与 claim 对齐；通过后才进入人工确认。",
    }


def _screen_id(seed_id, as_of_date):
    digest = hashlib.sha256(f"{seed_id}|{as_of_date}".encode("utf-8")).hexdigest()[:10].upper()
    return f"CS-{digest}"


def latest_by_seed(state):
    out = {}
    for screen in state.get("candidate_screens", []):
        if not isinstance(screen, dict) or not screen.get("seed_id"):
            continue
        current = out.get(screen["seed_id"])
        if not current or screen.get("as_of_date", "") >= current.get("as_of_date", ""):
            out[screen["seed_id"]] = screen
    return out


def selection_features(seed):
    """Deterministic research-priority features, never an expected-return score."""
    evidence = [
        item for item in seed.get("evidence", [])
        if crux_engine.valid_citation(item)
    ]
    source_urls = {
        crux_engine.citation_source_identity(item) for item in evidence
    }
    source_orgs = {_source_org(item) for item in evidence if _source_org(item)}
    primary_urls = {
        crux_engine.citation_source_identity(item) for item in evidence if _primary(item)
    }
    anchor = seed.get("pricing_anchor") if isinstance(seed.get("pricing_anchor"), dict) else {}
    anchor_fields = (
        "as_of_date", "anchor_type", "metric", "current_value",
        "comparison_value", "source", "source_url", "source_claim",
    )
    window = seed.get("catalyst_window") if isinstance(seed.get("catalyst_window"), dict) else {}
    return {
        "independent_source_orgs": len(source_orgs),
        "unique_source_urls": len(source_urls),
        "primary_source_urls": len(primary_urls),
        "causal_directness": RELATION_DIRECTNESS.get(_text(seed.get("relation_type")).upper(), 0),
        "pricing_anchor_fields": sum(bool(_text(anchor.get(field))) for field in anchor_fields),
        "observable_catalyst": int(bool(
            _text(window.get("event")) and _parse_date(window.get("expected_by"))
        )),
    }


def selection_audit(seeds):
    return [
        {
            "rank": index,
            "seed_id": seed.get("seed_id"),
            "candidate": seed.get("candidate"),
            "features": selection_features(seed),
            "selection_basis": (
                "evidence breadth, causal directness, structured pricing anchor, "
                "and observable catalyst; not return or conviction"
            ),
        }
        for index, seed in enumerate(seeds, 1)
    ]


def screenable_seeds(state, seed_id=None):
    latest = latest_by_seed(state)
    seeds = [s for s in state.get("opportunity_seeds", []) if isinstance(s, dict)]
    if seed_id:
        return [
            seed for seed in seeds
            if seed.get("seed_id") == seed_id
            and opportunity_engine.assess_seed(state, seed)["screening_status"]
            == opportunity_engine.READY
        ][:1]

    seed_by_id = {seed.get("seed_id"): seed for seed in seeds}
    screened_entities = {
        opportunity_engine.entity_identity(seed_by_id[sid])
        for sid in latest if sid in seed_by_id
    }
    out = []
    for entity in opportunity_engine.entity_views(state):
        if entity["screening_status"] != opportunity_engine.READY:
            continue
        if entity["entity_identity"] in screened_entities:
            continue
        out.append(entity["representative_seed"])
    out.sort(key=lambda seed: (
        -selection_features(seed)["independent_source_orgs"],
        -selection_features(seed)["primary_source_urls"],
        -selection_features(seed)["causal_directness"],
        -selection_features(seed)["pricing_anchor_fields"],
        -selection_features(seed)["observable_catalyst"],
        -selection_features(seed)["unique_source_urls"],
        _text(seed.get("seed_id")),
    ))
    return out[:MAX_BATCH]


def evaluate_batch(state, analyst_payload, skeptic_payload, as_of_date=None, isolation_status="unverified"):
    """Evaluate up to three paired candidate screens and persist idempotently."""
    as_of_date = normalize_as_of(as_of_date)
    as_of = _parse_date(as_of_date)
    isolation_status = _text(isolation_status).lower()
    if isolation_status not in {"verified", "degraded", "unverified"}:
        isolation_status = "unverified"
    analyst_map = _screen_map(analyst_payload)
    skeptic_map = _screen_map(skeptic_payload)
    eligible = {
        seed.get("seed_id"): seed
        for seed in state.get("opportunity_seeds", [])
        if isinstance(seed, dict)
        and opportunity_engine.assess_seed(state, seed)["screening_status"]
        == opportunity_engine.READY
    }
    requested_ids = list(dict.fromkeys(list(analyst_map) + list(skeptic_map)))[:MAX_BATCH]
    audit = {
        "as_of_date": as_of_date,
        "submitted_seed_ids": requested_ids,
        "evaluated": 0,
        "unknown_seed_ids": [],
        "missing_analyst": [],
        "missing_skeptic": [],
    }
    screens = state.setdefault("candidate_screens", [])
    by_id = {s.get("screen_id"): i for i, s in enumerate(screens) if isinstance(s, dict)}

    for seed_id in requested_ids:
        seed = eligible.get(seed_id)
        if not seed:
            audit["unknown_seed_ids"].append(seed_id)
            continue
        analyst_raw = analyst_map.get(seed_id, {})
        skeptic_raw = skeptic_map.get(seed_id, {})
        if not analyst_raw:
            audit["missing_analyst"].append(seed_id)
        if not skeptic_raw:
            audit["missing_skeptic"].append(seed_id)
        analyst_questions = _question_map(analyst_raw)
        skeptic_questions = _question_map(skeptic_raw)
        dimensions = {}
        for dimension in DIMENSIONS:
            analyst = _assessment(analyst_questions.get(dimension), dimension, as_of)
            skeptic = _assessment(skeptic_questions.get(dimension), dimension, as_of)
            dimensions[dimension] = _combine_dimension(analyst, skeptic)

        source_gate = _source_gate(dimensions)
        rejected = [d for d in CRITICAL_REJECT if dimensions[d]["state"] == "REJECTED"]
        if rejected:
            status = "REJECTED"
        elif (all(dimensions[d]["state"] == "SUPPORTED" for d in DIMENSIONS)
              and source_gate["passed"] and isolation_status == "verified"):
            status = "THESIS_CANDIDATE"
        else:
            status = "WATCHLIST"
        gaps = [d for d in DIMENSIONS if dimensions[d]["state"] != "SUPPORTED"]
        gaps += [name for name, passed in source_gate["checks"].items() if not passed]
        if isolation_status != "verified":
            gaps.append("screen_isolation_unverified")
        screen = {
            "screen_id": _screen_id(seed_id, as_of_date),
            "seed_id": seed_id,
            "entity_id": opportunity_engine.entity_id(seed),
            "candidate": seed.get("candidate"),
            "ticker": seed.get("ticker"),
            "as_of_date": as_of_date,
            "isolation_status": isolation_status,
            "status": status,
            "dimensions": dimensions,
            "source_gate": source_gate,
            "gaps": gaps,
            "critical_rejections": sorted(rejected),
            "promotion_packet": _promotion_packet(state, seed) if status == "THESIS_CANDIDATE" else None,
        }
        if screen["screen_id"] in by_id:
            screens[by_id[screen["screen_id"]]] = screen
        else:
            screens.append(screen)
            by_id[screen["screen_id"]] = len(screens) - 1
        seed["screen_status"] = status
        seed["last_screened_as_of"] = as_of_date
        seed["latest_screen_id"] = screen["screen_id"]
        audit["evaluated"] += 1

    screens.sort(key=lambda s: (s.get("as_of_date", ""), s.get("seed_id", "")))
    opportunity_engine.refresh_candidate_states(state)
    audit.update(summary(state))
    return audit


def summary(state):
    latest = latest_by_seed(state)
    counts = {"WATCHLIST": 0, "REJECTED": 0, "THESIS_CANDIDATE": 0}
    for screen in latest.values():
        if screen.get("status") in counts:
            counts[screen["status"]] += 1
    seed_by_id = {
        seed.get("seed_id"): seed for seed in state.get("opportunity_seeds", [])
        if isinstance(seed, dict) and seed.get("seed_id")
    }
    screened_entities = {
        screen.get("entity_id")
        or opportunity_engine.entity_id(seed_by_id[seed_id])
        for seed_id, screen in latest.items() if seed_id in seed_by_id
    }
    return {
        "screened_candidate_count": len(latest),
        "screened_entity_count": len(screened_entities),
        "watchlist_count": counts["WATCHLIST"],
        "rejected_candidate_count": counts["REJECTED"],
        "thesis_candidate_count": counts["THESIS_CANDIDATE"],
    }
