import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discovery_benchmark_harness as harness


REPO_ROOT = Path(__file__).resolve().parent.parent
SUITE_PATH = REPO_ROOT / "benchmarks" / "v014-discovery-pilot" / "suite.json"
ANSWER_KEY_PATH = SUITE_PATH.parent / "assessor" / "answer-key.json"
CURRENT_SUITE_PATH = SUITE_PATH.parent / "suite-48e0366.json"
CURRENT_ANSWER_KEY_PATH = SUITE_PATH.parent / "assessor" / "answer-key-48e0366.json"


def load_suite(candidate_variant=None):
    data = harness._load_json(SUITE_PATH)
    if candidate_variant:
        data["candidate_variant"] = candidate_variant
    return harness.validate_suite(data, SUITE_PATH)


def engine_receipt(contract, invocation_id):
    receipt = {
        "verified_by_host": True,
        "host_invocation_id": invocation_id,
    }
    receipt.update(harness._variant_receipt_expected(contract))
    return receipt


def write_complete_results(suite, answer_key, root):
    for case in suite["cases"]:
        relevant = answer_key["cases"][case["case_id"]]["relevant_doc_ids"]
        for variant in suite["variants"]:
            stem = f"{case['case_id']}__{variant}"
            artifact_path = root / f"{stem}.report.md"
            artifact_path.write_text(
                f"frozen report for {stem}\n", encoding="utf-8"
            )
            artifact_hash = harness._hash_file(artifact_path)
            log_path = root / f"{stem}.retrieval.jsonl"
            log_path.write_text(
                harness._json(
                    {"seq": 1, "event": "READ_SET", "doc_ids": relevant}
                )
                + "\n",
                encoding="utf-8",
            )
            receipt = {
                "schema_version": harness.RETRIEVAL_RECEIPT_SCHEMA,
                "session_id": f"DISC-{case['case_id']}-{variant}",
                "suite_contract_sha256": suite["suite_contract_sha256"],
                "corpus_sha256": suite["corpus_manifest"]["sha256"],
                "case_id": case["case_id"],
                "variant": variant,
                "as_of": case["as_of"],
                "query_count": 3,
                "event_count": 1,
                "read_doc_ids": relevant,
                "distinct_documents_read": len(relevant),
                "retrieval_log_sha256": harness._hash_file(log_path),
                "within_gateway_budget": True,
            }
            receipt_path = root / f"{stem}.retrieval-receipt.json"
            receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
            contract = suite["variant_manifest"][variant]
            result = {
                "schema_version": harness.RESULT_SCHEMA,
                "case_id": case["case_id"],
                "variant": variant,
                "suite_contract_sha256": suite["suite_contract_sha256"],
                "variant_contract_sha256": contract["variant_contract_sha256"],
                "engine_version": contract["engine_version"],
                "engine_receipt": engine_receipt(contract, f"HOST-{stem}"),
                "completion_status": "COMPLETE",
                "artifact_path": artifact_path.name,
                "artifact_sha256": artifact_hash,
                "retrieval_receipt_path": receipt_path.name,
                "retrieval_receipt_sha256": harness._hash_file(receipt_path),
                "retrieval_log_path": log_path.name,
                "usage": {"tokens_total": 6000, "wall_seconds": 90},
            }
            assessment = {
                "schema_version": harness.ASSESSMENT_SCHEMA,
                "case_id": case["case_id"],
                "variant": variant,
                "artifact_sha256": artifact_hash,
                "assessor_id": "blind-reviewer",
                "blind": True,
                "metrics": {
                    "decisive_claim_total": 4,
                    "decisive_claim_correct": 3,
                    "false_source_count": 0,
                    "major_path_total": len(
                        answer_key["cases"][case["case_id"]]["major_paths"]
                    ),
                    "major_path_found": 3,
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
                    "false_discovery_count": 0,
                    "novel_valid_path_count": 0,
                    "pricing_anchor_total": 2,
                    "pricing_anchor_valid": 1,
                    "maturity_misread_count": 0,
                    "comprehension_question_total": 3,
                    "comprehension_question_correct": 3,
                    "manual_edit_count": 0,
                },
            }
            (root / f"{stem}.result.json").write_text(
                json.dumps(result) + "\n", encoding="utf-8"
            )
            (root / f"{stem}.assessment.json").write_text(
                json.dumps(assessment) + "\n", encoding="utf-8"
            )


