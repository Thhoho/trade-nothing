#!/usr/bin/env python3
"""Offline regression tests for the two-sided CandidateScreen gate."""
import os
import tempfile
import unittest

import candidate_screen_engine as screen_engine
import crux_engine
import deepthink_orchestrator_v2 as orchestrator
import report_v2


AS_OF = "2026-07-10"


def citation(path, source=None, date="2026-07-01", tier="primary"):
    return {
        "claim": f"screen evidence {path}",
        "number": "1",
        "source": source or f"Source {path}",
        "url": f"https://example.com/screen/{path}",
        "date": date,
        "source_tier": tier,
    }


def state_with_seed():
    st = crux_engine.new_state(
        "root", "root question", "3-6M",
        [{"id": "C1", "label": "root crux", "monitor_anchor": "observable"}],
    )
    st["opportunity_seeds"] = [{
        "seed_id": "OS-TEST",
        "candidate": "Asset Owner",
        "ticker": "AO",
        "asset_type": "LISTED_EQUITY",
        "relation_type": "BOTTLENECK_OWNER",
        "origin_crux": "C1",
        "causal_path": "constraint persists -> rent shifts to owner",
        "economic_exposure": "owner reports input-linked revenue",
        "why_market_may_miss": "consensus tracks downstream volume",
        "pricing_anchor": "consensus EBITDA excludes the disclosed contract",
        "catalyst": "contract disclosure",
        "catalyst_window": {
            "event": "contract disclosure",
            "expected_by": "2026-10-10",
            "date_status": "REVIEW_CHECKPOINT",
        },
        "falsifier": "substitute qualifies",
        "evidence": [citation("seed-a"), citation("seed-b")],
        "first_seen_round": 1,
        "last_seen_round": 2,
        "source_agents": ["detective", "inquisitor"],
        "maturity": "READY_FOR_SCREENING",
    }]
    st["frame_contract"] = {"as_of_date": AS_OF}
    st["cruxes"]["C1"].update({
        "first_contested": 1,
        "contested_history": [0.35, 0.35, 0.35],
        "status": "RESOLVED_BEAR",
        "retired": True,
        "citations": [citation("origin-a"), citation("origin-b")],
    })
    st["last_convergence"] = {"decision": "converge"}
    st["decision_trace"].append({
        "round": 3, "weakest": "C1", "p_weakest": 0.35, "p_mean": 0.45,
        "support_weakest": 0.35, "support_mean": 0.45, "decision": "NO_EDGE / AVOID",
    })
    return st


def payload(side, default_answer="YES", overrides=None, source_override=None, stale_dimensions=None):
    overrides = overrides or {}
    stale_dimensions = stale_dimensions or set()
    questions = []
    for dimension in screen_engine.DIMENSIONS:
        answer = overrides.get(dimension, default_answer)
        source = source_override if source_override else f"{side}-{dimension}"
        date = "2025-01-01" if dimension in stale_dimensions else "2026-07-01"
        evidence = [] if answer == "UNKNOWN" else [
            citation(f"{side.lower()}-{dimension.lower()}", source=source, date=date)
        ]
        questions.append({
            "dimension": dimension,
            "answer": answer,
            "finding": "" if answer == "UNKNOWN" else f"{side} says {answer} on {dimension}",
            "evidence": evidence,
        })
    return {
        "as_of_date": AS_OF,
        "candidate_screens": [{"seed_id": "OS-TEST", "questions": questions}],
    }


