#!/usr/bin/env python3
"""Architecture-level contracts for the v0.18 harness-first kernel."""
from pathlib import Path
import unittest

import check_source_sync
import method_identity
import research_core
import research_loop
from test_research_core import task_spec


ROOT = Path(__file__).resolve().parents[1]


class ProductResetContractTests(unittest.TestCase):
    def test_product_contract_has_one_semantic_truth(self):
        text = (ROOT / "docs" / "topic-led-research-product.md").read_text(
            encoding="utf-8"
        )
        for fragment in (
            "主对象是用户的课题",
            "四对象内核",
            "每轮既要回答，也要发现新的未知",
            "严格性用于校准结论",
            "产品止于深度研究报告与建议",
            "Research Agenda 不再是独立控制平面",
            "Deep Research Report 产品合同",
            "朱雀三号类课题验收基准",
        ):
            self.assertIn(fragment, text)

    def test_skill_declares_reality_recall_and_research_boundary(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for fragment in (
            "## The kernel",
            "## One useful-action loop",
            "official disclosure index",
            "Every HIGH EvidenceItem",
            "The Value Lead alone replaces",
            "Stop at an evidence-bounded Deep Research Report",
            "`exposure_evidence_ids`",
            "`market_evidence_ids`",
            "HARNESS_SUBAGENT / HARNESS_REPORTED / SEPARATE_CONTEXT_REPORTED",
            "The kernel has two clocks",
            "market_carriers_by_horizon",
            "typed `measures`",
        ):
            self.assertIn(fragment, text)
        self.assertNotIn("Judge 不得空转", text)

    def test_generated_prompts_replace_parallel_role_contracts(self):
        for relative in (
            "agents/framer.md", "agents/detective.md", "agents/inquisitor.md",
            "agents/judge.md", "agents/runtime/research-round.md",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)
        source = (ROOT / "scripts" / "research_loop.py").read_text(encoding="utf-8")
        self.assertIn("def _lead_prompt", source)
        self.assertIn("def _challenger_prompt", source)
        self.assertIn("OUTPUT CONTRACT", source)

    def test_generated_work_window_is_closed_and_bounded(self):
        run = research_core.new_research_run(
            task_spec(2), {"method_version": "0.18.0"}, execution_mode="UNVERIFIED"
        )
        dispatched = research_loop.dispatch(run)
        prompt = dispatched["prompt"]
        # The bounded window carries the complete metric/basis registry so a
        # child model never has to guess quantitative semantics.
        self.assertLess(len(prompt.encode("utf-8")), 18000)
        self.assertIn("WORKING SET", prompt)
        self.assertIn("OUTPUT CONTRACT", prompt)
        self.assertIn("LATEST_PERIODIC_REPORT_OR_120D", prompt)
        self.assertIn("exposure_evidence_ids", prompt)
        self.assertIn("market_evidence_ids", prompt)
        self.assertIn("market_carriers_by_horizon", prompt)
        self.assertIn('"measures"', prompt)
        self.assertNotIn("[BEGIN CONTRACT: agents/detective.md]", prompt)
        self.assertNotIn("Judge", prompt)

        zero = research_core.new_research_run(
            task_spec(0), {"method_version": "0.18.0"}, execution_mode="UNVERIFIED"
        )
        zero_prompt = research_loop.dispatch(zero)["prompt"]
        self.assertIn("no-search synthesis", zero_prompt)
        self.assertIn('"evidence_items":[]', zero_prompt)

    def test_active_method_and_install_bundle_exclude_legacy_engines(self):
        active = set(method_identity.ACTIVE_METHOD_PATHS)
        published = {
            path.relative_to(ROOT).as_posix()
            for path in check_source_sync.controlled_files(ROOT)
        }
        for legacy in (
            "agents/judge.md",
            "agents/detective.md",
            "scripts/deepthink_orchestrator_v2.py",
            "scripts/crux_engine.py",
            "scripts/report_v2.py",
            "scripts/research_agenda_engine.py",
            "scripts/market_bridge_engine.py",
            "scripts/run_registry.py",
            "scripts/artifact_envelope.py",
        ):
            self.assertNotIn(legacy, active)
            self.assertNotIn(legacy, published)
        self.assertTrue(active.issubset(published))
        self.assertIn("scripts/free_market_observations.py", active)
        self.assertIn("scripts/market_snapshot_adapter.py", active)
        self.assertIn("scripts/research_market_input.py", active)
        for adapter in (
            "scripts/research_host_runner.py",
            "scripts/model_process_runtime.py",
            "scripts/codex_research_receipt.py",
        ):
            self.assertNotIn(adapter, active)
            self.assertIn(adapter, published)


if __name__ == "__main__":
    unittest.main(verbosity=2)
