#!/usr/bin/env python3
"""Offline regression tests for the v2 evidence and report safety gates."""
import os
import json
import tempfile
import unittest

import crux_engine
import deepthink_orchestrator_v2 as orchestrator
import report_v2
import research_output
import validate_report_v2
import utils


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
        self.assertEqual(verdict["actionability"], "MONITOR")
        self.assertEqual(verdict["reason_code"], "PATH_OR_PRICING_COVERAGE_INCOMPLETE")
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

    def test_universe_search_requires_path_and_pricing_to_find_edge(self):
        st = self._state("UNIVERSE_SEARCH", [
            {"id": "C1", "label": "path a", "logic_role": "OPPORTUNITY_PATH"},
            {"id": "C2", "label": "path b", "logic_role": "OPPORTUNITY_PATH"},
            {"id": "C3", "label": "pricing", "logic_role": "PRICING"},
        ])
        st["cruxes"]["C1"]["p_history"] = [0.5, 0.35]
        st["cruxes"]["C2"]["p_history"] = [0.5, 0.65]
        st["cruxes"]["C3"]["p_history"] = [0.5, 0.60]
        verdict = crux_engine.research_verdict(st)
        self.assertEqual(verdict["edge_state"], "EDGE_FOUND")
        self.assertEqual(verdict["actionability"], "MONITOR")
        st["last_convergence"] = {"decision": "converge"}
        verdict = crux_engine.research_verdict(st)
        self.assertEqual(verdict["actionability"], "READY_FOR_SCREENING")

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
        self.assertLessEqual(cx["p_history"][-1], first)
        flags = st["rounds"][-1]["signals"]["C1"]["quality_flags"]
        self.assertIn("dropped_duplicate_evidence:1", flags)
        self.assertIn("signal_zeroed_no_valid_citation", flags)

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
                 "falsifier": "f1", "catalyst_window": {
                     "event": "e1", "expected_by": "2026-10-31",
                     "date_status": "REVIEW_CHECKPOINT", "basis_claim_id": "P1"}},
                {"id": "C2", "label": "c2", "logic_role": "THESIS_HINGE",
                 "definition": "d2", "monitor_anchor": "m2",
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

    def test_evolution_path_falls_back_to_nonempty_configured_vault(self):
        with tempfile.TemporaryDirectory() as root:
            skill_dir = os.path.join(root, "skill")
            vault_dir = os.path.join(root, "vault")
            os.makedirs(skill_dir)
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
        blocked = orchestrator.cmd_report(topic)
        self.assertEqual(blocked["status"], "blocked_unconverged")
        self.assertIn("未收敛研究备忘录", blocked["resolution_memo_markdown"])
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

    def test_converged_legacy_state_without_sources_is_still_blocked(self):
        topic = "legacy-evidence-gate"
        st = state()
        st["last_convergence"] = {"decision": "converge"}
        st["cruxes"]["C1"]["status"] = "RESOLVED_BULL"
        st["decision_trace"].append({
            "round": 3, "weakest": "C1", "p_weakest": 0.6, "p_mean": 0.6,
            "support_weakest": 0.6, "support_mean": 0.6, "decision": "RESEARCH_READY",
        })
        orchestrator._save(topic, st)
        self.assertEqual(orchestrator.cmd_report(topic)["status"], "blocked_evidence_gate")


class ReportSafetyTests(unittest.TestCase):
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

    def test_formal_renderer_rejects_unconverged_state(self):
        with self.assertRaisesRegex(ValueError, "not converged"):
            report_v2.render(state())

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
