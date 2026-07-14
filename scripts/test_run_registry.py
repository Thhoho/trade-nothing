#!/usr/bin/env python3
"""Offline tests for immutable run identity and stage envelopes."""
import json
import os
import tempfile
import unittest
from unittest import mock

import run_registry
import utils
from utils import save_json


class RunRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_scratch = os.environ.get("TRADE_NOTHING_SCRATCH_DIR")
        self.old_state = os.environ.pop("TRADE_NOTHING_STATE_PATH", None)
        self.old_run = os.environ.pop("TRADE_NOTHING_RUN_ID", None)
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
        self.tmp.cleanup()

    def test_run_id_owns_state_path_and_rejects_topic_drift(self):
        manifest = run_registry.create_manifest("Exact topic")
        self.assertTrue(manifest["run_id"].startswith("RUN-"))
        self.assertIn(manifest["run_id"], manifest["state_path"])
        resolved = run_registry.resolve_context(run_id=manifest["run_id"])
        self.assertEqual(resolved["topic"], "Exact topic")
        with self.assertRaisesRegex(ValueError, "topic_run_mismatch"):
            run_registry.resolve_context(
                run_id=manifest["run_id"], topic="Exact topic?"
            )

    def test_adopt_existing_state_without_renaming_it(self):
        path = os.path.join(self.tmp.name, "v2-state", "legacy.json")
        save_json(path, {"topic": "Legacy exact topic", "rounds": []})
        manifest = run_registry.adopt_manifest("", path)
        self.assertEqual(manifest["topic"], "Legacy exact topic")
        self.assertEqual(manifest["state_path"], path)
        self.assertEqual(manifest["stage"], "adopted")

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

    def test_manifest_read_does_not_attempt_advisory_write_lock(self):
        manifest = run_registry.create_manifest("Read-only status")
        with mock.patch.object(
            utils.CrossPlatformFileLock, "acquire", side_effect=AssertionError("must not lock")
        ) as acquire:
            loaded = run_registry.load_manifest(manifest["run_id"])
        self.assertEqual(loaded["topic"], "Read-only status")
        self.assertFalse(acquire.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
