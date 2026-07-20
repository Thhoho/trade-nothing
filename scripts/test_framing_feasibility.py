#!/usr/bin/env python3
"""Offline contract tests for Framer source-route and round feasibility."""
import unittest

import crux_engine
import framing_feasibility
import landscape_engine


def evidence_plan(crux_id):
    return [
        {
            "plan_id": f"SP-{crux_id}-1",
            "publisher_class": "ISSUER_OR_FILING",
            "target_claim": f"issuer anchor for {crux_id}",
            "search_query": f"site:sec.gov {crux_id} filing metric",
        },
        {
            "plan_id": f"SP-{crux_id}-2",
            "publisher_class": "REGULATOR_OR_OFFICIAL_DATASET",
            "target_claim": f"independent official anchor for {crux_id}",
            "search_query": f"site:.gov {crux_id} official dataset",
        },
    ]


def frame(crux_count=2, paths_per_crux=None, suggested_max_rounds=5):
    cruxes = [
        {
            "id": f"C{index + 1}",
            "logic_role": "OPPORTUNITY_PATH" if index == 0 else "PRICING",
            "evidence_plan": evidence_plan(f"C{index + 1}"),
        }
        for index in range(crux_count)
    ]
    paths_per_crux = paths_per_crux or ["C1"] * 5
    paths = [
        {"path_id": f"L{index + 1}", "linked_crux_id": linked}
        for index, linked in enumerate(paths_per_crux)
    ]
    return {
        "question_type": "UNIVERSE_SEARCH",
        "candidate_cruxes": cruxes,
        "landscape_map": {"paths": paths},
        "no_edge_precheck": {"is_researchable": True},
        "suggested_max_rounds": suggested_max_rounds,
    }


class FramingFeasibilityTests(unittest.TestCase):
    def test_each_researchable_crux_requires_two_distinct_publisher_routes(self):
        raw = frame()
        raw["candidate_cruxes"][0].pop("evidence_plan")
        raw["candidate_cruxes"][1]["evidence_plan"][1]["publisher_class"] = (
            "ISSUER_OR_FILING"
        )
        issues = framing_feasibility.validate_evidence_plans(raw)
        self.assertIn("crux_C1_evidence_plan_required", issues)
        self.assertIn(
            "crux_C2_evidence_plan_requires_two_publisher_classes", issues
        )

    def test_duplicate_queries_and_unknown_classes_are_rejected(self):
        raw = frame()
        plan = raw["candidate_cruxes"][0]["evidence_plan"]
        plan[1]["search_query"] = plan[0]["search_query"]
        plan[1]["publisher_class"] = "BLOG"
        issues = framing_feasibility.validate_evidence_plans(raw)
        self.assertIn("crux_C1_evidence_plan_search_queries_must_be_distinct", issues)
        self.assertIn("crux_C1_evidence_plan_2_invalid_publisher_class", issues)

    def test_concentrated_landscape_and_five_cruxes_require_six_rounds(self):
        raw = frame(crux_count=5, suggested_max_rounds=5)
        self.assertEqual(framing_feasibility.minimum_rounds(raw), 6)
        self.assertEqual(
            framing_feasibility.validate_round_budget(raw),
            ["framing_feasibility_requires_at_least_6_rounds"],
        )

    def test_distributed_paths_fit_existing_five_round_window(self):
        raw = frame(
            crux_count=5,
            paths_per_crux=["C1", "C2", "C3", "C4", "C5"],
            suggested_max_rounds=5,
        )
        self.assertEqual(framing_feasibility.minimum_rounds(raw), 5)
        self.assertEqual(framing_feasibility.validate_round_budget(raw), [])

    def test_no_edge_frame_does_not_require_research_budget(self):
        raw = frame()
        raw["no_edge_precheck"]["is_researchable"] = False
        raw["candidate_cruxes"][0].pop("evidence_plan")
        self.assertEqual(framing_feasibility.validate_frame(raw), [])

    def test_runtime_constants_match_scheduler_and_convergence(self):
        self.assertEqual(framing_feasibility.MAX_CRUXES_PER_ROUND, 2)
        self.assertEqual(
            framing_feasibility.MIN_EVIDENCE_ROUTES,
            crux_engine.MIN_VALID_CITATIONS,
        )
        self.assertEqual(landscape_engine.MAX_PATHS_PER_ROLE_ROUND, 2)


if __name__ == "__main__":
    unittest.main()

