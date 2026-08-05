#!/usr/bin/env python3
"""Regression tests for evidence-exhaustion convergence and its safety gates."""
import unittest

import crux_engine


def citation(name, claim=None):
    return {
        "claim": claim or f"claim-{name}",
        "number": f"number-{name}",
        "source": f"Source {name}",
        "url": f"https://fixture-research.org/evidence/{name}",
        "date": "2026-07-29",
        "source_tier": "primary",
    }


def state():
    return crux_engine.new_state(
        "evidence-exhaustion",
        "Can an exhausted but unresolved crux leave the active queue?",
        "3-6M",
        [{
            "id": "C1",
            "label": "unresolved crux",
            "monitor_anchor": "next dated disclosure",
            "falsifier": "counterparty contradiction",
        }],
    )


def probe(new_count=0, detective=True, inquisitor=True):
    return {
        "crux_probe_audit": {
            "C1": {
                "detective_probed": detective,
                "inquisitor_probed": inquisitor,
                "new_valid_evidence_count": new_count,
            },
        },
    }


def submit(st, round_num, signal=0.0, citations=None, context=None):
    return crux_engine.submit_round(
        st,
        round_num,
        {"C1": {"signal": signal, "citations": list(citations or [])}},
        round_context=context,
    )


class EvidenceExhaustionConvergenceTests(unittest.TestCase):
    def test_two_bilateral_dry_probes_transition_open_crux_without_score_change(self):
        st = state()
        submit(st, 1, 1.0, [citation("a")], probe(new_count=1))
        submit(st, 2, -1.0, [citation("b")], probe(new_count=1))
        support_before_dry = st["cruxes"]["C1"]["p_history"][-1]
        log_odds_before_dry = st["cruxes"]["C1"]["L"]

        first = submit(st, 3, 0.0, [], probe(new_count=0))
        self.assertEqual(first["decision"], "continue")
        self.assertEqual(st["cruxes"]["C1"]["status"], "OPEN")
        self.assertEqual(st["cruxes"]["C1"]["evidence_exhaustion_dry_streak"], 1)

        second = submit(st, 4, 0.0, [], probe(new_count=0))
        crux = st["cruxes"]["C1"]
        self.assertEqual(second["decision"], "converge")
        self.assertEqual(crux["status"], "MONITORABLE")
        self.assertTrue(crux["retired"])
        self.assertEqual(crux["p_history"][-1], support_before_dry)
        self.assertEqual(crux["L"], log_odds_before_dry)
        self.assertEqual(
            crux["transition_reason"],
            crux_engine.MONITORABLE_EXHAUSTION_REASON,
        )
        self.assertEqual(
            crux["monitorable_semantics"],
            crux_engine.MONITORABLE_SEMANTICS,
        )
        audit = st["rounds"][-1]["evidence_exhaustion"]["C1"]
        self.assertTrue(audit["transitioned"])
        self.assertTrue(audit["support_score_unchanged_by_transition"])
        self.assertEqual(audit["dry_streak_after"], 2)
        self.assertEqual(audit["blocking_reasons"], [])

    def test_zero_signal_wash_is_ledgered_and_resets_dry_without_moving_support(self):
        st = state()
        submit(st, 1, 1.0, [citation("directional")], probe(new_count=1))
        support_before_wash = st["cruxes"]["C1"]["p_history"][-1]
        log_odds_before_wash = st["cruxes"]["C1"]["L"]

        submit(st, 2, 0.0, [citation("wash")], probe(new_count=1))
        crux = st["cruxes"]["C1"]
        self.assertEqual(crux["p_history"][-1], support_before_wash)
        self.assertEqual(crux["L"], log_odds_before_wash)
        self.assertEqual(len(crux["citations"]), 2)
        self.assertEqual(crux["citations"][-1]["support_effect"], "NONE_ZERO_SIGNAL_WASH")
        self.assertEqual(crux["evidence_exhaustion_dry_streak"], 0)

        submit(st, 3, 0.0, [citation("wash")], probe(new_count=0))
        crux = st["cruxes"]["C1"]
        self.assertEqual(len(crux["citations"]), 2)
        self.assertEqual(crux["evidence_exhaustion_dry_streak"], 1)
        flags = st["rounds"][-1]["signals"]["C1"]["quality_flags"]
        self.assertIn("dropped_duplicate_evidence:1", flags)

    def test_zero_signal_citation_without_bilateral_probe_audit_is_not_ledgered(self):
        st = state()
        submit(st, 1, 0.0, [citation("untraced")], context=None)
        self.assertEqual(st["cruxes"]["C1"]["citations"], [])
        self.assertEqual(st["cruxes"]["C1"]["p_history"][-1], 0.5)
        flags = st["rounds"][-1]["signals"]["C1"]["quality_flags"]
        self.assertIn(
            "dropped_zero_signal_citations_without_bilateral_probe_audit:1",
            flags,
        )

    def test_bilateral_probe_opens_crux_but_cannot_bypass_source_minimum(self):
        st = state()
        for round_num in (1, 2, 3):
            submit(st, round_num, 0.0, [], probe(new_count=0))
        crux = st["cruxes"]["C1"]
        self.assertEqual(crux["status"], "OPEN")
        self.assertFalse(crux["retired"])
        audit = st["rounds"][-1]["evidence_exhaustion"]["C1"]
        self.assertNotIn("STATUS_NOT_OPEN", audit["blocking_reasons"])
        self.assertIn("MINIMUM_VALID_CITATIONS_NOT_MET", audit["blocking_reasons"])

    def test_under_sourced_open_crux_fails_closed_after_dry_probes(self):
        st = state()
        submit(st, 1, 1.0, [citation("only-source")], probe(new_count=1))
        submit(st, 2, 0.0, [], probe(new_count=0))
        result = submit(st, 3, 0.0, [], probe(new_count=0))
        crux = st["cruxes"]["C1"]
        self.assertEqual(result["decision"], "continue")
        self.assertEqual(crux["status"], "OPEN")
        self.assertFalse(crux["retired"])
        audit = st["rounds"][-1]["evidence_exhaustion"]["C1"]
        self.assertIn("MINIMUM_VALID_CITATIONS_NOT_MET", audit["blocking_reasons"])

    def test_explicit_unilateral_probe_breaks_the_dry_streak(self):
        st = state()
        submit(st, 1, 1.0, [citation("a")], probe(new_count=1))
        submit(st, 2, -1.0, [citation("b")], probe(new_count=1))
        submit(st, 3, 0.0, [], probe(new_count=0))
        self.assertEqual(st["cruxes"]["C1"]["evidence_exhaustion_dry_streak"], 1)

        submit(
            st,
            4,
            0.0,
            [],
            probe(new_count=0, detective=True, inquisitor=False),
        )
        crux = st["cruxes"]["C1"]
        self.assertEqual(crux["evidence_exhaustion_dry_streak"], 0)
        self.assertEqual(crux["status"], "OPEN")
        audit = st["rounds"][-1]["evidence_exhaustion"]["C1"]
        self.assertIn("BILATERAL_PROBE_NOT_ESTABLISHED", audit["blocking_reasons"])

    def test_malformed_evidence_count_fails_closed_and_breaks_the_dry_streak(self):
        st = state()
        submit(st, 1, 1.0, [citation("a")], probe(new_count=1))
        submit(st, 2, -1.0, [citation("b")], probe(new_count=1))
        submit(st, 3, 0.0, [], probe(new_count=0))
        self.assertEqual(st["cruxes"]["C1"]["evidence_exhaustion_dry_streak"], 1)

        malformed = probe(new_count=0)
        malformed["crux_probe_audit"]["C1"]["new_valid_evidence_count"] = "0"
        submit(st, 4, 0.0, [], malformed)
        crux = st["cruxes"]["C1"]
        self.assertEqual(crux["evidence_exhaustion_dry_streak"], 0)
        self.assertEqual(crux["status"], "OPEN")
        audit = st["rounds"][-1]["evidence_exhaustion"]["C1"]
        self.assertIn("PROBE_AUDIT_INVALID", audit["blocking_reasons"])

    def test_recently_introduced_crux_fails_closed_despite_dry_streak(self):
        st = state()
        crux = st["cruxes"]["C1"]
        crux.update({
            "introduced": 3,
            "first_contested": 3,
            "status": "OPEN",
            "citations": [citation("a"), citation("b")],
            "seen_evidence_keys": [
                crux_engine.citation_identity(citation("a")),
                crux_engine.citation_identity(citation("b")),
            ],
        })
        st["max_introduced_round"] = 3
        submit(st, 4, 0.0, [], probe(new_count=0))
        result = submit(st, 5, 0.0, [], probe(new_count=0))
        self.assertEqual(result["decision"], "continue")
        self.assertEqual(crux["status"], "OPEN")
        audit = st["rounds"][-1]["evidence_exhaustion"]["C1"]
        self.assertIn("ADVERSARY_NOT_DRY", audit["blocking_reasons"])
        self.assertIn("CRUX_RECENTLY_INTRODUCED", audit["blocking_reasons"])

    def test_neutral_stable_support_does_not_auto_become_monitorable(self):
        st = state()
        for round_num, signal in ((1, 0.1), (2, -0.1), (3, 0.001)):
            submit(
                st,
                round_num,
                signal,
                [citation(f"round-{round_num}")],
                probe(new_count=1),
            )
        crux = st["cruxes"]["C1"]
        self.assertEqual(len(crux["contested_history"]), 3)
        self.assertLess(
            abs(crux["contested_history"][-1] - crux["contested_history"][-2]),
            crux_engine.EPS_STABLE,
        )
        self.assertEqual(crux["status"], "OPEN")
        self.assertFalse(crux["retired"])
        self.assertEqual(crux["evidence_exhaustion_dry_streak"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
