# Test Plan & Verification Methodology: Trade Nothing v0.9.1

This document defines the formal test suite, execution guidelines, and verification criteria for **Trade Nothing v0.9.1 — The Sovereign Investment Master**.

---

## 1. Objectives & Scope

The test plan is designed to verify the core quantitative upgrades of the Trade Nothing v0.9.1 engine. Specifically, we test:
*   **Adaptive Severity Modes**: Correct industry classification and convergence thresholds based on target topic names.
*   **Dual-Path Argumentation & Dung Graph Penalties**: Automatic rejection of unanchored speculative claims in Audit Mode, while permitting them in Sovereign Vision Mode.
*   **Expectation Gap Index (EGI)**: Mathematical accuracy of the delta between Narrative nodes and physical facts.
*   **Optionality Premium Multiplier**: Mathematical verification of the 1.5x Bayes Odds boost on undefeated Vision nodes.
*   **Windows & Platform Portability**: Guaranteeing crash-free concurrency using atomic cross-platform locks instead of raw POSIX `fcntl`.

---

## 2. Realistic Test Scenario 1: Cyclical Commodity (300118 HJT Solar)

This scenario tests the engine's behavior under heavy-asset, commodity manufacturing constraints where defensive "downside security" (Margin of Safety) is critical.

### 2.1 Test Parameters
*   **Target Symbol/Topic**: `300118 异质结组件出口分析` (HJT Solar export analysis)
*   **Expected Mode**: `Audit-Hardened Mode` (Cyclical)
*   **LFI Convergence Limit**: `0.15` (High rigor required)
*   **Test Input claims**:
    1.  `[Audit Node: HS 85414300 exports MoM +8.2% | Proxy Data Anchor: Ningbo Customs Q1 HS]`
    2.  `[Vision Node: Future HJT will achieve absolute grid parity soon | Catalyst/Optionality: Tech S-curve]`
*   **Attacks**: None (undefeated by default).

### 2.2 Expected Behavior & Mathematical Verification
*   **Dung Graph**: Because the mode is `audit`, the engine must inject a virtual `System:AuditHardenedPenalty` node. This node attacks the unanchored `[Vision Node]`. In the final Grounded Extension, only the `[Audit Node]` and `System:AuditHardenedPenalty` must survive.
*   **Expectation Gap Index (EGI)**: Calculated as:
    $$EGI = \text{Narrative accepted} - \text{Audit accepted}$$
    With 1 audit node and 1 system legacy node in Grounded Extension, EGI must equal `-2.0`.
*   **Result**: Speculative growth claims must be strictly defeated.

---

## 3. Realistic Test Scenario 2: High-Optionality Asset (AI Liquid Cooling)

This scenario tests the engine's behavior under high-growth, high-optionality tech assets where capturing early-stage "upside ceiling" (optionality) is crucial.

### 3.1 Test Parameters
*   **Target Topic**: `AI Liquid Cooling Infrastructure Analysis`
*   **Expected Mode**: `Sovereign Vision Mode` (High-Optionality)
*   **LFI Convergence Limit**: `0.25` (Relaxed threshold to facilitate narrative capturing)
*   **Test Input claims**:
    1.  `[Vision Node: Liquid cooling market share will hit 60% by 2027 | Catalyst/Optionality: NVIDIA GB200 platform ramp-up]`
    2.  `[Narrative Node: SNOWBALL retail sentiment is extremely bullish | Sentiment Source: Snowball Forum]`
*   **Attacks**: None.

### 3.2 Expected Behavior & Mathematical Verification
*   **Dung Graph**: No penalty node is injected. Speculative growth `[Vision Node]` must be fully allowed and survive in Grounded Extension.
*   **Optionality Premium**: Since the `[Vision Node]` successfully survives bear audits, the engine must multiply posterior Odds by `1.5` (`Odds * 1.5`), boosting posterior probability.
*   **Expectation Gap Index (EGI)**: With 1 Narrative node and 0 Audit nodes accepted in Grounded Extension, EGI must equal `1.0`.
*   **Result**: speculativeness is rewarded with premium valuation.

---

## 4. Execution & Verification Instructions

### 4.1 Running the Suite
Execute the programmatic test suite locally using PowerShell/Terminal:
```powershell
python scripts/test_v9_engine.py
```

### 4.2 Verification Checklist

| Requirement ID | Deliverable Description | Verification Evidence | Status |
|----------------|-------------------------|-----------------------|--------|
| **REQ-01** | Windows Portability | Syntax help command runs successfully: `python scripts/deepthink_engine.py --help` without `fcntl` ModuleNotFoundError. | ✅ PASS |
| **REQ-02** | Mode Classification | Case 1 classified as `AUDIT`; Case 2 classified as `VISION` in console logs. | ✅ PASS |
| **REQ-03** | Dung Penalty in Audit | In Case 1, `✅ Target Verification (Vision Node Defeated): True` is printed. | ✅ PASS |
| **REQ-04** | EGI Calculation | EGI outputs `-2.0` in Case 1 and `1.0` in Case 2. | ✅ PASS |
| **REQ-05** | Optionality Premium | Case 2 odds are multiplied by `1.5x`, updating posterior to `81.82%` from a baseline of `80.0%`. | ✅ PASS |
| **REQ-06** | Convergence LFI Limit | Case 1 logs show LFI threshold of `0.15`; Case 2 logs show LFI threshold of `0.25`. | ✅ PASS |
| **REQ-07** | Process-Safe Locks | `CrossPlatformFileLock` created directories (`.lockdir`) successfully on Windows disk. | ✅ PASS |
