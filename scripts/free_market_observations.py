#!/usr/bin/env python3
"""Collect a narrow, frozen A-share observation packet from one selected source.

This adapter deliberately does not scan the full market, choose a fallback, or
admit evidence.  The caller selects exactly one provider for a bounded request.
The output is compatible with ``market_snapshot_adapter.py`` and carries a
content-addressed acquisition receipt.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import importlib
from importlib import metadata
import io
import json
import multiprocessing
import os
from pathlib import Path
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from urllib.parse import urlparse


SCHEMA_VERSION = "trade-nothing.free-market-observations.v1"
RECEIPT_SCHEMA = "trade-nothing.free-market-acquisition-receipt.v1"
SUPPORTED_PROVIDERS = frozenset({"TUSHARE", "BAOSTOCK", "AKSHARE_TENCENT", "CSV"})
SUPPORTED_EXCHANGES = frozenset({"XSHG", "XSHE"})
SUPPORTED_ASSET_TYPES = frozenset({"EQUITY", "INDEX"})
MIN_LOOKBACK_DAYS = 90
MAX_LOOKBACK_DAYS = 730


class AcquisitionError(ValueError):
    """Bounded acquisition failure with a machine-readable status."""

    def __init__(self, status, reason):
        super().__init__(reason)
        self.status = status
        self.reason = reason


def _text(value):
    return " ".join(str(value or "").split())


def _canonical_hash(value):
    material = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _iso_date(value, field):
    text = _text(value)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise AcquisitionError("REQUEST_REJECTED", f"{field}_invalid") from exc


def _number(value, *, positive=False):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    if text.endswith("%"):
        text = text[:-1]
    if not text or text.lower() in {"nan", "none", "null", "--"}:
        return None
    try:
        result = float(text)
    except (TypeError, ValueError):
        return None
    if positive and result <= 0:
        return None
    return result


def _valid_url(value, field):
    text = _text(value)
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AcquisitionError("REQUEST_REJECTED", f"{field}_source_url_required")
    return text


def _asset(raw, label, provider):
    if not isinstance(raw, dict):
        raise AcquisitionError("REQUEST_REJECTED", f"{label}_must_be_object")
    ticker = _text(raw.get("ticker"))
    exchange = _text(raw.get("exchange")).upper()
    asset_type = _text(raw.get("asset_type")).upper()
    if not re.fullmatch(r"\d{6}", ticker):
        raise AcquisitionError("REQUEST_REJECTED", f"{label}_ticker_must_be_six_digits")
    if exchange not in SUPPORTED_EXCHANGES:
        raise AcquisitionError("REQUEST_REJECTED", f"{label}_exchange_unsupported")
    if asset_type not in SUPPORTED_ASSET_TYPES:
        raise AcquisitionError("REQUEST_REJECTED", f"{label}_asset_type_unsupported")
    result = {
        "name": _text(raw.get("name")) or ticker,
        "ticker": ticker,
        "exchange": exchange,
        "asset_type": asset_type,
    }
    if provider == "CSV":
        csv_path = _text(raw.get("csv_path"))
        if not csv_path:
            raise AcquisitionError("REQUEST_REJECTED", f"{label}_csv_path_required")
        result["csv_path"] = csv_path
        result["source_url"] = _valid_url(raw.get("source_url"), label)
        result["source"] = _text(raw.get("source")) or "MANUAL_CSV"
        result["source_class"] = _text(raw.get("source_class")) or "SECONDARY_MARKET_DATA"
    return result


def _request(raw):
    if not isinstance(raw, dict):
        raise AcquisitionError("REQUEST_REJECTED", "request_must_be_object")
    provider = _text(raw.get("provider")).upper()
    if provider not in SUPPORTED_PROVIDERS:
        raise AcquisitionError("REQUEST_REJECTED", "provider_must_be_explicit")
    as_of = _iso_date(raw.get("as_of_date"), "as_of_date")
    lookback = raw.get("lookback_calendar_days", 180)
    if isinstance(lookback, bool) or not isinstance(lookback, int):
        raise AcquisitionError("REQUEST_REJECTED", "lookback_calendar_days_must_be_integer")
    if not MIN_LOOKBACK_DAYS <= lookback <= MAX_LOOKBACK_DAYS:
        raise AcquisitionError("REQUEST_REJECTED", "lookback_calendar_days_out_of_range")
    return {
        "schema_version": SCHEMA_VERSION,
        "as_of_date": as_of.isoformat(),
        "lookback_calendar_days": lookback,
        "provider": provider,
        "adjustment": "QFQ_AS_OF_CUTOFF" if provider == "TUSHARE" else "NONE",
        "candidate": _asset(raw.get("candidate"), "candidate", provider),
        "benchmark": _asset(raw.get("benchmark"), "benchmark", provider),
    }


def _provider_code(asset, dotted=False):
    prefix = "sh" if asset["exchange"] == "XSHG" else "sz"
    separator = "." if dotted else ""
    return f"{prefix}{separator}{asset['ticker']}"


def _tushare_code(asset):
    suffix = "SH" if asset["exchange"] == "XSHG" else "SZ"
    return f"{asset['ticker']}.{suffix}"


def _normalize_records(records, *, cutoff, start, label):
    aliases = {
        "date": ("date", "日期", "trade_date"),
        "close": ("close", "收盘", "收盘价"),
        "volume": ("volume", "成交量", "vol"),
        "turnover_rate": ("turnover_rate", "换手率", "turn"),
        "provider_volume_ratio": ("provider_volume_ratio", "volume_ratio"),
        "pe_ttm": ("pe_ttm",),
        "pb": ("pb",),
        "total_market_cap_cny": ("total_market_cap_cny",),
        "float_market_cap_cny": ("float_market_cap_cny",),
    }

    def value(record, field):
        for key in aliases[field]:
            if key in record:
                return record.get(key)
        return None

    by_date = {}
    for raw in records:
        if not isinstance(raw, dict):
            raise AcquisitionError("SOURCE_INVALID", f"{label}_row_must_be_object")
        raw_date = value(raw, "date")
        if hasattr(raw_date, "isoformat"):
            raw_date = raw_date.isoformat()
        raw_date = _text(raw_date)[:10]
        if re.fullmatch(r"\d{8}", raw_date):
            raw_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        try:
            session = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise AcquisitionError("SOURCE_INVALID", f"{label}_row_date_invalid") from exc
        if session < start or session > cutoff:
            continue
        session_text = session.isoformat()
        if session_text in by_date:
            raise AcquisitionError("SOURCE_INVALID", f"{label}_duplicate_session:{session_text}")
        close = _number(value(raw, "close"), positive=True)
        if close is None:
            raise AcquisitionError("SOURCE_INVALID", f"{label}_close_invalid:{session_text}")
        item = {"date": session_text, "close": close}
        volume = _number(value(raw, "volume"))
        turnover = _number(value(raw, "turnover_rate"))
        if volume is not None:
            item["volume"] = volume
        if turnover is not None:
            item["turnover_rate"] = turnover
        for field in (
            "provider_volume_ratio",
            "pe_ttm",
            "pb",
            "total_market_cap_cny",
            "float_market_cap_cny",
        ):
            numeric = _number(value(raw, field))
            if numeric is not None:
                item[field] = numeric
        by_date[session_text] = item
    observations = [by_date[key] for key in sorted(by_date)]
    if not observations:
        raise AcquisitionError("SOURCE_EMPTY", f"{label}_no_rows_in_requested_window")
    return observations


def _optional_import(name):
    try:
        return importlib.import_module(name)
    except (ImportError, ModuleNotFoundError) as exc:
        raise AcquisitionError("PROVIDER_UNAVAILABLE", f"optional_dependency_missing:{name}") from exc


def _package_version(name, module):
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return _text(getattr(module, "__version__", "")) or "UNKNOWN"


def _read_csv(asset):
    path = Path(asset["csv_path"]).expanduser()
    if not path.is_file():
        raise AcquisitionError("SOURCE_UNAVAILABLE", f"csv_not_found:{path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
            except csv.Error:
                dialect = csv.excel
            rows = list(csv.DictReader(handle, dialect=dialect))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise AcquisitionError("SOURCE_UNAVAILABLE", f"csv_read_failed:{path}") from exc
    return rows, _file_hash(path)


def _collect_csv(request, cutoff, start):
    series = {}
    raw_hashes = {}
    for label in ("candidate", "benchmark"):
        asset = request[label]
        records, raw_hash = _read_csv(asset)
        observations = _normalize_records(
            records, cutoff=cutoff, start=start, label=label
        )
        series[label] = {
            "name": asset["name"],
            "ticker": asset["ticker"],
            "exchange": asset["exchange"],
            "source": asset["source"],
            "source_class": asset["source_class"],
            "source_url": asset["source_url"],
            "observations": observations,
        }
        raw_hashes[label] = raw_hash
    return series, {"provider_version": "stdlib-csv", "raw_file_sha256": raw_hashes}


def _baostock_worker(connection, request, cutoff_text, start_text):
    output = io.StringIO()
    try:
        with redirect_stdout(output), redirect_stderr(output):
            series, meta = _collect_baostock_session(
                request, date.fromisoformat(cutoff_text), date.fromisoformat(start_text)
            )
        connection.send({"ok": True, "series": series, "meta": meta})
    except AcquisitionError as exc:
        connection.send({"ok": False, "status": exc.status, "reason": exc.reason})
    except Exception as exc:
        connection.send({
            "ok": False,
            "status": "SOURCE_UNAVAILABLE",
            "reason": f"baostock_worker_failed:{type(exc).__name__}",
        })
    finally:
        connection.close()


def _baostock_context():
    methods = multiprocessing.get_all_start_methods()
    return multiprocessing.get_context("fork" if "fork" in methods else "spawn")


def _collect_baostock(request, cutoff, start, *, timeout_seconds=20.0, context=None):
    # BaoStock 0.8.9 has no total request timeout and can keep receiving partial
    # frames forever. Isolate it so the host has a real wall-clock boundary.
    ctx = context or _baostock_context()
    parent, child = ctx.Pipe(duplex=False)
    process = ctx.Process(
        target=_baostock_worker,
        args=(child, request, cutoff.isoformat(), start.isoformat()),
    )
    process.daemon = True
    process.start()
    child.close()
    try:
        if not parent.poll(timeout_seconds):
            process.terminate()
            process.join(2.0)
            if process.is_alive() and hasattr(process, "kill"):
                process.kill()
                process.join(1.0)
            raise AcquisitionError("SOURCE_TIMEOUT", "baostock_wall_clock_timeout")
        try:
            payload = parent.recv()
        except EOFError as exc:
            raise AcquisitionError("SOURCE_UNAVAILABLE", "baostock_worker_closed") from exc
    finally:
        parent.close()
    process.join(1.0)
    if process.is_alive():
        process.terminate()
        process.join(1.0)
    if not payload.get("ok"):
        raise AcquisitionError(payload.get("status"), payload.get("reason"))
    return payload["series"], payload["meta"]


def _collect_baostock_session(request, cutoff, start):
    bs = _optional_import("baostock")
    login = bs.login()
    if _text(getattr(login, "error_code", "")) != "0":
        raise AcquisitionError(
            "SOURCE_UNAVAILABLE", f"baostock_login_failed:{_text(getattr(login, 'error_msg', ''))}"
        )
    series = {}
    try:
        for label in ("candidate", "benchmark"):
            asset = request[label]
            fields = "date,code,close,volume,amount"
            if asset["asset_type"] == "EQUITY":
                fields += ",turn"
            result = bs.query_history_k_data_plus(
                _provider_code(asset, dotted=True),
                fields,
                start_date=start.isoformat(),
                end_date=cutoff.isoformat(),
                frequency="d",
                adjustflag="3",
            )
            if _text(getattr(result, "error_code", "")) != "0":
                raise AcquisitionError(
                    "SOURCE_UNAVAILABLE",
                    f"baostock_query_failed:{label}:{_text(getattr(result, 'error_msg', ''))}",
                )
            rows = []
            field_names = list(getattr(result, "fields", []))
            while result.next():
                rows.append(dict(zip(field_names, result.get_row_data())))
            observations = _normalize_records(rows, cutoff=cutoff, start=start, label=label)
            series[label] = {
                "name": asset["name"],
                "ticker": asset["ticker"],
                "exchange": asset["exchange"],
                "source": "BaoStock",
                "source_class": "SECONDARY_MARKET_DATA",
                "source_url": "https://www.baostock.com/",
                "observations": observations,
            }
    except AcquisitionError:
        raise
    except Exception as exc:
        raise AcquisitionError("SOURCE_UNAVAILABLE", f"baostock_request_failed:{type(exc).__name__}") from exc
    finally:
        try:
            bs.logout()
        except Exception:
            pass
    return series, {"provider_version": _package_version("baostock", bs)}


def _collect_akshare_tencent(request, cutoff, start):
    ak = _optional_import("akshare")
    series = {}
    try:
        for label in ("candidate", "benchmark"):
            asset = request[label]
            code = _provider_code(asset)
            # The Tencent history endpoint accepts both equities and indices.
            # Do not use stock_zh_index_daily_tx here: it fetches every year
            # since inception and would violate this adapter's bounded window.
            frame = ak.stock_zh_a_hist_tx(
                symbol=code,
                start_date=start.strftime("%Y%m%d"),
                end_date=cutoff.strftime("%Y%m%d"),
                adjust="",
                timeout=10.0,
            )
            records = frame.to_dict(orient="records")
            observations = _normalize_records(
                records, cutoff=cutoff, start=start, label=label
            )
            series[label] = {
                "name": asset["name"],
                "ticker": asset["ticker"],
                "exchange": asset["exchange"],
                "source": "AKShare/Tencent",
                "source_class": "SECONDARY_AGGREGATOR",
                "source_url": f"https://gu.qq.com/{code}/zs",
                "observations": observations,
            }
    except AcquisitionError:
        raise
    except Exception as exc:
        raise AcquisitionError(
            "SOURCE_UNAVAILABLE", f"akshare_tencent_request_failed:{type(exc).__name__}"
        ) from exc
    return series, {"provider_version": _package_version("akshare", ak)}


def _tushare_query(pro, api_name, **kwargs):
    try:
        frame = pro.query(api_name, **kwargs)
    except Exception as exc:
        message = _text(exc).lower()
        if any(marker in message for marker in ("权限", "积分", "permission")):
            raise AcquisitionError(
                "PROVIDER_PERMISSION_DENIED", f"tushare_permission_denied:{api_name}"
            ) from exc
        raise AcquisitionError(
            "SOURCE_UNAVAILABLE", f"tushare_request_failed:{api_name}:{type(exc).__name__}"
        ) from exc
    if frame is None or not hasattr(frame, "to_dict"):
        raise AcquisitionError("SOURCE_INVALID", f"tushare_frame_invalid:{api_name}")
    return frame.to_dict(orient="records")


def _collect_tushare(request, cutoff, start):
    token = _text(os.environ.get("TUSHARE_TOKEN"))
    if not token:
        raise AcquisitionError("CREDENTIAL_MISSING", "tushare_token_missing")
    ts = _optional_import("tushare")
    try:
        pro = ts.pro_api(token, timeout=15)
    except Exception as exc:
        raise AcquisitionError(
            "PROVIDER_UNAVAILABLE", f"tushare_client_failed:{type(exc).__name__}"
        ) from exc

    start_text = start.strftime("%Y%m%d")
    cutoff_text = cutoff.strftime("%Y%m%d")
    series = {}
    endpoints = set()
    for label in ("candidate", "benchmark"):
        asset = request[label]
        code = _tushare_code(asset)
        if asset["asset_type"] == "INDEX":
            endpoints.add("index_daily")
            rows = _tushare_query(
                pro,
                "index_daily",
                ts_code=code,
                start_date=start_text,
                end_date=cutoff_text,
                fields="ts_code,trade_date,close,vol",
            )
            source_url = "https://tushare.pro/document/2?doc_id=95"
        else:
            endpoints.update(("daily", "adj_factor", "daily_basic"))
            daily = _tushare_query(
                pro,
                "daily",
                ts_code=code,
                start_date=start_text,
                end_date=cutoff_text,
                fields="ts_code,trade_date,close,vol",
            )
            factors = _tushare_query(
                pro,
                "adj_factor",
                ts_code=code,
                start_date=start_text,
                end_date=cutoff_text,
                fields="ts_code,trade_date,adj_factor",
            )
            basics = _tushare_query(
                pro,
                "daily_basic",
                ts_code=code,
                start_date=start_text,
                end_date=cutoff_text,
                fields=(
                    "ts_code,trade_date,turnover_rate,volume_ratio,pe_ttm,pb,"
                    "total_mv,circ_mv"
                ),
            )
            factor_by_date = {
                _text(row.get("trade_date")): _number(row.get("adj_factor"), positive=True)
                for row in factors if isinstance(row, dict)
            }
            valid_factors = [value for value in factor_by_date.values() if value is not None]
            if not valid_factors:
                raise AcquisitionError("SOURCE_INVALID", f"{label}_tushare_adj_factor_missing")
            latest_factor = factor_by_date.get(max(factor_by_date))
            if latest_factor is None:
                raise AcquisitionError("SOURCE_INVALID", f"{label}_tushare_latest_adj_factor_missing")
            basic_by_date = {
                _text(row.get("trade_date")): row
                for row in basics if isinstance(row, dict)
            }
            rows = []
            for raw in daily:
                if not isinstance(raw, dict):
                    raise AcquisitionError("SOURCE_INVALID", f"{label}_tushare_daily_row_invalid")
                trade_date = _text(raw.get("trade_date"))
                close = _number(raw.get("close"), positive=True)
                factor = factor_by_date.get(trade_date)
                if close is None or factor is None:
                    raise AcquisitionError(
                        "SOURCE_INVALID", f"{label}_tushare_adjustment_incomplete:{trade_date}"
                    )
                basic = basic_by_date.get(trade_date, {})
                total_mv = _number(basic.get("total_mv"))
                circ_mv = _number(basic.get("circ_mv"))
                rows.append({
                    "trade_date": trade_date,
                    "close": close * factor / latest_factor,
                    "vol": raw.get("vol"),
                    "turnover_rate": basic.get("turnover_rate"),
                    "provider_volume_ratio": basic.get("volume_ratio"),
                    "pe_ttm": basic.get("pe_ttm"),
                    "pb": basic.get("pb"),
                    "total_market_cap_cny": (
                        total_mv * 10000.0 if total_mv is not None else None
                    ),
                    "float_market_cap_cny": (
                        circ_mv * 10000.0 if circ_mv is not None else None
                    ),
                })
            source_url = "https://tushare.pro/document/2?doc_id=27"

        observations = _normalize_records(rows, cutoff=cutoff, start=start, label=label)
        series[label] = {
            "name": asset["name"],
            "ticker": asset["ticker"],
            "exchange": asset["exchange"],
            "source": "Tushare Pro",
            "source_class": "STRUCTURED_MARKET_DATA",
            "source_url": source_url,
            "observations": observations,
        }
    return series, {
        "provider_version": _package_version("tushare", ts),
        "provider_endpoints": sorted(endpoints),
    }


def collect(raw_request, *, now=None):
    request = _request(raw_request)
    cutoff = date.fromisoformat(request["as_of_date"])
    start = cutoff - timedelta(days=request["lookback_calendar_days"])
    provider = request["provider"]
    collectors = {
        "CSV": _collect_csv,
        "TUSHARE": _collect_tushare,
        "BAOSTOCK": _collect_baostock,
        "AKSHARE_TENCENT": _collect_akshare_tencent,
    }
    series, provider_meta = collectors[provider](request, cutoff, start)
    candidate_session = series["candidate"]["observations"][-1]["date"]
    benchmark_session = series["benchmark"]["observations"][-1]["date"]
    if candidate_session != benchmark_session:
        raise AcquisitionError(
            "SESSION_MISMATCH",
            f"candidate_benchmark_latest_session_mismatch:{candidate_session}:{benchmark_session}",
        )

    series_hashes = {
        label: _canonical_hash(series[label]["observations"])
        for label in ("candidate", "benchmark")
    }
    receipt_core = {
        "schema_version": RECEIPT_SCHEMA,
        "request_sha256": _canonical_hash(request),
        "provider": provider,
        "provider_version": provider_meta.get("provider_version", "UNKNOWN"),
        "research_as_of_date": request["as_of_date"],
        "market_session_date": candidate_session,
        "adjustment": request["adjustment"],
        "series_sha256": series_hashes,
    }
    if provider_meta.get("raw_file_sha256"):
        receipt_core["raw_file_sha256"] = provider_meta["raw_file_sha256"]
    if provider_meta.get("provider_endpoints"):
        receipt_core["provider_endpoints"] = provider_meta["provider_endpoints"]
    receipt_id = _canonical_hash(receipt_core)
    observed_at = now or datetime.now(timezone.utc)
    warnings = []
    for label in ("candidate", "benchmark"):
        count = len(series[label]["observations"])
        if count <= 60:
            warnings.append(f"{label}_insufficient_60_session_history:{count}")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "OBSERVATIONS_READY",
        "as_of_date": request["as_of_date"],
        "provider": provider,
        "adjustment": request["adjustment"],
        "candidate": series["candidate"],
        "benchmark": series["benchmark"],
        "acquisition_receipt": {
            **receipt_core,
            "receipt_id": receipt_id,
            "fetched_at": observed_at.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
            "attempted_providers": [provider],
            "fallback_attempted": False,
            "warnings": warnings,
        },
    }


def _render(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="bounded acquisition request JSON")
    parser.add_argument("--output", help="observation packet or failure receipt JSON")
    args = parser.parse_args(argv)
    try:
        raw_request = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = collect(raw_request)
        exit_code = 0
    except (OSError, json.JSONDecodeError) as exc:
        result = {"schema_version": SCHEMA_VERSION, "status": "REQUEST_REJECTED", "reason": type(exc).__name__}
        exit_code = 2
    except AcquisitionError as exc:
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": exc.status,
            "reason": exc.reason,
            "fallback_attempted": False,
        }
        exit_code = 2
    rendered = _render(result)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
