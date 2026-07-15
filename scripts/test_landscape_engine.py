#!/usr/bin/env python3
"""Offline regression tests for Landscape Map coverage and seed binding."""
import os
import tempfile
import unittest

import crux_engine
import deepthink_orchestrator_v2 as orchestrator
import landscape_engine
import opportunity_engine
import report_v2


def citation(path, claim="path evidence"):
    return {
        "claim": claim,
        "number": "1",
        "source": "Fixture Org",
        "url": f"https://fixture-landscape.org/{path}",
        "date": "2026-07-15",
        "source_tier": "primary",
    }


def frame(path_count=5, suggested_max_rounds=5):
    archetypes = [
        "DIRECT_CAPTURE",
        "BOTTLENECK_OWNER",
        "ENABLER_OR_INPUT",
        "SUBSTITUTE_OR_AVOIDANCE",
        "ADVERSE_EXPOSURE",
        "DIRECT_CAPTURE",
        "BOTTLENECK_OWNER",
    ]
    paths = []
    for index in range(path_count):
        number = index + 1
        paths.append({
            "path_id": f"L{number}",
            "archetype": archetypes[index],
            "linked_crux_id": "C1",
            "hypothesis": f"shock {number} -> capture mechanism {number}",
            "hypothesis_status": "HYPOTHESIS",
            "value_transfer_chain": ["shock", f"constraint {number}", "capture", "owner return"],
            "economic_capture_test": f"observable capture test {number}",
            "pricing_question": f"as-of expectation question {number}",
            "falsifier": f"observable falsifier {number}",
            "search_queries": [f"primary query {number}a", f"primary query {number}b"],
        })
    return {
        "question_type": "UNIVERSE_SEARCH",
        "candidate_cruxes": [
            {"id": "C1", "logic_role": "OPPORTUNITY_PATH"},
            {"id": "C2", "logic_role": "PRICING"},
        ],
        "landscape_map": {"paths": paths},
        "suggested_max_rounds": suggested_max_rounds,
    }


def mapped_state(path_count=5):
    raw = frame(path_count=path_count, suggested_max_rounds=5)
    state = crux_engine.new_state(
        "mapped", "find value capture", "3-6M",
        [
            {"id": "C1", "label": "path", "logic_role": "OPPORTUNITY_PATH"},
            {"id": "C2", "label": "pricing", "logic_role": "PRICING"},
        ],
        question_type="UNIVERSE_SEARCH",
    )
    state["landscape_map"] = landscape_engine.initialize(raw)
    state["frame_contract"] = {"as_of_date": "2026-07-15"}
    return state


def orchestrator_frame():
    raw = frame()
    raw.update({
        "decision_question": "Which value-transfer paths are researchable over 3-6 months?",
        "horizon": "3-6M",
        "as_of_date": "2026-07-15",
        "unit_of_analysis": "entity-agnostic candidate universe",
        "thesis_seed": "If the mapped capture tests hold, a mispriced vehicle may exist.",
        "logic_graph": {
            "root_id": "Q1",
            "nodes": [
                {"id": "Q1", "node_type": "QUESTION", "label": "root"},
                {"id": "C1", "node_type": "CRUX", "label": "path"},
                {"id": "C2", "node_type": "CRUX", "label": "pricing"},
            ],
            "edges": [
                {"from": "C1", "to": "Q1", "relation": "ALTERNATIVE_PATH"},
                {"from": "C2", "to": "Q1", "relation": "PRICING_FOR"},
            ],
        },
        "premise_audit": [{
            "id": "P1", "claim": "the question has observable primary-source tests",
            "status": "HYPOTHESIS", "as_of": "UNKNOWN", "source_url": None,
            "required_primary_source": "filing or official dataset", "use": "scope research",
        }],
        "candidate_cruxes": [
            {"id": "C1", "label": "path", "logic_role": "OPPORTUNITY_PATH",
             "definition": "who captures economics", "monitor_anchor": "reported economics",
             "falsifier": "no measurable capture", "catalyst_window": {
                 "event": "path review", "expected_by": "2026-10-15",
                 "date_status": "REVIEW_CHECKPOINT", "basis_claim_id": "P1"}},
            {"id": "C2", "label": "pricing", "logic_role": "PRICING",
             "definition": "whether capture is priced", "monitor_anchor": "as-of anchor",
             "falsifier": "expectation already embeds capture", "catalyst_window": {
                 "event": "pricing review", "expected_by": "2026-10-15",
                 "date_status": "REVIEW_CHECKPOINT", "basis_claim_id": "P1"}},
        ],
        "forbidden_consensus": ["theme growth alone proves a candidate"],
        "no_edge_precheck": {
            "is_researchable": True, "basis_type": "TESTABILITY",
            "basis_claim_ids": ["P1"], "reason": "observable tests can reject each path",
        },
    })
    return raw


