#!/usr/bin/env python3
"""Integration tests for the v0.18 CLI-level research loop."""
from __future__ import annotations

from copy import deepcopy
import json
import hashlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import codex_research_receipt
import research_core
import research_io
import research_loop
import research_registry
from test_research_core import lead_packet, market_evidence, task_spec


class ResearchLoopIntegrationTests(unittest.TestCase):
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

    def _start(self, budget=1):
        return research_loop.cmd_start(
            "测试公司资本变化", task_spec(budget), round_budget=budget,
            run_purpose="CONTROLLED_FIXTURE", execution_mode="CONTROLLED_FIXTURE",
        )

    def test_start_binds_dispatch_submit_and_pure_report(self):
        started = self._start(1)
        self.assertEqual(started["status"], "dispatch_model")
        self.assertEqual(started["call_mode"], "LEAD_RESEARCH")
        self.assertLess(len(started["prompt"]), 40000)
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        self.assertEqual(
            run["run_ledger"]["pending_dispatch"]["prompt_sha256"],
            started["prompt_sha256"],
        )
        packet = lead_packet(run)
        receipt = codex_research_receipt.build(
            started, packet, agent_id="/root", isolation="UNVERIFIED"
        )
        submitted = research_loop.cmd_submit_lead(
            started["run_id"], packet, receipt
        )
        self.assertEqual(submitted["status"], "ready_for_report")
        report = research_loop.cmd_report(started["run_id"])
        self.assertTrue(report["delivery_verified"])
        self.assertEqual(
            report["bundle_verification"]["status"],
            "report_bundle_verified",
        )
        self.assertEqual(
            report["rendering_mode"], "PURE_DECISION_SNAPSHOT_USER_AND_AUDIT"
        )
        self.assertTrue(os.path.isfile(report["audit_report_path"]))
        self.assertTrue(os.path.isfile(report["report_bundle_path"]))
        with open(report["report_bundle_path"], encoding="utf-8") as handle:
            bundle = json.load(handle)
        self.assertEqual(bundle["run_id"], started["run_id"])
        self.assertEqual(
            bundle["schema_version"], research_loop.REPORT_BUNDLE_SCHEMA
        )
        self.assertIn("method_identity_sha256", bundle)
        self.assertIn("renderer_sha256", bundle)
        self.assertEqual(bundle["views"]["user"]["sha256"], report["report_sha256"])
        self.assertEqual(
            bundle["views"]["audit"]["sha256"], report["audit_report_sha256"]
        )
        self.assertEqual(
            hashlib.sha256(report["report_markdown"].encode("utf-8")).hexdigest(),
            report["report_sha256"],
        )
        self.assertIn("资本事件已改变融资边界", report["report_markdown"])
        self.assertNotIn("CandidateMap", report["report_markdown"])

    def test_report_bundle_verifier_detects_post_delivery_tampering(self):
        started = self._start(1)
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        packet = lead_packet(run)
        receipt = codex_research_receipt.build(
            started, packet, agent_id="/root", isolation="UNVERIFIED"
        )
        research_loop.cmd_submit_lead(started["run_id"], packet, receipt)
        report = research_loop.cmd_report(started["run_id"])
        os.chmod(report["report_path"], 0o644)
        with open(report["report_path"], "a", encoding="utf-8") as handle:
            handle.write("\nforged conclusion\n")
        with self.assertRaisesRegex(
            ValueError,
            "report_bundle_view_content_(?:address_)?mismatch:user",
        ):
            research_loop.verify_report_bundle(
                started["run_id"], report["report_bundle_path"]
            )

    def test_report_bundle_itself_is_content_addressed_and_read_only(self):
        started = self._start(1)
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        packet = lead_packet(run)
        receipt = codex_research_receipt.build(
            started, packet, agent_id="/root", isolation="UNVERIFIED"
        )
        research_loop.cmd_submit_lead(started["run_id"], packet, receipt)
        report = research_loop.cmd_report(started["run_id"])
        bundle_path = report["report_bundle_path"]
        with open(bundle_path, encoding="utf-8") as handle:
            bundle = json.load(handle)
        os.chmod(bundle_path, 0o644)
        with open(bundle_path, "w", encoding="utf-8") as handle:
            json.dump(bundle, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        with self.assertRaisesRegex(
            ValueError, "report_bundle_content_address_mismatch"
        ):
            research_loop.verify_report_bundle(started["run_id"], bundle_path)

    def test_report_bundle_rejects_a_non_addressed_view_alias(self):
        started = self._start(1)
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        packet = lead_packet(run)
        receipt = codex_research_receipt.build(
            started, packet, agent_id="/root", isolation="UNVERIFIED"
        )
        research_loop.cmd_submit_lead(started["run_id"], packet, receipt)
        report = research_loop.cmd_report(started["run_id"])
        with open(report["report_bundle_path"], encoding="utf-8") as handle:
            bundle = json.load(handle)
        alias = os.path.join(
            os.path.dirname(report["report_path"]),
            "report-user-not-content-addressed.md",
        )
        with open(report["report_path"], "rb") as source, open(alias, "wb") as target:
            target.write(source.read())
        os.chmod(alias, 0o444)
        bundle["views"]["user"]["path"] = alias
        forged = research_registry.save_derived_artifact(
            started["run_id"], "report-bundle", bundle, suffix=".json"
        )
        with self.assertRaisesRegex(
            ValueError, "report_bundle_view_content_address_mismatch:user"
        ):
            research_loop.verify_report_bundle(
                started["run_id"], forged["path"]
            )

    def test_report_bundle_binds_the_complete_run_ledger(self):
        started = self._start(1)
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        packet = lead_packet(run)
        receipt = codex_research_receipt.build(
            started, packet, agent_id="/root", isolation="UNVERIFIED"
        )
        research_loop.cmd_submit_lead(started["run_id"], packet, receipt)
        report = research_loop.cmd_report(started["run_id"])
        tampered = research_io.load_json(manifest["state_path"], default=None)
        tampered["run_ledger"]["calls"][0]["agent_id"] = "/forged-lead"
        research_io.save_json(manifest["state_path"], tampered)
        with self.assertRaisesRegex(
            ValueError,
            "report_bundle_binding_mismatch:(?:run_ledger_sha256|research_run_sha256)",
        ):
            research_loop.verify_report_bundle(
                started["run_id"], report["report_bundle_path"]
            )

    def test_start_requires_explicit_execution_mode(self):
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "execution_mode_required"
        ):
            research_loop.cmd_start(
                "明确主题", task_spec(1), round_budget=1
            )

    def test_manual_codex_receipt_cannot_claim_verified_isolation(self):
        started = self._start(1)
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        packet = lead_packet(run)
        with self.assertRaisesRegex(
            ValueError, "cannot_attest_isolation"
        ):
            codex_research_receipt.build(
                started, packet, agent_id="claimed-independent",
                isolation="VERIFIED_PROCESS",
            )

    def test_start_rejects_a_generic_unscoped_deep_research_run(self):
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "explicit_primary_entities_and_questions_required",
        ):
            research_loop.cmd_start(
                "泛化主题", {"as_of": "2026-08-12"}, round_budget=1,
                execution_mode="UNVERIFIED",
            )

    def test_payload_hash_mismatch_is_rejected_without_state_mutation(self):
        started = self._start(1)
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        packet = lead_packet(run)
        receipt = codex_research_receipt.build(
            started, packet, agent_id="/root", isolation="UNVERIFIED"
        )
        receipt["payload_sha256"] = "0" * 64
        before = json.dumps(run, ensure_ascii=False, sort_keys=True)
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "payload_hash_mismatch"
        ):
            research_loop.cmd_submit_lead(started["run_id"], packet, receipt)
        after = research_io.load_json(manifest["state_path"], default=None)
        self.assertEqual(before, json.dumps(after, ensure_ascii=False, sort_keys=True))

    def test_dispatch_replay_is_idempotent(self):
        started = self._start(1)
        replay = research_loop.cmd_dispatch(started["run_id"])
        self.assertEqual(replay["prompt_sha256"], started["prompt_sha256"])
        self.assertEqual(replay["working_set"], started["working_set"])

    def test_host_input_recompiles_the_unspent_dispatch(self):
        started = self._start(1)
        market = market_evidence()
        fragment = {
            "input_id": "HOST-MARKET-TEST",
            "evidence_items": [market],
            "source_checks": [{
                "source_check_id": "SC-HOST-MARKET-TEST",
                "entity_id": "E1",
                "security_id": "300001@XSHE",
                "fact_surface": "MARKET_PRICE_LIQUIDITY",
                "window_start": "2026-08-12",
                "window_end": "2026-08-12",
                "queries": [market["url"]],
                "official_index_url": "",
                "checked_document_urls": [market["url"]],
                "index_entries": [],
                "enumeration_complete": False,
                "outcome": "FOUND",
                "evidence_ids": [market["evidence_id"]],
                "negative_scope": "",
                "limitation": "host-frozen market observation",
            }],
        }
        result = research_loop.cmd_ingest_host(
            started["run_id"], fragment
        )
        self.assertEqual(result["status"], "dispatch_model")
        self.assertNotEqual(result["prompt_sha256"], started["prompt_sha256"])
        self.assertEqual(result["delivery_state"]["completed_research_loops"], 0)
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        self.assertEqual(run["evidence_store"]["items"][0]["origin"], "USER_OR_HOST_SEED")
        self.assertEqual(run["evidence_store"]["source_checks"][0]["origin"], "HOST_INPUT")

    def test_host_append_cannot_be_rolled_back_through_raw_cas(self):
        started = self._start(2)
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        packet = lead_packet(run, continue_research=True)
        lead_receipt = codex_research_receipt.build(
            started, packet, agent_id="/root", isolation="UNVERIFIED"
        )
        research_loop.cmd_submit_lead(started["run_id"], packet, lead_receipt)
        before_host = research_io.load_json(manifest["state_path"], default=None)
        market = market_evidence()
        market["decision_impact"] = "HIGH"
        fragment = {
            "input_id": "HOST-MARKET-ROLLBACK",
            "evidence_items": [market],
            "source_checks": [{
                "source_check_id": "SC-HOST-MARKET-ROLLBACK",
                "entity_id": "E1", "security_id": "300001@XSHE",
                "fact_surface": "MARKET_PRICE_LIQUIDITY",
                "window_start": "2026-08-12", "window_end": "2026-08-12",
                "queries": [market["url"]], "official_index_url": "",
                "checked_document_urls": [market["url"]], "index_entries": [],
                "enumeration_complete": False, "outcome": "FOUND",
                "evidence_ids": [market["evidence_id"]], "negative_scope": "",
                "limitation": "host-frozen market observation",
            }],
        }
        research_loop.cmd_ingest_host(started["run_id"], fragment)
        after_host = research_io.load_json(manifest["state_path"], default=None)
        rollback = deepcopy(before_host)
        rollback["run_ledger"]["state_revision"] = after_host["run_ledger"][
            "state_revision"
        ]
        revision = after_host["run_ledger"]["state_revision"]
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "transition.evidence_store_items_append_only",
        ):
            research_io.save_run_cas(
                manifest["state_path"], rollback, expected_revision=revision,
            )
        self.assertEqual(
            research_io.load_json(manifest["state_path"], default=None), after_host
        )

    def test_evidence_store_tampering_is_rejected_before_resume(self):
        started = self._start(1)
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        run["evidence_store"]["items"].append({"evidence_id": "EV-TAMPERED"})
        research_io.save_json(manifest["state_path"], run)
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "evidence_store_hash_drift"
        ):
            research_loop.cmd_dispatch(started["run_id"])

    def test_report_and_budget_extension_require_a_stopped_run(self):
        started = self._start(1)
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "run_not_stopped"
        ):
            research_loop.cmd_report(started["run_id"])
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "requires_stopped_report_state"
        ):
            research_loop.cmd_authorize(started["run_id"], 1)

    def test_failure_after_a_snapshot_produces_an_explicit_degraded_report(self):
        started = self._start(2)
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        packet = lead_packet(run, continue_research=True)
        packet["decision_snapshot"]["lowest_cost_next_validation"][0][
            "availability"
        ] = "SEARCH_NOW"
        receipt = codex_research_receipt.build(
            started, packet, agent_id="/root", isolation="UNVERIFIED"
        )
        continued = research_loop.cmd_submit_lead(
            started["run_id"], packet, receipt
        )
        self.assertEqual(continued["call_mode"], "LEAD_RESEARCH")
        research_loop.cmd_runtime_failure(
            started["run_id"], "LEAD", "host_permission_denied", "failed-2"
        )
        report = research_loop.cmd_report(started["run_id"])
        self.assertIn("执行状态 `RUNTIME_FAILURE`", report["report_markdown"])
        self.assertIn("host_permission_denied", report["report_markdown"])
        self.assertIn("未自动重试", report["report_markdown"])

    def test_success_after_explicit_retry_is_not_mislabeled_as_current_failure(self):
        started = self._start(1)
        research_loop.cmd_runtime_failure(
            started["run_id"], "LEAD", "temporary_host_failure", "failed-first"
        )
        retried = research_loop.cmd_authorize(started["run_id"], 0)
        manifest = research_registry.load_manifest(started["run_id"])
        run = research_io.load_json(manifest["state_path"], default=None)
        packet = lead_packet(run)
        retry_receipt = codex_research_receipt.build(
            retried, packet, agent_id="/root", isolation="UNVERIFIED"
        )
        research_loop.cmd_submit_lead(started["run_id"], packet, retry_receipt)
        report = research_loop.cmd_report(started["run_id"])["report_markdown"]
        self.assertIn("执行状态 `COMPLETE_AFTER_EXPLICIT_RETRY`", report)
        self.assertNotIn("执行状态 `RUNTIME_FAILURE`", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
