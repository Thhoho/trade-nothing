#!/usr/bin/env python3
"""Offline contract tests for the isolated Claim Verifier runner."""
import unittest

import candidate_screen_engine
import claim_verification_engine
import claim_verifier_runner
import codex_claim_verifier_receipt


class ClaimVerifierRunnerTests(unittest.TestCase):
    def test_process_receipt_binds_dispatch_prompt_and_payload(self):
        payload = {"claim_verifications": [{"claim_id": "CL-1"}]}
        dispatch = {
            "dispatch_id": "CVD-TEST",
            "claim_ids": ["CL-1"],
            "snapshot_ids": ["SS-1"],
        }
        result = {
            "host_runtime": "claude-code",
            "invocation_id": "claim-verifier-test",
            "process_id": 4242,
            "exit_code": 0,
            "timed_out": False,
            "elapsed_seconds": 1.25,
            "prompt_sha256": "a" * 64,
            "payload_sha256": candidate_screen_engine.payload_sha256(payload),
            "parse_error": "",
        }
        receipt = claim_verifier_runner.build_receipt(dispatch, result)
        self.assertEqual(receipt["runner_kind"], "claude_separate_process_v1")
        self.assertEqual(receipt["verifier"]["payload_sha256"], result["payload_sha256"])
        self.assertEqual(
            receipt["receipt_id"], claim_verification_engine.isolation_receipt_id(receipt)
        )

    def test_codex_receipt_binds_canonical_agent_and_exact_payload(self):
        payload = {"claim_verifications": [{"claim_id": "CL-1"}]}
        dispatch = {
            "dispatch_id": "CVD-CODEX",
            "claim_ids": ["CL-1"],
            "snapshot_ids": ["SS-1"],
            "verifier_prompt": "exact verifier prompt",
        }
        receipt = codex_claim_verifier_receipt.build_receipt(
            dispatch, payload, "/root/claim-verifier"
        )
        self.assertEqual(receipt["runner_kind"], "codex_collaboration_v1")
        self.assertEqual(receipt["verifier"]["agent_id"], "/root/claim-verifier")
        self.assertEqual(
            receipt["verifier"]["payload_sha256"],
            candidate_screen_engine.payload_sha256(payload),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
