#!/usr/bin/env python3
"""Regressions for the industry-to-market bridge and recommendation authority."""
import hashlib
import json
import unittest
from unittest import mock

import crux_engine
import deepthink_orchestrator_v2
import execution_integrity
import market_bridge_engine
import market_map_engine
import report_v2


def evidence(evidence_id, claim, suffix):
    return {
        "evidence_id": evidence_id,
        "claim": claim,
        "number": None,
        "source": f"source-{suffix}",
        "url": f"https://source-{suffix}.example.cn/2026/08/10/item",
        "date": "2026-08-10",
        "source_tier": "primary",
        "question_ids": ["RQ1"],
        "direction_ids": [],
        "stance": "CONTEXT",
    }


def state():
    st = crux_engine.new_state(
        "产业到市场映射测试",
        "产业价值如何映射到不同时间的市场载体？",
        "事件到三个季度",
        [{"id": "C1", "label": "价值转移", "monitor_anchor": "订单与相对强弱"}],
    )
    st["frame_contract"] = {
        "as_of_date": "2026-08-10",
        "control_mode": "AGENDA_NATIVE",
    }
    items = [
        evidence("EV-MECH", "公司业务和供应链约束形成直接映射", "mechanism"),
        evidence("EV-ECON", "公司相关业务收入和利润暴露可核验", "economics"),
        evidence("EV-CAT", "公司公告给出订单交付日期窗口", "catalyst"),
        evidence("EV-PRICE", "公司股价相对固定行业基准取得超额收益", "price"),
        evidence("EV-CROWD", "公司换手和成交量显示资金拥挤变化", "crowding"),
    ]
    st["research_agenda"] = {
        "agenda_source": "EXPLICIT_WORKPLAN",
        "as_of_date": "2026-08-10",
        "questions": [{
            "question_id": "RQ1",
            "question": "价值从产业约束转移到哪些公司？",
            "answer_status": "PARTIAL",
        }],
        "research_directions": [],
        "evidence_items": items,
        "evidence_aliases": {},
    }
    return st


def value_path():
    return {
        "path_key": "VT1",
        "origin_question_ids": ["RQ1"],
        "origin_direction_ids": [],
        "state_change": "供给约束由设备数量转向系统交付效率",
        "constraint_change": "供配电和热管理成为交付瓶颈",
        "profit_pool_shift": "增量利润流向具备认证和服务能力的供应商",
        "economic_winners": ["系统瓶颈供应商"],
        "economic_losers": ["无服务能力的通用组装商"],
        "realization_horizon": "EARNINGS_QUARTERS",
        "falsifier": "订单增长不能转化为收入、利润和现金",
        "evidence_ids": ["EV-MECH", "EV-ECON"],
    }


def phase(phase_name="VERIFICATION", role="detective"):
    return {
        "as_of_date": "2026-08-10",
        "horizon": "EARNINGS_QUARTERS",
        "phase": phase_name,
        "dominant_pricing_variable": "订单向利润和现金的转换质量",
        "industry_clock": "订单已出现，利润和现金仍待验证",
        "market_clock": "市场从主题扩散转入财务验证",
        "strongest_alternative_phase": "仍可能只是主题扩散而非验证",
        "falsifier": "低经济暴露标签股继续主导且财务差异不影响价格",
        "evidence_ids": ["EV-PRICE"],
    }


