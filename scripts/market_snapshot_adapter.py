#!/usr/bin/env python3
"""Build a frozen, provider-neutral market snapshot from observed series.

The adapter does not fetch data and does not guess a market calendar.  It turns
host-supplied, source-bound observations into reproducible relative-strength
metrics and a content-addressed receipt suitable for Candidate BridgeView.
"""
import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import sys
from urllib.parse import urlparse


SCHEMA_VERSION = "trade-nothing.market-snapshot-adapter.v1"
UPSTREAM_RECEIPT_SCHEMA = "trade-nothing.free-market-acquisition-receipt.v1"
UPSTREAM_PROVIDERS = {"TUSHARE", "BAOSTOCK", "AKSHARE_TENCENT", "CSV"}
WINDOWS = (5, 20, 60)
CURRENT_FUNDAMENTAL_FIELDS = (
    "provider_volume_ratio",
    "pe_ttm",
    "pb",
    "total_market_cap_cny",
    "float_market_cap_cny",
)


def _text(value):
    return " ".join(str(value or "").split())


def _parse_date(value):
    try:
        return date.fromisoformat(_text(value))
    except (TypeError, ValueError):
        return None


def _number(value, field, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field}_must_be_number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field}_must_be_finite")
    if positive and result <= 0:
        raise ValueError(f"{field}_must_be_positive")
    return result


def _source(series, label):
    if not isinstance(series, dict):
        raise ValueError(f"{label}_series_must_be_object")
    source_url = _text(series.get("source_url"))
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{label}_source_url_required")
    return {
        "name": _text(series.get("name")) or label,
        "ticker": _text(series.get("ticker")),
        "exchange": _text(series.get("exchange")),
        "source": _text(series.get("source")) or parsed.netloc,
        "source_class": _text(series.get("source_class")) or "UNSPECIFIED",
        "source_url": source_url,
    }


def _rows(series, cutoff, label):
    raw_rows = series.get("observations") if isinstance(series, dict) else None
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ValueError(f"{label}_observations_required")
    by_date = {}
    for raw in raw_rows:
        if not isinstance(raw, dict):
            raise ValueError(f"{label}_observation_must_be_object")
        session = _parse_date(raw.get("date"))
        if session is None:
            raise ValueError(f"{label}_observation_date_invalid")
        if session > cutoff:
            continue
        item = {
            "date": session.isoformat(),
            "close": _number(raw.get("close"), f"{label}_close", positive=True),
            "volume": None,
            "turnover_rate": None,
            **{field: None for field in CURRENT_FUNDAMENTAL_FIELDS},
        }
        if raw.get("volume") is not None:
            item["volume"] = _number(raw.get("volume"), f"{label}_volume")
        if raw.get("turnover_rate") is not None:
            item["turnover_rate"] = _number(
                raw.get("turnover_rate"), f"{label}_turnover_rate"
            )
        for field in CURRENT_FUNDAMENTAL_FIELDS:
            if raw.get(field) is not None:
                item[field] = _number(raw.get(field), f"{label}_{field}")
        by_date[item["date"]] = item
    rows = [by_date[key] for key in sorted(by_date)]
    if not rows:
        raise ValueError(f"{label}_no_observation_on_or_before_as_of")
    return rows


def _return(current, base):
    return round((current / base - 1.0) * 100.0, 6)


def _series_return(rows, window):
    if len(rows) <= window:
        return None, None
    current = rows[-1]
    base = rows[-window - 1]
    return _return(current["close"], base["close"]), base["date"]


def _benchmark_return_on_dates(rows, base_date, current_date):
    index = {item["date"]: item["close"] for item in rows}
    if base_date not in index or current_date not in index:
        return None
    return _return(index[current_date], index[base_date])


def _input_hash(packet):
    material = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _upstream_receipt_core(receipt):
    core_keys = (
        "schema_version", "request_sha256", "provider", "provider_version",
        "research_as_of_date", "market_session_date", "adjustment", "series_sha256",
    )
    core = {key: receipt.get(key) for key in core_keys}
    if receipt.get("raw_file_sha256") is not None:
        core["raw_file_sha256"] = receipt.get("raw_file_sha256")
    if receipt.get("provider_endpoints") is not None:
        core["provider_endpoints"] = receipt.get("provider_endpoints")
    return core