class LandscapeFrameTests(unittest.TestCase):
    def test_opportunity_frame_requires_real_map(self):
        raw = frame()
        raw.pop("landscape_map")
        self.assertIn(
            "opportunity_question_requires_landscape_map",
            landscape_engine.validate_frame(raw),
        )

    def test_map_requires_all_archetypes_and_exactly_two_queries(self):
        raw = frame()
        raw["landscape_map"]["paths"][4]["archetype"] = "DIRECT_CAPTURE"
        raw["landscape_map"]["paths"][0]["search_queries"] = ["only one"]
        issues = landscape_engine.validate_frame(raw)
        self.assertTrue(any(item.startswith("landscape_missing_archetypes:") for item in issues))
        self.assertIn("landscape_path_1_requires_exactly_two_search_queries", issues)

    def test_round_budget_must_cover_map_plus_stability(self):
        raw = frame(path_count=7, suggested_max_rounds=4)
        self.assertIn("landscape_requires_at_least_6_rounds", landscape_engine.validate_frame(raw))

        raw = frame(path_count=5, suggested_max_rounds=4)
        self.assertIn("landscape_requires_at_least_5_rounds", landscape_engine.validate_frame(raw))

    def test_pure_challenge_frame_does_not_require_map(self):
        raw = {"question_type": "CONJUNCTIVE", "candidate_cruxes": [
            {"id": "C1", "logic_role": "THESIS_HINGE"}
        ]}
        self.assertEqual(landscape_engine.validate_frame(raw), [])


class LandscapeOrchestratorIntegrationTests(unittest.TestCase):
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

    def test_init_rejects_opportunity_frame_without_map(self):
        raw = orchestrator_frame()
        raw.pop("landscape_map")
        result = orchestrator.cmd_init("missing-map", raw)
        self.assertEqual(result["status"], "frame_rejected")
        self.assertIn("opportunity_question_requires_landscape_map", result["issues"])

    def test_init_persists_map_and_round_assignments(self):
        result = orchestrator.cmd_init("mapped-init", orchestrator_frame())
        self.assertEqual(result["status"], "dispatch_subagents")
        self.assertEqual(result["landscape_assignments"]["detective"], ["L1", "L2"])
        stored = orchestrator._load("mapped-init")
        self.assertEqual(len(stored["landscape_map"]["paths"]), 5)
        self.assertEqual(stored["landscape_map"]["round_plans"][0]["round"], 1)


