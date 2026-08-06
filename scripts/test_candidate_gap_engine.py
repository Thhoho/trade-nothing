#!/usr/bin/env python3
import copy
import unittest
from unittest.mock import patch

import candidate_gap_engine
import crux_engine
import deepthink_orchestrator_v2 as orchestrator
import opportunity_engine


def citation(domain, claim="independent confirmation", number="25 MW"):
    return {
        "claim": claim,
        "number": number,
        "source": domain,
        "url": f"https://{domain}/research/specific-evidence",
        "date": "2026-07-19",
        "source_tier": "primary",
    }


def fixture_state(*, missing_expectation=False):
    first = citation("issuer-source.org", "issuer discloses contracted capacity")
    root_second = citation("regulator.gov", "regulator confirms project approval")
    seed = {
        "seed_id": "OS-ABCDEF1234",
        "entity_id": "OE-ABCDEF1234",
        "candidate": "Candidate Corp",
        "ticker": "CAND",
        "asset_type": "LISTED_EQUITY",
        "relation_type": "INFRA_ASSET_OWNER",
        "origin_crux": "C1",
        "landscape_path_id": "L1",
        "causal_path": "approved capacity -> binding customer use -> contracted cash flow",
        "economic_exposure": "owns the approved capacity",
        "why_market_may_miss": "" if missing_expectation else "coverage omits signed capacity",
        "pricing_anchor": {
            "as_of_date": "2026-07-19",
            "anchor_type": "CAPACITY_OR_EARNINGS",
            "metric": "contracted capacity",
            "current_value": "25 MW",
            "comparison_value": "100 MW approved",
            "source": first["source"],
            "source_url": first["url"],
            "source_claim": first["claim"],
        },
        "catalyst": "customer acceptance",
        "catalyst_window": {
            "event": "customer acceptance",
            "expected_by": "2026-10-31",
            "date_status": "REVIEW_CHECKPOINT",
        },
        "falsifier": "customer cancels the capacity",
        "evidence": [first],
        "first_seen_round": 1,
        "last_seen_round": 1,
        "source_agents": ["detective"],
    }
    state = {
        "topic": "candidate gap fixture",
        "question_type": "UNIVERSE_SEARCH",
        "horizon": "3-6M",
        "frame_contract": {"as_of_date": "2026-07-19"},
        "runtime": {
            "run_id": "RUN-20260719-ABCDEF123456",
            "run_purpose": "PRODUCTION_RESEARCH",
        },
        "last_convergence": {"decision": "converge"},
        "cruxes": {
            "C1": {
                "status": "MONITORABLE",
                "first_contested": 1,
                "citations": [first, root_second],
            }
        },
        "landscape_map": {
            "paths": [
                {
                    "path_id": "L1",
                    "linked_crux_id": "C1",
                    "state": "SUPPORTED",
                }
            ]
        },
        "opportunity_seeds": [seed],
        "candidate_gap_tasks": [],
        "candidate_evidence_supplements": [],
        "candidate_gap_resolutions": [],
        "candidate_screens": [],
    }
    opportunity_engine.refresh_candidate_states(state)
    return state


def supplement(task, source_domain, alignment="SUPPORTED", field_additions=None):
    return {
        "task_id": task["task_id"],
        "seed_id": task["seed_id"],
        "claim_alignment": alignment,
        "source_type": task["required_source_types"][0],
        "citation": citation(source_domain),
        "field_additions": field_additions or {},
        "alignment_rationale": "directly addresses the frozen target claim",
    }


