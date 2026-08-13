#!/usr/bin/env python3
"""Offline host-harness tests; no model process or network is invoked."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy
from unittest import mock

import research_core
import research_host_runner
import research_io
import research_loop
import research_registry
import process_control
from test_research_core import (
    challenge_source_check, complete_source_checks, evidence, lead_packet,
    snapshot, task_spec,
)


class ResearchHostRunnerTests(unittest.TestCase):
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

    def _started(self):
        spec = deepcopy(task_spec(1))
        spec["seed_evidence_items"] = [evidence()]
        spec["seed_source_checks"] = complete_source_checks()
        return research_loop.cmd_start(
            "受控宿主测试", spec, round_budget=1,
            run_purpose="CONTROLLED_FIXTURE",
            execution_mode="EXTERNAL_PROCESS_REPORTED",
        )

    @staticmethod
    def _valid_payload(run):
        observation = evidence("EV-PROCESS-OBS", impact="LOW")
        payload = lead_packet(run)
        payload["evidence_items"] = [observation]
        payload["source_checks"] = [challenge_source_check("EV-PROCESS-OBS")]
        payload["decision_snapshot"] = snapshot(
            run, extra_evidence_ids=["EV-PROCESS-OBS"]
        )
        return payload

    def test_one_valid_model_call_returns_ready_without_owning_the_loop(self):
        started = self._started()
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        payload = self._valid_payload(run)

        def fake_call(role, prompt, **_kwargs):
            return {
                "role": role,
                "invocation_id": "lead-process-1",
                "host_runtime": "claude-code",
                "host_executable": "claude",
                "process_id": 101,
                "exit_code": 0,
                "timed_out": False,
                "elapsed_seconds": 1.0,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "payload": payload,
                "payload_sha256": research_core.stable_hash(payload),
                "parse_error": "",
                "error_code": "",
                "diagnostic_excerpt": "",
                "diagnostic_sha256": "",
                "external_tools_enabled": True,
            }

        with mock.patch.object(
            research_host_runner.model_process_runtime,
            "run_json_call",
            side_effect=fake_call,
        ) as invoked:
            result = research_host_runner.run_one_request(
                started["run_id"], runtime="claude-code", allow_tools=True
            )
        self.assertEqual(result["status"], "ready_for_report")
        report = research_loop.cmd_report(started["run_id"])
        self.assertEqual(report["status"], "report_data_ready")
        self.assertEqual(
            report["rendering_mode"],
            "PURE_DECISION_SNAPSHOT_USER_AND_AUDIT",
        )
        self.assertEqual(invoked.call_count, 1)
        self.assertEqual(len(result["model_calls"]), 1)

    def test_external_process_record_is_reported_not_attested(self):
        started = self._started()
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        payload = self._valid_payload(run)
        fake = {
            "role": "LEAD",
            "invocation_id": "fake-process-record",
            "host_runtime": "caller-reported-runtime",
            "host_executable": "caller-reported-binary",
            "process_id": 99999,
            "exit_code": 0,
            "timed_out": False,
            "prompt_sha256": started["prompt_sha256"],
            "payload_sha256": research_core.stable_hash(payload),
            "external_tools_enabled": True,
        }
        self.assertFalse(hasattr(process_control, "attest_host_record"))
        self.assertFalse(hasattr(process_control, "host_record_attested"))
        registered = research_loop.cmd_register_host_invocation(
            started["run_id"], fake
        )
        self.assertEqual(registered["status"], "host_invocation_registered")
        result = research_loop.cmd_submit_lead(
            started["run_id"], payload, research_host_runner._receipt(fake)
        )
        self.assertEqual(result["status"], "ready_for_report")
        report = research_loop.cmd_report(started["run_id"])
        audit = Path(report["audit_report_path"]).read_text(encoding="utf-8")
        self.assertIn(
            "HOST_PROCESS / PROCESS_REPORTED / PROCESS_CONTEXT_REPORTED", audit
        )
        self.assertNotIn("PROCESS_ATTESTED", audit)

    def test_runtime_failure_is_recorded_once_and_not_retried(self):
        started = self._started()

        def failed_call(role, prompt, **_kwargs):
            return {
                "role": role,
                "invocation_id": "lead-process-failed",
                "host_runtime": "claude-code",
                "host_executable": "claude",
                "process_id": 102,
                "exit_code": 1,
                "timed_out": False,
                "elapsed_seconds": 0.2,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "payload": None,
                "payload_sha256": "",
                "parse_error": "",
                "error_code": "host_authentication_required",
                "diagnostic_excerpt": "authentication required",
                "diagnostic_sha256": "a" * 64,
                "external_tools_enabled": False,
            }

        with mock.patch.object(
            research_host_runner.model_process_runtime,
            "run_json_call",
            side_effect=failed_call,
        ) as invoked:
            result = research_host_runner.run_one_request(
                started["run_id"], runtime="claude-code"
            )
        self.assertEqual(result["status"], "runtime_failure_recorded")
        self.assertEqual(invoked.call_count, 1)
        status = research_loop.cmd_status(started["run_id"])
        self.assertEqual(status["delivery_state"]["next_call"], "REPORT")
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        self.assertEqual(len(run["run_ledger"]["failures"]), 1)
        self.assertNotIn("pending_dispatch", run["run_ledger"])
        retried = research_loop.cmd_authorize(started["run_id"], 0)
        self.assertEqual(retried["status"], "dispatch_model")
        self.assertEqual(retried["call_mode"], "LEAD_RESEARCH")
        self.assertEqual(
            retried["delivery_state"]["authorized_research_loops"], 1
        )

    def test_contract_rejection_stops_without_consuming_or_retrying(self):
        started = self._started()

        def invalid_call(role, prompt, **_kwargs):
            payload = {"unexpected": "parallel thesis"}
            return {
                "role": role,
                "invocation_id": "lead-process-invalid",
                "host_runtime": "claude-code",
                "host_executable": "claude",
                "process_id": 103,
                "exit_code": 0,
                "timed_out": False,
                "elapsed_seconds": 0.3,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "payload": payload,
                "payload_sha256": research_core.stable_hash(payload),
                "parse_error": "",
                "error_code": "",
                "diagnostic_excerpt": "",
                "diagnostic_sha256": "",
                "external_tools_enabled": True,
            }

        with mock.patch.object(
            research_host_runner.model_process_runtime,
            "run_json_call",
            side_effect=invalid_call,
        ) as invoked:
            result = research_host_runner.run_one_request(
                started["run_id"], runtime="claude-code", allow_tools=True
            )
        self.assertEqual(result["status"], "contract_rejected")
        self.assertEqual(invoked.call_count, 1)
        self.assertIn("lead.packet_fields_invalid", " ".join(result["errors"]))
        status = research_loop.cmd_status(started["run_id"])
        self.assertEqual(status["delivery_state"]["completed_research_loops"], 0)
        self.assertEqual(status["delivery_state"]["next_call"], "LEAD_RESEARCH")
        self.assertEqual(status["delivery_state"]["rejection_count"], 1)
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        self.assertNotIn("pending_dispatch", run["run_ledger"])
        resumed = research_loop.cmd_dispatch(started["run_id"])
        self.assertIn("last_contract_rejection", resumed["prompt"])
        self.assertIn("lead.packet_fields_invalid", resumed["prompt"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
