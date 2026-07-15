#!/usr/bin/env python3
"""Offline regression tests for the two-sided CandidateScreen gate."""
import copy
import hashlib
import os
import re
import tempfile
import unittest

import candidate_screen_engine as screen_engine
import codex_candidate_screen_receipt as codex_receipt
import crux_engine
import deepthink_orchestrator_v2 as orchestrator
import report_v2


AS_OF = "2026-07-10"


def citation(path, source=None, date="2026-07-01", tier="primary"):
    publisher = source or f"Source {path}"
    publisher_slug = re.sub(r"[^a-z0-9]+", "-", publisher.lower()).strip("-")
    return {
        "claim": f"screen evidence {path}",
        "number": "1",
        "source": publisher,
        "url": f"https://fixture-{publisher_slug}.org/screen/{path}",
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
        "pricing_anchor": {
            "as_of_date": AS_OF,
            "anchor_type": "EMBEDDED_EXPECTATION",
            "metric": "consensus EBITDA",
            "current_value": "excludes disclosed contract",
            "comparison_value": "includes contract contribution",
            "source": "Source seed-a",
            "source_url": "https://fixture-source-seed-a.org/screen/seed-a",
            "source_claim": "screen evidence seed-a",
        },
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
    st["runtime_contract"] = {"isolation_status": "verified"}
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


def receipt_from_dispatch(dispatch, analyst, skeptic):
    receipt = {
        "schema": "candidate-screen-isolation.v1",
        "runner_kind": "agy_separate_process_v1",
        "host_enforced": True,
        "dispatch_id": dispatch["dispatch_id"],
        "as_of_date": dispatch["as_of_date"],
        "candidate_seed_ids": dispatch["candidate_seed_ids"],
        "roles": {
            "analyst": {
                "invocation_id": "test-analyst",
                "process_id": 1001,
                "exit_code": 0,
                "timed_out": False,
                "prompt_sha256": hashlib.sha256(
                    dispatch["analyst_prompt"].encode("utf-8")
                ).hexdigest(),
                "payload_sha256": screen_engine.payload_sha256(analyst),
            },
            "skeptic": {
                "invocation_id": "test-skeptic",
                "process_id": 1002,
                "exit_code": 0,
                "timed_out": False,
                "prompt_sha256": hashlib.sha256(
                    dispatch["skeptic_prompt"].encode("utf-8")
                ).hexdigest(),
                "payload_sha256": screen_engine.payload_sha256(skeptic),
            },
        },
    }
    receipt["receipt_id"] = screen_engine.isolation_receipt_id(receipt)
    return receipt


def codex_receipt_from_dispatch(dispatch, analyst, skeptic):
    receipt = {
        "schema": "candidate-screen-isolation.v1",
        "runner_kind": "codex_collaboration_v1",
        "host_enforced": True,
        "dispatch_id": dispatch["dispatch_id"],
        "as_of_date": dispatch["as_of_date"],
        "candidate_seed_ids": dispatch["candidate_seed_ids"],
        "roles": {},
    }
    for role, value in (("analyst", analyst), ("skeptic", skeptic)):
        receipt["roles"][role] = {
            "invocation_id": f"/root/test-{role}",
            "agent_id": f"/root/test-{role}",
            "context_isolation": "independent_agent_context",
            "status": "completed",
            "timed_out": False,
            "prompt_sha256": hashlib.sha256(
                dispatch[f"{role}_prompt"].encode("utf-8")
            ).hexdigest(),
            "payload_sha256": screen_engine.payload_sha256(value),
        }
    receipt["receipt_id"] = screen_engine.isolation_receipt_id(receipt)
    return receipt


def install_test_dispatch(st, analyst, skeptic):
    prompts = orchestrator.candidate_screen_prompts(
        st, screen_engine.screenable_seeds(st), AS_OF
    )
    dispatch = {
        "dispatch_id": "CSD-TEST",
        "as_of_date": AS_OF,
        **prompts,
    }
    st["candidate_screen_dispatches"] = [{
        "dispatch_id": dispatch["dispatch_id"],
        "as_of_date": AS_OF,
        "candidate_seed_ids": dispatch["candidate_seed_ids"],
        "prompt_sha256": {
            "analyst": hashlib.sha256(dispatch["analyst_prompt"].encode("utf-8")).hexdigest(),
            "skeptic": hashlib.sha256(dispatch["skeptic_prompt"].encode("utf-8")).hexdigest(),
        },
    }]
    return receipt_from_dispatch(dispatch, analyst, skeptic)


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

    def test_default_batch_is_deterministic_top_three_not_five(self):
        st = state_with_seed()
        base = st["opportunity_seeds"][0]
        seeds = []
        specs = [
            ("OS-A", "A", "DIRECT_WINNER", 4),
            ("OS-B", "B", "BOTTLENECK_OWNER", 3),
            ("OS-C", "C", "DIRECT_WINNER", 2),
            ("OS-D", "D", "SECOND_ORDER", 2),
        ]
        for seed_id, ticker, relation, source_count in specs:
            seed = copy.deepcopy(base)
            evidence = [citation(f"{ticker.lower()}-{index}") for index in range(source_count)]
            seed.update({
                "seed_id": seed_id,
                "candidate": f"Candidate {ticker}",
                "ticker": ticker,
                "relation_type": relation,
                "evidence": evidence,
            })
            seed["pricing_anchor"].update({
                "source": evidence[0]["source"],
                "source_url": evidence[0]["url"],
                "source_claim": evidence[0]["claim"],
            })
            seeds.append(seed)
        st["opportunity_seeds"] = list(reversed(seeds))
        selected = screen_engine.screenable_seeds(st)
        self.assertEqual(screen_engine.MAX_BATCH, 3)
        self.assertEqual([item["seed_id"] for item in selected], ["OS-A", "OS-B", "OS-C"])
        audit = screen_engine.selection_audit(selected)
        self.assertEqual([item["rank"] for item in audit], [1, 2, 3])
        self.assertIn("not return", audit[0]["selection_basis"])

    def test_two_sided_fresh_independent_evidence_creates_thesis_candidate(self):
        st = state_with_seed()
        analyst = payload("Analyst")
        skeptic = payload("Skeptic")
        receipt = install_test_dispatch(st, analyst, skeptic)
        audit = screen_engine.evaluate_batch(
            st, analyst, skeptic, AS_OF, isolation_status="verified",
            isolation_receipt=receipt,
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

    def test_codex_collaboration_receipt_requires_distinct_host_agents(self):
        st = state_with_seed()
        analyst = payload("Analyst")
        skeptic = payload("Skeptic")
        prompts = orchestrator.candidate_screen_prompts(
            st, screen_engine.screenable_seeds(st), AS_OF
        )
        dispatch = {
            "dispatch_id": "CSD-CODEX",
            "as_of_date": AS_OF,
            **prompts,
        }
        st["candidate_screen_dispatches"] = [{
            "dispatch_id": dispatch["dispatch_id"],
            "as_of_date": AS_OF,
            "candidate_seed_ids": dispatch["candidate_seed_ids"],
            "prompt_sha256": {
                role: hashlib.sha256(dispatch[f"{role}_prompt"].encode("utf-8")).hexdigest()
                for role in ("analyst", "skeptic")
            },
        }]
        receipt = codex_receipt_from_dispatch(dispatch, analyst, skeptic)
        audit = screen_engine.evaluate_batch(
            st, analyst, skeptic, AS_OF, isolation_status="verified",
            isolation_receipt=receipt,
        )
        self.assertEqual(audit["thesis_candidate_count"], 1)
        self.assertEqual(audit["isolation_receipt_status"], "verified")

        receipt["roles"]["skeptic"]["agent_id"] = receipt["roles"]["analyst"]["agent_id"]
        receipt["receipt_id"] = screen_engine.isolation_receipt_id(receipt)
        validation = screen_engine.validate_isolation_receipt(
            st, receipt, analyst, skeptic, AS_OF
        )
        self.assertIn("isolation_receipt_agents_not_distinct", validation["blockers"])

    def test_codex_receipt_builder_binds_dispatch_payloads_and_agent_ids(self):
        st = state_with_seed()
        analyst = payload("Analyst")
        skeptic = payload("Skeptic")
        prompts = orchestrator.candidate_screen_prompts(
            st, screen_engine.screenable_seeds(st), AS_OF
        )
        dispatch = {"dispatch_id": "CSD-BUILDER", "as_of_date": AS_OF, **prompts}
        receipt = codex_receipt.build_receipt(
            dispatch, analyst, skeptic, "/root/analyst", "/root/skeptic"
        )
        self.assertEqual(receipt["runner_kind"], "codex_collaboration_v1")
        self.assertEqual(receipt["roles"]["analyst"]["agent_id"], "/root/analyst")
        self.assertEqual(
            receipt["roles"]["skeptic"]["payload_sha256"],
            screen_engine.payload_sha256(skeptic),
        )
        with self.assertRaises(ValueError):
            codex_receipt.build_receipt(
                dispatch, analyst, skeptic, "/root/same", "/root/same"
            )

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

    def test_claimed_verified_isolation_is_capped_by_runtime_attestation(self):
        st = state_with_seed()
        st["runtime_contract"]["isolation_status"] = "unverified"
        audit = screen_engine.evaluate_batch(
            st, payload("Analyst"), payload("Skeptic"), AS_OF,
            isolation_status="verified",
        )
        screen = st["candidate_screens"][0]
        self.assertEqual(screen["status"], "WATCHLIST")
        self.assertEqual(screen["claimed_isolation_status"], "verified")
        self.assertEqual(screen["runtime_isolation_status"], "unverified")
        self.assertEqual(screen["isolation_status"], "unverified")
        self.assertIn("screen_isolation_claim_exceeds_runtime", screen["gaps"])
        self.assertEqual(audit["effective_isolation_status"], "unverified")

    def test_unverified_runtime_is_worse_than_degraded_screen_claim(self):
        st = state_with_seed()
        st["runtime_contract"]["isolation_status"] = "unverified"
        audit = screen_engine.evaluate_batch(
            st, payload("Analyst"), payload("Skeptic"), AS_OF,
            isolation_status="degraded",
        )
        self.assertEqual(audit["effective_isolation_status"], "unverified")
        self.assertEqual(st["candidate_screens"][0]["isolation_status"], "unverified")

    def test_reserved_example_urls_cannot_satisfy_candidate_screen(self):
        st = state_with_seed()
        analyst = payload("Analyst")
        skeptic = payload("Skeptic")
        for packet in (analyst, skeptic):
            for question in packet["candidate_screens"][0]["questions"]:
                question["evidence"][0]["url"] = (
                    f"https://www.example.com/{question['dimension'].lower()}"
                )
        screen_engine.evaluate_batch(
            st, analyst, skeptic, AS_OF, isolation_status="verified"
        )
        screen = st["candidate_screens"][0]
        self.assertEqual(screen["status"], "WATCHLIST")
        self.assertEqual(screen["source_gate"]["n_unique_urls"], 0)
        self.assertIn("total_unique_urls", screen["gaps"])

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
        analyst = payload("Analyst")
        skeptic = payload("Skeptic")
        receipt = install_test_dispatch(st, analyst, skeptic)
        screen_engine.evaluate_batch(
            st, analyst, skeptic, AS_OF, isolation_status="verified",
            isolation_receipt=receipt,
        )
        screen_engine.evaluate_batch(
            st, analyst, skeptic, AS_OF, isolation_status="verified",
            isolation_receipt=receipt,
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
        self.assertIn("pricing_anchor", dispatch["analyst_prompt"])
        self.assertIn("cheap-first", dispatch["analyst_prompt"])
        self.assertIn("其余维度填 UNKNOWN", dispatch["skeptic_prompt"])
        self.assertNotIn("selection_rank", dispatch["analyst_prompt"])
        self.assertEqual(dispatch["max_batch"], 3)
        self.assertEqual(dispatch["selection_audit"][0]["seed_id"], "OS-TEST")
        analyst = payload("Analyst")
        skeptic = payload("Skeptic")
        receipt = receipt_from_dispatch(dispatch, analyst, skeptic)
        result = orchestrator.cmd_submit_screen(
            topic, analyst, skeptic, AS_OF, isolation_status="verified",
            isolation_receipt=receipt,
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

    def test_opportunity_report_physically_defers_to_default_screen_batch(self):
        topic = "candidate screen default continuation"
        st = state_with_seed()
        st["question_type"] = "UNIVERSE_SEARCH"
        orchestrator._save(topic, st)
        result = orchestrator.cmd_report(topic)
        self.assertEqual(result["status"], "dispatch_candidate_screeners")
        self.assertFalse(result["formal_report_allowed"])
        self.assertTrue(result["formal_report_deferred"])
        self.assertEqual(result["report_deferred_reason"], "default_candidate_screen_pending")
        stored = orchestrator._load(topic)
        self.assertEqual(stored["candidate_screen_dispatches"][0]["max_batch"], 3)

    def test_final_research_submit_immediately_dispatches_default_screeners(self):
        topic = "candidate screen direct continuation"
        st = state_with_seed()
        st["question_type"] = "UNIVERSE_SEARCH"
        st["cruxes"]["C1"]["logic_role"] = "OPPORTUNITY_PATH"
        st["opportunity_seeds"][0]["landscape_path_id"] = "L1"
        st["cruxes"]["C2"] = copy.deepcopy(st["cruxes"]["C1"])
        st["cruxes"]["C2"].update({
            "label": "pricing crux",
            "logic_role": "PRICING",
            "citations": [citation("pricing-origin-a"), citation("pricing-origin-b")],
        })
        st["landscape_map"] = {"paths": [{
            "path_id": "L1",
            "linked_crux_id": "C1",
            "state": "SUPPORTED",
            "probes": {
                "detective": {"round": 1, "state": "SUPPORTED", "evidence": []},
                "inquisitor": {"round": 1, "state": "SUPPORTED", "evidence": []},
            },
        }]}
        verdict = crux_engine.research_verdict(st)
        st["rounds"] = [
            {"round": 1, "opportunity_harvest": {
                "accepted_new": 1, "merged_existing": 0,
            }},
            {"round": 2, "opportunity_harvest": {
                "accepted_new": 0, "merged_existing": 0,
            }},
        ]
        st["decision_trace"] = [{
            "round": 2,
            "weakest": "C1",
            "p_weakest": st["cruxes"]["C1"]["p_history"][-1],
            "p_mean": st["cruxes"]["C1"]["p_history"][-1],
            "decision": crux_engine._legacy_decision(verdict),
            "research_verdict": verdict,
        }]
        st["last_convergence"] = {"decision": "continue"}
        orchestrator._save(topic, st)
        result = orchestrator.cmd_submit(
            topic,
            {"crux_evidence": [], "opportunity_seeds": []},
            {"crux_attacks": [], "opportunity_seeds": []},
            {"crux_signals": {}, "new_cruxes": []},
        )
        self.assertEqual(result["status"], "dispatch_candidate_screeners")
        self.assertTrue(result["research_converged"])
        self.assertTrue(result["formal_report_deferred"])
        self.assertEqual(result["candidate_seed_ids"], ["OS-TEST"])


class CandidateScreenReportTests(unittest.TestCase):
    def test_watchlist_card_prioritizes_gap_and_debiases_short_label(self):
        st = state_with_seed()
        st["opportunity_seeds"][0]["relation_type"] = "SHORT_CANDIDATE"
        unresolved = {
            dimension: "UNKNOWN"
            for dimension in screen_engine.DIMENSIONS
            if dimension != "ECONOMIC_EXPOSURE"
        }
        analyst = payload("Analyst", overrides=unresolved)
        skeptic = payload("Skeptic", overrides=unresolved)
        receipt = install_test_dispatch(st, analyst, skeptic)
        screen_engine.evaluate_batch(
            st, analyst, skeptic, AS_OF, isolation_status="verified",
            isolation_receipt=receipt,
        )
        md = report_v2.render(st, view="cards")
        self.assertIn("反向风险暴露", md)
        self.assertNotIn("SHORT_CANDIDATE", md)
        self.assertIn("首要筛选缺口**: EXPECTATION_GAP", md)
        self.assertIn("Analyst UNKNOWN ｜ Skeptic UNKNOWN", md)
        self.assertIn("派生未研究项", md)
        self.assertIn("优先补齐 EXPECTATION_GAP", md)

    def test_report_renders_screen_matrix_without_auto_promotion(self):
        st = state_with_seed()
        analyst = payload("Analyst")
        skeptic = payload("Skeptic")
        receipt = install_test_dispatch(st, analyst, skeptic)
        screen_engine.evaluate_batch(
            st, analyst, skeptic, AS_OF, isolation_status="verified",
            isolation_receipt=receipt,
        )
        md = report_v2.render(st)
        self.assertIn("THESIS_CANDIDATE", md)
        self.assertIn("CandidateScreen", md)
        self.assertIn("DRAFT_REQUIRES_SOURCE_VERIFICATION", md)
        self.assertIn("P2 PENDING", md)
        self.assertIn(
            "https://fixture-analyst-economic-exposure.org/screen/analyst-economic_exposure",
            md,
        )
        self.assertLess(md.index("# Candidate Cards"), md.index("# Audit Appendix"))
        model = report_v2.build_report_view_model(st)
        self.assertEqual(model["candidate_cards"][0]["candidate_state"], "THESIS_CANDIDATE")
        self.assertEqual(
            model["candidate_cards"][0]["next_action_code"],
            "RUN_CLAIM_VERIFICATION",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