class LandscapeDispatchTests(unittest.TestCase):
    def test_assignments_are_deterministic_and_bounded(self):
        state = mapped_state()
        first = landscape_engine.ensure_round_plan(state, 1)
        self.assertEqual(first["assignments"]["detective"], ["L1", "L2"])
        self.assertEqual(first["assignments"]["inquisitor"], ["L1", "L2"])
        self.assertEqual(landscape_engine.ensure_round_plan(state, 1), first)

    def test_both_roles_must_probe_and_conflict_becomes_unknown(self):
        state = mapped_state()
        landscape_engine.ensure_round_plan(state, 1)
        det_ev = citation("det")
        inq_ev = {**citation("inq", "counter path evidence"), "attack": "capture bypassed"}
        detective = {
            "crux_evidence": [{"crux_id": "C1", "evidence": [det_ev]}],
            "landscape_findings": [
                {"path_id": "L1", "linked_crux_id": "C1", "state": "SUPPORTED",
                 "rationale": "capture observed", "evidence": [det_ev]},
                {"path_id": "L2", "linked_crux_id": "C1", "state": "SUPPORTED",
                 "rationale": "capture observed", "evidence": [det_ev]},
            ],
        }
        inquisitor = {
            "crux_attacks": [{"crux_id": "C1", "attacks": [inq_ev]}],
            "landscape_findings": [
                {"path_id": "L1", "linked_crux_id": "C1", "state": "UNKNOWN",
                 "rationale": "counter not found", "evidence": []},
                {"path_id": "L2", "linked_crux_id": "C1", "state": "REJECTED",
                 "rationale": "bypass found", "evidence": [inq_ev]},
            ],
        }
        audit = landscape_engine.ingest_round(state, 1, detective, inquisitor)
        paths = {item["path_id"]: item for item in state["landscape_map"]["paths"]}
        self.assertEqual(audit["accepted"], 4)
        self.assertEqual(paths["L1"]["state"], "SUPPORTED")
        self.assertEqual(paths["L2"]["state"], "UNKNOWN")
        second = landscape_engine.ensure_round_plan(state, 2)
        self.assertEqual(second["assignments"]["detective"], ["L3", "L4"])

    def test_invented_evidence_and_out_of_scope_path_fail_closed(self):
        state = mapped_state()
        landscape_engine.ensure_round_plan(state, 1)
        real = citation("real")
        invented = citation("invented")
        detective = {
            "crux_evidence": [{"crux_id": "C1", "evidence": [real]}],
            "landscape_findings": [
                {"path_id": "L1", "linked_crux_id": "C1", "state": "SUPPORTED",
                 "rationale": "invented", "evidence": [invented]},
                {"path_id": "L3", "linked_crux_id": "C1", "state": "UNKNOWN",
                 "rationale": "outside assignment", "evidence": []},
            ],
        }
        audit = landscape_engine.ingest_round(state, 1, detective, {"landscape_findings": []})
        path = landscape_engine.path_for_seed(state, "L1")
        self.assertEqual(path["state"], "UNPROBED")
        self.assertIn("detective_non_unknown_requires_agent_evidence", audit["rejected_reasons"])
        self.assertIn("detective_finding_outside_assignment", audit["rejected_reasons"])


