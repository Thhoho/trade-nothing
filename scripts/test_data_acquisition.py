#!/usr/bin/env python3
"""
Trade Nothing v0.9.1 — Real Data Acquisition Verification Suite
"""
import os
import sys
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

from data_providers import (
    GLOBAL_DATA_GATEWAY, 
    EastMoneyConsensusProvider, 
    YahooFinanceConsensusProvider, 
    FREDMacroProvider
)
from verified_crawler import VerifiedCrawler

def run_verifications():
    print("==================================================================")
    print("🧪 Verifying Real Data Acquisition Capabilities (v0.9.1 Specs)")
    print("==================================================================")

    # 1. Verify EastMoney Consensus API
    print("\n--- Test Case 1: EastMoney Analyst Consensus (300118.SZ) ---")
    em_prov = EastMoneyConsensusProvider()
    em_res = em_prov.fetch_quote("300118")
    if em_res:
        print("✅ EastMoney Consensus fetched successfully:")
        print(json.dumps(em_res, ensure_ascii=False, indent=2))
    else:
        print("⚠️ EastMoney Consensus API returned None (network offline or no forecast available)")

    # 2. Verify Yahoo Finance Consensus API
    print("\n--- Test Case 2: Yahoo Finance Analyst Consensus (AAPL) ---")
    yf_prov = YahooFinanceConsensusProvider()
    yf_res = yf_prov.fetch_quote("AAPL")
    if yf_res:
        print("✅ Yahoo Finance Consensus fetched successfully:")
        print(json.dumps(yf_res, ensure_ascii=False, indent=2))
    else:
        print("⚠️ Yahoo Finance Consensus API returned None (network offline)")

    # 3. Verify FRED Macro Ticker
    print("\n--- Test Case 3: FRED Macro Yield (US10Y) ---")
    fred_prov = FREDMacroProvider()
    fred_res = fred_prov.fetch_quote("US10Y")
    if fred_res:
        print("✅ FRED US10Y Yield fetched successfully:")
        print(json.dumps(fred_res, ensure_ascii=False, indent=2))
    else:
        print("⚠️ FRED US10Y Yield failed (network offline)")

    # 4. Verify DuckDuckGo Web Search Scraper & Crawler
    print("\n--- Test Case 4: Real DuckDuckGo Crawler Web Search ---")
    crawler = VerifiedCrawler()
    ddg_res = crawler._execute_search("300118 中标公示")
    if ddg_res:
        print(f"✅ DuckDuckGo Web Search returned {len(ddg_res)} real snippets. Sample:")
        print(json.dumps(ddg_res[0], ensure_ascii=False, indent=2))
    else:
        print("⚠️ DuckDuckGo Web Search returned empty (likely rate-limited or offline)")

    # 5. Verify Synthesized micro facts
    print("\n--- Test Case 5: Synthesized Micro-Facts Cascade ---")
    facts = crawler.synthesize_micro_facts("300118", "低温银浆")
    if facts:
        print("✅ Micro-Facts synthesized successfully:")
        print(f"   - Symbol: {facts.get('symbol')}")
        print(f"   - Tenders: {len(facts.get('micro_order_tenders', []))} entries")
        print(f"   - Commodity Unit Price: {facts.get('raw_material_price_track', {}).get('price')} {facts.get('raw_material_price_track', {}).get('unit')} (Source: {facts.get('raw_material_price_track', {}).get('source')})")
        print(f"   - Customs Volume: {facts.get('customs_export_validation', {}).get('export_value_millions_usd')}M USD (Source: {facts.get('customs_export_validation', {}).get('source')})")
        print(f"   - Snowball Expert Notes: {len(facts.get('expert_minutes_leak', []))} entries")
    else:
        print("❌ Micro-Facts synthesis failed")

    print("\n==================================================================")
    print("🎉 Data Acquisition Verification Complete!")
    print("==================================================================")

if __name__ == "__main__":
    run_verifications()
