#!/usr/bin/env python3
"""Offline failure-injection tests for resumable deepthink2 host dispatch."""
import os
import tempfile
import unittest
from unittest import mock

import deepthink_host_runner as runner
import deepthink_orchestrator_v2 as orchestrator
import run_registry


def frame():
    return {
        "decision_question": "test", "horizon": "3-6M", "as_of_date": "2026-07-14",
        "question_type": "CONJUNCTIVE",
        "logic_graph": {
            "root_id": "Q1",
            "nodes": [
                {"id": "Q1", "node_type": "QUESTION", "label": "test"},
                {"id": "C1", "node_type": "CRUX", "label": "c1"},
                {"id": "C2", "node_type": "CRUX", "label": "c2"},
            ],
            "edges": [
                {"from": "C1", "to": "Q1", "relation": "REQUIRED_FOR"},
                {"from": "C2", "to": "Q1", "relation": "REQUIRED_FOR"},
            ],
        },
        "unit_of_analysis": "test assets",
        "thesis_seed": "test premise may reveal an edge",
        "premise_audit": [{
            "id": "P1", "claim": "seed premise", "status": "HYPOTHESIS",
            "as_of": "UNKNOWN", "source_url": None,
            "required_primary_source": "issuer filing", "use": "scope",
        }],
        "candidate_cruxes": [
            {"id": "C1", "label": "c1", "logic_role": "THESIS_HINGE",
             "definition": "d1", "monitor_anchor": "m1", "falsifier": "f1",
             "catalyst_window": {"event": "e1", "expected_by": "2026-10-31",
                                 "date_status": "REVIEW_CHECKPOINT", "basis_claim_id": "P1"}},
            {"id": "C2", "label": "c2", "logic_role": "THESIS_HINGE",
             "definition": "d2", "monitor_anchor": "m2", "falsifier": "f2",
             "catalyst_window": {"event": "e2", "expected_by": "2026-12-31",
                                 "date_status": "REVIEW_CHECKPOINT", "basis_claim_id": "P1"}},
        ],
        "no_edge_precheck": {"is_researchable": True, "basis_type": "TESTABILITY",
                             "basis_claim_ids": ["P1"], "reason": "observable"},
        "suggested_max_rounds": 3,
    }


def result(role, prompt, payload=None, *, resource_exhausted=False):
    return {
        "role": role,
        "invocation_id": f"{role}-test",
        "process_id": 100 if role == "detective" else 101,
        "exit_code": 0 if payload is not None else 1,
        "timed_out": False,
        "elapsed_seconds": 1.0,
        "prompt_sha256": runner._prompt_hash(prompt),
        "payload": payload,
        "payload_sha256": run_registry.canonical_json_hash(payload) if payload else "",
        "parse_error": "" if payload is not None else "failed",
        "resource_exhausted": resource_exhausted,
        "error_code": "resource_exhausted_429" if resource_exhausted else "",
    }


class HostRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_scratch = os.environ.get("TRADE_NOTHING_SCRATCH_DIR")
        self.old_state = os.environ.pop("TRADE_NOTHING_STATE_PATH", None)
        self.old_run = os.environ.pop("TRADE_NOTHING_RUN_ID", None)
        self.old_evolution = os.environ.get("TRADE_NOTHING_EVOLUTION_PATH")
        os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.tmp.name
        os.environ["TRADE_NOTHING_EVOLUTION_PATH"] = os.path.join(self.tmp.name, "missing.md")
        self.context = run_registry.create_manifest("Stable run topic")
        run_registry.bind_context(self.context)
        initialized = orchestrator.cmd_init(
            self.context["topic"], frame(), runtime_isolation="verified"
        )
        self.assertEqual(initialized["status"], "dispatch_subagents")

    def tearDown(self):
        for name, value in (
            ("TRADE_NOTHING_SCRATCH_DIR", self.old_scratch),
            ("TRADE_NOTHING_STATE_PATH", self.old_state),
            ("TRADE_NOTHING_RUN_ID", self.old_run),
            ("TRADE_NOTHING_EVOLUTION_PATH", self.old_evolution),
        ):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmp.cleanup()

    def test_permission_bypass_is_explicit(self):
        safe = runner._command("agy", "p", 60)
        unsafe = runner._command("agy", "p", 60, allow_agent_tools=True)
        self.assertNotIn("--dangerously-skip-permissions", safe)
        self.assertIn("--dangerously-skip-permissions", unsafe)

    def test_429_resume_reuses_successful_detective_and_only_runs_missing_roles(self):
        state = orchestrator._load(self.context["topic"])
        prompts = orchestrator.dispatch_prompts(state, 1)
        det_payload = {"evidence_chain": [{"claim_node": "det", "source": "source"}]}
        inq_payload = {"lethal_attack_vectors": [{"attack": "inq", "evidence_audit": "source"}]}
        detective_record = result("detective", prompts["detective_prompt"], det_payload)
        checkpoint = {
            "prompt_sha256": {
                "detective": runner._prompt_hash(prompts["detective_prompt"]),
                "inquisitor": runner._prompt_hash(prompts["inquisitor_prompt"]),
            },
            "roles": {"detective": detective_record},
        }
        run_registry.save_checkpoint(self.context["run_id"], "round-1", checkpoint)

        with mock.patch.object(
            runner, "_run_role",
            return_value=result(
                "inquisitor", prompts["inquisitor_prompt"], None,
                resource_exhausted=True,
            ),
        ) as failed_call:
            paused = runner.execute_round(
                self.context, agy_bin="agy", timeout_seconds=60
            )
        self.assertEqual(paused["status"], "paused_runtime_failure")
        self.assertEqual(paused["result"]["missing_roles"], ["inquisitor"])
        self.assertEqual(failed_call.call_count, 1)

        calls = []
        def recovered(role, prompt, agy_bin, timeout_seconds, allow_agent_tools=False,
                      workdir=""):
            calls.append(role)
            if role == "inquisitor":
                return result(role, prompt, inq_payload)
            judge_payload = {
                "round": 1,
                "crux_signals": {
                    "C1": {"signal": 0, "rationale": "insufficient", "citations": []},
                    "C2": {"signal": 0, "rationale": "insufficient", "citations": []},
                },
                "new_cruxes": [],
            }
            return result(role, prompt, judge_payload)

        with mock.patch.object(runner, "_run_role", side_effect=recovered):
            resumed = runner.execute_round(
                self.context, agy_bin="agy", timeout_seconds=60
            )
        self.assertNotEqual(resumed["status"], "paused_runtime_failure")
        self.assertEqual(calls, ["inquisitor", "judge"])
        self.assertEqual(len(orchestrator._load(self.context["topic"])["rounds"]), 1)
        stored = run_registry.load_checkpoint(self.context["run_id"], "round-1")
        self.assertTrue(stored["submitted"])
        self.assertEqual(stored["roles"]["detective"]["payload"], det_payload)

        self.assertEqual(
            run_registry.load_checkpoint(self.context["run_id"], "round-1")["submit_result"],
            resumed["result"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
