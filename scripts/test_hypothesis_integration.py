#!/usr/bin/env python3
"""Cross-engine regression tests for the v0.10 exploration architecture."""

import copy
import os
import tempfile
import unittest
from unittest import mock

import deepthink_orchestrator_v2 as orchestrator
import hypothesis_engine
import landscape_engine
import opportunity_engine
import report_v2
import research_output
from test_hypothesis_engine import citation, frame as hypothesis_frame, garden, proxy
from test_landscape_engine import orchestrator_frame
from test_opportunity_engine import (
    detective_payload,
    research_state,
    seed,
)
from test_v2_engine import converged_state


def explicit_hybrid_frame():
    """Upgrade a complete legacy universe frame to the explicit v0.10 garden."""
    raw = orchestrator_frame()
    raw.pop("landscape_map", None)
    raw["research_intent"] = "HYBRID"
    raw["hypothesis_garden"] = {"wild_hypotheses": garden()}
    return raw


class OrchestratorIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_scratch = os.environ.get("TRADE_NOTHING_SCRATCH_DIR")
        self.old_evolution = os.environ.get("TRADE_NOTHING_EVOLUTION_PATH")
        os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.tmp.name
        os.environ["TRADE_NOTHING_EVOLUTION_PATH"] = os.path.join(
            self.tmp.name, "missing.md"
        )

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

    def plan_and_authorize(self, topic, design=None):
        planned = orchestrator.cmd_plan_exploration(topic, design)
        self.assertEqual(planned["status"], "exploration_action_planned")
        action_id = planned["action_id"]
        authorized = orchestrator.cmd_authorize_exploration(
            topic,
            action_id,
            {
                "action_id": action_id,
                "explicit_user_authorization": True,
                "authorization_scope": "ONE_BOUNDED_EXPLORATION_ACTION",
                "authorization_note": "user approved this exact bounded route",
            },
        )
        self.assertEqual(
            authorized["status"], "dispatch_authorized_exploration"
        )
        return planned

    def document(self, proposal, domain="fixture-research.org", **overrides):
        item = {
            "claim": "A dated proxy observation was reported.",
            "source": "Official Test Publisher",
            "url": f"https://{domain}/reports/proxy-observation",
            "date": "2026-07-10",
            "source_tier": "primary",
            "publisher_class": proposal["source_class"],
        }
        item.update(overrides)
        return item

    def result(
        self,
        planned,
        execution_status="OBSERVATION_RECORDED",
        document=None,
    ):
        proposal = planned["proposal"]
        action_id = planned["action_id"]
        documents = [] if document is None else [document]
        proxy_trail = None
        if execution_status in {
            "OBSERVATION_RECORDED", "FALSIFIED_ROUTE"
        }:
            route = proposal["route_spec"]
            proxy_trail = {
                "route_id": route["route_id"],
                "planned_proxy": route["proxy"],
                "observation": "Actual dated observation from the receipt",
                "origin_crux": route["origin_crux"],
                "causal_link": route["causal_link"],
                "direction": (
                    "CONTRADICTS"
                    if execution_status == "FALSIFIED_ROUTE"
                    else "AMBIGUOUS"
                ),
                "alternative_explanation": "Ordinary reporting cadence",
                "checkpoint": "next official update",
                "next_source_class": proposal["source_class"],
                "bounded_query": proposal["bounded_query"],
                "stop_condition": proposal["stop_condition"],
                "evidence": [document] if document else [],
            }
        return {
            "action_id": action_id,
            "as_of_date": proposal["as_of_date"],
            "execution_status": execution_status,
            "query_executed": proposal["bounded_query"],
            "search_count": 1,
            "documents_read": documents,
            "automatic_follow_on": False,
            "stop_reason": "the exact one-action route stopped",
            "proxy_trail": proxy_trail,
        }

    def test_init_binds_explicit_garden_to_landscape_without_promotion(self):
        topic = "explicit hypothesis garden integration"
        result = orchestrator.cmd_init(topic, explicit_hybrid_frame())
        self.assertEqual(result["status"], "dispatch_subagents")
        self.assertTrue(result["hypothesis_exploration"]["exploration_enabled"])
        self.assertTrue(
            result["exploration_action"]["requires_human_authorization"]
        )

        state = orchestrator._load(topic)
        hypotheses = state["hypothesis_ledger"]["hypotheses"]
        paths = state["landscape_map"]["paths"]
        self.assertEqual(len(hypotheses), 5)
        self.assertEqual(len(paths), 5)
        self.assertEqual(
            {item["state"] for item in hypotheses},
            {"HYPOTHESIS_ONLY"},
        )
        hypothesis_ids = {item["hypothesis_id"] for item in hypotheses}
        self.assertEqual(
            {item["hypothesis_id"] for item in paths},
            hypothesis_ids,
        )
        self.assertEqual(state.get("opportunity_seeds", []), [])

    def test_explicit_garden_wins_when_legacy_map_is_also_present(self):
        raw = explicit_hybrid_frame()
        raw["landscape_map"] = {
            "paths": [
                {
                    "path_id": "LEGACY-ONLY",
                    "hypothesis": "A stale legacy path",
                }
            ]
        }
        selected = landscape_engine.frame_paths(raw)
        self.assertIs(
            selected,
            raw["hypothesis_garden"]["wild_hypotheses"],
        )

    def test_landscape_reads_all_public_hypothesis_garden_aliases(self):
        paths = garden()
        for raw in (
            {"hypothesis_garden": paths},
            {"wild_hypotheses": paths},
        ):
            with self.subTest(raw=raw):
                self.assertIs(landscape_engine.frame_paths(raw), paths)

    def test_explicitly_authorized_exploration_is_bounded_and_nonpromotional(self):
        topic = "authorized exploration integration"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        before = orchestrator._load(topic)
        formal_before = orchestrator._formal_surface_digest(before)

        planned = orchestrator.cmd_plan_exploration(topic)
        self.assertEqual(planned["status"], "exploration_action_planned")
        action_id = planned["action_id"]
        planned_state = orchestrator._load(topic)
        planned_projection = hypothesis_engine.report_view(
            planned_state
        )["exploration_action"]
        self.assertEqual(planned_projection["action_id"], action_id)
        self.assertEqual(
            planned_projection["host_action_status"],
            "PLANNED_NOT_AUTHORIZED",
        )
        planned_memo = research_output.render_resolution_memo(
            planned_state
        )
        self.assertIn(action_id, planned_memo)
        self.assertIn("PLANNED_NOT_AUTHORIZED", planned_memo)
        rejected = orchestrator.cmd_authorize_exploration(
            topic,
            action_id,
            {
                "action_id": action_id,
                "explicit_user_authorization": False,
                "authorization_scope": "ONE_BOUNDED_EXPLORATION_ACTION",
                "authorization_note": "not actually authorized",
            },
        )
        self.assertEqual(
            rejected["status"], "exploration_authorization_rejected"
        )
        authorized = orchestrator.cmd_authorize_exploration(
            topic,
            action_id,
            {
                "action_id": action_id,
                "explicit_user_authorization": True,
                "authorization_scope": "ONE_BOUNDED_EXPLORATION_ACTION",
                "authorization_note": "user approved exactly this one probe",
            },
        )
        self.assertEqual(
            authorized["status"], "dispatch_authorized_exploration"
        )
        dispatch = authorized["dispatch_contract"]
        self.assertEqual(
            dispatch["runtime_failure_result_schema"]["documents_read"],
            [],
        )
        self.assertIsNone(
            dispatch["runtime_failure_result_schema"]["query_executed"]
        )
        self.assertEqual(
            dispatch["in_query_failure_result_schema"]["documents_read"],
            [],
        )
        self.assertEqual(
            dispatch["in_query_failure_result_schema"][
                "documents_read_cardinality"
            ],
            "0..3",
        )
        self.assertIsInstance(
            dispatch["in_query_failure_result_schema"][
                "documents_read_item_schema"
            ],
            dict,
        )
        stored_action = next(
            item
            for item in orchestrator._load(topic)["exploration_actions"]
            if item["action_id"] == action_id
        )
        exhausted = copy.deepcopy(
            dispatch["exhausted_result_schema"]
        )
        self.assertEqual(
            orchestrator._validate_exploration_result(
                stored_action, exhausted
            )[0],
            "EXHAUSTED",
        )
        self.assertIsNone(exhausted["proxy_trail"])
        self.assertEqual(
            dispatch["falsified_result_schema"]["proxy_trail"][
                "direction"
            ],
            "CONTRADICTS",
        )
        in_flight = hypothesis_engine.exploration_action(
            orchestrator._load(topic)
        )
        self.assertEqual(
            in_flight["action_code"], "AUTHORIZED_ACTION_IN_FLIGHT"
        )
        self.assertEqual(
            in_flight["authorization_state"],
            "AUTHORIZED_NOT_EXECUTED",
        )
        authorized_memo = research_output.render_resolution_memo(
            orchestrator._load(topic)
        )
        self.assertIn(action_id, authorized_memo)
        self.assertIn("AUTHORIZED_NOT_EXECUTED", authorized_memo)
        self.assertIn(
            "CALLER_ATTESTED_NOT_HOST_VERIFIED", authorized_memo
        )
        self.assertEqual(
            in_flight["budget_boundary"]["max_bounded_queries"], 0
        )
        proposal = planned["proposal"]
        state = orchestrator._load(topic)
        hypothesis = next(
            item
            for item in state["hypothesis_ledger"]["hypotheses"]
            if item["hypothesis_id"] == proposal["hypothesis_id"]
        )
        origin_crux = hypothesis["context"]["origin_crux"]
        document = {
            "claim": "A dated proxy observation was reported.",
            "source": "Official Test Publisher",
            "url": "https://fixture-research.org/reports/proxy-observation",
            "date": "2026-07-10",
            "source_tier": "primary",
            "publisher_class": proposal["source_class"],
        }
        result = {
            "action_id": action_id,
            "as_of_date": proposal["as_of_date"],
            "execution_status": "OBSERVATION_RECORDED",
            "query_executed": proposal["bounded_query"],
            "search_count": 1,
            "documents_read": [document],
            "automatic_follow_on": False,
            "stop_reason": "one admissible observation found",
            "proxy_trail": {
                "route_id": proposal["route_spec"]["route_id"],
                "planned_proxy": proposal["route_spec"]["proxy"],
                "observation": "A dated proxy observation",
                "origin_crux": origin_crux,
                "causal_link": proposal["route_spec"]["causal_link"],
                "direction": "AMBIGUOUS",
                "alternative_explanation": "Ordinary reporting cadence",
                "checkpoint": "next official update",
                "next_source_class": proposal["source_class"],
                "bounded_query": proposal["bounded_query"],
                "stop_condition": proposal["stop_condition"],
                "evidence": [document],
            },
        }
        recorded = orchestrator.cmd_submit_exploration_result(
            topic, action_id, result
        )
        self.assertEqual(
            recorded["status"], "exploration_result_recorded"
        )
        self.assertTrue(recorded["formal_state_unchanged"])
        self.assertFalse(recorded["automatic_follow_on"])
        after = orchestrator._load(topic)
        self.assertEqual(
            orchestrator._formal_surface_digest(after), formal_before
        )
        self.assertEqual(after.get("opportunity_seeds", []), [])
        completed_memo = research_output.render_resolution_memo(after)
        self.assertIn(action_id, completed_memo)
        self.assertIn(
            "CALLER_ATTESTED_NOT_HOST_VERIFIED", completed_memo
        )
        updated = next(
            item
            for item in after["hypothesis_ledger"]["hypotheses"]
            if item["hypothesis_id"] == proposal["hypothesis_id"]
        )
        self.assertEqual(updated["state"], "TRACED")
        replay = orchestrator.cmd_submit_exploration_result(
            topic, action_id, result
        )
        self.assertEqual(
            replay["status"], "exploration_result_not_accepted"
        )

    def test_authorized_exploration_rejects_document_budget_overrun(self):
        topic = "authorized exploration budget"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = orchestrator.cmd_plan_exploration(topic)
        action_id = planned["action_id"]
        orchestrator.cmd_authorize_exploration(
            topic,
            action_id,
            {
                "action_id": action_id,
                "explicit_user_authorization": True,
                "authorization_scope": "ONE_BOUNDED_EXPLORATION_ACTION",
                "authorization_note": "one bounded test",
            },
        )
        proposal = planned["proposal"]
        documents = [
            {
                "claim": f"Document {index}",
                "source": f"Publisher {index}",
                "url": f"https://fixture-research.org/reports/{index}",
                "date": "2026-07-10",
                "publisher_class": proposal["source_class"],
            }
            for index in range(4)
        ]
        rejected = orchestrator.cmd_submit_exploration_result(
            topic,
            action_id,
            {
                "action_id": action_id,
                "as_of_date": proposal["as_of_date"],
                "execution_status": "EXHAUSTED",
                "query_executed": proposal["bounded_query"],
                "search_count": 1,
                "documents_read": documents,
                "automatic_follow_on": False,
                "stop_reason": "budget exhausted",
                "proxy_trail": None,
            },
        )
        self.assertEqual(rejected["status"], "exploration_result_rejected")
        self.assertIn("document_budget_exceeded", rejected["reason"])

    def test_evidence_must_exactly_reuse_document_receipt(self):
        topic = "authorized exploration exact evidence binding"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = self.plan_and_authorize(topic)
        document = self.document(planned["proposal"])
        result = self.result(planned, document=document)
        result["proxy_trail"]["evidence"][0] = {
            **document,
            "claim": "A fabricated scarcity claim using the same URL.",
            "source": "Different Publisher Label",
        }
        rejected = orchestrator.cmd_submit_exploration_result(
            topic, planned["action_id"], result
        )
        self.assertEqual(rejected["status"], "exploration_result_rejected")
        self.assertIn("not_in_read_receipt", rejected["reason"])

    def test_route_identity_and_origin_are_exactly_bound(self):
        topic = "authorized exploration route binding"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = self.plan_and_authorize(topic)
        document = self.document(planned["proposal"])
        result = self.result(planned, document=document)
        result["proxy_trail"]["route_id"] = "XR-SPOOFED"
        rejected = orchestrator.cmd_submit_exploration_result(
            topic, planned["action_id"], result
        )
        self.assertEqual(rejected["status"], "exploration_result_rejected")
        self.assertIn("route_id_mismatch", rejected["reason"])

    def test_document_date_and_publisher_domain_budgets_fail_closed(self):
        topic = "authorized exploration receipt boundaries"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = self.plan_and_authorize(topic)
        future = self.document(
            planned["proposal"], date="2026-07-16"
        )
        rejected = orchestrator.cmd_submit_exploration_result(
            topic,
            planned["action_id"],
            self.result(planned, document=future),
        )
        self.assertEqual(rejected["status"], "exploration_result_rejected")
        self.assertIn("after_as_of", rejected["reason"])

        month_only = self.document(
            planned["proposal"], date="2026-07"
        )
        rejected = orchestrator.cmd_submit_exploration_result(
            topic,
            planned["action_id"],
            self.result(planned, document=month_only),
        )
        self.assertEqual(rejected["status"], "exploration_result_rejected")
        self.assertIn("day_precision", rejected["reason"])

        first = self.document(
            planned["proposal"], domain="publisher-one.org"
        )
        second = self.document(
            planned["proposal"],
            domain="publisher-two.net",
            url="https://publisher-two.net/reports/second",
            claim="A second dated document.",
        )
        result = self.result(planned, document=first)
        result["documents_read"] = [first, second]
        rejected = orchestrator.cmd_submit_exploration_result(
            topic, planned["action_id"], result
        )
        self.assertEqual(rejected["status"], "exploration_result_rejected")
        self.assertIn("publisher_domain_budget", rejected["reason"])

    def test_independent_publisher_action_rejects_existing_domain(self):
        topic = "independent publisher exact gate"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = self.plan_and_authorize(topic)
        proposal = copy.deepcopy(planned["proposal"])
        proposal["action_code"] = "SEEK_INDEPENDENT_PUBLISHER"
        proposal["excluded_existing_domains"] = ["existing-publisher.org"]
        record = {
            "action_id": planned["action_id"],
            "proposal": proposal,
        }
        document = self.document(
            proposal, domain="existing-publisher.org"
        )
        result = self.result(
            {**planned, "proposal": proposal}, document=document
        )
        with self.assertRaisesRegex(
            ValueError, "independent_publisher_required"
        ):
            orchestrator._validate_exploration_result(record, result)

    def test_falsified_route_is_evidence_bound_visible_negative_knowledge(self):
        topic = "authorized exploration falsified route"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = self.plan_and_authorize(topic)
        first_hypothesis = planned["proposal"]["hypothesis_id"]
        document = self.document(
            planned["proposal"],
            claim="The official observation contradicts the planned mechanism.",
        )
        recorded = orchestrator.cmd_submit_exploration_result(
            topic,
            planned["action_id"],
            self.result(
                planned,
                execution_status="FALSIFIED_ROUTE",
                document=document,
            ),
        )
        self.assertEqual(recorded["status"], "exploration_result_recorded")
        state = orchestrator._load(topic)
        history = state["hypothesis_ledger"]["authorized_action_audits"]
        self.assertEqual(history[-1]["execution_status"], "FALSIFIED_ROUTE")
        self.assertTrue(history[-1]["negative_knowledge"])
        self.assertEqual(len(state["hypothesis_ledger"]["closed_routes"]), 1)
        hypothesis = next(
            item for item in state["hypothesis_ledger"]["hypotheses"]
            if item["hypothesis_id"] == first_hypothesis
        )
        self.assertEqual(
            hypothesis["proxy_trails"][0]["direction"], "CONTRADICTS"
        )
        next_action = hypothesis_engine.exploration_action(state)
        self.assertNotEqual(next_action["hypothesis_id"], first_hypothesis)
        markdown = research_output.render_resolution_memo({
            **state,
            "last_convergence": {
                "decision": "fuse_break",
                "reason": "BLOCKED_MAX_ROUNDS",
            },
        })
        self.assertIn(planned["action_id"], markdown)
        self.assertIn("FALSIFIED_ROUTE", markdown)

    def test_exhausted_route_closes_only_that_route_and_falls_through(self):
        topic = "authorized exploration exhausted route"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = self.plan_and_authorize(topic)
        first_hypothesis = planned["proposal"]["hypothesis_id"]
        recorded = orchestrator.cmd_submit_exploration_result(
            topic,
            planned["action_id"],
            self.result(planned, execution_status="EXHAUSTED"),
        )
        self.assertEqual(recorded["status"], "exploration_result_recorded")
        state = orchestrator._load(topic)
        self.assertEqual(
            state["hypothesis_ledger"]["closed_routes"][0][
                "execution_status"
            ],
            "EXHAUSTED",
        )
        next_action = hypothesis_engine.exploration_action(state)
        self.assertNotEqual(next_action["hypothesis_id"], first_hypothesis)
        self.assertNotEqual(
            next_action["action_code"],
            "NO_FOLLOW_ON_AFTER_BOUNDED_ACTION",
        )

    def test_typed_design_supplement_makes_missing_route_plannable(self):
        topic = "typed exploration design supplement"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        state = orchestrator._load(topic)
        for item in state["hypothesis_ledger"]["hypotheses"]:
            item["proxy_plan"] = []
        orchestrator._save(topic, state)
        base = hypothesis_engine.exploration_action(
            orchestrator._load(topic)
        )
        self.assertEqual(base["authorization_state"], "NEEDS_ACTION_DESIGN")
        design = {
            "design_reviewed": True,
            "design_scope": "ONE_EXPLORATION_LEDGER_DESIGN",
            "design_note": "reviewed ledger design, not execution authority",
            "design_target_id": base["design_target_id"],
            "expected_state_revision": base["design_state_revision"],
            "hypothesis_id": base["hypothesis_id"],
            "action_code": base["action_code"],
            "proxy_plan": [
                {
                    "proxy": "Official physical-flow series",
                    "causal_link": (
                        "Separates physical constraint from narrative noise"
                    ),
                    "direction": "SUPPORTS",
                    "publisher_class": "REGULATOR_OR_OFFICIAL_DATASET",
                    "bounded_query": "one official physical-flow series",
                    "stop_condition": "stop after one bounded query",
                },
                {
                    "proxy": "Official cancellation series",
                    "causal_link": (
                        "A cancellation rise contradicts durable scarcity"
                    ),
                    "direction": "CONTRADICTS",
                    "publisher_class": "REGULATOR_OR_OFFICIAL_DATASET",
                    "bounded_query": "one official cancellation series",
                    "stop_condition": "stop after one bounded query",
                },
            ],
        }
        duplicate_routes = copy.deepcopy(design)
        duplicate_routes["proxy_plan"][1] = {
            **copy.deepcopy(duplicate_routes["proxy_plan"][0]),
            "direction": "CONTRADICTS",
        }
        rejected = orchestrator.cmd_record_exploration_design(
            topic, duplicate_routes
        )
        self.assertEqual(rejected["status"], "exploration_design_rejected")
        self.assertIn("distinct_diagnostic_routes", rejected["reason"])
        recorded = orchestrator.cmd_record_exploration_design(topic, design)
        self.assertEqual(recorded["status"], "exploration_design_recorded")
        self.assertTrue(recorded["formal_state_unchanged"])
        planned = orchestrator.cmd_plan_exploration(topic)
        self.assertEqual(planned["status"], "exploration_action_planned")
        self.assertTrue(planned["proposal"]["authorization_ready"])
        self.assertEqual(
            planned["proposal"]["authorization_state"],
            "PROPOSED_NOT_AUTHORIZED",
        )
        self.assertTrue(planned["proposal"]["route_spec"]["route_id"])

    def test_alternative_design_unblocks_traced_hypothesis_without_search(self):
        topic = "typed alternative explanation design"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        state = orchestrator._load(topic)
        for item in state["hypothesis_ledger"]["hypotheses"]:
            item["proxy_plan"] = []
        target = state["hypothesis_ledger"]["hypotheses"][0]
        target["strongest_alternative_explanation"] = ""
        hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "proxy_trails": [{
                    "hypothesis_id": target["hypothesis_id"],
                    "origin_crux": "C1",
                    "proxy": "Unverified physical-flow clue",
                    "causal_link": "Tests whether the physical constraint exists",
                    "direction": "AMBIGUOUS",
                }]
            },
            inquisitor={},
            allowed_crux_ids=["C1"],
        )
        orchestrator._save(topic, state)
        action = hypothesis_engine.exploration_action(
            orchestrator._load(topic)
        )
        self.assertEqual(
            action["action_code"], "ARTICULATE_STRONGEST_ALTERNATIVE"
        )
        recorded = orchestrator.cmd_record_exploration_design(
            topic,
            {
                "design_reviewed": True,
                "design_scope": "ONE_EXPLORATION_LEDGER_DESIGN",
                "design_note": "reviewed ordinary explanation",
                "design_target_id": action["design_target_id"],
                "expected_state_revision": action[
                    "design_state_revision"
                ],
                "hypothesis_id": action["hypothesis_id"],
                "action_code": action["action_code"],
                "strongest_alternative_explanation": (
                    "Ordinary inventory timing explains the clue"
                ),
                "cheap_discriminating_test": (
                    "Compare physical flow with inventory normalization"
                ),
            },
        )
        self.assertEqual(recorded["status"], "exploration_design_recorded")
        self.assertNotEqual(
            recorded["exploration_action"]["action_code"],
            "ARTICULATE_STRONGEST_ALTERNATIVE",
        )
        current = orchestrator._load(topic)
        target = next(
            item
            for item in current["hypothesis_ledger"]["hypotheses"]
            if item["hypothesis_id"] == action["hypothesis_id"]
        )
        self.assertEqual(
            target["strongest_alternative_explanation"],
            "Ordinary inventory timing explains the clue",
        )

    def test_stale_design_target_cannot_apply_after_context_change(self):
        topic = "stale exploration design target"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        state = orchestrator._load(topic)
        for item in state["hypothesis_ledger"]["hypotheses"]:
            item["proxy_plan"] = []
        orchestrator._save(topic, state)
        old_action = hypothesis_engine.exploration_action(
            orchestrator._load(topic)
        )
        current = orchestrator._load(topic)
        target = next(
            item
            for item in current["hypothesis_ledger"]["hypotheses"]
            if item["hypothesis_id"] == old_action["hypothesis_id"]
        )
        target["cheap_discriminating_test"] = (
            "A materially changed diagnostic question"
        )
        orchestrator._save(topic, current)
        stale = orchestrator.cmd_record_exploration_design(
            topic,
            {
                "design_reviewed": True,
                "design_scope": "ONE_EXPLORATION_LEDGER_DESIGN",
                "design_note": "stale design should not apply",
                "design_target_id": old_action["design_target_id"],
                "expected_state_revision": old_action[
                    "design_state_revision"
                ],
                "hypothesis_id": old_action["hypothesis_id"],
                "action_code": old_action["action_code"],
                "proxy_plan": [
                    {
                        "proxy": "First stale route",
                        "causal_link": "First stale causal link",
                        "direction": "SUPPORTS",
                        "publisher_class": "REGULATOR_DATA",
                        "bounded_query": "first stale query",
                        "stop_condition": "one query",
                    },
                    {
                        "proxy": "Second stale route",
                        "causal_link": "Second stale causal link",
                        "direction": "CONTRADICTS",
                        "publisher_class": "REGULATOR_DATA",
                        "bounded_query": "second stale query",
                        "stop_condition": "one query",
                    },
                ],
            },
        )
        self.assertEqual(stale["status"], "exploration_design_rejected")
        self.assertIn(
            stale["reason"],
            {
                "exploration_design_target_mismatch",
                "exploration_design_state_revision_mismatch",
            },
        )

    def test_second_proxy_design_must_use_new_diagnostic_identity(self):
        topic = "second proxy diagnostic identity"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        state = orchestrator._load(topic)
        for item in state["hypothesis_ledger"]["hypotheses"]:
            item["proxy_plan"] = []
        target = state["hypothesis_ledger"]["hypotheses"][0]
        target["proxy_trails"] = [{
            "proxy_id": "PT-FIRST",
            "proxy": "Existing physical-flow diagnostic",
            "causal_link": "Existing causal diagnostic",
            "direction": "AMBIGUOUS",
            "origin_crux": "C1",
            "origin_cruxes": ["C1"],
            "evidence": [],
        }]
        hypothesis_engine._refresh(target)
        orchestrator._save(topic, state)
        action = hypothesis_engine.exploration_action(
            orchestrator._load(topic)
        )
        self.assertEqual(
            action["action_code"], "COLLECT_SECOND_PROXY_EVIDENCE"
        )
        rejected = orchestrator.cmd_record_exploration_design(
            topic,
            {
                "design_reviewed": True,
                "design_scope": "ONE_EXPLORATION_LEDGER_DESIGN",
                "design_note": "same diagnostic must not masquerade as second",
                "design_target_id": action["design_target_id"],
                "expected_state_revision": action[
                    "design_state_revision"
                ],
                "hypothesis_id": action["hypothesis_id"],
                "action_code": action["action_code"],
                "proxy_plan": [{
                    "proxy": "Existing physical-flow diagnostic",
                    "causal_link": "Existing causal diagnostic",
                    "direction": "SUPPORTS",
                    "publisher_class": "SECOND_PUBLISHER",
                    "bounded_query": "different query for same diagnostic",
                    "stop_condition": "one query",
                }],
            },
        )
        self.assertEqual(rejected["status"], "exploration_design_rejected")
        self.assertIn("second_proxy_must_be_distinct", rejected["reason"])

    def test_reviewed_resolution_unblocks_contested_alternative(self):
        topic = "contested alternative resolution"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        state = orchestrator._load(topic)
        for item in state["hypothesis_ledger"]["hypotheses"]:
            item["proxy_plan"] = []
        target = state["hypothesis_ledger"]["hypotheses"][0]
        target["proxy_trails"] = [{
            "proxy_id": "PT-CONTESTED",
            "proxy": "One ambiguous physical-flow clue",
            "causal_link": "Tests the declared constraint",
            "direction": "AMBIGUOUS",
            "origin_crux": "C1",
            "origin_cruxes": ["C1"],
            "evidence": [],
        }]
        variants = [
            "Inventory timing explains the clue",
            "Seasonality explains the clue",
        ]
        target["field_variants"] = {
            "strongest_alternative_explanation": variants
        }
        target[
            "strongest_alternative_explanation_contested"
        ] = True
        target["strongest_alternative_explanation"] = variants[0]
        hypothesis_engine._refresh(target)
        orchestrator._save(topic, state)
        action = hypothesis_engine.exploration_action(
            orchestrator._load(topic)
        )
        self.assertEqual(
            action["action_code"], "ARTICULATE_STRONGEST_ALTERNATIVE"
        )
        base_design = {
            "design_reviewed": True,
            "design_scope": "ONE_EXPLORATION_LEDGER_DESIGN",
            "design_note": "reviewed conflicting alternatives",
            "design_target_id": action["design_target_id"],
            "expected_state_revision": action["design_state_revision"],
            "hypothesis_id": action["hypothesis_id"],
            "action_code": action["action_code"],
            "strongest_alternative_explanation": variants[1],
            "cheap_discriminating_test": "Seasonally adjust the same series",
        }
        rejected = orchestrator.cmd_record_exploration_design(
            topic, base_design
        )
        self.assertEqual(rejected["status"], "exploration_design_rejected")
        resolved = orchestrator.cmd_record_exploration_design(
            topic,
            {
                **base_design,
                "resolve_contested": True,
                "resolution_rationale": (
                    "This variant is the cheapest observable discriminator"
                ),
            },
        )
        self.assertEqual(resolved["status"], "exploration_design_recorded")
        current = orchestrator._load(topic)
        target = next(
            item
            for item in current["hypothesis_ledger"]["hypotheses"]
            if item["hypothesis_id"] == action["hypothesis_id"]
        )
        self.assertFalse(
            target["strongest_alternative_explanation_contested"]
        )
        self.assertEqual(
            target["field_variants"][
                "strongest_alternative_explanation"
            ],
            variants,
        )

    def test_fake_engine_action_without_host_ledger_is_rejected(self):
        state = {
            "hypothesis_ledger": hypothesis_engine.initialize(
                hypothesis_frame(hypotheses=garden())
            ),
            "exploration_actions": [],
        }
        fake = {
            "action_id": "EA-FAKE",
            "status": "AUTHORIZED_NOT_EXECUTED",
            "proposal": {
                "hypothesis_id": state["hypothesis_ledger"][
                    "hypotheses"
                ][0]["hypothesis_id"],
            },
            "authorization_receipt": {
                "action_id": "EA-FAKE",
                "explicit_user_authorization": True,
                "authorization_scope": "ONE_BOUNDED_EXPLORATION_ACTION",
                "authorization_note": "self asserted",
            },
        }
        with self.assertRaisesRegex(
            ValueError, "authorized_action_not_in_host_ledger"
        ):
            hypothesis_engine.ingest_authorized_action_result(
                state, fake, {}
            )

    def test_formal_state_change_makes_authorization_stale(self):
        topic = "exploration authorization stale formal state"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = orchestrator.cmd_plan_exploration(topic)
        state = orchestrator._load(topic)
        state["candidate_screens"] = [{"screen_id": "CS-CONCURRENT"}]
        orchestrator._save(topic, state)
        stale = orchestrator.cmd_authorize_exploration(
            topic,
            planned["action_id"],
            {
                "action_id": planned["action_id"],
                "explicit_user_authorization": True,
                "authorization_scope": "ONE_BOUNDED_EXPLORATION_ACTION",
                "authorization_note": "exact action",
            },
        )
        self.assertEqual(stale["status"], "exploration_action_stale")
        current = orchestrator._load(topic)
        record = next(
            item
            for item in current["exploration_actions"]
            if item["action_id"] == planned["action_id"]
        )
        self.assertEqual(record["status"], "STALE_NOT_AUTHORIZED")
        replanned = orchestrator.cmd_plan_exploration(topic)
        self.assertEqual(replanned["status"], "exploration_action_planned")
        self.assertNotEqual(replanned["action_id"], planned["action_id"])

    def test_unapproved_plan_blocks_design_until_cancel_then_replans(self):
        topic = "cancelled exploration plan permits redesign"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = orchestrator.cmd_plan_exploration(topic)
        blocked = orchestrator.cmd_record_exploration_design(topic, {})
        self.assertEqual(
            blocked["status"], "exploration_design_blocked_open_action"
        )
        cancelled = orchestrator.cmd_cancel_exploration_action(
            topic, planned["action_id"], "superseded by a better route"
        )
        self.assertEqual(
            cancelled["status"], "exploration_action_cancelled"
        )
        projected = hypothesis_engine.exploration_action(
            orchestrator._load(topic)
        )
        self.assertNotIn("action_id", projected)
        replanned = orchestrator.cmd_plan_exploration(topic)
        self.assertEqual(replanned["status"], "exploration_action_planned")
        self.assertNotEqual(replanned["action_id"], planned["action_id"])

    def test_duplicate_plan_reuses_the_single_open_action(self):
        topic = "duplicate exploration plan is idempotent"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        first = orchestrator.cmd_plan_exploration(topic)
        second = orchestrator.cmd_plan_exploration(topic)
        self.assertEqual(
            second["status"], "exploration_action_already_planned"
        )
        self.assertEqual(second["action_id"], first["action_id"])
        state = orchestrator._load(topic)
        self.assertEqual(
            len([
                item
                for item in state["exploration_actions"]
                if item["status"] == "PLANNED_NOT_AUTHORIZED"
            ]),
            1,
        )

    def test_state_drift_cannot_create_second_open_exploration_action(self):
        topic = "formal drift cannot fork exploration authorization"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        first = self.plan_and_authorize(topic)
        state = orchestrator._load(topic)
        state["candidate_screens"] = [{"screen_id": "CS-DRIFT"}]
        orchestrator._save(topic, state)

        blocked = orchestrator.cmd_plan_exploration(topic)

        self.assertEqual(
            blocked["status"], "exploration_plan_blocked_open_action"
        )
        self.assertEqual(blocked["action_id"], first["action_id"])
        self.assertEqual(blocked["action_status"], "AUTHORIZED_NOT_EXECUTED")
        self.assertEqual(blocked["open_action_count"], 1)
        current = orchestrator._load(topic)
        open_records = [
            item
            for item in current["exploration_actions"]
            if item["status"] in {
                "PLANNED_NOT_AUTHORIZED",
                "AUTHORIZED_NOT_EXECUTED",
            }
        ]
        self.assertEqual(len(open_records), 1)
        self.assertEqual(open_records[0]["action_id"], first["action_id"])

    def test_authorized_frozen_action_remains_visible_after_route_drift(self):
        topic = "authorized action remains control truth after route drift"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = self.plan_and_authorize(topic)
        state = orchestrator._load(topic)
        target = next(
            item
            for item in state["hypothesis_ledger"]["hypotheses"]
            if item["hypothesis_id"]
            == planned["proposal"]["hypothesis_id"]
        )
        target["proxy_plan"] = []
        hypothesis_engine._refresh(target)
        orchestrator._save(topic, state)

        projected = hypothesis_engine.report_view(
            orchestrator._load(topic)
        )["exploration_action"]

        self.assertEqual(projected["action_id"], planned["action_id"])
        self.assertEqual(
            projected["action_code"], "AUTHORIZED_ACTION_IN_FLIGHT"
        )
        self.assertEqual(
            projected["host_action_status"], "AUTHORIZED_NOT_EXECUTED"
        )
        self.assertTrue(projected["proposal_drifted"])
        self.assertFalse(projected["authorization_ready"])
        self.assertEqual(
            projected["budget_boundary"]["max_bounded_queries"], 0
        )
        blocked = orchestrator.cmd_plan_exploration(topic)
        self.assertEqual(
            blocked["status"], "exploration_plan_blocked_open_action"
        )
        self.assertEqual(blocked["action_id"], planned["action_id"])

    def test_authorized_action_blocks_design_and_cannot_be_cancelled(self):
        topic = "authorized exploration freezes design"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = self.plan_and_authorize(topic)
        blocked = orchestrator.cmd_record_exploration_design(topic, {})
        self.assertEqual(
            blocked["status"], "exploration_design_blocked_open_action"
        )
        self.assertEqual(
            blocked["action_status"], "AUTHORIZED_NOT_EXECUTED"
        )
        rejected = orchestrator.cmd_cancel_exploration_action(
            topic, planned["action_id"], "try to revoke with cancel"
        )
        self.assertEqual(
            rejected["status"], "exploration_action_not_cancellable"
        )

    def test_authorized_runtime_failure_without_search_releases_route(self):
        topic = "authorized exploration runtime failure"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = self.plan_and_authorize(topic)
        failed = {
            **self.result(planned, execution_status="EXHAUSTED"),
            "execution_status": "EXECUTION_FAILED_NO_SEARCH",
            "query_executed": None,
            "search_count": 0,
            "failure_reason": "network tool unavailable before dispatch",
            "stop_reason": "no query or document read occurred",
        }
        recorded = orchestrator.cmd_submit_exploration_result(
            topic, planned["action_id"], failed
        )
        self.assertEqual(
            recorded["status"], "exploration_result_recorded"
        )
        state = orchestrator._load(topic)
        record = next(
            item
            for item in state["exploration_actions"]
            if item["action_id"] == planned["action_id"]
        )
        self.assertEqual(record["status"], "FAILED_NO_SEARCH")
        self.assertEqual(
            record["execution_receipt"]["search_count"], 0
        )
        self.assertEqual(
            state["hypothesis_ledger"].get("closed_routes", []), []
        )
        history = state["hypothesis_ledger"][
            "authorized_action_audits"
        ]
        self.assertIsNone(history[-1]["negative_knowledge"])
        replanned = orchestrator.cmd_plan_exploration(topic)
        self.assertEqual(replanned["status"], "exploration_action_planned")
        self.assertNotEqual(replanned["action_id"], planned["action_id"])

    def test_authorized_failure_during_query_is_not_market_exhaustion(self):
        topic = "authorized exploration in query failure"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = self.plan_and_authorize(topic)
        failed = {
            **self.result(planned, execution_status="EXHAUSTED"),
            "execution_status": "EXECUTION_FAILED_DURING_QUERY",
            "failure_reason": "connection dropped before a usable receipt",
            "stop_reason": "query stopped on runtime failure",
        }
        recorded = orchestrator.cmd_submit_exploration_result(
            topic, planned["action_id"], failed
        )
        self.assertEqual(
            recorded["status"], "exploration_result_recorded"
        )
        state = orchestrator._load(topic)
        record = next(
            item
            for item in state["exploration_actions"]
            if item["action_id"] == planned["action_id"]
        )
        self.assertEqual(record["status"], "FAILED_DURING_QUERY")
        self.assertEqual(
            state["hypothesis_ledger"].get("closed_routes", []), []
        )
        history = state["hypothesis_ledger"][
            "authorized_action_audits"
        ]
        self.assertIsNone(history[-1]["negative_knowledge"])

    def test_authorized_ledger_change_closes_stale_result_without_ingest(self):
        topic = "authorized exploration ledger mutation"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = self.plan_and_authorize(topic)
        state = orchestrator._load(topic)
        before_proxy_count = sum(
            len(item.get("proxy_trails", []))
            for item in state["hypothesis_ledger"]["hypotheses"]
        )
        state["hypothesis_ledger"].setdefault("design_audits", []).append({
            "design_id": "DESIGN-CONCURRENT",
            "status": "RECORDED",
        })
        orchestrator._save(topic, state)
        document = self.document(planned["proposal"])
        result = self.result(planned, document=document)
        stale = orchestrator.cmd_submit_exploration_result(
            topic, planned["action_id"], result
        )
        self.assertEqual(stale["status"], "exploration_action_stale")
        self.assertEqual(
            stale["reason"],
            "exploration_ledger_changed_after_authorization",
        )
        self.assertEqual(len(stale["result_sha256"]), 64)
        self.assertFalse(stale["automatic_retry"])
        current = orchestrator._load(topic)
        record = next(
            item
            for item in current["exploration_actions"]
            if item["action_id"] == planned["action_id"]
        )
        self.assertEqual(
            record["status"], "STALE_RESULT_NOT_RECORDED"
        )
        report_view = hypothesis_engine.report_view(current)
        terminal = report_view["terminal_action_history"][-1]
        self.assertEqual(
            terminal["status"], "STALE_RESULT_NOT_RECORDED"
        )
        self.assertEqual(
            terminal["result_sha256"], stale["result_sha256"]
        )
        self.assertFalse(terminal["result_ingested"])
        self.assertFalse(terminal["automatic_retry"])
        memo = research_output.render_resolution_memo(current)
        self.assertIn("STALE_RESULT_NOT_RECORDED", memo)
        self.assertIn(stale["result_sha256"], memo)
        self.assertIn(planned["action_id"], memo)
        self.assertIn(
            "CALLER_ATTESTED_NOT_HOST_VERIFIED", memo
        )
        self.assertIn(
            "证据截止: "
            f"{current['frame_contract']['as_of_date']}",
            memo,
        )
        after_proxy_count = sum(
            len(item.get("proxy_trails", []))
            for item in current["hypothesis_ledger"]["hypotheses"]
        )
        self.assertEqual(after_proxy_count, before_proxy_count)
        replanned = orchestrator.cmd_plan_exploration(topic)
        self.assertEqual(replanned["status"], "exploration_action_planned")
        self.assertNotEqual(replanned["action_id"], planned["action_id"])

    def test_authorized_as_of_change_closes_stale_result_without_ingest(self):
        topic = "authorized exploration as of mutation"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = self.plan_and_authorize(topic)
        state = orchestrator._load(topic)
        state["frame_contract"]["as_of_date"] = "2026-07-14"
        orchestrator._save(topic, state)
        document = self.document(planned["proposal"])
        stale = orchestrator.cmd_submit_exploration_result(
            topic,
            planned["action_id"],
            self.result(planned, document=document),
        )
        self.assertEqual(stale["status"], "exploration_action_stale")
        self.assertEqual(
            stale["reason"], "formal_state_changed_after_authorization"
        )
        current = orchestrator._load(topic)
        record = next(
            item
            for item in current["exploration_actions"]
            if item["action_id"] == planned["action_id"]
        )
        self.assertEqual(
            record["status"], "STALE_RESULT_NOT_RECORDED"
        )
        memo = research_output.render_resolution_memo(current)
        self.assertIn("证据截止: 2026-07-14", memo)
        self.assertIn(
            f"action_as_of={planned['proposal']['as_of_date']}",
            memo,
        )

    def test_state_revision_cas_preserves_concurrent_formal_write(self):
        topic = "state revision cas"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        formal_writer = orchestrator._load(topic)
        stale_writer = orchestrator._load(topic)
        formal_writer["opportunity_seeds"] = [{"seed_id": "OS-CONCURRENT"}]
        orchestrator._save(topic, formal_writer)
        stale_writer["exploration_actions"] = [{"action_id": "EA-STALE"}]
        with self.assertRaisesRegex(ValueError, "state_revision_conflict"):
            orchestrator._save(topic, stale_writer)
        current = orchestrator._load(topic)
        self.assertEqual(
            current["opportunity_seeds"][0]["seed_id"], "OS-CONCURRENT"
        )
        self.assertNotIn(
            "EA-STALE",
            {
                item.get("action_id")
                for item in current.get("exploration_actions", [])
                if isinstance(item, dict)
            },
        )

    def test_submit_conflict_returns_recoverable_receipt_without_retry(self):
        topic = "exploration result cas conflict receipt"
        orchestrator.cmd_init(topic, explicit_hybrid_frame())
        planned = self.plan_and_authorize(topic)
        document = self.document(planned["proposal"])
        result = self.result(planned, document=document)
        with mock.patch.object(
            orchestrator,
            "_save",
            side_effect=ValueError("state_revision_conflict"),
        ):
            conflict = orchestrator.cmd_submit_exploration_result(
                topic, planned["action_id"], result
            )
        self.assertEqual(
            conflict["status"], "exploration_result_not_recorded"
        )
        self.assertEqual(len(conflict["result_sha256"]), 64)
        self.assertFalse(conflict["automatic_retry"])
        persisted = orchestrator._load(topic)
        record = next(
            item
            for item in persisted["exploration_actions"]
            if item["action_id"] == planned["action_id"]
        )
        self.assertEqual(record["status"], "AUTHORIZED_NOT_EXECUTED")


