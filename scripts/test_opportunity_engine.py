#!/usr/bin/env python3
"""Offline regression tests for evidence-backed OpportunitySeed harvesting."""
import os
import tempfile
import unittest

import crux_engine
import deepthink_orchestrator_v2 as orchestrator
import opportunity_engine
import report_v2


def citation(path, claim="candidate captures the bottleneck", number="1"):
    return {
        "claim": claim,
        "number": number,
        "source": "Test Source",
        "url": f"https://example.com/research/{path}",
        "date": "2026-07-10",
        "source_tier": "primary",
    }


def research_state():
    st = crux_engine.new_state(
        "root thesis", "Is the root thesis research-ready?", "3-6M",
        [{"id": "C1", "label": "binding crux", "monitor_anchor": "observable"}],
    )
    st["frame_contract"] = {"as_of_date": "2026-07-10"}
    return st


def seed(evidence, candidate="Asset Owner", ticker="AO", **overrides):
    item = {
        "candidate": candidate,
        "ticker": ticker,
        "asset_type": "LISTED_EQUITY",
        "relation_type": "BOTTLENECK_OWNER",
        "origin_crux": "C1",
        "causal_path": "constraint persists -> scarce input reprices -> owner captures rent",
        "economic_exposure": "owns the scarce input",
        "why_market_may_miss": "coverage tracks downstream volume, not input scarcity",
        "catalyst": "new capacity contract disclosure",
        "catalyst_window": {
            "event": "new capacity contract disclosure",
            "expected_by": "2026-10-10",
            "date_status": "REVIEW_CHECKPOINT",
        },
        "falsifier": "substitute reaches commercial qualification",
        "evidence": [evidence],
    }
    item.update(overrides)
    return item


def detective_payload(evidence, candidate_seed=None):
    return {
        "crux_evidence": [{"crux_id": "C1", "evidence": [evidence]}],
        "opportunity_seeds": [candidate_seed or seed(evidence)],
    }


def inquisitor_payload(evidence, candidate_seed=None):
    attack = {**evidence, "attack": "substitution redirects value to the asset owner"}
    candidate_seed = candidate_seed or seed(attack)
    return {
        "crux_attacks": [{"crux_id": "C1", "attacks": [attack]}],
        "opportunity_seeds": [candidate_seed],
    }


class OpportunityEngineTests(unittest.TestCase):
    def test_invented_seed_citation_is_rejected(self):
        st = research_state()
        real = citation("real")
        invented = citation("invented")
        payload = detective_payload(real, seed(invented))
        audit = opportunity_engine.harvest_round(st, 1, payload, {})
        self.assertEqual(st["opportunity_seeds"], [])
        self.assertEqual(audit["rejected_reasons"]["no_agent_backed_citation"], 1)
        self.assertEqual(audit["dropped_citations"], 1)

    def test_two_agents_merge_sources_but_pending_origin_blocks_screening(self):
        st = research_state()
        first = citation("first", claim="scarce input is contracted")
        audit1 = opportunity_engine.harvest_round(st, 1, detective_payload(first), {})
        self.assertEqual(audit1["opportunity_seed_count"], 1)
        self.assertEqual(st["opportunity_seeds"][0]["maturity"], "EVIDENCE_BACKED")

        second = citation("second", claim="owner reports input-linked revenue")
        alternate_name = seed({**second, "attack": "value migrates"}, candidate="Asset Owner Ltd")
        audit2 = opportunity_engine.harvest_round(
            st, 2, {}, inquisitor_payload(second, alternate_name),
        )
        stored = st["opportunity_seeds"][0]
        self.assertEqual(audit2["merged_existing"], 1)
        self.assertEqual(audit2["evidence_ready_count"], 1)
        self.assertEqual(audit2["ready_for_screening_count"], 0)
        self.assertEqual(stored["maturity"], "READY_FOR_SCREENING")
        assessment = opportunity_engine.assess_seed(st, stored)
        self.assertEqual(assessment["screening_status"], "BLOCKED_ORIGIN_CRUX")
        self.assertIn("origin_crux_never_contested", assessment["blockers"])
        self.assertEqual(len(stored["evidence"]), 2)
        self.assertEqual(stored["source_agents"], ["detective", "inquisitor"])
        self.assertIn("Asset Owner Ltd", stored["candidate_aliases"])

        # Replaying the first citation cannot inflate source count or create a new seed.
        audit3 = opportunity_engine.harvest_round(st, 3, detective_payload(first), {})
        self.assertEqual(audit3["opportunity_seed_count"], 1)
        self.assertEqual(len(stored["evidence"]), 2)

        # Once the origin crux and root thesis are healthy, readiness is recomputed
        # without replaying or rewriting the seed.
        cx = st["cruxes"]["C1"]
        cx.update({
            "first_contested": 1,
            "contested_history": [0.4, 0.39, 0.39],
            "status": "RESOLVED_BEAR",
            "retired": True,
            "citations": [first, second],
        })
        st["last_convergence"] = {"decision": "converge"}
        self.assertEqual(opportunity_engine.summary(st)["ready_for_screening_count"], 1)
        self.assertEqual(opportunity_engine.assess_seed(st, stored)["screening_status"],
                         "READY_FOR_SCREENING")

    def test_same_ticker_is_one_entity_but_paths_stay_separate(self):
        st = research_state()
        first = citation("one")
        second = citation("two")
        opportunity_engine.harvest_round(st, 1, detective_payload(first), {})
        alternate = seed(second, relation_type="DIRECT_WINNER", origin_crux="C1")
        opportunity_engine.harvest_round(st, 2, {}, inquisitor_payload(second, alternate))
        self.assertEqual(len(st["opportunity_seeds"]), 2)
        views = opportunity_engine.entity_views(st)
        self.assertEqual(len(views), 1)
        self.assertEqual(len(views[0]["paths"]), 2)
        self.assertEqual(opportunity_engine.summary(st)["duplicate_path_count"], 1)

    def test_missing_causal_path_is_not_a_thematic_seed(self):
        st = research_state()
        evidence = citation("theme")
        payload = detective_payload(evidence, seed(evidence, causal_path=""))
        audit = opportunity_engine.harvest_round(st, 1, payload, {})
        self.assertEqual(audit["rejected_reasons"]["missing_causal_path"], 1)
        self.assertEqual(audit["opportunity_seed_count"], 0)


class OpportunityOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_scratch = os.environ.get("TRADE_NOTHING_SCRATCH_DIR")
        self.old_evolution = os.environ.get("TRADE_NOTHING_EVOLUTION_PATH")
        os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.tmp.name
        os.environ["TRADE_NOTHING_EVOLUTION_PATH"] = os.path.join(self.tmp.name, "missing.md")

    def tearDown(self):
        if self.old_scratch is None:
            os.environ.pop("TRADE_NOTHING_SCRATCH_DIR", None)
        else:
            os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.old_scratch
        if self.old_evolution is None:
            os.environ.pop("TRADE_NOTHING_EVOLUTION_PATH", None)
        else:
            os.environ["TRADE_NOTHING_EVOLUTION_PATH"] = self.old_evolution
        self.tmp.cleanup()

    def test_submit_persists_harvest_audit_and_counts(self):
        topic = "opportunity integration"
        frame = {
            "decision_question": "test", "horizon": "3-6M", "as_of_date": "2026-07-11",
            "unit_of_analysis": "test assets",
            "thesis_seed": "If the premise holds, there may be an edge.",
            "premise_audit": [{
                "id": "P1", "claim": "seed premise", "status": "HYPOTHESIS",
                "as_of": "UNKNOWN", "source_url": None,
                "required_primary_source": "issuer filing", "use": "scope the test",
            }],
            "candidate_cruxes": [
                {"id": "C1", "label": "c1", "definition": "d1", "monitor_anchor": "m1",
                 "falsifier": "f1", "catalyst_window": {
                     "event": "e1", "expected_by": "2026-10-31",
                     "date_status": "REVIEW_CHECKPOINT", "basis_claim_id": "P1"}},
                {"id": "C2", "label": "c2", "definition": "d2", "monitor_anchor": "m2",
                 "falsifier": "f2", "catalyst_window": {
                     "event": "e2", "expected_by": "2026-12-31",
                     "date_status": "REVIEW_CHECKPOINT", "basis_claim_id": "P1"}},
            ],
            "no_edge_precheck": {
                "is_researchable": True, "basis_type": "TESTABILITY",
                "basis_claim_ids": ["P1"], "reason": "observable anchors can settle the question",
            },
            "suggested_max_rounds": 3,
        }
        orchestrator.cmd_init(topic, frame)
        evidence = citation("orchestrator")
        detective = detective_payload(evidence)
        result = orchestrator.cmd_submit(
            topic, detective, {"crux_attacks": [], "opportunity_seeds": []},
            {"crux_signals": {"C1": {"signal": 0.5, "citations": [evidence]}}, "new_cruxes": []},
        )
        stored = orchestrator._load(topic)
        self.assertEqual(result["opportunity_seed_count"], 1)
        self.assertEqual(result["ready_for_screening_count"], 0)
        self.assertEqual(stored["rounds"][-1]["opportunity_harvest"]["accepted_new"], 1)


class OpportunityReportTests(unittest.TestCase):
    def test_no_edge_root_still_renders_evidence_backed_treasure_map(self):
        st = research_state()
        evidence = citation("report", claim="asset owns qualified capacity")
        opportunity_engine.harvest_round(st, 1, detective_payload(evidence), {})
        st["decision_trace"].append({
            "round": 3, "weakest": "C1", "p_weakest": 0.35, "p_mean": 0.45,
            "support_weakest": 0.35, "support_mean": 0.45, "decision": "NO_EDGE / AVOID",
        })
        st["last_convergence"] = {"decision": "converge"}
        st["cruxes"]["C1"].update({
            "first_contested": 1,
            "contested_history": [0.35, 0.35, 0.35],
            "status": "RESOLVED_BEAR",
            "retired": True,
            "citations": [evidence, citation("report-2", claim="second source")],
        })
        md = report_v2.render(st)
        self.assertIn("NO_EDGE / AVOID", md)
        self.assertIn("A.3 · 宝藏地图", md)
        self.assertIn("Asset Owner", md)
        self.assertIn("不是投资建议", md)
        self.assertIn("https://example.com/research/report", md)
        self.assertNotIn("全量工作数据", md)
        self.assertNotIn("待 deep 模型写入", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
