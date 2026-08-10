#!/usr/bin/env python3
"""Offline tests for the deepthink2 execution-truth boundary."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

import execution_integrity
import method_identity
import run_registry
import validate_report_v2
from utils import save_json


class ExecutionIntegrityTests(unittest.TestCase):
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

    def _fixture(self):
        dispatch = {
            "detective_prompt": "detective contract",
            "inquisitor_prompt": "inquisitor contract",
            "judge_prompt": "judge contract",
        }
        payloads = {
            "detective": {"answer": "d"},
            "inquisitor": {"answer": "i"},
            "judge": {"crux_signals": {}},
        }
        receipt = execution_integrity.build_codex_receipt(
            1, dispatch, payloads,
            {"detective": "/root/d", "inquisitor": "/root/i", "judge": "/root/j"},
        )
        return dispatch, payloads, receipt

    def test_codex_receipt_binds_three_distinct_agents_prompts_and_payloads(self):
        dispatch, payloads, receipt = self._fixture()
        valid = execution_integrity.validate_round_receipt(
            receipt, 1, dispatch,
            payloads["detective"], payloads["inquisitor"], payloads["judge"],
        )
        self.assertEqual(valid["status"], "verified")
        tampered = json.loads(json.dumps(payloads["detective"]))
        tampered["answer"] = "changed"
        invalid = execution_integrity.validate_round_receipt(
            receipt, 1, dispatch, tampered, payloads["inquisitor"], payloads["judge"]
        )
        self.assertEqual(invalid["status"], "invalid")
        self.assertIn("round_receipt_detective_payload_hash_mismatch", invalid["blockers"])

    def test_only_registered_current_state_with_all_receipts_can_claim_rounds(self):
        _, payloads, receipt = self._fixture()
        manifest = run_registry.create_manifest("Truth boundary")
        state = {
            "topic": manifest["topic"],
            "method_identity": method_identity.build_method_identity(),
            "runtime": {
                "run_id": manifest["run_id"],
                "state_path": manifest["state_path"],
            },
            "rounds": [{
                "round": 1,
                "detective_raw": payloads["detective"],
                "inquisitor_raw": payloads["inquisitor"],
                "judge_host_raw": payloads["judge"],
                "execution_receipt": receipt,
                "execution_integrity": {
                    "status": "verified",
                    "receipt_id": receipt["receipt_id"],
                    "runner_kind": receipt["runner_kind"],
                    "blockers": [],
                },
            }],
        }
        save_json(manifest["state_path"], state)
        audit = execution_integrity.audit_state(state)
        self.assertEqual(audit["execution_mode"], "ORCHESTRATED_VERIFIED")
        self.assertTrue(audit["can_claim_completed_rounds"])

        state["rounds"][0]["execution_integrity"] = {"status": "missing"}
        degraded = execution_integrity.audit_state(state)
        self.assertEqual(degraded["execution_mode"], "STATE_ONLY_UNVERIFIED")
        self.assertFalse(degraded["can_claim_completed_rounds"])

    def test_phase_authority_requires_persisted_payload_bound_round_receipt(self):
        _, payloads, receipt = self._fixture()
        state = {
            "rounds": [{
                "round": 1,
                "detective_raw": payloads["detective"],
                "inquisitor_raw": payloads["inquisitor"],
                "judge_host_raw": payloads["judge"],
                "execution_receipt": receipt,
                "execution_integrity": {
                    "status": "verified",
                    "receipt_id": receipt["receipt_id"],
                },
            }],
        }
        self.assertTrue(
            execution_integrity.round_role_execution_verified(state, 1, "detective")
        )
        state["rounds"][0]["detective_raw"] = {"answer": "tampered"}
        self.assertFalse(
            execution_integrity.round_role_execution_verified(state, 1, "detective")
        )

    def test_caller_supplied_receipt_label_has_no_phase_authority(self):
        state = {
            "rounds": [{
                "round": 1,
                "detective_raw": {"answer": "d"},
                "inquisitor_raw": {"answer": "i"},
                "judge_host_raw": {},
                "execution_integrity": {
                    "status": "verified",
                    "receipt_id": "RER-ARBITRARY",
                },
            }],
        }
        self.assertFalse(
            execution_integrity.round_role_execution_verified(state, 1, "detective")
        )

    def test_method_drift_is_always_historical_replay(self):
        state = {
            "method_identity": {
                **method_identity.build_method_identity(),
                "contract_sha256": "0" * 64,
            },
            "runtime": {},
            "rounds": [{"execution_integrity": {"status": "verified"}}],
        }
        audit = execution_integrity.audit_state(state)
        self.assertEqual(audit["execution_mode"], "HISTORICAL_REPLAY")
        self.assertFalse(audit["can_claim_current_method_run"])

    def test_inline_marker_has_no_round_or_isolation_authority(self):
        audit = execution_integrity.inline_audit("topic", "2026-08-10")
        parsed = execution_integrity.parse_marker(execution_integrity.marker(audit))
        self.assertEqual(parsed, audit)
        self.assertFalse(parsed["can_claim_completed_rounds"])
        self.assertFalse(parsed["can_claim_isolated_roles"])

    def test_report_validator_rejects_missing_marker_and_inline_round_theatre(self):
        missing = (
            "# Custom research title\n\n"
            "> Trade Nothing `-deepthink2`｜3 轮预算\n"
        )
        inline = (
            "# Deep Research Report\n"
            + execution_integrity.marker(execution_integrity.inline_audit("topic"))
            + "\n\n## 第一轮：搜索\n"
        )
        for markdown, expected in (
            (missing, "Missing TRADE_NOTHING_EXECUTION_INTEGRITY marker"),
            (inline, "INLINE_DEGRADED_RESEARCH cannot claim completed rounds"),
        ):
            path = os.path.join(
                self.tmp.name,
                execution_integrity.canonical_json_hash(expected)[:12] + ".md",
            )
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(markdown)
            errors, _ = validate_report_v2.validate_report(path)
            self.assertTrue(any(expected in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
