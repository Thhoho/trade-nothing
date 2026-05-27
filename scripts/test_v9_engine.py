#!/usr/bin/env python3
"""
Trade Nothing v9.0 — Sovereign Investment Master Test Suite
"""
import os
import sys
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

import deepthink_engine

class DummyArgs:
    def __init__(self, **kwargs):
        self.topic = kwargs.get("topic", "")
        self.state_file = kwargs.get("state_file", "")
        self.round = kwargs.get("round", 1)
        self.next_action = kwargs.get("next_action", "继续质证")
        self.arguments_json = kwargs.get("arguments_json", "[]")
        self.attacks_json = kwargs.get("attacks_json", "[]")
        self.evidence_json = kwargs.get("evidence_json", "[]")
        self.forbidden_consensus_json = kwargs.get("forbidden_consensus_json", "[]")
        self.no_timer = True
        self.start = False
        self.checkpoint = True
        self.status = False

def run_test_suite():
    print("==================================================================")
    print("🧪 Starting Trade Nothing v9.0 Sovereign Investment Master Test Suite")
    print("==================================================================")

    # ------------------------------------------------------------------
    # Test Case 1: Cyclical/Manufacturing Stock (HJT Solar - 300118)
    # Expected: Audit-Hardened Mode. Unanchored claims penalized.
    # ------------------------------------------------------------------
    print("\n--- Test Case 1: Cyclical Asset (300118 HJT Solar) ---")
    topic_1 = "300118 异质结组件出口分析"
    mode_1 = deepthink_engine.get_topic_mode(topic_1)
    print(f"🔹 Classified Mode for '{topic_1}': {mode_1.upper()} (Expected: AUDIT)")

    deepthink_engine.resolve_state_file(topic=topic_1)
    deepthink_engine.cmd_start(topic_1)

    # Round 1: Introduce one anchored claim and one unanchored claim
    claims_r1 = [
        "[Audit Node: HS 85414300 exports MoM +8.2% | Proxy Data Anchor: Ningbo Customs Q1 HS]",
        "[Vision Node: Future HJT will achieve absolute grid parity soon | Catalyst/Optionality: Tech scaling S-curve]"
    ]
    # In inquisitor audit, the Bear launches an attack on the unanchored claim
    attacks_r1 = []
    
    args_r1 = DummyArgs(
        topic=topic_1,
        round=1,
        arguments_json=json.dumps(claims_r1),
        attacks_json=json.dumps(attacks_r1),
        evidence_json=json.dumps([{"category": "Hard Proxy Data", "direction": "Bull", "strength": "Strong"}])
    )
    
    deepthink_engine.cmd_checkpoint(args_r1)
    state_r1 = deepthink_engine.load_state()
    latest_r1 = state_r1["rounds"][-1]

    print(f"🔸 Round 1 Posterior Probability: {latest_r1['posterior']}% (Odds: {state_r1['odds']:.4f})")
    print(f"🔸 Round 1 LFI: {latest_r1['lfi']:.4f} (Threshold: 0.15)")
    print(f"🔸 Expectation Gap Index (EGI): {latest_r1['egi']:.1f}")

    # Let's inspect the active arguments in Dung solver to see if the penalty was applied
    # In audit mode, the engine should have injected "System:AuditHardenedPenalty" attacking the vision node
    print("🔸 Inspecting Dung Grounded Extension elements:")
    ge = latest_r1.get("grounded_extension", [])
    print(f"   - Grounded Extension accepted nodes: {ge}")
    
    # Check if the Vision Node was successfully defeated
    vision_defeated = any("[Vision Node" in node for node in ge) == False
    print(f"✅ Target Verification (Vision Node Defeated in Audit Mode): {vision_defeated}")
    assert vision_defeated is True, "Error: Speculative Vision Node was NOT defeated in Audit Mode!"
    assert "System:AuditHardenedPenalty" in ge, "Error: Audit hardened penalty node was not injected!"


    # ------------------------------------------------------------------
    # Test Case 2: High-Optionality Tech Stock (AI Liquid Cooling)
    # Expected: Sovereign Vision Mode. Speculative claims allowed, optionality premium active.
    # ------------------------------------------------------------------
    print("\n--- Test Case 2: High-Optionality Asset (AI Liquid Cooling) ---")
    topic_2 = "AI Liquid Cooling Infrastructure Analysis"
    mode_2 = deepthink_engine.get_topic_mode(topic_2)
    print(f"🔹 Classified Mode for '{topic_2}': {mode_2.upper()} (Expected: VISION)")

    deepthink_engine.resolve_state_file(topic=topic_2)
    deepthink_engine.cmd_start(topic_2)

    # Round 1: Introduce speculative vision claim
    claims_r2 = [
        "[Vision Node: Liquid cooling market share will hit 60% by 2027 | Catalyst/Optionality: NVIDIA GB200 platform ramp-up]",
        "[Narrative Node: SNOWBALL retail sentiment is extremely bullish on liquid cooling | Sentiment Source: Snowball Forum]"
    ]
    # Undefeated in round 1
    attacks_r2 = []
    
    args_r2 = DummyArgs(
        topic=topic_2,
        round=1,
        arguments_json=json.dumps(claims_r2),
        attacks_json=json.dumps(attacks_r2),
        evidence_json=json.dumps([{"category": "Factual Disclosed", "direction": "Bull", "strength": "Strong"}])
    )
    
    deepthink_engine.cmd_checkpoint(args_r2)
    state_r2 = deepthink_engine.load_state()
    latest_r2 = state_r2["rounds"][-1]

    print(f"🔸 Round 1 Posterior Probability: {latest_r2['posterior']}% (Odds: {state_r2['odds']:.4f})")
    print(f"   *Note: In Sovereign Vision mode, validated Vision Node boosted posterior odds by 1.5x!")
    print(f"🔸 Round 1 LFI: {latest_r2['lfi']:.4f} (Threshold: 0.25)")
    print(f"🔸 Expectation Gap Index (EGI): {latest_r2['egi']:.1f}")

    # Inspect Dung solver accepted nodes
    ge_2 = latest_r2.get("grounded_extension", [])
    print(f"   - Grounded Extension accepted nodes: {ge_2}")
    
    vision_accepted = any("[Vision Node" in node for node in ge_2)
    print(f"✅ Target Verification (Vision Node Allowed in Vision Mode): {vision_accepted}")
    assert vision_accepted is True, "Error: Speculative Vision Node was incorrectly defeated in Vision Mode!"
    
    print("\n==================================================================")
    print("🎉 Test Suite Execution Complete!")
    print("==================================================================")

if __name__ == "__main__":
    run_test_suite()
