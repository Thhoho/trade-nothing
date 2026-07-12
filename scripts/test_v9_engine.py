#!/usr/bin/env python3
"""
Trade Nothing v0.9.4 — Comprehensive Test Suite for Metric Fixes

Tests all 5 fixes:
  Fix 1: Bidirectional Bayesian (Bear evidence reduces odds)
  Fix 2: ES saturation dampened (slower convergence)
  Fix 3: Vision factor capped (first-appearance, max 2, factor 1.3)
  Fix 4: Fuzzy attack threshold (0.3 instead of 0.5)
  Fix 5: Extreme bias + stability guard in check_convergence
"""
import os
import sys
import json
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import deepthink_engine
from deepthink_engine import (
    check_convergence, get_topic_mode, classify_argument,
    resolve_state_file, cmd_start, cmd_checkpoint, load_state,
    get_bayes_factor, calculate_jaccard_novelty
)
from dungs_argumentation import DungSolver

# Import orchestrator functions for Fix 1 testing
sys.path.insert(0, SCRIPT_DIR)
from deepthink_orchestrator import (
    _extract_evidence_from_inquisitor,
    _classify_evidence_category,
    _extract_evidence,
    _extract_arguments_from_detective,
    _extract_attacks_from_inquisitor
)


class DummyArgs:
    """Minimal args object for cmd_checkpoint."""
    def __init__(self, **kwargs):
        self.topic = kwargs.get("topic", "")
        self.state_file = kwargs.get("state_file", "")
        self.round = kwargs.get("round", 1)
        self.next_action = kwargs.get("next_action", "继续质证")
        self.arguments_json = kwargs.get("arguments_json", "[]")
        self.attacks_json = kwargs.get("attacks_json", "[]")
        self.evidence_json = kwargs.get("evidence_json", "[]")
        self.forbidden_consensus_json = kwargs.get("forbidden_consensus_json", "[]")
        self.detective_raw_json = kwargs.get("detective_raw_json", "")
        self.inquisitor_raw_json = kwargs.get("inquisitor_raw_json", "")
        self.no_timer = True


passed = 0
failed = 0

def assert_true(cond, msg):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {msg}")
    else:
        failed += 1
        print(f"  ❌ FAIL: {msg}")