def universes(horizon="EARNINGS_QUARTERS"):
    members = [
        {"candidate": "甲公司", "ticker": "600001", "exchange": "XSHG"},
        {"candidate": "乙公司", "ticker": "000002", "exchange": "XSHE"},
    ]
    return [
        {
            "universe_key": "EU1",
            "universe_type": "ECONOMIC_EXPOSURE",
            "as_of_date": "2026-08-10",
            "horizon": horizon,
            "universe_name": "系统交付经济暴露池",
            "construction_rule": "纳入有公司收入或利润暴露证据的上市公司",
            "benchmark": "固定行业篮子",
            "evidence_ids": ["EV-ECON"],
            "members": [
                {**item, "evidence_ids": ["EV-ECON"]} for item in members
            ],
        },
        {
            "universe_key": "MU1",
            "universe_type": "MARKET_TRADING",
            "as_of_date": "2026-08-10",
            "horizon": horizon,
            "universe_name": "系统交付市场交易池",
            "construction_rule": "固定候选后按相对行业基准强弱和成交确认市场载体",
            "benchmark": "固定行业篮子",
            "evidence_ids": ["EV-PRICE"],
            "members": [
                {**item, "evidence_ids": ["EV-PRICE"]} for item in members
            ],
        },
    ]


def candidate(name, ticker, alternative_name, alternative_ticker, role="ECONOMIC_CAPTURE",
              snapshot_date="2026-08-10", bridge=True):
    item = {
        "candidate": name,
        "ticker": ticker,
        "asset_type": "LISTED_EQUITY",
        "market_role": role,
        "setup_types": ["ECONOMIC_SETUP"],
        "mechanism": "系统交付约束 -> 订单增长 -> 公司收入和利润兑现",
        "economic_exposure": "相关业务收入和利润对公司整体具有实质影响",
        "catalyst": "下一季度订单、利润率和现金流披露",
        "catalyst_window": {"event": "季度财报", "expected_by": "2026-10-31"},
        "invalidation": "订单增长但利润率和现金流持续恶化",
        "price_or_expectation": "相对行业基准保持强势",
        "crowding_or_position": "成交活跃但尚未出现极端拥挤",
        "strongest_alternative_explanation": "上涨只来自主题资金扩散",
        "cheap_discriminating_test": "比较下一季度现金转换和20日相对强弱",
        "mapping_is_inference": True,
        "field_evidence_ids": {
            "mechanism": ["EV-MECH"],
            "economic_exposure": ["EV-ECON"],
            "catalyst": ["EV-CAT"],
            "price_or_expectation": ["EV-PRICE"],
            "crowding_or_position": ["EV-CROWD"],
        },
    }
    if bridge:
        item["bridge"] = {
            "value_path_refs": ["VT1"],
            "economic_exposure_strength": "HIGH",
            "economic_rationale": "收入暴露、利润弹性和现金转换均可直接核验",
            "market_recognition": "LEADER",
            "market_selection_rationale": "相对强势和流动性表明资金已选择该载体",
            "horizon_fit": ["EARNINGS_QUARTERS"],
            "market_snapshot": {
                "as_of_date": snapshot_date,
                "benchmark": "固定行业篮子",
                "theme_basket": "系统交付固定篮子",
                "excess_20d": 7.5,
                "volume_ratio_20d": 1.4,
                "evidence_ids": ["EV-PRICE", "EV-CROWD"],
            },
            "closest_alternative": {
                "candidate": alternative_name,
                "ticker": alternative_ticker,
                "exchange": "XSHG" if alternative_ticker.startswith("6") else "XSHE",
            },
            "why_prefer_now": "当前现金转换和相对强势优于最接近替代项",
            "switch_condition": "替代项现金流改善且20日相对强弱反超",
        }
    return item


