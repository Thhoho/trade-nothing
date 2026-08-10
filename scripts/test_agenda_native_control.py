#!/usr/bin/env python3
"""Regression replay for Agenda-native scheduling, stopping, and authorization."""
import os
import tempfile
import unittest

import deepthink_orchestrator_v2 as orchestrator


def _evidence_plan(cid):
    return [
        {
            "plan_id": f"{cid}-A",
            "publisher_class": "ISSUER_OR_FILING",
            "target_claim": f"official fact for {cid}",
            "search_query": f"official {cid}",
        },
        {
            "plan_id": f"{cid}-B",
            "publisher_class": "EXCHANGE_OR_MARKET_DATA",
            "target_claim": f"market fact for {cid}",
            "search_query": f"market {cid}",
        },
    ]


def _frame():
    questions = []
    for qid, qtype, text, linked in (
        ("RQ1", "FACT", "任务时间和状态是什么？", "C1"),
        ("RQ2", "CAUSAL", "结果由什么工程约束决定？", "C1"),
        ("RQ3", "MARKET", "市场会如何交易结果？", "C2"),
        ("RQ4", "CANDIDATE", "哪个具体载体最值得条件性关注？", "C2"),
    ):
        questions.append({
            "question_id": qid,
            "question": text,
            "question_type": qtype,
            "why_it_matters": "会改变当前结论或条件性建议",
            "success_condition": "形成有边界的可交付答案",
            "initial_search_routes": ["官方或市场数据"],
            "decision_impact": "HIGH",
            "research_cost": "MEDIUM",
            "blocks_current_recommendation": False,
            "linked_crux_id": linked,
        })
    cruxes = []
    for cid, label, role in (
        ("C1", "任务事实与工程约束", "THESIS_HINGE"),
        ("C2", "市场与具体载体", "PRICING"),
    ):
        cruxes.append({
            "id": cid,
            "label": label,
            "logic_role": role,
            "definition": label,
            "monitor_anchor": f"{label}的可观察数据",
            "falsifier": f"数据否定{label}",
            "evidence_plan": _evidence_plan(cid),
            "catalyst_window": {
                "event": f"复核{label}",
                "expected_by": "2026-10-10",
                "date_status": "REVIEW_CHECKPOINT",
                "basis_claim_id": "P1",
            },
        })
    return {
        "frame_schema_version": "trade-nothing.frame.v2",
        "decision_question": "事件结果如何影响产业与短线机会？",
        "question_type": "CONJUNCTIVE",
        "research_intent": "OPPORTUNITY_DISCOVERY",
        "logic_graph": {
            "root_id": "Q0",
            "nodes": [
                {"id": "Q0", "node_type": "QUESTION", "label": "root"},
                {"id": "C1", "node_type": "CRUX", "label": "facts"},
                {"id": "C2", "node_type": "CRUX", "label": "market"},
            ],
            "edges": [
                {"from": "C1", "to": "Q0", "relation": "REQUIRED_FOR"},
                {"from": "C2", "to": "Q0", "relation": "PRICING_FOR"},
            ],
        },
        "horizon": "3-6M",
        "as_of_date": "2026-08-10",
        "forecast_target_date": "",
        "unit_of_analysis": "事件、产业链和上市载体",
        "thesis_seed": "方向未知，先回答课题。",
        "research_workplan": {
            "research_objective": "回答事实、机制、市场和具体载体并给条件性建议",
            "questions": questions,
        },
        "premise_audit": [{
            "id": "P1",
            "claim": "事件在研究窗口内可观察",
            "status": "HYPOTHESIS",
            "as_of": "UNKNOWN",
            "source_url": None,
            "required_primary_source": "项目方公告",
            "use": "冻结研究窗口",
        }],
        "candidate_cruxes": cruxes,
        "forbidden_consensus": ["技术成功等于所有股票受益"],
        "no_edge_precheck": {
            "is_researchable": True,
            "basis_type": "TESTABILITY",
            "basis_claim_ids": ["P1"],
            "reason": "事实、市场和价格均可观察。",
        },
        # This used to be rejected by the global MIN_ROUNDS feasibility gate.
        "suggested_max_rounds": 1,
    }


def _answered_payload():
    return {
        "crux_evidence": [],
        "question_updates": [
            {
                "question_id": f"RQ{index}",
                "answer_status": "ANSWERED",
                "answer": f"当前已形成第 {index} 项有边界答案。",
                "answer_is_inference": True,
                "evidence": [],
                "strongest_challenge": "仍可能被新事实改变",
                "missing_information": "",
                "next_question": "",
            }
            for index in range(1, 5)
        ],
        "new_blind_spots": [],
        "new_research_questions": [],
    }


