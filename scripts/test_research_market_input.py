#!/usr/bin/env python3
"""Offline tests for host market-snapshot ingestion into the v0.18 core."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import market_snapshot_adapter
import research_core
import research_market_input
from test_market_snapshot_adapter import series


def receipt_bound_artifact():
    packet = {
        "as_of_date": "2026-03-14",
        "candidate": series(
            "甲公司", "600001", [100 + index for index in range(70)]
        ),
        "benchmark": series(
            "沪深300", "000300", [100 + index * 0.5 for index in range(70)]
        ),
    }
    packet["candidate"]["source"] = "Tushare Pro"
    packet["candidate"]["source_url"] = (
        "https://tushare.pro/document/2?doc_id=27"
    )
    packet["benchmark"]["source"] = "Tushare Pro"
    packet["benchmark"]["source_url"] = (
        "https://tushare.pro/document/2?doc_id=95"
    )
    receipt_core = {
        "schema_version": market_snapshot_adapter.UPSTREAM_RECEIPT_SCHEMA,
        "request_sha256": "a" * 64,
        "provider": "TUSHARE",
        "provider_version": "controlled-test",
        "research_as_of_date": "2026-03-14",
        "market_session_date": "2026-03-14",
        "adjustment": "qfq",
        "series_sha256": {
            "candidate": market_snapshot_adapter._input_hash(
                packet["candidate"]["observations"]
            ),
            "benchmark": market_snapshot_adapter._input_hash(
                packet["benchmark"]["observations"]
            ),
        },
        "provider_endpoints": ["https://api.tushare.pro"],
    }
    packet["acquisition_receipt"] = {
        **receipt_core,
        "receipt_id": market_snapshot_adapter._input_hash(receipt_core),
    }
    return market_snapshot_adapter.build_snapshot(packet)


def industry_spec():
    return research_core.normalize_task_spec({
        "question": "产业变化如何映射到上市公司？",
        "as_of": "2026-03-14",
        "budget": 2,
        "primary_entities": [{
            "entity_id": "E1", "name": "测试产业", "entity_type": "INDUSTRY",
        }],
        "questions": [{
            "question_id": "RQ1", "question": "市场载体是谁？",
        }],
    })


class ResearchMarketInputTests(unittest.TestCase):
    def test_builds_canonical_security_bound_host_fragment(self):
        fragment = research_market_input.build_fragment(
            receipt_bound_artifact(), entity_id="E1", claim_ids=["MV-MARKET-1"]
        )
        evidence = fragment["evidence_items"][0]
        check = fragment["source_checks"][0]
        self.assertEqual(evidence["security_ids"], ["600001@XSHG"])
        self.assertIsNone(evidence["number"])
        self.assertTrue(evidence["measures"])
        self.assertEqual(
            {item["unit"] for item in evidence["measures"] if item["metric"].startswith("return_")},
            {"PERCENT"},
        )
        self.assertEqual(
            next(
                item for item in evidence["measures"]
                if item["metric"] == "turnover_rate"
            )["unit"],
            "PERCENT",
        )
        self.assertEqual(check["security_id"], "600001@XSHG")
        self.assertEqual(len(check["acquisition_receipt_ids"]), 2)

        store, _ = research_core.append_evidence_items(
            research_core.new_evidence_store(), fragment["evidence_items"],
            as_of="2026-03-14",
        )
        store, _ = research_core.append_source_checks(
            store, fragment["source_checks"], task_spec=industry_spec(),
            origin="HOST_INPUT",
        )
        research_core.validate_evidence_scope(industry_spec(), store)

    def test_rejects_snapshot_without_upstream_acquisition_receipt(self):
        artifact = receipt_bound_artifact()
        artifact["upstream_acquisition_receipt"] = None
        with self.assertRaisesRegex(ValueError, "receipt"):
            research_market_input.build_fragment(artifact, entity_id="E1")

    def test_host_ingest_recompiles_without_writing_snapshot_or_budget(self):
        fragment = research_market_input.build_fragment(
            receipt_bound_artifact(), entity_id="E1"
        )
        run = research_core.new_research_run(
            industry_spec(), {"method_version": "0.18.0"},
            execution_mode="UNVERIFIED",
        )
        run = research_core.bind_dispatch(
            run, call_mode="LEAD_RESEARCH", role="LEAD",
            prompt_sha256="a" * 64,
        )
        updated = research_core.ingest_host_evidence(
            run, fragment["evidence_items"], fragment["source_checks"],
            input_id=fragment["input_id"],
        )
        self.assertEqual(updated["decision_snapshot"], run["decision_snapshot"])
        self.assertEqual(updated["run_ledger"]["completed_research_loops"], 0)
        self.assertNotIn("pending_dispatch", updated["run_ledger"])
        self.assertEqual(len(updated["run_ledger"]["host_inputs"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
