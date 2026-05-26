#!/usr/bin/env python3
"""
Trade Nothing v0.9.1 — Kelly Sizing & Reflexivity Exception Verification Suite
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

from portfolio_manager import PortfolioManager
from scenario_matrix import ScenarioMatrix

def run_verifications():
    print("================================================================")
    print("🧪 Verifying Entropy-Discounted Kelly Sizing (v0.9.1 Specs)")
    print("================================================================")

    pm = PortfolioManager()

    # Base parameters
    posterior = 0.85      # 85% Judge win rate
    target_price = 25.0
    current_price = 15.0
    fractional = 0.25     # Quarter-Kelly

    print("\n--- Test Case 1: Ideal low-entropy state (High Confidence) ---")
    # Low AFI, high es, zero EGI
    size_ideal = pm.calculate_kelly_size(
        posterior=posterior,
        target_price=target_price,
        current_price=current_price,
        fractional=fractional,
        lfi=0.05,
        afi=0.02,
        es=0.98,
        egi=0.0
    )
    print(f"Ideal Sizing: {size_ideal*100:.2f}% (Expected: High allocation)")

    print("\n--- Test Case 2: High friction/argumentation index (High AFI) ---")
    # High AFI, moderate es
    size_high_afi = pm.calculate_kelly_size(
        posterior=posterior,
        target_price=target_price,
        current_price=current_price,
        fractional=fractional,
        lfi=0.08,
        afi=0.60,  # high debate conflict
        es=0.80,
        egi=0.0
    )
    print(f"High AFI Sizing: {size_high_afi*100:.2f}% (Expected: Scaled down due to uncertainty)")
    assert size_high_afi < size_ideal, "High AFI sizing must be smaller than ideal sizing"

    print("\n--- Test Case 3: Bubble State (High EGI > 0, cash growth = False) ---")
    # High positive EGI should scale down Kelly cap strictly
    size_bubble_no_growth = pm.calculate_kelly_size(
        posterior=posterior,
        target_price=target_price,
        current_price=current_price,
        fractional=2.0,  # larger multiplier to exceed cap
        lfi=0.05,
        afi=0.05,
        es=0.90,
        egi=0.4,         # high hype bubble (normalized)
        company_cash_growth=False
    )
    print(f"Bubble Sizing (No Cash Growth): {size_bubble_no_growth*100:.2f}% (Expected: Capped tightly)")

    print("\n--- Test Case 4: Soros Reflexivity Bubble (High EGI > 0, cash growth = True) ---")
    # High positive EGI but with simultaneous corporate balance sheet cash growth
    size_bubble_with_growth = pm.calculate_kelly_size(
        posterior=posterior,
        target_price=target_price,
        current_price=current_price,
        fractional=2.0,
        lfi=0.05,
        afi=0.05,
        es=0.90,
        egi=0.4,
        company_cash_growth=True  # Soros exception active
    )
    print(f"Bubble Sizing (With Cash Growth Exception): {size_bubble_with_growth*100:.2f}% (Expected: Cap bypassed / High allocation)")
    assert size_bubble_with_growth > size_bubble_no_growth, "Soros exception must bypass standard bubble capping reduction"

    print("\n================================================================")
    print("🧪 Verifying ScenarioMatrix Entropy Sizing Integration")
    print("================================================================")

    print("\n--- Scenario Matrix Case A: Hype Bubble (No Cash Growth) ---")
    matrix_bubble = ScenarioMatrix(
        topic="AI Bubble Ticker",
        afi=0.05,
        es=0.90,
        egi=0.4,
        company_cash_growth=False
    )
    matrix_bubble.current_price = 15.0
    matrix_bubble.add_scenario("Bear", 20, 10.0, "Hype pop", [], "6m")
    matrix_bubble.add_scenario("Base", 30, 16.0, "Stable", [], "6m")
    matrix_bubble.add_scenario("Bull", 50, 30.0, "Accelerated growth", [], "6m")

    kelly_bubble_no_growth = matrix_bubble.calculate_kelly_fraction()
    print(f"Scenario Kelly (No Cash Growth): {kelly_bubble_no_growth*100:.2f}%")

    print("\n--- Scenario Matrix Case B: Hype Bubble (With Cash Growth Exception) ---")
    matrix_bubble_growth = ScenarioMatrix(
        topic="AI Bubble Ticker (Reflexive)",
        afi=0.05,
        es=0.90,
        egi=0.4,
        company_cash_growth=True
    )
    matrix_bubble_growth.current_price = 15.0
    matrix_bubble_growth.add_scenario("Bear", 20, 10.0, "Hype pop", [], "6m")
    matrix_bubble_growth.add_scenario("Base", 30, 16.0, "Stable", [], "6m")
    matrix_bubble_growth.add_scenario("Bull", 50, 30.0, "Accelerated growth", [], "6m")

    kelly_bubble_growth = matrix_bubble_growth.calculate_kelly_fraction()
    print(f"Scenario Kelly (With Cash Growth): {kelly_bubble_growth*100:.2f}%")
    assert kelly_bubble_growth > kelly_bubble_no_growth, "Scenario Matrix Soros exception must increase position sizing ceiling"

    print("\n🎉 All mathematical validations and exception paths passed successfully!")

if __name__ == "__main__":
    run_verifications()