def _agenda_only_frame():
    frame = _frame()
    frame["candidate_cruxes"] = []
    frame["logic_graph"] = {}
    for question in frame["research_workplan"]["questions"]:
        question["linked_crux_id"] = ""
    return frame


class AgendaNativeReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_scratch = os.environ.get("TRADE_NOTHING_SCRATCH_DIR")
        self.old_evolution = os.environ.get("TRADE_NOTHING_EVOLUTION_PATH")
        os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.tmp.name
        os.environ["TRADE_NOTHING_EVOLUTION_PATH"] = os.path.join(
            self.tmp.name, "missing.md"
        )

    def tearDown(self):
        if self.old_scratch is None:
            os.environ.pop("TRADE_NOTHING_SCRATCH_DIR", None)
        else:
            os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.old_scratch
        if self.old_evolution is None:
            os.environ.pop("TRADE_NOTHING_EVOLUTION_PATH", None)
        else:
            os.environ["TRADE_NOTHING_EVOLUTION_PATH"] = self.old_evolution
        self.tmp.cleanup()

    def test_evidence_free_answer_claims_remain_reportable_but_not_complete(self):
        topic = "zhuque-replay-answerable"
        initialized = orchestrator.cmd_init(topic, _frame())
        self.assertEqual(initialized["status"], "dispatch_subagents")
        self.assertEqual(initialized["research_control"]["authorized_rounds"], 1)

        result = orchestrator.cmd_submit(
            topic, _answered_payload(), {}, {"crux_signals": {}}
        )

        self.assertEqual(result["status"], "ready_for_report")
        self.assertEqual(result["audit_convergence"]["decision"], "continue")
        self.assertEqual(
            result["research_control"]["product_readiness"],
            "DELIVERABLE_CURRENT_QUESTION_ANSWERABLE",
        )
        self.assertFalse(result["research_control"]["more_research_recommended"])
        self.assertTrue(result["report_always_available"])
        report = orchestrator.cmd_report(topic)
        self.assertEqual(report["status"], "report_data_ready")
        self.assertIn("交付状态", report["deep_research_report_markdown"])
        self.assertIn("完整回答 0", report["deep_research_report_markdown"])

    def test_agenda_only_frame_uses_inert_legacy_audit_adapter(self):
        topic = "agenda-only-audit-adapter"
        initialized = orchestrator.cmd_init(topic, _agenda_only_frame())
        self.assertEqual(initialized["status"], "dispatch_subagents")
        adapter = initialized["legacy_crux_audit_adapter"]
        self.assertTrue(adapter["applied"])
        self.assertEqual(adapter["mode"], "DERIVED_AUDIT_ONLY")
        self.assertEqual(initialized["dispatch_cruxes"], [])
        self.assertEqual(initialized["round_policy"]["audit_only_cruxes"],
                         adapter["audit_only_crux_ids"])
        self.assertFalse(initialized["round_policy"]["new_cruxes_allowed"])

        result = orchestrator.cmd_submit(
            topic,
            _answered_payload(),
            {},
            {"crux_signals": {}, "new_cruxes": [{"id": "SHADOW-C1"}]},
        )
        self.assertEqual(result["admitted_new_cruxes"], [])
        self.assertEqual(result["round_policy"]["dispatch_cruxes"], [])
        self.assertTrue(result["report_always_available"])

    def test_new_high_impact_blind_spot_reassigns_only_after_authorization(self):
        topic = "zhuque-replay-blind-spot"
        orchestrator.cmd_init(topic, _frame())
        payload = _answered_payload()
        statement = "先发国家队已经改变民营火箭成功的稀缺性叙事"
        payload["new_blind_spots"] = [{
            "statement": statement,
            "why_missed": "只研究技术成功，没有研究市场叙事相对位置",
            "potential_impact": "改变事件资金扩散和短线首选",
            "linked_question_ids": ["RQ3"],
            "cheapest_test": "核对先发事件和板块相对表现",
            "decision_impact": "HIGH",
            "research_cost": "LOW",
            "blocks_current_recommendation": True,
        }]
        payload["new_research_questions"] = [{
            "question": "先发成功是否降低本事件的全国首次稀缺性？",
            "question_type": "MARKET",
            "why_it_matters": "会改变事件弹性和候选排序",
            "success_condition": "查明先发事实并比较叙事差异",
            "search_routes": ["主管部门公告与市场数据"],
            "decision_impact": "HIGH",
            "research_cost": "LOW",
            "blocks_current_recommendation": True,
            "parent_question_id": "RQ3",
            "decision_change": "改变事件稀缺性与候选优先关注顺序",
            "linked_crux_id": "",
            "introduced_by_blind_spot": statement,
        }]

        result = orchestrator.cmd_submit(
            topic, payload, {}, {"crux_signals": {}}
        )
        self.assertEqual(result["status"], "research_more_requires_authorization")
        self.assertTrue(result["report_always_available"])
        self.assertEqual(
            result["continuation_packet"]["focus_questions"][0]["question"],
            "先发成功是否降低本事件的全国首次稀缺性？",
        )

        resumed = orchestrator.cmd_resume_blocked(topic, extra_rounds=1)
        self.assertEqual(resumed["status"], "dispatch_subagents")
        self.assertGreaterEqual(len(resumed["research_questions"]), 1)
        self.assertIn("先发成功", resumed["research_questions"][0]["question"])
        self.assertTrue(all(
            item["answer_status"] != "ANSWERED"
            for item in resumed["research_questions"]
        ))

    def test_explicit_four_round_budget_ignores_legacy_three_round_fuse(self):
        topic = "zhuque-replay-four-authorized-rounds"
        raw = _frame()
        blocker = raw["research_workplan"]["questions"][-1]
        blocker["research_cost"] = "LOW"
        blocker["blocks_current_recommendation"] = True
        orchestrator.cmd_init(topic, raw, authorized_round_budget=4)
        partial = {
            "question_updates": [{
                "question_id": "RQ1",
                "answer_status": "PARTIAL",
                "answer": "已有阶段性答案。",
                "answer_is_inference": True,
                "evidence": [],
                "strongest_challenge": "关键建议问题仍未回答",
                "missing_information": "具体载体",
                "next_question": "哪个载体？",
            }],
            "new_blind_spots": [],
            "new_research_questions": [],
        }
        results = [
            orchestrator.cmd_submit(
                topic, partial, {}, {"crux_signals": {}}
            )
            for _ in range(4)
        ]
        self.assertEqual(
            [item["status"] for item in results[:3]],
            ["dispatch_subagents"] * 3,
        )
        self.assertEqual(
            results[2]["audit_convergence"]["decision"], "fuse_break"
        )
        self.assertEqual(
            results[3]["status"], "research_more_requires_authorization"
        )
        self.assertEqual(results[3]["round_completed"], 4)

    def test_zhuque_challenge_opens_commercial_loop_viewpoint(self):
        topic = "zhuque-replay-new-viewpoint"
        raw = _frame()
        raw["research_workplan"]["questions"][2]["research_cost"] = "LOW"
        initialized = orchestrator.cmd_init(topic, raw)
        self.assertIn("RD-C2", [
            item["direction_id"] for item in initialized["research_directions"]
        ])
        payload = {
            "question_updates": [{
                "question_id": "RQ3",
                "answer_status": "PARTIAL",
                "answer": "全国首次叙事被削弱，但民营商业闭环可能仍有独立稀缺性。",
                "answer_is_inference": True,
                "evidence_ids": [],
                "strongest_challenge": "资金可能只交易板块贝塔",
                "missing_information": "先发与民营事件的相对量价",
                "next_question": "市场定价的是全国首次还是民营商业闭环？",
            }],
            "direction_updates": [{
                "direction_id": "RD-C2",
                "research_judgment": "CHALLENGED",
                "next_move": "OPEN_NEW_DIRECTION",
                "rationale": "先发事实削弱了原有全国首次稀缺性解释。",
                "evidence_ids": [],
                "strongest_challenge": "民营闭环可能有不同的政策和资本含义",
                "unresolved_question": "市场究竟为哪类稀缺性付费？",
            }],
            "new_research_directions": [{
                "direction_id": "RD-ZQ-COMMERCIAL-LOOP",
                "proposition": "市场交易的是民营商业闭环而非全国首次回收",
                "direction_kind": "MARKET_MECHANISM",
                "why_it_matters": "会改写事件弹性、产业增量和短线载体排序",
                "discriminating_test": "比较先发国家队与民营闭环事件窗口的板块相对强弱",
                "linked_question_ids": ["RQ3", "RQ4"],
                "linked_crux_id": "C2",
                "parent_direction_ids": ["RD-C2"],
                "origin_reason": "先发成功让全国首次叙事不再成立",
                "load_bearing": True,
                "decision_impact": "HIGH",
                "research_cost": "LOW",
            }],
            "new_blind_spots": [],
            "new_research_questions": [],
        }
        result = orchestrator.cmd_submit(
            topic, payload, {}, {"crux_signals": {}}
        )
        self.assertEqual(result["status"], "research_more_requires_authorization")
        self.assertIn(
            "NEW_VIEWPOINT_OPENED", result["research_control"]["reason_codes"]
        )
        direction_ids = [
            item["direction_id"]
            for item in result["continuation_packet"]["focus_directions"]
        ]
        self.assertIn("RD-ZQ-COMMERCIAL-LOOP", direction_ids)

        report = orchestrator.cmd_report(topic)["deep_research_report_markdown"]
        self.assertIn("研究方向判断与新观点", report)
        self.assertIn("市场交易的是民营商业闭环而非全国首次回收", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