def run_tests():
    global passed, failed

    print("=" * 70)
    print("🧪 Trade Nothing v0.9.4 — Comprehensive Metric Fix Test Suite")
    print("=" * 70)

    # ── Fix 1: Bidirectional Bayesian ─────────────────────────────────────

    print("\n--- Fix 1: Bidirectional Bayesian Evidence ---")

    # 1a. Bear evidence extraction from Inquisitor JSON
    inquisitor_json = {
        "lethal_attack_vectors": [
            {
                "attack": "海关出口数据存在统计口径偏差，实际出货量远低于报关量",
                "target_claim_node": "[Audit Node: exports MoM +8%]",
                "severity": "critical"
            },
            {
                "attack": "The company's capex ROI is deteriorating below cost of capital",
                "target_claim_node": "[Audit Node: capex efficiency]",
                "severity": "medium"
            }
        ],
        "cognitive_biases_detected": ["confirmation bias", "survivorship bias"],
        "death_path": {
            "trigger": "Tariff escalation",
            "timeline": "Q3 2026"
        }
    }
    bear_evidence = _extract_evidence_from_inquisitor(inquisitor_json)
    assert_true(len(bear_evidence) >= 4, f"Should extract ≥4 bear evidence items, got {len(bear_evidence)}")
    assert_true(all(e["direction"] == "Bear" for e in bear_evidence),
                "All inquisitor evidence should be Bear direction")

    # Verify category classification
    assert_true(bear_evidence[0]["category"] == "Hard Proxy Data",
                f"海关出口数据 → Hard Proxy Data (got {bear_evidence[0]['category']})")
    assert_true(bear_evidence[0]["strength"] == "Strong",
                f"Severity 'critical' → Strong (got {bear_evidence[0]['strength']})")
    assert_true(bear_evidence[1]["category"] == "Factual Disclosed",
                f"capex ROI → Factual Disclosed (got {bear_evidence[1]['category']})")
    assert_true(bear_evidence[1]["strength"] == "Weak",
                f"Severity 'medium' → Weak (got {bear_evidence[1]['strength']})")

    # 1b. Verify Bayes Factor matrix works for Bear
    bf_bull = get_bayes_factor("Hard Proxy Data", "Bull", "Strong")
    bf_bear = get_bayes_factor("Hard Proxy Data", "Bear", "Strong")
    assert_true(bf_bull == 4.0, f"Bull Strong Hard Proxy BF = 4.0 (got {bf_bull})")
    assert_true(bf_bear == 0.25, f"Bear Strong Hard Proxy BF = 0.25 (got {bf_bear})")
    assert_true(bf_bull * bf_bear == 1.0, "Bull×Bear should cancel out to 1.0")

    # 1c. Engine-level: balanced evidence → moderate posterior
    topic_1c = "Test_Fix1_Balanced"
    resolve_state_file(topic=topic_1c)
    cmd_start(topic_1c)

    evidence_balanced = json.dumps([
        {"category": "Hard Proxy Data", "direction": "Bull", "strength": "Strong"},
        {"category": "Factual Disclosed", "direction": "Bull", "strength": "Strong"},
        {"category": "Hard Proxy Data", "direction": "Bear", "strength": "Strong"},
        {"category": "Factual Disclosed", "direction": "Bear", "strength": "Strong"},
    ])
    args_1c = DummyArgs(
        topic=topic_1c, round=1,
        arguments_json=json.dumps(["[Audit Node: test claim]"]),
        evidence_json=evidence_balanced
    )
    cmd_checkpoint(args_1c)
    state_1c = load_state()
    p_1c = state_1c["rounds"][-1]["posterior"]
    # 4.0 * 3.0 * 0.25 * 0.33 = 0.99 → posterior ≈ 49.7%
    assert_true(40.0 < p_1c < 60.0,
                f"Balanced Bull+Bear evidence → posterior ~50% (got {p_1c:.2f}%)")

    # ── Fix 2: ES Saturation Dampened ────────────────────────────────────

    print("\n--- Fix 2: ES Saturation Dampened ---")

    topic_2 = "Test_Fix2_ES_300118"
    resolve_state_file(topic=topic_2)
    cmd_start(topic_2)

    es_values = []
    for r in range(1, 4):
        claims = [f"[Audit Node: Claim R{r} #{i} | Proxy Data Anchor: data{r}_{i}]" for i in range(3)]
        args_2 = DummyArgs(
            topic=topic_2, round=r,
            arguments_json=json.dumps(claims),
            evidence_json=json.dumps([
                {"category": "Hard Proxy Data", "direction": "Bull", "strength": "Strong"}
            ])
        )
        cmd_checkpoint(args_2)
        state_2 = load_state()
        es_r = state_2["rounds"][-1]["es"]
        es_values.append(es_r)

    assert_true(es_values[0] < 0.15,
                f"R1 ES should be < 0.15 (got {es_values[0]:.4f})")
    assert_true(es_values[1] < 0.35,
                f"R2 ES should be < 0.35 (got {es_values[1]:.4f})")
    assert_true(es_values[2] < 0.50,
                f"R3 ES should be < 0.50 (got {es_values[2]:.4f})")

    lfi_r3 = state_2["rounds"][-1]["lfi"]
    # With dampened ES, LFI should still be well above audit threshold (0.15) at R3
    assert_true(lfi_r3 > 0.15,
                f"R3 LFI should be > 0.15 with dampened ES (got {lfi_r3:.4f})")

    # ── Fix 3: Vision Factor Cap ─────────────────────────────────────────

    print("\n--- Fix 3: Vision Factor Cap ---")

    topic_3 = "AI Liquid Cooling Infrastructure Analysis"
    resolve_state_file(topic=topic_3)
    cmd_start(topic_3)

    # R1: 2 new vision nodes
    vision_claims_r1 = [
        "[Vision Node: Liquid cooling 60% share by 2027 | Catalyst: NVIDIA GB200]",
        "[Vision Node: AI inference demand 5x by 2028 | Catalyst: Agent-native apps]",
    ]
    args_3_r1 = DummyArgs(
        topic=topic_3, round=1,
        arguments_json=json.dumps(vision_claims_r1),
        evidence_json=json.dumps([
            {"category": "Factual Disclosed", "direction": "Bull", "strength": "Strong"}
        ])
    )
    cmd_checkpoint(args_3_r1)
    state_3_r1 = load_state()
    odds_r1 = state_3_r1["odds"]

    # R2: Same 2 vision nodes (no new ones)
    args_3_r2 = DummyArgs(
        topic=topic_3, round=2,
        arguments_json=json.dumps(vision_claims_r1),  # Same claims
        evidence_json=json.dumps([
            {"category": "Factual Disclosed", "direction": "Bull", "strength": "Strong"}
        ])
    )
    cmd_checkpoint(args_3_r2)
    state_3_r2 = load_state()
    odds_r2 = state_3_r2["odds"]

    # R1 should get vision premium (2 new nodes → 1.3^2 = 1.69)
    # R2 should NOT get vision premium (same nodes, not new)
    # Both rounds get the same Bayesian evidence update (3.0 for Factual Strong Bull)
    # So odds_r2 / odds_r1 should be ≈ 3.0 (just the evidence, no vision premium)
    ratio = odds_r2 / odds_r1
    assert_true(2.5 < ratio < 3.5,
                f"R2/R1 odds ratio should be ~3.0 (just evidence, no repeat vision premium), got {ratio:.4f}")

    # Verify vision premium was applied in R1 but not R2
    # R1: odds = 1.0 × 3.0 (evidence) × 1.3^2 (vision) = 5.07
    assert_true(4.5 < odds_r1 < 5.5,
                f"R1 odds should be ~5.07 (3.0 × 1.69), got {odds_r1:.4f}")

    # ── Fix 4: Fuzzy Attack Threshold ────────────────────────────────────

    print("\n--- Fix 4: Fuzzy Attack Threshold ---")

    # Directly test Dung solver with partially defeated attack
    # Setup: A attacks B, C attacks A (C partially defends B)
    # A's belief should be reduced but not eliminated
    solver = DungSolver(
        ["A_attacker", "B_target", "C_defender"],
        [("A_attacker", "B_target"), ("C_defender", "A_attacker")]
    )
    V = solver.compute_fuzzy_valuations()
    a_belief = V.get("A_attacker", 0)
    
    # A is attacked by C, so A's belief should be between 0 and 1
    # With default confidence=0.9 for legacy nodes and attack strength=0.85:
    # A's belief = dampened iteration result
    print(f"  Fuzzy valuations: A={a_belief:.4f}, B={V.get('B_target', 0):.4f}, C={V.get('C_defender', 0):.4f}")

    # Now test with the engine — create a scenario where attacks should be partially resolved
    topic_4 = "Test_Fix4_FuzzyAttacks"
    resolve_state_file(topic=topic_4)
    cmd_start(topic_4)

    # Round with attack edges that create partial resolution
    claims = [
        "[Audit Node: Strong claim A | Proxy Data Anchor: customs data]",
        "[Audit Node: Strong claim B | Proxy Data Anchor: tender data]",
    ]
    attacks = [
        ["Inquisitor_attack_1", "[Audit Node: Strong claim A | Proxy Data Anchor: customs data]"],
        ["Inquisitor_attack_2", "[Audit Node: Strong claim B | Proxy Data Anchor: tender data]"],
    ]
    # Add Inquisitor attacks as arguments too
    all_claims = claims + ["Inquisitor_attack_1", "Inquisitor_attack_2"]
    # Detective rebuttals partially defeat the attacks
    rebuttal_attacks = [
        ["Rebuttal_1", "Inquisitor_attack_1"],  # Partially defeats attack 1
    ]
    all_attacks = attacks + rebuttal_attacks
    all_claims.append("Rebuttal_1")

    args_4 = DummyArgs(
        topic=topic_4, round=1,
        arguments_json=json.dumps(all_claims),
        attacks_json=json.dumps(all_attacks),
        evidence_json=json.dumps([
            {"category": "Hard Proxy Data", "direction": "Bull", "strength": "Strong"}
        ])
    )
    cmd_checkpoint(args_4)
    state_4 = load_state()
    open_attacks = state_4["rounds"][-1]["open_attacks"]
    
    # With fuzzy threshold 0.3, partially defeated attacks should still count
    # Inquisitor_attack_1 is attacked by Rebuttal_1, so its belief is reduced but > 0.3
    # Inquisitor_attack_2 is unattacked, so its belief should be high
    assert_true(open_attacks >= 1,
                f"Should have ≥1 open attack with fuzzy threshold (got {open_attacks})")
    
    unrefuted = state_4["unrefuted_attacks"]
    has_fuzzy_belief = any("fuzzy_belief" in a for a in unrefuted)
    assert_true(has_fuzzy_belief,
                "Unrefuted attacks should include fuzzy_belief field")

    # ── Fix 5: Extreme Bias + Stability Guard ────────────────────────────

    print("\n--- Fix 5: Extreme Bias + Stability Guard ---")

    # 5a. Extreme bias at R3 should NOT converge
    result_extreme = check_convergence(
        round_num=3, lfi=0.10, open_attacks=0, mode="vision",
        posterior_trace=[99.71, 100.0, 100.0]
    )
    assert_true(result_extreme["decision"] == "continue",
                f"Extreme bias (100%) at R3 → continue (got {result_extreme['decision']})")
    assert_true("极端偏置" in result_extreme["reason"],
                f"Reason should mention extreme bias")

    # 5b. Moderate posterior at R5 SHOULD converge
    result_moderate = check_convergence(
        round_num=5, lfi=0.10, open_attacks=0, mode="vision",
        posterior_trace=[50.0, 62.0, 68.0, 71.0, 73.0]
    )
    assert_true(result_moderate["decision"] == "converge",
                f"Moderate stable posterior at R5 → converge (got {result_moderate['decision']})")

    # 5c. Posterior instability should block convergence
    result_unstable = check_convergence(
        round_num=4, lfi=0.10, open_attacks=0, mode="vision",
        posterior_trace=[50.0, 65.0, 78.0, 70.0]
    )
    assert_true(result_unstable["decision"] == "continue",
                f"Unstable posterior (Δ=8%) → continue (got {result_unstable['decision']})")
    assert_true("波动" in result_unstable["reason"],
                "Reason should mention instability")

    # 5d. Extreme at R5 SHOULD converge (≥5 rounds threshold met)
    result_extreme_r5 = check_convergence(
        round_num=5, lfi=0.10, open_attacks=0, mode="vision",
        posterior_trace=[95.0, 97.0, 98.0, 98.5, 98.8]
    )
    assert_true(result_extreme_r5["decision"] == "converge",
                f"Extreme but stable at R5 → converge (got {result_extreme_r5['decision']})")

    # 5e. Old API (no posterior_trace) should still work
    result_legacy = check_convergence(
        round_num=3, lfi=0.10, open_attacks=0, mode="vision"
    )
    assert_true(result_legacy["decision"] == "converge",
                f"Legacy call without posterior_trace → converge (got {result_legacy['decision']})")

    # 5f. Open attacks but low LFI and stable posterior should converge
    result_open_attacks_converge = check_convergence(
        round_num=3, lfi=0.10, open_attacks=2, mode="vision",
        posterior_trace=[50.0, 60.0, 62.0]
    )
    assert_true(result_open_attacks_converge["decision"] == "converge",
                f"Open attacks with low LFI and stable posterior → converge (got {result_open_attacks_converge['decision']})")

    # 5g. Open attacks with HIGH LFI should NOT converge
    result_open_attacks_high_lfi = check_convergence(
        round_num=3, lfi=0.30, open_attacks=2, mode="vision",
        posterior_trace=[50.0, 60.0, 62.0]
    )
    assert_true(result_open_attacks_high_lfi["decision"] == "continue",
                f"Open attacks with high LFI → continue (got {result_open_attacks_high_lfi['decision']})")

    # ── Integration: Multi-round simulation ──────────────────────────────

    print("\n--- Integration: Multi-round Convergence Timing ---")

    topic_int = "Test_Integration_MultiRound"
    resolve_state_file(topic=topic_int)
    cmd_start(topic_int)

    converge_round = None
    for r in range(1, 8):
        claims = [f"[Audit Node: Integration claim R{r}_{i} | Proxy Data Anchor: data_{r}_{i}]" for i in range(3)]
        # Balanced evidence: 2 bull + 1 bear per round
        evidence = [
            {"category": "Hard Proxy Data", "direction": "Bull", "strength": "Strong"},
            {"category": "Factual Disclosed", "direction": "Bull", "strength": "Weak"},
            {"category": "Hard Proxy Data", "direction": "Bear", "strength": "Weak"},
        ]
        args_int = DummyArgs(
            topic=topic_int, round=r,
            arguments_json=json.dumps(claims),
            evidence_json=json.dumps(evidence),
        )
        # Capture stdout to check convergence action
        import io
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        cmd_checkpoint(args_int)
        output = buffer.getvalue()
        sys.stdout = old_stdout

        try:
            result = json.loads(output)
            action = result.get("action", "")
            posterior_pct = result.get("posterior", "?")
            lfi_val = result.get("lfi", "?")
            print(f"  R{r}: action={action}, P={posterior_pct}, LFI={lfi_val}")
            if action in ("converge", "fuse_break") and converge_round is None:
                converge_round = r
        except json.JSONDecodeError:
            print(f"  R{r}: [non-JSON output]")

    assert_true(converge_round is None or converge_round >= 4,
                f"Convergence should occur at R4+ (got R{converge_round})")
    if converge_round:
        assert_true(converge_round <= 12,
                    f"Should converge before fuse break (got R{converge_round})")

    # ── Orchestrator: _classify_evidence_category ─────────────────────────

    print("\n--- Orchestrator: Evidence Category Classification ---")

    assert_true(_classify_evidence_category("海关出口数据同比增长8%") == "Hard Proxy Data",
                "海关出口 → Hard Proxy Data")
    assert_true(_classify_evidence_category("公司毛利率同比下降5个百分点") == "Factual Disclosed",
                "毛利率 → Factual Disclosed")
    assert_true(_classify_evidence_category("渠道调研显示终端需求疲软") == "Channel Checks",
                "渠道调研 → Channel Checks")
    assert_true(_classify_evidence_category("市场情绪过于乐观") == "Narrative",
                "市场情绪 → Narrative")
    assert_true(_classify_evidence_category("The estimated capex ROI is negative") == "Factual Disclosed",
                "capex ROI → Factual Disclosed")

    # ── Summary ──────────────────────────────────────────────────────────

    print("\n" + "=" * 70)
    total = passed + failed
    print(f"🧪 Results: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️ {failed} tests FAILED")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
