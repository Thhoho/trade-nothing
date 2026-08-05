#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic tests for the v0.12 path-analysis layer (logic chain + odds)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from opportunity_engine import (
    path_analysis,
    odds_summary,
    _inherit_path_fields,
    _split_causal_path,
)


def _state_with_hypothesis():
    return {
        "hypothesis_ledger": {
            "hypotheses": [
                {
                    "hypothesis_id": "WH-1",
                    "why_nonconsensus": "市场常分别估值电力、土地和服务器。",
                    "causal_chain": ["AI用电需求", "并网与绿电约束", "客户长约", "项目融资", "可交付MW现金流"],
                    "scenario_paths": {
                        "bull": "并网电力与客户长约共同闭合融资。",
                        "base": "项目交付但资本成本限制回报。",
                        "bear": "许可、并网或客户信用任一环节失败。",
                    },
                    "asymmetry_case": {
                        "upside_shape": "OUTSIZED",
                        "convexity": "OPTION_LIKE",
                        "downside_shape": "SEVERE",
                        "time_to_signal": "MEDIUM",
                        "basis": "融资闭合可使未变现权利转为长期现金流。",
                    },
                    "payoff": {"upside": None, "downside": None, "unit": "UNSPECIFIED_SAME_UNIT"},
                }
            ]
        }
    }


def _seed(**overrides):
    seed = {
        "seed_id": "OS-TEST",
        "candidate": "Test Asset",
        "origin_hypothesis_id": "WH-1",
        "causal_path": "A -> B -> C",
        "why_market_may_miss": "",
        "catalyst": "三季报披露并网数据",
        "falsifier": "并网延期",
        "evidence": [
            {
                "claim": "500MW光伏已并网并面向中卫云基地负荷。",
                "source": "国务院国资委",
                "url": "https://example.org/1",
                "date": "2026-06-01",
            }
        ],
    }
    seed.update(overrides)
    return seed


class PathAnalysisTests(unittest.TestCase):
    def test_split_causal_path_arrow_variants(self):
        self.assertEqual(_split_causal_path("A -> B -> C"), ["A", "B", "C"])
        self.assertEqual(_split_causal_path("甲 → 乙 → 丙"), ["甲", "乙", "丙"])
        self.assertEqual(_split_causal_path(""), [])

    def test_chain_inherited_from_hypothesis(self):
        state = _state_with_hypothesis()
        seed = _seed(
            evidence=[
                {
                    "claim": "绿电约束导致500MW光伏并网延迟，面向中卫云基地。",
                    "source": "国务院国资委",
                    "url": "https://example.org/1",
                    "date": "2026-06-01",
                }
            ]
        )
        _inherit_path_fields(state, seed)
        analysis = path_analysis(state, seed)
        self.assertEqual(
            [n["node"] for n in analysis["chain"]],
            ["AI用电需求", "并网与绿电约束", "客户长约", "项目融资", "可交付MW现金流"],
        )
        # "绿电约束" (4 chars) is a phrase from "并网与绿电约束" and appears in the
        # evidence claim -> evidence_touched=true.  The catalyst "三季报披露并网数据"
        # contains "并网" (2 chars) but the >=3 char threshold means phrase matching is
        # stricter now; "绿电约束" does NOT appear in the catalyst text, so
        # observable is now false.
        touched = {n["node"]: n for n in analysis["chain"]}
        self.assertTrue(touched["并网与绿电约束"]["evidence_touched"])
        self.assertFalse(touched["项目融资"]["evidence_touched"])
        self.assertEqual(analysis["confirmed"], 1)
        self.assertEqual(analysis["unverified"], 4)
        self.assertEqual(analysis["observed"], 0)

    def test_no_hypothesis_no_chain_no_inheritance(self):
        state = _state_with_hypothesis()
        seed = _seed(origin_hypothesis_id=None)
        _inherit_path_fields(state, seed)
        analysis = path_analysis(state, seed)
        # Falls back to the causal_path string split.
        self.assertEqual([n["node"] for n in analysis["chain"]], ["A", "B", "C"])
        self.assertFalse(seed.get("asymmetry_case"))
        self.assertFalse(seed.get("scenario_paths"))
        self.assertFalse(seed.get("causal_chain"))

    def test_odds_summary_qualitative_without_numeric_payoff(self):
        state = _state_with_hypothesis()
        seed = _seed()
        _inherit_path_fields(state, seed)
        odds = odds_summary(seed)
        self.assertIsNotNone(odds)
        self.assertIn("上行形状=OUTSIZED", odds["qualitative"])
        self.assertIn("凸性=OPTION_LIKE", odds["qualitative"])
        self.assertFalse(odds["has_numeric_payoff"])
        self.assertEqual(odds["break_even"]["status"], "UNKNOWN")

    def test_odds_summary_numeric_break_even(self):
        state = _state_with_hypothesis()
        seed = _seed(
            payoff={"upside": "3", "downside": "1", "unit": "R"},
            asymmetry_case={
                "upside_shape": "OUTSIZED",
                "convexity": "OPTION_LIKE",
                "downside_shape": "LIMITED",
                "time_to_signal": "NEAR",
                "basis": "显式同单位赔率。",
            },
        )
        odds = odds_summary(seed)
        self.assertTrue(odds["has_numeric_payoff"])
        self.assertEqual(odds["break_even"]["status"], "KNOWN")
        # 1/(3+1) = 25% break-even success rate.
        self.assertEqual(odds["break_even"]["p_star_percent"], 25)

    def test_odds_summary_none_when_not_substantive(self):
        state = _state_with_hypothesis()
        seed = _seed(origin_hypothesis_id=None, asymmetry_case={})
        self.assertIsNone(odds_summary(seed))


if __name__ == "__main__":
    unittest.main()
