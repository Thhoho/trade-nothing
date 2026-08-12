#!/usr/bin/env python3
"""Regression tests for the product-value comparison gate."""
import unittest

import product_value_benchmark as benchmark


def _key():
    return {
        "schema_version": benchmark.KEY_SCHEMA,
        "case_id": "company-current-truth",
        "research_question_sha256": "a" * 64,
        "as_of_date": "2026-08-12",
        "material_facts": [
            {
                "fact_id": "F-CRITICAL", "weight": 5,
                "claim": "A recent event superseded the old operating fact.",
                "date": "2026-08-01",
                "source_url": "https://issuer.example/critical.pdf",
                "decision_effect": "Changes the economic-exposure conclusion.",
            },
            {
                "fact_id": "F-OTHER", "weight": 1,
                "claim": "A second current fact changes timing.",
                "date": "2026-08-02",
                "source_url": "https://issuer.example/other.pdf",
                "decision_effect": "Changes the catalyst window.",
            },
        ],
    }


def _assessment(variant, found, usefulness, tokens):
    return {
        "schema_version": benchmark.ASSESSMENT_SCHEMA,
        "case_id": "company-current-truth",
        "variant": variant,
        "blind": True,
        "artifact_sha256": ("b" if variant == "single_agent" else "c") * 64,
        "assessor_id": "blind-reviewer-1",
        "comparison_contract": {
            "model": "same-model",
            "research_question_sha256": "a" * 64,
            "as_of_date": "2026-08-12",
            "tool_profile": "web-primary-sources",
            "max_tokens": 100000,
            "max_searches": 20,
            "max_wall_seconds": 3600,
        },
        "usage": {"total_tokens": tokens, "search_count": 10, "wall_seconds": 900},
        "metrics": {
            "material_fact_ids_found": found,
            "decision_usefulness_score": usefulness,
            "false_source_count": 0,
            "hypothesis_laundering_count": 0,
            "material_omission_count": len({"F-CRITICAL", "F-OTHER"} - set(found)),
        },
    }


def _score(key, baseline, candidate):
    return benchmark.score(
        key, baseline, candidate,
        observed_artifact_hashes={
            "baseline": baseline["artifact_sha256"],
            "candidate": candidate["artifact_sha256"],
        },
    )


class ProductValueBenchmarkTests(unittest.TestCase):
    def test_reproduces_the_product_failure_even_when_report_is_formal(self):
        baseline = _assessment("single_agent", ["F-CRITICAL"], 70, 10000)
        candidate = _assessment("v0_15_formal", ["F-OTHER"], 65, 30000)
        result = _score(_key(), baseline, candidate)
        self.assertEqual(result["status"], "BLOCKED_PRODUCT_VALUE")
        self.assertIn("MATERIAL_FACT_RECALL_BELOW_BASELINE", result["blockers"])
        self.assertIn("COST_RATIO_EXCEEDS_UNPROVEN_METHOD_CAP", result["blockers"])
        self.assertIn("KNOWN_MATERIAL_OMISSION_PRESENT", result["blockers"])

    def test_value_first_candidate_must_improve_usefulness_with_bounded_cost(self):
        baseline = _assessment("single_agent", ["F-CRITICAL"], 70, 10000)
        candidate = _assessment(
            "v0_16_value_first", ["F-CRITICAL", "F-OTHER"], 82, 14000
        )
        result = _score(_key(), baseline, candidate)
        self.assertEqual(result["status"], "PRODUCT_VALUE_READY")

    def test_comparison_contract_drift_is_not_an_experiment(self):
        baseline = _assessment("single_agent", ["F-CRITICAL"], 70, 10000)
        candidate = _assessment("v0_16_value_first", ["F-CRITICAL"], 80, 12000)
        candidate["comparison_contract"]["model"] = "different-model"
        result = _score(_key(), baseline, candidate)
        self.assertEqual(result["status"], "INVALID_COMPARISON")

    def test_assessor_cannot_declare_a_known_omission_away(self):
        baseline = _assessment("single_agent", ["F-CRITICAL"], 70, 10000)
        candidate = _assessment("v0_16_value_first", ["F-CRITICAL"], 80, 12000)
        candidate["metrics"]["material_omission_count"] = 0
        result = _score(_key(), baseline, candidate)
        self.assertEqual(result["status"], "INVALID_COMPARISON")
        self.assertIn(
            "candidate:material_omission_count_mismatch", result["blockers"]
        )

    def test_assessment_is_bound_to_distinct_artifacts_and_budget(self):
        baseline = _assessment("single_agent", ["F-CRITICAL"], 70, 10000)
        candidate = _assessment(
            "v0_16_value_first", ["F-CRITICAL", "F-OTHER"], 82, 14000
        )
        candidate["artifact_sha256"] = baseline["artifact_sha256"]
        candidate["usage"]["search_count"] = 21
        result = _score(_key(), baseline, candidate)
        self.assertEqual(result["status"], "INVALID_COMPARISON")
        self.assertIn("comparison_artifacts_must_differ", result["blockers"])
        self.assertIn("candidate:usage_exceeds_max_searches", result["blockers"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