class TrackIsolationTests(unittest.TestCase):
    def test_proxy_ingestion_cannot_change_crux_or_create_candidate(self):
        state = research_state()
        state["hypothesis_ledger"] = hypothesis_engine.initialize(
            hypothesis_frame(hypotheses=garden())
        )
        before_crux = copy.deepcopy(state["cruxes"]["C1"])
        observed = citation(
            domain="proxy-one.org",
            path="qualification",
            claim="Qualification lead time expanded.",
        )
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "proxy_trails": [
                    {
                        "hypothesis_id": "H1",
                        **proxy(evidence=[observed]),
                    }
                ]
            },
            inquisitor={},
        )

        self.assertEqual(audit["state_counts"]["TRACED"], 1)
        self.assertEqual(state["cruxes"]["C1"], before_crux)
        self.assertEqual(state.get("opportunity_seeds", []), [])
        self.assertNotIn("candidate_screen_results", state)

    def test_hypothesis_lineage_never_replaces_seed_admission(self):
        state = research_state()
        state["hypothesis_ledger"] = hypothesis_engine.initialize(
            hypothesis_frame(hypotheses=garden())
        )
        canonical_id = next(
            item["hypothesis_id"]
            for item in state["hypothesis_ledger"]["hypotheses"]
            if item["hypothesis"] == garden()[0]["hypothesis"]
        )
        evidence = citation(
            domain="lineage.org",
            path="candidate",
            claim="Candidate controls a scarce qualified input.",
        )

        unknown = seed(evidence, origin_hypothesis_id="WH-UNKNOWN")
        audit = opportunity_engine.harvest_round(
            state,
            1,
            detective_payload(evidence, unknown),
            {},
        )
        self.assertEqual(audit["rejected_reasons"]["unknown_origin_hypothesis"], 1)
        self.assertEqual(state["opportunity_seeds"], [])

        state["cruxes"]["C2"] = copy.deepcopy(state["cruxes"]["C1"])
        state["cruxes"]["C2"]["id"] = "C2"
        wrong_crux = seed(
            evidence,
            origin_hypothesis_id=canonical_id,
            origin_crux="C2",
        )
        audit = opportunity_engine.harvest_round(
            state,
            2,
            detective_payload(evidence, wrong_crux),
            {},
        )
        self.assertEqual(
            audit["rejected_reasons"]["origin_hypothesis_crux_mismatch"],
            1,
        )
        self.assertEqual(state["opportunity_seeds"], [])

        admitted = seed(evidence, origin_hypothesis_id=canonical_id)
        audit = opportunity_engine.harvest_round(
            state,
            3,
            detective_payload(evidence, admitted),
            {},
        )
        self.assertEqual(audit["accepted_new"], 1)
        self.assertEqual(
            state["opportunity_seeds"][0]["origin_hypothesis_id"],
            canonical_id,
        )
        self.assertEqual(
            state["opportunity_seeds"][0]["maturity"],
            "EVIDENCE_BACKED",
        )

        second_evidence = citation(
            domain="lineage-two.org",
            path="candidate-follow-up",
            claim="Candidate reports revenue tied to the qualified input.",
        )
        audit = opportunity_engine.harvest_round(
            state,
            4,
            detective_payload(second_evidence, seed(second_evidence)),
            {},
        )
        self.assertEqual(audit["merged_existing"], 1)
        self.assertEqual(len(state["opportunity_seeds"]), 1)
        self.assertEqual(
            state["opportunity_seeds"][0]["origin_hypothesis_id"],
            canonical_id,
        )

    def test_merged_multi_crux_hypothesis_accepts_either_preserved_origin(self):
        state = research_state()
        state["cruxes"]["C2"] = copy.deepcopy(state["cruxes"]["C1"])
        state["cruxes"]["C2"]["id"] = "C2"
        state["hypothesis_ledger"] = hypothesis_engine.initialize(
            hypothesis_frame(hypotheses=garden())
        )
        canonical_id = next(
            item["hypothesis_id"]
            for item in state["hypothesis_ledger"]["hypotheses"]
            if item["hypothesis"] == garden()[0]["hypothesis"]
        )
        same_hypothesis = copy.deepcopy(garden()[0])
        same_hypothesis["linked_crux_id"] = "C2"
        same_hypothesis["origin_crux"] = "C2"
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={"hypothesis_sparks": [same_hypothesis]},
            inquisitor={},
            allowed_crux_ids=["C2"],
        )
        self.assertEqual(audit["merged_hypotheses"], 1)
        hypothesis = next(
            item for item in state["hypothesis_ledger"]["hypotheses"]
            if item["hypothesis_id"] == canonical_id
        )
        self.assertEqual(
            set(hypothesis["context"]["origin_cruxes"]), {"C1", "C2"}
        )
        evidence = citation(
            domain="multi-lineage.org",
            path="candidate",
            claim="The C2 route identifies a candidate economic exposure.",
        )
        candidate = seed(
            evidence,
            origin_hypothesis_id=canonical_id,
            origin_crux="C2",
        )
        audit = opportunity_engine.harvest_round(
            state,
            2,
            {
                "crux_evidence": [{
                    "crux_id": "C2",
                    "evidence": [evidence],
                }],
                "opportunity_seeds": [candidate],
            },
            {},
        )
        self.assertEqual(audit["accepted_new"], 1)
        self.assertEqual(
            state["opportunity_seeds"][0]["origin_crux"], "C2"
        )
        self.assertEqual(
            state["opportunity_seeds"][0]["maturity"],
            "EVIDENCE_BACKED",
        )


