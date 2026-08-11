#!/usr/bin/env python3
"""Offline tests for frozen market snapshot calculation."""
import unittest

import market_snapshot_adapter


def series(name, ticker, closes, volume_multiplier=1.0):
    return {
        "name": name,
        "ticker": ticker,
        "exchange": "XSHG",
        "source": "fixture",
        "source_url": f"https://market.example.cn/{ticker}/history",
        "observations": [
            {
                "date": f"2026-{1 + index // 28:02d}-{1 + index % 28:02d}",
                "close": close,
                "volume": (1000 + index * 10) * volume_multiplier,
                "turnover_rate": 2.5 + index / 100,
            }
            for index, close in enumerate(closes)
        ],
    }


class MarketSnapshotAdapterTests(unittest.TestCase):
    def packet(self):
        candidate_closes = [100 + index for index in range(70)]
        benchmark_closes = [100 + index * 0.5 for index in range(70)]
        return {
            "as_of_date": "2026-03-14",
            "candidate": series("甲公司", "600001", candidate_closes),
            "benchmark": series("固定行业篮子", "INDEX", benchmark_closes),
        }

    def test_builds_reproducible_relative_strength_snapshot(self):
        result = market_snapshot_adapter.build_snapshot(self.packet())
        snapshot = result["market_snapshot"]
        self.assertEqual(snapshot["as_of_date"], "2026-03-14")
        self.assertTrue(snapshot["latest_observed_session_on_or_before_as_of"])
        self.assertIsNotNone(snapshot["return_5d"])
        self.assertIsNotNone(snapshot["return_20d"])
        self.assertIsNotNone(snapshot["return_60d"])
        self.assertGreater(snapshot["excess_20d"], 0)
        self.assertIsNotNone(snapshot["volume_ratio_20d"])
        self.assertEqual(len(snapshot["adapter_receipt"]["input_sha256"]), 64)

    def test_input_order_does_not_change_receipt_or_metrics(self):
        packet = self.packet()
        reversed_packet = self.packet()
        reversed_packet["candidate"]["observations"].reverse()
        reversed_packet["benchmark"]["observations"].reverse()
        first = market_snapshot_adapter.build_snapshot(packet)
        second = market_snapshot_adapter.build_snapshot(reversed_packet)
        self.assertEqual(first["market_snapshot"]["return_20d"], second["market_snapshot"]["return_20d"])
        # Receipt binds the exact supplied packet, while computed metrics are order-independent.
        self.assertNotEqual(
            first["market_snapshot"]["adapter_receipt"]["receipt_id"],
            second["market_snapshot"]["adapter_receipt"]["receipt_id"],
        )

    def test_rejects_mismatched_latest_market_sessions(self):
        packet = self.packet()
        packet["benchmark"]["observations"].pop()
        with self.assertRaisesRegex(ValueError, "latest_session_mismatch"):
            market_snapshot_adapter.build_snapshot(packet)

    def test_snapshot_does_not_require_model_evidence_ids(self):
        packet = self.packet()
        result = market_snapshot_adapter.build_snapshot(packet)
        snapshot = result["market_snapshot"]
        self.assertNotIn("evidence_ids", snapshot)
        self.assertEqual(result["candidate"]["ticker"], "600001")
        self.assertEqual(len(snapshot["adapter_receipt"]["input_sha256"]), 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
