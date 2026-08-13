#!/usr/bin/env python3
"""Deterministic checks for the generic model-process adapter."""
from __future__ import annotations

import json
import os
import unittest
from unittest import mock

import model_process_runtime


class ModelProcessRuntimeTests(unittest.TestCase):
    def test_runtime_aliases_and_commands_are_explicit(self):
        self.assertEqual(model_process_runtime.normalize_runtime("claude"), "claude-code")
        self.assertEqual(model_process_runtime.normalize_runtime("agy"), "antigravity")
        command = model_process_runtime.command(
            "claude", "prompt", 60, runtime="claude-code", allow_tools=False
        )
        self.assertIn("--json-schema", command)
        self.assertNotIn("--dangerously-skip-permissions", command)
        enabled = model_process_runtime.command(
            "claude", "prompt", 60, runtime="claude-code", allow_tools=True
        )
        self.assertIn("--dangerously-skip-permissions", enabled)

    def test_claude_structured_result_is_unwrapped(self):
        payload = model_process_runtime.parse_json_output(json.dumps({
            "type": "result", "is_error": False,
            "structured_output": {"ok": True},
        }), runtime="claude-code")
        self.assertEqual(payload, {"ok": True})

    def test_child_environment_does_not_forward_research_credentials(self):
        with mock.patch.dict(os.environ, {
            "TUSHARE_TOKEN": "secret", "CLAUDE_CODE_SESSION_ID": "nested",
            "TRADE_NOTHING_STATE_PATH": "/tmp/private-run/state.json",
            "TRADE_NOTHING_RUN_ID": "RUN-PRIVATE",
            "SAFE_VALUE": "keep",
        }, clear=False):
            child = model_process_runtime.child_environment("claude-code")
        self.assertNotIn("TUSHARE_TOKEN", child)
        self.assertNotIn("CLAUDE_CODE_SESSION_ID", child)
        self.assertNotIn("TRADE_NOTHING_STATE_PATH", child)
        self.assertNotIn("TRADE_NOTHING_RUN_ID", child)
        self.assertEqual(child.get("SAFE_VALUE"), "keep")

    def test_diagnostics_redact_secrets_and_home(self):
        diagnostic = model_process_runtime._diagnostic(
            "TUSHARE_TOKEN=very-secret-value " + os.path.expanduser("~/private")
        )
        self.assertNotIn("very-secret-value", diagnostic)
        self.assertNotIn(os.path.expanduser("~"), diagnostic)

    def test_preflight_never_spends_a_hidden_model_call(self):
        with mock.patch.object(
            model_process_runtime, "run_json_call"
        ) as model_call, mock.patch.object(
            model_process_runtime.shutil, "which", return_value="/bin/sh"
        ):
            result = model_process_runtime.preflight("claude-code", "claude")
        self.assertEqual(result["status"], "runtime_preflight_ready")
        self.assertFalse(result["credential_probe_performed"])
        model_call.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