class CandidateGapEngineTests(unittest.TestCase):
    def test_asymmetry_orders_equal_gap_work_but_does_not_beat_nearer_readiness(self):
        state = fixture_state(missing_expectation=True)
        high = state["opportunity_seeds"][0]
        high["origin_hypothesis_id"] = "WH-HIGH"
        high["seed_id"] = "OS-HIGH"
        low = copy.deepcopy(high)
        low["origin_hypothesis_id"] = "WH-LOW"
        low["seed_id"] = "OS-LOW"
        state["hypothesis_ledger"] = {"hypotheses": [
            {"hypothesis_id": "WH-HIGH", "exploration_priority": {"score": 9}},
            {"hypothesis_id": "WH-LOW", "exploration_priority": {"score": 1}},
        ]}

        self.assertLess(
            candidate_gap_engine._candidate_rank(state, high),
            candidate_gap_engine._candidate_rank(state, low),
        )
        low["why_market_may_miss"] = "one fewer local blocker"
        self.assertLess(
            candidate_gap_engine._candidate_rank(state, low),
            candidate_gap_engine._candidate_rank(state, high),
        )

    def test_seed_local_gap_research_can_run_before_root_convergence(self):
        state = fixture_state(missing_expectation=True)
        state["last_convergence"] = {"decision": "continue"}
        state["cruxes"]["C1"]["status"] = "OPEN"
        state["landscape_map"]["paths"][0]["state"] = "UNKNOWN"
        opportunity_engine.refresh_candidate_states(state)

        result = candidate_gap_engine.plan_tasks(state)

        self.assertEqual(result["status"], "candidate_gap_tasks_planned")
        self.assertEqual(result["planning_phase"], "PARALLEL_PRE_SCREEN_RESEARCH")
        self.assertTrue(result["candidate_screen_gate_unchanged"])
        self.assertEqual(result["tasks"][0]["blocker_code"], "missing_expectation_gap")
        self.assertEqual(
            opportunity_engine.candidate_state(
                state, state["opportunity_seeds"][0]
            ),
            opportunity_engine.EVIDENCE_BACKED,
        )

    def test_plan_creates_bounded_task_without_mutating_seed(self):
        state = fixture_state()
        before = copy.deepcopy(state["opportunity_seeds"])
        result = candidate_gap_engine.plan_tasks(state)
        self.assertEqual(result["status"], "candidate_gap_tasks_planned")
        self.assertEqual(result["task_count"], 1)
        task = result["tasks"][0]
        self.assertEqual(task["blocker_code"], "insufficient_independent_seed_sources")
        self.assertEqual(task["search_budget"], 4)
        self.assertEqual(state["opportunity_seeds"], before)
        self.assertEqual(candidate_gap_engine.validate_histories(state), [])

    def test_plan_skips_seed_blocked_by_immutable_landscape_gate(self):
        state = fixture_state()
        state["opportunity_seeds"][0]["evidence"].append(
            citation("customer-source.com", "customer confirms contracted use")
        )
        state["landscape_map"]["paths"][0]["state"] = "UNKNOWN"
        opportunity_engine.refresh_candidate_states(state)

        assessment = opportunity_engine.assess_seed(
            state, state["opportunity_seeds"][0]
        )
        self.assertEqual(assessment["evidence_maturity"], "READY_FOR_SCREENING")
        self.assertIn("landscape_path_not_supported", assessment["blockers"])

        before = copy.deepcopy(state["opportunity_seeds"])
        result = candidate_gap_engine.plan_tasks(state)
        self.assertEqual(result["status"], "no_candidate_gap_tasks")
        self.assertEqual(result["tasks"], [])
        self.assertEqual(state["candidate_gap_tasks"], [])
        self.assertEqual(state["opportunity_seeds"], before)

    def test_same_publisher_cannot_satisfy_independent_source(self):
        state = fixture_state()
        task = candidate_gap_engine.plan_tasks(state)["tasks"][0]
        duplicate = supplement(task, "issuer-source.org")
        duplicate["citation"]["url"] = "https://issuer-source.org/another/specific-page"
        with self.assertRaisesRegex(ValueError, "not independent"):
            candidate_gap_engine.submit_supplement(state, task["task_id"], duplicate)
        self.assertEqual(state["candidate_evidence_supplements"], [])

    def test_attempted_publisher_cannot_be_reused_with_a_new_alignment(self):
        state = fixture_state()
        task = candidate_gap_engine.plan_tasks(state)["tasks"][0]
        first = supplement(task, "customer-source.com", alignment="NOT_ALIGNED")
        candidate_gap_engine.submit_supplement(state, task["task_id"], first)
        with self.assertRaisesRegex(ValueError, "previously attempted publisher"):
            candidate_gap_engine.submit_supplement(
                state,
                task["task_id"],
                supplement(task, "customer-source.com", alignment="SUPPORTED"),
            )

    def test_supported_supplement_matures_effective_seed_without_rewriting_original(self):
        state = fixture_state()
        original = copy.deepcopy(state["opportunity_seeds"][0])
        task = candidate_gap_engine.plan_tasks(state)["tasks"][0]
        result = candidate_gap_engine.submit_supplement(
            state, task["task_id"], supplement(task, "customer-source.com")
        )
        self.assertEqual(result["candidate_state"], "READY_FOR_SCREENING")
        self.assertEqual(state["opportunity_seeds"][0]["evidence"], original["evidence"])
        effective = opportunity_engine.effective_seed(state, state["opportunity_seeds"][0])
        self.assertEqual(len(effective["evidence"]), 2)
        self.assertEqual(
            opportunity_engine.assess_seed(state, state["opportunity_seeds"][0])["screening_status"],
            "READY_FOR_SCREENING",
        )
        self.assertEqual(candidate_gap_engine.validate_histories(state), [])

    def test_supported_field_addition_fills_missing_contract_without_seed_edit(self):
        state = fixture_state(missing_expectation=True)
        task = candidate_gap_engine.plan_tasks(state)["tasks"][0]
        self.assertEqual(task["blocker_code"], "missing_expectation_gap")
        result = candidate_gap_engine.submit_supplement(
            state,
            task["task_id"],
            supplement(
                task,
                "customer-source.com",
                field_additions={
                    "why_market_may_miss": "customer evidence is absent from the current baseline"
                },
            ),
        )
        self.assertEqual(result["candidate_state"], "READY_FOR_SCREENING")
        self.assertEqual(state["opportunity_seeds"][0]["why_market_may_miss"], "")
        effective = opportunity_engine.effective_seed(state, state["opportunity_seeds"][0])
        self.assertTrue(effective["why_market_may_miss"])

    def test_nested_field_addition_fills_only_missing_pricing_anchor_key(self):
        state = fixture_state()
        state["opportunity_seeds"][0]["pricing_anchor"]["comparison_value"] = ""
        opportunity_engine.refresh_candidate_states(state)
        task = candidate_gap_engine.plan_tasks(state)["tasks"][0]
        result = candidate_gap_engine.submit_supplement(
            state,
            task["task_id"],
            supplement(
                task,
                "customer-source.com",
                field_additions={"pricing_anchor": {"comparison_value": "50 MW contracted"}},
            ),
        )
        self.assertEqual(result["candidate_state"], "READY_FOR_SCREENING")
        original = state["opportunity_seeds"][0]["pricing_anchor"]
        self.assertEqual(original["comparison_value"], "")
        effective = opportunity_engine.effective_seed(state, state["opportunity_seeds"][0])
        self.assertEqual(effective["pricing_anchor"]["comparison_value"], "50 MW contracted")
        with self.assertRaisesRegex(ValueError, "already resolved"):
            candidate_gap_engine.submit_supplement(
                state,
                task["task_id"],
                supplement(
                    task,
                    "another-source.org",
                    field_additions={"pricing_anchor": {"metric": "changed metric"}},
                ),
            )

    def test_sequential_tasks_project_prior_support_without_rewriting_seed(self):
        state = fixture_state()
        state["opportunity_seeds"][0]["economic_exposure"] = ""
        state["opportunity_seeds"][0]["pricing_anchor"]["comparison_value"] = ""
        opportunity_engine.refresh_candidate_states(state)
        first = candidate_gap_engine.plan_tasks(state)["tasks"][0]
        self.assertEqual(first["field_target"], "economic_exposure")
        candidate_gap_engine.submit_supplement(
            state,
            first["task_id"],
            supplement(
                first,
                "customer-source.com",
                field_additions={"economic_exposure": "owns the contracted capacity"},
            ),
        )
        second = candidate_gap_engine.plan_tasks(state)["tasks"][0]
        self.assertEqual(second["field_target"], "pricing_anchor")
        self.assertEqual(
            second["excluded_publishers"],
            ["customer-source.com", "issuer-source.org"],
        )
        result = candidate_gap_engine.submit_supplement(
            state,
            second["task_id"],
            supplement(
                second,
                "market-data-source.net",
                field_additions={"pricing_anchor": {"comparison_value": "50 MW contracted"}},
            ),
        )
        self.assertEqual(result["candidate_state"], "READY_FOR_SCREENING")
        self.assertEqual(state["opportunity_seeds"][0]["economic_exposure"], "")
        self.assertEqual(candidate_gap_engine.validate_histories(state), [])

    def test_contradiction_is_preserved_and_blocks_screening(self):
        state = fixture_state()
        task = candidate_gap_engine.plan_tasks(state)["tasks"][0]
        candidate_gap_engine.submit_supplement(
            state,
            task["task_id"],
            supplement(task, "customer-source.com", alignment="CONTRADICTED"),
        )
        assessment = opportunity_engine.assess_seed(state, state["opportunity_seeds"][0])
        self.assertEqual(assessment["screening_status"], "EVIDENCE_BACKED")
        self.assertIn("candidate_evidence_contradicted", assessment["blockers"])
        self.assertEqual(candidate_gap_engine.plan_tasks(state)["task_count"], 0)

    def test_four_not_aligned_attempts_close_source_exhausted(self):
        state = fixture_state()
        task = candidate_gap_engine.plan_tasks(state)["tasks"][0]
        for index in range(4):
            candidate_gap_engine.submit_supplement(
                state,
                task["task_id"],
                supplement(
                    task,
                    f"unrelated-{index}.net",
                    alignment="NOT_ALIGNED",
                ),
            )
        resolution = candidate_gap_engine.latest_resolution_for_seed(
            state, task["seed_id"]
        )
        self.assertEqual(resolution["status"], "SOURCE_EXHAUSTED")
        assessment = opportunity_engine.assess_seed(state, state["opportunity_seeds"][0])
        self.assertIn("candidate_gap_source_exhausted", assessment["blockers"])
        with self.assertRaisesRegex(ValueError, "already resolved"):
            candidate_gap_engine.submit_supplement(
                state,
                task["task_id"],
                supplement(task, "late-source.net", alignment="NOT_ALIGNED"),
            )

    def test_manual_waiting_event_closure_is_hashed_and_terminal(self):
        state = fixture_state()
        task = candidate_gap_engine.plan_tasks(state)["tasks"][0]
        result = candidate_gap_engine.close_task(
            state, task["task_id"], "WAITING_EVENT", "wait for regulator docket"
        )
        self.assertEqual(result["resolution"]["status"], "WAITING_EVENT")
        self.assertEqual(candidate_gap_engine.validate_histories(state), [])

    def test_task_content_tampering_fails_history_validation(self):
        state = fixture_state()
        task = candidate_gap_engine.plan_tasks(state)["tasks"][0]
        task["search_budget"] = 99
        state["candidate_gap_tasks"][0]["search_budget"] = 99
        blockers = candidate_gap_engine.validate_histories(state)
        self.assertIn("candidate_gap_task_hash_invalid", blockers)
        self.assertIn("candidate_gap_task_identity_invalid", blockers)

    def test_orchestrator_continues_from_gap_task_to_candidate_screen(self):
        state = fixture_state()
        saved = []
        with patch.object(orchestrator, "_load", return_value=state), patch.object(
            orchestrator, "_save", side_effect=lambda topic, current: saved.append(topic)
        ):
            planned = orchestrator.cmd_plan_candidate_gaps("candidate-gap-fixture")
            task = planned["tasks"][0]
            submitted = orchestrator.cmd_submit_gap_evidence(
                "candidate-gap-fixture",
                task["task_id"],
                supplement(task, "customer-source.com"),
            )
        self.assertEqual(planned["status"], "candidate_gap_tasks_planned")
        self.assertEqual(submitted["status"], "dispatch_candidate_screeners")
        self.assertEqual(submitted["candidate_seed_ids"], [task["seed_id"]])
        self.assertEqual(submitted["gap_evidence_status"], "candidate_gap_evidence_recorded")
        self.assertGreaterEqual(len(saved), 2)


if __name__ == "__main__":
    unittest.main()
