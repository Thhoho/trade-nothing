#!/usr/bin/env python3
"""Deterministic tests for the single-command daily content producer."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import daily_topic

SHANGHAI = ZoneInfo("Asia/Shanghai")


def ready_selection(budget=2):
    return {
        "status": "TOPIC_READY",
        "topic": "AI系统交付的利润池映射",
        "decision_question": "有效算力约束是否正在改变A股利润池和市场载体？",
        "why_now": "本周出现新的订单与相对强弱分化。",
        "decision_change": "决定继续观察芯片，还是切换到系统交付环节。",
        "supporting_change_ids": ["C1", "C2"],
        "round_budget": budget,
        "budget_reason": "需要先建立价值路径，再比较经济暴露与市场载体。",
        "why_not_less": "一轮无法同时完成事实核验和横向比较。",
        "why_not_more": "第二轮已能回答当前决策问题。",
        "round_plan": [
            {
                "round": number,
                "objective": f"完成第{number}轮目标。",
                "enter_if": "上一轮仍有立即可搜索的关键缺口。",
                "stop_if": "当前问题已可回答或只剩等待型信息。",
            }
            for number in range(1, budget + 1)
        ],
        "stop_condition": "问题已可回答，或只剩等待未来财报验证。",
        "continuation_condition": "仍存在低成本、高影响、可立即搜索的问题。",
        "evidence_risks": ["订单口径可能不等于收入确认。"],
        "execution_instruction": (
            "使用最新 $trade-nothing，研究：有效算力约束是否正在改变A股利润池和市场载体？，"
            f"-deepthink2 {budget}轮。"
        ),
    }


def ready_observation():
    return {
        "status": "READY",
        "market_state": "结构分化，产业证据与主题价格尚未完全对齐",
        "headline": "订单与相对强弱同时变化，但尚不足以把产业趋势直接写成推荐。",
        "changes": [
            {
                "change_id": "C1",
                "title": "订单出现新增事实",
                "detail": "公司发布新的订单公告，但收入确认仍待后续验证。",
                "source_url": "https://example.com/filing",
                "source_date": "2026-08-12",
                "evidence_label": "FACT",
            },
            {
                "change_id": "C2",
                "title": "市场载体出现分化",
                "detail": "相关指数出现一周相对强弱变化，尚不能单独证明利润池迁移。",
                "source_url": "https://example.com/market",
                "source_date": "2026-08-12",
                "evidence_label": "SINGLE_SOURCE",
            },
            {
                "change_id": "C3",
                "title": "替代解释仍然存在",
                "detail": "同行披露显示需求改善并不均匀，需区分行业贝塔和公司兑现。",
                "source_url": "https://example.com/peer",
                "source_date": "2026-08-11",
                "evidence_label": "INFERENCE",
            },
        ],
        "industry_market_bridge": (
            "产业端先验证订单、交付和现金转化，市场端再比较真正有经济暴露的公司与"
            "仅有概念标签的交易载体，并观察拥挤度是否已提前透支。"
        ),
        "decision_boundary": "当前只形成研究优先级，不形成具名推荐、目标价或仓位建议。",
        "next_validation": "下一步核对订单验收、毛利率与经营现金流，并比较三类载体。",
        "degradation_reason": "",
    }


class DailyTopicTests(unittest.TestCase):
    def test_model_child_environment_does_not_receive_provider_secrets(self):
        sanitized = daily_topic._sanitized_child_env(
            {
                "PATH": "/usr/bin",
                "TUSHARE_TOKEN": "private",
                "OPENAI_API_KEY": "private",
                "OTHER_SECRET": "private",
            }
        )
        self.assertEqual(sanitized, {"PATH": "/usr/bin"})

    def test_explicit_missing_codex_binary_fails_closed(self):
        with self.assertRaisesRegex(daily_topic.DailyTopicError, "codex_cli_not_found"):
            daily_topic._resolve_codex("/definitely/missing/codex")

    def test_date_only_cutoff_defaults_to_1830_shanghai(self):
        parsed = daily_topic._parse_as_of("2026-08-12")
        self.assertEqual(parsed.isoformat(timespec="minutes"), "2026-08-12T18:30+08:00")

    def test_ready_selection_requires_plan_matching_budget(self):
        selection = ready_selection(2)
        self.assertIs(daily_topic.validate_selection(selection), selection)
        selection["round_plan"].pop()
        with self.assertRaisesRegex(daily_topic.DailyTopicError, "round_plan_must_match"):
            daily_topic.validate_selection(selection)

    def test_ready_observation_requires_three_sequential_sourced_changes(self):
        observation = ready_observation()
        self.assertIs(daily_topic.validate_observation(observation), observation)
        observation["changes"].pop()
        with self.assertRaisesRegex(daily_topic.DailyTopicError, "requires_three"):
            daily_topic.validate_observation(observation)

    def test_observation_rejects_sources_after_fact_cutoff(self):
        observation = ready_observation()
        observation["changes"][0]["source_date"] = "2026-08-13"
        with self.assertRaisesRegex(daily_topic.DailyTopicError, "after_cutoff"):
            daily_topic.validate_observation(
                observation, cutoff_date=datetime(2026, 8, 12).date()
            )

    def test_no_topic_requires_zero_budget_and_no_named_topic(self):
        selection = daily_topic._closed_selection(
            {"session": "2026-08-15", "status": "CLOSED"}
        )
        self.assertEqual(daily_topic.validate_selection(selection)["round_budget"], 0)
        selection["topic"] = "forced topic"
        with self.assertRaisesRegex(daily_topic.DailyTopicError, "must_not_name_topic"):
            daily_topic.validate_selection(selection)

    def test_prompt_requires_one_scan_two_outputs_and_dynamic_budget_boundary(self):
        as_of = datetime(2026, 8, 12, 18, 30, tzinfo=SHANGHAI)
        prompt = daily_topic.build_prompt(
            as_of,
            {"status": "OPEN", "session": "2026-08-12"},
            [{"date": "2026-08-11", "topic": "商业航天", "question": "Q"}],
            {"method_version": "0.15.0", "contract_sha256": "abc"},
        )
        self.assertIn("ONE SCAN, TWO LINKED OUTPUTS", prompt)
        self.assertIn("600-1000 Chinese-character", prompt)
        self.assertIn("supporting_change_ids", prompt)
        self.assertIn("0 rounds", prompt)
        self.assertIn("7-10 rounds", prompt)
        self.assertIn("Never recommend more than 10 rounds", prompt)
        self.assertIn("means a recommendation for later user authorization", prompt)
        self.assertIn("商业航天", prompt)

    def test_persist_is_atomic_and_refuses_silent_replace(self):
        as_of = datetime(2026, 8, 12, 18, 30, tzinfo=SHANGHAI)
        record = daily_topic.build_record(
            as_of,
            {"status": "OPEN", "session": "2026-08-12"},
            {"method_version": "0.15.0", "contract_sha256": "abc"},
            ready_observation(),
            ready_selection(1),
        )
        with tempfile.TemporaryDirectory() as tmp:
            paths = daily_topic.persist_record(record, tmp)
            topic = json.loads(paths["topic_json"].read_text())
            self.assertEqual(topic["selection"]["round_budget"], 1)
            self.assertEqual(topic["supporting_changes"][0]["change_id"], "C1")
            self.assertIn(
                "每日观察", paths["observation_markdown"].read_text(encoding="utf-8")
            )
            self.assertIn(
                "每日选题卡", paths["topic_markdown"].read_text(encoding="utf-8")
            )
            with self.assertRaisesRegex(daily_topic.DailyTopicError, "use --replace"):
                daily_topic.persist_record(record, tmp)
            daily_topic.persist_record(record, tmp, replace=True)

    def test_daily_output_rejects_selection_fact_outside_observation(self):
        selection = ready_selection(2)
        selection["supporting_change_ids"] = ["C1", "C3"]
        observation = ready_observation()
        observation["status"] = "DEGRADED"
        observation["degradation_reason"] = "第三条变化缺少足够来源。"
        observation["changes"].pop()
        with self.assertRaisesRegex(daily_topic.DailyTopicError, "change_ref_missing"):
            daily_topic.validate_daily_output(
                {"observation": observation, "selection": selection}
            )

    def test_ten_round_budget_is_valid_but_eleven_is_rejected(self):
        selection = ready_selection(10)
        self.assertEqual(daily_topic.validate_selection(selection)["round_budget"], 10)
        selection["round_budget"] = 11
        with self.assertRaisesRegex(daily_topic.DailyTopicError, "round_budget_invalid"):
            daily_topic.validate_selection(selection)

    def test_weekend_closes_without_model_call(self):
        status = daily_topic._trade_day_status(
            datetime(2026, 8, 15, 18, 30, tzinfo=SHANGHAI)
        )
        self.assertEqual(status["status"], "CLOSED")
        self.assertEqual(status["reason"], "weekend")

    def test_market_session_requires_completed_close_for_canonical_output(self):
        calendar = {"status": "OPEN", "session": "2026-08-12"}
        phases = {
            8: "PRE_OPEN",
            10: "IN_SESSION",
            16: "POST_CLOSE_SETTLING",
            18: "POST_CLOSE_FINAL",
        }
        for hour, expected in phases.items():
            with self.subTest(hour=hour):
                context = daily_topic._market_session_context(
                    datetime(2026, 8, 12, hour, 30, tzinfo=SHANGHAI), calendar
                )
                self.assertEqual(context["phase"], expected)
                self.assertEqual(
                    context["canonical_output_allowed"], hour >= 18
                )

    def test_ready_output_is_rejected_outside_completed_open_session(self):
        output = {
            "observation": ready_observation(),
            "selection": ready_selection(2),
        }
        with self.assertRaisesRegex(
            daily_topic.DailyTopicError, "completed_open_session"
        ):
            daily_topic.validate_daily_output(
                output,
                as_of=datetime(2026, 8, 12, 8, 30, tzinfo=SHANGHAI),
                market_session={"ready_allowed": False},
            )

    def test_preopen_main_fails_before_nested_model_execution(self):
        with mock.patch.object(
            daily_topic,
            "_trade_day_status",
            return_value={"status": "OPEN", "session": "2026-08-12"},
        ), mock.patch.object(daily_topic, "_method_identity", return_value={}), mock.patch.object(
            daily_topic, "_run_codex"
        ) as nested:
            code = daily_topic.main(["--as-of", "2026-08-12T08:30:00+08:00"])
        self.assertEqual(code, 2)
        nested.assert_not_called()

    def test_completed_close_archives_legacy_early_slot_instead_of_blocking(self):
        calendar = {"status": "OPEN", "session": "2026-08-12"}
        identity = {"method_version": "0.15.0", "contract_sha256": "abc"}
        early_as_of = datetime(2026, 8, 12, 1, 23, tzinfo=SHANGHAI)
        close_as_of = datetime(2026, 8, 12, 18, 30, tzinfo=SHANGHAI)
        early = daily_topic.build_record(
            early_as_of,
            calendar,
            identity,
            ready_observation(),
            ready_selection(1),
        )
        final = daily_topic.build_record(
            close_as_of,
            calendar,
            identity,
            ready_observation(),
            ready_selection(1),
        )
        with tempfile.TemporaryDirectory() as tmp:
            daily_topic.persist_record(early, tmp)
            paths = daily_topic.persist_record(final, tmp)
            self.assertIn("archived_nonfinal", paths)
            self.assertTrue(paths["archived_nonfinal"].is_dir())
            current = json.loads(paths["observation_json"].read_text())
            self.assertEqual(
                current["market_session"]["phase"], "POST_CLOSE_FINAL"
            )

    def test_closed_day_still_has_explicit_observation_artifact(self):
        calendar = {"session": "2026-08-15", "status": "CLOSED"}
        observation = daily_topic._closed_observation(calendar)
        self.assertEqual(observation["status"], "SKIPPED_CLOSED")
        self.assertIs(
            daily_topic.validate_observation(observation, allow_closed=True), observation
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
