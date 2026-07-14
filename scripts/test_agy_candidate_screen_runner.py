#!/usr/bin/env python3
"""Offline tests for the separate-process agy CandidateScreen adapter."""
import hashlib
import json
import unittest

import agy_candidate_screen_runner as runner
import candidate_screen_engine
import deepthink_orchestrator_v2 as orchestrator
import test_candidate_screen_engine as fixtures


class AgyCandidateScreenRunnerTests(unittest.TestCase):
    def test_dangerous_permission_bypass_requires_explicit_opt_in(self):
        safe = runner._build_command("agy", "prompt", 60)
        enabled = runner._build_command("agy", "prompt", 60, allow_agent_tools=True)
        self.assertNotIn("--dangerously-skip-permissions", safe)
        self.assertIn("--dangerously-skip-permissions", enabled)

    def test_role_output_must_be_exact_json_without_commentary(self):
        self.assertEqual(runner._parse_json_output('{"candidate_screens": []}'), {
            "candidate_screens": [],
        })
        with self.assertRaisesRegex(ValueError, "exact JSON"):
            runner._parse_json_output('I finished.\n{"candidate_screens": []}')

    def test_separate_process_receipt_binds_dispatch_prompt_and_payload(self):
        st = fixtures.state_with_seed()
        analyst = fixtures.payload("Analyst")
        skeptic = fixtures.payload("Skeptic")
        prompts = orchestrator.candidate_screen_prompts(
            st, candidate_screen_engine.screenable_seeds(st), fixtures.AS_OF
        )
        dispatch = {
            "dispatch_id": "CSD-RUNNER-TEST",
            "as_of_date": fixtures.AS_OF,
            **prompts,
        }
        st["candidate_screen_dispatches"] = [{
            "dispatch_id": dispatch["dispatch_id"],
            "as_of_date": fixtures.AS_OF,
            "candidate_seed_ids": dispatch["candidate_seed_ids"],
            "prompt_sha256": {
                role: hashlib.sha256(dispatch[f"{role}_prompt"].encode("utf-8")).hexdigest()
                for role in ("analyst", "skeptic")
            },
        }]
        results = {
            "analyst": {
                "invocation_id": "runner-analyst",
                "process_id": 2001,
                "exit_code": 0,
                "timed_out": False,
                "elapsed_seconds": 1.0,
                "prompt_sha256": st["candidate_screen_dispatches"][0]["prompt_sha256"]["analyst"],
                "payload_sha256": candidate_screen_engine.payload_sha256(analyst),
                "parse_error": "",
            },
            "skeptic": {
                "invocation_id": "runner-skeptic",
                "process_id": 2002,
                "exit_code": 0,
                "timed_out": False,
                "elapsed_seconds": 1.2,
                "prompt_sha256": st["candidate_screen_dispatches"][0]["prompt_sha256"]["skeptic"],
                "payload_sha256": candidate_screen_engine.payload_sha256(skeptic),
                "parse_error": "",
            },
        }
        receipt = runner.build_receipt(dispatch, results)
        validated = candidate_screen_engine.validate_isolation_receipt(
            st, receipt, analyst, skeptic, fixtures.AS_OF
        )
        self.assertEqual(validated["status"], "verified")
        self.assertTrue(receipt["receipt_id"].startswith("ISR-"))

        forged = json.loads(json.dumps(receipt))
        forged["roles"]["analyst"]["payload_sha256"] = "0" * 64
        forged["receipt_id"] = candidate_screen_engine.isolation_receipt_id(forged)
        rejected = candidate_screen_engine.validate_isolation_receipt(
            st, forged, analyst, skeptic, fixtures.AS_OF
        )
        self.assertEqual(rejected["status"], "invalid")
        self.assertIn("isolation_receipt_analyst_payload_hash_mismatch", rejected["blockers"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
