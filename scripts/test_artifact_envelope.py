#!/usr/bin/env python3
import json
import os
import tempfile
import unittest

import artifact_envelope


class ArtifactEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_json_stays_off_envelope_and_requires_explicit_verified_read(self):
        payload = {"rows": [{"value": "x" * 1000} for _ in range(20)]}
        envelope = artifact_envelope.create_json_artifact(
            payload,
            artifact_path=os.path.join(self.tmp.name, "result.json"),
            artifact_kind="external-agent-result",
            producer="agy",
            summary={"record_count": 20, "headline": "completed"},
            next_action="review only decisive conflicts",
        )
        serialized = json.dumps(envelope)
        self.assertNotIn("x" * 100, serialized)
        self.assertLess(len(serialized.encode("utf-8")), artifact_envelope.MAX_ENVELOPE_BYTES)
        with self.assertRaisesRegex(ValueError, "explicit_artifact_read_required"):
            artifact_envelope.load_json(envelope, allowed_root=self.tmp.name)
        self.assertEqual(
            artifact_envelope.load_json(
                envelope, allowed_root=self.tmp.name, explicit=True
            ),
            payload,
        )

    def test_tampered_artifact_fails_closed(self):
        envelope = artifact_envelope.create_json_artifact(
            {"status": "ok"},
            artifact_path=os.path.join(self.tmp.name, "result.json"),
            artifact_kind="test",
            producer="fixture",
        )
        with open(envelope["artifact_path"], "w", encoding="utf-8") as handle:
            handle.write("{}")
        with self.assertRaisesRegex(ValueError, "artifact_(size|hash)_mismatch"):
            artifact_envelope.verify(envelope, allowed_root=self.tmp.name)

    def test_envelope_rejects_raw_payload_fields(self):
        with self.assertRaisesRegex(ValueError, "raw_field_forbidden"):
            artifact_envelope.create_json_artifact(
                {"safe": True},
                artifact_path=os.path.join(self.tmp.name, "result.json"),
                artifact_kind="test",
                producer="fixture",
                summary={"raw_output": "must not be copied"},
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
