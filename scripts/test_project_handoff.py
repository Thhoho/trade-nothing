#!/usr/bin/env python3
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import project_handoff
import method_identity


def fixture_state():
    verdict = {
        "edge_state": "NO_EDGE",
        "evidence_direction": "MIXED",
        "actionability": "MONITOR",
        "question_type": "CONJUNCTIVE",
        "reason_code": "FIXTURE",
    }
    return {
        "topic": "fixture",
        "decision_question": "Is this importable?",
        "question_type": "CONJUNCTIVE",
        "horizon": "3-6M",
        "logic_graph": {
            "root_id": "ROOT",
            "nodes": [{"id": "ROOT"}, {"id": "C1"}],
            "edges": [{"from": "ROOT", "to": "C1", "relation": "REQUIRES"}],
        },
        "landscape_map": {},
        "frame_contract": {"as_of_date": "2026-07-15"},
        "research_verdict": verdict,
        "last_convergence": {"decision": "converge", "reason": "fixture"},
        "decision_trace": [
            {"round": 1, "decision": "continue", "raw": "drop"},
            {
                "round": 2,
                "decision": "converge",
                "aggregation_rule": "WEAKEST_NECESSARY_CRUX",
                "research_verdict": verdict,
                "raw": "drop",
            },
        ],
        "cruxes": {
            "C1": {
                "label": "fixture crux",
                "definition": "fixture definition",
                "logic_role": "THESIS_HINGE",
                "status": "MONITORABLE",
                "p_history": [0.1, 0.2],
                "monitor_anchor": "fixture",
                "falsifier": "fixture falsifier",
                "catalyst_window": {},
                "best_bull": None,
                "best_bear": None,
                "citations": [],
                "private_reasoning": "drop",
            }
        },
        "opportunity_seeds": [],
        "candidate_screens": [],
        "claim_verifications": [],
        "runtime_contract": {"isolation_status": "verified"},
        "method_identity": method_identity.build_method_identity(),
        "research_start_context": {
            "packet_id": "RSP-20260715-ABCDEF123456",
            "payload_sha256": "a" * 64,
            "question": {"topic": "fixture"},
            "lesson_constraints": [{"lesson_id": 7, "title": "fixture"}],
            "use_policy": "framing only",
        },
        "runtime": {"run_id": "RUN-20260715-ABCDEF123456", "other": "drop"},
        "rounds": [{"detective": {"raw": "must not cross handoff"}}],
        "candidate_screen_dispatches": [{"prompt": "drop"}],
    }


class ProjectHandoffTests(unittest.TestCase):
    def test_handoff_is_deterministic_compact_and_checksummed(self):
        first = project_handoff.build_handoff(fixture_state())
        second = project_handoff.build_handoff(copy.deepcopy(fixture_state()))
        self.assertEqual(first, second)
        self.assertEqual(first["schema_version"], project_handoff.HANDOFF_SCHEMA)
        self.assertEqual(first["lesson_injections"], [])
        self.assertEqual(
            first["state"]["method_identity"], method_identity.build_method_identity()
        )
        self.assertNotIn("rounds", first["state"])
        self.assertNotIn("candidate_screen_dispatches", first["state"])
        self.assertNotIn("raw", first["state"]["decision_trace"][0])
        self.assertEqual(
            first["state"]["research_start_context"]["packet_id"],
            "RSP-20260715-ABCDEF123456",
        )
        self.assertEqual(first["state"]["cruxes"]["C1"]["p_history"], [0.2])
        expected = hashlib.sha256(
            project_handoff.canonical_json(first["state"]).encode("utf-8")
        ).hexdigest()
        self.assertEqual(first["handoff_integrity"]["state_sha256"], expected)

    def test_preflight_reports_all_legacy_blockers_without_rewriting_state(self):
        legacy = fixture_state()
        legacy.pop("question_type")
        legacy.pop("logic_graph")
        legacy["runtime"] = {"state_path": "/tmp/legacy.json"}
        legacy["runtime_contract"] = {"isolation_status": "unverified"}
        legacy["decision_trace"][-1].pop("aggregation_rule")
        legacy["decision_trace"][-1].pop("research_verdict")
        legacy.pop("research_verdict")
        legacy.pop("method_identity")
        legacy["decision_trace"][-1]["decision"] = "NO_EDGE / AVOID"

        assessment = project_handoff.preflight_handoff(legacy)
        codes = {item["code"] for item in assessment["blockers"]}
        warning_codes = {item["code"] for item in assessment["warnings"]}

        self.assertEqual(assessment["status"], "BLOCKED")
        self.assertFalse(assessment["exportable"])
        self.assertTrue(
            {
                "QUESTION_TYPE_INVALID",
                "LOGIC_GRAPH_INVALID",
                "LEGACY_AVOID_SEMANTICS",
                "THREE_AXIS_VERDICT_MISSING",
                "RUN_ID_INVALID",
                "METHOD_IDENTITY_MISSING",
            }.issubset(codes)
        )
        self.assertIn("RUNTIME_ISOLATION_NOT_VERIFIED", warning_codes)
        with self.assertRaisesRegex(ValueError, "handoff preflight blocked"):
            project_handoff.build_handoff(legacy)

    def test_writer_refuses_implicit_overwrite_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "state.json"
            output = root / "handoff.json"
            linked_output = root / "linked-handoff.json"
            source.write_text(json.dumps(fixture_state()), encoding="utf-8")
            output.write_text("existing", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "output already exists"):
                project_handoff.write_handoff(
                    project_handoff.build_handoff(fixture_state()), output
                )
            linked_output.symlink_to(source)
            with self.assertRaisesRegex(ValueError, "output symlink"):
                project_handoff.write_handoff(
                    project_handoff.build_handoff(fixture_state()), linked_output, force=True
                )
            self.assertEqual(json.loads(source.read_text(encoding="utf-8")), fixture_state())


if __name__ == "__main__":
    unittest.main()