class LandscapeGateAndReportTests(unittest.TestCase):
    def _coverage_complete_universe(self):
        state = mapped_state()
        for path in state["landscape_map"]["paths"]:
            path["state"] = "SUPPORTED"
            path["probes"] = {
                "detective": {"round": 1, "state": "SUPPORTED", "evidence": []},
                "inquisitor": {"round": 1, "state": "SUPPORTED", "evidence": []},
            }
        for index, crux in enumerate(state["cruxes"].values(), 1):
            crux["first_contested"] = 1
            crux["status"] = "OPEN"
            crux["citations"] = [
                citation(f"c{index}-a"), citation(f"c{index}-b"),
            ]
        state["max_introduced_round"] = 0
        verdict = crux_engine.research_verdict(state)
        state["decision_trace"] = [
            {"round": 3, "research_verdict": verdict},
            {"round": 4, "research_verdict": verdict},
        ]
        state["rounds"] = [
            {"round": 3, "opportunity_harvest": {
                "accepted_new": 0, "merged_existing": 0,
            }},
            {"round": 4, "opportunity_harvest": {
                "accepted_new": 0, "merged_existing": 0,
            }},
        ]
        return state

    def test_universe_converges_on_coverage_and_dry_harvest_not_global_direction(self):
        state = self._coverage_complete_universe()
        state["cruxes"]["C1"]["p_history"] = [0.5, 0.8, 0.2]
        state["cruxes"]["C2"]["p_history"] = [0.5, 0.2, 0.8]
        result = crux_engine.convergence(state, 4)
        self.assertEqual(result["decision"], "converge")
        self.assertEqual(result["convergence_basis"], "UNIVERSE_COVERAGE_AND_HARVEST_DRY")
        self.assertTrue(all(
            crux["status"] == "MONITORABLE" and crux["retired"]
            for crux in state["cruxes"].values()
        ))
        self.assertEqual(
            crux_engine.research_verdict(state)["evidence_direction"],
            "UNDETERMINED",
        )

    def test_universe_final_round_seed_or_evidence_growth_blocks_convergence(self):
        for field in ("accepted_new", "merged_existing"):
            state = self._coverage_complete_universe()
            state["rounds"][-1]["opportunity_harvest"][field] = 1
            result = crux_engine.convergence(state, 4)
            self.assertEqual(result["decision"], "continue")
            self.assertTrue(all(
                crux["status"] == "OPEN" for crux in state["cruxes"].values()
            ))

    def test_universe_dry_rounds_before_coverage_do_not_count(self):
        state = self._coverage_complete_universe()
        for path in state["landscape_map"]["paths"]:
            for probe in path["probes"].values():
                probe["round"] = 4
        result = crux_engine.convergence(state, 4)
        self.assertEqual(result["decision"], "continue")
        self.assertIn("R4 完成后", result["reason"])

    def test_unprobed_path_blocks_edge_and_convergence(self):
        state = mapped_state()
        for crux in state["cruxes"].values():
            crux.update({"status": "MONITORABLE", "retired": True, "first_contested": 1})
        state["max_introduced_round"] = 0
        state["decision_trace"] = [
            {"round": 2, "decision": "MONITOR", "p_weakest": 0.5,
             "research_verdict": {"edge_state": "INSUFFICIENT_EVIDENCE",
                                  "evidence_direction": "UNDETERMINED", "actionability": "NONE"}},
            {"round": 3, "decision": "MONITOR", "p_weakest": 0.5,
             "research_verdict": {"edge_state": "INSUFFICIENT_EVIDENCE",
                                  "evidence_direction": "UNDETERMINED", "actionability": "NONE"}},
        ]
        verdict = crux_engine.research_verdict(state, {"C1": 0.7, "C2": 0.7})
        self.assertEqual(verdict["reason_code"], "LANDSCAPE_PATHS_UNPROBED")
        self.assertEqual(crux_engine.convergence(state, 3)["decision"], "continue")

    def test_seed_must_bind_matching_path_and_unsupported_path_cannot_be_ready(self):
        state = mapped_state()
        ev = citation("seed")
        raw = {
            "candidate": "Capture Asset", "asset_type": "LISTED_EQUITY",
            "relation_type": "DIRECT_WINNER", "origin_crux": "C1",
            "causal_path": "shock -> capture -> earnings", "evidence": [ev],
        }
        payload = {"crux_evidence": [{"crux_id": "C1", "evidence": [ev]}],
                   "opportunity_seeds": [raw]}
        rejected = opportunity_engine.harvest_round(state, 1, payload, {})
        self.assertIn("missing_landscape_path_id", rejected["rejected_reasons"])
        raw["landscape_path_id"] = "L1"
        accepted = opportunity_engine.harvest_round(state, 1, payload, {})
        self.assertEqual(accepted["accepted_new"], 1)
        stored = state["opportunity_seeds"][0]
        self.assertIn("landscape_path_not_supported", opportunity_engine._origin_gate(state, stored))

    def test_report_exposes_planned_to_probed_to_candidate_binding(self):
        state = mapped_state()
        for path in state["landscape_map"]["paths"]:
            path["state"] = "UNKNOWN"
            path["probes"] = {
                "detective": {"round": 1, "state": "UNKNOWN", "evidence": []},
                "inquisitor": {"round": 1, "state": "UNKNOWN", "evidence": []},
            }
        state["landscape_map"]["paths"][0]["state"] = "SUPPORTED"
        state["last_convergence"] = {"decision": "converge"}
        state["decision_trace"] = [{
            "round": 3, "weakest": "C1", "p_weakest": 0.5, "p_mean": 0.5,
            "support_weakest": 0.5, "support_mean": 0.5, "decision": "MONITOR",
        }]
        for crux in state["cruxes"].values():
            crux.update({"status": "MONITORABLE", "first_contested": 1})
        brief = report_v2.render(state, view="brief")
        audit = report_v2.render(state, view="audit")
        self.assertIn("发现路径覆盖", brief)
        self.assertIn("Landscape Map 覆盖账本", audit)
        self.assertIn("L1", audit)
        self.assertIn("SUPPORTED", audit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
