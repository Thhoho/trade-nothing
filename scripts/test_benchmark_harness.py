import json
import hashlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark_harness as harness


def suite():
    return {
        "schema_version": harness.SUITE_SCHEMA,
        "suite_id": "v013-smoke",
        "variants": ["single_agent", "v0_12", "v0_13"],
        "cases": [{
            "case_id": "case_universe_01",
            "question_type": "UNIVERSE_SEARCH",
            "as_of": "2026-01-15",
            "prompt": "Find investable value-transfer paths without using future information.",
            "frozen_evidence": ["SNAP-A", "SNAP-B"],
            "budget": {
                "max_tokens": 10000,
                "max_searches": 8,
                "max_wall_seconds": 600,
            },
        }],
    }


def result(variant, tokens=5000, artifact_path="artifact.md", artifact_sha256="a" * 64):
    return {
        "schema_version": harness.RESULT_SCHEMA,
        "case_id": "case_universe_01",
        "variant": variant,
        "execution_id": f"EXEC-{variant}",
        "engine_version": variant,
        "completion_status": "COMPLETE",
        "artifact_path": artifact_path,
        "artifact_sha256": artifact_sha256,
        "usage": {"tokens_total": tokens, "search_count": 4, "wall_seconds": 120},
        "recovery_count": 0,
    }


def assessment(variant, artifact_sha256="a" * 64):
    return {
        "schema_version": harness.ASSESSMENT_SCHEMA,
        "case_id": "case_universe_01",
        "variant": variant,
        "artifact_sha256": artifact_sha256,
        "assessor_id": "blind-reviewer-1",
        "blind": True,
        "metrics": {
            "decisive_claim_total": 4,
            "decisive_claim_correct": 3,
            "false_source_count": 0,
            "major_path_total": 3,
            "major_path_found": 2,
            "candidate_count": 2,
            "effective_seed_count": 1,
            "false_opportunity_count": 1,
            "pricing_anchor_total": 2,
            "pricing_anchor_valid": 1,
            "maturity_misread_count": 0,
            "comprehension_question_total": 3,
            "comprehension_question_correct": 3,
            "manual_edit_count": 1,
        },
    }


class BenchmarkHarnessTests(unittest.TestCase):
    def test_suite_rejects_answer_leakage(self):
        data = suite()
        data["cases"][0]["gold_answer"] = "future winner"
        with self.assertRaisesRegex(ValueError, "leakage"):
            harness.validate_suite(data)

    def test_result_cannot_score_itself(self):
        data = result("v0_13")
        data["assessment"] = {"great": True}
        case = harness.validate_suite(suite())["cases"][0]
        with self.assertRaisesRegex(ValueError, "own assessment"):
            harness.validate_result(data, case, suite()["variants"])

    def test_blind_assessment_must_bind_exact_artifact(self):
        case = harness.validate_suite(suite())["cases"][0]
        run = harness.validate_result(result("v0_13"), case, suite()["variants"])
        review = assessment("v0_13")
        review["artifact_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "exact result artifact"):
            harness.validate_assessment(review, run)

    def test_scores_complete_equal_budget_comparison(self):
        with tempfile.TemporaryDirectory() as root:
            for variant in suite()["variants"]:
                stem = f"case_universe_01__{variant}"
                artifact_name = stem + ".artifact.md"
                artifact = f"frozen output for {variant}".encode("utf-8")
                artifact_hash = hashlib.sha256(artifact).hexdigest()
                with open(os.path.join(root, artifact_name), "wb") as handle:
                    handle.write(artifact)
                with open(os.path.join(root, stem + ".result.json"), "w", encoding="utf-8") as handle:
                    json.dump(result(
                        variant, artifact_path=artifact_name, artifact_sha256=artifact_hash
                    ), handle)
                with open(os.path.join(root, stem + ".assessment.json"), "w", encoding="utf-8") as handle:
                    json.dump(assessment(variant, artifact_sha256=artifact_hash), handle)
            summary = harness.score_suite(suite(), root)
        self.assertTrue(summary["comparison_ready"])
        self.assertEqual(summary["observed_case_variant_pairs"], 3)
        self.assertEqual(summary["aggregates"]["v0_13"]["claim_precision"], 0.75)
        self.assertEqual(summary["aggregates"]["v0_13"]["major_path_coverage"], 0.666667)
        self.assertEqual(summary["aggregates"]["v0_13"]["tokens_per_effective_seed"], 5000)
        md = harness.render_markdown(summary)
        self.assertIn("Benchmark Summary", md)
        self.assertIn("v0_13", md)

    def test_over_budget_run_is_observed_but_not_comparable(self):
        with tempfile.TemporaryDirectory() as root:
            for variant in suite()["variants"]:
                stem = f"case_universe_01__{variant}"
                tokens = 10001 if variant == "v0_13" else 5000
                artifact_name = stem + ".artifact.md"
                artifact = f"frozen output for {variant}".encode("utf-8")
                artifact_hash = hashlib.sha256(artifact).hexdigest()
                with open(os.path.join(root, artifact_name), "wb") as handle:
                    handle.write(artifact)
                with open(os.path.join(root, stem + ".result.json"), "w", encoding="utf-8") as handle:
                    json.dump(result(
                        variant, tokens=tokens, artifact_path=artifact_name,
                        artifact_sha256=artifact_hash,
                    ), handle)
                with open(os.path.join(root, stem + ".assessment.json"), "w", encoding="utf-8") as handle:
                    json.dump(assessment(variant, artifact_sha256=artifact_hash), handle)
            summary = harness.score_suite(suite(), root)
        row = next(item for item in summary["rows"] if item["variant"] == "v0_13")
        self.assertFalse(summary["comparison_ready"])
        self.assertFalse(row["within_budget"])
        self.assertFalse(row["comparable"])

    def test_score_rejects_tampered_bound_artifact(self):
        with tempfile.TemporaryDirectory() as root:
            for variant in suite()["variants"]:
                stem = f"case_universe_01__{variant}"
                artifact_name = stem + ".artifact.md"
                with open(os.path.join(root, artifact_name), "w", encoding="utf-8") as handle:
                    handle.write("tampered")
                with open(os.path.join(root, stem + ".result.json"), "w", encoding="utf-8") as handle:
                    json.dump(result(variant, artifact_path=artifact_name), handle)
                with open(os.path.join(root, stem + ".assessment.json"), "w", encoding="utf-8") as handle:
                    json.dump(assessment(variant), handle)
            summary = harness.score_suite(suite(), root)
        self.assertFalse(summary["comparison_ready"])
        self.assertTrue(any("does not match" in error for error in summary["errors"]))

    def test_variant_path_traversal_is_rejected(self):
        data = suite()
        data["variants"] = ["single_agent", "../escape"]
        with self.assertRaisesRegex(ValueError, "variants must use"):
            harness.validate_suite(data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
