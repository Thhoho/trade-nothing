#!/usr/bin/env python3
"""Frozen P0 regression: multiple capital/control facts may not disappear."""
from __future__ import annotations

from copy import deepcopy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import research_core
import research_report
from test_research_core import (
    action_intent, bind, index_manifest, receipt, snapshot, task_spec,
)


EVENTS = (
    (
        "EV-UNLOCK-1", "限售股份进入解禁窗口。", "CAPITAL_ACTIONS",
        "https://www.szse.cn/disclosure/fixture-unlock.html",
    ),
    (
        "EV-PLEDGE-1", "控股股东所持股份质押比例接近全部持股。", "OWNERSHIP_CONTROL",
        "https://www.szse.cn/disclosure/fixture-pledge.html",
    ),
    (
        "EV-INCREASE-1", "公司披露带明确金额上限的增持计划。", "CAPITAL_ACTIONS",
        "https://www.szse.cn/disclosure/fixture-increase.html",
    ),
)


def event_evidence():
    items = []
    for evidence_id, claim, surface, url in EVENTS:
        item = {
            "evidence_id": evidence_id,
            "claim": claim,
            "number": None,
            "measures": [],
            "source": "深圳证券交易所 controlled fixture",
            "url": url,
            "date": "2026-08-10",
            "source_tier": "PRIMARY_FIXTURE",
            "boundary": "FACT",
            "decision_impact": "HIGH",
            "entity_ids": ["E1"],
            "security_ids": ["300001@XSHE"],
            "fact_surface": surface,
            "claim_ids": ["CORE-1"],
        }
        if evidence_id == "EV-INCREASE-1":
            item["measures"] = [{
                "measure_id": "MEASURE-INCREASE-CAP",
                "metric": "financing_amount",
                "value": 1.0,
                "unit": "CNY_100M",
                "dimension": "CURRENCY",
                "subject_id": "E1",
                "as_of": "2026-08-10",
                "period": "POINT_IN_TIME",
                "basis": "DISCLOSURE_REPORTED",
                "definition": "融资或资本计划金额",
            }]
        items.append(item)
    return items


def checks():
    ids_by_surface = {
        "OWNERSHIP_CONTROL": ["EV-PLEDGE-1"],
        "CAPITAL_ACTIONS": ["EV-UNLOCK-1", "EV-INCREASE-1"],
    }
    urls = {evidence_id: url for evidence_id, _, _, url in EVENTS}
    result = []
    for surface in research_core.LISTED_COMPANY_FACT_SURFACES:
        evidence_ids = (
            [item[0] for item in EVENTS]
            if surface == "OFFICIAL_DISCLOSURE_INDEX"
            else ids_by_surface.get(surface, [])
        )
        result.append({
            "source_check_id": f"SC-P0-{surface.replace('_', '-')}",
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
            "index_item_count": 37 if surface == "OFFICIAL_DISCLOSURE_INDEX" else 0,
            "index_entries": (
                index_manifest(37, [urls[item] for item in evidence_ids])
                if surface == "OFFICIAL_DISCLOSURE_INDEX" else []
            ),
            "queries": [f"controlled full index {surface}"],
            "official_index_url": "https://www.szse.cn/disclosure/listed/notice/index.html",
            "checked_document_urls": [urls[item] for item in evidence_ids] or [
                "https://www.szse.cn/disclosure/listed/notice/index.html"
            ],
            "enumeration_complete": surface == "OFFICIAL_DISCLOSURE_INDEX",
            "outcome": "FOUND" if evidence_ids else "NO_RESULT",
            "evidence_ids": evidence_ids,
            "negative_scope": "受控窗口内标题全集未见该类事项" if not evidence_ids else "",
            "limitation": "CONTROLLED_FIXTURE; not live market evidence.",
        })
    return result


def packet_for(run):
    evidence_ids = [item[0] for item in EVENTS]
    snap = snapshot(run, extra_evidence_ids=evidence_ids[1:])
    snap["core_judgment"]["evidence_ids"] = evidence_ids
    snap["material_changes"] = [{
        "change_id": f"MC-{index}",
        "title": claim,
        "summary": claim,
        "decision_effect": "必须进入资本与控制风险判断。",
        "boundary": "FACT",
        "evidence_ids": [evidence_id],
    } for index, (evidence_id, claim, _, _) in enumerate(EVENTS, start=1)]
    snap["agenda_answers"][0]["evidence_ids"] = evidence_ids
    snap["consumed_evidence_ids"] = evidence_ids
    return {
        "action_intent": action_intent(),
        "evidence_items": event_evidence(),
        "source_checks": checks(),
        "decision_snapshot": snap,
        "challenge_request": None,
        "continue_research": False,
        "stop_reason": "受控事实面完成",
    }


class CurrentRealityRegressionTests(unittest.TestCase):
    def setUp(self):
        self.run = research_core.new_research_run(
            task_spec(1), {"method_version": "0.17.0"}, execution_mode="CONTROLLED_FIXTURE"
        )
        self.run = bind(self.run, "LEAD_RESEARCH", "LEAD")

    def test_all_three_load_bearing_events_survive_to_report(self):
        packet = packet_for(self.run)
        final = research_core.apply_lead_packet(
            self.run, packet, receipt("LEAD", packet)
        )
        rendered = research_report.render(final)
        for evidence_id, claim, _, _ in EVENTS:
            self.assertIn(evidence_id, rendered)
            self.assertIn(claim, rendered)

    def test_omitting_any_high_event_blocks_the_snapshot(self):
        for missing_id, _, _, _ in EVENTS:
            with self.subTest(missing_id=missing_id):
                packet = packet_for(self.run)
                packet["decision_snapshot"]["material_changes"] = [
                    item for item in packet["decision_snapshot"]["material_changes"]
                    if missing_id not in item["evidence_ids"]
                ]
                with self.assertRaisesRegex(
                    research_core.ResearchContractError,
                    f"HIGH_EVIDENCE:{missing_id}|open_material_gaps_missing",
                ):
                    research_core.apply_lead_packet(
                        self.run, packet, receipt("LEAD", packet)
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
