#!/usr/bin/env python3
"""Offline product regressions for topic-led CandidateMap and Deep Research Report."""
from copy import deepcopy
import hashlib
import json
import unittest

import crux_engine
import execution_integrity
import market_bridge_engine
import market_map_engine
import research_agenda_engine
import report_v2


def state(topic="朱雀三号遥二回收与商业航天机会"):
    st = crux_engine.new_state(
        topic,
        "朱雀三号遥二成功回收如何映射到A股机会？",
        "事件前后1-3个月",
        [{"id": "C1", "label": "回收验证", "monitor_anchor": "官方发射与回收结果"}],
    )
    st["frame_contract"] = {"as_of_date": "2026-08-09"}
    return st


def citation(host, claim):
    return {
        "claim": claim,
        "number": None,
        "source": host,
        "url": f"https://{host}.com.cn/disclosure/2026/0809/item.html",
        "date": "2026-08-09",
        "source_tier": "primary",
    }


def candidate(name="超捷股份", ticker="301005", **overrides):
    item = {
        "candidate": name,
        "ticker": ticker,
        "asset_type": "LISTED_EQUITY",
        "market_role": "EVENT_BETA",
        "setup_types": ["EVENT_SETUP"],
        "mechanism": "回收验证 -> 商业火箭关注度上升 -> 高弹性供应链载体获得事件资金",
        "economic_exposure": "火箭结构件业务弹性仍待订单核验",
        "catalyst": "遥二发射及一级回收结果",
        "catalyst_window": {"event": "发射窗口", "expected_by": "2026-08-20"},
        "invalidation": "再次延期、发射失败或回收失败且市场预期转弱",
        "price_or_expectation": "从阶段高点已有回撤，市场仍计入部分成功预期（fixture 假说）",
        "crowding_or_position": "近期换手回落但前高仍有套牢盘（fixture 假说）",
        "strongest_alternative_explanation": "上涨仅由商业航天板块贝塔驱动",
        "cheap_discriminating_test": "比较发射窗口前5日相对板块强弱与换手",
        "scenario_fit": {
            "完整回收": "事件弹性最强，但仍需区分情绪与订单兑现",
            "入轨成功但回收失败": "题材保留、复用逻辑受损",
            "发射或入轨失败": "事件路径失效，失败对冲更重要",
            "再次延期": "时间价值衰减，拥挤资金可能先撤离",
        },
        "evidence": [],
    }
    item.update(overrides)
    return item


def scoped_field_evidence(prefix="candidate", economic=False):
    fields = {
        "mechanism": [citation(
            f"{prefix}-mechanism", "回收验证事件与公司供应业务链相关"
        )],
        "catalyst": [citation(f"{prefix}-catalyst", "官方披露可核验事件窗口")],
        "price_or_expectation": [citation(f"{prefix}-price", "行情数据形成价格锚")],
        "crowding_or_position": [citation(f"{prefix}-crowding", "换手数据形成筹码锚")],
        "economic_exposure": [],
    }
    if economic:
        fields["economic_exposure"] = [
            citation(f"{prefix}-economics", "公司披露高频供应相关业务收入边界")
        ]
    return fields


def canonical_field_packet(prefix="candidate", economic=False):
    citations = scoped_field_evidence(prefix, economic=economic)
    evidence_items = []
    field_evidence_ids = {field: [] for field in citations}
    for field, items in citations.items():
        for index, item in enumerate(items, 1):
            evidence_id = f"EV-{prefix.upper()}-{field.upper()}-{index}"
            evidence_items.append({
                **item,
                "evidence_id": evidence_id,
                "question_ids": ["RQ3", "RQ4"],
                "direction_ids": [],
                "stance": "CONTEXT",
            })
            field_evidence_ids[field].append(evidence_id)
    return evidence_items, field_evidence_ids


