#!/usr/bin/env python3
"""Offline regressions for the topic-led Research Agenda."""
import os
import tempfile
import unittest

import crux_engine
import deepthink_orchestrator_v2 as orchestrator
import research_agenda_engine


def frame():
    return {
        "decision_question": "某事件如何改变产业与短线交易机会？",
        "as_of_date": "2026-08-10",
        "research_workplan": {
            "research_objective": "解释事件、市场传导、产业增量与可操作建议",
            "questions": [
                {
                    "question_id": "RQ1",
                    "question": "事件当前处于什么状态？",
                    "question_type": "FACT",
                    "why_it_matters": "决定事件窗口是否存在",
                    "success_condition": "找到官方时间与状态",
                    "initial_search_routes": ["官方公告"],
                    "linked_crux_id": "C1",
                },
                {
                    "question_id": "RQ2",
                    "question": "市场将如何交易该事件？",
                    "question_type": "MARKET",
                    "why_it_matters": "决定短线载体",
                    "success_condition": "形成事件到资金到载体链",
                    "initial_search_routes": ["市场数据"],
                    "linked_crux_id": "C2",
                },
                {
                    "question_id": "RQ3",
                    "question": "最大的二阶盲点是什么？",
                    "question_type": "FORWARD_LOOKING",
                    "why_it_matters": "决定前瞻性",
                    "success_condition": "找到能改变结论的二阶变量",
                    "initial_search_routes": ["产业链反向追踪"],
                    "linked_crux_id": "",
                },
            ],
            "research_directions": [
                {
                    "direction_id": "RD1",
                    "proposition": "官方窗口能够建立事件研究时点",
                    "direction_kind": "FACT_ROUTE",
                    "why_it_matters": "决定事件窗口是否存在",
                    "discriminating_test": "官方公告与非正式占位信息的效力不同",
                    "linked_question_ids": ["RQ1"],
                    "linked_crux_id": "C1",
                    "load_bearing": True,
                    "decision_impact": "HIGH",
                    "research_cost": "LOW",
                },
                {
                    "direction_id": "RD2",
                    "proposition": "市场优先交易事件稀缺性而非产业兑现",
                    "direction_kind": "MARKET_MECHANISM",
                    "why_it_matters": "决定短线载体排序",
                    "discriminating_test": "事件弹性载体与经济兑现载体的相对强弱",
                    "linked_question_ids": ["RQ2"],
                    "linked_crux_id": "C2",
                    "load_bearing": True,
                    "decision_impact": "HIGH",
                    "research_cost": "MEDIUM",
                },
            ],
        },
        "candidate_cruxes": [
            {"id": "C1"}, {"id": "C2"},
        ],
    }


def citation(source="项目方"):
    return {
        "claim": "官方披露事件窗口",
        "number": None,
        "source": source,
        "url": "https://official-project.com.cn/disclosure/2026/event-window.html",
        "date": "2026-08-10",
        "source_tier": "primary",
    }


