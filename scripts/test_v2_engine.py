#!/usr/bin/env python3
"""Offline regression tests for the v2 evidence and report safety gates."""
import os
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

import crux_engine
import deepthink_orchestrator_v2 as orchestrator
import report_v2
import research_output
import validate_report_v2
import utils


def evidence_plan(crux_id):
    return [
        {"plan_id": f"SP-{crux_id}-1", "publisher_class": "ISSUER_OR_FILING",
         "target_claim": f"issuer anchor {crux_id}", "search_query": f"issuer {crux_id}"},
        {"plan_id": f"SP-{crux_id}-2", "publisher_class": "REGULATOR_OR_OFFICIAL_DATASET",
         "target_claim": f"official anchor {crux_id}", "search_query": f"official {crux_id}"},
    ]


def citation(path, claim="claim", number="1", tier="primary"):
    return {
        "claim": claim,
        "number": number,
        "source": "Test Source",
        "url": f"https://fixture-research.org/{path}",
        "date": "2026-07-10",
        "source_tier": tier,
    }


def state():
    return crux_engine.new_state(
        "test", "Is the evidence research-ready?", "3-6M",
        [{"id": "C1", "label": "binding", "monitor_anchor": "observable"}],
    )


def converged_state():
    st = state()
    st["last_convergence"] = {"decision": "converge"}
    st["decision_trace"].append({
        "round": 3, "weakest": "C1", "p_weakest": 0.5, "p_mean": 0.5,
        "support_weakest": 0.5, "support_mean": 0.5, "decision": "MONITOR",
    })
    return st


class ClaimTierTests(unittest.TestCase):
    """Tiers label a claim's support; they never suppress the claim."""

    def test_tier_requires_independent_publishers_not_just_urls(self):
        cx = {"citations": []}
        self.assertEqual(crux_engine.crux_claim_tier(cx), "HYPOTHESIS")

        # Two distinct URLs on one domain are still a single publisher.
        cx = {"citations": [citation("a"), citation("b")]}
        self.assertEqual(crux_engine.crux_claim_tier(cx), "SINGLE_SOURCE")

        independent = {**citation("c"), "url": "https://second-publisher.org/report",
                       "source": "Second Publisher"}
        cx = {"citations": [citation("a"), independent]}
        self.assertEqual(crux_engine.crux_claim_tier(cx), "VERIFIED")

    def test_republication_does_not_manufacture_independence(self):
        """Aggregators reposting one report must not reach VERIFIED."""
        reposts = [
            {**citation("a"), "url": "https://aggregator-one.com/a/1",
             "source": "Guosheng Research (aggregator-one repost)"},
            {**citation("b"), "url": "https://aggregator-two.cn/2026/x.html",
             "source": "Guosheng Research (aggregator-two repost)"},
            {**citation("c"), "url": "https://aggregator-three.com/a/3",
             "source": "Guosheng Research (aggregator-three repost)"},
        ]
        self.assertEqual(
            crux_engine.crux_claim_tier({"citations": reposts}), "SINGLE_SOURCE"
        )
        distinct = [
            {**citation("a"), "url": "https://publisher-one.org/a", "source": "Publisher One"},
            {**citation("b"), "url": "https://publisher-two.org/b", "source": "Publisher Two"},
        ]
        self.assertEqual(
            crux_engine.crux_claim_tier({"citations": distinct}), "VERIFIED"
        )

    def test_source_labels_can_only_reduce_diversity(self):
        """A fabricated label must never buy a higher tier."""
        same_domain = [
            {**citation("a"), "url": "https://one-domain.org/a", "source": "Org A"},
            {**citation("b"), "url": "https://one-domain.org/b", "source": "Org B"},
        ]
        self.assertEqual(
            crux_engine.crux_claim_tier({"citations": same_domain}), "SINGLE_SOURCE"
        )

    def test_rejected_only_screen_does_not_unlock_ranking(self):
        """A screen that rejected everything proves there is nothing to rank."""
        st = converged_state()
        st["cruxes"]["C1"]["citations"] = [
            {**citation("a"), "url": "https://publisher-one.org/a", "source": "Publisher One"},
            {**citation("b"), "url": "https://publisher-two.org/b", "source": "Publisher Two"},
        ]
        st["candidate_screens"] = [{"seed_id": "OS-1", "status": "REJECTED"}]
        rejected = crux_engine.research_grade(st)
        self.assertFalse(rejected["ranking_allowed"])
        self.assertEqual(rejected["candidate_lifecycle"]["rankable_seed_ids"], [])
        st["candidate_screens"].append({"seed_id": "OS-2", "status": "WATCHLIST"})
        surviving = crux_engine.research_grade(st)
        self.assertTrue(surviving["ranking_allowed"])
        self.assertEqual(
            surviving["candidate_lifecycle"]["rankable_seed_ids"], ["OS-2"]
        )

    def test_latest_screen_controls_ranking_instead_of_stale_history(self):
        st = converged_state()
        st["cruxes"]["C1"]["citations"] = [
            {**citation("a"), "url": "https://publisher-one.org/a", "source": "Publisher One"},
            {**citation("b"), "url": "https://publisher-two.org/b", "source": "Publisher Two"},
        ]
        st["candidate_screens"] = [
            {"seed_id": "OS-1", "as_of_date": "2026-07-01", "status": "WATCHLIST"},
            {"seed_id": "OS-1", "as_of_date": "2026-08-01", "status": "REJECTED"},
        ]
        self.assertFalse(crux_engine.research_grade(st)["ranking_allowed"])

    def test_formal_research_report_does_not_require_candidate_workflow(self):
        st = converged_state()
        st["cruxes"]["C1"]["citations"] = [
            {**citation("a"), "url": "https://publisher-one.org/a", "source": "Publisher One"},
            {**citation("b"), "url": "https://publisher-two.org/b", "source": "Publisher Two"},
        ]

        grade = crux_engine.research_grade(st)

        self.assertEqual(grade["report_grade"], "FORMAL")
        self.assertEqual(grade["unmet_gates"], [])
        self.assertTrue(grade["publication_allowed"])
        self.assertFalse(grade["ranking_allowed"])
        self.assertEqual(
            grade["candidate_lifecycle"]["screening_status"], "NOT_REQUIRED"
        )
        self.assertEqual(grade["candidate_lifecycle"]["pending_steps"], [])

    def test_opportunity_report_can_be_formal_with_zero_screenable_candidates(self):
        st = converged_state()
        st["research_intent"] = "OPPORTUNITY_DISCOVERY"
        st["cruxes"]["C1"]["citations"] = [
            {**citation("a"), "url": "https://publisher-one.org/a", "source": "Publisher One"},
            {**citation("b"), "url": "https://publisher-two.org/b", "source": "Publisher Two"},
        ]
        st["landscape_map"] = {
            "paths": [{
                "path_id": "L1",
                "state": "UNKNOWN",
                "probes": {
                    "detective": {"state": "UNKNOWN"},
                    "inquisitor": {"state": "UNKNOWN"},
                },
            }],
            "round_plans": [],
        }

        grade = crux_engine.research_grade(st)

        self.assertEqual(grade["report_grade"], "FORMAL")
        self.assertNotIn("CANDIDATE_SCREEN", grade["unmet_gates"])
        self.assertNotIn("CLAIM_VERIFICATION", grade["unmet_gates"])
        self.assertEqual(
            grade["candidate_lifecycle"]["screening_status"],
            "NO_SCREENABLE_CANDIDATE",
        )

    def test_missing_required_landscape_cannot_erase_its_own_grade_gate(self):
        st = converged_state()
        st["research_intent"] = "OPPORTUNITY_DISCOVERY"
        st["cruxes"]["C1"]["citations"] = [
            {**citation("a"), "url": "https://publisher-one.org/a", "source": "Publisher One"},
            {**citation("b"), "url": "https://publisher-two.org/b", "source": "Publisher Two"},
        ]

        grade = crux_engine.research_grade(st)

        self.assertEqual(grade["report_grade"], "PROVISIONAL")
        self.assertIn("LANDSCAPE_COVERAGE", grade["unmet_gates"])
        self.assertTrue(grade["coverage"]["required"])

    def test_pending_claim_verification_is_visible_but_does_not_lower_grade(self):
        st = converged_state()
        st["cruxes"]["C1"]["citations"] = [
            {**citation("a"), "url": "https://publisher-one.org/a", "source": "Publisher One"},
            {**citation("b"), "url": "https://publisher-two.org/b", "source": "Publisher Two"},
        ]
        st["candidate_screens"] = [{
            "seed_id": "OS-1",
            "as_of_date": "2026-08-01",
            "status": "THESIS_CANDIDATE",
            "claim_verification_status": "PENDING",
        }]

        grade = crux_engine.research_grade(st)

        self.assertEqual(grade["report_grade"], "FORMAL")
        self.assertEqual(grade["unmet_gates"], [])
        self.assertTrue(grade["ranking_allowed"])
        self.assertEqual(
            grade["candidate_lifecycle"]["pending_steps"], ["CLAIM_VERIFICATION"]
        )
        self.assertEqual(
            grade["candidate_lifecycle"]["pending_verification_seed_ids"], ["OS-1"]
        )

    def test_evidence_counts_are_script_filled(self):
        st = state()
        independent = {**citation("c"), "url": "https://second-publisher.org/report"}
        st["cruxes"]["C1"]["citations"] = [citation("a"), citation("b"), independent]
        counts = crux_engine.evidence_counts(st)
        self.assertEqual(counts["valid_citations"], 3)
        self.assertEqual(counts["unique_source_urls"], 3)
        self.assertEqual(counts["unique_publishers"], 2)