def _validate_upstream_receipt_envelope(receipt):
    if not isinstance(receipt, dict):
        raise ValueError("upstream_acquisition_receipt_required")
    if _text(receipt.get("schema_version")) != UPSTREAM_RECEIPT_SCHEMA:
        raise ValueError("upstream_acquisition_receipt_schema_invalid")
    if _text(receipt.get("provider")).upper() not in UPSTREAM_PROVIDERS:
        raise ValueError("upstream_acquisition_receipt_provider_invalid")
    receipt_id = _text(receipt.get("receipt_id"))
    if not _is_sha256(receipt_id):
        raise ValueError("upstream_acquisition_receipt_id_invalid")
    if _input_hash(_upstream_receipt_core(receipt)) != receipt_id:
        raise ValueError("upstream_acquisition_receipt_identity_mismatch")
    series_hashes = receipt.get("series_sha256")
    if not isinstance(series_hashes, dict) or not all(
        _is_sha256(_text(series_hashes.get(label)))
        for label in ("candidate", "benchmark")
    ):
        raise ValueError("upstream_acquisition_receipt_series_hash_invalid")
    return receipt_id


def _validate_upstream_receipt(packet, candidate_raw, benchmark_raw, session_date):
    receipt = packet.get("acquisition_receipt")
    if receipt is None:
        return None
    if not isinstance(receipt, dict):
        raise ValueError("acquisition_receipt_must_be_object")
    receipt_id = _text(receipt.get("receipt_id"))
    if not _is_sha256(receipt_id):
        raise ValueError("acquisition_receipt_id_invalid")
    expected_series = {
        "candidate": _input_hash(candidate_raw.get("observations")),
        "benchmark": _input_hash(benchmark_raw.get("observations")),
    }
    if receipt.get("series_sha256") != expected_series:
        raise ValueError("acquisition_receipt_series_hash_mismatch")
    if _text(receipt.get("market_session_date")) != session_date:
        raise ValueError("acquisition_receipt_session_mismatch")
    try:
        _validate_upstream_receipt_envelope(receipt)
    except ValueError as exc:
        raise ValueError(str(exc).replace("upstream_", "", 1)) from exc
    return receipt_id


