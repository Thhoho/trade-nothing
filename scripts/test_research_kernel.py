#!/usr/bin/env python3
"""Pure regressions for the shared deterministic research invariants."""
import unittest

import research_kernel


AS_OF = "2026-08-10"


def citation(host, claim="可核验事实", date=AS_OF):
    return {
        "claim": claim,
        "number": None,
        "source": f"agent label for {host}",
        "url": f"https://{host}/disclosure/item.html",
        "date": date,
        "source_tier": "primary",
    }


def normalized(host, claim="可核验事实"):
    item, reason = research_kernel.normalize_evidence(citation(host, claim), AS_OF)
    if reason:
        raise AssertionError(reason)
    return item


class EvidenceKernelTests(unittest.TestCase):
    def test_evidence_must_be_iso_and_not_after_as_of(self):
        _, reason = research_kernel.normalize_evidence(
            citation("official-source.com.cn", date="2026/08/10"), AS_OF
        )
        self.assertEqual(reason, "EVIDENCE_DATE_REQUIRES_ISO")
        _, reason = research_kernel.normalize_evidence(
            citation("official-source.com.cn", date="2026-08-11"), AS_OF
        )
        self.assertEqual(reason, "EVIDENCE_AFTER_AS_OF_DATE")

    def test_publisher_diversity_comes_from_url_not_agent_label(self):
        first = normalized("issuer.example.com.cn")
        second = dict(first)
        second["source"] = "completely different label"
        self.assertEqual(
            research_kernel.evidence_boundary([first, second]), "SINGLE_SOURCE"
        )
        independent = normalized("exchange-source.org", "交易所独立披露")
        self.assertEqual(
            research_kernel.evidence_boundary([first, independent]), "FACT"
        )

    def test_evidence_plane_counts_canonical_items_and_publishers(self):
        first = normalized("issuer.example.com.cn", "公司披露业务收入")
        first["evidence_id"] = "EV-1"
        duplicate = dict(first)
        duplicate["source"] = "renamed by another role"
        second = normalized("exchange-source.org", "交易所披露收盘价格")
        second["evidence_id"] = "EV-2"
        counts = research_kernel.evidence_plane_counts([first, duplicate, second])
        self.assertEqual(counts["canonical_evidence_item_count"], 2)
        self.assertEqual(counts["unique_source_url_count"], 2)
        self.assertEqual(counts["independent_publisher_count"], 2)

    def test_host_evidence_identity_includes_bound_subject(self):
        agenda = {"evidence_items": [], "evidence_aliases": {}}
        base = citation("market.example.cn", "同一观测值")
        base.update({
            "origin": "HOST_MARKET_SNAPSHOT",
            "receipt_id": "receipt",
        })
        first, _ = research_kernel.upsert_canonical_evidence(
            agenda,
            {**base, "binding": {"candidate_identity": "LISTED_EQUITY|XSHG|600001"}},
            AS_OF,
        )
        second, _ = research_kernel.upsert_canonical_evidence(
            agenda,
            {**base, "binding": {"candidate_identity": "LISTED_EQUITY|XSHE|000002"}},
            AS_OF,
        )
        self.assertNotEqual(first["evidence_id"], second["evidence_id"])
        self.assertEqual(len(agenda["evidence_items"]), 2)
        self.assertEqual(
            research_kernel.evidence_plane_counts(agenda["evidence_items"])[
                "canonical_evidence_item_count"
            ],
            2,
        )