class ReportAndFuseTests(unittest.TestCase):
    def state_with_exploration(self):
        state = converged_state()
        state["hypothesis_ledger"] = hypothesis_engine.initialize(
            hypothesis_frame(hypotheses=garden())
        )
        return state

    def test_report_keeps_formal_and_exploration_actions_separate(self):
        state = self.state_with_exploration()
        model = report_v2.build_report_view_model(state)
        markdown = report_v2.render(state)
        self.assertEqual(
            model["formal_action"]["code"],
            "STOP_NO_PROMOTABLE_CANDIDATE",
        )
        self.assertEqual(
            model["exploration_action"]["authority"],
            "RESEARCH_ONLY_NO_PROMOTION",
        )
        self.assertTrue(
            model["exploration_action"]["requires_human_authorization"]
        )
        self.assertEqual(model["candidate_counts"]["lead_count"], 0)
        self.assertLess(
            markdown.index("## 正式晋级动作"),
            markdown.index("## 探索动作（无晋级与交易权限）"),
        )
        self.assertLess(
            markdown.index("# Insight Cards"),
            markdown.index("# Candidate Cards"),
        )

    def test_resolution_memo_preserves_hypotheses_without_authorizing_resume(self):
        state = self.state_with_exploration()
        state["last_convergence"] = {
            "decision": "fuse_break",
            "reason": "BLOCKED_MAX_ROUNDS",
        }
        memo = research_output.render_resolution_memo(state)
        self.assertIn("大胆假说与草蛇灰线", memo)
        self.assertIn("Conditional value-transfer mechanism", memo)
        self.assertIn("显式授权", memo)
        self.assertIn("探索排序=", memo)
        self.assertIn("components=", memo)
        self.assertIn("争议变体=", memo)
        self.assertEqual(state.get("opportunity_seeds", []), [])

    def test_blocked_memo_preserves_proxy_direction_lineage(self):
        state = self.state_with_exploration()
        hypothesis_id = state["hypothesis_ledger"]["hypotheses"][0][
            "hypothesis_id"
        ]
        shared = {
            "hypothesis_id": hypothesis_id,
            "origin_crux": "C1",
            "observation": "Shared diagnostic observation",
            "causal_link": "Shared causal diagnostic",
        }
        hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "proxy_trails": [{
                    **shared,
                    "direction": "SUPPORTS",
                    "evidence": [citation(
                        domain="direction-support.org",
                        path="support",
                    )],
                }],
            },
            inquisitor={
                "proxy_trails": [{
                    **shared,
                    "direction": "CONTRADICTS",
                    "evidence": [citation(
                        domain="direction-contradict.org",
                        path="contradict",
                    )],
                }],
            },
            allowed_crux_ids=["C1"],
        )
        state["last_convergence"] = {
            "decision": "fuse_break",
            "reason": "BLOCKED_MAX_ROUNDS",
        }

        memo = research_output.render_resolution_memo(state)

        self.assertIn("bindings=", memo)
        self.assertIn("SUPPORTS@R1/detective/C1", memo)
        self.assertIn("CONTRADICTS@R1/inquisitor/C1", memo)

    def test_proxy_sources_cannot_make_formal_crux_evidence_gate_pass(self):
        state = self.state_with_exploration()
        hypothesis_id = state["hypothesis_ledger"]["hypotheses"][0][
            "hypothesis_id"
        ]
        hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "proxy_trails": [
                    {
                        "hypothesis_id": hypothesis_id,
                        **proxy(
                            observation="First independent proxy",
                            causal_link="First causal diagnostic",
                            evidence=[
                                citation(
                                    domain="proxy-formal-a.org",
                                    path="first",
                                )
                            ],
                        ),
                    },
                    {
                        "hypothesis_id": hypothesis_id,
                        **proxy(
                            observation="Second independent proxy",
                            causal_link="Second causal diagnostic",
                            evidence=[
                                citation(
                                    domain="proxy-formal-b.net",
                                    path="second",
                                )
                            ],
                        ),
                    },
                ]
            },
            inquisitor={},
        )
        audit = report_v2.render(state, view="audit")
        self.assertIn("EVIDENCE_BACKED", audit)
        self.assertIn("状态: **FAIL**", audit)
        self.assertIn("正式 crux 引用: 0 条", audit)
        self.assertIn("不计入正式 crux 证据质量闸", audit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
