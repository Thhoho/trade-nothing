#!/usr/bin/env python3
"""Regression tests for the topic-led research product boundary."""
from pathlib import Path
import unittest

import deepthink_orchestrator_v2 as orchestrator


ROOT = Path(__file__).resolve().parents[1]


class ProductResetContractTests(unittest.TestCase):
    def test_baseline_freezes_topic_led_target_and_acceptance(self):
        text = (ROOT / "docs" / "topic-led-research-product.md").read_text(
            encoding="utf-8"
        )
        for fragment in (
            "主对象是课题",
            "每轮既要回答，也要发现新的未知",
            "严格性用于校准结论",
            "产品止于深度研究报告与建议",
            "Research Agenda",
            "盲点账本",
            "Deep Research Report 产品合同",
            "朱雀三号类课题验收基准",
            "Research Agenda 是控制平面",
            "一轮结束后始终可交付完整报告",
        ):
            self.assertIn(fragment, text)

    def test_skill_declares_research_boundary_not_downstream_ownership(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("**Deep Research Report（深度研究报告与建议）**", text)
        self.assertIn("Research Agenda（事实/因果/市场/载体/定价/风险/前瞻问题）", text)
        self.assertIn("假说只在不确定机制需要对照检验时使用", text)
        self.assertIn("抽象 hypothesis 永远不得自动晋升", text)
        self.assertIn("新运行\n  默认不要求 crux/logic graph", text)
        self.assertIn("Skill 到 Deep Research Report 与建议为止", text)

    def test_agents_and_runtime_make_agenda_primary(self):
        framer = (ROOT / "agents" / "framer.md").read_text(encoding="utf-8")
        detective = (ROOT / "agents" / "detective.md").read_text(encoding="utf-8")
        inquisitor = (ROOT / "agents" / "inquisitor.md").read_text(encoding="utf-8")
        orchestrator = (ROOT / "scripts" / "deepthink_orchestrator_v2.py").read_text(encoding="utf-8")
        report = (ROOT / "scripts" / "report_v2.py").read_text(encoding="utf-8")
        self.assertIn('"frame_schema_version": "trade-nothing.frame.v2"', framer)
        self.assertIn('"research_workplan"', framer)
        self.assertIn('"candidate_cruxes": []', framer)
        self.assertIn('"question_updates"', detective)
        self.assertIn('"new_blind_spots"', inquisitor)
        self.assertIn("research_agenda_engine.harvest_round", orchestrator)
        self.assertIn("research_agenda_engine.control_decision", orchestrator)
        self.assertIn('"research_more_requires_authorization"', orchestrator)
        self.assertIn('def render(state, view="research")', report)
        self.assertIn('"# Deep Research Report"', report)

    def test_active_protocols_do_not_define_downstream_lifecycle(self):
        opportunity = (ROOT / "references" / "opportunity-protocol.md").read_text(
            encoding="utf-8"
        )
        report = (ROOT / "references" / "report-contract.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("must never auto-promote", opportunity)
        self.assertIn("listed securities", opportunity)
        self.assertIn("ends at the Deep Research Report", opportunity)
        for legacy_state in (
            "THESIS_CANDIDATE",
            "VERIFIED_FOR_HUMAN",
            "DRAFT_REQUIRES_HUMAN",
            "publication_allowed",
            "ranking_allowed",
        ):
            self.assertNotIn(legacy_state, opportunity)
            self.assertNotIn(legacy_state, report)

    def test_model_work_windows_embed_the_contract_they_reference(self):
        frame_prompt = orchestrator.frame_prompt("测试课题")
        self.assertIn("[WORK WINDOW — AUTHORITATIVE]", frame_prompt)
        self.assertIn("[BEGIN CONTRACT: agents/framer.md]", frame_prompt)
        self.assertIn('"frame_schema_version": "trade-nothing.frame.v2"', frame_prompt)

        prompts = orchestrator.candidate_screen_prompts({}, [], "2026-08-10")
        for role in ("analyst_prompt", "skeptic_prompt"):
            self.assertIn("[WORK WINDOW — AUTHORITATIVE]", prompts[role])
            self.assertIn("[BEGIN CONTRACT: references/candidate-screen-protocol.md]", prompts[role])
            self.assertIn('"candidate_screens"', prompts[role])

        detective_contract = orchestrator._contract_text(
            "agents/runtime/research-round.md", "agents/runtime/detective.md"
        )
        self.assertIn('"question_updates"', detective_contract)
        self.assertIn('"field_update_modes"', detective_contract)
        self.assertIn("trusted_market_snapshots", detective_contract)

        state = {
            "decision_question": "产业价值如何映射到市场载体？",
            "horizon": "一个季度",
            "frame_contract": {"as_of_date": "2026-08-10"},
            "cruxes": {},
            "rounds": [],
            "config": {},
            "research_agenda": {
                "agenda_source": "EXPLICIT_WORKPLAN",
                "questions": [],
                "research_directions": [],
                "evidence_items": [],
            },
            "forbidden_consensus": [],
            "negative_priors": [],
        }
        round_prompts = orchestrator.dispatch_prompts(state, 1)
        self.assertLess(len(round_prompts["detective_prompt"]), 24000)
        self.assertLess(len(round_prompts["inquisitor_prompt"]), 24000)
        for role in ("detective_prompt", "inquisitor_prompt"):
            self.assertIn('"coverage_route_kinds"', round_prompts[role])
            self.assertIn('"next_test_availability"', round_prompts[role])
            self.assertIn("WAIT_FOR_EVENT", round_prompts[role])
        self.assertNotIn("[BEGIN CONTRACT: agents/detective.md]", round_prompts["detective_prompt"])
        self.assertNotIn("[BEGIN CONTRACT: agents/inquisitor.md]", round_prompts["inquisitor_prompt"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