class ResearchAgendaTests(unittest.TestCase):
    def test_explicit_workplan_becomes_primary_agenda(self):
        agenda = research_agenda_engine.initialize(frame())
        self.assertEqual(agenda["agenda_source"], "EXPLICIT_WORKPLAN")
        self.assertEqual(len(agenda["questions"]), 3)
        self.assertTrue(all(item["answer_status"] == "OPEN" for item in agenda["questions"]))

    def test_round_preserves_answer_challenge_and_blind_spot(self):
        state = {"research_agenda": research_agenda_engine.initialize(frame())}
        cit = citation()
        detective = {
            "crux_evidence": [{"crux_id": "C1", "evidence": [cit]}],
            "question_updates": [{
                "question_id": "RQ1",
                "answer_status": "ANSWERED",
                "answer": "官方已给出窗口，但仍可能调整。",
                "answer_is_inference": False,
                "evidence": [cit],
                "strongest_challenge": "天气与许可仍可改变窗口",
                "missing_information": "最终放行通知",
                "next_question": "延迟由技术、许可还是天气驱动？",
            }],
            "new_blind_spots": [{
                "statement": "窗口变化本身可能成为筹码催化",
                "why_missed": "只关注事件结果",
                "potential_impact": "改变事件前交易节奏",
                "linked_question_ids": ["RQ1"],
                "cheapest_test": "比较历次窗口变化后的量价",
            }],
            "new_research_questions": [{
                "question": "历次延期如何影响板块量价？",
                "question_type": "MARKET",
                "why_it_matters": "决定窗口前是否提前撤退",
                "success_condition": "完成事件研究",
                "search_routes": ["事件日行情"],
                "parent_question_id": "RQ1",
                "decision_change": "改变窗口前的事件交易节奏",
                "linked_crux_id": "C2",
                "introduced_by_blind_spot": "窗口变化本身可能成为筹码催化",
            }],
        }
        audit = research_agenda_engine.harvest_round(state, 1, detective, {})
        question = state["research_agenda"]["questions"][0]
        self.assertEqual(question["answer_status"], "ANSWERED")
        self.assertEqual(question["evidence_boundary"], "SINGLE_SOURCE")
        self.assertIn("天气", question["strongest_challenge"])
        self.assertEqual(len(audit["new_blind_spot_ids"]), 1)
        self.assertEqual(len(audit["new_question_ids"]), 1)

    def test_round_discovery_requires_lineage_and_has_one_global_budget(self):
        state = {"research_agenda": research_agenda_engine.initialize(frame())}

        def new_question(parent, suffix):
            return {
                "question": f"新问题{suffix}？",
                "question_type": "MARKET",
                "why_it_matters": f"改变判断{suffix}",
                "success_condition": f"观察到结果{suffix}",
                "search_routes": [f"路线{suffix}"],
                "decision_impact": "HIGH",
                "research_cost": "LOW",
                "parent_question_id": parent,
                "decision_change": f"改变候选{suffix}",
            }

        payload = {
            "new_research_questions": [
                new_question("RQ1", "A"),
                new_question("RQ2", "B"),
                new_question("RQ3", "C"),
                {"question": "无父问题？", "why_it_matters": "背景"},
            ],
            "new_blind_spots": [{
                "statement": "代理自称阻塞",
                "why_missed": "框架遗漏",
                "potential_impact": "也许改变结论",
                "linked_question_ids": ["RQ1"],
                "cheapest_test": "查一个官方页面",
                "decision_impact": "HIGH",
                "research_cost": "LOW",
                "blocks_current_recommendation": True,
            }],
        }
        audit = research_agenda_engine.harvest_round(state, 1, payload, {})
        self.assertEqual(len(audit["new_question_ids"]), 2)
        self.assertTrue(any(
            item["reason"] == "ROUND_DISCOVERY_BUDGET_EXHAUSTED"
            for item in audit["rejected_new_questions"]
        ))
        blind = state["research_agenda"]["blind_spots"][0]
        self.assertFalse(blind["blocks_current_recommendation"])

    def test_unbacked_citation_cannot_be_laundered_but_answer_survives(self):
        state = {"research_agenda": research_agenda_engine.initialize(frame())}
        payload = {
            "question_updates": [{
                "question_id": "RQ2",
                "answer_status": "PARTIAL",
                "answer": "资金可能先交易高弹性载体。",
                "answer_is_inference": True,
                "evidence": [citation("未出现在正式证据的来源")],
                "strongest_challenge": "可能只是板块贝塔",
                "missing_information": "相对强弱和换手",
                "next_question": "谁是市场实际选择的载体？",
            }]
        }
        research_agenda_engine.harvest_round(state, 1, payload, {})
        question = state["research_agenda"]["questions"][1]
        self.assertEqual(question["answer_status"], "PARTIAL")
        self.assertEqual(question["current_answer"], "资金可能先交易高弹性载体。")
        self.assertEqual(question["evidence"], [])
        self.assertEqual(question["evidence_boundary"], "HYPOTHESIS")

    def test_focus_reprioritizes_disputed_and_linked_questions(self):
        state = {"research_agenda": research_agenda_engine.initialize(frame())}
        state["research_agenda"]["questions"][1]["answer_status"] = "DISPUTED"
        focus = research_agenda_engine.focus_questions(state, ["C2"], limit=2)
        self.assertEqual(focus[0]["question_id"], "RQ2")

    def test_dispatch_packet_keeps_current_semantics_not_full_history(self):
        state = {"research_agenda": research_agenda_engine.initialize(frame())}
        question = state["research_agenda"]["questions"][0]
        question.update({
            "blocks_current_recommendation": True,
            "answer_status": "PARTIAL",
            "current_answer": "当前答案",
            "evidence_boundary": "SINGLE_SOURCE",
            "answer_variants": [{
                "round": 1,
                "role": "detective",
                "answer_status": "PARTIAL",
                "answer": "当前答案",
                "evidence_boundary": "SINGLE_SOURCE",
                "evidence": [citation()],
            }],
            "evidence": [{**citation(), "evidence_id": "EV-1", "stance": "SUPPORT"}],
        })
        packet = research_agenda_engine.dispatch_questions(state, limit=1)[0]
        self.assertNotIn("answer_variants", packet)
        self.assertNotIn("evidence", packet)
        self.assertEqual(packet["history_summary"]["variant_count"], 1)
        self.assertEqual(packet["evidence_refs"][0]["evidence_id"], "EV-1")

    def test_later_unsupported_conflict_cannot_erase_prior_supported_answer(self):
        state = {"research_agenda": research_agenda_engine.initialize(frame())}
        cit = citation()
        research_agenda_engine.harvest_round(state, 1, {
            "crux_evidence": [{"crux_id": "C1", "evidence": [cit]}],
            "question_updates": [{
                "question_id": "RQ1", "answer_status": "ANSWERED",
                "answer": "官方窗口已经披露。", "answer_is_inference": False,
                "evidence": [cit], "strongest_challenge": "", "missing_information": "",
                "next_question": "窗口是否会变？",
            }],
        }, {})
        research_agenda_engine.harvest_round(state, 2, {}, {
            "question_updates": [{
                "question_id": "RQ1", "answer_status": "DISPUTED",
                "answer": "窗口可能只是非正式占位。", "answer_is_inference": True,
                "evidence": [], "strongest_challenge": "正式通知措辞不清",
                "missing_information": "最终放行", "next_question": "文件效力是什么？",
            }],
        })
        question = state["research_agenda"]["questions"][0]
        self.assertEqual(question["answer_status"], "ANSWERED")
        self.assertEqual(question["evidence_boundary"], "SINGLE_SOURCE")
        self.assertEqual(question["current_answer"], "官方窗口已经披露。")
        self.assertIn("正式通知措辞不清", question["strongest_challenge"])
        self.assertEqual(len(question["answer_variants"]), 2)

    def test_unified_evidence_binds_question_and_direction_without_crux_wrapper(self):
        state = {
            "research_agenda": research_agenda_engine.initialize(frame()),
            "research_runtime": {"authorized_rounds": 1},
        }
        cit = citation()
        cit.update({
            "evidence_id": "EV-R1-D-001",
            "question_ids": ["RQ1"],
            "direction_ids": ["RD1"],
            "stance": "SUPPORT",
        })
        payload = {
            "evidence_items": [cit],
            "question_updates": [{
                "question_id": "RQ1",
                "answer_status": "ANSWERED",
                "answer": "官方窗口足以建立当前事件研究时点。",
                "answer_is_inference": False,
                "evidence_ids": ["EV-R1-D-001"],
                "strongest_challenge": "窗口仍可能调整",
                "missing_information": "最终放行",
                "next_question": "延期原因是什么？",
            }],
            "direction_updates": [{
                "direction_id": "RD1",
                "research_judgment": "SUPPORTED",
                "next_move": "ANSWER",
                "rationale": "项目方具体页面给出可核日期。",
                "evidence_ids": ["EV-R1-D-001"],
                "strongest_challenge": "窗口并非最终放行",
                "unresolved_question": "",
            }],
        }
        audit = research_agenda_engine.harvest_round(state, 1, payload, {})
        agenda = state["research_agenda"]
        self.assertEqual(audit["accepted_evidence_ids"], ["EV-R1-D-001"])
        self.assertEqual(agenda["questions"][0]["evidence"][0]["evidence_id"], "EV-R1-D-001")
        direction = next(
            item for item in agenda["research_directions"]
            if item["direction_id"] == "RD1"
        )
        self.assertEqual(direction["research_judgment"], "SUPPORTED")
        self.assertEqual(direction["next_move"], "ANSWER")
        self.assertEqual(direction["evidence_ids"], ["EV-R1-D-001"])
        self.assertEqual(direction["evidence_boundary"], "SINGLE_SOURCE")

    def test_duplicate_evidence_tuple_is_stored_once_and_aliases_canonical_id(self):
        state = {"research_agenda": research_agenda_engine.initialize(frame())}
        first = citation("项目方标签")
        first.update({
            "evidence_id": "EV-FIRST",
            "question_ids": ["RQ1"],
            "direction_ids": [],
            "stance": "SUPPORT",
        })
        duplicate = dict(first)
        duplicate.update({
            "evidence_id": "EV-ALIAS",
            "source": "另一个代理写的来源标签",
        })
        # Same claim/URL/date is one evidence fact even when an agent invents a
        # different source label or ID for it.
        audit = research_agenda_engine.harvest_round(
            state, 1,
            {"evidence_items": [first]},
            {
                "evidence_items": [duplicate],
                "question_updates": [{
                    "question_id": "RQ1",
                    "answer_status": "ANSWERED",
                    "answer": "官方窗口已披露。",
                    "answer_is_inference": False,
                    "evidence_ids": ["EV-ALIAS"],
                    "strongest_challenge": "仍可能调整",
                    "missing_information": "最终放行",
                    "next_question": "窗口是否变化？",
                }],
            },
        )
        agenda = state["research_agenda"]
        self.assertEqual(len(agenda["evidence_items"]), 1)
        self.assertEqual(audit["accepted_evidence_ids"], ["EV-FIRST"])
        self.assertEqual(
            audit["duplicate_evidence_aliases"][0]["canonical_evidence_id"],
            "EV-FIRST",
        )
        self.assertEqual(agenda["questions"][0]["evidence"][0]["evidence_id"], "EV-FIRST")

    def test_future_dated_evidence_is_rejected_at_as_of_boundary(self):
        state = {"research_agenda": research_agenda_engine.initialize(frame())}
        future = citation()
        future.update({
            "evidence_id": "EV-FUTURE",
            "date": "2026-08-11",
            "question_ids": ["RQ1"],
            "direction_ids": [],
            "stance": "SUPPORT",
        })
        audit = research_agenda_engine.harvest_round(
            state, 1, {"evidence_items": [future]}, {}
        )
        self.assertEqual(audit["accepted_evidence_ids"], [])
        self.assertEqual(
            audit["rejected_evidence_items"][0]["reason"],
            "EVIDENCE_AFTER_AS_OF_DATE",
        )
        self.assertEqual(state["research_agenda"]["evidence_items"], [])

    def test_same_tier_answer_disagreement_stays_disputed(self):
        state = {"research_agenda": research_agenda_engine.initialize(frame())}
        support = citation("issuer-one")
        support.update({
            "evidence_id": "EV-SUPPORT", "question_ids": ["RQ1"],
            "direction_ids": [], "stance": "SUPPORT",
        })
        challenge = citation("regulator-two")
        challenge.update({
            "evidence_id": "EV-CHALLENGE", "question_ids": ["RQ1"],
            "direction_ids": [], "stance": "CHALLENGE",
            "url": "https://regulator-two.gov.cn/notice/window.html",
        })
        detective = {
            "evidence_items": [support],
            "question_updates": [{
                "question_id": "RQ1", "answer_status": "ANSWERED",
                "answer": "现有公告足以确认窗口。", "answer_is_inference": False,
                "evidence_ids": ["EV-SUPPORT"], "strongest_challenge": "可能调整",
                "missing_information": "", "next_question": "",
            }],
        }
        inquisitor = {
            "evidence_items": [challenge],
            "question_updates": [{
                "question_id": "RQ1", "answer_status": "PARTIAL",
                "answer": "监管条件尚未满足，窗口仍非最终结论。",
                "answer_is_inference": False,
                "evidence_ids": ["EV-CHALLENGE"],
                "strongest_challenge": "项目方公告仍具参考价值",
                "missing_information": "最终许可", "next_question": "许可何时落地？",
            }],
        }
        research_agenda_engine.harvest_round(state, 1, detective, inquisitor)
        question = state["research_agenda"]["questions"][0]
        self.assertEqual(question["answer_status"], "DISPUTED")
        self.assertEqual(question["answer_resolution"], "CONFLICTED")
        self.assertIn("detective:", question["current_answer"])
        self.assertIn("inquisitor:", question["current_answer"])

    def test_evidence_id_cannot_cross_bind_to_unlisted_question_or_direction(self):
        state = {"research_agenda": research_agenda_engine.initialize(frame())}
        cit = citation()
        cit.update({
            "evidence_id": "EV-R1-D-SCOPED",
            "question_ids": ["RQ1"],
            "direction_ids": ["RD1"],
            "stance": "SUPPORT",
        })
        research_agenda_engine.harvest_round(state, 1, {
            "evidence_items": [cit],
            "question_updates": [{
                "question_id": "RQ2",
                "answer_status": "PARTIAL",
                "answer": "该证据被错误引用到另一个问题。",
                "answer_is_inference": False,
                "evidence_ids": ["EV-R1-D-SCOPED"],
                "strongest_challenge": "证据范围不匹配",
                "missing_information": "RQ2 的直接证据",
                "next_question": "如何建立市场机制？",
            }],
            "direction_updates": [{
                "direction_id": "RD2",
                "research_judgment": "SUPPORTED",
                "next_move": "ANSWER",
                "rationale": "错误借用了 RD1 证据。",
                "evidence_ids": ["EV-R1-D-SCOPED"],
                "strongest_challenge": "证据范围不匹配",
                "unresolved_question": "市场证据是什么？",
            }],
        }, {})
        agenda = state["research_agenda"]
        question = next(
            item for item in agenda["questions"] if item["question_id"] == "RQ2"
        )
        direction = next(
            item for item in agenda["research_directions"]
            if item["direction_id"] == "RD2"
        )
        self.assertEqual(question["evidence"], [])
        self.assertEqual(question["evidence_boundary"], "HYPOTHESIS")
        self.assertEqual(direction["evidence_ids"], [])
        self.assertEqual(direction["evidence_boundary"], "HYPOTHESIS")

    def test_challenge_can_open_and_prioritize_a_new_viewpoint(self):
        state = {
            "research_agenda": research_agenda_engine.initialize(frame()),
            "research_runtime": {"authorized_rounds": 1},
            "rounds": [{}],
        }
        state["research_agenda"]["questions"][1]["research_cost"] = "LOW"
        payload = {
            "new_research_directions": [{
                "direction_id": "RD-NEW-MARKET",
                "proposition": "市场交易的是民营商业闭环而非全国首次",
                "direction_kind": "MARKET_MECHANISM",
                "why_it_matters": "会改变事件稀缺性和短线载体排序",
                "discriminating_test": "比较先发国家队与民营闭环事件的板块相对表现",
                "linked_question_ids": ["RQ2"],
                "linked_crux_id": "",
                "parent_direction_ids": ["RD2"],
                "origin_reason": "先发事实挑战了全国首次叙事",
                "load_bearing": True,
                "decision_impact": "HIGH",
                "research_cost": "LOW",
            }],
            "direction_updates": [{
                "direction_id": "RD2",
                "research_judgment": "CHALLENGED",
                "next_move": "OPEN_NEW_DIRECTION",
                "rationale": "全国首次叙事已被先发事实削弱。",
                "evidence_ids": [],
                "strongest_challenge": "民营属性仍可能保留独立稀缺性",
                "unresolved_question": "市场究竟给哪类稀缺性定价？",
            }],
            "question_updates": [{
                "question_id": "RQ2",
                "answer_status": "PARTIAL",
                "answer": "原稀缺性解释被削弱，但民营商业闭环可能是新主线。",
                "answer_is_inference": True,
                "evidence_ids": [],
                "strongest_challenge": "也可能只是商业航天板块贝塔",
                "missing_information": "事件窗口相对强弱",
                "next_question": "资金交易全国首次还是民营闭环？",
            }],
        }
        research_agenda_engine.harvest_round(state, 1, payload, {})
        focus = research_agenda_engine.focus_directions(
            state, question_ids=["RQ2"], limit=2
        )
        self.assertEqual(focus[0]["direction_id"], "RD2")
        self.assertIn("RD-NEW-MARKET", [item["direction_id"] for item in focus])
        control = research_agenda_engine.control_decision(state, round_num=1)
        self.assertIn("NEW_VIEWPOINT_OPENED", control["reason_codes"])
        self.assertEqual(control["recommended_action"], "RESEARCH_MORE_IF_AUTHORIZED")


class AgendaOrchestratorIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_scratch = os.environ.get("TRADE_NOTHING_SCRATCH_DIR")
        self.old_evolution = os.environ.get("TRADE_NOTHING_EVOLUTION_PATH")
        os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.tmp.name
        os.environ["TRADE_NOTHING_EVOLUTION_PATH"] = os.path.join(self.tmp.name, "missing.md")

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

    def test_frame_v2_without_hypothesis_garden_dispatches_agenda(self):
        cruxes = []
        for cid, label, role in (
            ("C1", "事件状态与原因", "THESIS_HINGE"),
            ("C2", "市场与定价", "PRICING"),
        ):
            cruxes.append({
                "id": cid,
                "label": label,
                "logic_role": role,
                "definition": f"回答 {label}",
                "monitor_anchor": f"{label}的官方或市场数据",
                "falsifier": f"数据否定 {label}",
                "evidence_plan": [
                    {
                        "plan_id": f"SP-{cid}-1",
                        "publisher_class": "ISSUER_OR_FILING",
                        "target_claim": f"{label}的项目方事实",
                        "search_query": f"项目方 {label}",
                    },
                    {
                        "plan_id": f"SP-{cid}-2",
                        "publisher_class": "EXCHANGE_OR_MARKET_DATA",
                        "target_claim": f"{label}的市场数据",
                        "search_query": f"市场数据 {label}",
                    },
                ],
                "catalyst_window": {
                    "event": f"复核 {label}",
                    "expected_by": "2026-10-10",
                    "date_status": "REVIEW_CHECKPOINT",
                    "basis_claim_id": "P1",
                },
            })
        workplan = frame()["research_workplan"]
        workplan["questions"].append({
            "question_id": "RQ4",
            "question": "哪个具体载体最值得条件性关注？",
            "question_type": "CANDIDATE",
            "why_it_matters": "决定报告建议",
            "success_condition": "比较具名载体、触发、失效和筹码",
            "initial_search_routes": ["公司与行情数据"],
            "linked_crux_id": "C2",
        })
        raw = {
            "frame_schema_version": "trade-nothing.frame.v2",
            "decision_question": "未来3个月该事件如何影响市场与具体载体？",
            "question_type": "CONJUNCTIVE",
            "research_intent": "OPPORTUNITY_DISCOVERY",
            "logic_graph": {
                "root_id": "Q1",
                "nodes": [
                    {"id": "Q1", "node_type": "QUESTION", "label": "root"},
                    {"id": "C1", "node_type": "CRUX", "label": "event"},
                    {"id": "C2", "node_type": "CRUX", "label": "market"},
                ],
                "edges": [
                    {"from": "C1", "to": "Q1", "relation": "REQUIRED_FOR"},
                    {"from": "C2", "to": "Q1", "relation": "PRICING_FOR"},
                ],
            },
            "horizon": "3-6M",
            "as_of_date": "2026-08-10",
            "forecast_target_date": "",
            "unit_of_analysis": "事件与上市载体",
            "thesis_seed": "方向未知，先回答事实、市场和定价问题。",
            "research_workplan": workplan,
            "premise_audit": [{
                "id": "P1", "claim": "事件在研究窗口内可观察",
                "status": "HYPOTHESIS", "as_of": "UNKNOWN", "source_url": None,
                "required_primary_source": "项目方正式公告", "use": "冻结研究窗口",
            }],
            "candidate_cruxes": cruxes,
            "forbidden_consensus": ["行业增长等于所有股票受益"],
            "no_edge_precheck": {
                "is_researchable": True,
                "basis_type": "TESTABILITY",
                "basis_claim_ids": ["P1"],
                "reason": "事件、市场反应与价格均可观察。",
            },
            "suggested_max_rounds": 8,
        }
        result = orchestrator.cmd_init("agenda-no-garden", raw)
        self.assertEqual(result["status"], "dispatch_subagents")
        self.assertEqual(result["research_agenda"]["question_count"], 4)
        self.assertIn("Research Agenda", result["detective_prompt"])
        self.assertEqual(result["landscape_assignments"]["detective"], [])
        stored = orchestrator._load("agenda-no-garden")
        self.assertEqual(stored["frame_contract"]["agenda_source"], "EXPLICIT_WORKPLAN")
        self.assertNotIn("landscape_map", stored)


if __name__ == "__main__":
    unittest.main(verbosity=2)