def _is_sha256(value):
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def validate_snapshot_artifact(artifact, require_upstream_receipt=False):
    """Validate the adapter envelope and its content-addressed receipt.

    This proves adapter identity, not truth of the upstream observations.  A
    recommendation-authoritative consumer should additionally require the
    upstream acquisition receipt and bind evidence in its own run state.
    """
    if not isinstance(artifact, dict):
        raise ValueError("market_snapshot_artifact_must_be_object")
    if _text(artifact.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("market_snapshot_artifact_schema_invalid")
    candidate = artifact.get("candidate")
    snapshot = artifact.get("market_snapshot")
    if not isinstance(candidate, dict) or not isinstance(snapshot, dict):
        raise ValueError("market_snapshot_artifact_payload_required")
    receipt = snapshot.get("adapter_receipt")
    if not isinstance(receipt, dict):
        raise ValueError("market_snapshot_adapter_receipt_required")
    receipt_id = _text(receipt.get("receipt_id"))
    if not _is_sha256(receipt_id):
        raise ValueError("market_snapshot_adapter_receipt_id_invalid")
    receipt_core = {
        key: value for key, value in receipt.items() if key != "receipt_id"
    }
    if _input_hash(receipt_core) != receipt_id:
        raise ValueError("market_snapshot_adapter_receipt_identity_mismatch")
    if _text(receipt.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("market_snapshot_adapter_receipt_schema_invalid")
    if _text(receipt.get("market_session_date")) != _text(snapshot.get("as_of_date")):
        raise ValueError("market_snapshot_adapter_receipt_session_mismatch")
    if _text(receipt.get("candidate_source_url")) != _text(candidate.get("source_url")):
        raise ValueError("market_snapshot_adapter_receipt_candidate_source_mismatch")
    if _text(receipt.get("candidate_identity_sha256")) != _input_hash(candidate):
        raise ValueError("market_snapshot_adapter_candidate_identity_mismatch")
    snapshot_core = {
        key: value for key, value in snapshot.items() if key != "adapter_receipt"
    }
    if _text(receipt.get("market_snapshot_sha256")) != _input_hash(snapshot_core):
        raise ValueError("market_snapshot_adapter_snapshot_hash_mismatch")
    upstream = artifact.get("upstream_acquisition_receipt")
    upstream_id = ""
    if upstream is not None or require_upstream_receipt:
        upstream_id = _validate_upstream_receipt_envelope(upstream)
        if upstream_id != _text(receipt.get("upstream_acquisition_receipt_id")):
            raise ValueError("upstream_acquisition_receipt_binding_mismatch")
        if _text(upstream.get("market_session_date")) != _text(snapshot.get("as_of_date")):
            raise ValueError("upstream_acquisition_receipt_session_mismatch")
        if _text(upstream.get("research_as_of_date")) != _text(
            receipt.get("research_as_of_date")
        ):
            raise ValueError("upstream_acquisition_receipt_as_of_mismatch")
    return {
        "receipt_id": receipt_id,
        "upstream_acquisition_receipt_id": upstream_id,
        "market_session_date": _text(receipt.get("market_session_date")),
    }


def build_snapshot(packet):
    if not isinstance(packet, dict):
        raise ValueError("packet_must_be_object")
    as_of_text = _text(packet.get("as_of_date"))
    cutoff = _parse_date(as_of_text)
    if cutoff is None:
        raise ValueError("as_of_date_invalid")
    candidate_raw = packet.get("candidate")
    benchmark_raw = packet.get("benchmark")
    candidate_source = _source(candidate_raw, "candidate")
    benchmark_source = _source(benchmark_raw, "benchmark")
    candidate_rows = _rows(candidate_raw, cutoff, "candidate")
    benchmark_rows = _rows(benchmark_raw, cutoff, "benchmark")
    session_date = candidate_rows[-1]["date"]
    if benchmark_rows[-1]["date"] != session_date:
        raise ValueError("candidate_benchmark_latest_session_mismatch")
    upstream_receipt_id = _validate_upstream_receipt(
        packet, candidate_raw, benchmark_raw, session_date
    )

    metrics = {}
    for window in WINDOWS:
        candidate_return, base_date = _series_return(candidate_rows, window)
        benchmark_return = (
            _benchmark_return_on_dates(benchmark_rows, base_date, session_date)
            if base_date else None
        )
        metrics[f"return_{window}d"] = candidate_return
        metrics[f"excess_{window}d"] = (
            round(candidate_return - benchmark_return, 6)
            if candidate_return is not None and benchmark_return is not None else None
        )

    if len(candidate_rows) > 60:
        current = candidate_rows[-1]["close"]
        high = max(item["close"] for item in candidate_rows[-61:])
        metrics["drawdown_60d"] = round((current / high - 1.0) * 100.0, 6)
    else:
        metrics["drawdown_60d"] = None

    prior_volumes = [
        item["volume"] for item in candidate_rows[-21:-1]
        if item.get("volume") is not None
    ] if len(candidate_rows) > 20 else []
    current_volume = candidate_rows[-1].get("volume")
    if len(prior_volumes) == 20 and current_volume is not None:
        average = sum(prior_volumes) / len(prior_volumes)
        metrics["volume_ratio_20d"] = (
            round(current_volume / average, 6) if average > 0 else None
        )
    else:
        metrics["volume_ratio_20d"] = None
    metrics["turnover_rate"] = candidate_rows[-1].get("turnover_rate")
    for field in CURRENT_FUNDAMENTAL_FIELDS:
        metrics[field] = candidate_rows[-1].get(field)

    theme = packet.get("theme_basket")
    theme_name = "UNKNOWN"
    theme_source = None
    if isinstance(theme, dict):
        theme_source = _source(theme, "theme_basket")
        theme_rows = _rows(theme, cutoff, "theme_basket")
        if theme_rows[-1]["date"] != session_date:
            raise ValueError("candidate_theme_latest_session_mismatch")
        theme_name = theme_source["name"]

    snapshot_core = {
        "as_of_date": session_date,
        "benchmark": benchmark_source["name"],
        "theme_basket": theme_name,
        "latest_observed_session_on_or_before_as_of": True,
        **metrics,
    }
    receipt_core = {
        "schema_version": SCHEMA_VERSION,
        "input_sha256": _input_hash(packet),
        "market_snapshot_sha256": _input_hash(snapshot_core),
        "candidate_identity_sha256": _input_hash(candidate_source),
        "research_as_of_date": as_of_text,
        "market_session_date": session_date,
        "candidate_observation_count": len(candidate_rows),
        "benchmark_observation_count": len(benchmark_rows),
        "candidate_source_url": candidate_source["source_url"],
        "benchmark_source_url": benchmark_source["source_url"],
    }
    if upstream_receipt_id:
        receipt_core["upstream_acquisition_receipt_id"] = upstream_receipt_id
    receipt_core["receipt_id"] = _input_hash(receipt_core)
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate": candidate_source,
        "market_snapshot": {
            **snapshot_core,
            "adapter_receipt": receipt_core,
        },
        "sources": [
            candidate_source,
            benchmark_source,
            *([theme_source] if theme_source else []),
        ],
        "upstream_acquisition_receipt": (
            dict(packet.get("acquisition_receipt"))
            if isinstance(packet.get("acquisition_receipt"), dict) else None
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    packet = json.loads(Path(args.input).read_text(encoding="utf-8"))
    try:
        result = build_snapshot(packet)
    except ValueError as exc:
        print(json.dumps({
            "status": "market_snapshot_rejected",
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
