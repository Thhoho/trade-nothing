#!/usr/bin/env python3
import copy
import hashlib
import json
import unittest

import deepthink_orchestrator_v2
import research_start_packet


def fixture_packet():
    packet = {
        "schema_version": research_start_packet.SCHEMA_VERSION,
        "packet_id": "RSP-20260715-ABCDEF123456",
        "source_system": "tradenothing-next",
        "created_at": "2026-07-15T00:00:00Z",
        "question": {
            "topic": "AI power infrastructure",
            "decision_question": "Which assets have an unpriced catalyst?",
            "question_type": "UNIVERSE_SEARCH",
            "horizon": "6-12M",
            "as_of_date": "2026-07-15",
            "universe": "listed power assets",
        },
        "lesson_context": [{
            "lesson_id": 7,
            "source_review_id": 3,
            "title_snapshot": "Separate truth from pricing",
            "body_snapshot": "Test whether the market already prices the mechanism.",
            "applies_to_snapshot": "pricing",
            "activated_at": "2026-07-15T00:00:00Z",
            "activation_reason_snapshot": "Human approved the reusable constraint.",
            "selection_reason": "The new question can repeat the same category error.",
        }],
        "inheritance_policy": {
            "prior_verdict": False,
            "support_scores": False,
            "candidate_state": False,
            "actionability": False,
            "prior_evidence": False,
            "allowed_context": [
                "question_contract",
                "human_selected_active_lesson_snapshots",
            ],
        },
    }
    digest = hashlib.sha256(
        research_start_packet.canonical_json(packet).encode("utf-8")
    ).hexdigest()
    packet["integrity"] = {
        "schema_version": research_start_packet.INTEGRITY_SCHEMA,
        "algorithm": "sha256",
        "payload_sha256": digest,
        "claim": "human_selected_active_lessons_only_no_state_inheritance",
    }
    return packet


def first_run_packet():
    packet = fixture_packet()
    packet["lesson_context"] = []
    packet["inheritance_policy"]["allowed_context"] = ["question_contract"]
    payload = {key: value for key, value in packet.items() if key != "integrity"}
    packet["integrity"]["payload_sha256"] = hashlib.sha256(
        research_start_packet.canonical_json(payload).encode("utf-8")
    ).hexdigest()
    return packet


class ResearchStartPacketTests(unittest.TestCase):
    def test_valid_packet_becomes_bounded_framing_context(self):
        context = research_start_packet.framing_context(fixture_packet())
        self.assertEqual(context["question"]["question_type"], "UNIVERSE_SEARCH")
        self.assertEqual(context["lesson_constraints"][0]["lesson_id"], 7)
        self.assertNotIn("prior_verdict", context)
        self.assertNotIn("prior_evidence", context)

    def test_first_run_without_lessons_keeps_only_the_question_contract(self):
        packet = first_run_packet()
        context = research_start_packet.framing_context(packet)
        self.assertEqual(context["lesson_constraints"], [])
        self.assertEqual(
            packet["inheritance_policy"]["allowed_context"],
            ["question_contract"],
        )

        widened = first_run_packet()
        widened["inheritance_policy"]["allowed_context"].append(
            "human_selected_active_lesson_snapshots"
        )
        payload = {key: value for key, value in widened.items() if key != "integrity"}
        widened["integrity"]["payload_sha256"] = hashlib.sha256(
            research_start_packet.canonical_json(payload).encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "allowed_context"):
            research_start_packet.validate_packet(widened)

    def test_tamper_and_state_inheritance_are_rejected(self):
        tampered = fixture_packet()
        tampered["lesson_context"][0]["body_snapshot"] = "changed"
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            research_start_packet.validate_packet(tampered)
        stateful = fixture_packet()
        stateful["verdict"] = {"edge_state": "EDGE_FOUND"}
        with self.assertRaisesRegex(ValueError, "unexpected top-level fields"):
            research_start_packet.validate_packet(stateful)

    def test_orchestrator_frame_consumes_packet_as_constraint(self):
        packet = fixture_packet()
        output = deepthink_orchestrator_v2.cmd_frame("AI power infrastructure", packet)
        self.assertEqual(output["status"], "need_framing")
        self.assertEqual(output["research_start_context"]["packet_id"], packet["packet_id"])
        self.assertIn("not evidence", output["framer_prompt"])
        self.assertIn("research_start_binding", output["framer_prompt"])
        mismatch = deepthink_orchestrator_v2.cmd_frame("different topic", packet)
        self.assertEqual(mismatch["status"], "start_packet_rejected")

    def test_init_requires_packet_and_exact_frame_binding(self):
        packet = fixture_packet()
        frame = {
            "decision_question": packet["question"]["decision_question"],
            "question_type": packet["question"]["question_type"],
            "horizon": packet["question"]["horizon"],
            "as_of_date": packet["question"]["as_of_date"],
            "research_start_binding": {
                "packet_id": packet["packet_id"],
                "payload_sha256": packet["integrity"]["payload_sha256"],
            },
        }
        missing = deepthink_orchestrator_v2.cmd_init(
            packet["question"]["topic"], frame, start_packet=None
        )
        self.assertEqual(missing["status"], "start_packet_rejected")
        changed = copy.deepcopy(frame)
        changed["research_start_binding"]["payload_sha256"] = "0" * 64
        rejected = deepthink_orchestrator_v2.cmd_init(
            packet["question"]["topic"], changed, start_packet=packet
        )
        self.assertEqual(rejected["status"], "start_packet_rejected")


if __name__ == "__main__":
    unittest.main()
