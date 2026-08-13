#!/usr/bin/env python3
"""Convert one receipt-bound market snapshot into a research host-input fragment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import market_snapshot_adapter
import research_core


SCHEMA_VERSION = "trade-nothing.research-market-input.v1"


def _metric_payload(snapshot):
    fields = (
        "return_5d", "return_20d", "return_60d",
        "excess_5d", "excess_20d", "excess_60d", "drawdown_60d",
        "volume_ratio_20d", "turnover_rate", "provider_volume_ratio",
        "pe_ttm", "pb", "total_market_cap_cny", "float_market_cap_cny",
    )
    return {
        field: snapshot.get(field) for field in fields
        if snapshot.get(field) is not None
    }


def _typed_measures(snapshot, session_date, security_id):
    unit_by_metric = {
        "return_5d": "PERCENT", "return_20d": "PERCENT",
        "return_60d": "PERCENT", "excess_5d": "PERCENT",
        "excess_20d": "PERCENT", "excess_60d": "PERCENT",
        "drawdown_60d": "PERCENT", "turnover_rate": "PERCENT",
        "volume_ratio_20d": "RATIO", "provider_volume_ratio": "RATIO",
        "pe_ttm": "RATIO", "pb": "RATIO", "total_market_cap_cny": "CNY",
        "float_market_cap_cny": "CNY",
    }
    dimension_by_unit = research_core.MEASURE_UNIT_DIMENSIONS
    period_by_metric = {
        **{field: "5D" for field in ("return_5d", "excess_5d")},
        **{field: "20D" for field in ("return_20d", "excess_20d", "volume_ratio_20d")},
        **{field: "60D" for field in ("return_60d", "excess_60d", "drawdown_60d")},
        "turnover_rate": "SESSION",
    }
    basis_by_metric = {
        **{field: "CALCULATED_PRICE_RETURN" for field in (
            "return_5d", "return_20d", "return_60d",
        )},
        **{field: "CALCULATED_BENCHMARK_EXCESS" for field in (
            "excess_5d", "excess_20d", "excess_60d",
        )},
        "drawdown_60d": "CALCULATED_PRICE_DRAWDOWN",
        "volume_ratio_20d": "CALCULATED_VOLUME_RATIO",
    }
    return [
        {
            "measure_id": research_core.stable_id(
                "MEASURE", security_id, metric, session_date
            ),
            "metric": metric,
            "value": value,
            "unit": unit_by_metric[metric],
            "dimension": dimension_by_unit[unit_by_metric[metric]],
            "subject_id": security_id,
            "as_of": session_date,
            "period": period_by_metric.get(metric, "POINT_IN_TIME"),
            "basis": basis_by_metric.get(metric, "PROVIDER_REPORTED"),
        }
        for metric, value in _metric_payload(snapshot).items()
    ]


def build_fragment(artifact, *, entity_id, claim_ids=None,
                   decision_impact="MEDIUM"):
    """Build canonical EvidenceItem/SourceCheck input without semantic scoring."""
    validation = market_snapshot_adapter.validate_snapshot_artifact(
        artifact, require_upstream_receipt=True
    )
    candidate = artifact["candidate"]
    snapshot = artifact["market_snapshot"]
    ticker = research_core.text(candidate.get("ticker")).upper()
    exchange = research_core.normalize_exchange(candidate.get("exchange"))
    security_id = research_core.normalize_security_id(f"{ticker}@{exchange}")
    if not research_core.SECURITY_ID_RE.fullmatch(security_id):
        raise ValueError("candidate_security_identity_invalid")
    if not research_core.text(entity_id):
        raise ValueError("entity_id_required")
    claim_ids = research_core._unique_text(
        claim_ids or ["MV-MARKET-1"], limit=12
    )
    if not claim_ids:
        raise ValueError("claim_ids_required")
    impact = research_core._enum(
        decision_impact, research_core.DECISION_IMPACTS
    )
    if not impact:
        raise ValueError("decision_impact_invalid")

    session_date = research_core.text(snapshot.get("as_of_date"))
    source_url = research_core.text(candidate.get("source_url"))
    if not research_core.concrete_url(source_url):
        raise ValueError("candidate_source_url_not_concrete")
    adapter_receipt_id = validation["receipt_id"]
    upstream_receipt_id = validation["upstream_acquisition_receipt_id"]
    measures = _typed_measures(snapshot, session_date, security_id)
    evidence_id = research_core.stable_id(
        "EV", "MARKET", security_id, session_date, adapter_receipt_id
    )
    source_check_id = research_core.stable_id(
        "SC", "MARKET", security_id, session_date, upstream_receipt_id
    )
    input_id = research_core.stable_id(
        "HOST", "MARKET", security_id, adapter_receipt_id
    )
    upstream = artifact.get("upstream_acquisition_receipt") or {}
    queries = research_core._unique_text(
        upstream.get("provider_endpoints", []), limit=12
    ) or [source_url]
    evidence = {
        "evidence_id": evidence_id,
        "claim": (
            f"截至 {session_date}，{research_core.text(candidate.get('name')) or ticker}"
            f"相对 {research_core.text(snapshot.get('benchmark')) or '固定基准'} 的"
            "冻结行情、相对收益、成交与可得估值字段如下；这些数值不自动构成强势判断或推荐。"
        ),
        "number": None,
        "measures": measures,
        "roles": ["MARKET_STATE", "TECHNICAL_STATE"],
        "source": (
            f"{research_core.text(candidate.get('source'))} via "
            "Trade Nothing market snapshot adapter"
        ),
        "url": source_url,
        "date": session_date,
        "source_tier": "STRUCTURED_MARKET_DATA",
        "boundary": "SINGLE_SOURCE",
        "decision_impact": impact,
        "entity_ids": [research_core.text(entity_id)],
        "security_ids": [security_id],
        "fact_surface": "MARKET_PRICE_LIQUIDITY",
        "claim_ids": claim_ids,
    }
    source_check = {
        "source_check_id": source_check_id,
        "entity_id": research_core.text(entity_id),
        "security_id": security_id,
        "fact_surface": "MARKET_PRICE_LIQUIDITY",
        "window_start": session_date,
        "window_end": session_date,
        "window_basis": "",
        "latest_periodic_report_date": "",
        "index_item_count": 0,
        "index_entries": [],
        "queries": queries,
        "official_index_url": "",
        "checked_document_urls": [source_url],
        "acquisition_receipt_ids": [
            upstream_receipt_id, adapter_receipt_id,
        ],
        "enumeration_complete": False,
        "outcome": "FOUND",
        "evidence_ids": [evidence_id],
        "negative_scope": "",
        "limitation": (
            "Host-frozen structured market observation; upstream truth is bounded "
            "by the named provider and receipts, and market strength remains a Lead judgment."
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "input_id": input_id,
        "evidence_items": [evidence],
        "source_checks": [source_check],
        "market_receipts": {
            "upstream_acquisition_receipt_id": upstream_receipt_id,
            "adapter_receipt_id": adapter_receipt_id,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--entity-id", required=True)
    parser.add_argument("--claim-id", action="append", default=[])
    parser.add_argument(
        "--decision-impact", default="MEDIUM",
        choices=sorted(research_core.DECISION_IMPACTS),
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)
    artifact = json.loads(Path(args.input).read_text(encoding="utf-8"))
    try:
        result = build_fragment(
            artifact, entity_id=args.entity_id,
            claim_ids=args.claim_id or None,
            decision_impact=args.decision_impact,
        )
    except (ValueError, research_core.ResearchContractError) as exc:
        print(json.dumps({
            "status": "research_market_input_rejected",
            "reason": str(exc),
        }, ensure_ascii=False, indent=2))
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