def host_snapshot(name, ticker, exchange, evidence_ids, salt):
    candidate_url = f"https://fixture-market.example.cn/{ticker}/2026-08-09"
    candidate_source = {
        "name": name, "ticker": ticker, "exchange": exchange,
        "source": "fixture", "source_class": "STRUCTURED_MARKET_DATA",
        "source_url": candidate_url,
    }
    snapshot_core = {
        "as_of_date": "2026-08-09",
        "benchmark": "商业航天固定篮子",
        "theme_basket": "商业航天固定篮子",
        "latest_observed_session_on_or_before_as_of": True,
        "excess_20d": 8.0,
        "volume_ratio_20d": 1.4,
        "evidence_ids": evidence_ids,
    }
    snapshot_hash = hashlib.sha256(json.dumps(
        snapshot_core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    receipt = {
        "schema_version": "trade-nothing.market-snapshot-adapter.v1",
        "input_sha256": hashlib.sha256(f"input:{salt}".encode()).hexdigest(),
        "market_snapshot_sha256": snapshot_hash,
        "candidate_identity_sha256": hashlib.sha256(json.dumps(
            candidate_source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest(),
        "research_as_of_date": "2026-08-09",
        "market_session_date": "2026-08-09",
        "candidate_observation_count": 61,
        "benchmark_observation_count": 61,
        "candidate_source_url": candidate_url,
        "benchmark_source_url": "https://fixture-market.example.cn/index/2026-08-09",
    }
    upstream_core = {
        "schema_version": "trade-nothing.free-market-acquisition-receipt.v1",
        "request_sha256": hashlib.sha256(f"request:{salt}".encode()).hexdigest(),
        "provider": "CSV",
        "provider_version": "fixture",
        "research_as_of_date": "2026-08-09",
        "market_session_date": "2026-08-09",
        "adjustment": "NONE",
        "series_sha256": {
            "candidate": hashlib.sha256(f"candidate:{salt}".encode()).hexdigest(),
            "benchmark": hashlib.sha256(f"benchmark:{salt}".encode()).hexdigest(),
        },
    }
    upstream = dict(upstream_core)
    upstream["receipt_id"] = hashlib.sha256(json.dumps(
        upstream_core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    receipt["upstream_acquisition_receipt_id"] = upstream["receipt_id"]
    receipt["receipt_id"] = hashlib.sha256(json.dumps(
        receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return {
        "schema_version": "trade-nothing.market-snapshot-adapter.v1",
        "candidate": candidate_source,
        "market_snapshot": {**snapshot_core, "adapter_receipt": receipt},
        "sources": [],
        "upstream_acquisition_receipt": upstream,
    }


def attach_verified_round(st, round_num, detective, inquisitor):
    judge = {"fixture": "judge"}
    dispatch = {
        "detective_prompt": f"detective fixture round {round_num}",
        "inquisitor_prompt": f"inquisitor fixture round {round_num}",
        "judge_prompt": f"judge fixture round {round_num}",
    }
    payloads = {"detective": detective, "inquisitor": inquisitor, "judge": judge}
    receipt = execution_integrity.build_codex_receipt(
        round_num,
        dispatch,
        payloads,
        {
            "detective": f"/fixture/detective/{round_num}",
            "inquisitor": f"/fixture/inquisitor/{round_num}",
            "judge": f"/fixture/judge/{round_num}",
        },
    )
    audit = execution_integrity.validate_round_receipt(
        receipt, round_num, dispatch, detective, inquisitor, judge
    )
    st.setdefault("rounds", []).append({
        "round": round_num,
        "detective_raw": detective,
        "inquisitor_raw": inquisitor,
        "judge_host_raw": judge,
        "execution_receipt": receipt,
        "execution_integrity": audit,
    })


def full_coverage():
    return {
        "concrete_instrument_search": True,
        "alternative_paths": True,
        "price_and_crowding": True,
        "event_window": True,
        "note": "已覆盖具名载体、替代路径、价格筹码和事件窗口",
        "routes": [
            {
                "coverage_field": field,
                "query": f"fixture bounded query for {field}",
                "checked_urls": [f"https://coverage-source.org/research/{field}"],
                "outcome": "FOUND",
            }
            for field in market_map_engine.COVERAGE_FIELDS
        ],
    }


class CandidateMapTests(unittest.TestCase):
    def test_uncited_concrete_candidate_is_preserved_as_hypothesis(self):
        st = state()
        audit = market_map_engine.harvest_round(
            st, 1, {"market_map_candidates": [candidate()]}, {}
        )
        self.assertEqual(audit["accepted"], 1)
        view = market_map_engine.report_view(st)
        self.assertEqual(view["candidates"][0]["ticker"], "301005")
        self.assertEqual(view["candidates"][0]["evidence_boundary"], "HYPOTHESIS")
        self.assertEqual(view["candidates"][0]["attention_band"], "EXPLORE")
        self.assertEqual(view["result_type"], "EXPLORE")
        self.assertIn("缺字段证据", report_v2.render(st))

    def test_listed_equity_without_ticker_and_abstract_mapping_are_rejected(self):
        st = state()
        wrong = candidate(
            name="可重复使用火箭产业链受益逻辑",
            ticker=None,
            mechanism="回收成功 -> 行业受益",
        )
        audit = market_map_engine.harvest_round(
            st, 1, {"market_map_candidates": [wrong]}, {}
        )
        self.assertEqual(audit["rejected_reasons"]["listed_equity_ticker_required"], 1)
        self.assertEqual(market_map_engine.summary(st)["candidate_map_count"], 0)

    def test_unknown_is_not_a_listed_instrument_identity(self):
        st = state()
        audit = market_map_engine.harvest_round(
            st, 1, {"market_map_candidates": [candidate(ticker="UNKNOWN")]}, {}
        )
        self.assertEqual(
            audit["rejected_reasons"]["listed_equity_valid_ticker_required"], 1
        )
        self.assertEqual(market_map_engine.summary(st)["candidate_map_count"], 0)

    def test_same_ticker_merges_roles_and_independent_sources(self):
        st = state()
        first = candidate(field_evidence={
            "mechanism": [citation("issuer-a", "公司披露火箭结构件业务")]
        })
        second = candidate(
            name="超捷股份有限公司",
            market_role="ECONOMIC_CAPTURE",
            setup_types=["ECONOMIC_SETUP"],
            field_evidence={
                "mechanism": [citation("exchange-b", "问询回复披露业务收入边界")]
            },
        )
        market_map_engine.harvest_round(st, 1, {"market_map_candidates": [first]}, {})
        audit = market_map_engine.harvest_round(
            st, 2, {}, {"market_map_candidates": [second]}
        )
        self.assertEqual(audit["merged_existing"], 1)
        item = market_map_engine.report_view(st)["candidates"][0]
        self.assertEqual(item["evidence_boundary"], "FACT")
        self.assertEqual(item["market_roles"], ["ECONOMIC_CAPTURE", "EVENT_BETA"])
        self.assertEqual(item["setup_types"], ["ECONOMIC_SETUP", "EVENT_SETUP"])

    def test_result_types_require_explicit_coverage_for_no_setup(self):
        st = state()
        incomplete = candidate(catalyst="UNKNOWN", crowding_or_position="UNKNOWN")
        market_map_engine.harvest_round(
            st, 1, {"market_map_candidates": [incomplete]}, {}
        )
        self.assertEqual(market_map_engine.report_view(st)["result_type"], "EXPLORE")
        market_map_engine.harvest_round(
            st, 2, {"market_map_coverage": full_coverage()}, {}
        )
        self.assertEqual(
            market_map_engine.report_view(st)["result_type"], "NO_USABLE_SETUP"
        )

    def test_coverage_checkboxes_without_explanation_cannot_claim_no_setup(self):
        st = state()
        market_map_engine.harvest_round(
            st, 1,
            {"market_map_coverage": {
                "concrete_instrument_search": True,
                "alternative_paths": True,
                "price_and_crowding": True,
                "event_window": True,
            }},
            {},
        )
        self.assertEqual(market_map_engine.report_view(st)["result_type"], "EXPLORE")

    def test_coverage_claim_and_note_without_routes_cannot_claim_no_setup(self):
        st = state()
        claimed = full_coverage()
        claimed.pop("routes")
        market_map_engine.harvest_round(
            st, 1, {"market_map_coverage": claimed}, {}
        )
        view = market_map_engine.report_view(st)
        self.assertEqual(view["result_type"], "EXPLORE")
        self.assertTrue(all(view["coverage_claims"].values()))
        self.assertFalse(any(view["coverage"].values()))

    def test_coverage_route_requires_a_concrete_non_reserved_url(self):
        st = state()
        audit = market_map_engine.harvest_round(st, 1, {
            "market_map_coverage": {
                "concrete_instrument_search": True,
                "note": "仅声称查过，但没有可审计页面",
                "routes": [{
                    "coverage_field": "concrete_instrument_search",
                    "query": "fixture query",
                    "checked_urls": ["https://example.com"],
                    "outcome": "NO_RESULT",
                }],
            }
        }, {})
        self.assertIn(
            "invalid_coverage_checked_url", audit["coverage_route_rejections"]
        )
        self.assertFalse(
            market_map_engine.report_view(st)["coverage"]["concrete_instrument_search"]
        )

    def test_event_and_economic_setups_are_separate(self):
        st = state()
        payload = {
            "market_map_candidates": [
                candidate(field_evidence=scoped_field_evidence("event")),
                candidate(
                    name="斯瑞新材",
                    ticker="688102",
                    market_role="ECONOMIC_CAPTURE",
                    setup_types=["ECONOMIC_SETUP"],
                    mechanism="高频发射 -> 液体火箭发动机材料需求 -> 锻件订单兑现",
                    field_evidence=scoped_field_evidence("economic", economic=True),
                ),
            ]
        }
        market_map_engine.harvest_round(st, 1, payload, {})
        view = market_map_engine.report_view(st)
        self.assertEqual(len(view["event_setups"]), 1)
        self.assertEqual(len(view["economic_setups"]), 1)

    def test_conflicting_mechanisms_do_not_become_setup_ready(self):
        st = state()
        first = candidate(field_evidence=scoped_field_evidence("first"))
        second = candidate(
            mechanism="回收验证与公司收入无直接关系，仅有板块情绪映射",
            field_evidence=scoped_field_evidence("second"),
            field_update_modes={"mechanism": "CHALLENGE"},
        )
        market_map_engine.harvest_round(st, 1, {"market_map_candidates": [first]}, {})
        market_map_engine.harvest_round(st, 2, {}, {"market_map_candidates": [second]})
        item = market_map_engine.report_view(st)["candidates"][0]
        self.assertEqual(item["attention_band"], "EXPLORE")
        self.assertIn(
            "UNRESOLVED_FIELD_CONFLICT",
            item["setup_checks"]["EVENT_SETUP"]["reason_codes"],
        )

    def test_later_refinement_replaces_snapshot_without_creating_conflict(self):
        st = state()
        first = candidate(
            mechanism="回收验证带来板块关注",
            field_evidence=scoped_field_evidence("first"),
        )
        refined = candidate(
            mechanism="回收验证 -> 复用预期 -> 高频供应链获得事件关注",
            field_evidence=scoped_field_evidence("second"),
            field_update_modes={"mechanism": "REFINE"},
        )
        market_map_engine.harvest_round(st, 1, {"market_map_candidates": [first]}, {})
        market_map_engine.harvest_round(st, 2, {}, {"market_map_candidates": [refined]})
        item = market_map_engine.report_view(st)["candidates"][0]
        self.assertEqual(item["mechanism"], refined["mechanism"])
        self.assertEqual(item.get("field_conflicts", {}), {})
        self.assertEqual(item["attention_band"], "SETUP_CANDIDATE")


class DeepResearchReplayTests(unittest.TestCase):
    def test_zhuque_replay_surfaces_market_logic_and_concrete_setups(self):
        st = state()
        st["research_agenda"] = research_agenda_engine.initialize({
            "decision_question": st["decision_question"],
            "candidate_cruxes": [{"id": "C1"}],
            "research_workplan": {
                "research_objective": "解释回收、延期、产业增量和短线条件性机会",
                "questions": [
                    {"question_id": "RQ1", "question": "什么算成功回收？", "question_type": "FACT", "why_it_matters": "定义事件结果", "success_condition": "拆分入轨和回收", "initial_search_routes": ["项目方任务定义"], "linked_crux_id": "C1"},
                    {"question_id": "RQ2", "question": "为什么延期到当前窗口？", "question_type": "CAUSAL", "why_it_matters": "判断风险是否消除", "success_condition": "区分技术、许可和天气", "initial_search_routes": ["项目方与监管信息"], "linked_crux_id": "C1"},
                    {"question_id": "RQ3", "question": "市场会先交易什么？", "question_type": "MARKET", "why_it_matters": "决定短线载体", "success_condition": "形成资金传导链", "initial_search_routes": ["事件行情"], "linked_crux_id": "C1"},
                    {"question_id": "RQ4", "question": "最大产业链增量在哪里？", "question_type": "FORWARD_LOOKING", "why_it_matters": "区分题材与利润", "success_condition": "定位订单利润池", "initial_search_routes": ["供应链披露"], "linked_crux_id": "C1"},
                ],
            },
        })
        event_evidence, event_field_ids = canonical_field_packet(
            "replay-event", economic=True
        )
        economic_evidence, economic_field_ids = canonical_field_packet(
            "replay-economic", economic=True
        )
        det = {
            "evidence_items": event_evidence + economic_evidence,
            "question_updates": [{
                "question_id": "RQ3", "answer_status": "PARTIAL",
                "answer": "短线资金可能先交易高辨识度事件 beta，再分化到有订单兑现的供应商。",
                "answer_is_inference": True, "evidence": [],
                "strongest_challenge": "板块可能在利好兑现时高开低走",
                "missing_information": "窗口前相对强弱和换手",
                "next_question": "谁在回调后仍保持相对强势？",
            }],
            "new_blind_spots": [{
                "statement": "再次延期本身可能比最终结果更先改变筹码结构",
                "why_missed": "原框架只分析成功与失败",
                "potential_impact": "改变窗口前短线优先级和放弃时点",
                "linked_question_ids": ["RQ2", "RQ3"],
                "cheapest_test": "回放历次窗口变化后的相对强弱与换手",
            }],
            "new_research_questions": [],
            "market_mechanics": {
                "event_change": "遥二将同时验证入轨与一级回收",
                "narrative": "成功会把叙事从可发射推进到可复用",
                "capital_flow": "短线先寻找高弹性商业航天载体",
                "carrier_selection": "事件资金偏好辨识度、弹性和近期回调后的筹码结构",
                "crowding_path": "预期过满时利好兑现可能转为兑现卖出",
                "realization_path": "长期增量取决于发射频次、复用成本与供应商订单",
                "strongest_alternative": "单次成功不等于商业化降本成立",
            },
            "value_transfer_paths": [{
                "path_key": "VT1",
                "origin_question_ids": ["RQ3", "RQ4"],
                "origin_direction_ids": [],
                "state_change": "回收验证提高市场对可复用和发射频次的预期",
                "constraint_change": "高频可靠供应与复用维护成为新约束",
                "profit_pool_shift": "价值由单次事件标签分化到高频供应和发动机材料",
                "economic_winners": ["高频结构件与发动机材料供应商"],
                "economic_losers": ["只有商业航天标签但无订单暴露的公司"],
                "realization_horizon": "EARNINGS_QUARTERS",
                "falsifier": "回收后复飞频率和供应商订单均未改善",
                "evidence_ids": [
                    event_field_ids["mechanism"][0],
                    event_field_ids["economic_exposure"][0],
                ],
            }],
            "market_phase_snapshot": {
                "as_of_date": "2026-08-09",
                "horizon": "TACTICAL_WEEKS",
                "phase": "IGNITION",
                "dominant_pricing_variable": "回收事件预期和高辨识度载体弹性",
                "industry_clock": "技术验证早于订单和利润兑现",
                "market_clock": "事件预期已经形成但尚未完成财务验证",
                "strongest_alternative_phase": "市场可能已进入拥挤兑现阶段",
                "falsifier": "事件临近时领涨载体持续弱于板块和基准",
                "evidence_ids": [event_field_ids["price_or_expectation"][0]],
            },
            "carrier_universe_snapshots": [
                {
                    "universe_key": "EU1",
                    "universe_type": "ECONOMIC_EXPOSURE",
                    "as_of_date": "2026-08-09",
                    "horizon": "TACTICAL_WEEKS",
                    "universe_name": "商业航天经济暴露池",
                    "construction_rule": "固定具名供应链候选并核对公司业务收入证据",
                    "benchmark": "商业航天固定篮子",
                    "evidence_ids": [event_field_ids["economic_exposure"][0]],
                    "members": [
                        {"candidate": "超捷股份", "ticker": "301005", "exchange": "XSHE", "evidence_ids": [event_field_ids["economic_exposure"][0]]},
                        {"candidate": "斯瑞新材", "ticker": "688102", "exchange": "XSHG", "evidence_ids": [economic_field_ids["economic_exposure"][0]]},
                    ],
                },
                {
                    "universe_key": "MU1",
                    "universe_type": "MARKET_TRADING",
                    "as_of_date": "2026-08-09",
                    "horizon": "TACTICAL_WEEKS",
                    "universe_name": "商业航天市场交易池",
                    "construction_rule": "冻结候选后比较事件窗口相对强弱和成交",
                    "benchmark": "商业航天固定篮子",
                    "evidence_ids": [event_field_ids["price_or_expectation"][0]],
                    "members": [
                        {"candidate": "超捷股份", "ticker": "301005", "exchange": "XSHE", "evidence_ids": [event_field_ids["price_or_expectation"][0]]},
                        {"candidate": "斯瑞新材", "ticker": "688102", "exchange": "XSHG", "evidence_ids": [economic_field_ids["price_or_expectation"][0]]},
                    ],
                },
            ],
            "market_map_candidates": [
                candidate(
                    field_evidence_ids=event_field_ids,
                    mapping_is_inference=True,
                    bridge={
                        "value_path_refs": ["VT1"],
                        "economic_exposure_strength": "LOW",
                        "economic_rationale": "事件弹性高但当前订单暴露占比仍低",
                        "market_recognition": "LEADER",
                        "market_selection_rationale": "高辨识度和小市值使其成为事件资金载体",
                        "horizon_fit": ["TACTICAL_WEEKS"],
                        "market_snapshot": {
                            "as_of_date": "2026-08-09",
                            "benchmark": "商业航天固定篮子",
                            "theme_basket": "商业航天固定篮子",
                            "excess_20d": 12.0,
                            "volume_ratio_20d": 1.8,
                            "evidence_ids": [event_field_ids["price_or_expectation"][0]],
                        },
                        "closest_alternative": {
                            "candidate": "斯瑞新材", "ticker": "688102",
                            "exchange": "XSHG",
                        },
                        "why_prefer_now": "事件窗口内相对强势和辨识度高于经济兑现载体",
                        "switch_condition": "事件退潮且斯瑞新增订单和相对强势同时确认",
                    },
                ),
                candidate(
                    name="斯瑞新材",
                    ticker="688102",
                    market_role="ECONOMIC_CAPTURE",
                    setup_types=["ECONOMIC_SETUP"],
                    mechanism="回收验证 -> 发射频次预期 -> 发动机材料订单弹性",
                    field_evidence_ids=economic_field_ids,
                    mapping_is_inference=True,
                    bridge={
                        "value_path_refs": ["VT1"],
                        "economic_exposure_strength": "HIGH",
                        "economic_rationale": "发动机材料订单能把发射频次转为公司收入",
                        "market_recognition": "CONFIRMED",
                        "market_selection_rationale": "具名订单和材料瓶颈使其区别于标签股",
                        "horizon_fit": ["EARNINGS_QUARTERS"],
                        "market_snapshot": {
                            "as_of_date": "2026-08-09",
                            "benchmark": "商业航天固定篮子",
                            "theme_basket": "商业航天固定篮子",
                            "excess_60d": 8.0,
                            "volume_ratio_20d": 1.2,
                            "evidence_ids": [economic_field_ids["price_or_expectation"][0]],
                        },
                        "closest_alternative": {
                            "candidate": "超捷股份", "ticker": "301005",
                            "exchange": "XSHE",
                        },
                        "why_prefer_now": "季度视野下具名订单暴露强于纯事件弹性",
                        "switch_condition": "订单不增且事件资金重新集中到高弹性载体",
                    },
                ),
            ],
            "market_map_coverage": full_coverage(),
        }
        inq = {
            "market_phase_snapshot": {
                "as_of_date": "2026-08-09",
                "horizon": "EARNINGS_QUARTERS",
                "phase": "VERIFICATION",
                "dominant_pricing_variable": "发射频次是否转化为供应商订单和利润",
                "industry_clock": "技术验证领先于订单和收入确认",
                "market_clock": "市场等待订单兑现后的二次分化",
                "strongest_alternative_phase": "事件题材可能在订单前先行退潮",
                "falsifier": "具名订单改善仍不能带来相对强势和利润确认",
                "evidence_ids": [economic_field_ids["price_or_expectation"][0]],
            },
            "carrier_universe_snapshots": [
                {
                    "universe_key": "EU2",
                    "universe_type": "ECONOMIC_EXPOSURE",
                    "as_of_date": "2026-08-09",
                    "horizon": "EARNINGS_QUARTERS",
                    "universe_name": "商业航天季度经济暴露池",
                    "construction_rule": "按订单和收入暴露固定季度核验候选",
                    "benchmark": "商业航天固定篮子",
                    "evidence_ids": [economic_field_ids["economic_exposure"][0]],
                    "members": [
                        {"candidate": "超捷股份", "ticker": "301005", "exchange": "XSHE", "evidence_ids": [event_field_ids["economic_exposure"][0]]},
                        {"candidate": "斯瑞新材", "ticker": "688102", "exchange": "XSHG", "evidence_ids": [economic_field_ids["economic_exposure"][0]]},
                    ],
                },
                {
                    "universe_key": "MU2",
                    "universe_type": "MARKET_TRADING",
                    "as_of_date": "2026-08-09",
                    "horizon": "EARNINGS_QUARTERS",
                    "universe_name": "商业航天季度市场交易池",
                    "construction_rule": "冻结候选后比较季度视野相对强弱",
                    "benchmark": "商业航天固定篮子",
                    "evidence_ids": [economic_field_ids["price_or_expectation"][0]],
                    "members": [
                        {"candidate": "超捷股份", "ticker": "301005", "exchange": "XSHE", "evidence_ids": [event_field_ids["price_or_expectation"][0]]},
                        {"candidate": "斯瑞新材", "ticker": "688102", "exchange": "XSHG", "evidence_ids": [economic_field_ids["price_or_expectation"][0]]},
                    ],
                },
            ],
        }
        research_agenda_engine.harvest_round(st, 1, det, {})
        for artifact in (
            host_snapshot(
                "超捷股份", "301005", "XSHE",
                [
                    event_field_ids["price_or_expectation"][0],
                    event_field_ids["crowding_or_position"][0],
                ],
                "event",
            ),
            host_snapshot(
                "斯瑞新材", "688102", "XSHG",
                [
                    economic_field_ids["price_or_expectation"][0],
                    economic_field_ids["crowding_or_position"][0],
                ],
                "economic",
            ),
        ):
            self.assertEqual(
                market_bridge_engine.ingest_host_market_snapshot(st, artifact)["status"],
                "ACCEPTED",
            )
        round_1_inquisitor = {
            "market_phase_snapshot": deepcopy(det["market_phase_snapshot"])
        }
        round_2_detective = {
            "market_phase_snapshot": deepcopy(inq["market_phase_snapshot"])
        }
        market_bridge_engine.harvest_context(st, 1, det, round_1_inquisitor)
        attach_verified_round(st, 1, det, round_1_inquisitor)
        market_bridge_engine.harvest_context(st, 2, round_2_detective, inq)
        attach_verified_round(st, 2, round_2_detective, inq)
        market_map_engine.harvest_round(st, 1, det, {})
        report_view = report_v2.build_report_view_model(st)
        self.assertEqual(
            report_view["runtime"]["evidence_plane"][
                "canonical_evidence_item_count"
            ],
            10,
        )
        self.assertEqual(report_view["runtime"]["unique_source_count"], 10)
        self.assertEqual(
            report_view["runtime"]["legacy_crux_audit"][
                "unique_source_url_count"
            ],
            0,
        )
        md = report_v2.render(st)
        self.assertTrue(md.startswith("# Deep Research Report"))
        self.assertIn("超捷股份（301005）", md)
        self.assertIn("斯瑞新材（688102）", md)
        self.assertIn("## 6. 事件驱动与产业链兑现", md)
        self.assertIn("### 事件驱动", md)
        self.assertIn("### 产业链兑现", md)
        self.assertIn("完整回收", md)
        self.assertIn("价格与筹码", md)
        self.assertIn("短线资金可能先交易高辨识度事件 beta", md)
        self.assertIn("再次延期本身可能比最终结果更先改变筹码结构", md)
        self.assertIn("条件性优先关注 超捷股份", md)
        self.assertIn("条件性优先关注 斯瑞新材", md)
        self.assertIn("当前相对 斯瑞新材（688102） 优先", md)
        self.assertIn("10 条 canonical evidence", md)
        full = report_v2.render(st, view="full")
        self.assertIn("Agenda evidence: 10 条 / 10 个去重 URL", full)
        self.assertIn("旧 crux 审计 URL=0（仅兼容指标）", full)
        self.assertIn("## 9. 未回答问题与下一轮研究", md)
        self.assertNotIn("# Decision Brief", md)
        self.assertNotIn("CandidateScreen", md)

    def test_zero_setup_is_honest_only_after_coverage(self):
        st = state("没有合适载体的主题")
        market_map_engine.harvest_round(
            st, 1,
            {"market_map_coverage": {**full_coverage(), "note": "映射均缺少经济暴露"}},
            {},
        )
        md = report_v2.render(st)
        self.assertIn("`NO_USABLE_SETUP`", md)
        self.assertIn("没有形成可用的条件型机会", md)
        self.assertIn("映射均缺少经济暴露", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