class QuestionAwareVerdictTests(unittest.TestCase):
    def _state(self, question_type, cruxes):
        nodes = [{"id": "Q1", "node_type": "QUESTION", "label": "root"}]
        nodes.extend({"id": item["id"], "node_type": "CRUX", "label": item["label"]}
                     for item in cruxes)
        edges = [{"from": item["id"], "to": "Q1", "relation": "PRICING_FOR"
                  if item.get("logic_role") == "PRICING" else "ALTERNATIVE_PATH"}
                 for item in cruxes]
        return crux_engine.new_state(
            "question-aware", "test", "3-6M", cruxes, question_type,
            {"root_id": "Q1", "nodes": nodes, "edges": edges},
        )

    def test_universe_search_one_failed_path_cannot_kill_the_universe(self):
        st = self._state("UNIVERSE_SEARCH", [
            {"id": "C1", "label": "BTM path", "logic_role": "OPPORTUNITY_PATH"},
            {"id": "C2", "label": "grid path", "logic_role": "OPPORTUNITY_PATH"},
            {"id": "C3", "label": "pricing gap", "logic_role": "PRICING"},
        ])
        st["cruxes"]["C1"]["p_history"] = [0.5, 0.35]
        st["cruxes"]["C2"]["p_history"] = [0.5, 0.50]
        st["cruxes"]["C3"]["p_history"] = [0.5, 0.50]
        verdict = crux_engine.research_verdict(st)
        self.assertEqual(verdict["edge_state"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(verdict["evidence_direction"], "UNDETERMINED")
        self.assertEqual(verdict["actionability"], "NONE")
        self.assertEqual(verdict["reason_code"], "UNIVERSE_LANDSCAPE_MISSING")
        st["decision_trace"].append({
            "round": 3, "weakest": "C1", "focus_crux": "C1",
            "p_weakest": 0.35, "p_mean": 0.45,
            "decision": "MONITOR", "research_verdict": verdict,
            "aggregation_rule": "LOGIC_GRAPH_MULTI_PATH",
        })
        report = crux_engine.report_data(st)
        self.assertIsNone(report["binding_crux"])
        self.assertEqual(report["focus_crux"], "C1")
        self.assertEqual(report["aggregation_rule"], "LOGIC_GRAPH_MULTI_PATH")

    def test_universe_search_never_promotes_pooled_global_scores_to_edge(self):
        st = self._state("UNIVERSE_SEARCH", [
            {"id": "C1", "label": "path a", "logic_role": "OPPORTUNITY_PATH"},
            {"id": "C2", "label": "path b", "logic_role": "OPPORTUNITY_PATH"},
            {"id": "C3", "label": "pricing", "logic_role": "PRICING"},
        ])
        st["cruxes"]["C1"]["p_history"] = [0.5, 0.35]
        st["cruxes"]["C2"]["p_history"] = [0.5, 0.65]
        st["cruxes"]["C3"]["p_history"] = [0.5, 0.60]
        st["landscape_map"] = {"paths": [{
            "path_id": "L1", "state": "SUPPORTED",
            "probes": {"detective": {"state": "SUPPORTED"},
                       "inquisitor": {"state": "SUPPORTED"}},
        }]}
        verdict = crux_engine.research_verdict(st)
        self.assertEqual(verdict["edge_state"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(verdict["evidence_direction"], "UNDETERMINED")
        self.assertEqual(verdict["actionability"], "MONITOR")
        st["last_convergence"] = {"decision": "converge"}
        verdict = crux_engine.research_verdict(st)
        self.assertEqual(verdict["actionability"], "MONITOR")

    def test_conjunctive_bear_crux_yields_no_edge_but_never_short(self):
        st = self._state("CONJUNCTIVE", [
            {"id": "C1", "label": "necessary", "logic_role": "THESIS_HINGE"},
            {"id": "C2", "label": "necessary two", "logic_role": "THESIS_HINGE"},
        ])
        st["cruxes"]["C1"]["p_history"] = [0.5, 0.35]
        st["cruxes"]["C2"]["p_history"] = [0.5, 0.65]
        verdict = crux_engine.research_verdict(st)
        decision = crux_engine._legacy_decision(verdict)
        self.assertEqual(verdict["edge_state"], "NO_EDGE")
        self.assertEqual(decision, "NO_EDGE")
        self.assertNotIn("AVOID", decision)
        self.assertNotIn("SHORT", decision)

    def test_supported_thesis_without_pricing_is_not_called_an_edge(self):
        st = self._state("CONJUNCTIVE", [
            {"id": "C1", "label": "necessary", "logic_role": "THESIS_HINGE"},
            {"id": "C2", "label": "necessary two", "logic_role": "THESIS_HINGE"},
        ])
        st["cruxes"]["C1"]["p_history"] = [0.5, 0.65]
        st["cruxes"]["C2"]["p_history"] = [0.5, 0.70]
        verdict = crux_engine.research_verdict(st)
        self.assertEqual(verdict["evidence_direction"], "BULL")
        self.assertEqual(verdict["edge_state"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(verdict["reason_code"], "PRICING_NOT_ASSESSED")


class EvidenceGateTests(unittest.TestCase):
    def test_signal_without_citation_is_zeroed(self):
        st = state()
        crux_engine.submit_round(st, 1, {"C1": {"signal": 1, "citations": []}})
        cx = st["cruxes"]["C1"]
        self.assertEqual(cx["p_history"][-1], 0.5)
        self.assertEqual(cx["status"], "PENDING")
        flags = st["rounds"][-1]["signals"]["C1"]["quality_flags"]
        self.assertIn("signal_zeroed_no_valid_citation", flags)

    def test_bare_domain_is_rejected(self):
        st = state()
        bad = {
            "claim": "x", "number": "1", "source": "Test",
            "url": "https://fixture-research.org", "date": "2026-07",
        }
        crux_engine.submit_round(st, 1, {"C1": {"signal": -1, "citations": [bad]}})
        self.assertEqual(st["cruxes"]["C1"]["p_history"][-1], 0.5)

    def test_reserved_example_path_is_rejected(self):
        st = state()
        bad = citation("placeholder")
        bad["url"] = "https://www.example.com/specific-page"
        crux_engine.submit_round(st, 1, {"C1": {"signal": -1, "citations": [bad]}})
        self.assertEqual(st["cruxes"]["C1"]["p_history"][-1], 0.5)

    def test_grounding_redirect_is_not_a_direct_source(self):
        st = state()
        bad = citation("redirect")
        bad["url"] = (
            "https://vertexaisearch.cloud.google.com/grounding-api-redirect/opaque-token"
        )
        crux_engine.submit_round(st, 1, {"C1": {"signal": 1, "citations": [bad]}})
        self.assertEqual(st["cruxes"]["C1"]["p_history"][-1], 0.5)

    def test_strong_signal_without_number_is_capped(self):
        st = state()
        crux_engine.submit_round(
            st, 1, {"C1": {"signal": 9, "citations": [citation("a", number="")]}}
        )
        signal = st["rounds"][-1]["signals"]["C1"]["signal"]
        self.assertEqual(signal, 0.5)

    def test_duplicate_evidence_cannot_be_scored_twice(self):
        st = state()
        item = citation("same", claim="same", number="7")
        crux_engine.submit_round(st, 1, {"C1": {"signal": 1, "citations": [item]}})
        first = st["cruxes"]["C1"]["p_history"][-1]
        crux_engine.submit_round(st, 2, {"C1": {"signal": 1, "citations": [item]}})
        cx = st["cruxes"]["C1"]
        self.assertEqual(len(cx["citations"]), 1)
        self.assertEqual(cx["p_history"][-1], first)
        flags = st["rounds"][-1]["signals"]["C1"]["quality_flags"]
        self.assertIn("dropped_duplicate_evidence:1", flags)
        self.assertIn("signal_zeroed_no_valid_citation", flags)

    def test_zero_signal_carries_forward_support_without_decay(self):
        st = state()
        crux_engine.submit_round(
            st, 1, {"C1": {"signal": 1, "citations": [citation("new-evidence")]}}
        )
        before = st["cruxes"]["C1"]["p_history"][-1]
        before_log_odds = st["cruxes"]["C1"]["L"]

        crux_engine.submit_round(
            st, 2, {"C1": {"signal": 0, "rationale": "no new evidence", "citations": []}}
        )

        cx = st["cruxes"]["C1"]
        self.assertEqual(cx["p_history"][-1], before)
        self.assertEqual(cx["L"], before_log_odds)
        self.assertNotIn("C1", st["rounds"][-1]["fired_cruxes"])

    def test_independent_evidence_can_retire_a_crux(self):
        st = state()
        for r, signal in ((1, 1.0), (2, 1.0), (3, 0.2)):
            crux_engine.submit_round(
                st, r, {"C1": {"signal": signal, "citations": [citation(f"r{r}", claim=f"c{r}")]}}
            )
        self.assertTrue(st["cruxes"]["C1"]["retired"])
        self.assertEqual(st["cruxes"]["C1"]["status"], "RESOLVED_BULL")


class OrchestratorTests(unittest.TestCase):
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

    def frame(self):
        return {
            "decision_question": "test", "horizon": "3-6M", "as_of_date": "2026-07-11",
            "question_type": "CONJUNCTIVE",
            "logic_graph": {
                "root_id": "Q1",
                "nodes": [
                    {"id": "Q1", "node_type": "QUESTION", "label": "test"},
                    {"id": "C1", "node_type": "CRUX", "label": "c1"},
                    {"id": "C2", "node_type": "CRUX", "label": "c2"},
                ],
                "edges": [
                    {"from": "C1", "to": "Q1", "relation": "REQUIRED_FOR"},
                    {"from": "C2", "to": "Q1", "relation": "REQUIRED_FOR"},
                ],
            },
            "unit_of_analysis": "test assets",
            "thesis_seed": "If P1 holds, the test may reveal an edge.",
            "premise_audit": [{
                "id": "P1", "claim": "seed premise", "status": "HYPOTHESIS",
                "as_of": "UNKNOWN", "source_url": None,
                "required_primary_source": "issuer filing", "use": "scope the cruxes",
            }],
            "candidate_cruxes": [
                {"id": "C1", "label": "c1", "logic_role": "THESIS_HINGE",
                 "definition": "d1", "monitor_anchor": "m1",
                 "evidence_plan": evidence_plan("C1"),
                 "falsifier": "f1", "catalyst_window": {
                     "event": "e1", "expected_by": "2026-10-31",
                     "date_status": "REVIEW_CHECKPOINT", "basis_claim_id": "P1"}},
                {"id": "C2", "label": "c2", "logic_role": "THESIS_HINGE",
                 "definition": "d2", "monitor_anchor": "m2",
                 "evidence_plan": evidence_plan("C2"),
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

    def test_frame_command_declares_inline_only_artifact_policy(self):
        result = orchestrator.cmd_frame("test")
        self.assertEqual(result["artifact_policy"]["mode"], "inline_only")
        self.assertIn("禁止创建 Markdown", result["framer_prompt"])

    def test_frame_command_physically_forbids_subagent_dispatch(self):
        result = orchestrator.cmd_frame("test")
        contract = result["execution_contract"]
        self.assertEqual(contract["dispatch_mode"], "INLINE_PARENT")
        self.assertFalse(contract["subagent_dispatch_allowed"])
        self.assertFalse(contract["tool_calls_allowed"])
        self.assertFalse(contract["isolation_required"])
        self.assertIn("Do not call define_subagent", result["framer_prompt"])

    def test_preinit_runtime_failure_is_nonformal_and_bounded(self):
        result = orchestrator.cmd_runtime_failure(
            "failed-frame", "framing", "timeout " + ("x" * 2000)
        )
        self.assertEqual(result["status"], "blocked_runtime_failure")
        self.assertFalse(result["formal_report_allowed"])
        self.assertFalse(result["state_initialized"])
        memo = result["runtime_failure_memo_markdown"]
        self.assertIn("非研究结论", memo)
        self.assertIn("framing", memo)
        self.assertLess(len(memo), 1200)

    def test_init_rejects_legacy_unaudited_frame(self):
        result = orchestrator.cmd_init("legacy-frame", {
            "decision_question": "test", "horizon": "3-6M", "thesis_seed": "asserted fact",
            "candidate_cruxes": [{"id": "C1", "label": "c", "monitor_anchor": "m"}],
            "no_edge_precheck": {"is_researchable": True},
        })
        self.assertEqual(result["status"], "frame_rejected")
        self.assertIn("premise_audit_required", result["issues"])
        self.assertIsNone(orchestrator._load("legacy-frame"))

    def test_sourced_status_is_forbidden_during_framing(self):
        frame = self.frame()
        frame["premise_audit"][0].update({
            "status": "SOURCED", "source_url": "https://fixture-research.org", "as_of": "2026-07-11",
        })
        result = orchestrator.cmd_init("bad-source", frame)
        self.assertEqual(result["status"], "frame_rejected")
        self.assertIn("premise_1_invalid_status", result["issues"])

    def test_url_claim_stays_unverified_and_requires_concrete_url(self):
        frame = self.frame()
        frame["premise_audit"][0].update({
            "status": "URL_CLAIMED_UNVERIFIED", "source_url": "https://fixture-research.org",
            "as_of": "2026-07-11",
        })
        result = orchestrator.cmd_init("bad-url-claim", frame)
        self.assertEqual(result["status"], "frame_rejected")
        self.assertIn("premise_1_url_claim_requires_concrete_url", result["issues"])

    def test_catalyst_requires_future_iso_date_within_horizon(self):
        frame = self.frame()
        frame["candidate_cruxes"][0]["catalyst_window"]["expected_by"] = "2025-Q4"
        result = orchestrator.cmd_init("bad-catalyst", frame)
        self.assertEqual(result["status"], "frame_rejected")
        self.assertIn("crux_1_catalyst_expected_by_requires_iso_date", result["issues"])

    def test_catalyst_requires_premise_binding(self):
        frame = self.frame()
        frame["candidate_cruxes"][0]["catalyst_window"].pop("basis_claim_id")
        result = orchestrator.cmd_init("unbound-catalyst", frame)
        self.assertEqual(result["status"], "frame_rejected")
        self.assertIn("crux_1_catalyst_basis_claim_id_required", result["issues"])

    def test_init_preserves_provisional_frame_contract(self):
        result = orchestrator.cmd_init("provisional", self.frame())
        self.assertEqual(result["status"], "dispatch_subagents")
        stored = orchestrator._load("provisional")
        self.assertEqual(stored["frame_contract"]["quality_status"], "PROVISIONAL_UNVERIFIED")
        self.assertEqual(stored["cruxes"]["C1"]["falsifier"], "f1")
        self.assertEqual(stored["cruxes"]["C1"]["catalyst_window"]["expected_by"], "2026-10-31")
        self.assertEqual(stored["question_type"], "CONJUNCTIVE")
        self.assertEqual(stored["logic_graph"]["root_id"], "Q1")
        self.assertEqual(
            stored["method_identity"]["schema_version"],
            "trade-nothing.method-identity.v1",
        )

    def test_low_level_state_load_rejects_method_identity_drift(self):
        orchestrator.cmd_init("drifted-method", self.frame())
        path = orchestrator._path("drifted-method")
        stored = utils.load_json_safe(path, default={})
        stored["method_identity"]["contract_sha256"] = "0" * 64
        utils.save_json(path, stored)
        with self.assertRaisesRegex(ValueError, "method_contract_drift"):
            orchestrator._load("drifted-method")

    def test_framer_cannot_self_attest_runtime_isolation(self):
        frame = self.frame()
        frame["isolation_status"] = "verified"
        orchestrator.cmd_init("ignored-frame-isolation", frame)
        stored = orchestrator._load("ignored-frame-isolation")
        self.assertEqual(stored["runtime_contract"]["isolation_status"], "unverified")
        self.assertEqual(
            stored["runtime_contract"]["frame_isolation_claim_ignored"], "verified"
        )
        orchestrator.cmd_init("host-runtime-isolation", frame, runtime_isolation="verified")
        host_stored = orchestrator._load("host-runtime-isolation")
        self.assertEqual(host_stored["runtime_contract"]["isolation_status"], "verified")

    def test_universe_search_without_pricing_crux_is_rejected(self):
        frame = self.frame()
        frame["question_type"] = "UNIVERSE_SEARCH"
        for crux in frame["candidate_cruxes"]:
            crux["logic_role"] = "OPPORTUNITY_PATH"
        result = orchestrator.cmd_init("universe-without-pricing", frame)
        self.assertEqual(result["status"], "frame_rejected")
        self.assertIn("universe_search_requires_pricing_crux", result["issues"])

    def test_disconnected_logic_graph_is_rejected(self):
        frame = self.frame()
        frame["logic_graph"]["edges"] = [
            {"from": "C1", "to": "Q1", "relation": "REQUIRED_FOR"},
        ]
        result = orchestrator.cmd_init("disconnected-graph", frame)
        self.assertEqual(result["status"], "frame_rejected")
        self.assertIn("logic_graph_cruxes_not_connected_to_root:C2", result["issues"])

    def test_state_uses_scratch_and_collision_resistant_slug(self):
        a = "a" * 80 + "x"
        b = "a" * 80 + "y"
        self.assertTrue(orchestrator._path(a).startswith(self.tmp.name))
        self.assertNotEqual(orchestrator._path(a), orchestrator._path(b))

    def test_dynamic_dispatch_bounds_cruxes_and_prioritizes_untested_without_starvation(self):
        st = crux_engine.new_state(
            "bounded", "bounded", "3-6M",
            [
                {"id": "C1", "label": "one"},
                {"id": "C2", "label": "two"},
                {"id": "C3", "label": "three"},
            ],
        )
        first = orchestrator.dispatch_prompts(st, 1)
        self.assertEqual(first["open_cruxes"], ["C1", "C2", "C3"])
        self.assertEqual(first["dispatch_cruxes"], ["C1", "C2"])
        self.assertEqual(first["round_policy"]["deferred_open_cruxes"], ["C3"])
        # v0.13: static directives moved to agent.md; verify prompt carries dynamic state
        self.assertIn("本轮调度: free_roam=false", first["detective_prompt"])
        self.assertIn("本轮处理: ['C1', 'C2']", first["detective_prompt"])

        st["cruxes"]["C1"]["first_contested"] = 1
        st["cruxes"]["C2"]["first_contested"] = 1
        st["rounds"] = [{
            "round": 1,
            "judge_raw": {"crux_signals": {"C1": {}, "C2": {}}},
        }]
        second = orchestrator.dispatch_prompts(st, 2)
        self.assertEqual(second["dispatch_cruxes"][0], "C3")
        self.assertEqual(len(second["dispatch_cruxes"]), 2)

    def test_probe_audit_rejects_role_claims_outside_host_dispatch(self):
        st = crux_engine.new_state(
            "scope",
            "scope",
            "3-6M",
            [
                {"id": "C1", "label": "one"},
                {"id": "C2", "label": "two"},
                {"id": "C3", "label": "deferred"},
            ],
        )
        detective = {
            "crux_evidence": [
                {"crux_id": cid, "evidence": []}
                for cid in ("C1", "C2", "C3")
            ]
        }
        inquisitor = {
            "crux_attacks": [
                {"crux_id": cid, "attacks": []}
                for cid in ("C1", "C2", "C3")
            ]
        }
        audit = orchestrator._crux_probe_audit(
            st,
            detective,
            inquisitor,
            dispatch_cruxes=["C1", "C2"],
        )
        self.assertEqual(set(audit), {"C1", "C2"})
        self.assertNotIn("C3", audit)

    def test_agent_evidence_novelty_survives_judge_omission_and_resume(self):
        st = crux_engine.new_state(
            "resume", "resume", "3-6M", [{"id": "C1", "label": "one"}],
        )
        ev = citation("resume-source")
        detective = {
            "crux_evidence": [{"crux_id": "C1", "evidence": [ev]}]
        }
        inquisitor = {
            "crux_attacks": [{"crux_id": "C1", "attacks": []}]
        }
        first = orchestrator._crux_probe_audit(
            st, detective, inquisitor, dispatch_cruxes=["C1"]
        )
        self.assertEqual(first["C1"]["new_valid_evidence_count"], 1)
        second = orchestrator._crux_probe_audit(
            st, detective, inquisitor, dispatch_cruxes=["C1"]
        )
        self.assertEqual(second["C1"]["new_valid_evidence_count"], 0)

        legacy = crux_engine.new_state(
            "legacy", "legacy", "3-6M", [{"id": "C1", "label": "one"}],
        )
        legacy["rounds"] = [{
            "round": 1,
            "detective_raw": detective,
            "inquisitor_raw": inquisitor,
            "judge_raw": {"crux_signals": {"C1": {
                "signal": 0.0, "citations": [],
            }}},
        }]
        self.assertEqual(orchestrator._backfill_seen_agent_evidence_keys(legacy), 1)
        resumed = orchestrator._crux_probe_audit(
            legacy, detective, inquisitor, dispatch_cruxes=["C1"]
        )
        self.assertEqual(resumed["C1"]["new_valid_evidence_count"], 0)

    def test_evolution_path_falls_back_to_nonempty_configured_vault(self):
        with tempfile.TemporaryDirectory() as root:
            skill_dir = os.path.join(root, "skill")
            vault_dir = os.path.join(root, "vault")
            os.makedirs(skill_dir)
            with open(
                os.path.join(skill_dir, "Methodology_Evolution.md"),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write("# stale installed memory\n")
            memory_dir = os.path.join(vault_dir, "Methodology")
            os.makedirs(memory_dir)
            memory_path = os.path.join(memory_dir, "Evolution.md")
            with open(memory_path, "w", encoding="utf-8") as handle:
                handle.write("# active memory\n")
            old_skill = os.environ.get("TRADE_NOTHING_SKILL_DIR")
            old_vault = os.environ.get("TRADE_NOTHING_VAULT_DIR")
            old_evolution = os.environ.pop("TRADE_NOTHING_EVOLUTION_PATH", None)
            os.environ["TRADE_NOTHING_SKILL_DIR"] = skill_dir
            os.environ["TRADE_NOTHING_VAULT_DIR"] = vault_dir
            try:
                self.assertEqual(utils.get_evolution_path(), memory_path)
            finally:
                if old_skill is None:
                    os.environ.pop("TRADE_NOTHING_SKILL_DIR", None)
                else:
                    os.environ["TRADE_NOTHING_SKILL_DIR"] = old_skill
                if old_vault is None:
                    os.environ.pop("TRADE_NOTHING_VAULT_DIR", None)
                else:
                    os.environ["TRADE_NOTHING_VAULT_DIR"] = old_vault
                if old_evolution is not None:
                    os.environ["TRADE_NOTHING_EVOLUTION_PATH"] = old_evolution

    def test_configured_fuse_blocks_formal_report(self):
        topic = "configured-fuse"
        orchestrator.cmd_init(topic, self.frame())
        empty_agent = {"crux_evidence": []}
        for _ in range(3):
            result = orchestrator.cmd_submit(
                topic, empty_agent, {"crux_attacks": []},
                {"crux_signals": {"C1": {"signal": 0, "citations": []}}, "new_cruxes": []},
            )
        self.assertEqual(result["status"], "blocked_max_rounds")
        self.assertFalse(result["formal_report_allowed"])
        self.assertIn("未收敛研究备忘录", result["resolution_memo_markdown"])
        self.assertEqual(result["continuation_packet"]["dispatch_policy"]["crux_ids"], ["C1", "C2"])
        self.assertLess(research_output.assert_compact_packet(result["continuation_packet"]), 32768)
        # The run still delivers its research; the grade and the publication gate
        # carry the limitation instead of erasing the report.
        degraded = orchestrator.cmd_report(topic)
        self.assertEqual(degraded["status"], "report_data_ready")
        self.assertEqual(degraded["report_grade"], "EXPLORATORY")
        self.assertFalse(degraded["formal_report_allowed"])
        self.assertFalse(degraded["publication_allowed"])
        self.assertFalse(degraded["ranking_allowed"])
        self.assertIn("CONVERGENCE", degraded["unmet_gates"])
        self.assertIn("未收敛研究备忘录", degraded["resolution_memo_markdown"])
        refused = orchestrator.cmd_submit(
            topic, {"crux_evidence": []}, {"crux_attacks": []},
            {"crux_signals": {}, "new_cruxes": []},
        )
        self.assertEqual(refused["status"], "resume_requires_explicit_extension")
        self.assertEqual(orchestrator.cmd_resume_blocked(topic)["status"],
                         "resume_requires_explicit_extension")
        resumed = orchestrator.cmd_resume_blocked(topic, 2)
        self.assertEqual(resumed["status"], "dispatch_subagents")
        self.assertEqual(resumed["open_cruxes"], ["C1", "C2"])
        self.assertFalse(resumed["round_policy"]["free_roam_allowed"])

    def test_late_new_crux_is_deferred_instead_of_blocking_current_run(self):
        topic = "late-crux"
        frame = self.frame()
        frame["suggested_max_rounds"] = 6
        orchestrator.cmd_init(topic, frame)
        for _ in range(3):
            orchestrator.cmd_submit(
                topic, {"crux_evidence": []}, {"crux_attacks": []},
                {"crux_signals": {}, "new_cruxes": []},
            )
        new_crux = {
            "id": "C3", "label": "late", "definition": "late dispute",
            "monitor_anchor": "late observable", "falsifier": "late falsifier",
            "catalyst_window": {
                "event": "late event", "expected_by": "2026-11-30",
                "date_status": "REVIEW_CHECKPOINT", "basis_claim_id": "P1",
            },
        }
        result = orchestrator.cmd_submit(
            topic, {"crux_evidence": []}, {"crux_attacks": []},
            {"crux_signals": {}, "new_cruxes": [new_crux]},
        )
        stored = orchestrator._load(topic)
        self.assertNotIn("C3", stored["cruxes"])
        self.assertIn("new_crux_introduced_after_cutoff",
                      result["deferred_new_cruxes"][0]["reason_codes"])

    def test_new_crux_requires_same_round_scoped_attack_and_exact_citation(self):
        topic = "admissible-new-crux"
        frame = self.frame()
        frame["suggested_max_rounds"] = 6
        orchestrator.cmd_init(topic, frame)
        evidence = {
            **citation(
                "new-crux-attack",
                claim="A same-round attack reveals a distinct causal hinge.",
            ),
            "attack": "The original C1 omits a distinct causal hinge.",
        }
        new_crux = {
            "id": "C3",
            "label": "distinct hinge",
            "logic_role": "THESIS_HINGE",
            "definition": "A distinct hinge exposed by the C1 attack",
            "monitor_anchor": "one observable C3 event",
            "falsifier": "the C3 event does not occur",
            "catalyst_window": {
                "event": "C3 review checkpoint",
                "expected_by": "2026-11-30",
                "date_status": "REVIEW_CHECKPOINT",
                "basis_claim_id": "P1",
            },
            "source_attack_crux_id": "C1",
            "supporting_citation": evidence,
        }
        result = orchestrator.cmd_submit(
            topic,
            {"crux_evidence": []},
            {
                "crux_attacks": [{
                    "crux_id": "C1",
                    "attacks": [evidence],
                }]
            },
            {"crux_signals": {}, "new_cruxes": [new_crux]},
        )
        self.assertEqual(result["admitted_new_cruxes"], ["C3"])
        stored = orchestrator._load(topic)
        self.assertIn("C3", stored["cruxes"])
        self.assertEqual(
            stored["cruxes"]["C3"]["admission_receipt"][
                "source_attack_crux_id"
            ],
            "C1",
        )
        self.assertEqual(len(stored["cruxes"]["C3"]["citations"]), 1)

    def test_hypothesis_only_or_out_of_scope_new_crux_is_deferred(self):
        topic = "inadmissible-new-crux"
        frame = self.frame()
        frame["suggested_max_rounds"] = 6
        orchestrator.cmd_init(topic, frame)
        bare = {
            "id": "C3",
            "label": "unsupported idea",
            "logic_role": "THESIS_HINGE",
            "definition": "A merely hypothesized hinge",
            "monitor_anchor": "one future event",
            "falsifier": "the event does not occur",
            "catalyst_window": {
                "event": "review unsupported idea",
                "expected_by": "2026-11-30",
                "date_status": "REVIEW_CHECKPOINT",
                "basis_claim_id": "P1",
            },
        }
        result = orchestrator.cmd_submit(
            topic,
            {"crux_evidence": []},
            {"crux_attacks": []},
            {"crux_signals": {}, "new_cruxes": [bare]},
        )
        reasons = result["deferred_new_cruxes"][0]["reason_codes"]
        self.assertIn("new_crux_missing_source_attack_crux_id", reasons)
        self.assertIn("new_crux_missing_supporting_citation", reasons)

        evidence = {
            **citation(
                "outside-scope-attack",
                claim="An attack was submitted outside host dispatch.",
            ),
            "attack": "outside scope",
        }
        outside = {
            **bare,
            "id": "C4",
            "source_attack_crux_id": "C9",
            "supporting_citation": evidence,
        }
        result = orchestrator.cmd_submit(
            topic,
            {"crux_evidence": []},
            {
                "crux_attacks": [{
                    "crux_id": "C9",
                    "attacks": [evidence],
                }]
            },
            {"crux_signals": {}, "new_cruxes": [outside]},
        )
        reasons = result["deferred_new_cruxes"][0]["reason_codes"]
        self.assertIn("new_crux_source_attack_outside_round_scope", reasons)

    def test_pending_crux_disables_free_roam_reopen_signal(self):
        topic = "scope-priority"
        orchestrator.cmd_init(topic, self.frame())
        stored = orchestrator._load(topic)
        stored["cruxes"]["C2"].update({"retired": True, "status": "RESOLVED_BEAR"})
        orchestrator._save(topic, stored)
        ev = citation("retired-free-roam", claim="retired attack")
        result = orchestrator.cmd_submit(
            topic,
            {"crux_evidence": []},
            {"crux_attacks": [{"crux_id": "C2", "attacks": [{**ev, "attack": "new attack"}]}]},
            {"crux_signals": {"C2": {"signal": -1, "citations": [{**ev, "attack": "new attack"}]}},
             "new_cruxes": []},
        )
        stored = orchestrator._load(topic)
        self.assertNotIn("C2", stored["rounds"][-1]["fired_cruxes"])
        self.assertIn("signal_zeroed_outside_round_scope",
                      stored["rounds"][-1]["signals"]["C2"]["quality_flags"])
        self.assertFalse(result["round_policy"]["free_roam_allowed"])

    def test_judge_cannot_invent_a_citation(self):
        real = citation("real", claim="real")
        invented = citation("invented", claim="invented")
        detective = {"crux_evidence": [{"crux_id": "C1", "evidence": [real]}]}
        cleaned = orchestrator._sanitize_judge_for_agent_support(
            {"crux_signals": {"C1": {"signal": 1, "citations": [invented]}}},
            detective, {"crux_attacks": []},
        )
        signal = cleaned["crux_signals"]["C1"]
        self.assertEqual(signal["signal"], 0.0)
        self.assertEqual(signal["citations"], [])
        self.assertIn("dropped_judge_invented_citations:1", signal["quality_flags"])

    def test_converged_state_without_sources_is_provisional_not_publishable(self):
        topic = "legacy-evidence-gate"
        st = state()
        st["last_convergence"] = {"decision": "converge"}
        st["cruxes"]["C1"]["status"] = "RESOLVED_BULL"
        st["decision_trace"].append({
            "round": 3, "weakest": "C1", "p_weakest": 0.6, "p_mean": 0.6,
            "support_weakest": 0.6, "support_mean": 0.6, "decision": "RESEARCH_READY",
        })
        orchestrator._save(topic, st)
        result = orchestrator.cmd_report(topic)
        self.assertEqual(result["status"], "report_data_ready")
        self.assertEqual(result["report_grade"], "PROVISIONAL")
        self.assertIn("CRUX_SOURCE_MINIMUM", result["unmet_gates"])
        self.assertFalse(result["publication_allowed"])
        self.assertIn("C1", result["claim_tiers"]["HYPOTHESIS"])


class ReportSafetyTests(unittest.TestCase):
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

    def test_full_report_leads_with_decision_brief_and_defers_audit(self):
        md = report_v2.render(converged_state())
        self.assertTrue(md.startswith("# Decision Brief"))
        self.assertLess(md.index("# Insight Cards"), md.index("# Candidate Cards"))
        self.assertLess(md.index("# Candidate Cards"), md.index("# Audit Appendix"))
        self.assertLess(md.index("# Audit Appendix"), md.index("## A · 证明账本"))
        self.assertIn("<details><summary>展开完整证据、状态、来源与运行审计</summary>", md)

    def test_report_view_model_excludes_raw_role_payloads(self):
        st = converged_state()
        st["rounds"] = [{
            "round": 1,
            "detective_raw": {"private": "do not expose"},
            "inquisitor_raw": {"private": "do not expose"},
        }]
        model = report_v2.build_report_view_model(st)
        encoded = json.dumps(model, ensure_ascii=False)
        self.assertEqual(model["schema_version"], "trade-nothing.report-view-model.v2")
        self.assertNotIn("do not expose", encoded)
        self.assertNotIn("detective_raw", encoded)
        self.assertEqual(model["next_action"]["code"], "STOP_NO_PROMOTABLE_CANDIDATE")
        self.assertEqual(model["formal_action"]["code"], "STOP_NO_PROMOTABLE_CANDIDATE")
        self.assertEqual(
            model["exploration_action"]["authority"],
            "RESEARCH_ONLY_NO_PROMOTION",
        )

    def test_each_report_view_uses_same_three_axis_verdict(self):
        st = converged_state()
        model = report_v2.build_report_view_model(st)
        brief = report_v2.render(st, view="brief")
        full = report_v2.render(st, view="full")
        for value in model["verdict"].values():
            self.assertIn(str(value), brief)
            self.assertIn(str(value), full)

    def test_facts_box_locks_core_facts_in_under_forty_lines(self):
        st = converged_state()
        st["topic"] = "test <!-- FACTS_BOX_END -->"
        st["as_of_date"] = "2026-07-31"
        st["runtime_contract"] = {"isolation_status": "verified"}
        st["rounds"] = [{"round": 1}, {"round": 2}, {"round": 3}]
        st["cruxes"]["C1"].update({
            "label": "binding | constraint",
            "status": "MONITORABLE",
            "retired": True,
            "best_bull": "bull | case " + ("x" * 100),
            "best_bear": "bear | case",
            "citations": [citation("facts-a"), citation("facts-b")],
        })
        model = report_v2.build_report_view_model(st)
        facts = report_v2.render(st, view="facts_box")
        self.assertLess(len(facts.splitlines()), 40)
        self.assertIn("<!-- FACTS_BOX_START", facts)
        self.assertIn("<!-- FACTS_BOX_END -->", facts)
        self.assertEqual(facts.count("<!-- FACTS_BOX_START"), 1)
        self.assertEqual(facts.count("<!-- FACTS_BOX_END -->"), 1)
        self.assertIn("FACTS-BOX-END", facts)
        self.assertIn("**证据截止**: 2026-07-31", facts)
        self.assertIn("隔离=verified", facts)
        self.assertIn(r"C1 binding \| constraint", facts)
        self.assertIn(r"bull \| case", facts)
        self.assertIn("MONITORABLE", facts)
        self.assertIn("完整证据账本见配套 Evidence Ledger 文件", facts)
        for key in ("edge_state", "evidence_direction", "actionability"):
            self.assertIn(str(model["verdict"][key]), facts)
        if "temporal_contract" in model:
            self.assertIn("**时间合同**", facts)
            self.assertIn("**预测目标**: RELATIVE_HORIZON", facts)
        self.assertIn(model["formal_action"]["code"], facts)
        self.assertNotIn("# Insight Cards", facts)
        self.assertNotIn("# Audit Appendix", facts)

    def test_report_cli_accepts_facts_box_view(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", encoding="utf-8"
        ) as state_handle:
            json.dump(converged_state(), state_handle)
            state_handle.flush()
            completed = subprocess.run(
                [
                    sys.executable,
                    report_v2.__file__,
                    "--state",
                    state_handle.name,
                    "--view",
                    "facts_box",
                ],
                check=True,
                capture_output=True,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        self.assertIn("<!-- FACTS_BOX_START", completed.stdout)
        self.assertNotIn("# Audit Appendix", completed.stdout)

    def test_universe_report_recomputes_root_verdict_and_hides_global_support_aggregates(self):
        st = converged_state()
        st["question_type"] = "UNIVERSE_SEARCH"
        st["cruxes"]["C1"]["logic_role"] = "OPPORTUNITY_PATH"
        st["landscape_map"] = {"paths": [{
            "path_id": "L1", "state": "SUPPORTED",
            "probes": {
                "detective": {"round": 1, "state": "SUPPORTED"},
                "inquisitor": {"round": 1, "state": "SUPPORTED"},
            },
        }]}
        st["decision_trace"][-1]["research_verdict"] = {
            "edge_state": "INSUFFICIENT_EVIDENCE", "evidence_direction": "BEAR",
            "actionability": "MONITOR", "question_type": "UNIVERSE_SEARCH",
            "reason_code": "STALE_GLOBAL_AGGREGATE",
        }
        md = report_v2.render(st)
        facts = report_v2.render(st, view="facts_box")
        self.assertIn("INSUFFICIENT_EVIDENCE / UNDETERMINED / MONITOR", md)
        self.assertNotIn("INSUFFICIENT_EVIDENCE / BEAR / MONITOR", md)
        self.assertNotIn("最低路径支持度", md)
        self.assertNotIn("命题均值支持度", md)
        self.assertIn("Landscape 双边覆盖 + 候选收割静默", md)
        self.assertIn("## 研究轴证据状态", md)
        self.assertIn("不构成候选宇宙的整体多空方向", md)
        self.assertNotIn("## 原想法经质证后发生了什么", md)
        self.assertIn("**研究轴质证**", facts)
        self.assertNotIn("**经质证后**", facts)
        self.assertIn("**发现路径覆盖**", facts)

    def test_validator_rejects_rendered_verdict_drift_from_state(self):
        st = converged_state()
        st["cruxes"]["C1"].update({
            "status": "MONITORABLE", "retired": True, "first_contested": 1,
            "citations": [citation("drift-a"), citation("drift-b")],
        })
        md = report_v2.render(st).replace(
            "证据方向: **UNDETERMINED**", "证据方向: **BEAR**"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as report_handle, \
                tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as state_handle:
            report_handle.write(md)
            report_handle.flush()
            json.dump(st, state_handle)
            state_handle.flush()
            errors, _ = validate_report_v2.validate_report(
                report_handle.name, state_handle.name
            )
        self.assertTrue(any("does not match" in item for item in errors))

    def test_validator_accepts_exact_facts_box_with_free_narrative(self):
        st = converged_state()
        facts = report_v2.render(st, view="facts_box")
        md = (
            facts
            + "\n\n# 供需矛盾决定下一步\n\n"
            + "这段叙事可以按本次发现自由组织，不需要旧模板标题。\n"
        )
        with tempfile.NamedTemporaryFile(
            "w", suffix=".md", encoding="utf-8"
        ) as report_handle, tempfile.NamedTemporaryFile(
            "w", suffix=".json", encoding="utf-8"
        ) as state_handle:
            report_handle.write(md)
            report_handle.flush()
            json.dump(st, state_handle)
            state_handle.flush()
            errors, _ = validate_report_v2.validate_report(
                report_handle.name, state_handle.name
            )
        self.assertEqual(errors, [])

    def test_validator_rejects_facts_box_drift_or_duplicate_markers(self):
        st = converged_state()
        facts = report_v2.render(st, view="facts_box")
        expected_action = report_v2.build_report_view_model(st)["formal_action"]["code"]
        drifted = facts.replace(
            f"`{expected_action}`", "`RUN_CANDIDATE_SCREEN`", 1
        )
        duplicate = facts + "\n" + facts
        for md, expected_error in (
            (drifted, "Facts Box differs"),
            (duplicate, "exactly one ordered START/END"),
        ):
            with tempfile.NamedTemporaryFile(
                "w", suffix=".md", encoding="utf-8"
            ) as report_handle, tempfile.NamedTemporaryFile(
                "w", suffix=".json", encoding="utf-8"
            ) as state_handle:
                report_handle.write(md)
                report_handle.flush()
                json.dump(st, state_handle)
                state_handle.flush()
                errors, _ = validate_report_v2.validate_report(
                    report_handle.name, state_handle.name
                )
            self.assertTrue(
                any(expected_error in item for item in errors),
                msg=f"missing {expected_error}: {errors}",
            )

    def test_official_gov_record_counts_as_primary_source(self):
        st = converged_state()
        st["cruxes"]["C1"]["citations"] = [{
            "claim": "official filing", "number": "1", "source": "SEC",
            "url": "https://www.sec.gov/Archives/edgar/data/1/filing.htm",
            "date": "2026-07-15",
        }]
        self.assertEqual(crux_engine.report_data(st)["n_primary_sources"], 1)

    def test_report_rejects_unknown_view(self):
        with self.assertRaisesRegex(ValueError, "unknown report view"):
            report_v2.render(converged_state(), view="raw-transcript")

    def test_report_has_no_sizing_or_numeric_scenario_request(self):
        md = report_v2.render(converged_state())
        self.assertNotIn("Half-Kelly", md)
        self.assertNotIn("建议仓位", md)
        self.assertNotIn("| 概率 |", md)
        self.assertNotIn("回报预期", md)
        self.assertIn("辩论支持度", md)
        self.assertIn("不是交易指令", md)
        self.assertNotIn("NO_EDGE / AVOID", md)
        self.assertNotIn("全量工作数据", md)
        self.assertNotIn("detective_raw", md)
        self.assertNotIn("待 deep 模型写入", md)

    def test_unconverged_render_is_delivered_but_graded_exploratory(self):
        md = report_v2.render(state())
        self.assertIn("EXPLORATORY", md)
        self.assertIn("对外发布=False", md)
        self.assertIn("个股排序=False", md)

    def test_compact_formal_report_passes_validator_without_raw_bundle(self):
        st = converged_state()
        st["cruxes"]["C1"].update({
            "first_contested": 1,
            "contested_history": [0.5, 0.5, 0.5],
            "status": "MONITORABLE",
            "retired": True,
            "best_bull": "bull evidence",
            "best_bear": "bear evidence",
            "falsifier": "observable reversal",
            "citations": [citation("formal-a"), citation("formal-b")],
        })
        md = report_v2.render(st)
        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as handle:
            handle.write(md)
            handle.flush()
            errors, warnings = validate_report_v2.validate_report(handle.name)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_report_validator_rejects_legacy_no_edge_avoid_semantics(self):
        st = converged_state()
        md = report_v2.render(st) + "\nNO_EDGE / AVOID\n"
        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as handle:
            handle.write(md)
            handle.flush()
            errors, _ = validate_report_v2.validate_report(handle.name)
        self.assertTrue(any("semantic leak" in item for item in errors))

    def test_validator_separates_report_validity_from_blocked_promotion(self):
        st = converged_state()
        st["cruxes"]["C1"].update({
            "first_contested": 1,
            "contested_history": [0.5, 0.5, 0.5],
            "status": "MONITORABLE",
            "retired": True,
            "citations": [citation("state-a"), citation("state-b")],
        })
        st["opportunity_seeds"] = [{
            "seed_id": "OS-MISSING-ANCHOR",
            "candidate": "Unscreened Asset",
            "ticker": "UA",
            "asset_type": "LISTED_EQUITY",
            "relation_type": "BOTTLENECK_OWNER",
            "origin_crux": "C1",
            "causal_path": "constraint -> rent -> owner",
            "economic_exposure": "owner captures rent",
            "why_market_may_miss": "coverage misses the segment",
            "pricing_anchor": "",
            "catalyst": "contract filing",
            "catalyst_window": {"event": "contract filing", "expected_by": "2026-10-10", "date_status": "REVIEW_CHECKPOINT"},
            "falsifier": "contract fails",
            "evidence": [citation("seed-a"), citation("seed-b")],
        }]
        md = report_v2.render(st)
        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as report_handle, \
                tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as state_handle:
            report_handle.write(md)
            report_handle.flush()
            json.dump(st, state_handle)
            state_handle.flush()
            outcome = validate_report_v2.validate_report_outcomes(
                report_handle.name, state_handle.name
            )
        self.assertTrue(outcome["report_render_valid"])
        self.assertTrue(outcome["research_state_valid"])
        self.assertEqual(outcome["promotion_eligibility"][0]["promotion_eligibility"], "BLOCKED")
        self.assertIn("missing_structured_pricing_anchor", outcome["promotion_eligibility"][0]["blocking_reasons"])

    def test_report_exposes_provisional_framing_premises(self):
        st = converged_state()
        st["frame_contract"] = {
            "quality_status": "PROVISIONAL_UNVERIFIED",
            "as_of_date": "2026-07-11",
            "unit_of_analysis": "test assets",
            "premise_audit": [{
                "id": "P1", "claim": "unverified seed", "status": "HYPOTHESIS",
                "as_of": "UNKNOWN", "required_primary_source": "issuer filing",
                "use": "scope the research",
            }],
            "artifact_policy": orchestrator._frame_artifact_policy(),
        }
        md = report_v2.render(st)
        self.assertIn("## 0.1 · 立题完整性闸", md)
        self.assertIn("PROVISIONAL_UNVERIFIED", md)
        self.assertIn("unverified seed", md)
        self.assertIn("requires_explicit_user_opt_in", md)

    def test_orchestrator_can_emit_brief_without_synthesis_packet(self):
        topic = "brief report view"
        st = converged_state()
        st["cruxes"]["C1"].update({
            "status": "MONITORABLE",
            "retired": True,
            "first_contested": 1,
            "contested_history": [0.5, 0.5, 0.5],
            "citations": [citation("brief-a"), citation("brief-b")],
        })
        orchestrator._save(topic, st)
        out = orchestrator.cmd_report(
            topic, challenge_only=True, report_view="brief", include_synthesis=False
        )
        self.assertEqual(out["status"], "report_data_ready")
        self.assertEqual(out["report_view"], "brief")
        self.assertTrue(out["report_markdown"].startswith("# Decision Brief"))
        self.assertNotIn("# Audit Appendix", out["report_markdown"])
        self.assertNotIn("synthesis_packet", out)
        self.assertIn("facts_box", out["available_report_views"])
        self.assertIn("<!-- FACTS_BOX_START", out["facts_box_markdown"])
        self.assertEqual(
            out["facts_box_sha256"],
            hashlib.sha256(out["facts_box_markdown"].encode("utf-8")).hexdigest(),
        )
        self.assertTrue(out["candidate_cards_markdown"].startswith("# Candidate Cards"))
        self.assertIn("## A · 证明账本", out["evidence_ledger_markdown"])
        self.assertTrue(out["report_markdown_deprecated"])
        self.assertIn("两个主文件", out["instruction"])
        self.assertEqual(
            out["report_view_model"]["schema_version"],
            "trade-nothing.report-view-model.v2",
        )

    def test_allow_non_formal_is_compatibility_noop_returning_full_bundle(self):
        topic = "deprecated non formal flag"
        orchestrator._save(topic, state())

        out = orchestrator.cmd_report(
            topic,
            allow_non_formal=True,
            include_synthesis=False,
        )

        self.assertEqual(out["status"], "report_data_ready")
        self.assertEqual(out["report_grade"], "EXPLORATORY")
        self.assertIn("CONVERGENCE", out["unmet_gates"])
        self.assertIn("facts_box_markdown", out)
        self.assertIn("evidence_ledger_markdown", out)
        self.assertIn("candidate_cards_markdown", out)
        self.assertIn("resolution_memo_markdown", out)
        self.assertIn("report_view_model", out)
        self.assertIn("deprecated", out["compatibility_warnings"][0])
        self.assertNotEqual(out["status"], "non_formal_ledger_ready")

    def test_orchestrator_can_select_facts_box_compatibility_view(self):
        topic = "facts box report view"
        st = converged_state()
        st["cruxes"]["C1"].update({
            "status": "MONITORABLE",
            "retired": True,
            "first_contested": 1,
            "contested_history": [0.5, 0.5, 0.5],
            "citations": [citation("facts-view-a"), citation("facts-view-b")],
        })
        orchestrator._save(topic, st)
        out = orchestrator.cmd_report(
            topic, challenge_only=True, report_view="facts_box", include_synthesis=False
        )
        self.assertEqual(out["status"], "report_data_ready")
        self.assertEqual(out["report_view"], "facts_box")
        self.assertEqual(out["report_markdown"], out["facts_box_markdown"])
        self.assertNotIn("synthesis_packet", out)

    def test_synthesis_packet_ships_by_default_and_carries_the_contract(self):
        topic = "brief report synthesis opt in"
        st = converged_state()
        st["cruxes"]["C1"].update({
            "status": "MONITORABLE",
            "retired": True,
            "first_contested": 1,
            "contested_history": [0.5, 0.5, 0.5],
            "citations": [citation("synthesis-a"), citation("synthesis-b")],
        })
        orchestrator._save(topic, st)
        without_synthesis = orchestrator.cmd_report(
            topic, challenge_only=True, report_view="brief", include_synthesis=False
        )
        out = orchestrator.cmd_report(topic, challenge_only=True, report_view="brief")
        self.assertIn("synthesis_packet", out)
        packet = out["synthesis_packet"]
        # The packet is the enforceable contract for styled artifacts, which
        # legitimately drop the Facts Box.
        self.assertEqual(packet["evidence_counts"]["valid_citations"], 2)
        self.assertFalse(packet["publication_allowed"])
        self.assertFalse(packet["ranking_allowed"])
        self.assertIn("style_is_free", packet["assertion_contract"])
        self.assertIn("no_new_numbers", packet["assertion_contract"])
        for field in (
            "facts_box_markdown",
            "facts_box_sha256",
            "evidence_ledger_markdown",
            "candidate_cards_markdown",
        ):
            self.assertEqual(out[field], without_synthesis[field])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class StyledArtifactLintTests(unittest.TestCase):
    """The styled lint is a provenance aid, not a correctness proof."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, text):
        path = os.path.join(self.tmp.name, "article.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def _state_file(self, st):
        path = os.path.join(self.tmp.name, "state.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(st, handle)
        return path

    def test_flags_urls_absent_from_the_ledger(self):
        st = converged_state()
        st["cruxes"]["C1"]["citations"] = [citation("real")]
        article = self._write(
            "cited https://fixture-research.org/real and "
            "invented https://never-seen.example.org/story\n"
        )
        lint = validate_report_v2.lint_styled_artifact(article, self._state_file(st))
        self.assertEqual(lint["urls_not_in_ledger"],
                         ["https://never-seen.example.org/story"])

    def test_flags_outputs_that_are_never_allowed(self):
        st = converged_state()
        article = self._write("目标价 78 元。\n建议配置，仓位不超过 20%。\n")
        lint = validate_report_v2.lint_styled_artifact(article, self._state_file(st))
        kinds = {hit["kind"] for hit in lint["forbidden_output_hits"]}
        self.assertIn("TARGET_PRICE", kinds)
        self.assertIn("POSITION_SIZING", kinds)

    def test_describing_third_party_flows_is_not_a_sizing_instruction(self):
        st = converged_state()
        article = self._write("公募基金已经在 Q1 大幅减仓源杰，机构在业绩爆发前就跑了。\n")
        lint = validate_report_v2.lint_styled_artifact(article, self._state_file(st))
        self.assertEqual(lint["forbidden_output_hits"], [])

    def test_lint_never_claims_to_be_a_proof(self):
        st = converged_state()
        lint = validate_report_v2.lint_styled_artifact(
            self._write("no urls here\n"), self._state_file(st)
        )
        self.assertFalse(lint["is_proof"])
        self.assertTrue(lint["unchecked"])


class BudgetAndPayloadYieldTests(unittest.TestCase):
    """Budget is measured in outcomes; discarded work must be visible."""

    def test_round_fuse_includes_crux_settling_headroom(self):
        # Coverage(4) + harvest-dry(2) alone is a floor a productive run overshoots.
        self.assertEqual(crux_engine.recommended_max_rounds(7), 9)
        self.assertEqual(crux_engine.recommended_max_rounds(5), 8)
        self.assertEqual(crux_engine.recommended_max_rounds(0), crux_engine.MIN_ROUNDS)

    def test_dry_streak_counts_only_trailing_unproductive_rounds(self):
        st = state()
        st["rounds"] = [
            {"round": 1, "opportunity_harvest": {"accepted_new": 1}},
            {"round": 2, "landscape_audit": {"accepted": 0}},
            {"round": 3, "landscape_audit": {"accepted": 0}},
        ]
        self.assertEqual(crux_engine.consecutive_unproductive_rounds(st), 2)
        st["rounds"].append({"round": 4, "landscape_audit": {"accepted": 2}})
        self.assertEqual(crux_engine.consecutive_unproductive_rounds(st), 0)

        st["rounds"] = [{
            "round": 1,
            "crux_probe_audit": {"C1": {"new_valid_evidence_count": 1}},
            "signals": {"C1": {"signal": 0.0, "citations": []}},
        }]
        self.assertEqual(crux_engine.consecutive_unproductive_rounds(st), 0)

    def test_payload_yield_separates_discards_from_omissions(self):
        st = state()
        st["rounds"] = [{
            "round": 1,
            "landscape_audit": {
                "submitted": 4, "accepted": 2, "rejected": 2, "omitted": 3,
                "rejected_reasons": {"detective_unknown_path": 2},
                "repair_notes": {"detective_linked_crux_corrected": 1},
            },
            "opportunity_harvest": {
                "submitted": 6, "accepted_new": 0, "rejected": 6,
                "rejected_reasons": {"missing_causal_path": 6},
            },
        }]
        yielded = crux_engine.payload_yield(st)
        self.assertEqual(yielded["submitted"], 10)
        self.assertEqual(yielded["accepted"], 2)
        self.assertEqual(yielded["rejected"], 8)
        # Never-submitted work must not inflate the discard rate past 100%.
        self.assertEqual(yielded["omitted"], 3)
        self.assertLessEqual(yielded["discard_rate"], 1.0)
        self.assertEqual(yielded["top_rejection_reasons"][0], ("missing_causal_path", 6))
        self.assertEqual(
            yielded["repairs_applied"][0], ("detective_linked_crux_corrected", 1)
        )

    def test_payload_yield_repairs_legacy_missing_finding_overcount(self):
        st = state()
        st["rounds"] = [{
            "round": 1,
            "landscape_audit": {
                "submitted": 2,
                "accepted": 1,
                "rejected": 3,
                "rejected_reasons": {
                    "detective_assigned_path_missing_finding": 2,
                    "inquisitor_non_unknown_requires_agent_evidence": 1,
                },
            },
        }]
        yielded = crux_engine.payload_yield(st)
        self.assertEqual(yielded["submitted"], 2)
        self.assertEqual(yielded["accepted"], 1)
        self.assertEqual(yielded["rejected"], 1)
        self.assertEqual(yielded["omitted"], 2)
        self.assertEqual(yielded["discard_rate"], 0.5)
        self.assertEqual(
            yielded["top_omission_reasons"],
            [("detective_assigned_path_missing_finding", 2)],
        )


class JudgeCitationRebindingTests(unittest.TestCase):
    """A Judge rewords claims by design; only invented sources may be dropped."""

    def _payloads(self, agent_citation):
        return (
            {"crux_evidence": [{"crux_id": "C1", "evidence": [agent_citation]}]},
            {"crux_attacks": []},
        )

    def test_reworded_judge_citation_is_rebound_not_dropped(self):
        agent = citation("shared", claim="segment margin reached 18 percent")
        detective, inquisitor = self._payloads(agent)
        judge = {"crux_signals": {"C1": {
            "signal": 0.5,
            "citations": [{**agent, "claim": "margin in the segment hit 18%"}],
        }}}
        cleaned = orchestrator._sanitize_judge_for_agent_support(
            judge, detective, inquisitor
        )
        signal = cleaned["crux_signals"]["C1"]
        self.assertEqual(signal["signal"], 0.5)
        self.assertEqual(len(signal["citations"]), 1)
        # The stored copy is the agent's wording, not the Judge's paraphrase.
        self.assertEqual(signal["citations"][0]["claim"], "segment margin reached 18 percent")
        self.assertIn("judge_citation_rebound_by_source_url:1", signal["quality_flags"])

    def test_invented_source_is_still_dropped_and_zeroes_the_signal(self):
        agent = citation("real")
        detective, inquisitor = self._payloads(agent)
        judge = {"crux_signals": {"C1": {
            "signal": 0.8,
            "citations": [{**citation("fabricated"),
                           "url": "https://never-cited.org/story"}],
        }}}
        cleaned = orchestrator._sanitize_judge_for_agent_support(
            judge, detective, inquisitor
        )
        signal = cleaned["crux_signals"]["C1"]
        self.assertEqual(signal["signal"], 0.0)
        self.assertEqual(signal["citations"], [])
        self.assertIn("signal_zeroed_no_agent_backed_citation", signal["quality_flags"])