class ReconciliationKernelTests(unittest.TestCase):
    def test_answer_reconciliation_is_order_invariant(self):
        variants = [
            {
                "role": "detective", "answer_status": "ANSWERED",
                "answer": "公告足以确认窗口。", "evidence_boundary": "SINGLE_SOURCE",
                "evidence": [normalized("issuer-source.com.cn")],
            },
            {
                "role": "inquisitor", "answer_status": "PARTIAL",
                "answer": "监管条件仍未确认。", "evidence_boundary": "SINGLE_SOURCE",
                "evidence": [normalized("regulator-source.gov.cn")],
            },
        ]
        forward = research_kernel.reconcile_answer_variants(variants)
        reverse = research_kernel.reconcile_answer_variants(list(reversed(variants)))
        self.assertEqual(forward, reverse)
        self.assertEqual(forward["answer_status"], "DISPUTED")

    def test_unsupported_dispute_does_not_erase_stronger_answer(self):
        result = research_kernel.reconcile_answer_variants([
            {
                "role": "detective", "answer_status": "ANSWERED",
                "answer": "两家独立发布方确认窗口。", "evidence_boundary": "FACT",
                "evidence": [
                    normalized("one-source.com.cn"),
                    normalized("two-source.org.cn"),
                ],
            },
            {
                "role": "inquisitor", "answer_status": "DISPUTED",
                "answer": "也许仍会变化。", "evidence_boundary": "HYPOTHESIS",
                "evidence": [], "strongest_challenge": "最终执行仍需观察",
            },
        ])
        self.assertEqual(result["answer_status"], "ANSWERED")
        self.assertEqual(result["evidence_boundary"], "FACT")
        self.assertIn("最终执行仍需观察", result["strongest_challenge"])

    def test_old_open_variant_does_not_dispute_later_answer(self):
        result = research_kernel.reconcile_answer_variants([
            {
                "round": 1, "role": "detective", "answer_status": "OPEN",
                "answer": "尚未找到足够证据。", "evidence_boundary": "HYPOTHESIS",
                "evidence": [], "next_test_availability": "SEARCH_NOW",
            },
            {
                "round": 3, "role": "detective", "answer_status": "ANSWERED",
                "answer": "官方披露已经确认当前窗口。",
                "evidence_boundary": "SINGLE_SOURCE",
                "evidence": [normalized("issuer-source.com.cn")],
                "next_test_availability": "WAIT_FOR_EVENT",
            },
        ])
        self.assertEqual(result["answer_status"], "ANSWERED")
        self.assertEqual(result["latest_round"], 3)
        self.assertEqual(result["next_test_availability"], "WAIT_FOR_EVENT")
        self.assertTrue(result["resolution"].startswith("TEMPORAL_"))

    def test_newer_wait_signal_survives_stronger_answer_preservation(self):
        result = research_kernel.reconcile_answer_variants([
            {
                "round": 1, "role": "detective", "answer_status": "ANSWERED",
                "answer": "现有证据已回答可观察部分。", "evidence_boundary": "FACT",
                "evidence": [normalized("one-source.com.cn"), normalized("two-source.org")],
                "next_test_availability": "SEARCH_NOW",
            },
            {
                "round": 2, "role": "inquisitor", "answer_status": "PARTIAL",
                "answer": "最终结果尚未发生。", "evidence_boundary": "HYPOTHESIS",
                "evidence": [], "missing_information": "最终事件结果",
                "next_test_availability": "WAIT_FOR_EVENT",
            },
        ])
        self.assertEqual(result["answer_status"], "ANSWERED")
        self.assertEqual(result["next_test_availability"], "WAIT_FOR_EVENT")

    def test_same_tier_direction_conflict_is_unresolved(self):
        records = [
            {
                "research_judgment": "SUPPORTED", "next_move": "ANSWER",
                "rationale": "项目方支持。", "evidence_boundary": "SINGLE_SOURCE",
                "evidence_ids": ["EV-1"],
            },
            {
                "research_judgment": "CHALLENGED", "next_move": "CONTINUE",
                "rationale": "监管方挑战。", "evidence_boundary": "SINGLE_SOURCE",
                "evidence_ids": ["EV-2"],
            },
        ]
        forward = research_kernel.reconcile_direction_records(records)
        reverse = research_kernel.reconcile_direction_records(list(reversed(records)))
        self.assertEqual(forward, reverse)
        self.assertEqual(forward["research_judgment"], "UNRESOLVED")
        self.assertEqual(forward["next_move"], "CONTINUE")


