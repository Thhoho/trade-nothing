#!/usr/bin/env python3
"""Regression tests for the v0.18 harness-first research core."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import research_core
import research_report
import codex_research_receipt


def task_spec(budget=3):
    return research_core.normalize_task_spec({
        "question": "截至截止日，这家公司是否形成可验证经济暴露？",
        "as_of": "2026-08-12",
        "horizons": ["EVENT_DAYS", "EARNINGS_QUARTERS"],
        "budget": budget,
        "primary_entities": [{
            "entity_id": "E1",
            "name": "测试公司",
            "entity_type": "LISTED_COMPANY",
            "ticker": "300001",
            "exchange": "SZSE",
        }],
        "questions": [{
            "question_id": "RQ1",
            "question": "资本变化是否改写判断？",
            "decision_impact": "HIGH",
        }],
    })


def evidence(evidence_id="EV-CAPITAL-1", impact="HIGH"):
    return {
        "evidence_id": evidence_id,
        "claim": "公司公告披露一项会改变资本约束的融资事件。",
        "number": None,
        "measures": [{
            "measure_id": f"MEASURE-{evidence_id.replace('EV-', '')}",
            "metric": "financing_amount",
            "value": 1.0,
            "unit": "CNY_100M",
            "dimension": "CURRENCY",
            "subject_id": "E1",
            "as_of": "2026-08-10",
            "period": "POINT_IN_TIME",
            "basis": "DISCLOSURE_REPORTED",
            "definition": "融资或资本计划金额",
        }],
        "roles": ["CURRENT_REALITY", "ECONOMIC_EXPOSURE"],
        "source": "深圳证券交易所",
        "url": f"https://www.szse.cn/disclosure/{evidence_id.lower()}.html",
        "date": "2026-08-10",
        "source_tier": "PRIMARY",
        "boundary": "FACT",
        "decision_impact": impact,
        "entity_ids": ["E1"],
        "security_ids": ["300001@SZSE"],
        "fact_surface": "CAPITAL_ACTIONS",
        "claim_ids": ["CORE-1"],
    }


def document_facts(
    *, event_type="RELATED_PARTY_BORROWING", event_anchor="LOAN-TEST-A"
):
    document_sha256 = hashlib.sha256(
        f"{event_type}:{event_anchor}:official-document".encode("utf-8")
    ).hexdigest()
    return [{
        "fact_id": research_core.stable_id(
            "DF", event_type, event_anchor, "COUNTERPARTY"
        ),
        "fact_type": "COUNTERPARTY",
        "locator": "正文第二页第一段",
        "excerpt": "交易对手为公司控股股东，公告明确本次事项构成关联交易。",
        "document_sha256": document_sha256,
        "event_type": event_type,
        "event_anchor": event_anchor,
    }, {
        "fact_id": research_core.stable_id(
            "DF", event_type, event_anchor, "STATUS"
        ),
        "fact_type": "STATUS",
        "locator": "正文第三页第二段",
        "excerpt": "公告说明相关借款尚未实际提款，后续使用仍受约定条件约束。",
        "document_sha256": document_sha256,
        "event_type": event_type,
        "event_anchor": event_anchor,
    }]


def market_evidence():
    return {
        "evidence_id": "EV-MARKET-1",
        "claim": "截至截止日，标的中窗口相对基准表现与成交状态已被冻结。",
        "number": None,
        "measures": [{
            "measure_id": "MEASURE-EXCESS-20D",
            "metric": "excess_20d",
            "value": 8.2,
            "unit": "PERCENT",
            "dimension": "PERCENT",
            "subject_id": "300001@XSHE",
            "as_of": "2026-08-12",
            "period": "20D",
            "basis": "CALCULATED_BENCHMARK_EXCESS",
            "definition": "相对基准中窗口超额收益",
        }, {
            "measure_id": "MEASURE-TURNOVER-1",
            "metric": "turnover_rate",
            "value": 3.1,
            "unit": "PERCENT",
            "dimension": "PERCENT",
            "subject_id": "300001@XSHE",
            "as_of": "2026-08-12",
            "period": "SESSION",
            "basis": "PROVIDER_REPORTED",
            "definition": "最新交易日换手率",
        }],
        "roles": ["MARKET_STATE", "TECHNICAL_STATE"],
        "source": "Tushare Pro daily/daily_basic",
        "url": "https://tushare.pro/document/2?doc_id=27",
        "date": "2026-08-12",
        "source_tier": "STRUCTURED_MARKET_DATA",
        "boundary": "SINGLE_SOURCE",
        "decision_impact": "MEDIUM",
        "entity_ids": ["E1"],
        "security_ids": ["300001@SZSE"],
        "fact_surface": "MARKET_PRICE_LIQUIDITY",
        "claim_ids": ["MV-1", "CAND-1"],
    }


def index_manifest(count, primary_urls):
    entries = [
        {
            "title": f"承重公告 {index}", "url": url, "date": "2026-08-10",
            "disposition": "OPENED_RELEVANT",
            "reason": "可能改变资本或经营判断，已打开并形成证据。",
        }
        for index, url in enumerate(primary_urls, start=1)
    ]
    while len(entries) < count:
        index = len(entries) + 1
        entries.append({
            "title": f"例行公告 {index}",
            "url": f"https://www.szse.cn/disclosure/index-entry-{index}.html",
            "date": "2026-08-01",
            "disposition": "DISMISSED_BY_TITLE",
            "reason": "标题明确属于例行治理事项，不改变当前判断。",
        })
    return entries


def complete_source_checks(evidence_id="EV-CAPITAL-1"):
    checks = []
    for surface in research_core.LISTED_COMPANY_FACT_SURFACES:
        found = surface in {"OFFICIAL_DISCLOSURE_INDEX", "CAPITAL_ACTIONS"}
        checks.append({
            "source_check_id": f"SC-{surface.replace('_', '-')}",
            "entity_id": "E1",
            "fact_surface": surface,
            "window_start": "2026-04-01",
            "window_end": "2026-08-12",
            "window_basis": (
                research_core.OFFICIAL_INDEX_WINDOW_BASIS
                if surface == "OFFICIAL_DISCLOSURE_INDEX" else ""
            ),
            "latest_periodic_report_date": (
                "2026-04-30" if surface == "OFFICIAL_DISCLOSURE_INDEX" else ""
            ),
            "index_item_count": 24 if surface == "OFFICIAL_DISCLOSURE_INDEX" else 0,
            "index_entries": (
                index_manifest(24, [evidence(evidence_id)["url"]])
                if surface == "OFFICIAL_DISCLOSURE_INDEX" else []
            ),
            "queries": [f"测试公司 {surface} site:szse.cn"],
            "official_index_url": "https://www.szse.cn/disclosure/listed/notice/index.html",
            "checked_document_urls": [
                evidence(evidence_id)["url"]
            ],
            "enumeration_complete": surface == "OFFICIAL_DISCLOSURE_INDEX",
            "outcome": "FOUND" if found else "NO_RESULT",
            "evidence_ids": [evidence_id] if found else [],
            "negative_scope": "窗口内公告标题全集未见该类事项" if not found else "",
            "limitation": "仅覆盖截至日官方披露。",
        })
    return checks


def action_intent(action_type="RESEARCH"):
    return {
        "action_type": action_type,
        "target_snapshot_field": "material_changes" if action_type != "RESOLUTION" else "core_judgment",
        "current_uncertainty": "资本事件是否改变当前判断",
        "evidence_needed": "官方披露及其对结论的含义",
        "expected_decision_delta": "改变重大变化与核心判断",
        "stop_condition": "官方事实面完成且重大证据已消费",
        "cost_bound": "LOW",
    }


def challenge_source_check(evidence_id="EV-CHALLENGE-1"):
    return {
        "source_check_id": f"SC-CHALLENGE-{evidence_id}",
        "entity_id": "E1",
        "fact_surface": "CAPITAL_ACTIONS",
        "window_start": "2026-08-01",
        "window_end": "2026-08-12",
        "queries": ["融资是否已经到账 官方公告"],
        "official_index_url": "",
        "checked_document_urls": [evidence(evidence_id)["url"]],
        "index_entries": [],
        "enumeration_complete": False,
        "outcome": "FOUND",
        "evidence_ids": [evidence_id],
        "negative_scope": "",
        "limitation": "定向挑战检查。",
    }


def snapshot(run, *, version=1, challenge=None, status="DECISION_READY",
             extra_evidence_ids=None):
    ids = ["EV-CAPITAL-1"] + list(extra_evidence_ids or [])
    result = {
        "schema_version": research_core.SNAPSHOT_SCHEMA,
        "version": version,
        "base_snapshot_sha256": research_core.snapshot_hash(run["decision_snapshot"]),
        "as_of": "2026-08-12",
        "decision_status": status,
        "core_judgment": {
            "claim_id": "CORE-1",
            "summary": "资本事件已改变融资边界，但不自动证明产业兑现。",
            "boundary": "FACT",
            "evidence_ids": ids,
        },
        "boundary": "不包含交易执行或目标价。",
        "material_changes": [{
            "change_id": "MC-1",
            "title": "资本约束变化",
            "summary": "官方披露确认融资事件。",
            "decision_effect": "改善融资可见度但保留兑现条件。",
            "boundary": "FACT",
            "evidence_ids": ["EV-CAPITAL-1"],
        }],
        "open_material_gaps": [],
        "agenda_answers": [{
            "question_id": "RQ1",
            "question": "资本变化是否改写判断？",
            "status": "ANSWERED",
            "answer": "改变融资边界，不等于利润兑现。",
            "boundary": "FACT",
            "evidence_ids": ["EV-CAPITAL-1"],
            "self_countercase": "融资可能未实际到账。",
            "missing_information": "后续到账与使用进度。",
            "next_test_availability": "WAIT_FOR_EVENT",
        }],
        "value_transfer_paths": [],
        "market_by_horizon": [],
        "market_carriers_by_horizon": [],
        "candidates_by_horizon": [],
        "self_countercases": [{
            "claim_id": "SELF-1",
            "target_claim_id": "CORE-1",
            "argument": "融资计划可能不等于到账。",
            "evidence_ids": [],
        }],
        "challenge_resolutions": [challenge] if challenge else [],
        "unresolved_questions": [],
        "lowest_cost_next_validation": [{
            "action": "等待资金到账公告",
            "availability": "WAIT_FOR_EVENT",
            "expected_decision_delta": "验证融资确定性",
            "evidence_ids": [],
        }],
        "consumed_evidence_ids": ids,
        "non_material_evidence_dispositions": [],
    }
    return result


def bind(run, call_mode, role):
    return research_core.bind_dispatch(
        run, call_mode=call_mode, role=role, prompt_sha256="a" * 64
    )


def receipt(role, packet, suffix="1", challenge_id="", agent_id=""):
    return {
        "receipt_id": f"RCPT-{role}-{suffix}",
        "status": "SUCCEEDED",
        "agent_id": agent_id or f"agent-{role.lower()}",
        "isolation": "CONTROLLED_FIXTURE",
        "receipt_provenance": "CONTROLLED_FIXTURE",
        "process_id": 0,
        "host_runtime": "controlled-fixture",
        "external_tools_enabled": False,
        "parent_agent_id": "",
        "attestation_level": "CONTROLLED_FIXTURE",
        "prompt_sha256": "a" * 64,
        "payload_sha256": research_core.stable_hash(packet),
        "challenge_id": challenge_id,
    }


def lead_packet(run, *, request_challenge=False, continue_research=False):
    packet = {
        "action_intent": action_intent(),
        "evidence_items": [evidence()],
        "source_checks": complete_source_checks(),
        "decision_snapshot": snapshot(run),
        "challenge_request": None,
        "continue_research": continue_research,
        "stop_reason": "当前无更高价值可检索动作",
    }
    if request_challenge:
        packet["challenge_request"] = {
            "challenge_id": "CH-CAPITAL-1",
            "target_claim_ids": ["CORE-1"],
            "question": "融资计划是否可能因未到账而不改变实质约束？",
            "why_load_bearing": "可能推翻核心判断中的融资改善。",
        }
    return packet


class TaskAndEvidenceTests(unittest.TestCase):
    def test_listed_company_cannot_delete_mandatory_fact_surfaces(self):
        raw = {
            "question": "test", "as_of": "2026-08-12", "budget": 1,
            "primary_entities": [{
                "name": "A", "entity_type": "LISTED_COMPANY",
                "ticker": "1", "exchange": "X", "fact_surfaces": ["CUSTOM"],
            }],
        }
        spec = research_core.normalize_task_spec(raw)
        surfaces = spec["primary_entities"][0]["fact_surfaces"]
        self.assertTrue(set(research_core.LISTED_COMPANY_FACT_SURFACES).issubset(surfaces))
        self.assertIn("CUSTOM", surfaces)

    def test_official_index_requires_complete_enumeration(self):
        spec = task_spec()
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [evidence()], as_of=spec["as_of"]
        )
        raw = complete_source_checks()[0]
        raw["enumeration_complete"] = False
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "official_index_requires_complete_enumeration",
        ):
            research_core.normalize_source_check(raw, task_spec=spec, store=store)

    def test_official_index_rejects_a_short_window(self):
        spec = task_spec()
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [evidence()], as_of=spec["as_of"]
        )
        raw = complete_source_checks()[0]
        raw["window_start"] = "2026-08-01"
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "official_index_window_too_short"
        ):
            research_core.normalize_source_check(raw, task_spec=spec, store=store)

    def test_official_index_count_requires_the_actual_manifest(self):
        spec = task_spec()
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [evidence()], as_of=spec["as_of"]
        )
        raw = complete_source_checks()[0]
        raw["index_entries"] = raw["index_entries"][:-1]
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "official_index_manifest_count_mismatch",
        ):
            research_core.normalize_source_check(raw, task_spec=spec, store=store)

    def test_official_index_requires_host_acquisition_not_lead_attestation(self):
        spec = task_spec()
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [evidence()], as_of=spec["as_of"]
        )
        raw = complete_source_checks()[0]
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "official_index_requires_host_acquisition",
        ):
            research_core.normalize_source_check(
                raw, task_spec=spec, store=store, origin="LEAD_RESEARCH"
            )

    def test_official_index_manifest_requires_a_disposition_for_every_title(self):
        spec = task_spec()
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [evidence()], as_of=spec["as_of"]
        )
        raw = complete_source_checks()[0]
        raw["index_entries"][0].pop("disposition", None)
        raw["index_entries"][0].pop("reason", None)
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "index_entry_fields_invalid",
        ):
            research_core.normalize_source_check(
                raw, task_spec=spec, store=store,
                origin="HOST_INPUT",
            )

    def test_source_check_cannot_claim_an_unopened_evidence_url(self):
        spec = task_spec()
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [evidence()], as_of=spec["as_of"]
        )
        raw = next(
            item for item in complete_source_checks()
            if item["fact_surface"] == "CAPITAL_ACTIONS"
        )
        raw["checked_document_urls"] = ["https://www.szse.cn/disclosure/other.html"]
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "evidence_url_not_checked"
        ):
            research_core.normalize_source_check(raw, task_spec=spec, store=store)

    def test_evidence_after_as_of_is_rejected(self):
        raw = evidence()
        raw["date"] = "2026-08-13"
        with self.assertRaisesRegex(research_core.ResearchContractError, "after_as_of"):
            research_core.normalize_evidence_item(raw, as_of="2026-08-12")

    def test_duplicate_evidence_cannot_mutate_materiality_in_place(self):
        low = evidence("EV-DUPLICATE-LOW", impact="LOW")
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [low], as_of="2026-08-12"
        )
        high = evidence("EV-DUPLICATE-HIGH", impact="HIGH")
        high["url"] = low["url"]
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "duplicate_semantic_conflict.*decision_impact",
        ):
            research_core.append_evidence_items(
                store, [high], as_of="2026-08-12"
            )

    def test_opaque_number_field_accepts_only_json_null(self):
        for invalid in ("", 0, False, "1亿元", {"value": 1}, [1]):
            with self.subTest(invalid=invalid):
                raw = evidence()
                raw["number"] = invalid
                with self.assertRaisesRegex(
                    research_core.ResearchContractError,
                    "number_removed_use_typed_measures",
                ):
                    research_core.normalize_evidence_item(
                        raw, as_of="2026-08-12"
                    )

    def test_typed_measure_enforces_metric_unit_and_scale(self):
        raw = market_evidence()
        raw["measures"][0]["unit"] = "CNY_BN"
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "metric_unit_mismatch"
        ):
            research_core.normalize_evidence_item(raw, as_of="2026-08-12")
        rendered = research_core.format_measure({
            "value": 2167.1641, "unit": "CNY_BN",
        })
        self.assertEqual(rendered, "2.167万亿元（21671.64亿元）")

    def test_measure_identity_and_metric_dimension_are_fail_closed(self):
        first = evidence()
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [first], as_of="2026-08-12"
        )
        conflicting = evidence("EV-CAPITAL-CONFLICT", impact="MEDIUM")
        conflicting["measures"][0]["measure_id"] = (
            first["measures"][0]["measure_id"]
        )
        conflicting["measures"][0]["value"] = 2.0
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "measure_id_conflict"
        ):
            research_core.append_evidence_items(
                store, [conflicting], as_of="2026-08-12"
            )
        wrong_dimension = evidence("EV-CAPITAL-WRONG-UNIT", impact="MEDIUM")
        wrong_dimension["measures"][0].update({
            "unit": "PERCENT", "dimension": "PERCENT",
        })
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "metric_unit_mismatch"
        ):
            research_core.normalize_evidence_item(
                wrong_dimension, as_of="2026-08-12"
            )

    def test_measure_registry_and_structured_basis_close_semantic_aliases(self):
        unknown = evidence("EV-UNKNOWN-METRIC")
        unknown["measures"][0]["metric"] = "profit_net"
        unknown["measures"][0].pop("definition", None)
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "metric_unregistered:profit_net"
        ):
            research_core.normalize_evidence_item(unknown, as_of="2026-08-12")

        mislabeled = evidence("EV-MISLABELED-METRIC")
        mislabeled["measures"][0]["definition"] = "公司归母净利润"
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "definition_registry_mismatch"
        ):
            research_core.normalize_evidence_item(mislabeled, as_of="2026-08-12")

        synonym_basis = evidence("EV-BASIS-SYNONYM")
        synonym_basis["measures"][0]["basis"] = "公告所披露金额"
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "basis_unregistered"
        ):
            research_core.normalize_evidence_item(
                synonym_basis, as_of="2026-08-12"
            )

        first = evidence("EV-BASIS-FIRST")
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [first], as_of="2026-08-12"
        )
        conflicting = evidence("EV-BASIS-SECOND")
        conflicting["measures"][0]["value"] = 99.0
        conflicting["measures"][0]["basis"] = "PROVIDER_REPORTED"
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "measure_semantic_conflict"
        ):
            research_core.append_evidence_items(
                store, [conflicting], as_of="2026-08-12"
            )

    def test_measure_subject_prevents_cross_security_false_conflicts(self):
        first = market_evidence()
        second = deepcopy(first)
        second["evidence_id"] = "EV-MARKET-SECOND"
        second["url"] = "https://tushare.pro/document/2?doc_id=32"
        second["security_ids"] = ["600001@XSHG"]
        second["measures"][0]["measure_id"] = "MEASURE-SECOND-EXCESS"
        second["measures"][0]["subject_id"] = "600001@XSHG"
        second["measures"][0]["value"] = -3.4
        second["measures"][1]["measure_id"] = "MEASURE-SECOND-TURNOVER"
        second["measures"][1]["subject_id"] = "600001@XSHG"
        second["measures"][1]["value"] = 1.2
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [first, second],
            as_of="2026-08-12",
        )
        self.assertEqual(len(store["items"]), 2)

    def test_automatic_measure_identity_is_scoped_to_subject(self):
        first = market_evidence()
        second = deepcopy(first)
        for measure in first["measures"]:
            measure.pop("measure_id")
        for measure in second["measures"]:
            measure.pop("measure_id")
        second["evidence_id"] = "EV-MARKET-AUTO-SECOND"
        second["url"] = "https://tushare.pro/document/2?doc_id=33"
        second["security_ids"] = ["600001@XSHG"]
        for measure in second["measures"]:
            measure["subject_id"] = "600001@XSHG"
        second["measures"][0]["value"] = -3.4
        normalized_first = research_core.normalize_evidence_item(
            first, as_of="2026-08-12"
        )
        normalized_second = research_core.normalize_evidence_item(
            second, as_of="2026-08-12"
        )
        self.assertTrue(
            {
                measure["measure_id"] for measure in normalized_first["measures"]
            }.isdisjoint({
                measure["measure_id"] for measure in normalized_second["measures"]
            })
        )

    def test_one_evidence_item_cannot_bridge_two_security_subjects(self):
        raw = market_evidence()
        raw["security_ids"].append("600001@XSHG")
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "security_subject_must_be_single",
        ):
            research_core.normalize_evidence_item(raw, as_of="2026-08-12")

    def test_security_scoped_source_check_rejects_unbound_evidence(self):
        spec = task_spec()
        raw_evidence = evidence()
        raw_evidence["security_ids"] = []
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [raw_evidence],
            as_of=spec["as_of"],
        )
        capital_check = next(
            item for item in complete_source_checks()
            if item["fact_surface"] == "CAPITAL_ACTIONS"
        )
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "evidence_security_mismatch",
        ):
            research_core.normalize_source_check(
                capital_check, task_spec=spec, store=store,
                origin="HOST_INPUT",
            )

    def test_measure_definition_and_basis_cannot_smuggle_values(self):
        for field in ("definition", "basis"):
            with self.subTest(field=field):
                raw = evidence()
                raw["measures"][0][field] = "净利润口径为99亿元"
                with self.assertRaisesRegex(
                    research_core.ResearchContractError,
                    "definition_registry_mismatch|basis_unregistered",
                ):
                    research_core.normalize_evidence_item(
                        raw, as_of="2026-08-12"
                    )

    def test_measure_context_tuple_is_semantically_closed(self):
        cases = []
        wrong_surface = market_evidence()
        wrong_surface["fact_surface"] = "CAPITAL_ACTIONS"
        cases.append((wrong_surface, "market_metric_surface_mismatch"))

        wrong_market_basis = market_evidence()
        wrong_market_basis["measures"][0]["basis"] = "DISCLOSURE_REPORTED"
        cases.append((wrong_market_basis, "metric_basis_mismatch"))

        wrong_disclosure_basis = evidence()
        wrong_disclosure_basis["measures"][0]["basis"] = (
            "CALCULATED_PRICE_RETURN"
        )
        cases.append((wrong_disclosure_basis, "disclosure_metric_basis_mismatch"))

        future_measure = evidence()
        future_measure["measures"][0]["as_of"] = "2026-08-11"
        cases.append((future_measure, "as_of_after_source_date"))

        unknown_basis = evidence()
        unknown_basis["measures"][0]["basis"] = "CONTROLLED_FIXTURE"
        cases.append((unknown_basis, "basis_unregistered"))

        for raw, expected in cases:
            with self.subTest(expected=expected), self.assertRaisesRegex(
                research_core.ResearchContractError, expected
            ):
                research_core.normalize_evidence_item(
                    raw, as_of="2026-08-12"
                )

    def test_free_text_amount_is_rejected_even_when_a_measure_matches(self):
        raw = market_evidence()
        raw["claim"] = "全A成交额为2167.16亿元。"
        raw["measures"] = [{
            "measure_id": "MEASURE-A-SHARE-TURNOVER",
            "metric": "a_share_turnover",
            "value": 2167.1641,
            "unit": "CNY_BN",
            "dimension": "CURRENCY",
            "subject_id": "300001@XSHE",
            "as_of": "2026-08-12",
            "period": "SESSION",
            "basis": "PROVIDER_REPORTED",
            "definition": "A股市场成交额",
        }]
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "numeric_literal.must_be_rendered_from_measure",
        ):
            research_core.normalize_evidence_item(raw, as_of="2026-08-12")

    def test_numeric_guard_covers_signs_science_chinese_shares_and_points(self):
        for literal in (
            "-14.93%", "2167.16亿", "2.167e3亿元", "二千一百六十七亿元",
            "百分之十", "1.62亿股", "17.62个百分点", "1,234万元",
            "20日", "99\u200b亿元", "99**亿元**", "99<!-- -->亿元",
            "玖拾玖亿元", "九十九亿", "99bps", "¥99", "99美元",
            "三年", "1/3", "0.99x", "99&#20159;&#20803;",
            "99&nbsp;亿元", "99[亿元](https://example.invalid)", "99\\%",
            "99\ufe0f亿元", "99\u034f亿元",
        ):
            with self.subTest(literal=literal):
                invalid = market_evidence()
                invalid["claim"] = f"未经绑定的数值为{literal}。"
                invalid["measures"] = []
                with self.assertRaisesRegex(
                    research_core.ResearchContractError,
                    "numeric_literal.must_be_rendered_from_measure",
                ):
                    research_core.normalize_evidence_item(
                        invalid, as_of="2026-08-12"
                    )

    def test_report_visible_source_and_runtime_prose_cannot_smuggle_values(self):
        raw = evidence()
        raw["source"] = "深圳证券交易所｜公司净利润99亿元"
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "numeric_literal.must_be_rendered_from_measure:evidence.source",
        ):
            research_core.normalize_evidence_item(raw, as_of="2026-08-12")
        intent = action_intent()
        intent["current_uncertainty"] = "净利润是否达到99亿元"
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "action_intent.current_uncertainty",
        ):
            research_core.normalize_action_intent(intent)

    def test_host_content_binding_covers_decision_relevant_evidence_and_checks(self):
        spec = task_spec()
        store, evidence_ids = research_core.append_evidence_items(
            research_core.new_evidence_store(), [evidence()], as_of=spec["as_of"]
        )
        store, check_ids = research_core.append_source_checks(
            store, complete_source_checks(), task_spec=spec, origin="HOST_INPUT"
        )
        original = research_core._host_input_content_hash(
            store, evidence_ids, check_ids
        )
        for field, replacement in (
            ("boundary", "SINGLE_SOURCE"),
            ("decision_impact", "LOW"),
            ("source_tier", "SECONDARY"),
            ("claim_ids", ["OTHER-CLAIM"]),
            ("roles", ["RISK"]),
        ):
            with self.subTest(field=field):
                mutated = deepcopy(store)
                mutated["items"][0][field] = replacement
                self.assertNotEqual(
                    research_core._host_input_content_hash(
                        mutated, evidence_ids, check_ids
                    ),
                    original,
                )
        mutated_check = deepcopy(store)
        mutated_check["source_checks"][0]["limitation"] = "changed boundary"
        self.assertNotEqual(
            research_core._host_input_content_hash(
                mutated_check, evidence_ids, check_ids
            ),
            original,
        )

    def test_material_disclosure_title_cannot_be_dismissed_by_template(self):
        spec = task_spec()
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [evidence()], as_of=spec["as_of"]
        )
        raw = complete_source_checks()[0]
        raw["index_entries"][1]["title"] = "关于向控股股东借款暨关联交易的公告"
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "material_title_requires_opened_evidence",
        ):
            research_core.normalize_source_check(
                raw, task_spec=spec, store=store, origin="HOST_INPUT"
            )

    def test_material_title_cannot_hide_behind_generic_review(self):
        spec = task_spec()
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [evidence()], as_of=spec["as_of"]
        )
        raw = complete_source_checks()[0]
        raw["index_entries"][1].update({
            "title": "关于未弥补亏损达到实收股本总额三分之一的公告",
            "disposition": "REVIEWED_NOT_MATERIAL",
            "reason": "已打开，判断不重要。",
        })
        raw["checked_document_urls"].append(raw["index_entries"][1]["url"])
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "material_title_requires_opened_evidence",
        ):
            research_core.normalize_source_check(
                raw, task_spec=spec, store=store, origin="HOST_INPUT"
            )

    def test_material_title_evidence_requires_visible_snapshot_accounting(self):
        run = research_core.new_research_run(
            task_spec(1), {"method_version": "0.18.0"},
            execution_mode="CONTROLLED_FIXTURE",
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        low = evidence("EV-MATERIAL-LOW", impact="LOW")
        low["claim"] = "公司披露向控股股东借款暨关联交易，经济影响待判断。"
        low["measures"] = []
        low["document_facts"] = document_facts()
        packet = lead_packet(run)
        packet["evidence_items"].append(low)
        index_check = packet["source_checks"][0]
        marker_entry = index_check["index_entries"][1]
        marker_entry.update({
            "title": "关于向控股股东借款暨关联交易的公告",
            "url": low["url"], "disposition": "OPENED_RELEVANT",
            "reason": "涉及关联方资金约束，已打开并形成证据。",
        })
        index_check["checked_document_urls"].append(low["url"])
        index_check["evidence_ids"].append(low["evidence_id"])
        index_check["acquisition_receipt_ids"] = [
            "docsha256:" + low["document_facts"][0]["document_sha256"]
        ]
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "MATERIAL_INDEX_EVIDENCE_UNACCOUNTED|open_material_gaps_missing",
        ):
            research_core.apply_lead_packet(
                run, packet, receipt("LEAD", packet)
            )
        packet["decision_snapshot"][
            "non_material_evidence_dispositions"
        ].append({
            "evidence_id": low["evidence_id"],
            "decision_dimension": "CASH_FLOW",
            "reason": "借款额度尚未实际使用，暂不改变现金约束判断。",
            "reversal_condition": "实际提款或资金用途改变现金约束时重评",
        })
        packet["decision_snapshot"]["consumed_evidence_ids"].append(
            low["evidence_id"]
        )
        accepted = research_core.apply_lead_packet(
            run, packet, receipt("LEAD", packet)
        )
        rendered = research_report.render(accepted, view="user")
        self.assertIn("EVENT-", rendered)
        self.assertIn("STATUS@正文第三页第二段", rendered)
        self.assertIn("借款额度尚未实际使用", rendered)

    def test_event_family_id_is_derived_by_the_kernel_not_the_lead(self):
        run = research_core.new_research_run(
            task_spec(1), {"method_version": "0.18.0"},
            execution_mode="CONTROLLED_FIXTURE",
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        packet = lead_packet(run)
        packet["decision_snapshot"][
            "non_material_evidence_dispositions"
        ].append({
            "evidence_id": "EV-CAPITAL-1",
            "event_family_id": "EVENT-MODEL-INVENTED",
            "decision_dimension": "CASH_FLOW",
            "reason": "模型不应被要求猜测或提交内核事件族标识。",
            "reversal_condition": "出现宿主绑定正文事实后重新判断",
        })
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "event_family_id_is_kernel_owned",
        ):
            research_core.apply_lead_packet(run, packet, receipt("LEAD", packet))

    def test_material_title_cannot_be_closed_with_shallow_generic_disposition(self):
        run = research_core.new_research_run(
            task_spec(1), {"method_version": "0.18.0"},
            execution_mode="CONTROLLED_FIXTURE",
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        low = evidence("EV-MATERIAL-SHALLOW", impact="LOW")
        low["claim"] = "公司发布向控股股东借款暨关联交易公告。"
        low["measures"] = []
        packet = lead_packet(run)
        packet["evidence_items"].append(low)
        index_check = packet["source_checks"][0]
        index_check["index_entries"][1].update({
            "title": "关于向控股股东借款暨关联交易的公告",
            "url": low["url"], "disposition": "OPENED_RELEVANT",
            "reason": "已打开公告。",
        })
        index_check["checked_document_urls"].append(low["url"])
        index_check["evidence_ids"].append(low["evidence_id"])
        packet["decision_snapshot"][
            "non_material_evidence_dispositions"
        ].append({
            "evidence_id": low["evidence_id"],
            "decision_dimension": "CASH_FLOW",
            "reason": "不影响判断。",
            "reversal_condition": "出现变化时重新判断",
        })
        packet["decision_snapshot"]["consumed_evidence_ids"].append(
            low["evidence_id"]
        )
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "non_material_disposition_invalid|requires_body_fact",
        ):
            research_core.apply_lead_packet(
                run, packet, receipt("LEAD", packet)
            )

    def test_freeze_title_cannot_be_dismissed_by_generic_title_review(self):
        spec = task_spec()
        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [evidence()], as_of=spec["as_of"]
        )
        raw = complete_source_checks()[0]
        raw["index_entries"][1].update({
            "title": "关于控股股东所持股份被司法冻结的公告",
            "disposition": "DISMISSED_BY_TITLE",
            "reason": "标题层判断与本题无关。",
        })
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "material_title_requires_opened_evidence",
        ):
            research_core.normalize_source_check(
                raw, task_spec=spec, store=store, origin="HOST_INPUT"
            )

    def test_document_facts_require_acquisition_hash_and_event_specific_facts(self):
        spec = task_spec()
        low = evidence("EV-MATERIAL-HOST", impact="LOW")
        low["claim"] = "公司披露向控股股东借款暨关联交易，经济影响待判断。"
        low["measures"] = []
        low["document_facts"] = document_facts()
        raw_check = complete_source_checks(low["evidence_id"])[0]
        raw_check["index_entries"][0]["title"] = (
            "关于向控股股东借款暨关联交易的公告"
        )

        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [low], as_of=spec["as_of"]
        )
        store, _ = research_core.append_source_checks(
            store, [raw_check], task_spec=spec, origin="HOST_INPUT"
        )
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "document_fact.acquisition_hash_unbound",
        ):
            research_core.validate_document_fact_acquisition(store)

        raw_check["acquisition_receipt_ids"] = [
            "docsha256:" + low["document_facts"][0]["document_sha256"]
        ]
        wrong_semantics = deepcopy(low)
        wrong_semantics["evidence_id"] = "EV-MATERIAL-WRONG-TYPES"
        wrong_semantics["url"] = (
            "https://www.szse.cn/disclosure/ev-material-wrong-types.html"
        )
        wrong_semantics["document_facts"][0]["fact_id"] = "DF-WRONG-SCOPE"
        wrong_semantics["document_facts"][0]["fact_type"] = "SCOPE"
        wrong_check = complete_source_checks(wrong_semantics["evidence_id"])[0]
        wrong_check["index_entries"][0]["title"] = (
            "关于向控股股东借款暨关联交易的公告"
        )
        wrong_check["acquisition_receipt_ids"] = [
            "docsha256:"
            + wrong_semantics["document_facts"][0]["document_sha256"]
        ]
        wrong_store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), [wrong_semantics],
            as_of=spec["as_of"],
        )
        wrong_store, _ = research_core.append_source_checks(
            wrong_store, [wrong_check], task_spec=spec, origin="HOST_INPUT"
        )
        research_core.validate_document_fact_acquisition(wrong_store)
        self.assertFalse(research_core.material_evidence_has_body_facts(
            wrong_store, wrong_semantics["evidence_id"]
        ))

    def test_marker_material_change_still_requires_host_body_extraction(self):
        run = research_core.new_research_run(
            task_spec(1), {"method_version": "0.18.0"},
            execution_mode="CONTROLLED_FIXTURE",
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        low = evidence("EV-MATERIAL-CHANGE", impact="LOW")
        low["claim"] = "公司发布向控股股东借款暨关联交易公告。"
        low["measures"] = []
        packet = lead_packet(run)
        packet["evidence_items"].append(low)
        index_check = packet["source_checks"][0]
        index_check["index_entries"][1].update({
            "title": "关于向控股股东借款暨关联交易的公告",
            "url": low["url"], "disposition": "OPENED_RELEVANT",
            "reason": "涉及关联方资金约束，已打开并形成证据。",
        })
        index_check["checked_document_urls"].append(low["url"])
        index_check["evidence_ids"].append(low["evidence_id"])
        packet["decision_snapshot"]["material_changes"].append({
            "change_id": "MC-MARKER-1", "claim_id": "MC-MARKER-1",
            "title": "关联借款公告", "summary": "公司发布相关公告。",
            "decision_effect": "该事项可能影响后续判断。",
            "boundary": "SINGLE_SOURCE", "evidence_ids": [low["evidence_id"]],
        })
        packet["decision_snapshot"]["consumed_evidence_ids"].append(
            low["evidence_id"]
        )
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "decision_ready_has_hard_obligations|MATERIAL_BODY_FACTS_REQUIRED|open_material_gaps_missing",
        ):
            research_core.apply_lead_packet(
                run, packet, receipt("LEAD", packet)
            )

    def test_marker_evidence_cannot_be_counted_as_two_material_changes(self):
        run = research_core.new_research_run(
            task_spec(1), {"method_version": "0.18.0"},
            execution_mode="CONTROLLED_FIXTURE",
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        marker = evidence("EV-MATERIAL-DUPLICATE", impact="LOW")
        marker["claim"] = "公司披露向控股股东借款暨关联交易。"
        marker["measures"] = []
        marker["document_facts"] = document_facts()
        packet = lead_packet(run)
        packet["evidence_items"].append(marker)
        index_check = packet["source_checks"][0]
        index_check["index_entries"][1].update({
            "title": "关于向控股股东借款暨关联交易的公告",
            "url": marker["url"], "disposition": "OPENED_RELEVANT",
            "reason": "涉及关联方资金约束，已打开并形成证据。",
        })
        index_check["checked_document_urls"].append(marker["url"])
        index_check["evidence_ids"].append(marker["evidence_id"])
        index_check["acquisition_receipt_ids"] = [
            "docsha256:" + marker["document_facts"][0]["document_sha256"]
        ]
        for suffix in ("A", "B"):
            packet["decision_snapshot"]["material_changes"].append({
                "change_id": f"MC-MARKER-{suffix}",
                "claim_id": f"MC-MARKER-{suffix}",
                "title": "关联借款事项",
                "summary": "关联借款事项改变现金约束判断。",
                "decision_effect": "需要跟踪实际提款与资金用途。",
                "boundary": "SINGLE_SOURCE",
                "evidence_ids": [marker["evidence_id"]],
            })
        packet["decision_snapshot"]["consumed_evidence_ids"].append(
            marker["evidence_id"]
        )
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "material_evidence_assigned_multiple_times",
        ):
            research_core.apply_lead_packet(run, packet, receipt("LEAD", packet))

    def test_one_event_family_must_be_one_material_change_aggregate(self):
        run = research_core.new_research_run(
            task_spec(1), {"method_version": "0.18.0"},
            execution_mode="CONTROLLED_FIXTURE",
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        first = evidence("EV-MATERIAL-FAMILY-A", impact="LOW")
        first["claim"] = "公司披露向控股股东借款暨关联交易。"
        first["measures"] = []
        first["document_facts"] = document_facts(event_anchor="LOAN-FAMILY-A")
        second = evidence("EV-MATERIAL-FAMILY-B", impact="LOW")
        second["claim"] = "公司补充披露同一关联借款事项。"
        second["measures"] = []
        second["document_facts"] = document_facts(event_anchor="LOAN-FAMILY-A")
        second_document_sha = hashlib.sha256(
            b"RELATED_PARTY_BORROWING:LOAN-FAMILY-A:supplement"
        ).hexdigest()
        for fact in second["document_facts"]:
            fact["document_sha256"] = second_document_sha
            fact["fact_id"] = research_core.stable_id(
                "DF", second["evidence_id"], fact["fact_type"]
            )

        packet = lead_packet(run)
        packet["evidence_items"].extend([first, second])
        index_check = packet["source_checks"][0]
        for entry, marker in zip(
            index_check["index_entries"][1:3], (first, second)
        ):
            entry.update({
                "title": "关于向控股股东借款暨关联交易的公告",
                "url": marker["url"], "disposition": "OPENED_RELEVANT",
                "reason": "涉及关联方资金约束，已打开并形成证据。",
            })
            index_check["checked_document_urls"].append(marker["url"])
            index_check["evidence_ids"].append(marker["evidence_id"])
            index_check.setdefault("acquisition_receipt_ids", []).append(
                "docsha256:"
                + marker["document_facts"][0]["document_sha256"]
            )
        for suffix, marker in (("A", first), ("B", second)):
            packet["decision_snapshot"]["material_changes"].append({
                "change_id": f"MC-FAMILY-{suffix}",
                "claim_id": f"MC-FAMILY-{suffix}",
                "title": "关联借款事项",
                "summary": "关联借款事项改变现金约束判断。",
                "decision_effect": "需要跟踪实际提款与资金用途。",
                "boundary": "SINGLE_SOURCE",
                "evidence_ids": [marker["evidence_id"]],
            })
            packet["decision_snapshot"]["consumed_evidence_ids"].append(
                marker["evidence_id"]
            )
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "material_event_family_must_be_single_aggregate",
        ):
            research_core.apply_lead_packet(run, packet, receipt("LEAD", packet))


class SingleWriterTests(unittest.TestCase):
    def setUp(self):
        self.run = research_core.new_research_run(
            task_spec(), {"method_version": "0.18.0"}, execution_mode="CONTROLLED_FIXTURE"
        )
        self.run = bind(self.run, "LEAD_RESEARCH", "LEAD")

    def test_complete_lead_packet_writes_one_snapshot_and_report(self):
        packet = lead_packet(self.run)
        updated = research_core.apply_lead_packet(
            self.run, packet, receipt("LEAD", packet)
        )
        self.assertEqual(updated["decision_snapshot"]["version"], 1)
        self.assertEqual(updated["run_ledger"]["next_call"], "REPORT")
        self.assertEqual(research_core.hard_obligations(updated), [])
        report = research_report.render(updated)
        self.assertIn("资本事件已改变融资边界", report)
        self.assertIn("没有带执行来源的 Challenger", report)
        self.assertNotIn("隔离质证已完成", report)

    def test_high_evidence_cannot_be_hidden_from_material_accounting(self):
        packet = lead_packet(self.run)
        packet["decision_snapshot"]["material_changes"] = []
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "HIGH_EVIDENCE|open_material_gaps",
        ):
            research_core.apply_lead_packet(self.run, packet, receipt("LEAD", packet))

    def test_new_evidence_must_be_bound_to_the_same_packet_check(self):
        packet = lead_packet(self.run)
        packet["source_checks"] = []
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "new_item_requires_same_packet_source_check",
        ):
            research_core.apply_lead_packet(self.run, packet, receipt("LEAD", packet))

    def test_consumed_ids_must_equal_visible_snapshot_evidence(self):
        packet = lead_packet(self.run)
        packet["decision_snapshot"]["consumed_evidence_ids"] = []
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "consumed_evidence",
        ):
            research_core.apply_lead_packet(self.run, packet, receipt("LEAD", packet))

    def test_user_visible_snapshot_numbers_cannot_bypass_typed_measures(self):
        packet = lead_packet(self.run)
        packet["decision_snapshot"]["self_countercases"][0]["argument"] = (
            "未经证据绑定的融资额为2167.16亿。"
        )
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "numeric_literal.must_be_rendered_from_measure",
        ):
            research_core.apply_lead_packet(
                self.run, packet, receipt("LEAD", packet)
            )
        stop_packet = lead_packet(self.run)
        stop_packet["stop_reason"] = "公司净利润99亿元，因此停止"
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "lead.stop_reason"
        ):
            research_core.apply_lead_packet(
                self.run, stop_packet, receipt("LEAD", stop_packet, suffix="STOP")
            )

    def test_agenda_question_is_task_owned_and_cannot_smuggle_a_number(self):
        packet = lead_packet(self.run)
        packet["decision_snapshot"]["agenda_answers"][0]["question"] = (
            "融资金额是否为999亿元？"
        )
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "answer_question_text_drift|numeric_literal.must_be_rendered_from_measure",
        ):
            research_core.apply_lead_packet(
                self.run, packet, receipt("LEAD", packet)
            )

    def test_factual_core_judgment_cannot_be_uncited_even_when_degraded(self):
        packet = lead_packet(self.run)
        snap = packet["decision_snapshot"]
        snap["decision_status"] = "RESEARCH_INCOMPLETE"
        snap["core_judgment"]["evidence_ids"] = []
        snap["consumed_evidence_ids"] = ["EV-CAPITAL-1"]
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "core_non_hypothesis_requires_evidence",
        ):
            research_core.apply_lead_packet(self.run, packet, receipt("LEAD", packet))

    def test_partial_non_hypothesis_answer_still_requires_evidence(self):
        packet = lead_packet(self.run)
        answer = packet["decision_snapshot"]["agenda_answers"][0]
        answer["status"] = "PARTIAL"
        answer["evidence_ids"] = []
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "answer_requires_evidence"
        ):
            research_core.apply_lead_packet(self.run, packet, receipt("LEAD", packet))

    def test_nested_parallel_semantics_are_rejected(self):
        packet = lead_packet(self.run)
        packet["decision_snapshot"]["core_judgment"]["hidden_thesis"] = "parallel truth"
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "unknown_item_fields"
        ):
            research_core.apply_lead_packet(self.run, packet, receipt("LEAD", packet))

    def test_continue_control_intent_does_not_pollute_user_validation_fields(self):
        packet = lead_packet(self.run, continue_research=True)
        updated = research_core.apply_lead_packet(
            self.run, packet, receipt("LEAD", packet)
        )
        self.assertEqual(updated["run_ledger"]["next_call"], "LEAD_RESEARCH")
        self.assertEqual(
            updated["decision_snapshot"]["lowest_cost_next_validation"][0][
                "availability"
            ],
            "WAIT_FOR_EVENT",
        )

    def test_research_loop_cannot_consume_budget_without_new_observation(self):
        run = research_core.new_research_run(
            task_spec(2), {"method_version": "0.18.0"},
            execution_mode="CONTROLLED_FIXTURE",
        )
        run = research_core.seed_research_run(
            run, [evidence()], complete_source_checks()
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        packet = lead_packet(run)
        packet["evidence_items"] = []
        packet["source_checks"] = []
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "research_requires_observation_delta",
        ):
            research_core.apply_lead_packet(run, packet, receipt("LEAD", packet))

    def test_discovered_priority_candidate_creates_company_reality_obligations(self):
        spec = research_core.normalize_task_spec({
            "question": "产业变化映射到哪些上市公司？",
            "as_of": "2026-08-12",
            "budget": 2,
            "primary_entities": [{
                "entity_id": "E1",
                "name": "测试产业",
                "entity_type": "INDUSTRY",
            }],
        })
        candidate_snapshot = research_core.empty_snapshot(spec)
        candidate_snapshot["candidates_by_horizon"] = [{
            "horizon": "EVENT_DAYS",
            "candidates": [{
                "stance": "CONDITIONAL_PRIORITY",
                "name": "动态发现公司",
                "ticker": "300001",
                "exchange": "SZSE",
            }],
        }]
        obligations = research_core.coverage_obligations(
            spec, research_core.new_evidence_store(), candidate_snapshot
        )
        candidate_obligations = {
            item["fact_surface"] for item in obligations
            if item["obligation_id"].startswith(
                "CANDIDATE_COVERAGE:300001@XSHE:"
            )
        }
        self.assertEqual(
            candidate_obligations,
            set(research_core.LISTED_COMPANY_FACT_SURFACES),
        )

    def test_watch_cannot_be_an_empty_named_row(self):
        packet = lead_packet(self.run)
        packet["decision_snapshot"]["candidates_by_horizon"] = [{
            "horizon": "EVENT_DAYS", "candidates": [{
                "claim_id": "CAND-WATCH-1", "stance": "WATCH",
                "name": "测试公司", "ticker": "300001", "exchange": "SZSE",
                "economic_exposure": "", "market_role": "", "why_now": "",
                "closest_alternative": "UNKNOWN", "switch_condition": "",
                "trigger": "", "invalidation": "",
                "price_crowding_boundary": "", "boundary": "INFERENCE",
                "value_path_ids": [], "exposure_evidence_ids": [],
                "market_evidence_ids": [], "alternative_evidence_ids": [],
                "evidence_ids": ["EV-CAPITAL-1"],
            }],
        }]
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "watch_candidate_missing|watch_candidate_exposure_evidence_required|watch_candidate_market_evidence_required",
        ):
            research_core.apply_lead_packet(
                self.run, packet, receipt("LEAD", packet)
            )

    def test_no_setup_cannot_name_or_borrow_an_alternative(self):
        packet = lead_packet(self.run)
        packet["decision_snapshot"]["candidates_by_horizon"] = [{
            "horizon": "EVENT_DAYS", "candidates": [{
                "claim_id": "CAND-NONE-1", "stance": "NO_SETUP",
                "name": "", "ticker": "", "exchange": "",
                "economic_exposure": "", "market_role": "", "why_now": "",
                "closest_alternative": "600001@XSHG", "switch_condition": "",
                "trigger": "", "invalidation": "",
                "price_crowding_boundary": "", "boundary": "",
                "value_path_ids": [], "exposure_evidence_ids": [],
                "market_evidence_ids": [], "alternative_evidence_ids": [],
                "evidence_ids": [],
            }],
        }]
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "no_setup_must_be_empty_sentinel",
        ):
            research_core.apply_lead_packet(
                self.run, packet, receipt("LEAD", packet)
            )

    def test_fake_independent_challenge_is_rejected_without_receipt(self):
        packet = lead_packet(self.run)
        packet["decision_snapshot"]["challenge_resolutions"] = [{
            "challenge_id": "CH-FAKE-1",
            "target_claim_ids": ["CORE-1"],
            "resolution": "REJECTED",
            "summary": "fake",
            "lead_response": "fake",
            "evidence_ids": [],
        }]
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "challenge_without_receipt",
        ):
            research_core.apply_lead_packet(self.run, packet, receipt("LEAD", packet))

    def test_priority_candidate_is_blocked_when_snapshot_is_not_ready(self):
        packet = lead_packet(self.run)
        snap = packet["decision_snapshot"]
        snap["decision_status"] = "RESEARCH_INCOMPLETE"
        snap["candidates_by_horizon"] = [{
            "horizon": "EVENT_DAYS",
            "candidates": [{
                "claim_id": "CAND-1", "stance": "CONDITIONAL_PRIORITY",
                "name": "测试公司", "ticker": "300001", "exchange": "SZSE",
                "economic_exposure": "融资改善", "market_role": "事件载体",
                "why_now": "公告出现", "closest_alternative": "UNKNOWN",
                "switch_condition": "替代更强", "trigger": "到账",
                "invalidation": "终止", "price_crowding_boundary": "量价确认",
                "alternative_evidence_ids": [],
                "evidence_ids": ["EV-CAPITAL-1"],
            }],
        }]
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "priority_requires_decision_ready",
        ):
            research_core.apply_lead_packet(self.run, packet, receipt("LEAD", packet))

    def test_priority_candidate_requires_both_industry_and_market_bindings(self):
        packet = lead_packet(self.run)
        snap = packet["decision_snapshot"]
        snap["value_transfer_paths"] = [{
            "path_id": "VP-1", "constraint_change": "资本约束改善",
            "profit_pool_shift": "可投资金增加", "economic_exposure": "融资能力",
            "market_carrier": "公告事件载体", "boundary": "FACT",
            "evidence_ids": ["EV-CAPITAL-1"],
        }]
        snap["market_by_horizon"] = [{
            "market_view_id": "MV-1", "horizon": "EVENT_DAYS",
            "current_state": "公告已出", "mechanism": "事件资金交易融资预期",
            "switch_condition": "资金未到账", "evidence_ids": ["EV-CAPITAL-1"],
        }]
        snap["candidates_by_horizon"] = [{
            "horizon": "EVENT_DAYS", "candidates": [{
                "claim_id": "CAND-1", "stance": "CONDITIONAL_PRIORITY",
                "name": "测试公司", "ticker": "300001", "exchange": "SZSE",
                "economic_exposure": "融资改善", "market_role": "事件载体",
                "why_now": "公告出现", "closest_alternative": "UNKNOWN",
                "switch_condition": "替代更强", "trigger": "到账",
                "invalidation": "终止", "price_crowding_boundary": "量价确认",
                "value_path_ids": ["VP-1"],
                "exposure_evidence_ids": ["EV-CAPITAL-1"],
                "market_evidence_ids": [],
                "alternative_evidence_ids": [],
                "evidence_ids": ["EV-CAPITAL-1"],
            }],
        }]
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "priority_candidate_market_evidence_required",
        ):
            research_core.apply_lead_packet(self.run, packet, receipt("LEAD", packet))

    def test_priority_candidate_forms_one_connected_industry_market_path(self):
        packet = lead_packet(self.run)
        packet["evidence_items"].append(market_evidence())
        for check in packet["source_checks"]:
            if check["fact_surface"] == "MARKET_PRICE_LIQUIDITY":
                check.update({
                    "outcome": "FOUND",
                    "evidence_ids": ["EV-MARKET-1"],
                    "checked_document_urls": [market_evidence()["url"]],
                    "negative_scope": "",
                })
        snap = packet["decision_snapshot"]
        snap["value_transfer_paths"] = [{
            "path_id": "VP-1", "constraint_change": "资本约束改善",
            "profit_pool_shift": "可投资金增加", "economic_exposure": "融资能力",
            "market_carrier": "公告事件载体", "boundary": "FACT",
            "evidence_ids": ["EV-CAPITAL-1"],
        }]
        snap["market_by_horizon"] = [{
            "market_view_id": "MV-1", "horizon": "EVENT_DAYS",
            "current_state": "相对强度与换手已形成", "mechanism": "事件资金定价",
            "switch_condition": "相对强度转负", "boundary": "SINGLE_SOURCE",
            "evidence_ids": ["EV-MARKET-1"],
        }]
        snap["candidates_by_horizon"] = [{
            "horizon": "EVENT_DAYS", "candidates": [{
                "claim_id": "CAND-1", "stance": "CONDITIONAL_PRIORITY",
                "name": "测试公司", "ticker": "300001", "exchange": "SZSE",
                "economic_exposure": "融资改善", "market_role": "事件载体",
                "why_now": "公告与相对强度共振", "closest_alternative": "UNKNOWN",
                "switch_condition": "替代强度反超", "trigger": "资金到账",
                "invalidation": "融资终止", "price_crowding_boundary": "放量滞涨",
                "boundary": "INFERENCE", "value_path_ids": ["VP-1"],
                "exposure_evidence_ids": ["EV-CAPITAL-1"],
                "market_evidence_ids": ["EV-MARKET-1"],
                "alternative_evidence_ids": [],
                "evidence_ids": ["EV-CAPITAL-1", "EV-MARKET-1"],
            }],
        }]
        snap["consumed_evidence_ids"] = ["EV-CAPITAL-1", "EV-MARKET-1"]
        final = research_core.apply_lead_packet(
            self.run, packet, receipt("LEAD", packet)
        )
        candidate = final["decision_snapshot"]["candidates_by_horizon"][0][
            "candidates"
        ][0]
        self.assertEqual(candidate["stance"], "CONDITIONAL_PRIORITY")

    def test_market_carrier_does_not_require_a_recommendation_stance(self):
        packet = lead_packet(self.run)
        packet["evidence_items"].append(market_evidence())
        for check in packet["source_checks"]:
            if check["fact_surface"] == "MARKET_PRICE_LIQUIDITY":
                check.update({
                    "outcome": "FOUND",
                    "evidence_ids": ["EV-MARKET-1"],
                    "checked_document_urls": [market_evidence()["url"]],
                    "negative_scope": "",
                })
        snap = packet["decision_snapshot"]
        snap["market_by_horizon"] = [{
            "market_view_id": "MV-1", "horizon": "EVENT_DAYS",
            "current_state": "相对收益和换手状态已冻结",
            "mechanism": "事件资金寻找高辨识度载体",
            "switch_condition": "相对强度转弱", "boundary": "SINGLE_SOURCE",
            "evidence_ids": ["EV-MARKET-1"],
        }]
        snap["market_carriers_by_horizon"] = [{
            "horizon": "EVENT_DAYS", "carriers": [{
                "claim_id": "CARRIER-1", "name": "测试公司",
                "ticker": "300001", "exchange": "SZSE",
                "market_role": "融资事件载体",
                "why_traded": "公告与相对收益形成观察窗口",
                "closest_alternative": "UNKNOWN",
                "switch_condition": "替代标的相对强度反超",
                "boundary": "INFERENCE",
                "market_evidence_ids": ["EV-MARKET-1"],
                "alternative_evidence_ids": [],
                "evidence_ids": ["EV-MARKET-1"],
            }],
        }]
        snap["candidates_by_horizon"] = []
        snap["consumed_evidence_ids"] = ["EV-CAPITAL-1", "EV-MARKET-1"]
        final = research_core.apply_lead_packet(
            self.run, packet, receipt("LEAD", packet)
        )
        self.assertEqual(
            final["decision_snapshot"]["market_carriers_by_horizon"][0][
                "carriers"
            ][0]["ticker"],
            "300001",
        )
        self.assertEqual(final["decision_snapshot"]["candidates_by_horizon"], [])
        unbound = deepcopy(packet)
        carrier = unbound["decision_snapshot"][
            "market_carriers_by_horizon"
        ][0]["carriers"][0]
        carrier["closest_alternative"] = "600001@XSHG"
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "alternative_binding_required",
        ):
            research_core.apply_lead_packet(
                self.run, unbound, receipt("LEAD", unbound, suffix="ALT")
            )

    def test_negative_recommendation_stance_is_not_in_the_research_contract(self):
        packet = lead_packet(self.run)
        packet["decision_snapshot"]["candidates_by_horizon"] = [{
            "horizon": "EVENT_DAYS", "candidates": [{
                "claim_id": "CAND-NEGATIVE", "stance": "AVOID",
                "name": "测试公司", "ticker": "300001", "exchange": "SZSE",
                "economic_exposure": "", "market_role": "", "why_now": "",
                "closest_alternative": "UNKNOWN", "switch_condition": "",
                "trigger": "", "invalidation": "",
                "price_crowding_boundary": "", "boundary": "SINGLE_SOURCE",
                "value_path_ids": [], "exposure_evidence_ids": [],
                "market_evidence_ids": [], "alternative_evidence_ids": [],
                "evidence_ids": ["EV-CAPITAL-1"],
            }],
        }]
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "candidate_stance_invalid"
        ):
            research_core.apply_lead_packet(
                self.run, packet, receipt("LEAD", packet)
            )

    def test_host_append_after_commit_creates_pending_work_not_invalid_history(self):
        run = research_core.new_research_run(
            task_spec(2), {"method_version": "0.18.0"},
            execution_mode="CONTROLLED_FIXTURE",
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        first = lead_packet(run, continue_research=True)
        run = research_core.apply_lead_packet(
            run, first, receipt("LEAD", first)
        )
        host_market = market_evidence()
        host_market["decision_impact"] = "HIGH"
        host_check = {
            "source_check_id": "SC-HOST-MARKET-AFTER-COMMIT",
            "entity_id": "E1", "security_id": "300001@XSHE",
            "fact_surface": "MARKET_PRICE_LIQUIDITY",
            "window_start": "2026-08-12", "window_end": "2026-08-12",
            "queries": [host_market["url"]], "official_index_url": "",
            "checked_document_urls": [host_market["url"]],
            "index_entries": [], "enumeration_complete": False,
            "outcome": "FOUND", "evidence_ids": ["EV-MARKET-1"],
            "negative_scope": "", "limitation": "host snapshot",
        }
        updated = research_core.ingest_host_evidence(
            run, [host_market], [host_check], input_id="HOST-AFTER-COMMIT"
        )
        research_core.validate_persisted_run(updated)
        self.assertEqual(
            updated["decision_snapshot"], run["decision_snapshot"]
        )
        self.assertIn(
            "HIGH_EVIDENCE_UNACCOUNTED",
            {item["kind"] for item in research_core.hard_obligations(updated)},
        )


class ChallengerLoopTests(unittest.TestCase):
    def test_self_declared_verified_label_cannot_become_independent_receipt(self):
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "self_declared_receipt_must_be_unverified",
        ):
            research_core._normalize_receipt({
                "receipt_id": "RCPT-SELF-DECLARED",
                "status": "SUCCEEDED",
                "agent_id": "claimed-separate-agent",
                "isolation": "VERIFIED_PROCESS",
                "receipt_provenance": "SELF_DECLARED",
                "process_id": 0,
                "host_runtime": "codex",
                "prompt_sha256": "a" * 64,
                "payload_sha256": "b" * 64,
            }, role="CHALLENGER")

    def test_challenger_is_a_bounded_tool_and_only_lead_resolves(self):
        run = research_core.new_research_run(
            task_spec(3), {"method_version": "0.18.0"}, execution_mode="CONTROLLED_FIXTURE"
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        first_packet = lead_packet(run, request_challenge=True)
        after_lead = research_core.apply_lead_packet(
            run, first_packet, receipt("LEAD", first_packet)
        )
        self.assertEqual(after_lead["run_ledger"]["next_call"], "CHALLENGER")
        challenge_evidence = evidence("EV-CHALLENGE-1", impact="MEDIUM")
        challenge_evidence["claim"] = "融资尚未到账，计划不等于现金。"
        challenge = {
            "challenge_id": "CH-CAPITAL-1",
            "target_claim_ids": ["CORE-1"],
            "evidence_items": [challenge_evidence],
            "source_checks": [challenge_source_check()],
            "attacks": [{
                "target_claim_id": "CORE-1",
                "argument": "融资计划尚未到账，不能视为实质约束改善。",
                "evidence_ids": ["EV-CHALLENGE-1"],
                "severity": "LOAD_BEARING",
            }],
            "strongest_countercase": "计划可能失败或延迟。",
        }
        after_lead = bind(after_lead, "CHALLENGER", "CHALLENGER")
        after_challenge = research_core.apply_challenge_packet(
            after_lead, challenge, receipt(
                "CHALLENGER", challenge, challenge_id="CH-CAPITAL-1",
                agent_id="agent-bounded-challenger",
            )
        )
        self.assertEqual(after_challenge["decision_snapshot"], after_lead["decision_snapshot"])
        self.assertEqual(after_challenge["run_ledger"]["next_call"], "LEAD_RESOLUTION")
        resolution = {
            "challenge_id": "CH-CAPITAL-1",
            "challenge_packet_sha256": research_core.stable_hash(
                after_challenge["run_ledger"]["challenge_packets"][-1]
            ),
            "target_claim_ids": ["CORE-1"],
            "resolution": "ACCEPTED",
            "summary": "计划不等于到账。",
            "lead_response": "将核心判断收窄为融资可见度改善。",
            "evidence_ids": ["EV-CHALLENGE-1"],
        }
        resolution_packet = {
            "action_intent": action_intent("RESOLUTION"),
            "evidence_items": [],
            "source_checks": [],
            "decision_snapshot": snapshot(
                after_challenge, version=2, challenge=resolution,
                extra_evidence_ids=["EV-CHALLENGE-1"],
            ),
            "challenge_request": None,
            "continue_research": False,
            "stop_reason": "独立挑战已处理",
        }
        after_challenge = bind(after_challenge, "LEAD_RESOLUTION", "LEAD")
        final = research_core.apply_lead_packet(
            after_challenge, resolution_packet,
            receipt("LEAD", resolution_packet, "2"), resolution=True
        )
        self.assertEqual(final["run_ledger"]["next_call"], "REPORT")
        self.assertEqual(final["run_ledger"]["completed_research_loops"], 2)
        self.assertEqual(research_core.hard_obligations(final), [])
        rendered = research_report.render(final)
        self.assertIn("CH-CAPITAL-1", rendered)
        self.assertIn("受控 fixture Challenger", rendered)

    def test_challenger_free_text_numbers_require_typed_evidence(self):
        run = research_core.new_research_run(
            task_spec(3), {"method_version": "0.18.0"},
            execution_mode="CONTROLLED_FIXTURE",
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        first = lead_packet(run, request_challenge=True)
        run = research_core.apply_lead_packet(run, first, receipt("LEAD", first))
        run = bind(run, "CHALLENGER", "CHALLENGER")
        challenge = {
            "challenge_id": "CH-CAPITAL-1",
            "target_claim_ids": ["CORE-1"],
            "evidence_items": [], "source_checks": [],
            "attacks": [{
                "target_claim_id": "CORE-1",
                "argument": "融资额2167.16亿仍未到账。",
                "evidence_ids": [], "severity": "LOAD_BEARING",
            }],
            "strongest_countercase": "融资额2167.16亿可能终止。",
        }
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "numeric_literal.must_be_rendered_from_measure",
        ):
            research_core.apply_challenge_packet(
                run, challenge,
                receipt("CHALLENGER", challenge, agent_id="bounded-agent"),
            )

    def test_lead_cannot_rewrite_the_challenge_packet_during_resolution(self):
        run = research_core.new_research_run(
            task_spec(3), {"method_version": "0.18.0"}, execution_mode="CONTROLLED_FIXTURE"
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        first = lead_packet(run, request_challenge=True)
        run = research_core.apply_lead_packet(run, first, receipt("LEAD", first))
        challenge = {
            "challenge_id": "CH-CAPITAL-1", "target_claim_ids": ["CORE-1"],
            "evidence_items": [],
            "source_checks": [],
            "attacks": [{
                "target_claim_id": "CORE-1", "argument": "计划不等于到账",
                "evidence_ids": [], "severity": "LOAD_BEARING",
            }],
            "strongest_countercase": "融资计划可能终止。",
        }
        run = bind(run, "CHALLENGER", "CHALLENGER")
        run = research_core.apply_challenge_packet(
            run, challenge, receipt(
                "CHALLENGER", challenge, agent_id="bounded-agent"
            )
        )
        resolution = {
            "challenge_id": "CH-CAPITAL-1",
            "challenge_packet_sha256": "0" * 64,
            "target_claim_ids": ["CORE-1"], "resolution": "REJECTED",
            "summary": "被改写的挑战", "lead_response": "拒绝", "evidence_ids": [],
        }
        packet = {
            "action_intent": action_intent("RESOLUTION"),
            "evidence_items": [], "source_checks": [],
            "decision_snapshot": snapshot(run, version=2, challenge=resolution),
            "challenge_request": None, "continue_research": False,
            "stop_reason": "resolved",
        }
        run = bind(run, "LEAD_RESOLUTION", "LEAD")
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "challenge_packet_hash_mismatch"
        ):
            research_core.apply_lead_packet(
                run, packet, receipt("LEAD", packet, "2"), resolution=True
            )

    def test_challenge_cannot_start_without_remaining_budget(self):
        run = research_core.new_research_run(
            task_spec(1), {"method_version": "0.18.0"}, execution_mode="CONTROLLED_FIXTURE"
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        packet = lead_packet(run, request_challenge=True)
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "challenge_requires_remaining_budget",
        ):
            research_core.apply_lead_packet(
                run, packet, receipt("LEAD", packet)
            )

    def test_codex_native_subagent_is_the_harness_challenger_path(self):
        run = research_core.new_research_run(
            task_spec(3), {"method_version": "0.18.0"},
            execution_mode="HARNESS_ORCHESTRATED",
        )
        run = research_core.seed_research_run(
            run, [evidence()], complete_source_checks()
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        new_observation = evidence("EV-LEAD-OBSERVATION", impact="LOW")
        first = lead_packet(run, request_challenge=True)
        first["evidence_items"] = [new_observation]
        first["source_checks"] = [
            challenge_source_check("EV-LEAD-OBSERVATION")
        ]
        first["decision_snapshot"] = snapshot(run)
        lead_receipt = {
            "receipt_id": "CODEX-LEAD-1", "status": "SUCCEEDED",
            "agent_id": "/root", "isolation": "UNVERIFIED",
            "receipt_provenance": "SELF_DECLARED", "process_id": 0,
            "host_runtime": "codex", "external_tools_enabled": False,
            "prompt_sha256": "a" * 64,
            "payload_sha256": research_core.stable_hash(first),
        }
        run = research_core.apply_lead_packet(run, first, lead_receipt)
        run = bind(run, "CHALLENGER", "CHALLENGER")
        challenge = {
            "challenge_id": "CH-CAPITAL-1",
            "target_claim_ids": ["CORE-1"],
            "evidence_items": [], "source_checks": [],
            "attacks": [{
                "target_claim_id": "CORE-1",
                "argument": "融资可见度并不等于资金到账。",
                "evidence_ids": [], "severity": "LOAD_BEARING",
            }],
            "strongest_countercase": "融资可能延迟或终止。",
        }
        dispatch = {
            "status": "dispatch_model", "role": "CHALLENGER",
            "prompt": "bounded challenger prompt",
            "prompt_sha256": hashlib.sha256(
                b"bounded challenger prompt"
            ).hexdigest(),
        }
        # Rebind the exact prompt supplied to the child context.
        run["run_ledger"]["pending_dispatch"]["prompt_sha256"] = dispatch[
            "prompt_sha256"
        ]
        harness_receipt = codex_research_receipt.build(
            dispatch, challenge, agent_id="/root/challenger",
            parent_agent_id="/root", isolation="UNVERIFIED",
            harness_subagent=True,
        )
        wrong_parent = deepcopy(harness_receipt)
        wrong_parent["parent_agent_id"] = "/unrelated-parent"
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "harness_parent_must_match_latest_lead",
        ):
            research_core.apply_challenge_packet(run, challenge, wrong_parent)
        updated = research_core.apply_challenge_packet(
            run, challenge, harness_receipt
        )
        research_core.validate_persisted_run(updated)
        call = updated["run_ledger"]["calls"][-1]
        self.assertEqual(call["receipt_provenance"], "HARNESS_SUBAGENT")
        self.assertEqual(call["attestation_level"], "HARNESS_REPORTED")
        achieved = research_core.delivery_state(updated)["achieved_execution"]
        self.assertEqual(achieved["reported_subagent_challenge_count"], 1)
        self.assertEqual(achieved["reported_process_challenge_count"], 0)
        self.assertIn(
            "HARNESS_SUBAGENT / HARNESS_REPORTED / SEPARATE_CONTEXT_REPORTED",
            achieved["challenger_receipts"],
        )
        self.assertEqual(updated["run_ledger"]["next_call"], "LEAD_RESOLUTION")

    def test_harness_label_is_fail_closed_for_lead_or_same_agent(self):
        base = {
            "receipt_id": "HARNESS-FAKE", "status": "SUCCEEDED",
            "agent_id": "/root", "parent_agent_id": "/root",
            "isolation": "SEPARATE_CONTEXT_REPORTED",
            "receipt_provenance": "HARNESS_SUBAGENT",
            "attestation_level": "HARNESS_REPORTED", "process_id": 0,
            "host_runtime": "codex-harness", "external_tools_enabled": False,
            "prompt_sha256": "a" * 64, "payload_sha256": "b" * 64,
        }
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "harness_subagent_fields_invalid",
        ):
            research_core._normalize_receipt(base, role="LEAD")


class ContextCompilerTests(unittest.TestCase):
    def test_working_set_contains_current_truth_not_raw_role_history(self):
        run = research_core.new_research_run(
            task_spec(), {"method_version": "0.18.0"}, execution_mode="CONTROLLED_FIXTURE"
        )
        working = research_core.compile_working_set(run)
        self.assertEqual(working["next_call"], "LEAD_RESEARCH")
        self.assertIn("hard_obligations", working)
        self.assertNotIn("rounds", working)
        self.assertNotIn("detective_raw", str(working))

    def test_working_set_hashes_but_does_not_replay_full_index_manifest(self):
        run = research_core.new_research_run(
            task_spec(1), {"method_version": "0.18.0"}, execution_mode="CONTROLLED_FIXTURE"
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        packet = lead_packet(run)
        run = research_core.apply_lead_packet(run, packet, receipt("LEAD", packet))
        working = research_core.compile_working_set(run)
        official = next(
            item for item in working["source_check_summaries"]
            if item["fact_surface"] == "OFFICIAL_DISCLOSURE_INDEX"
        )
        self.assertEqual(official["index_manifest_entry_count"], 24)
        self.assertRegex(official["index_manifest_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("index_entries", official)

    def test_budget_zero_can_be_explicitly_extended_after_synthesis(self):
        run = research_core.new_research_run(
            task_spec(0), {"method_version": "0.18.0"}, execution_mode="CONTROLLED_FIXTURE"
        )
        run = research_core.seed_research_run(
            run, [evidence()], complete_source_checks()
        )
        run = bind(run, "LEAD_SYNTHESIS", "LEAD")
        packet = lead_packet(run)
        packet["evidence_items"] = []
        packet["source_checks"] = []
        run = research_core.apply_lead_packet(run, packet, receipt("LEAD", packet))
        self.assertEqual(run["run_ledger"]["completed_research_loops"], 0)
        run = research_core.authorize_more_loops(run, 1)
        self.assertEqual(run["run_ledger"]["next_call"], "LEAD_RESEARCH")


class PersistedLineageTests(unittest.TestCase):
    def _completed(self):
        run = research_core.new_research_run(
            task_spec(1), {"method_version": "0.18.0"}, execution_mode="CONTROLLED_FIXTURE"
        )
        run = bind(run, "LEAD_RESEARCH", "LEAD")
        packet = lead_packet(run)
        return research_core.apply_lead_packet(
            run, packet, receipt("LEAD", packet)
        )

    def test_snapshot_is_bound_to_action_and_receipt_lineage(self):
        run = self._completed()
        research_core.validate_persisted_run(run)
        tampered = deepcopy(run)
        tampered["decision_snapshot"]["core_judgment"]["summary"] = "被静默改写"
        changed_hash = research_core.snapshot_hash(tampered["decision_snapshot"])
        tampered["run_ledger"]["decision_snapshot_sha256"] = changed_hash
        with self.assertRaisesRegex(
            research_core.ResearchContractError,
            "snapshot_not_bound_to_latest_lead_action",
        ):
            research_core.validate_persisted_run(tampered)

    def test_updating_hashes_cannot_hide_parallel_snapshot_fields(self):
        run = self._completed()
        tampered = deepcopy(run)
        tampered["decision_snapshot"]["core_judgment"]["parallel_thesis"] = "hidden"
        changed_hash = research_core.snapshot_hash(tampered["decision_snapshot"])
        tampered["run_ledger"]["decision_snapshot_sha256"] = changed_hash
        tampered["run_ledger"]["action_intents"][-1]["snapshot_sha256"] = changed_hash
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "unknown_item_fields"
        ):
            research_core.validate_persisted_run(tampered)

    def test_action_payload_must_match_the_host_receipt(self):
        run = self._completed()
        tampered = deepcopy(run)
        tampered["run_ledger"]["action_intents"][-1][
            "submission_payload_sha256"
        ] = "b" * 64
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "action_call_payload_drift"
        ):
            research_core.validate_persisted_run(tampered)

    def test_ledger_records_reject_hidden_fields(self):
        run = self._completed()
        tampered = deepcopy(run)
        tampered["run_ledger"]["calls"][-1]["hidden_semantics"] = "forbidden"
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "call\\[1\\]_fields_invalid"
        ):
            research_core.validate_persisted_run(tampered)

    def test_transition_rejects_destructive_rewrite_even_with_rehashed_state(self):
        before = self._completed()
        after = deepcopy(before)
        after["evidence_store"]["items"] = []
        after["evidence_store"]["source_checks"] = []
        after["run_ledger"]["evidence_store_sha256"] = research_core.stable_hash(
            after["evidence_store"]
        )
        with self.assertRaisesRegex(
            research_core.ResearchContractError, "append_only"
        ):
            research_core.validate_transition(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
