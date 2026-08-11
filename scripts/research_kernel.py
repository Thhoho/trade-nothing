#!/usr/bin/env python3
"""Small deterministic kernel shared by Agenda and CandidateMap.

This module is deliberately not a workflow or lifecycle engine.  It owns only
the invariants that must mean the same thing everywhere in the research
product: evidence validity, answer reconciliation, instrument identity and
conditional-setup readiness.  Callers remain responsible for scheduling,
budgets, reporting and legacy compatibility.
"""
from copy import deepcopy
from datetime import date
import hashlib
import json
import re

import crux_engine


EVIDENCE_BOUNDARIES = {"FACT", "SINGLE_SOURCE", "INFERENCE", "HYPOTHESIS"}
BOUNDARY_RANK = {
    "HYPOTHESIS": 0,
    "INFERENCE": 1,
    "SINGLE_SOURCE": 2,
    "FACT": 3,
}
ANSWER_STATUSES = {"OPEN", "PARTIAL", "ANSWERED", "DISPUTED", "UNANSWERED"}
UNKNOWN_MARKERS = {
    "", "UNKNOWN", "UNVERIFIED", "N/A", "NONE", "未知", "未核验", "—",
}
RESERVED_TICKERS = UNKNOWN_MARKERS | {"TBD", "NA", "NULL", "待定", "待核验"}
FIELD_EVIDENCE_NAMES = {
    "mechanism",
    "economic_exposure",
    "catalyst",
    "price_or_expectation",
    "crowding_or_position",
}
FIELD_CLAIM_ANCHORS = {
    "mechanism": {
        "业务", "供应", "客户", "订单", "收入", "产品", "产业链", "事件",
        "需求", "产能", "技术", "制造", "service", "customer", "order",
        "revenue", "product", "supply", "demand",
    },
    "economic_exposure": {
        "收入", "订单", "客户", "利润", "毛利", "产能", "销量", "业务", "供货",
        "revenue", "order", "customer", "profit", "margin", "capacity", "sales",
    },
    "catalyst": {
        "公告", "计划", "窗口", "日期", "发射", "试验", "发布", "交付", "业绩",
        "结果", "政策", "launch", "window", "date", "release", "delivery", "result",
    },
    "price_or_expectation": {
        "价格", "股价", "收盘", "涨幅", "跌幅", "市值", "估值", "市盈", "回撤",
        "行情", "price", "close", "valuation", "market cap", "drawdown", "pe", "pb",
    },
    "crowding_or_position": {
        "换手", "成交", "资金", "持仓", "融资", "拥挤", "龙虎榜", "流通", "股东",
        "筹码", "turnover", "volume", "holding", "financing", "crowding", "ownership",
    },
}
SETUP_REQUIREMENTS = {
    "EVENT_SETUP": {
        "content": {
            "mechanism", "catalyst", "invalidation", "price_or_expectation",
            "crowding_or_position",
        },
        "evidence": {
            "mechanism", "catalyst", "price_or_expectation",
            "crowding_or_position",
        },
    },
    "ECONOMIC_SETUP": {
        "content": {
            "mechanism", "economic_exposure", "catalyst", "invalidation",
            "price_or_expectation", "crowding_or_position",
        },
        "evidence": {
            "mechanism", "economic_exposure", "catalyst",
            "price_or_expectation",
        },
    },
}


def text(value):
    return " ".join(str(value or "").split())


def norm(value):
    return text(value).lower()


def known(value):
    value_text = text(value)
    if any(marker in value_text for marker in (
        "需更新", "待更新", "待核验", "尚待", "不确定"
    )):
        return False
    return value_text.upper() not in UNKNOWN_MARKERS


def parse_iso_date(value):
    value_text = text(value)
    try:
        return date.fromisoformat(value_text)
    except (TypeError, ValueError):
        return None