class CandidateKernelTests(unittest.TestCase):
    def test_listed_identity_requires_real_ticker_and_exchange(self):
        instrument, reason = research_kernel.normalize_instrument_identity(
            "LISTED_EQUITY", "301005"
        )
        self.assertIsNone(reason)
        self.assertEqual(instrument, {"ticker": "301005", "exchange": "XSHE"})
        _, reason = research_kernel.normalize_instrument_identity(
            "LISTED_EQUITY", "UNKNOWN"
        )
        self.assertEqual(reason, "listed_equity_valid_ticker_required")
        _, reason = research_kernel.normalize_instrument_identity(
            "LISTED_EQUITY", "NVDA"
        )
        self.assertEqual(reason, "listed_equity_exchange_required")

    def test_setup_requires_field_bound_evidence_and_no_field_conflict(self):
        fields = {
            name: [normalized(f"{name}.source.com.cn", f"{name} fact")]
            for name in research_kernel.FIELD_EVIDENCE_NAMES
        }
        item = {
            "setup_types": ["EVENT_SETUP"],
            "mechanism": "事件到资金到载体",
            "economic_exposure": "相关业务收入边界",
            "catalyst": "官方事件",
            "catalyst_window": {"expected_by": "2026-08-20"},
            "invalidation": "事件失败",
            "price_or_expectation": "价格锚",
            "crowding_or_position": "换手锚",
            "field_evidence": fields,
            "field_conflicts": {},
        }
        ready = research_kernel.evaluate_setup(item, AS_OF)
        self.assertEqual(ready["attention_band"], "SETUP_CANDIDATE")
        item["field_conflicts"] = {"mechanism": ["路径甲", "路径乙"]}
        blocked = research_kernel.evaluate_setup(item, AS_OF)
        self.assertEqual(blocked["attention_band"], "EXPLORE")
        self.assertIn(
            "UNRESOLVED_FIELD_CONFLICT",
            blocked["setup_checks"]["EVENT_SETUP"]["reason_codes"],
        )

    def test_two_disputed_roles_share_uncertainty_without_fake_conflict(self):
        variants = [
            {
                "round": 1, "role": "detective", "answer_status": "DISPUTED",
                "answer": "更像多瓶颈共同约束。", "evidence_boundary": "SINGLE_SOURCE",
                "evidence": [normalized("issuer-a.com", "multi bottleneck")],
            },
            {
                "round": 1, "role": "inquisitor", "answer_status": "DISPUTED",
                "answer": "现有证据不能归因于单一瓶颈。", "evidence_boundary": "SINGLE_SOURCE",
                "evidence": [normalized("issuer-b.com", "not one bottleneck")],
            },
        ]
        result = research_kernel.reconcile_answer_variants(variants)
        self.assertEqual(result["answer_status"], "DISPUTED")
        self.assertEqual(result["resolution"], "SHARED_UNCERTAINTY")
        self.assertNotIn("detective:", result["current_answer"])

    def test_canonical_field_binding_rejects_obvious_category_mismatch(self):
        price = normalized("market-source.org", "行情收盘价格形成估值锚")
        price["evidence_id"] = "EV-PRICE"
        resolved, ids, checks, rejections = (
            research_kernel.resolve_field_evidence_ids(
                {"catalyst": ["EV-PRICE"]},
                [price],
                {"catalyst": "遥二发射窗口"},
            )
        )
        self.assertEqual(resolved["catalyst"], [])
        self.assertEqual(ids["catalyst"], [])
        self.assertFalse(checks[0]["aligned"])
        self.assertEqual(
            rejections[0]["reason"], "CLAIM_FIELD_CATEGORY_MISMATCH"
        )

    def test_duplicate_alias_resolves_to_canonical_evidence_id(self):
        catalyst = normalized("issuer-source.org", "官方公告发射窗口和日期")
        catalyst["evidence_id"] = "EV-CANONICAL"
        resolved, ids, checks, rejections = (
            research_kernel.resolve_field_evidence_ids(
                {"catalyst": ["EV-ALIAS"]},
                [catalyst],
                {"catalyst": "发射窗口"},
                evidence_aliases={"EV-ALIAS": "EV-CANONICAL"},
            )
        )
        self.assertEqual(ids["catalyst"], ["EV-CANONICAL"])
        self.assertEqual(resolved["catalyst"][0]["evidence_id"], "EV-CANONICAL")
        self.assertEqual(checks[0]["canonical_evidence_id"], "EV-CANONICAL")
        self.assertEqual(rejections, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
