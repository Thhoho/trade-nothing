#!/usr/bin/env python3
"""Pure-render and execution-truth regression tests for research reports."""
from __future__ import annotations

from copy import deepcopy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import research_core
import research_report
from test_research_core import (
    bind, challenge_source_check, complete_source_checks, evidence,
    lead_packet, receipt, snapshot, task_spec,
)


class ReportTruthTests(unittest.TestCase):
    def _controlled_run(self):
        run = research_core.new_research_run(
            task_spec(1), {"method_version": "0.18.0"},
            execution_mode="CONTROLLED_FIXTURE",
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        packet = lead_packet(run)
        return research_core.apply_lead_packet(
            run, packet, receipt("LEAD", packet)
        )

    def test_user_and_audit_views_share_one_decision_body_and_are_pure(self):
        run = self._controlled_run()
        before = deepcopy(run)
        user = research_report.render(run, view="user")
        audit = research_report.render(run, view="audit")
        self.assertEqual(user, research_report.render(run, view="user"))
        self.assertEqual(audit, research_report.render(run, view="audit"))
        self.assertEqual(run, before)
        self.assertEqual(
            user.split("## 8. Evidence Ledger", 1)[0],
            audit.split("## 8. Evidence Ledger", 1)[0],
        )
        self.assertNotIn("数字=", user + audit)
        self.assertIn("**1亿元**｜融资或资本计划金额", user)
        self.assertIn("`E1` / `financing_amount`", user)

    def test_requested_process_mode_does_not_overstate_actual_receipt(self):
        run = research_core.new_research_run(
            task_spec(1), {"method_version": "0.18.0"},
            execution_mode="EXTERNAL_PROCESS_REPORTED",
        )
        run = research_core.seed_research_run(
            run, [evidence()], complete_source_checks()
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        observation = evidence("EV-LEAD-LOW", impact="LOW")
        packet = lead_packet(run)
        packet["evidence_items"] = [observation]
        packet["source_checks"] = [challenge_source_check("EV-LEAD-LOW")]
        packet["decision_snapshot"] = snapshot(run)
        manual = {
            "receipt_id": "MANUAL-LEAD", "status": "SUCCEEDED",
            "agent_id": "/root", "isolation": "UNVERIFIED",
            "receipt_provenance": "SELF_DECLARED", "process_id": 0,
            "host_runtime": "codex", "external_tools_enabled": False,
            "prompt_sha256": "a" * 64,
            "payload_sha256": research_core.stable_hash(packet),
        }
        run = research_core.apply_lead_packet(run, packet, manual)
        report = research_report.render(run, view="audit")
        self.assertIn(
            "请求的编排模式：`EXTERNAL_PROCESS_REPORTED`", report
        )
        self.assertIn(
            "Lead 实际回执：`SELF_DECLARED / UNVERIFIED / UNVERIFIED`",
            report,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
