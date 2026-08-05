import json
import hashlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import benchmark_harness as harness


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALLED_PACKAGE = os.path.isfile(
    os.path.join(REPO_ROOT, ".trade-nothing-install-manifest.json")
)


def suite():
    prompt_hash = "c" * 64
    return {
        "schema_version": harness.SUITE_SCHEMA,
        "suite_id": "v013-smoke",
        "variants": ["single_agent", "v0_12", "v0_13"],
        "variant_manifest": {
            variant: {
                "runner_kind": "PROMPT_ONLY",
                "engine_version": f"prompt:{prompt_hash}",
                "instruction_path": f"arms/{variant}.md",
                "instruction_sha256": prompt_hash,
            }
            for variant in ("single_agent", "v0_12", "v0_13")
        },
        "evaluation_scope": "CLOSED_PACKET_REASONING",
        "research_access": {
            "external_search_allowed": False,
            "filesystem_allowed": False,
        },
        "evidence_manifest": {
            "SNAP-A": {"path": "evidence/snap-a.json", "sha256": "a" * 64},
            "SNAP-B": {"path": "evidence/snap-b.json", "sha256": "b" * 64},
        },
        "cases": [{
            "case_id": "case_universe_01",
            "question_type": "UNIVERSE_SEARCH",
            "as_of": "2026-01-15",
            "prompt": "Find investable value-transfer paths without using future information.",
            "frozen_evidence": ["SNAP-A", "SNAP-B"],
            "budget": {
                "max_tokens": 10000,
                "max_searches": 0,
                "max_wall_seconds": 600,
            },
        }],
    }


