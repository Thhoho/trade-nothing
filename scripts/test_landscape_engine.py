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


def evidence_plan(crux_id):
    return [
        {"plan_id": f"SP-{crux_id}-1", "publisher_class": "ISSUER_OR_FILING",
         "target_claim": f"issuer anchor {crux_id}", "search_query": f"issuer {crux_id}"},
        {"plan_id": f"SP-{crux_id}-2", "publisher_class": "REGULATOR_OR_OFFICIAL_DATASET",
         "target_claim": f"official anchor {crux_id}", "search_query": f"official {crux_id}"},
    ]


def citation(path, claim="path evidence"):
    return {
        "claim": claim,
        "number": "1",
        "source": "Fixture Org",
        "url": f"https://fixture-landscape.org/{path}",
        "date": "2026-07-15",
        "source_tier": "primary",
    }


def frame(path_count=5, suggested_max_rounds=8):
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
            {"id": "C1", "logic_role": "OPPORTUNITY_PATH",
             "evidence_plan": evidence_plan("C1")},
            {"id": "C2", "logic_role": "PRICING",
             "evidence_plan": evidence_plan("C2")},
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
             "evidence_plan": evidence_plan("C1"),
             "falsifier": "no measurable capture", "catalyst_window": {
                 "event": "path review", "expected_by": "2026-10-15",
                 "date_status": "REVIEW_CHECKPOINT", "basis_claim_id": "P1"}},
            {"id": "C2", "label": "pricing", "logic_role": "PRICING",
             "definition": "whether capture is priced", "monitor_anchor": "as-of anchor",
             "evidence_plan": evidence_plan("C2"),
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

    def test_round_budget_must_be_reachable_not_just_a_floor(self):
        """Coverage + harvest-dry is a floor; the fuse also needs crux-settling room."""
        raw = frame(path_count=7, suggested_max_rounds=4)
        self.assertIn("landscape_requires_at_least_9_rounds", landscape_engine.validate_frame(raw))

        raw = frame(path_count=5, suggested_max_rounds=4)
        self.assertIn("landscape_requires_at_least_8_rounds", landscape_engine.validate_frame(raw))

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

    def test_assignment_prioritizes_paths_linked_to_dispatched_crux(self):
        state = mapped_state()
        state["landscape_map"]["paths"][-1]["linked_crux_id"] = "C2"
        first = landscape_engine.ensure_round_plan(
            state, 1, dispatch_cruxes=["C2"]
        )
        self.assertEqual(first["assignments"]["detective"][0], "L5")
        self.assertEqual(first["assignments"]["inquisitor"][0], "L5")

    def test_dispatch_keeps_pending_landscape_crux_in_scope(self):
        raw = frame()
        state = crux_engine.new_state(
            "mapped", "find value capture", "3-6M",
            [
                {"id": "C1", "label": "path"},
                {"id": "C2", "label": "pricing"},
                {"id": "C3", "label": "economics"},
            ],
            question_type="UNIVERSE_SEARCH",
        )
        state["landscape_map"] = landscape_engine.initialize(raw)
        state["cruxes"]["C1"]["first_contested"] = 1
        state["cruxes"]["C2"]["first_contested"] = 1
        state["rounds"] = [{
            "round": 1,
            "judge_raw": {"crux_signals": {"C1": {}, "C2": {}}},
        }]
        self.assertEqual(
            orchestrator._dispatch_cruxes(state, ["C1", "C2", "C3"]),
            ["C1", "C3"],
        )

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

    def test_rejected_findings_cannot_starve_later_paths(self):
        """A path whose findings never bind must not re-occupy the slot forever."""
        state = mapped_state(path_count=7)
        assigned_rounds = []
        # Worst case seen in production: the role returns no landscape findings at
        # all, so no probe can be recorded from its output.
        for round_num in range(1, 6):
            plan = landscape_engine.ensure_round_plan(state, round_num)
            assigned_rounds.append(plan["assignments"]["detective"])
            landscape_engine.ingest_round(state, round_num, {}, {})

        # Every path gets a first attempt before any stalled path is retried.
        self.assertEqual(
            assigned_rounds[:4],
            [["L1", "L2"], ["L3", "L4"], ["L5", "L6"], ["L7", "L1"]],
        )
        # L1 exhausted its two attempts, so it retires instead of blocking R5.
        paths = {item["path_id"]: item for item in state["landscape_map"]["paths"]}
        self.assertTrue(paths["L1"]["probes"]["detective"]["exhausted"])
        self.assertEqual(paths["L1"]["probes"]["detective"]["state"], "UNKNOWN")
        self.assertNotIn("L1", assigned_rounds[4])

    def test_legacy_round_plans_backfill_assignment_attempts_on_resume(self):
        state = mapped_state()
        state["landscape_map"]["round_plans"] = [
            {"round": 1, "assignments": {
                "detective": ["L1", "L2"], "inquisitor": ["L1", "L2"],
            }},
            {"round": 2, "assignments": {
                "detective": ["L1", "L3"], "inquisitor": ["L1", "L3"],
            }},
        ]
        # Legacy paths predate assign_attempts entirely.
        for path in state["landscape_map"]["paths"]:
            path.pop("assign_attempts", None)
        plan = landscape_engine.ensure_round_plan(state, 3)
        l1 = landscape_engine.path_for_seed(state, "L1")
        self.assertEqual(l1["assign_attempts"]["detective"], 2)
        self.assertTrue(l1["probes"]["detective"]["exhausted"])
        self.assertNotIn("L1", plan["assignments"]["detective"])

    def test_unsupported_claim_is_downgraded_not_discarded(self):
        """A directional claim with no bound evidence becomes an honest UNKNOWN."""
        state = mapped_state()
        landscape_engine.ensure_round_plan(state, 1)
        real = citation("real")
        detective = {
            "crux_evidence": [{"crux_id": "C1", "evidence": [real]}],
            "landscape_findings": [
                {"path_id": "L1", "linked_crux_id": "C1", "state": "SUPPORTED",
                 "rationale": "asserted without binding", "evidence": [citation("ghost")]},
            ],
        }
        audit = landscape_engine.ingest_round(state, 1, detective, {})
        probe = landscape_engine.path_for_seed(state, "L1")["probes"]["detective"]
        self.assertEqual(probe["state"], "UNKNOWN")
        self.assertEqual(probe["downgraded_from"], "SUPPORTED")
        self.assertEqual(probe["evidence"], [])
        self.assertIn("detective_downgraded_unsupported_claim", audit["repair_notes"])

    def test_wrong_linked_crux_is_corrected_not_discarded(self):
        state = mapped_state()
        landscape_engine.ensure_round_plan(state, 1)
        real = citation("real")
        detective = {
            "crux_evidence": [{"crux_id": "C1", "evidence": [real]}],
            "landscape_findings": [
                # L1 is bound to C1; the role wrongly echoes C2.
                {"path_id": "L1", "linked_crux_id": "C2", "state": "SUPPORTED",
                 "rationale": "capture observed", "evidence": [real]},
            ],
        }
        audit = landscape_engine.ingest_round(state, 1, detective, {})
        probe = landscape_engine.path_for_seed(state, "L1")["probes"]["detective"]
        self.assertEqual(probe["state"], "SUPPORTED")
        self.assertEqual(probe["claimed_crux_id"], "C2")
        self.assertEqual(len(probe["evidence"]), 1)
        self.assertIn("detective_linked_crux_corrected", audit["repair_notes"])

    def test_paraphrased_landscape_evidence_still_binds_by_source(self):
        """Roles paraphrase claims between arrays; the URL must still bind."""
        state = mapped_state()
        landscape_engine.ensure_round_plan(state, 1)
        parent = citation("shared", claim="capture is observable in the filing")
        paraphrased = {**parent, "claim": "the filing shows observable capture"}
        detective = {
            "crux_evidence": [{"crux_id": "C1", "evidence": [parent]}],
            "landscape_findings": [
                {"path_id": "L1", "linked_crux_id": "C1", "state": "SUPPORTED",
                 "rationale": "capture observed", "evidence": [paraphrased]},
            ],
        }
        audit = landscape_engine.ingest_round(state, 1, detective, {})
        self.assertEqual(audit["accepted"], 1)
        stored = landscape_engine.path_for_seed(state, "L1")
        # The parent citation is stored verbatim, not the paraphrase.
        self.assertEqual(
            stored["probes"]["detective"]["evidence"][0]["claim"],
            "capture is observable in the filing",
        )

    def test_invented_evidence_never_becomes_support(self):
        """Tolerance is about protocol slips, never about admitting fake evidence."""
        state = mapped_state()
        landscape_engine.ensure_round_plan(state, 1)
        real = citation("real")
        invented = citation("invented")
        detective = {
            "crux_evidence": [{"crux_id": "C1", "evidence": [real]}],
            "landscape_findings": [
                {"path_id": "L1", "linked_crux_id": "C1", "state": "SUPPORTED",
                 "rationale": "invented", "evidence": [invented]},
                # Unassigned but unprobed: real work, so it is kept.
                {"path_id": "L3", "linked_crux_id": "C1", "state": "UNKNOWN",
                 "rationale": "outside assignment", "evidence": []},
            ],
        }
        audit = landscape_engine.ingest_round(state, 1, detective, {"landscape_findings": []})
        l1 = landscape_engine.path_for_seed(state, "L1")
        self.assertEqual(l1["probes"]["detective"]["state"], "UNKNOWN")
        self.assertEqual(l1["probes"]["detective"]["evidence"], [])
        self.assertNotEqual(l1["state"], "SUPPORTED")
        self.assertIn("L3", [
            item["path_id"] for item in state["landscape_map"]["paths"]
            if "detective" in (item.get("probes") or {})
        ])
        self.assertIn("detective_accepted_outside_assignment", audit["repair_notes"])

    def test_summary_distinguishes_partial_role_probes_from_zero_work(self):
        state = mapped_state()
        first = state["landscape_map"]["paths"][0]
        first["probes"] = {
            "detective": {"round": 1, "state": "UNKNOWN", "evidence": []},
        }
        first["state"] = "UNPROBED"
        summary = landscape_engine.summary(state)
        self.assertEqual(summary["unprobed_count"], 5)
        self.assertEqual(summary["partially_probed_count"], 1)
        self.assertEqual(summary["probe_slots_completed"], 1)
        self.assertEqual(summary["probe_slots_total"], 10)
        self.assertEqual(summary["probe_slot_coverage_ratio"], 0.1)


class LandscapeGateAndReportTests(unittest.TestCase):
    def test_hybrid_non_universe_requires_post_coverage_harvest_dry_window(self):
        state = mapped_state()
        state["question_type"] = "CONJUNCTIVE"
        state["frame_contract"]["research_intent"] = "HYBRID"
        for path in state["landscape_map"]["paths"]:
            path["probes"] = {
                "detective": {"round": 3, "state": "UNKNOWN"},
                "inquisitor": {"round": 3, "state": "UNKNOWN"},
            }
            path["state"] = "UNKNOWN"
        for crux_id, crux in state["cruxes"].items():
            crux.update({
                "status": "RESOLVED_BULL",
                "retired": True,
                "first_contested": 1,
                "contested_history": [0.6, 0.6, 0.6],
                "p_history": [0.5, 0.6, 0.6],
                "citations": [
                    citation(f"{crux_id}-a"),
                    citation(f"{crux_id}-b"),
                ],
            })
        stable = {
            "weakest": "C1",
            "p_weakest": 0.6,
            "p_mean": 0.6,
            "decision": "RESEARCH_READY",
            "research_verdict": {
                "edge_state": "INSUFFICIENT_EVIDENCE",
                "evidence_direction": "BULL",
                "actionability": "MONITOR",
            },
        }
        state["decision_trace"] = [
            {"round": 2, **stable},
            {"round": 3, **stable},
        ]
        state["rounds"] = [{
            "round": 3,
            "opportunity_harvest": {
                "accepted_new": 0,
                "merged_existing": 0,
            },
        }]
        first = crux_engine.convergence(state, 3)
        self.assertEqual(first["decision"], "continue")
        self.assertIn("连续静默 1 轮", first["reason"])

        state["decision_trace"].append({"round": 4, **stable})
        state["rounds"].append({
            "round": 4,
            "opportunity_harvest": {
                "accepted_new": 0,
                "merged_existing": 0,
            },
        })
        second = crux_engine.convergence(state, 4)
        self.assertEqual(second["decision"], "converge")

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
        # SECOND_ORDER has no unambiguous archetype, so with five C1 paths the
        # binding stays genuinely ambiguous and must not be guessed.
        raw["relation_type"] = "SECOND_ORDER"
        rejected = opportunity_engine.harvest_round(state, 1, payload, {})
        self.assertIn(
            "ambiguous_landscape_path_for_origin_crux", rejected["rejected_reasons"]
        )
        raw["relation_type"] = "DIRECT_WINNER"
        raw["landscape_path_id"] = "L1"
        accepted = opportunity_engine.harvest_round(state, 1, payload, {})
        self.assertEqual(accepted["accepted_new"], 1)
        stored = state["opportunity_seeds"][0]
        self.assertIn("landscape_path_not_supported", opportunity_engine._origin_gate(state, stored))

    def test_archetype_narrows_an_otherwise_ambiguous_seed_path(self):
        """DIRECT_WINNER maps to DIRECT_CAPTURE, which is unique inside C1."""
        state = mapped_state()
        ev = citation("seed")
        payload = {
            "crux_evidence": [{"crux_id": "C1", "evidence": [ev]}],
            "opportunity_seeds": [{
                "candidate": "Capture Asset", "asset_type": "LISTED_EQUITY",
                "relation_type": "DIRECT_WINNER", "origin_crux": "C1",
                "causal_path": "shock -> capture -> earnings", "evidence": [ev],
            }],
        }
        audit = opportunity_engine.harvest_round(state, 1, payload, {})
        self.assertEqual(audit["accepted_new"], 1)
        self.assertEqual(state["opportunity_seeds"][0]["landscape_path_id"], "L1")

    def test_seed_path_is_derived_when_origin_crux_identifies_one_path(self):
        """A seed must not be discarded over an ID the engine can derive."""
        state = mapped_state()
        # Give C2 exactly one path so the binding is unambiguous.
        state["landscape_map"]["paths"][-1]["linked_crux_id"] = "C2"
        ev = citation("seed")
        payload = {
            "crux_evidence": [{"crux_id": "C2", "evidence": [ev]}],
            "opportunity_seeds": [{
                "candidate": "Capture Asset", "asset_type": "LISTED_EQUITY",
                "relation_type": "DIRECT_WINNER", "origin_crux": "C2",
                "causal_path": "shock -> capture -> earnings", "evidence": [ev],
            }],
        }
        audit = opportunity_engine.harvest_round(state, 1, payload, {})
        self.assertEqual(audit["accepted_new"], 1)
        self.assertIn(
            "landscape_path_derived_from_origin_crux", audit["repair_notes"]
        )
        self.assertEqual(
            state["opportunity_seeds"][0]["landscape_path_id"], "L5"
        )

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
