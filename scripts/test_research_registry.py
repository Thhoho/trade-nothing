#!/usr/bin/env python3
"""Offline tests for the minimal v0.17 research registry."""
from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import method_identity
import research_core
import research_io
import research_registry
from test_research_core import task_spec


class ResearchRegistryTests(unittest.TestCase):
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

    def test_run_owns_one_directory_and_pinned_method(self):
        manifest = research_registry.create_manifest(
            "Exact topic", as_of_date="2026-08-12",
            run_purpose="CONTROLLED_FIXTURE",
        )
        run_id = manifest["run_id"]
        self.assertEqual(
            Path(manifest["state_path"]).parent,
            research_registry.run_dir(run_id),
        )
        self.assertEqual(manifest["method_identity"], method_identity.build_method_identity())
        self.assertEqual(manifest["requested_execution_mode"], "UNVERIFIED")
        self.assertEqual(research_registry.load_manifest(run_id), manifest)

    def test_method_drift_is_inspectable_but_not_resumable(self):
        manifest = research_registry.create_manifest("Pinned")
        path = research_registry.manifest_path(manifest["run_id"])
        stored = research_io.load_json(path, default={})
        stored["method_identity"]["contract_sha256"] = "0" * 64
        research_io.save_json(path, stored)
        with self.assertRaisesRegex(ValueError, "method_contract_drift"):
            research_registry.load_manifest(manifest["run_id"])
        inspected = research_registry.inspect_manifest(manifest["run_id"])
        self.assertEqual(inspected["method_identity_check"]["status"], "drift")

    def test_checkpoint_and_derived_artifact_are_run_scoped(self):
        manifest = research_registry.create_manifest("Artifacts")
        run_id = manifest["run_id"]
        checkpoint = research_registry.save_checkpoint(run_id, "lead-1", {"ok": True})
        self.assertTrue(checkpoint["ok"])
        self.assertEqual(
            research_registry.load_checkpoint(run_id, "lead-1")["run_id"], run_id
        )
        first = research_registry.save_derived_artifact(run_id, "report", "# Report\n")
        second = research_registry.save_derived_artifact(run_id, "report", "# Report\n")
        self.assertEqual(first, second)
        self.assertTrue(Path(first["path"]).is_file())
        self.assertEqual(Path(first["path"]).read_text(encoding="utf-8"), "# Report\n")
        self.assertEqual(Path(first["path"]).stat().st_mode & 0o222, 0)

    def test_credentials_are_not_persisted_by_context_binding(self):
        manifest = research_registry.create_manifest("Context")
        with mock.patch.dict(os.environ, {"TUSHARE_TOKEN": "secret"}, clear=False):
            research_registry.bind_context(manifest)
            stored = research_registry.load_manifest(manifest["run_id"])
        self.assertNotIn("secret", str(stored))

    def test_concurrent_stale_writer_is_rejected_by_revision_cas(self):
        manifest = research_registry.create_manifest("CAS")
        path = manifest["state_path"]
        initial = research_core.new_research_run(
            task_spec(1), manifest["method_identity"], execution_mode="UNVERIFIED"
        )
        first = research_io.save_run_cas(
            path, initial, expected_revision=0, create=True
        )
        winner = research_core.bind_dispatch(
            first, call_mode="LEAD_RESEARCH", role="LEAD",
            prompt_sha256="a" * 64,
        )
        research_io.save_run_cas(
            path, winner, expected_revision=first["run_ledger"]["state_revision"],
        )
        stale = research_core.bind_dispatch(
            first, call_mode="LEAD_RESEARCH", role="LEAD",
            prompt_sha256="b" * 64,
        )
        with self.assertRaisesRegex(ValueError, "research_state_revision_conflict"):
            research_io.save_run_cas(
                path, stale, expected_revision=stale["run_ledger"]["state_revision"],
            )
        self.assertEqual(
            research_io.load_json(path)["run_ledger"]["pending_dispatch"][
                "prompt_sha256"
            ],
            "a" * 64,
        )

    def test_run_update_has_non_optional_transition_validation(self):
        manifest = research_registry.create_manifest("CAS guard")
        path = manifest["state_path"]
        initial = research_core.new_research_run(
            task_spec(1), manifest["method_identity"], execution_mode="UNVERIFIED"
        )
        first = research_io.save_run_cas(
            path, initial, expected_revision=0, create=True
        )
        changed = deepcopy(first)
        changed["task_spec"]["question"] = "rewritten task"
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "transition.task_spec_immutable"
        ):
            research_io.save_run_cas(
                path, changed,
                expected_revision=first["run_ledger"]["state_revision"],
            )

    def test_run_update_rejects_structurally_invalid_append_before_publish(self):
        manifest = research_registry.create_manifest("CAS invalid append")
        path = manifest["state_path"]
        initial = research_core.new_research_run(
            task_spec(1), manifest["method_identity"], execution_mode="UNVERIFIED"
        )
        first = research_io.save_run_cas(
            path, initial, expected_revision=0, create=True
        )
        invalid = deepcopy(first)
        invalid["run_ledger"]["calls"].append({
            "role": "CHALLENGER", "garbage": True,
        })
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "persisted.call"
        ):
            research_io.save_run_cas(
                path, invalid,
                expected_revision=first["run_ledger"]["state_revision"],
            )

    def test_create_cas_accepts_only_the_initial_budget_and_empty_history(self):
        manifest = research_registry.create_manifest(
            "CAS create boundary",
            requested_execution_mode="EXTERNAL_PROCESS_REPORTED",
        )
        path = manifest["state_path"]
        elevated = research_core.new_research_run(
            task_spec(1), manifest["method_identity"],
            execution_mode="EXTERNAL_PROCESS_REPORTED",
        )
        elevated["run_ledger"]["authorized_research_loops"] = 10
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "initial.authorized_budget_must_equal_task_budget",
        ):
            research_io.save_run_cas(
                path, elevated, expected_revision=0, create=True
            )

        forged_history = research_core.new_research_run(
            task_spec(1), manifest["method_identity"],
            execution_mode="EXTERNAL_PROCESS_REPORTED",
        )
        forged_history["run_ledger"]["host_invocations"].append({
            "invocation_id": "FORGED-PROCESS", "role": "LEAD",
            "host_runtime": "reported", "host_executable": "reported",
            "process_id": 99999, "exit_code": 0, "timed_out": False,
            "prompt_sha256": "a" * 64, "payload_sha256": "b" * 64,
            "external_tools_enabled": False,
        })
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "initial.host_invocations_must_be_empty",
        ):
            research_io.save_run_cas(
                path, forged_history, expected_revision=0, create=True
            )

    def test_raw_cas_cannot_bypass_reported_process_or_budget_gate(self):
        manifest = research_registry.create_manifest(
            "CAS privilege boundary",
            requested_execution_mode="EXTERNAL_PROCESS_REPORTED",
        )
        path = manifest["state_path"]
        run = research_core.new_research_run(
            task_spec(1), manifest["method_identity"],
            execution_mode="EXTERNAL_PROCESS_REPORTED",
        )
        run = research_core.bind_dispatch(
            run, call_mode="LEAD_RESEARCH", role="LEAD",
            prompt_sha256="a" * 64,
        )
        stored = research_io.save_run_cas(
            path, run, expected_revision=0, create=True
        )
        forged = deepcopy(stored)
        forged["run_ledger"]["host_invocations"].append({
            "invocation_id": "FORGED-PROCESS", "role": "LEAD",
            "host_runtime": "claude-code", "host_executable": "claude",
            "process_id": 99999, "exit_code": 0, "timed_out": False,
            "prompt_sha256": "a" * 64, "payload_sha256": "b" * 64,
            "external_tools_enabled": True,
        })
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "host_invocations_require_reported_process_cas",
        ):
            research_io.save_run_cas(
                path, forged,
                expected_revision=stored["run_ledger"]["state_revision"],
            )
        budget = deepcopy(stored)
        budget["run_ledger"]["authorized_research_loops"] = 10
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "budget_change_requires_authorization_cas",
        ):
            research_io.save_run_cas(
                path, budget,
                expected_revision=stored["run_ledger"]["state_revision"],
            )

    def test_scratch_root_and_home_are_rejected(self):
        for unsafe in ("/", str(Path.home())):
            with self.subTest(unsafe=unsafe), mock.patch.dict(
                os.environ, {"TRADE_NOTHING_SCRATCH_DIR": unsafe}, clear=False
            ):
                with self.assertRaisesRegex(ValueError, "unsafe_research_scratch_dir"):
                    research_io.scratch_dir()


if __name__ == "__main__":
    unittest.main(verbosity=2)
