#!/usr/bin/env python3
"""Offline tests for compact resolution and continuation artifacts."""
import unittest

import crux_engine
import opportunity_engine
import research_output


def citation(path):
    return {
        "claim": f"claim {path}", "number": "1", "source": f"Source {path}",
        "url": f"https://example.com/evidence/{path}", "date": "2026-07-10",
        "source_tier": "primary",
    }


def blocked_state():
    st = crux_engine.new_state(
        "blocked topic", "Is the thesis ready?", "3-6M",
        [
            {"id": "C1", "label": "settled", "definition": "settled dispute",
             "monitor_anchor": "settled anchor", "falsifier": "settled falsifier",
             "catalyst_window": {"event": "event 1", "expected_by": "2026-10-10",
                                 "date_status": "REVIEW_CHECKPOINT"}},
            {"id": "C2", "label": "never tested", "definition": "open dispute",
             "monitor_anchor": "open anchor", "falsifier": "", "catalyst_window": {}},
        ],
    )
    st["frame_contract"] = {"as_of_date": "2026-07-10"}
    st["cruxes"]["C1"].update({
        "first_contested": 1, "contested_history": [0.4, 0.39, 0.39],
        "status": "RESOLVED_BEAR", "retired": True,
        "best_bull": "bull point", "best_bear": "bear point",
        "citations": [citation("c1-a"), citation("c1-b")],
    })
    st["rounds"] = [{"round": i, "detective_raw": {"secret": "raw"}} for i in range(1, 7)]
    st["decision_trace"] = [{
        "round": 6, "weakest": "C1", "p_weakest": 0.4, "p_mean": 0.45,
        "support_weakest": 0.4, "support_mean": 0.45, "decision": "NO_EDGE / AVOID",
    }]
    st["last_convergence"] = {
        "decision": "fuse_break", "round": 6,
        "reason": "maximum rounds reached", "open_cruxes": ["C2"],
    }
    return st


class ResearchOutputTests(unittest.TestCase):
    def test_runtime_failure_memo_is_compact_and_not_a_report(self):
        memo = research_output.render_runtime_failure_memo(
            "topic", "framing", "host timed out", state_initialized=False
        )
        self.assertIn(research_output.SCHEMA_RUNTIME_FAILURE, memo)
        self.assertIn("非研究结论", memo)
        self.assertIn("尚未初始化", memo)
        self.assertNotIn("正式研究报告", memo)

    def test_resolution_is_deterministic_and_exposes_real_gaps(self):
        st = blocked_state()
        first = research_output.render_resolution_memo(st)
        second = research_output.render_resolution_memo(st)
        self.assertEqual(first, second)
        self.assertIn("NON", research_output.build_resolution_view(st)["output_type"])
        self.assertIn("NEVER_CONTESTED", first)
        self.assertIn("MISSING_FALSIFIER", first)
        self.assertNotIn("secret", first)
        self.assertNotIn("detective_raw", first)

    def test_continuation_packet_is_bounded_and_raw_free(self):
        packet = research_output.build_continuation_packet(blocked_state())
        self.assertEqual(packet["dispatch_policy"]["crux_ids"], ["C2"])
        self.assertFalse(packet["dispatch_policy"]["free_roam_allowed"])
        self.assertLess(research_output.assert_compact_packet(packet), 32768)

    def test_unhealthy_origin_downgrades_stored_ready_seed(self):
        st = blocked_state()
        seed = {
            "seed_id": "OS-X", "candidate": "Asset", "ticker": "AST",
            "asset_type": "LISTED_EQUITY", "relation_type": "BOTTLENECK_OWNER",
            "origin_crux": "C2", "causal_path": "constraint -> rent",
            "economic_exposure": "owns constraint", "why_market_may_miss": "ignored",
            "catalyst": "event", "catalyst_window": {
                "event": "event", "expected_by": "2026-10-10",
                "date_status": "REVIEW_CHECKPOINT"},
            "falsifier": "substitute", "evidence": [citation("s-a"), citation("s-b")],
            "maturity": "READY_FOR_SCREENING",
        }
        st["opportunity_seeds"] = [seed]
        assessment = opportunity_engine.assess_seed(st, seed)
        self.assertEqual(assessment["evidence_maturity"], "READY_FOR_SCREENING")
        self.assertEqual(assessment["screening_status"], "BLOCKED_ORIGIN_CRUX")
        self.assertEqual(opportunity_engine.summary(st)["ready_for_screening_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
