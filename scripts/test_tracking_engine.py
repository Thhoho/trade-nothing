#!/usr/bin/env python3
"""Offline regression tests for the v0.12 tracking track (赔率轨)."""
import unittest

import crux_engine
import opportunity_engine
import tracking_engine

from test_opportunity_engine import (
    citation,
    detective_payload,
    research_state,
    seed,
)


def tracked_state():
    """A research state whose seed is EVIDENCE_BACKED with full odds structure."""
    st = research_state()
    real = citation("real")
    payload = detective_payload(
        real,
        seed(
            real,
            asymmetry_case={
                "upside_shape": "OUTSIZED",
                "convexity": "OPTION_LIKE",
                "downside_shape": "LIMITED",
                "time_to_signal": "NEAR",
                "basis": "scarce input repricing has convex upside.",
            },
        ),
    )
    opportunity_engine.harvest_round(st, 1, payload, {})
    return st


class TrackingAssessmentTests(unittest.TestCase):
    def test_blocked_seed_with_odds_chain_checkpoints_is_admitted(self):
        st = tracked_state()
        item = st["opportunity_seeds"][0]
        outcome = tracking_engine.tracking_assessment(st, item)
        self.assertTrue(outcome["admitted"], outcome["reasons"])

    def test_missing_odds_blocks_admission(self):
        st = tracked_state()
        item = st["opportunity_seeds"][0]
        # Remove both odds and the causal chain so the degraded fallback also fails.
        item["asymmetry_case"] = {}
        item["causal_path"] = "A -> B"
        item["causal_chain"] = []
        outcome = tracking_engine.tracking_assessment(st, item)
        self.assertFalse(outcome["admitted"])
        self.assertIn("no_substantive_odds", outcome["reasons"])

    def test_short_chain_blocks_admission(self):
        st = tracked_state()
        item = st["opportunity_seeds"][0]
        item["causal_path"] = "A -> B"
        item["causal_chain"] = []
        outcome = tracking_engine.tracking_assessment(st, item)
        self.assertFalse(outcome["admitted"])
        self.assertIn("chain_too_short", outcome["reasons"])

    def test_missing_checkpoints_blocks_admission(self):
        st = tracked_state()
        item = st["opportunity_seeds"][0]
        item["falsifier"] = ""
        outcome = tracking_engine.tracking_assessment(st, item)
        self.assertFalse(outcome["admitted"])
        self.assertIn("missing_checkpoints", outcome["reasons"])

    def test_failure_signals_extracted_from_inquisitor_payload(self):
        payload = {
            "opportunity_seeds": [
                {
                    "candidate": "Asset Owner",
                    "ticker": "000001",
                    "relation_type": "DIRECT_WINNER",
                    "origin_crux": "C1",
                    "causal_path": "A -> B",
                    "evidence": [],
                    "odds_calibration": {
                        "success_enablers": "contract closes",
                        "primary_failure_mode": "substitution wins qualification",
                        "failure_signal": "rival passes qualification at scale",
                    },
                },
                {"candidate": "No Calibration"},
            ]
        }
        # The function now requires state to match by entity_identity.
        st = tracked_state()
        signals = tracking_engine._failure_signals_from_payload(payload, st)
        # "Asset Owner" with ticker 000001 should match the tracked seed's entity
        # identity (LISTED_EQUITY|TICKER|000001).
        self.assertTrue(any("rival passes qualification at scale" == v for v in signals.values()))
        self.assertNotIn("No Calibration", signals)


class SyncLedgerTests(unittest.TestCase):
    def test_sync_enters_and_is_idempotent(self):
        st = tracked_state()
        tracking_engine.sync_tracking_ledger(st, 1)
        ledger = st["tracking_ledger"]
        self.assertEqual(len(ledger), 1)
        entry = next(iter(ledger.values()))
        self.assertEqual(entry["status"], tracking_engine.ACTIVE)
        self.assertEqual(entry["entered_round"], 1)
        # Second sync does not duplicate or downgrade.
        tracking_engine.sync_tracking_ledger(st, 2)
        self.assertEqual(len(st["tracking_ledger"]), 1)

    def test_sync_attaches_failure_signal_from_payload(self):
        st = tracked_state()
        payload = {
            "opportunity_seeds": [
                {
                    "candidate": "Asset Owner",
                    "odds_calibration": {
                        "failure_signal": "rival passes qualification at scale"
                    },
                }
            ]
        }
        tracking_engine.sync_tracking_ledger(st, 1, odds_payload=payload)
        entry = next(iter(st["tracking_ledger"].values()))
        self.assertEqual(
            entry["failure_signal"], "rival passes qualification at scale"
        )

    def test_active_tracked_lists_rows_with_checkpoints(self):
        st = tracked_state()
        tracking_engine.sync_tracking_ledger(st, 1)
        rows = tracking_engine.active_tracked(st)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["candidate"], "Asset Owner")
        self.assertEqual(row["upgrade_checkpoint"], "new capacity contract disclosure")
        self.assertEqual(row["abandon_checkpoint"], "substitute reaches commercial qualification")
        # "owner captures rent" is touched by the evidence claim "candidate
        # captures the bottleneck"; the other two links are unverified.
        self.assertEqual(row["chain_counts"]["confirmed"], 1)
        self.assertEqual(row["chain_counts"]["unverified"], 2)

    def test_rejected_seed_closes_entry(self):
        st = tracked_state()
        tracking_engine.sync_tracking_ledger(st, 1)
        item = st["opportunity_seeds"][0]
        # Force the formal track to reject it via a rejecting screen assessment:
        # simplest deterministic stand-in is marking the seed REJECTED upstream.
        st["candidate_screens"] = [{
            "seed_id": item["seed_id"],
            "status": "REJECTED",
            "as_of_date": "2026-07-10",
            "screen_id": "SCREEN-REJ",
            "dimensions": {},
        }]
        # Re-run sync: promotion now derives REJECTED, entry closes.
        tracking_engine.sync_tracking_ledger(st, 2)
        entry = st["tracking_ledger"][item["seed_id"]]
        self.assertEqual(entry["status"], tracking_engine.CLOSED)
        self.assertEqual(entry["close_reason"], "rejected_by_screen")


if __name__ == "__main__":
    unittest.main()
