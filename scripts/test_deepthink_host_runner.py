#!/usr/bin/env python3
"""Offline failure-injection tests for resumable deepthink2 host dispatch."""
import os
import json
import tempfile
import unittest
from unittest import mock

import deepthink_host_runner as runner
import deepthink_orchestrator_v2 as orchestrator
import process_control
import run_registry


def evidence_plan(crux_id):
    return [
        {"plan_id": f"SP-{crux_id}-1", "publisher_class": "ISSUER_OR_FILING",
         "target_claim": f"issuer anchor {crux_id}", "search_query": f"issuer {crux_id}"},
        {"plan_id": f"SP-{crux_id}-2", "publisher_class": "REGULATOR_OR_OFFICIAL_DATASET",
         "target_claim": f"official anchor {crux_id}", "search_query": f"official {crux_id}"},
    ]


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
             "evidence_plan": evidence_plan("C1"),
             "catalyst_window": {"event": "e1", "expected_by": "2026-10-31",
                                 "date_status": "REVIEW_CHECKPOINT", "basis_claim_id": "P1"}},
            {"id": "C2", "label": "c2", "logic_role": "THESIS_HINGE",
             "definition": "d2", "monitor_anchor": "m2", "falsifier": "f2",
             "evidence_plan": evidence_plan("C2"),
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
        self.old_purpose = os.environ.pop("TRADE_NOTHING_RUN_PURPOSE", None)
        self.old_evolution = os.environ.get("TRADE_NOTHING_EVOLUTION_PATH")
        os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.tmp.name
        os.environ["TRADE_NOTHING_EVOLUTION_PATH"] = os.path.join(self.tmp.name, "missing.md")
        self.context = run_registry.create_manifest(
            "Stable run topic", run_purpose="PRODUCTION_RESEARCH"
        )
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
            ("TRADE_NOTHING_RUN_PURPOSE", self.old_purpose),
            ("TRADE_NOTHING_EVOLUTION_PATH", self.old_evolution),
        ):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.tmp.cleanup()

    def test_initialized_state_freezes_manifest_run_purpose(self):
        state = orchestrator._load(self.context["topic"])
        self.assertEqual(state["runtime"]["run_purpose"], "PRODUCTION_RESEARCH")
        os.environ["TRADE_NOTHING_RUN_PURPOSE"] = "CONTROLLED_FIXTURE"
        with self.assertRaisesRegex(ValueError, "run_purpose_drift"):
            orchestrator._save(self.context["topic"], state)
        os.environ["TRADE_NOTHING_RUN_PURPOSE"] = "PRODUCTION_RESEARCH"

    def test_permission_bypass_is_explicit(self):
        safe = runner._command("agy", "p", 60)
        unsafe = runner._command("agy", "p", 60, allow_agent_tools=True)
        self.assertNotIn("--dangerously-skip-permissions", safe)
        self.assertIn("--dangerously-skip-permissions", unsafe)

        claude_safe = runner._command(
            "claude", "p", 60, host_runtime="claude-code"
        )
        claude_unsafe = runner._command(
            "claude", "p", 60, allow_agent_tools=True,
            host_runtime="claude-code",
        )
        self.assertIn("--output-format", claude_safe)
        self.assertIn("--json-schema", claude_safe)
        self.assertIn("--no-session-persistence", claude_safe)
        self.assertNotIn("--dangerously-skip-permissions", claude_safe)
        self.assertIn("--dangerously-skip-permissions", claude_unsafe)

    def test_claude_code_result_envelope_returns_structured_payload(self):
        role_payload = {"crux_evidence": [], "landscape_findings": []}
        envelope = {
            "type": "result", "subtype": "success", "is_error": False,
            "structured_output": role_payload,
        }
        self.assertEqual(
            runner._parse_json_output(
                json.dumps(envelope), host_runtime="claude-code"
            ),
            role_payload,
        )
        text_envelope = {
            "type": "result", "is_error": False,
            "result": json.dumps(role_payload),
        }
        self.assertEqual(
            runner._parse_json_output(
                json.dumps(text_envelope), host_runtime="claude-code"
            ),
            role_payload,
        )

    def test_runtime_resolution_respects_explicit_claude_binary(self):
        self.assertEqual(
            runner._resolve_host_runtime("auto", "/opt/bin/claude"),
            "claude-code",
        )
        self.assertEqual(
            runner._resolve_host_runtime("antigravity", "/opt/bin/claude"),
            "antigravity",
        )

    def test_claude_child_does_not_inherit_parent_session_markers(self):
        markers = {
            "CLAUDECODE": "1",
            "CLAUDE_CODE_ENTRYPOINT": "cli",
            "CLAUDE_CODE_SESSION_ID": "parent-session",
        }
        with mock.patch.dict(os.environ, {**markers, "KEEP_ME": "yes"}, clear=False):
            child = runner._host_environment("claude-code")
            antigravity = runner._host_environment("antigravity")
        self.assertEqual(child["KEEP_ME"], "yes")
        for name in markers:
            self.assertNotIn(name, child)
            self.assertEqual(antigravity[name], markers[name])

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
                      workdir="", host_runtime="antigravity"):
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
            run_registry.load_result_artifact(resumed),
        )

    def test_prompt_drift_discards_only_failed_payload_free_checkpoint(self):
        run_registry.save_checkpoint(self.context["run_id"], "round-1", {
            "prompt_sha256": {"detective": "old", "inquisitor": "old"},
            "roles": {
                "detective": {"exit_code": 1, "payload": None, "payload_sha256": ""},
                "inquisitor": {"exit_code": 1, "payload": None, "payload_sha256": ""},
            },
        })
        calls = []
        def successful(role, prompt, agy_bin, timeout_seconds, allow_agent_tools=False,
                       workdir="", host_runtime="antigravity"):
            calls.append(role)
            if role == "detective":
                payload = {"evidence_chain": [{"claim_node": "det", "source": "source"}]}
            elif role == "inquisitor":
                payload = {"lethal_attack_vectors": [{"attack": "inq", "evidence_audit": "s"}]}
            else:
                payload = {"round": 1, "crux_signals": {
                    "C1": {"signal": 0, "rationale": "none", "citations": []},
                    "C2": {"signal": 0, "rationale": "none", "citations": []},
                }, "new_cruxes": []}
            return result(role, prompt, payload)

        with mock.patch.object(runner, "_run_role", side_effect=successful):
            resumed = runner.execute_round(
                self.context, agy_bin="agy", timeout_seconds=60
            )
        self.assertNotEqual(resumed["status"], "paused_runtime_failure")
        self.assertEqual(calls, ["detective", "inquisitor", "judge"])
        stored = run_registry.load_checkpoint(self.context["run_id"], "round-1")
        self.assertEqual(stored["superseded_prompt_sha256"], {
            "detective": "old", "inquisitor": "old",
        })

    def test_judge_uses_its_shorter_bounded_timeout(self):
        observed = {}

        def successful(role, prompt, host_bin, timeout_seconds, allow_agent_tools=False,
                       workdir="", host_runtime="antigravity"):
            observed[role] = timeout_seconds
            if role == "detective":
                payload = {"evidence_chain": []}
            elif role == "inquisitor":
                payload = {"lethal_attack_vectors": []}
            else:
                payload = {"round": 1, "crux_signals": {
                    "C1": {"signal": 0, "rationale": "none", "citations": []},
                    "C2": {"signal": 0, "rationale": "none", "citations": []},
                }, "new_cruxes": []}
            return result(role, prompt, payload)

        with mock.patch.object(runner, "_run_role", side_effect=successful):
            runner.execute_round(
                self.context,
                agy_bin="agy",
                timeout_seconds=480,
                judge_timeout_seconds=240,
            )
        self.assertEqual(observed["detective"], 480)
        self.assertEqual(observed["inquisitor"], 480)
        self.assertEqual(observed["judge"], 240)

    def test_terminal_round_statuses_always_materialize_report(self):
        for terminal_status, stopped_reason in (
            ("ready_for_report", "CONVERGED"),
            ("blocked_max_rounds", "MAX_ROUNDS_REACHED"),
            ("dispatch_candidate_screeners", "CANDIDATE_SCREEN_PENDING"),
        ):
            with self.subTest(status=terminal_status), mock.patch.object(
                runner,
                "execute_round",
                return_value={
                    "status": terminal_status,
                    "next_action": "terminal next action",
                    "result": {"status": terminal_status},
                },
            ), mock.patch.object(
                orchestrator,
                "cmd_report",
                return_value={
                    "status": "report_data_ready",
                    "topic": self.context["topic"],
                    "instruction": "consume report",
                    "report_markdown": "# Fixture report",
                },
            ) as report_call:
                outcome = runner.continue_run(
                    self.context,
                    agy_bin="agy",
                    timeout_seconds=60,
                    round_budget=1,
                    continue_screen=False,
                )
            self.assertEqual(report_call.call_count, 1)
            self.assertEqual(outcome["status"], "report_data_ready")
            artifact = run_registry.load_result_artifact(outcome)
            self.assertEqual(artifact["runner_terminal_status"], terminal_status)
            self.assertEqual(artifact["stopped_reason"], stopped_reason)

    def test_round_budget_exhaustion_delivers_exploratory_report(self):
        with mock.patch.object(
            runner,
            "execute_round",
            return_value={
                "status": "dispatch_subagents",
                "next_action": "continue",
                "result": {"status": "dispatch_subagents"},
            },
        ), mock.patch.object(
            orchestrator,
            "cmd_report",
            return_value={
                "status": "report_data_ready",
                "topic": self.context["topic"],
                "instruction": "consume report",
                "report_markdown": "# Exploratory fixture report",
            },
        ):
            outcome = runner.continue_run(
                self.context,
                agy_bin="agy",
                timeout_seconds=60,
                round_budget=1,
            )
        artifact = run_registry.load_result_artifact(outcome)
        self.assertEqual(artifact["runner_terminal_status"], "paused_round_budget")
        self.assertEqual(artifact["stopped_reason"], "ROUND_BUDGET_EXHAUSTED")
        self.assertIn("resume --run-id", artifact["instruction"])

    def test_method_drift_status_is_structured_and_read_only(self):
        path = run_registry.manifest_path(self.context["run_id"])
        with open(path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["method_identity"]["contract_sha256"] = "0" * 64
        from utils import save_json
        save_json(path, manifest)

        outcome = runner._method_drift_status(self.context["run_id"])

        self.assertEqual(outcome["status"], "paused_method_contract_drift")
        self.assertFalse(outcome["result"]["resumable"])
        self.assertEqual(outcome["result"]["reason"], "method_contract_drift")
        self.assertEqual(
            outcome["result"]["pinned_method_identity"]["contract_sha256"],
            "0" * 64,
        )


class ProcessControlTests(unittest.TestCase):
    def test_timeout_kills_entire_isolated_process_group(self):
        process = mock.Mock(pid=4321)
        process.poll.return_value = None
        with mock.patch.object(process_control.os, "killpg") as killpg:
            mode = process_control.kill_process_group(process)
        killpg.assert_called_once_with(4321, process_control.signal.SIGKILL)
        process.kill.assert_not_called()
        self.assertEqual(mode, "process_group")

    def test_process_group_failure_falls_back_to_direct_child(self):
        process = mock.Mock(pid=4321)
        process.poll.return_value = None
        with mock.patch.object(
            process_control.os, "killpg", side_effect=OSError("unsupported")
        ):
            mode = process_control.kill_process_group(process)
        process.kill.assert_called_once_with()
        self.assertEqual(mode, "direct_process_fallback")


if __name__ == "__main__":
    unittest.main(verbosity=2)