def normalize_evidence(raw, as_of_date=""):
    """Return a normalized citation or a stable rejection reason."""
    if not isinstance(raw, dict) or not crux_engine.valid_citation(raw):
        return None, "INVALID_CITATION_ANCHOR"
    evidence_date = parse_iso_date(raw.get("date"))
    if evidence_date is None:
        return None, "EVIDENCE_DATE_REQUIRES_ISO"
    cutoff = parse_iso_date(as_of_date) if text(as_of_date) else None
    if text(as_of_date) and cutoff is None:
        return None, "INVALID_AS_OF_DATE"
    if cutoff is not None and evidence_date > cutoff:
        return None, "EVIDENCE_AFTER_AS_OF_DATE"
    normalized = deepcopy(raw)
    normalized.update({
        "claim": text(raw.get("claim")),
        "source": text(raw.get("source")),
        "url": text(raw.get("url")),
        "date": evidence_date.isoformat(),
        "source_tier": text(raw.get("source_tier")),
    })
    normalized["publisher_identity"] = crux_engine.citation_publisher_identity(
        normalized
    )
    return normalized, None


def evidence_identity(item):
    if not isinstance(item, dict):
        return ""
    identity = crux_engine.citation_identity(item)
    binding = item.get("binding")
    if identity and isinstance(binding, dict) and binding:
        identity += "|binding:" + json.dumps(
            binding, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    return identity


def unique_evidence(items):
    accepted = []
    seen = set()
    for item in items if isinstance(items, list) else []:
        key = evidence_identity(item)
        if key and key not in seen:
            accepted.append(deepcopy(item))
            seen.add(key)
    return accepted


def upsert_canonical_evidence(agenda, raw, as_of_date="", stable_material=None):
    """Insert one non-model evidence fact into the canonical evidence plane.

    Role payload ingestion needs question/direction lineage.  Host-owned data
    has a different trust root: its content receipt and subject binding.  This
    helper keeps both in the same evidence ledger without pretending that a
    model discovered or authored the observation.
    """
    if not isinstance(agenda, dict):
        return None, "AGENDA_REQUIRED"
    normalized, reason = normalize_evidence(raw, as_of_date)
    if reason:
        return None, reason
    material = stable_material if stable_material is not None else {
        "identity": evidence_identity(normalized),
        "origin": text(raw.get("origin")),
        "binding": raw.get("binding") if isinstance(raw.get("binding"), dict) else {},
    }
    digest = hashlib.sha256(json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()[:14].upper()
    evidence_id = text(raw.get("evidence_id")) or f"EV-HOST-{digest}"
    identity = evidence_identity({
        **normalized,
        "binding": raw.get("binding")
        if isinstance(raw.get("binding"), dict) else {},
    })
    items = agenda.setdefault("evidence_items", [])
    aliases = agenda.setdefault("evidence_aliases", {})
    for item in items:
        if not isinstance(item, dict):
            continue
        if evidence_identity(item) == identity:
            if evidence_id != item.get("evidence_id"):
                aliases[evidence_id] = item.get("evidence_id")
            return item, "IDEMPOTENT"
        if text(item.get("evidence_id")) == evidence_id:
            return None, "EVIDENCE_ID_COLLISION"
    item = {
        "evidence_id": evidence_id,
        "question_ids": list(dict.fromkeys(
            text(value) for value in raw.get("question_ids", []) if text(value)
        )) if isinstance(raw.get("question_ids"), list) else [],
        "direction_ids": list(dict.fromkeys(
            text(value) for value in raw.get("direction_ids", []) if text(value)
        )) if isinstance(raw.get("direction_ids"), list) else [],
        "stance": text(raw.get("stance") or "CONTEXT").upper(),
        "claim": normalized.get("claim"),
        "number": normalized.get("number"),
        "source": normalized.get("source"),
        "url": normalized.get("url"),
        "date": normalized.get("date"),
        "source_tier": normalized.get("source_tier"),
        "publisher_identity": normalized.get("publisher_identity"),
        "round": 0,
        "role": "host",
        "roles": ["host"],
        "origin": text(raw.get("origin") or "HOST_OBSERVATION"),
        "binding": deepcopy(raw.get("binding"))
        if isinstance(raw.get("binding"), dict) else {},
    }
    if isinstance(raw.get("supporting_urls"), list):
        item["supporting_urls"] = list(dict.fromkeys(
            text(value) for value in raw["supporting_urls"] if text(value)
        ))
    if raw.get("receipt_id"):
        item["receipt_id"] = text(raw.get("receipt_id"))
    items.append(item)
    return item, "CREATED"


def evidence_plane_counts(items):
    """Count the canonical evidence plane without consulting legacy crux ledgers."""
    accepted = unique_evidence([
        item for item in items if isinstance(item, dict) and crux_engine.valid_citation(item)
    ] if isinstance(items, list) else [])
    source_urls = {
        crux_engine.citation_source_identity(item)
        for item in accepted
        if crux_engine.citation_source_identity(item)
    }
    publishers = {
        crux_engine.citation_publisher_identity(item)
        for item in accepted
        if crux_engine.citation_publisher_identity(item)
    }
    return {
        "canonical_evidence_item_count": len(accepted),
        "unique_source_url_count": len(source_urls),
        "independent_publisher_count": len(publishers),
        "primary_source_count": sum(
            crux_engine.is_primary_citation(item) for item in accepted
        ),
    }


def evidence_boundary(citations, is_inference=False):
    citations = unique_evidence(citations)
    if not citations:
        return "HYPOTHESIS"
    if is_inference:
        return "INFERENCE"
    publishers = {
        crux_engine.citation_publisher_identity(item)
        for item in citations
        if crux_engine.citation_publisher_identity(item)
    }
    return "FACT" if len(publishers) >= 2 else "SINGLE_SOURCE"


def normalize_answer_status(status, boundary, answer):
    status = text(status).upper()
    if status == "UNANSWERED":
        status = "OPEN"
    if status not in {"OPEN", "PARTIAL", "ANSWERED", "DISPUTED"}:
        return "OPEN"
    # An answer may survive as a hypothesis, but it is not complete research.
    if status == "ANSWERED" and (
        not text(answer) or boundary == "HYPOTHESIS"
    ):
        return "PARTIAL"
    return status


def _variant_rank(item):
    status_rank = {"ANSWERED": 3, "PARTIAL": 2, "DISPUTED": 1, "OPEN": 0}
    boundary = text(item.get("evidence_boundary")).upper()
    return (
        BOUNDARY_RANK.get(boundary, 0),
        status_rank.get(text(item.get("answer_status")).upper(), 0),
        len(unique_evidence(item.get("evidence", []))),
        norm(item.get("answer")),
    )


def _join_unique(items, field):
    values = []
    for item in items:
        value = text(item.get(field))
        if value and value not in values:
            values.append(value)
    return "；".join(values)


def _reconcile_answer_peers(variants):
    """Resolve variants from one research instant without role-order dependence."""
    variants = [deepcopy(item) for item in variants if isinstance(item, dict)]
    if not variants:
        return None
    for item in variants:
        item["answer_status"] = normalize_answer_status(
            item.get("answer_status"),
            text(item.get("evidence_boundary")).upper(),
            item.get("answer"),
        )
    ranked = sorted(variants, key=_variant_rank, reverse=True)
    selected = ranked[0]
    selected_rank = BOUNDARY_RANK.get(
        text(selected.get("evidence_boundary")).upper(), 0
    )
    answered = [item for item in variants if item.get("answer_status") == "ANSWERED"]
    dissent = [
        item for item in variants
        if item.get("answer_status") in {"OPEN", "PARTIAL", "DISPUTED"}
    ]
    comparable_dissent = bool(answered and dissent) and max(
        BOUNDARY_RANK.get(text(item.get("evidence_boundary")).upper(), 0)
        for item in dissent
    ) >= max(
        BOUNDARY_RANK.get(text(item.get("evidence_boundary")).upper(), 0)
        for item in answered
    )
    # DISPUTED is an epistemic status: the underlying evidence or mechanism is
    # unsettled.  It is not proof that two agents contradict each other.  A
    # role-level conflict exists only when a completed answer meets comparable
    # dissent.  Two roles may consistently agree that the answer is disputed.
    conflict = comparable_dissent
    status = "DISPUTED" if conflict else selected.get("answer_status", "OPEN")
    answer = text(selected.get("answer"))
    if conflict:
        labelled = []
        for item in sorted(variants, key=lambda row: (
            text(row.get("role")), norm(row.get("answer"))
        )):
            value = text(item.get("answer"))
            if value:
                labelled_value = f"{text(item.get('role')) or 'role'}: {value}"
                if labelled_value not in labelled:
                    labelled.append(labelled_value)
        answer = "；".join(labelled) or answer
    return {
        "answer_status": status,
        "current_answer": answer,
        "evidence_boundary": text(selected.get("evidence_boundary")).upper()
        if selected_rank >= 0 else "HYPOTHESIS",
        "strongest_challenge": _join_unique(variants, "strongest_challenge"),
        "missing_information": _join_unique(variants, "missing_information"),
        "next_question": text(selected.get("next_question"))
        or _join_unique(variants, "next_question"),
        "next_test_availability": text(
            selected.get("next_test_availability") or "UNKNOWN"
        ).upper(),
        "resolution": "CONFLICTED" if conflict else (
            "SHARED_UNCERTAINTY"
            if selected.get("answer_status") == "DISPUTED" and len(variants) > 1
            else "CONSISTENT" if len(variants) > 1 else "SINGLE_VARIANT"
        ),
        "selected_role": text(selected.get("role")),
    }


def reconcile_answer_variants(variants):
    """Project append-only answer history into one current, bounded answer.

    Roles are reconciled symmetrically *within* a round.  Rounds are then folded
    in time.  Treating every old OPEN answer as a current peer made repaired
    data gaps permanently dispute later evidence and caused prompts/reports to
    grow without bound.
    """
    rows = [deepcopy(item) for item in variants if isinstance(item, dict)]
    if not rows:
        return None
    by_round = {}
    for item in rows:
        try:
            round_num = int(item.get("round", 0) or 0)
        except (TypeError, ValueError):
            round_num = 0
        by_round.setdefault(round_num, []).append(item)
    folded = None
    latest_round = 0
    for round_num in sorted(by_round):
        current = _reconcile_answer_peers(by_round[round_num])
        if not current:
            continue
        latest_round = round_num
        if folded is None:
            folded = current
            continue
        old_rank = BOUNDARY_RANK.get(text(folded.get("evidence_boundary")).upper(), 0)
        new_rank = BOUNDARY_RANK.get(text(current.get("evidence_boundary")).upper(), 0)
        preserve_completed = (
            folded.get("answer_status") == "ANSWERED"
            and current.get("answer_status") != "ANSWERED"
            and new_rank < old_rank
        )
        if preserve_completed:
            if text(current.get("strongest_challenge")):
                folded["strongest_challenge"] = text(
                    current.get("strongest_challenge")
                )
            if text(current.get("missing_information")):
                folded["missing_information"] = text(
                    current.get("missing_information")
                )
            if text(current.get("next_question")):
                folded["next_question"] = text(current.get("next_question"))
            folded["next_test_availability"] = text(
                current.get("next_test_availability") or "UNKNOWN"
            ).upper()
            folded["resolution"] = "TEMPORAL_STRONGER_ANSWER_PRESERVED"
        else:
            folded = current
    if folded:
        folded["latest_round"] = latest_round
        if len(by_round) > 1 and not text(folded.get("resolution")).startswith("TEMPORAL_"):
            folded["resolution"] = "TEMPORAL_" + text(
                folded.get("resolution") or "SINGLE_VARIANT"
            )
    return folded


def answer_is_usable(question):
    return (
        isinstance(question, dict)
        and question.get("answer_status") == "ANSWERED"
        and known(question.get("current_answer"))
        and text(question.get("evidence_boundary")).upper() != "HYPOTHESIS"
    )


def answer_has_progress(question):
    """Whether the report has an evidence-bounded answer, complete or not.

    This deliberately differs from ``answer_is_usable``.  A PARTIAL or
    DISPUTED answer can be useful to a human report without satisfying the
    question's success condition or disappearing from future research focus.
    """
    return (
        isinstance(question, dict)
        and text(question.get("answer_status")).upper()
        in {"PARTIAL", "ANSWERED", "DISPUTED"}
        and known(question.get("current_answer"))
        and text(question.get("evidence_boundary")).upper() != "HYPOTHESIS"
    )


def _reconcile_direction_peers(records):
    """Resolve one round of direction judgments conservatively."""
    records = [deepcopy(item) for item in records if isinstance(item, dict)]
    if not records:
        return None
    ranked = sorted(
        records,
        key=lambda item: (
            BOUNDARY_RANK.get(text(item.get("evidence_boundary")).upper(), 0),
            len(item.get("evidence_ids", [])),
            norm(item.get("rationale")),
        ),
        reverse=True,
    )
    top_rank = BOUNDARY_RANK.get(
        text(ranked[0].get("evidence_boundary")).upper(), 0
    )
    peers = [
        item for item in ranked
        if BOUNDARY_RANK.get(text(item.get("evidence_boundary")).upper(), 0)
        == top_rank
    ]
    judgments = {text(item.get("research_judgment")).upper() for item in peers}
    conflict = "SUPPORTED" in judgments and "CHALLENGED" in judgments
    selected = ranked[0]
    next_moves = {text(item.get("next_move")).upper() for item in peers}
    if conflict:
        judgment = "UNRESOLVED"
        next_move = "OPEN_NEW_DIRECTION" if "OPEN_NEW_DIRECTION" in next_moves else "CONTINUE"
    else:
        judgment = text(selected.get("research_judgment")).upper() or "UNRESOLVED"
        next_move = (
            "OPEN_NEW_DIRECTION" if "OPEN_NEW_DIRECTION" in next_moves
            else "CONTINUE" if "CONTINUE" in next_moves
            else "ANSWER"
        )
        if next_move == "ANSWER" and top_rank == 0:
            next_move = "CONTINUE"
    evidence_ids = []
    for item in peers:
        for evidence_id in item.get("evidence_ids", []):
            if evidence_id not in evidence_ids:
                evidence_ids.append(evidence_id)
    return {
        "research_judgment": judgment,
        "next_move": next_move,
        "rationale": _join_unique(peers, "rationale"),
        "evidence_boundary": text(selected.get("evidence_boundary")).upper()
        or "HYPOTHESIS",
        "strongest_challenge": _join_unique(records, "strongest_challenge"),
        "unresolved_question": _join_unique(records, "unresolved_question"),
        "evidence_ids": evidence_ids,
        "next_test_availability": text(
            selected.get("next_test_availability") or "UNKNOWN"
        ).upper(),
        "resolution": "CONFLICTED" if conflict else (
            "CONSISTENT" if len(records) > 1 else "SINGLE_VARIANT"
        ),
    }


def reconcile_direction_records(records):
    """Project append-only direction history into the latest round view."""
    rows = [deepcopy(item) for item in records if isinstance(item, dict)]
    if not rows:
        return None
    by_round = {}
    for item in rows:
        try:
            round_num = int(item.get("round", 0) or 0)
        except (TypeError, ValueError):
            round_num = 0
        by_round.setdefault(round_num, []).append(item)
    latest_round = max(by_round)
    resolved = _reconcile_direction_peers(by_round[latest_round])
    if resolved:
        resolved["latest_round"] = latest_round
        if len(by_round) > 1:
            resolved["resolution"] = "TEMPORAL_" + text(
                resolved.get("resolution") or "SINGLE_VARIANT"
            )
    return resolved


def _infer_a_share_exchange(ticker):
    if not re.fullmatch(r"\d{6}", ticker):
        return ""
    if ticker.startswith(("4", "8", "92")):
        return "XBEI"
    if ticker.startswith(("0", "3")):
        return "XSHE"
    if ticker.startswith(("5", "6", "9")):
        return "XSHG"
    return ""


def normalize_instrument_identity(asset_type, ticker, exchange=""):
    asset_type = text(asset_type or "OTHER").upper()
    ticker = re.sub(r"\s+", "", text(ticker).upper())
    exchange = text(exchange).upper()
    exchange_aliases = {
        "SH": "XSHG", "SSE": "XSHG", "SHSE": "XSHG",
        "SZ": "XSHE", "SZSE": "XSHE",
        "BJ": "XBEI", "BSE": "XBEI",
        "HK": "XHKG", "HKEX": "XHKG",
        "NASDAQ": "XNAS", "NYSE": "XNYS",
    }
    exchange = exchange_aliases.get(exchange, exchange)
    if asset_type != "LISTED_EQUITY":
        return {"ticker": ticker, "exchange": exchange}, None
    if not ticker:
        return None, "listed_equity_ticker_required"
    if ticker in RESERVED_TICKERS:
        return None, "listed_equity_valid_ticker_required"
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,14}", ticker):
        return None, "listed_equity_invalid_ticker"
    if not exchange:
        exchange = _infer_a_share_exchange(ticker)
    if not exchange:
        return None, "listed_equity_exchange_required"
    return {"ticker": ticker, "exchange": exchange}, None


def instrument_identity(item):
    asset_type = text(item.get("asset_type") or "OTHER").upper()
    ticker = text(item.get("ticker")).upper()
    exchange = text(item.get("exchange")).upper()
    if ticker:
        return f"{asset_type}|{exchange}|{ticker}"
    name = re.sub(r"[^\w一-龥]+", "", norm(item.get("candidate")))
    return f"{asset_type}|NAME|{name}"


def normalize_field_evidence(raw_fields, as_of_date=""):
    normalized = {field: [] for field in FIELD_EVIDENCE_NAMES}
    rejections = []
    if not isinstance(raw_fields, dict):
        return normalized, rejections
    for field in FIELD_EVIDENCE_NAMES:
        values = raw_fields.get(field, [])
        if not isinstance(values, list):
            rejections.append({"field": field, "reason": "FIELD_EVIDENCE_NOT_LIST"})
            continue
        for raw in values:
            item, reason = normalize_evidence(raw, as_of_date)
            if reason:
                rejections.append({"field": field, "reason": reason})
                continue
            normalized[field].append(item)
        normalized[field] = unique_evidence(normalized[field])
    return normalized, rejections


def _semantic_units(value):
    """Small bilingual units for bounded category/alignment checks, not entailment."""
    value = norm(value)
    latin = set(re.findall(r"[a-z0-9][a-z0-9._-]{1,}", value))
    cjk_runs = re.findall(r"[\u4e00-\u9fff]+", value)
    cjk = {
        run[index:index + 2]
        for run in cjk_runs
        for index in range(max(0, len(run) - 1))
    }
    return latin | cjk


def claim_supports_field(field, field_value, evidence, mapping_is_inference=False):
    """Reject obvious claim/field category misuse before setup readiness.

    This is intentionally a bounded structural check.  It can catch a price
    citation reused as catalyst evidence, but it cannot prove that the source
    page entails the submitted claim.
    """
    if field not in FIELD_EVIDENCE_NAMES:
        return False, "UNKNOWN_FIELD"
    if not known(field_value):
        return False, "FIELD_CONTENT_REQUIRED"
    claim = norm((evidence or {}).get("claim"))
    if not claim:
        return False, "EVIDENCE_CLAIM_REQUIRED"
    if not claim_matches_field_category(field, evidence):
        return False, "CLAIM_FIELD_CATEGORY_MISMATCH"
    if field in {"mechanism", "economic_exposure"}:
        overlap = _semantic_units(field_value) & _semantic_units(claim)
        if not overlap and not mapping_is_inference:
            return False, "CLAIM_FIELD_TEXT_MISMATCH"
    return True, "CLAIM_FIELD_ALIGNED"


def claim_matches_field_category(field, evidence):
    """Return whether a canonical evidence claim speaks to one field category.

    Unlike ``claim_supports_field``, this helper intentionally does not require
    a model-written field value.  Host-owned data projections use it to prove
    that their canonical evidence anchors cover the market axes they claim to
    measure (price/expectation and crowding/activity).
    """
    if field not in FIELD_EVIDENCE_NAMES:
        return False
    claim = norm((evidence or {}).get("claim"))
    return bool(
        claim
        and any(anchor in claim for anchor in FIELD_CLAIM_ANCHORS.get(field, set()))
    )


def resolve_field_evidence_ids(
    raw_fields, evidence_items, field_values, mapping_is_inference=False,
    evidence_aliases=None,
):
    """Resolve CandidateMap field bindings to canonical Agenda evidence IDs."""
    resolved = {field: [] for field in FIELD_EVIDENCE_NAMES}
    resolved_ids = {field: [] for field in FIELD_EVIDENCE_NAMES}
    checks = []
    rejections = []
    evidence_index = {
        text(item.get("evidence_id")): item
        for item in evidence_items if isinstance(item, dict) and text(item.get("evidence_id"))
    } if isinstance(evidence_items, list) else {}
    evidence_aliases = evidence_aliases if isinstance(evidence_aliases, dict) else {}
    if not isinstance(raw_fields, dict):
        return resolved, resolved_ids, checks, rejections
    for field in FIELD_EVIDENCE_NAMES:
        bindings = raw_fields.get(field, [])
        if not isinstance(bindings, list):
            rejections.append({
                "field": field, "reason": "FIELD_EVIDENCE_IDS_NOT_LIST",
            })
            continue
        for binding in bindings:
            evidence_id = text(
                binding.get("evidence_id") if isinstance(binding, dict) else binding
            )
            if not evidence_id:
                rejections.append({
                    "field": field, "reason": "EVIDENCE_ID_REQUIRED",
                })
                continue
            canonical_id = text(evidence_aliases.get(evidence_id) or evidence_id)
            evidence = evidence_index.get(canonical_id)
            if evidence is None:
                rejections.append({
                    "field": field, "evidence_id": evidence_id,
                    "reason": "UNKNOWN_CANONICAL_EVIDENCE_ID",
                })
                continue
            aligned, reason = claim_supports_field(
                field,
                (field_values or {}).get(field),
                evidence,
                mapping_is_inference=mapping_is_inference,
            )
            checks.append({
                "field": field,
                "evidence_id": evidence_id,
                "canonical_evidence_id": canonical_id,
                "aligned": aligned,
                "reason": reason,
            })
            if not aligned:
                rejections.append({
                    "field": field, "evidence_id": evidence_id, "reason": reason,
                })
                continue
            if canonical_id not in resolved_ids[field]:
                resolved_ids[field].append(canonical_id)
                resolved[field].append(deepcopy(evidence))
    return resolved, resolved_ids, checks, rejections


def field_boundaries(field_evidence, mapping_is_inference=False):
    return {
        field: evidence_boundary(
            (field_evidence or {}).get(field, []),
            is_inference=(mapping_is_inference and field in {
                "mechanism", "economic_exposure"
            }),
        )
        for field in FIELD_EVIDENCE_NAMES
    }


def _valid_catalyst_window(item, as_of_date=""):
    window = item.get("catalyst_window")
    if not isinstance(window, dict):
        return False
    checkpoint = parse_iso_date(window.get("expected_by"))
    if checkpoint is None:
        return False
    cutoff = parse_iso_date(as_of_date) if text(as_of_date) else None
    return cutoff is None or checkpoint >= cutoff


def evaluate_setup(item, as_of_date=""):
    """Return readiness without creating a lifecycle or investment score."""
    setup_types = [
        value for value in item.get("setup_types", []) if value in SETUP_REQUIREMENTS
    ]
    boundaries = field_boundaries(
        item.get("field_evidence", {}), item.get("mapping_is_inference") is True
    )
    # Text changing between rounds is usually refinement, not contradiction.
    # Only an explicit CHALLENGE delta creates a load-bearing field conflict.
    conflicts_by_field = item.get("field_conflicts", {}) if isinstance(
        item.get("field_conflicts"), dict
    ) else {}
    results = {}
    ready_types = []
    for setup_type in setup_types:
        requirements = SETUP_REQUIREMENTS[setup_type]
        missing_content = sorted(
            field for field in requirements["content"] if not known(item.get(field))
        )
        missing_evidence = sorted(
            field for field in requirements["evidence"]
            if boundaries.get(field) == "HYPOTHESIS"
        )
        conflicts = sorted(
            field for field in requirements["content"]
            if len(conflicts_by_field.get(field, [])) > 1
        )
        reasons = []
        if missing_content:
            reasons.append("MISSING_CONTENT")
        if missing_evidence:
            reasons.append("MISSING_FIELD_EVIDENCE")
        if conflicts:
            reasons.append("UNRESOLVED_FIELD_CONFLICT")
        if not _valid_catalyst_window(item, as_of_date):
            reasons.append("INVALID_OR_STALE_CATALYST_WINDOW")
        ready = not reasons
        if ready:
            ready_types.append(setup_type)
        results[setup_type] = {
            "ready": ready,
            "missing_content": missing_content,
            "missing_evidence": missing_evidence,
            "conflicting_fields": conflicts,
            "reason_codes": reasons or ["SETUP_EVIDENCE_COMPLETE"],
        }
    return {
        "attention_band": "SETUP_CANDIDATE" if ready_types else "EXPLORE",
        "ready_setup_types": ready_types,
        "setup_checks": results,
        "field_boundaries": boundaries,
    }
