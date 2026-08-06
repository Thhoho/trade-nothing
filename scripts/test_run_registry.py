#!/usr/bin/env python3
"""Offline tests for immutable run identity and stage envelopes."""
import json
import os
import tempfile
import unittest
from unittest import mock

import run_registry
import method_identity
import utils
from utils import save_json


class RunRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_scratch = os.environ.get("TRADE_NOTHING_SCRATCH_DIR")
        self.old_state = os.environ.pop("TRADE_NOTHING_STATE_PATH", None)
        self.old_run = os.environ.pop("TRADE_NOTHING_RUN_ID", None)
        self.old_purpose = os.environ.pop("TRADE_NOTHING_RUN_PURPOSE", None)
        os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.tmp.name

    def tearDown(self):
        if self.old_scratch is None:
            os.environ.pop("TRADE_NOTHING_SCRATCH_DIR", None)
        else:
            os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.old_scratch
        if self.old_state is not None:
            os.environ["TRADE_NOTHING_STATE_PATH"] = self.old_state
        else:
            os.environ.pop("TRADE_NOTHING_STATE_PATH", None)
        if self.old_run is not None:
            os.environ["TRADE_NOTHING_RUN_ID"] = self.old_run
        else:
            os.environ.pop("TRADE_NOTHING_RUN_ID", None)
        if self.old_purpose is not None:
            os.environ["TRADE_NOTHING_RUN_PURPOSE"] = self.old_purpose
        else:
            os.environ.pop("TRADE_NOTHING_RUN_PURPOSE", None)
        self.tmp.cleanup()

    def test_run_id_owns_state_path_and_rejects_topic_drift(self):
        manifest = run_registry.create_manifest("Exact topic")
        self.assertTrue(manifest["run_id"].startswith("RUN-"))
        self.assertIn(manifest["run_id"], manifest["state_path"])
        self.assertEqual(manifest["method_identity"], method_identity.build_method_identity())
        resolved = run_registry.resolve_context(run_id=manifest["run_id"])
        self.assertEqual(resolved["topic"], "Exact topic")
        with self.assertRaisesRegex(ValueError, "topic_run_mismatch"):
            run_registry.resolve_context(
                run_id=manifest["run_id"], topic="Exact topic?"
            )

    def test_run_purpose_is_validated_frozen_and_bound_to_runtime(self):
        manifest = run_registry.create_manifest(
            "Production topic", run_purpose="PRODUCTION_RESEARCH"
        )
        self.assertEqual(manifest["run_purpose"], "PRODUCTION_RESEARCH")
        run_registry.bind_context(manifest)
        self.assertEqual(
            os.environ["TRADE_NOTHING_RUN_PURPOSE"], "PRODUCTION_RESEARCH"
        )
        with self.assertRaisesRegex(ValueError, "run_purpose_invalid"):
            run_registry.create_manifest("Bad purpose", run_purpose="LIVEISH")

    def test_manifest_rejects_method_contract_drift(self):
        manifest = run_registry.create_manifest("Pinned method")
        path = run_registry.manifest_path(manifest["run_id"])
        with open(path, encoding="utf-8") as handle:
            stored = json.load(handle)
        stored["method_identity"]["contract_sha256"] = "0" * 64
        save_json(path, stored)
        with self.assertRaisesRegex(ValueError, "method_contract_drift"):
            run_registry.load_manifest(manifest["run_id"])
        inspected = run_registry.inspect_manifest(manifest["run_id"])
        self.assertEqual(inspected["method_identity_check"]["status"], "drift")
        self.assertEqual(
            inspected["method_identity_check"]["pinned"]["contract_sha256"],
            "0" * 64,
        )

    def test_adopt_existing_state_without_renaming_it(self):
        path = os.path.join(self.tmp.name, "v2-state", "legacy.json")
        save_json(path, {
            "topic": "Legacy exact topic",
            "rounds": [],
            "runtime": {"run_purpose": "HISTORICAL_REPLAY"},
        })
        manifest = run_registry.adopt_manifest("", path)
        self.assertEqual(manifest["topic"], "Legacy exact topic")
        self.assertEqual(manifest["state_path"], path)
        self.assertEqual(manifest["stage"], "adopted")
        self.assertEqual(manifest["run_purpose"], "HISTORICAL_REPLAY")

    def test_envelope_is_bounded_and_updates_manifest(self):
        manifest = run_registry.create_manifest("Envelope topic")
        envelope = run_registry.stage_envelope({
            "status": "paused_runtime_failure",
            "missing_roles": ["inquisitor"],
            "reason": "resource_exhausted_429",
            "instruction": "resume later",
            "state_path": manifest["state_path"],
        }, context=manifest, budget={"round_budget": 1, "rounds_used": 0})
        self.assertEqual(envelope["schema"], run_registry.ENVELOPE_SCHEMA)
        self.assertEqual(envelope["run_id"], manifest["run_id"])
        self.assertIn("inquisitor", envelope["blockers"])
        stored = run_registry.load_manifest(manifest["run_id"])
        self.assertEqual(stored["failure_count"], 1)
        self.assertLess(len(json.dumps(envelope)), 10000)

    def test_large_result_and_report_are_content_addressed_not_inlined(self):
        manifest = run_registry.create_manifest("Artifact topic")
        report = "# Report\n\n" + ("decision evidence\n" * 2000)
        facts_box = "<!-- FACTS_BOX_START -->\nlocked\n<!-- FACTS_BOX_END -->"
        evidence_ledger = "# Evidence Ledger\n\ncomplete evidence"
        candidate_cards = "# Candidate Cards\n\n0 candidates"
        result = {
            "status": "ready_for_report",
            "topic": manifest["topic"],
            "instruction": "consume the report path, not raw result",
            "report_markdown": report,
            "facts_box_markdown": facts_box,
            "evidence_ledger_markdown": evidence_ledger,
            "candidate_cards_markdown": candidate_cards,
            "report_view_model": {
                "schema_version": "trade-nothing.report-view-model.v1",
                "topic": manifest["topic"],
                "verdict": {"edge_state": "NO_EDGE"},
                "candidate_counts": {"lead_count": 0},
                "candidate_cards": [{"large": "y" * 20000}],
                "next_action": {"code": "STOP_NO_PROMOTABLE_CANDIDATE"},
            },
            "synthesis_packet": {"raw": "x" * 50000},
        }
        envelope = run_registry.stage_envelope(result, context=manifest)
        serialized = json.dumps(envelope)
        self.assertNotIn("decision evidence", serialized)
        self.assertNotIn("complete evidence", serialized)
        self.assertNotIn("x" * 100, serialized)
        self.assertLess(len(serialized), 10000)
        self.assertEqual(run_registry.load_result_artifact(envelope), result)
        self.assertEqual(
            envelope["result"]["decision_brief"]["verdict"]["edge_state"],
            "NO_EDGE",
        )
        self.assertNotIn("candidate_cards", envelope["result"]["decision_brief"])
        with open(envelope["artifact_paths"]["report_path"], encoding="utf-8") as handle:
            self.assertEqual(handle.read(), report)
        for path_key, expected in (
            ("facts_box_path", facts_box),
            ("evidence_ledger_path", evidence_ledger),
            ("candidate_cards_path", candidate_cards),
        ):
            with open(envelope["artifact_paths"][path_key], encoding="utf-8") as handle:
                self.assertEqual(handle.read(), expected)
        self.assertEqual(
            envelope["artifacts"]["result"]["read_policy"]["parent_context"],
            "ENVELOPE_ONLY",
        )

    def test_report_grade_and_candidate_lifecycle_remain_in_control_envelope(self):
        manifest = run_registry.create_manifest("Graded envelope")
        result = {
            "status": "report_data_ready",
            "topic": manifest["topic"],
            "report_grade": "FORMAL",
            "unmet_gates": [],
            "publication_allowed": True,
            "ranking_allowed": False,
            "candidate_lifecycle": {
                "report_grade_independent": True,
                "screening_status": "NO_SCREENABLE_CANDIDATE",
                "verification_status": "NOT_REQUIRED",
                "pending_steps": [],
            },
            "compatibility_warnings": ["deprecated flag ignored"],
            "instruction": "compose the report",
            "report_markdown": "# Report",
        }

        envelope = run_registry.stage_envelope(result, context=manifest)

        self.assertEqual(envelope["status"], "report_data_ready")
        self.assertEqual(envelope["result"]["report_grade"], "FORMAL")
        self.assertTrue(envelope["result"]["publication_allowed"])
        self.assertFalse(envelope["result"]["ranking_allowed"])
        self.assertTrue(
            envelope["result"]["candidate_lifecycle"]["report_grade_independent"]
        )
        self.assertIn("deprecated flag ignored", envelope["artifacts"]["result"]["warnings"])

    def test_read_only_status_projection_does_not_write_artifacts(self):
        manifest = run_registry.create_manifest("Read status")
        envelope = run_registry.stage_envelope(
            {
                "status": "run_status",
                "topic": manifest["topic"],
                "rounds_completed": 2,
                "execution_summary": {"role_attempts": 4},
            },
            context=manifest,
            persist=False,
        )
        self.assertEqual(envelope["result"]["rounds_completed"], 2)
        self.assertEqual(envelope["result"]["execution_summary"]["role_attempts"], 4)
        self.assertFalse(os.path.exists(run_registry.artifact_dir(manifest["run_id"])))

    def test_manifest_read_does_not_attempt_advisory_write_lock(self):
        manifest = run_registry.create_manifest("Read-only status")
        with mock.patch.object(
            utils.CrossPlatformFileLock, "acquire", side_effect=AssertionError("must not lock")
        ) as acquire:
            loaded = run_registry.load_manifest(manifest["run_id"])
        self.assertEqual(loaded["topic"], "Read-only status")
        self.assertFalse(acquire.called)

    def test_execution_summary_counts_structured_receipts_without_transcripts(self):
        manifest = run_registry.create_manifest("Metrics")
        run_registry.save_checkpoint(manifest["run_id"], "round-1", {
            "submitted": True,
            "roles": {
                "detective": {"exit_code": 0, "payload_sha256": "a", "elapsed_seconds": 2},
                "inquisitor": {"exit_code": 1, "payload_sha256": "", "elapsed_seconds": 3,
                               "error_code": "resource_exhausted_429"},
            },
        })
        summary = run_registry.execution_summary(manifest["run_id"])
        self.assertEqual(summary["checkpoint_count"], 1)
        self.assertEqual(summary["submitted_rounds"], 1)
        self.assertEqual(summary["role_attempts"], 2)
        self.assertEqual(summary["role_successes"], 1)
        self.assertEqual(summary["elapsed_seconds"], 5.0)
        self.assertEqual(summary["last_error_code"], "resource_exhausted_429")


if __name__ == "__main__":
    unittest.main(verbosity=2)
