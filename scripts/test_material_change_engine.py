#!/usr/bin/env python3
"""Offline tests for value-first material recall and delivery blocking."""
from __future__ import annotations

import unittest

import material_change_engine as engine


def _frame():
    return {
        "as_of_date": "2026-08-12",
        "unit_of_analysis": "Example Co",
        "research_workplan": {
            "primary_entities": [{
                "entity_id": "E1",
                "name": "Example Co",
                "entity_type": "LISTED_COMPANY",
                "ticker": "300001",
                "exchange": "XSHE",
            }],
        },
    }


def _state():
    return {
        "topic": "example",
        "frame_contract": {"as_of_date": "2026-08-12"},
        "material_change_register": engine.initialize(_frame(), "example"),
        "research_agenda": {
            "questions": [{
                "question_id": "RQ1",
                "question": "Did economics change?",
                "decision_impact": "HIGH",
                "blocks_current_recommendation": True,
                "answer_status": "OPEN",
                "answer_variants": [],
            }],
            "evidence_aliases": {},
            "evidence_items": [{
                "evidence_id": "EV1",
                "question_ids": ["RQ1"],
                "direction_ids": [],
                "claim": "A new material contract was signed.",
                "source": "issuer",
                "url": "https://www.cninfo.com.cn/new/disclosure/detail?announcementId=1",
                "date": "2026-08-01",
                "source_tier": "primary",
                "round": 1,
                "role": "detective",
                "roles": ["detective"],
            }],
        },
        "rounds": [],
    }


def _coverage():
    return [
        {
            "entity_id": "E1",
            "route_kind": route,
            "outcome": "FOUND" if route == "COMMERCIAL_MILESTONES" else "NO_RESULT",
            "query": f"Example Co {route}",
            "checked_urls": [
                f"https://www.cninfo.com.cn/new/disclosure/detail?route={route.lower()}"
            ],
            "note": "checked",
        }
        for route in engine.COMPANY_ROUTES
    ]


class MaterialChangeEngineTests(unittest.TestCase):
    def test_missing_fact_surface_blocks_decision_ready_delivery(self):
        gate = engine.delivery_gate(_state())
        self.assertEqual(gate["status"], "MATERIAL_FACT_GAP")
        self.assertEqual(gate["blocker_count"], 4)

    def test_primary_material_change_and_complete_coverage_clear_gate(self):
        state = _state()
        payload = {
            "material_change_coverage": _coverage(),
            "material_change_items": [{
                "event_id": "MC1",
                "entity_id": "E1",
                "event_type": "CONTRACT_CUSTOMER",
                "published_date": "2026-08-01",
                "effective_date": "2026-08-01",
                "claim": "A new material contract was signed.",
                "materiality_rationale": "It changes the revenue-realization answer.",
                "decision_impact": "HIGH",
                "affected_question_ids": ["RQ1"],
                "affected_conclusion_keys": ["revenue-realization"],
                "evidence_ids": ["EV1"],
                "status": "VERIFIED",
                "supersedes_event_ids": [],
                "resolves_lead_ids": [],
            }],
        }
        audit = engine.harvest_round(state, 1, detective=payload)
        self.assertEqual(audit["accepted_item_ids"], ["MC1"])
        self.assertEqual(engine.delivery_gate(state)["status"], "CURRENT_TRUTH_BOUNDED")
        self.assertEqual(engine.report_view(state)["current_items"][0]["status"], "VERIFIED")

    def test_known_high_impact_lead_cannot_hide_in_limitations(self):
        state = _state()
        engine.harvest_round(state, 1, detective={
            "material_change_coverage": _coverage(),
            "material_change_leads": [{
                "lead_id": "ML1",
                "entity_id": "E1",
                "claim": "A later contract may supersede the old conclusion.",
                "why_it_may_matter": "It can reverse the revenue conclusion.",
                "decision_impact": "HIGH",
                "source_url": "https://www.cninfo.com.cn/new/disclosure/detail?announcementId=2",
                "observed_date": "2026-08-10",
            }],
        })
        gate = engine.delivery_gate(state)
        self.assertEqual(gate["status"], "MATERIAL_FACT_GAP")
        self.assertIn("KNOWN_MATERIAL_LEAD_OPEN", {
            item["code"] for item in gate["blockers"]
        })

    def test_adaptive_challenge_targets_only_load_bearing_lead_answers(self):
        state = _state()
        question = state["research_agenda"]["questions"][0]
        question.update({
            "answer_status": "ANSWERED",
            "current_answer": "Economics improved.",
            "evidence_boundary": "FACT",
            "answer_variants": [{
                "round": 1, "role": "detective", "answer": "Economics improved."
            }],
        })
        targets = engine.challenge_targets(state)
        self.assertEqual([item["question_id"] for item in targets], ["RQ1"])
        question["answer_variants"].append({
            "round": 2, "role": "inquisitor", "answer": "Challenge checked."
        })
        self.assertEqual(engine.challenge_targets(state), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