class DiscoveryBenchmarkHarnessTests(unittest.TestCase):
    def test_persisted_pilot_is_bound_and_evaluator_material_is_separate(self):
        suite = load_suite()
        self.assertEqual(suite["evaluation_scope"], "FROZEN_CORPUS_DISCOVERY")
        self.assertEqual(len(suite["cases"]), 3)
        self.assertEqual(len(suite["documents"]), 20)
        self.assertEqual(suite["variants"], ["single_agent", "v0_12", "v0_14"])
        answer_key = harness._load_json(ANSWER_KEY_PATH)
        self.assertEqual(set(answer_key["cases"]), {case["case_id"] for case in suite["cases"]})
        self.assertTrue(all(
            len(case["comprehension_questions"]) == 3
            for case in answer_key["cases"].values()
        ))

    def test_current_pilot_compares_baseline_prior_and_48e0366(self):
        suite = harness.validate_suite(
            harness._load_json(CURRENT_SUITE_PATH), CURRENT_SUITE_PATH
        )
        self.assertEqual(suite["suite_id"], "v014-discovery-pilot-48e0366")
        self.assertEqual(suite["variants"], ["single_agent", "v0_14", "48e0366"])
        self.assertEqual(
            suite["variant_manifest"]["48e0366"]["git_commit"],
            "48e0366cb5069e28540ef3f45e948e635f171fcc",
        )
        self.assertEqual(
            suite["variant_manifest"]["48e0366"]["method_contract_sha256"],
            "1d68e4ace893ad8e91541af12a8f5da32a9c6b4ac003855dab0395697568107e",
        )
        self.assertEqual(
            harness.verify_git_variants(suite, REPO_ROOT), ["v0_14", "48e0366"]
        )
        answer_key = harness._load_json(CURRENT_ANSWER_KEY_PATH)
        self.assertEqual(answer_key["suite_id"], suite["suite_id"])
        self.assertEqual(
            set(answer_key["cases"]), {case["case_id"] for case in suite["cases"]}
        )

    def test_dispatch_has_no_corpus_bodies_or_evaluator_keys(self):
        suite = load_suite()
        with tempfile.TemporaryDirectory() as parent:
            run_dir = Path(parent) / "run"
            dispatch = harness.initialize_run(
                suite, SUITE_PATH, "ai_power_infrastructure_2025", "single_agent", run_dir
            )
            encoded = json.dumps(dispatch, ensure_ascii=False).lower()
        self.assertNotIn("answer_key", encoded)
        self.assertNotIn("major_paths", encoded)
        self.assertNotIn("relevant_doc_ids", encoded)
        self.assertNotIn("microsoft and constellation", encoded)
        self.assertNotIn(str(SUITE_PATH.parent).lower(), encoded)

    def test_git_method_adapters_are_executable_and_receipt_bound(self):
        suite = load_suite()
        for variant in ("v0_12", "v0_14"):
            contract = suite["variant_manifest"][variant]
            self.assertEqual(contract["runner_kind"], "GIT_METHOD_ADAPTER")
            with tempfile.TemporaryDirectory() as parent:
                dispatch = harness.initialize_run(
                    suite,
                    SUITE_PATH,
                    "ai_power_infrastructure_2025",
                    variant,
                    Path(parent) / "run",
                )
            self.assertIn(variant.replace("_", "."), dispatch["method_instruction"])
            self.assertEqual(
                harness._hash_bytes(dispatch["method_instruction"].encode("utf-8")),
                contract["method_instruction_sha256"],
            )
            self.assertEqual(
                harness._variant_receipt_expected(contract)["method_instruction_sha256"],
                contract["method_instruction_sha256"],
            )

    def test_read_requires_prior_search_and_as_of_excludes_future_documents(self):
        suite = load_suite()
        with tempfile.TemporaryDirectory() as parent:
            run_dir = Path(parent) / "run"
            harness.initialize_run(
                suite, SUITE_PATH, "regional_bank_systemic_short_2024", "single_agent", run_dir
            )
            with self.assertRaisesRegex(ValueError, "first be returned"):
                harness.read_document(run_dir, "DOC-CEG-MSFT-PPA")
            result = harness.search(run_dir, "Microsoft Constellation nuclear power", 5)
            self.assertEqual(result["results"], [])
            state = harness._load_json(run_dir / "gateway-state.json")
            self.assertNotIn("DOC-CEG-MSFT-PPA", state["accessible_doc_ids"])

    def test_repeated_reads_have_unique_sequence_and_finalization_locks_session(self):
        suite = load_suite()
        with tempfile.TemporaryDirectory() as parent:
            run_dir = Path(parent) / "run"
            harness.initialize_run(
                suite, SUITE_PATH, "regional_bank_systemic_short_2024", "single_agent", run_dir
            )
            search_result = harness.search(
                run_dir, "regional bank commercial real estate capital deposits", 5
            )
            doc_id = search_result["results"][0]["doc_id"]
            harness.read_document(run_dir, doc_id)
            harness.read_document(run_dir, doc_id)
            receipt = harness.finalize_retrieval(run_dir)
            self.assertEqual(receipt, harness.finalize_retrieval(run_dir))
            events = [json.loads(line) for line in (run_dir / "retrieval.jsonl").read_text().splitlines()]
            self.assertEqual([event["seq"] for event in events], [1, 2, 3])
            self.assertEqual(receipt["event_count"], 3)
            with self.assertRaisesRegex(ValueError, "finalized"):
                harness.search(run_dir, "capital", 5)
            with self.assertRaisesRegex(ValueError, "finalized"):
                harness.read_document(run_dir, doc_id)

    def test_query_budget_is_enforced(self):
        suite = load_suite()
        with tempfile.TemporaryDirectory() as parent:
            run_dir = Path(parent) / "run"
            harness.initialize_run(
                suite, SUITE_PATH, "regional_bank_systemic_short_2024", "single_agent", run_dir
            )
            for index in range(10):
                harness.search(run_dir, f"regional bank capital {index}", 1)
            with self.assertRaisesRegex(ValueError, "query budget exhausted"):
                harness.search(run_dir, "one query too many", 1)

    def test_full_three_by_three_score_contract_closes(self):
        suite = load_suite()
        answer_key = harness._load_json(ANSWER_KEY_PATH)
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent)
            write_complete_results(suite, answer_key, root)
            summary = harness.score_suite(suite, answer_key, root)
        self.assertTrue(summary["comparison_ready"])
        self.assertIsNone(summary["candidate_variant"])
        self.assertIsNone(summary["method_change_gate_pass"])
        self.assertFalse(summary["method_change_gate_ready"])
        self.assertEqual(
            harness._method_change_cli_outcome(summary),
            ("COMPARISON_READY_NOT_GATED", 3),
        )
        self.assertEqual(summary["observed_case_variant_pairs"], 9)
        self.assertEqual(summary["aggregates"]["v0_14"]["source_recall"], 1.0)
        self.assertEqual(summary["aggregates"]["v0_14"]["retrieval_precision"], 1.0)
        self.assertEqual(summary["aggregates"]["v0_14"]["tokens_per_effective_seed"], 6000.0)
        self.assertEqual(
            summary["aggregates"]["v0_14"]["insight_card_valid_rate"],
            0.75,
        )
        self.assertIn(
            "Hypothesis laundering", harness.render_markdown(summary)
        )
        self.assertIn(
            "Method-change ready: **FALSE**", harness.render_markdown(summary)
        )

    def test_method_change_gate_requires_declared_candidate_and_clean_safety(self):
        suite = load_suite(candidate_variant="v0_14")
        answer_key = harness._load_json(ANSWER_KEY_PATH)
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent)
            write_complete_results(suite, answer_key, root)
            ready = harness.score_suite(suite, answer_key, root)
            self.assertTrue(ready["comparison_ready"])
            self.assertTrue(ready["method_change_gate_pass"])
            self.assertTrue(ready["method_change_gate_ready"])
            self.assertEqual(
                harness._method_change_cli_outcome(ready),
                ("METHOD_CHANGE_READY", 0),
            )

            unsafe_path = (
                root
                / f"{suite['cases'][0]['case_id']}__v0_14.assessment.json"
            )
            unsafe = harness._load_json(unsafe_path)
            unsafe["metrics"]["formal_exploration_action_confusion_count"] = 1
            unsafe_path.write_text(json.dumps(unsafe) + "\n", encoding="utf-8")
            blocked = harness.score_suite(suite, answer_key, root)

        self.assertTrue(blocked["comparison_ready"])
        self.assertFalse(blocked["method_change_gate_pass"])
        self.assertFalse(blocked["method_change_gate_ready"])
        self.assertEqual(
            harness._method_change_cli_outcome(blocked),
            ("BLOCKED_METHOD_CHANGE", 4),
        )

    def test_incomplete_comparison_blocks_before_method_gate(self):
        self.assertEqual(
            harness._method_change_cli_outcome({
                "comparison_ready": False,
                "candidate_variant": "v0_14",
                "method_change_gate_ready": False,
            }),
            ("BLOCKED_COMPARISON", 2),
        )


if __name__ == "__main__":
    unittest.main()