def host_snapshot(name, ticker, exchange, snapshot_date="2026-08-10",
                  include_relative=True, include_activity=True, salt="base",
                  excess=7.5):
    candidate_url = f"https://data.example.cn/{ticker}/{snapshot_date}"
    candidate_source = {
        "name": name,
        "ticker": ticker,
        "exchange": exchange,
        "source": "fixture",
        "source_class": "STRUCTURED_MARKET_DATA",
        "source_url": candidate_url,
    }
    snapshot_core = {
        "as_of_date": snapshot_date,
        "benchmark": "固定行业篮子",
        "theme_basket": "系统交付固定篮子",
        "latest_observed_session_on_or_before_as_of": True,
        "excess_20d": excess if include_relative else None,
        "volume_ratio_20d": 1.4 if include_activity else None,
        "pe_ttm": 25.0,
    }
    receipt_core = {
        "schema_version": "trade-nothing.market-snapshot-adapter.v1",
        "input_sha256": hashlib.sha256(f"input:{salt}".encode()).hexdigest(),
        "market_snapshot_sha256": hashlib.sha256(json.dumps(
            snapshot_core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest(),
        "candidate_identity_sha256": hashlib.sha256(json.dumps(
            candidate_source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest(),
        "research_as_of_date": "2026-08-10",
        "market_session_date": snapshot_date,
        "candidate_observation_count": 61,
        "benchmark_observation_count": 61,
        "candidate_source_url": candidate_url,
        "benchmark_source_url": "https://data.example.cn/benchmark/2026-08-10",
    }
    upstream_core = {
        "schema_version": "trade-nothing.free-market-acquisition-receipt.v1",
        "request_sha256": hashlib.sha256(f"request:{salt}".encode()).hexdigest(),
        "provider": "CSV",
        "provider_version": "fixture",
        "research_as_of_date": "2026-08-10",
        "market_session_date": snapshot_date,
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
    receipt_core["upstream_acquisition_receipt_id"] = upstream["receipt_id"]
    receipt_core["receipt_id"] = hashlib.sha256(json.dumps(
        receipt_core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return {
        "schema_version": "trade-nothing.market-snapshot-adapter.v1",
        "candidate": candidate_source,
        "market_snapshot": {
            **snapshot_core,
            "adapter_receipt": receipt_core,
        },
        "sources": [],
        "upstream_acquisition_receipt": upstream,
    }


def ingest_pair(st):
    results = [
        market_bridge_engine.ingest_host_market_snapshot(
            st, host_snapshot("甲公司", "600001", "XSHG", salt="alpha")
        ),
        market_bridge_engine.ingest_host_market_snapshot(
            st, host_snapshot("乙公司", "000002", "XSHE", salt="beta")
        ),
    ]
    assert all(item["status"] == "ACCEPTED" for item in results), results


def attach_verified_round(st, round_num, detective, inquisitor):
    """Persist the same full host receipt that production phase authority uses."""
    judge = {"fixture": "judge"}
    dispatch = {
        "detective_prompt": f"detective fixture round {round_num}",
        "inquisitor_prompt": f"inquisitor fixture round {round_num}",
        "judge_prompt": f"judge fixture round {round_num}",
    }
    payloads = {
        "detective": detective,
        "inquisitor": inquisitor,
        "judge": judge,
    }
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


class MarketBridgeTests(unittest.TestCase):
    def test_host_snapshot_mints_candidate_bound_canonical_evidence(self):
        st = state()
        result = market_bridge_engine.ingest_host_market_snapshot(
            st, host_snapshot("甲公司", "600001", "XSHG", salt="identity")
        )
        self.assertEqual(result["status"], "ACCEPTED")
        ids = st["market_bridge"]["host_market_snapshots"][0][
            "canonical_evidence_ids"
        ]
        self.assertEqual(len(ids), 2)
        evidence = {
            item["evidence_id"]: item
            for item in st["research_agenda"]["evidence_items"]
        }
        for evidence_id in ids:
            item = evidence[evidence_id]
            self.assertEqual(item["origin"], "HOST_MARKET_SNAPSHOT")
            self.assertEqual(
                item["binding"]["candidate_identity"],
                "LISTED_EQUITY|XSHG|600001",
            )
            self.assertNotIn("000002", item["url"])

        second = market_bridge_engine.ingest_host_market_snapshot(
            st, host_snapshot("乙公司", "000002", "XSHE", salt="identity-beta")
        )
        self.assertEqual(second["status"], "ACCEPTED")
        beta = st["market_bridge"]["host_market_snapshots"][1]
        self.assertTrue(set(ids).isdisjoint(beta["canonical_evidence_ids"]))
        evidence = {
            item["evidence_id"]: item
            for item in st["research_agenda"]["evidence_items"]
        }
        for evidence_id in beta["canonical_evidence_ids"]:
            self.assertEqual(
                evidence[evidence_id]["binding"]["candidate_identity"],
                "LISTED_EQUITY|XSHE|000002",
            )

    def test_complete_bridge_creates_time_bounded_cross_sectional_priority(self):
        st = state()
        ingest_pair(st)
        detective = {
            "value_transfer_paths": [value_path()],
            "market_phase_snapshot": phase(),
            "carrier_universe_snapshots": universes(),
            "market_map_candidates": [
                candidate("甲公司", "600001", "乙公司", "000002"),
                candidate("乙公司", "000002", "甲公司", "600001"),
            ],
        }
        inquisitor = {"market_phase_snapshot": phase()}
        market_bridge_engine.harvest_context(st, 1, detective, inquisitor)
        attach_verified_round(st, 1, detective, inquisitor)
        market_map_engine.harvest_round(st, 1, detective, inquisitor)
        view = market_map_engine.report_view(st)["market_bridge"]
        self.assertEqual(len(view["value_paths"]), 1)
        self.assertEqual(view["phase_by_horizon"]["EARNINGS_QUARTERS"]["phase"], "VERIFICATION")
        self.assertEqual(view["priority_count"], 2)
        first = view["priorities_by_horizon"]["EARNINGS_QUARTERS"][0]
        self.assertEqual(first["bridge"]["projection"], "CONFIRMED_LEADER")
        self.assertEqual(first["bridge"]["recommendation_level"], "CROSS_SECTIONAL_PRIORITY")
        self.assertNotIn(
            "TRUSTED_MARKET_SNAPSHOT_NOT_INGESTED", first["bridge"]["issues"]
        )
        md = report_v2.render(st)
        self.assertIn("产业价值转移与市场时间结构", md)
        self.assertIn("经济暴露池 × 市场交易池", md)
        self.assertIn("条件性优先关注", md)
        self.assertIn("切换条件", md)
        ledger = report_v2.render(st, view="evidence")
        self.assertTrue(ledger.startswith("# Evidence Ledger"))
        for item in st["research_agenda"]["evidence_items"]:
            self.assertIn(item["evidence_id"], ledger)

    def test_complete_setup_without_bridge_never_becomes_recommendation(self):
        st = state()
        payload = {"market_map_candidates": [
            candidate("甲公司", "600001", "乙公司", "000002", bridge=False)
        ]}
        market_map_engine.harvest_round(st, 1, payload, {})
        view = market_map_engine.report_view(st)
        self.assertEqual(view["market_bridge"]["priority_count"], 0)
        self.assertEqual(view["candidates"][0]["attention_band"], "SETUP_CANDIDATE")
        self.assertIn("完整性不等于吸引力", report_v2.render(st))

    def test_watch_only_cannot_receive_recommendation_authority(self):
        st = state()
        ingest_pair(st)
        payload = {
            "value_transfer_paths": [value_path()],
            "market_map_candidates": [
                candidate("甲公司", "600001", "乙公司", "000002", role="WATCH_ONLY"),
                candidate("乙公司", "000002", "甲公司", "600001"),
            ],
        }
        market_bridge_engine.harvest_context(st, 1, payload, {})
        market_map_engine.harvest_round(st, 1, payload, {})
        candidates = market_map_engine.report_view(st)["candidates"]
        watch = next(item for item in candidates if item["ticker"] == "600001")
        self.assertEqual(watch["bridge"]["recommendation_level"], "COUNTEREXAMPLE")

    def test_pairwise_story_without_dual_universe_is_not_a_priority(self):
        st = state()
        ingest_pair(st)
        payload = {
            "value_transfer_paths": [value_path()],
            "market_phase_snapshot": phase(),
            "market_map_candidates": [
                candidate("甲公司", "600001", "乙公司", "000002"),
                candidate("乙公司", "000002", "甲公司", "600001"),
            ],
        }
        market_bridge_engine.harvest_context(st, 1, payload, {})
        market_map_engine.harvest_round(st, 1, payload, {})
        view = market_map_engine.report_view(st)["market_bridge"]
        self.assertEqual(view["priority_count"], 0)
        self.assertTrue(all(
            any(issue.startswith("DUAL_UNIVERSE_INCOMPLETE") for issue in item["bridge"]["issues"])
            for item in view["candidates"]
        ))

    def test_model_supplied_snapshot_never_grants_market_authority(self):
        st = state()
        payload = {
            "value_transfer_paths": [value_path()],
            "market_map_candidates": [
                candidate("甲公司", "600001", "乙公司", "000002"),
                candidate("乙公司", "000002", "甲公司", "600001"),
            ],
        }
        market_bridge_engine.harvest_context(st, 1, payload, {})
        market_map_engine.harvest_round(st, 1, payload, {})
        first = next(
            item for item in market_map_engine.report_view(st)["candidates"]
            if item["ticker"] == "600001"
        )
        self.assertEqual(first["bridge"]["market_recognition"]["effective"], "UNKNOWN")
        self.assertIn(
            "TRUSTED_MARKET_SNAPSHOT_NOT_INGESTED",
            first["bridge"]["issues"],
        )
        self.assertNotIn(
            "MODEL_MARKET_SNAPSHOT_IGNORED_FOR_AUTHORITY",
            first["bridge"]["issues"],
        )
        persisted = next(
            item for item in st["candidate_map"]["candidates"]
            if item["ticker"] == "600001"
        )
        self.assertIn(
            "MODEL_MARKET_SNAPSHOT_IGNORED_FOR_AUTHORITY",
            persisted["bridge"]["issues"],
        )

    def test_valuation_only_host_snapshot_is_rejected(self):
        st = state()
        result = market_bridge_engine.ingest_host_market_snapshot(
            st,
            host_snapshot(
                "甲公司", "600001", "XSHG",
                include_relative=False, include_activity=False,
            ),
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["reason"], "MARKET_SNAPSHOT_NOT_RECOMMENDATION_GRADE")
        self.assertIn("MARKET_SNAPSHOT_RELATIVE_STRENGTH_REQUIRED", result["issues"])
        self.assertIn("MARKET_SNAPSHOT_ACTIVITY_REQUIRED", result["issues"])

    def test_positive_recognition_cannot_ride_negative_relative_strength(self):
        st = state()
        artifact = host_snapshot(
            "甲公司", "600001", "XSHG", salt="negative", excess=-4.0
        )
        self.assertEqual(
            market_bridge_engine.ingest_host_market_snapshot(st, artifact)["status"],
            "ACCEPTED",
        )
        payload = {
            "value_transfer_paths": [value_path()],
            "market_map_candidates": [
                candidate("甲公司", "600001", "乙公司", "000002")
            ],
        }
        market_bridge_engine.harvest_context(st, 1, payload, {})
        market_map_engine.harvest_round(st, 1, payload, {})
        bridge = market_map_engine.report_view(st)["candidates"][0]["bridge"]
        self.assertEqual(bridge["market_recognition"]["effective"], "UNKNOWN")
        self.assertIn(
            "MARKET_RECOGNITION_CONTRADICTS_RELATIVE_STRENGTH",
            bridge["issues"],
        )

    def test_hypothesis_only_value_path_cannot_unlock_priority(self):
        st = state()
        ingest_pair(st)
        hypothesis_path = value_path()
        hypothesis_path["evidence_ids"] = []
        detective = {
            "value_transfer_paths": [hypothesis_path],
            "market_phase_snapshot": phase(),
            "carrier_universe_snapshots": universes(),
            "market_map_candidates": [
                candidate("甲公司", "600001", "乙公司", "000002"),
                candidate("乙公司", "000002", "甲公司", "600001"),
            ],
        }
        inquisitor = {"market_phase_snapshot": phase()}
        market_bridge_engine.harvest_context(st, 1, detective, inquisitor)
        attach_verified_round(st, 1, detective, inquisitor)
        market_map_engine.harvest_round(st, 1, detective, inquisitor)
        view = market_map_engine.report_view(st)["market_bridge"]
        self.assertEqual(view["priority_count"], 0)
        self.assertTrue(all(
            "VALUE_PATH_NOT_GROUNDED" in item["bridge"]["issues"]
            for item in view["candidates"]
        ))

    def test_unrelated_market_evidence_cannot_launder_value_path(self):
        st = state()
        ingest_pair(st)
        unrelated_path = value_path()
        unrelated_path["evidence_ids"] = ["EV-PRICE", "EV-CROWD"]
        detective = {
            "value_transfer_paths": [unrelated_path],
            "market_phase_snapshot": phase(),
            "carrier_universe_snapshots": universes(),
            "market_map_candidates": [
                candidate("甲公司", "600001", "乙公司", "000002"),
                candidate("乙公司", "000002", "甲公司", "600001"),
            ],
        }
        inquisitor = {"market_phase_snapshot": phase()}
        market_bridge_engine.harvest_context(st, 1, detective, inquisitor)
        attach_verified_round(st, 1, detective, inquisitor)
        market_map_engine.harvest_round(st, 1, detective, inquisitor)
        view = market_map_engine.report_view(st)["market_bridge"]
        self.assertEqual(view["value_paths"][0]["evidence_boundary"], "SINGLE_SOURCE")
        self.assertFalse(view["value_paths"][0]["grounded"])
        self.assertIn(
            "VALUE_PATH_MECHANISM_EVIDENCE_REQUIRED",
            view["value_paths"][0]["evidence_issues"],
        )
        self.assertIn(
            "VALUE_PATH_ECONOMIC_EVIDENCE_REQUIRED",
            view["value_paths"][0]["evidence_issues"],
        )
        self.assertEqual(view["priority_count"], 0)

    def test_category_words_without_path_alignment_cannot_launder_value_path(self):
        st = state()
        st["research_agenda"]["evidence_items"].extend([
            evidence("EV-OTHER-MECH", "消费电子客户需求发生变化", "other-mechanism"),
            evidence("EV-OTHER-ECON", "零售业务销量出现下滑", "other-economics"),
        ])
        unrelated_path = value_path()
        unrelated_path["evidence_ids"] = ["EV-OTHER-MECH", "EV-OTHER-ECON"]
        market_bridge_engine.harvest_context(
            st, 1, {"value_transfer_paths": [unrelated_path]}, {}
        )
        path = market_bridge_engine.report_view(st, [])["value_paths"][0]
        self.assertFalse(path["grounded"])
        self.assertIn("VALUE_PATH_MECHANISM_EVIDENCE_REQUIRED", path["evidence_issues"])
        self.assertIn("VALUE_PATH_ECONOMIC_EVIDENCE_REQUIRED", path["evidence_issues"])

    def test_single_role_phase_is_not_consensus(self):
        st = state()
        ingest_pair(st)
        detective = {
            "value_transfer_paths": [value_path()],
            "market_phase_snapshot": phase(),
            "carrier_universe_snapshots": universes(),
            "market_map_candidates": [
                candidate("甲公司", "600001", "乙公司", "000002"),
                candidate("乙公司", "000002", "甲公司", "600001"),
            ],
        }
        market_bridge_engine.harvest_context(st, 1, detective, {})
        attach_verified_round(st, 1, detective, {})
        market_map_engine.harvest_round(st, 1, detective, {})
        view = market_map_engine.report_view(st)["market_bridge"]
        phase_view = view["phase_by_horizon"]["EARNINGS_QUARTERS"]
        self.assertEqual(phase_view["status"], "SINGLE_VIEW")
        self.assertEqual(view["priority_count"], 0)
        self.assertTrue(all(
            "MARKET_PHASE_SINGLE_VIEW:EARNINGS_QUARTERS" in item["bridge"]["issues"]
            for item in view["candidates"]
        ))

    def test_two_role_phase_requires_evidence_from_both_roles(self):
        st = state()
        ingest_pair(st)
        detective = {
            "value_transfer_paths": [value_path()],
            "market_phase_snapshot": phase(),
            "carrier_universe_snapshots": universes(),
            "market_map_candidates": [
                candidate("甲公司", "600001", "乙公司", "000002"),
                candidate("乙公司", "000002", "甲公司", "600001"),
            ],
        }
        unsupported_phase = phase()
        unsupported_phase["evidence_ids"] = []
        inquisitor = {"market_phase_snapshot": unsupported_phase}
        market_bridge_engine.harvest_context(st, 1, detective, inquisitor)
        attach_verified_round(st, 1, detective, inquisitor)
        market_map_engine.harvest_round(st, 1, detective, inquisitor)
        view = market_map_engine.report_view(st)["market_bridge"]
        phase_view = view["phase_by_horizon"]["EARNINGS_QUARTERS"]
        self.assertEqual(phase_view["status"], "CONSENSUS")
        self.assertEqual(phase_view["grounded_source_agents"], ["detective"])
        self.assertEqual(view["priority_count"], 0)
        self.assertTrue(all(
            "MARKET_PHASE_NOT_GROUNDED:EARNINGS_QUARTERS" in item["bridge"]["issues"]
            for item in view["candidates"]
        ))

    def test_duplicate_role_slots_without_execution_receipt_have_no_phase_authority(self):
        st = state()
        ingest_pair(st)
        detective = {
            "value_transfer_paths": [value_path()],
            "market_phase_snapshot": phase(),
            "carrier_universe_snapshots": universes(),
            "market_map_candidates": [
                candidate("甲公司", "600001", "乙公司", "000002"),
                candidate("乙公司", "000002", "甲公司", "600001"),
            ],
        }
        inquisitor = {"market_phase_snapshot": phase()}
        market_bridge_engine.harvest_context(st, 1, detective, inquisitor)
        market_map_engine.harvest_round(st, 1, detective, inquisitor)
        view = market_map_engine.report_view(st)["market_bridge"]
        phase_view = view["phase_by_horizon"]["EARNINGS_QUARTERS"]
        self.assertEqual(phase_view["status"], "UNVERIFIED_CONSENSUS")
        self.assertEqual(phase_view["grounded_source_agents"], [])
        self.assertEqual(view["priority_count"], 0)
        self.assertTrue(all(
            "MARKET_PHASE_EXECUTION_UNVERIFIED:EARNINGS_QUARTERS"
            in item["bridge"]["issues"]
            for item in view["candidates"]
        ))

    def test_phase_snapshot_must_match_the_payload_bound_by_round_receipt(self):
        st = state()
        detective = {"market_phase_snapshot": phase()}
        inquisitor = {"market_phase_snapshot": phase()}
        market_bridge_engine.harvest_context(st, 1, detective, inquisitor)
        detached_detective = {
            "market_phase_snapshot": phase(),
            "unrelated_post_harvest_change": True,
        }
        attach_verified_round(st, 1, detached_detective, inquisitor)
        phase_view = market_bridge_engine.report_view(
            st, []
        )["phase_by_horizon"]["EARNINGS_QUARTERS"]
        self.assertEqual(phase_view["status"], "UNVERIFIED_CONSENSUS")
        self.assertEqual(phase_view["verified_source_agents"], ["inquisitor"])

    def test_receipt_tamper_and_same_session_conflict_fail_closed(self):
        st = state()
        artifact = host_snapshot("甲公司", "600001", "XSHG", salt="original")
        tampered = json.loads(json.dumps(artifact))
        tampered["market_snapshot"]["excess_20d"] = 99.0
        rejected = market_bridge_engine.ingest_host_market_snapshot(st, tampered)
        self.assertEqual(rejected["status"], "REJECTED")
        self.assertEqual(
            rejected["reason"], "market_snapshot_adapter_snapshot_hash_mismatch"
        )
        retargeted = json.loads(json.dumps(artifact))
        retargeted["candidate"]["ticker"] = "000002"
        retargeted["candidate"]["exchange"] = "XSHE"
        retarget_rejected = market_bridge_engine.ingest_host_market_snapshot(
            st, retargeted
        )
        self.assertEqual(retarget_rejected["status"], "REJECTED")
        self.assertEqual(
            retarget_rejected["reason"],
            "market_snapshot_adapter_candidate_identity_mismatch",
        )
        receipt_free = json.loads(json.dumps(artifact))
        receipt_free.pop("upstream_acquisition_receipt")
        receipt_rejected = market_bridge_engine.ingest_host_market_snapshot(
            st, receipt_free
        )
        self.assertEqual(receipt_rejected["status"], "REJECTED")
        self.assertEqual(
            receipt_rejected["reason"], "upstream_acquisition_receipt_required"
        )
        accepted = market_bridge_engine.ingest_host_market_snapshot(st, artifact)
        replay = market_bridge_engine.ingest_host_market_snapshot(st, artifact)
        conflict = market_bridge_engine.ingest_host_market_snapshot(
            st, host_snapshot("甲公司", "600001", "XSHG", salt="different")
        )
        self.assertEqual(accepted["status"], "ACCEPTED")
        self.assertEqual(replay["status"], "IDEMPOTENT")
        self.assertEqual(conflict["status"], "REJECTED")
        self.assertEqual(
            conflict["reason"], "MARKET_SNAPSHOT_CONFLICT_FOR_CANDIDATE_SESSION"
        )

    def test_orchestrator_ingestion_is_formal_and_exposes_safe_context(self):
        st = state()
        before = deepthink_orchestrator_v2._formal_surface_digest(st)
        saved = []
        with mock.patch.object(
            deepthink_orchestrator_v2, "_load", return_value=st
        ), mock.patch.object(
            deepthink_orchestrator_v2, "_save",
            side_effect=lambda topic, value: saved.append((topic, value)),
        ):
            result = deepthink_orchestrator_v2.cmd_ingest_market_snapshot(
                "产业到市场映射测试",
                host_snapshot("甲公司", "600001", "XSHG", salt="command"),
            )
        after = deepthink_orchestrator_v2._formal_surface_digest(st)
        self.assertEqual(result["status"], "market_snapshot_ingested")
        self.assertEqual(len(saved), 1)
        self.assertNotEqual(before, after)
        context = result["market_bridge"]["trusted_market_snapshots"]
        self.assertEqual(context[0]["ticker"], "600001")
        self.assertEqual(context[0]["authority"], "HOST_INGESTED_RECEIPT_BOUND")
        self.assertNotIn("upstream_acquisition_receipt_id", context[0])

    def test_competing_phase_readings_remain_disputed(self):
        st = state()
        detective = {"value_transfer_paths": [value_path()], "market_phase_snapshot": phase("VERIFICATION")}
        inquisitor = {"market_phase_snapshot": phase("CROWDING_RESET")}
        market_bridge_engine.harvest_context(st, 1, detective, inquisitor)
        phase_view = market_bridge_engine.report_view(st, [])["phase_by_horizon"]["EARNINGS_QUARTERS"]
        self.assertEqual(phase_view["status"], "DISPUTED")
        self.assertEqual(phase_view["phase"], "UNRESOLVED")
        self.assertEqual(phase_view["competing_phases"], ["CROWDING_RESET", "VERIFICATION"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
