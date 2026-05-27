#!/usr/bin/env python3
"""
Trade Nothing v10.0 — Unified Pluggable Data Gateway Verification Suite
"""
import os
import sys
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

from data_providers import GLOBAL_DATA_GATEWAY, AkShareProvider, PolymarketProvider

def run_verifications():
    print("==================================================================")
    print("🧪 Verifying Integrated Data Providers Gateway (v10.0 Specs)")
    print("==================================================================")

    # 1. Verify AkShare Quote Fetching
    print("\n--- Test Case 1: AkShare Direct Quote (300118) ---")
    ak_prov = AkShareProvider()
    ak_quote = ak_prov.fetch_quote("300118")
    if ak_quote:
        print("✅ AkShare quote fetched successfully:")
        print(json.dumps(ak_quote, ensure_ascii=False, indent=2))
    else:
        print("❌ AkShare quote failed (is akshare package installed?)")

    # 2. Verify AkShare Fundamental Fetching
    print("\n--- Test Case 2: AkShare Direct Fundamentals (300118) ---")
    ak_fund = ak_prov.fetch_fundamental("300118")
    if ak_fund:
        print("✅ AkShare fundamentals fetched successfully:")
        print(json.dumps(ak_fund, ensure_ascii=False, indent=2))
    else:
        print("❌ AkShare fundamentals failed")

    # 3. Verify Polymarket Prediction Market Fetching
    print("\n--- Test Case 3: Polymarket Prediction Market Sentiment (Query: Fed) ---")
    poly_prov = PolymarketProvider()
    poly_quote = poly_prov.fetch_quote("Fed")
    if poly_quote:
        print("✅ Polymarket event probability quote fetched successfully:")
        print(json.dumps(poly_quote, ensure_ascii=False, indent=2))
    else:
        print("❌ Polymarket event lookup failed (is the Polymarket Gamma API online?)")

    # 4. Verify Unified Gateway Cascade Fetching
    print("\n--- Test Case 4: Unified Gateway Cascade (300118) ---")
    gateway_quote = GLOBAL_DATA_GATEWAY.fetch_price("300118")
    if gateway_quote:
        print("✅ Unified Gateway cascade fetch successful:")
        print(json.dumps(gateway_quote, ensure_ascii=False, indent=2))
    else:
        print("❌ Unified Gateway cascade lookup failed")

    print("\n==================================================================")
    print("🎉 Pluggable Data Gateway Verification Complete!")
    print("==================================================================")

if __name__ == "__main__":
    run_verifications()
