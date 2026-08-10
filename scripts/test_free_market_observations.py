#!/usr/bin/env python3
"""Offline tests for the narrow free-market observation adapter."""
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import free_market_observations
import market_snapshot_adapter


class FreeMarketObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write_series(self, name, *, end=70):
        path = self.root / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["date", "close", "volume", "turnover_rate"]
            )
            writer.writeheader()
            for index in range(end):
                month = 1 + index // 28
                day = 1 + index % 28
                writer.writerow({
                    "date": f"2026-{month:02d}-{day:02d}",
                    "close": 100 + index,
                    "volume": 1000 + index,
                    "turnover_rate": 2 + index / 100,
                })
        return path

    def request(self):
        return {
            "as_of_date": "2026-03-14",
            "lookback_calendar_days": 180,
            "provider": "CSV",
            "candidate": {
                "name": "甲公司",
                "ticker": "600001",
                "exchange": "XSHG",
                "asset_type": "EQUITY",
                "csv_path": str(self.write_series("candidate.csv")),
                "source": "broker export",
                "source_url": "https://market.example/candidate",
            },
            "benchmark": {
                "name": "沪深300",
                "ticker": "000300",
                "exchange": "XSHG",
                "asset_type": "INDEX",
                "csv_path": str(self.write_series("benchmark.csv")),
                "source": "broker export",
                "source_url": "https://market.example/benchmark",
            },
            "evidence_ids": ["EV-PRICE", "EV-CROWDING"],
        }

    def test_csv_vertical_slice_feeds_market_snapshot(self):
        packet = free_market_observations.collect(self.request())
        self.assertEqual(packet["status"], "OBSERVATIONS_READY")
        self.assertEqual(packet["acquisition_receipt"]["attempted_providers"], ["CSV"])
        snapshot = market_snapshot_adapter.build_snapshot(packet)["market_snapshot"]
        self.assertEqual(snapshot["as_of_date"], "2026-03-14")
        self.assertIsNotNone(snapshot["return_60d"])
        self.assertEqual(len(packet["acquisition_receipt"]["receipt_id"]), 64)
        self.assertEqual(
            snapshot["adapter_receipt"]["upstream_acquisition_receipt_id"],
            packet["acquisition_receipt"]["receipt_id"],
        )

    def test_snapshot_rejects_post_acquisition_tampering(self):
        packet = free_market_observations.collect(self.request())
        packet["candidate"]["observations"][-1]["close"] += 1
        with self.assertRaisesRegex(ValueError, "acquisition_receipt_series_hash_mismatch"):
            market_snapshot_adapter.build_snapshot(packet)

    def test_receipt_identity_excludes_wall_clock(self):
        request = self.request()
        first = free_market_observations.collect(
            request, now=datetime(2026, 3, 15, tzinfo=timezone.utc)
        )
        second = free_market_observations.collect(
            request, now=datetime(2026, 3, 16, tzinfo=timezone.utc)
        )
        self.assertNotEqual(
            first["acquisition_receipt"]["fetched_at"],
            second["acquisition_receipt"]["fetched_at"],
        )
        self.assertEqual(
            first["acquisition_receipt"]["receipt_id"],
            second["acquisition_receipt"]["receipt_id"],
        )

    def test_csv_requires_real_source_url(self):
        request = self.request()
        request["candidate"]["source_url"] = "candidate.csv"
        with self.assertRaisesRegex(
            free_market_observations.AcquisitionError, "candidate_source_url_required"
        ):
            free_market_observations.collect(request)

    def test_session_mismatch_is_not_silently_joined(self):
        request = self.request()
        request["benchmark"]["csv_path"] = str(
            self.write_series("short-benchmark.csv", end=69)
        )
        with self.assertRaisesRegex(
            free_market_observations.AcquisitionError,
            "candidate_benchmark_latest_session_mismatch",
        ):
            free_market_observations.collect(request)

    def test_missing_optional_provider_is_explicit(self):
        request = self.request()
        request["provider"] = "BAOSTOCK"
        for key in ("candidate", "benchmark"):
            request[key].pop("csv_path")
            request[key].pop("source_url")
            request[key].pop("source")
        with mock.patch.object(
            free_market_observations,
            "_optional_import",
            side_effect=free_market_observations.AcquisitionError(
                "PROVIDER_UNAVAILABLE", "optional_dependency_missing:baostock"
            ),
        ):
            with self.assertRaisesRegex(
                free_market_observations.AcquisitionError,
                "optional_dependency_missing:baostock",
            ):
                free_market_observations.collect(request)

    def test_baostock_process_timeout_is_hard_failure(self):
        class Parent:
            def poll(self, timeout):
                self.timeout = timeout
                return False

            def close(self):
                pass

        class Child:
            def close(self):
                pass

        class Process:
            daemon = False

            def start(self):
                pass

            def terminate(self):
                self.terminated = True

            def join(self, timeout):
                pass

            def is_alive(self):
                return False

        parent = Parent()
        process = Process()
        context = SimpleNamespace(
            Pipe=lambda duplex: (parent, Child()),
            Process=lambda **kwargs: process,
        )
        with self.assertRaisesRegex(
            free_market_observations.AcquisitionError, "baostock_wall_clock_timeout"
        ):
            free_market_observations._collect_baostock(
                {},
                datetime(2026, 3, 14).date(),
                datetime(2025, 9, 15).date(),
                timeout_seconds=0.01,
                context=context,
            )
        self.assertTrue(process.terminated)
        self.assertEqual(parent.timeout, 0.01)

    def test_failed_provider_never_tries_an_unselected_fallback(self):
        request = self.request()
        request["provider"] = "BAOSTOCK"
        for key in ("candidate", "benchmark"):
            request[key].pop("csv_path")
            request[key].pop("source_url")
            request[key].pop("source")
        with mock.patch.object(
            free_market_observations,
            "_collect_baostock",
            side_effect=free_market_observations.AcquisitionError(
                "SOURCE_UNAVAILABLE", "bounded_failure"
            ),
        ), mock.patch.object(free_market_observations, "_collect_akshare_tencent") as fallback:
            with self.assertRaisesRegex(
                free_market_observations.AcquisitionError, "bounded_failure"
            ):
                free_market_observations.collect(request)
            fallback.assert_not_called()

    def test_akshare_uses_bounded_history_for_equity_and_index(self):
        request = self.request()
        request["provider"] = "AKSHARE_TENCENT"
        for key in ("candidate", "benchmark"):
            request[key].pop("csv_path")
            request[key].pop("source_url")
            request[key].pop("source")

        rows = []
        for index in range(70):
            month = 1 + index // 28
            day = 1 + index % 28
            rows.append({"date": f"2026-{month:02d}-{day:02d}", "close": 100 + index})

        class Frame:
            def to_dict(self, orient):
                self_orient = orient
                self.last_orient = self_orient
                return rows

        bounded = mock.Mock(side_effect=lambda **kwargs: Frame())
        fake_ak = SimpleNamespace(
            __version__="test",
            stock_zh_a_hist_tx=bounded,
            stock_zh_index_daily_tx=mock.Mock(
                side_effect=AssertionError("unbounded index endpoint must not be called")
            ),
        )
        with mock.patch.object(
            free_market_observations, "_optional_import", return_value=fake_ak
        ):
            packet = free_market_observations.collect(request)
        self.assertEqual(packet["status"], "OBSERVATIONS_READY")
        self.assertEqual(bounded.call_count, 2)
        for call in bounded.call_args_list:
            self.assertEqual(call.kwargs["start_date"], "20250915")
            self.assertEqual(call.kwargs["end_date"], "20260314")
            self.assertEqual(call.kwargs["timeout"], 10.0)

    def test_tushare_builds_qfq_series_and_current_market_fundamentals(self):
        request = self.request()
        request["provider"] = "TUSHARE"
        request["benchmark"]["asset_type"] = "INDEX"
        for key in ("candidate", "benchmark"):
            request[key].pop("csv_path")
            request[key].pop("source_url")
            request[key].pop("source")

        responses = {
            "daily": [
                {"trade_date": "20260314", "close": 110, "vol": 1200},
                {"trade_date": "20260313", "close": 100, "vol": 1000},
            ],
            "adj_factor": [
                {"trade_date": "20260314", "adj_factor": 2},
                {"trade_date": "20260313", "adj_factor": 1},
            ],
            "daily_basic": [
                {
                    "trade_date": "20260314", "turnover_rate": 3.2,
                    "volume_ratio": 1.4, "pe_ttm": 18.5, "pb": 4.2,
                    "total_mv": 2500000, "circ_mv": 2400000,
                },
                {"trade_date": "20260313", "turnover_rate": 2.8},
            ],
            "index_daily": [
                {"trade_date": "20260314", "close": 4200, "vol": 5000},
                {"trade_date": "20260313", "close": 4100, "vol": 4800},
            ],
        }

        class Frame:
            def __init__(self, records):
                self.records = records

            def to_dict(self, orient):
                self.last_orient = orient
                return self.records

        pro = SimpleNamespace(
            query=mock.Mock(side_effect=lambda api_name, **kwargs: Frame(responses[api_name]))
        )
        fake_ts = SimpleNamespace(
            __version__="test",
            pro_api=mock.Mock(return_value=pro),
        )
        with mock.patch.dict("os.environ", {"TUSHARE_TOKEN": "secret-test-token"}), \
             mock.patch.object(free_market_observations, "_optional_import", return_value=fake_ts):
            packet = free_market_observations.collect(request)

        self.assertEqual(packet["provider"], "TUSHARE")
        self.assertEqual(packet["adjustment"], "QFQ_AS_OF_CUTOFF")
        self.assertEqual(packet["candidate"]["observations"][0]["close"], 50.0)
        latest = packet["candidate"]["observations"][-1]
        self.assertEqual(latest["close"], 110.0)
        self.assertEqual(latest["turnover_rate"], 3.2)
        self.assertEqual(latest["pe_ttm"], 18.5)
        self.assertEqual(latest["total_market_cap_cny"], 25000000000.0)
        self.assertEqual(
            packet["acquisition_receipt"]["provider_endpoints"],
            ["adj_factor", "daily", "daily_basic", "index_daily"],
        )
        self.assertNotIn("secret-test-token", json.dumps(packet))
        snapshot = market_snapshot_adapter.build_snapshot(packet)["market_snapshot"]
        self.assertEqual(snapshot["pe_ttm"], 18.5)
        self.assertEqual(snapshot["provider_volume_ratio"], 1.4)

    def test_tushare_requires_host_credential(self):
        request = self.request()
        request["provider"] = "TUSHARE"
        for key in ("candidate", "benchmark"):
            request[key].pop("csv_path")
            request[key].pop("source_url")
            request[key].pop("source")
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(
                free_market_observations.AcquisitionError, "tushare_token_missing"
            ):
                free_market_observations.collect(request)

    def test_cli_persists_failure_receipt(self):
        request_path = self.root / "request.json"
        output_path = self.root / "output.json"
        bad_request = self.request()
        bad_request["provider"] = "AUTO"
        request_path.write_text(json.dumps(bad_request), encoding="utf-8")
        code = free_market_observations.main([
            "--input", str(request_path), "--output", str(output_path)
        ])
        self.assertEqual(code, 2)
        failure = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(failure["status"], "REQUEST_REJECTED")
        self.assertFalse(failure["fallback_attempted"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