def result(
    variant,
    tokens=5000,
    artifact_path="artifact.md",
    artifact_sha256="a" * 64,
    suite_data=None,
):
    validated = harness.validate_suite(suite_data or suite())
    variant_contract = validated["variant_manifest"][variant]
    receipt = {
        "verified_by_host": True,
        "host_invocation_id": f"HOST-{variant}",
        "runner_kind": variant_contract["runner_kind"],
        "engine_version": variant_contract["engine_version"],
        "variant_contract_sha256": variant_contract["variant_contract_sha256"],
    }
    if variant_contract["runner_kind"] == "PROMPT_ONLY":
        receipt["instruction_sha256"] = variant_contract["instruction_sha256"]
    else:
        receipt.update({
            "git_commit": variant_contract["git_commit"],
            "entrypoint_sha256": variant_contract["entrypoint_sha256"],
            "orchestrator_sha256": variant_contract["orchestrator_sha256"],
        })
    return {
        "schema_version": harness.RESULT_SCHEMA,
        "case_id": "case_universe_01",
        "variant": variant,
        "suite_contract_sha256": validated["suite_contract_sha256"],
        "variant_contract_sha256": variant_contract["variant_contract_sha256"],
        "execution_id": f"EXEC-{variant}",
        "engine_version": variant_contract["engine_version"],
        "engine_receipt": receipt,
        "completion_status": "COMPLETE",
        "artifact_path": artifact_path,
        "artifact_sha256": artifact_sha256,
        "usage": {"tokens_total": tokens, "search_count": 0, "wall_seconds": 120},
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
            "insight_card_total": 4,
            "insight_card_valid": 3,
            "causal_path_total": 3,
            "causal_path_valid": 2,
            "exploration_trace_total": 2,
            "exploration_trace_complete": 1,
            "hypothesis_laundering_count": 0,
            "formal_exploration_action_confusion_count": 0,
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
    def test_persisted_v014_suite_is_real_and_complete(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        suite_path = os.path.join(
            repo_root, "benchmarks", "v014-six-case", "suite.json"
        )
        data = harness._load_json(suite_path)
        validated = harness.validate_evidence_files(data, suite_path)
        self.assertEqual(len(validated["cases"]), 6)
        self.assertEqual(
            set(case["question_type"] for case in validated["cases"]),
            harness.QUESTION_TYPES,
        )
        self.assertEqual(validated["variants"], ["single_agent", "v0_12", "v0_14"])
        self.assertEqual(validated["evaluation_scope"], "CLOSED_PACKET_REASONING")
        self.assertTrue(all(case["budget"]["max_searches"] == 0 for case in validated["cases"]))
        self.assertEqual(
            validated["variant_manifest"]["v0_12"]["git_commit"],
            "b8514c77b329e67a95d8224ec36aaff479a27f5d",
        )
        self.assertEqual(
            validated["variant_manifest"]["v0_14"]["git_commit"],
            "50b4ed9d59df8dd9b0753d0432e6a15e8d95d18f",
        )

    def test_current_suite_compares_baseline_prior_and_48e0366(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        suite_path = os.path.join(
            repo_root, "benchmarks", "v014-six-case", "suite-48e0366.json"
        )
        data = harness._load_json(suite_path)
        validated = harness.validate_evidence_files(data, suite_path)
        self.assertEqual(validated["suite_id"], "v014-six-case-48e0366")
        self.assertEqual(validated["variants"], ["single_agent", "v0_14", "48e0366"])
        self.assertEqual(
            validated["variant_manifest"]["48e0366"]["git_commit"],
            "48e0366cb5069e28540ef3f45e948e635f171fcc",
        )
        self.assertEqual(
            validated["variant_manifest"]["48e0366"]["method_contract_sha256"],
            "1d68e4ace893ad8e91541af12a8f5da32a9c6b4ac003855dab0395697568107e",
        )
        if not INSTALLED_PACKAGE:
            verified = harness.verify_git_variants(data, repo_root)
            self.assertEqual(
                [item["variant"] for item in verified], ["v0_14", "48e0366"]
            )
        answer_key = harness._load_json(
            os.path.join(
                repo_root,
                "benchmarks",
                "v014-six-case",
                "assessor",
                "answer-key-48e0366.json",
            )
        )
        self.assertEqual(answer_key["suite_id"], validated["suite_id"])

    def test_closed_packet_suite_rejects_fake_search_budget(self):
        data = suite()
        data["cases"][0]["budget"]["max_searches"] = 1
        with self.assertRaisesRegex(ValueError, "must be 0"):
            harness.validate_suite(data)

    def test_result_must_bind_pinned_variant_engine(self):
        validated = harness.validate_suite(suite())
        case = validated["cases"][0]
        data = result("v0_13")
        data["engine_version"] = "latest"
        with self.assertRaisesRegex(ValueError, "pinned variant"):
            harness.validate_result(data, case, validated)

    def test_result_must_bind_variant_contract(self):
        validated = harness.validate_suite(suite())
        case = validated["cases"][0]
        data = result("v0_13")
        data["variant_contract_sha256"] = "d" * 64
        with self.assertRaisesRegex(ValueError, "variant contract"):
            harness.validate_result(data, case, validated)

    def test_result_requires_host_verified_engine_receipt(self):
        validated = harness.validate_suite(suite())
        case = validated["cases"][0]
        data = result("v0_13")
        data["engine_receipt"]["verified_by_host"] = False
        with self.assertRaisesRegex(ValueError, "host-verified"):
            harness.validate_result(data, case, validated)

    def test_canonical_git_variant_pins_are_real(self):
        if INSTALLED_PACKAGE:
            self.skipTest("pinned Git objects are unavailable in an installed package")
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        suite_path = os.path.join(
            repo_root, "benchmarks", "v014-six-case", "suite.json"
        )
        data = harness._load_json(suite_path)
        verified = harness.verify_git_variants(data, repo_root)
        self.assertEqual([item["variant"] for item in verified], ["v0_12", "v0_14"])

    def test_dispatch_contains_one_case_and_no_assessor_material(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        suite_path = os.path.join(
            repo_root, "benchmarks", "v014-six-case", "suite.json"
        )
        data = harness._load_json(suite_path)
        dispatch = harness.materialize_case_dispatch(
            data, suite_path, "ai_power_infrastructure_2025", "single_agent"
        )
        encoded = json.dumps(dispatch, ensure_ascii=False).lower()
        self.assertEqual(dispatch["schema_version"], harness.DISPATCH_SCHEMA)
        self.assertEqual(dispatch["case"]["case_id"], "ai_power_infrastructure_2025")
        self.assertEqual(dispatch["variant"], "single_agent")
        self.assertIn("one investment researcher", dispatch["method_instruction"])
        self.assertEqual(len(dispatch["evidence_packets"]), 1)
        self.assertNotIn("answer-key", encoded)
        self.assertNotIn("major_paths", encoded)
        self.assertNotIn("false_opportunity_traps", encoded)
        self.assertNotIn("ai_gpu_bottleneck_2024", encoded)

    def test_dispatch_must_be_written_outside_suite_tree(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        suite_path = os.path.join(
            repo_root, "benchmarks", "v014-six-case", "suite.json"
        )
        data = harness._load_json(suite_path)
        forbidden = os.path.join(
            repo_root, "benchmarks", "v014-six-case", "dispatch.json"
        )
        with self.assertRaisesRegex(ValueError, "outside the suite"):
            harness.write_case_dispatch(
                data, suite_path, "ai_power_infrastructure_2025", "single_agent", forbidden
            )

    def test_suite_rejects_answer_leakage(self):
        data = suite()
        data["cases"][0]["gold_answer"] = "future winner"
        with self.assertRaisesRegex(ValueError, "leakage"):
            harness.validate_suite(data)

    def test_result_cannot_score_itself(self):
        data = result("v0_13")
        data["assessment"] = {"great": True}
        validated = harness.validate_suite(suite())
        case = validated["cases"][0]
        with self.assertRaisesRegex(ValueError, "own assessment"):
            harness.validate_result(data, case, validated)

    def test_blind_assessment_must_bind_exact_artifact(self):
        validated = harness.validate_suite(suite())
        case = validated["cases"][0]
        run = harness.validate_result(result("v0_13"), case, validated)
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
        self.assertIsNone(summary["candidate_variant"])
        self.assertIsNone(summary["method_change_gate_pass"])
        self.assertFalse(summary["method_change_gate_ready"])
        self.assertEqual(
            harness._method_change_cli_outcome(summary),
            ("COMPARISON_READY_NOT_GATED", 3),
        )
        self.assertEqual(summary["observed_case_variant_pairs"], 3)
        self.assertEqual(summary["aggregates"]["v0_13"]["claim_precision"], 0.75)
        self.assertEqual(summary["aggregates"]["v0_13"]["major_path_coverage"], 0.666667)
        self.assertEqual(
            summary["aggregates"]["v0_13"]["insight_card_valid_rate"],
            0.75,
        )
        self.assertEqual(
            summary["aggregates"]["v0_13"]["causal_path_valid_rate"],
            0.666667,
        )
        self.assertEqual(
            summary["aggregates"]["v0_13"][
                "exploration_trace_complete_rate"
            ],
            0.5,
        )
        self.assertEqual(summary["aggregates"]["v0_13"]["tokens_per_effective_seed"], 5000)
        md = harness.render_markdown(summary)
        self.assertIn("Benchmark Summary", md)
        self.assertIn("v0_13", md)
        self.assertIn("Hypothesis laundering", md)
        self.assertIn("Method-change ready: **FALSE**", md)

    def test_method_change_gate_requires_declared_candidate_and_clean_safety(self):
        data = suite()
        data["candidate_variant"] = "v0_13"
        with tempfile.TemporaryDirectory() as root:
            for variant in data["variants"]:
                stem = f"case_universe_01__{variant}"
                artifact_name = stem + ".artifact.md"
                artifact = f"frozen output for {variant}".encode("utf-8")
                artifact_hash = hashlib.sha256(artifact).hexdigest()
                with open(os.path.join(root, artifact_name), "wb") as handle:
                    handle.write(artifact)
                with open(
                    os.path.join(root, stem + ".result.json"),
                    "w",
                    encoding="utf-8",
                ) as handle:
                    json.dump(
                        result(
                            variant,
                            artifact_path=artifact_name,
                            artifact_sha256=artifact_hash,
                            suite_data=data,
                        ),
                        handle,
                    )
                review = assessment(variant, artifact_sha256=artifact_hash)
                with open(
                    os.path.join(root, stem + ".assessment.json"),
                    "w",
                    encoding="utf-8",
                ) as handle:
                    json.dump(review, handle)

            ready = harness.score_suite(data, root)
            self.assertTrue(ready["comparison_ready"])
            self.assertTrue(ready["method_change_gate_pass"])
            self.assertTrue(ready["method_change_gate_ready"])
            self.assertEqual(
                harness._method_change_cli_outcome(ready),
                ("METHOD_CHANGE_READY", 0),
            )

            unsafe_path = os.path.join(
                root, "case_universe_01__v0_13.assessment.json"
            )
            unsafe = harness._load_json(unsafe_path)
            unsafe["metrics"]["hypothesis_laundering_count"] = 1
            with open(unsafe_path, "w", encoding="utf-8") as handle:
                json.dump(unsafe, handle)
            blocked = harness.score_suite(data, root)

        self.assertTrue(blocked["comparison_ready"])
        self.assertFalse(blocked["method_change_gate_pass"])
        self.assertFalse(blocked["method_change_gate_ready"])
        self.assertEqual(
            harness._method_change_cli_outcome(blocked),
            ("BLOCKED_METHOD_CHANGE", 4),
        )

    def test_exploration_numerator_cannot_exceed_denominator(self):
        validated = harness.validate_suite(suite())
        case = validated["cases"][0]
        run = harness.validate_result(result("v0_13"), case, validated)
        review = assessment("v0_13")
        review["metrics"]["insight_card_valid"] = 5
        with self.assertRaisesRegex(
            ValueError, "insight_card_valid cannot exceed"
        ):
            harness.validate_assessment(review, run)

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
        self.assertFalse(summary["method_change_gate_ready"])
        self.assertEqual(
            harness._method_change_cli_outcome(summary),
            ("BLOCKED_COMPARISON", 2),
        )
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

    def test_evidence_packet_hash_is_verified(self):
        with tempfile.TemporaryDirectory() as root:
            evidence_dir = os.path.join(root, "evidence")
            os.makedirs(evidence_dir)
            arms_dir = os.path.join(root, "arms")
            os.makedirs(arms_dir)
            data = suite()
            for variant in data["variants"]:
                path = os.path.join(arms_dir, f"{variant}.md")
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("baseline")
                with open(path, "rb") as handle:
                    arm_hash = hashlib.sha256(handle.read()).hexdigest()
                data["variant_manifest"][variant]["instruction_sha256"] = arm_hash
                data["variant_manifest"][variant]["engine_version"] = f"prompt:{arm_hash}"
            for evidence_id, filename in (("SNAP-A", "snap-a.json"), ("SNAP-B", "snap-b.json")):
                packet = {
                    "packet_id": evidence_id,
                    "as_of": "2026-01-15",
                    "sources": [{"date": "2026-01-14"}],
                }
                path = os.path.join(evidence_dir, filename)
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(packet, handle)
                with open(path, "rb") as handle:
                    data["evidence_manifest"][evidence_id]["sha256"] = hashlib.sha256(
                        handle.read()
                    ).hexdigest()
            suite_path = os.path.join(root, "suite.json")
            with open(suite_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            harness.validate_evidence_files(data, suite_path)
            with open(os.path.join(evidence_dir, "snap-a.json"), "a", encoding="utf-8") as handle:
                handle.write(" ")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                harness.validate_evidence_files(data, suite_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