class CandidateScreenEngineTests(unittest.TestCase):
    def test_default_dispatch_deduplicates_entity_and_honors_old_duplicate_screen(self):
        st = state_with_seed()
        duplicate = dict(st["opportunity_seeds"][0])
        duplicate.update({"seed_id": "OS-TEST-2", "relation_type": "DIRECT_WINNER"})
        st["opportunity_seeds"].append(duplicate)
        self.assertEqual(len(screen_engine.screenable_seeds(st)), 1)
        st["candidate_screens"].append({
            "screen_id": "CS-OLD", "seed_id": "OS-TEST-2", "as_of_date": AS_OF,
            "status": "WATCHLIST", "dimensions": {},
        })
        self.assertEqual(screen_engine.screenable_seeds(st), [])

    def test_two_sided_fresh_independent_evidence_creates_thesis_candidate(self):
        st = state_with_seed()
        audit = screen_engine.evaluate_batch(
            st, payload("Analyst"), payload("Skeptic"), AS_OF, isolation_status="verified"
        )
        screen = st["candidate_screens"][0]
        self.assertEqual(audit["thesis_candidate_count"], 1)
        self.assertEqual(screen["status"], "THESIS_CANDIDATE")
        self.assertTrue(screen["source_gate"]["passed"])
        self.assertTrue(all(v["state"] == "SUPPORTED" for v in screen["dimensions"].values()))
        self.assertEqual(screen["promotion_packet"]["status"], "DRAFT_REQUIRES_SOURCE_VERIFICATION")
        self.assertIn("页面快照", screen["promotion_packet"]["required_next_step"])
        self.assertEqual(st["opportunity_seeds"][0]["candidate_state"], "THESIS_CANDIDATE")
        self.assertEqual(st["opportunity_seeds"][0]["promotion_eligibility"], "BLOCKED")

    def test_same_source_organization_does_not_corroborate(self):
        st = state_with_seed()
        screen_engine.evaluate_batch(
            st,
            payload("Analyst", source_override="Same Organization"),
            payload("Skeptic", source_override="Same Organization"),
            AS_OF,
        )
        screen = st["candidate_screens"][0]
        self.assertEqual(screen["status"], "WATCHLIST")
        self.assertEqual(screen["dimensions"]["ECONOMIC_EXPOSURE"]["state"], "INCOMPLETE")

    def test_unverified_role_switch_cannot_create_thesis_candidate(self):
        st = state_with_seed()
        screen_engine.evaluate_batch(st, payload("Analyst"), payload("Skeptic"), AS_OF)
        screen = st["candidate_screens"][0]
        self.assertEqual(screen["status"], "WATCHLIST")
        self.assertIn("screen_isolation_unverified", screen["gaps"])

    def test_bilateral_critical_no_rejects_candidate(self):
        st = state_with_seed()
        overrides = {"ECONOMIC_EXPOSURE": "NO"}
        screen_engine.evaluate_batch(
            st, payload("Analyst", overrides=overrides), payload("Skeptic", overrides=overrides), AS_OF
        )
        screen = st["candidate_screens"][0]
        self.assertEqual(screen["status"], "REJECTED")
        self.assertEqual(screen["critical_rejections"], ["ECONOMIC_EXPOSURE"])

    def test_disagreement_is_preserved_not_averaged(self):
        st = state_with_seed()
        screen_engine.evaluate_batch(
            st,
            payload("Analyst", overrides={"EXPECTATION_GAP": "YES"}),
            payload("Skeptic", overrides={"EXPECTATION_GAP": "NO"}),
            AS_OF,
        )
        screen = st["candidate_screens"][0]
        self.assertEqual(screen["status"], "WATCHLIST")
        self.assertEqual(screen["dimensions"]["EXPECTATION_GAP"]["state"], "CONTESTED")

    def test_stale_market_evidence_is_zeroed(self):
        st = state_with_seed()
        stale = {"VALUATION_CONTEXT"}
        screen_engine.evaluate_batch(
            st, payload("Analyst", stale_dimensions=stale), payload("Skeptic", stale_dimensions=stale), AS_OF
        )
        dimension = st["candidate_screens"][0]["dimensions"]["VALUATION_CONTEXT"]
        self.assertEqual(dimension["state"], "INCOMPLETE")
        self.assertEqual(dimension["analyst"]["answer"], "UNKNOWN")
        self.assertIn("answer_zeroed_no_fresh_valid_evidence", dimension["analyst"]["quality_flags"])

    def test_same_day_replay_is_idempotent(self):
        st = state_with_seed()
        screen_engine.evaluate_batch(
            st, payload("Analyst"), payload("Skeptic"), AS_OF, isolation_status="verified"
        )
        screen_engine.evaluate_batch(
            st, payload("Analyst"), payload("Skeptic"), AS_OF, isolation_status="verified"
        )
        self.assertEqual(len(st["candidate_screens"]), 1)


class CandidateScreenOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_scratch = os.environ.get("TRADE_NOTHING_SCRATCH_DIR")
        os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.tmp.name

    def tearDown(self):
        if self.old_scratch is None:
            os.environ.pop("TRADE_NOTHING_SCRATCH_DIR", None)
        else:
            os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.old_scratch
        self.tmp.cleanup()

    def test_screen_dispatch_and_submit_persist_result(self):
        topic = "candidate screen integration"
        st = state_with_seed()
        orchestrator._save(topic, st)
        dispatch = orchestrator.cmd_screen(topic, AS_OF)
        self.assertEqual(dispatch["status"], "dispatch_candidate_screeners")
        self.assertIn("OS-TEST", dispatch["analyst_prompt"])
        result = orchestrator.cmd_submit_screen(
            topic, payload("Analyst"), payload("Skeptic"), AS_OF, isolation_status="verified"
        )
        stored = orchestrator._load(topic)
        self.assertEqual(result["thesis_candidate_count"], 1)
        self.assertEqual(len(stored["candidate_screens"]), 1)

    def test_screen_is_blocked_before_root_convergence(self):
        topic = "candidate screen blocked"
        st = state_with_seed()
        st["last_convergence"] = {"decision": "continue"}
        orchestrator._save(topic, st)
        self.assertEqual(orchestrator.cmd_screen(topic, AS_OF)["status"], "blocked_unconverged")


class CandidateScreenReportTests(unittest.TestCase):
    def test_report_renders_screen_matrix_without_auto_promotion(self):
        st = state_with_seed()
        screen_engine.evaluate_batch(
            st, payload("Analyst"), payload("Skeptic"), AS_OF, isolation_status="verified"
        )
        md = report_v2.render(st)
        self.assertIn("THESIS_CANDIDATE", md)
        self.assertIn("CandidateScreen", md)
        self.assertIn("DRAFT_REQUIRES_SOURCE_VERIFICATION", md)
        self.assertIn("P2 PENDING", md)
        self.assertIn("https://example.com/screen/analyst-economic_exposure", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
