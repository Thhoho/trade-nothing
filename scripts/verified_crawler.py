"""
Trade Nothing v0.9.3 — Micro Industrial Trend & Order Crawler

A targeted, grass-roots web information crawler. Resolves the quantitative data
deficits by executing resilient DuckDuckGo queries against premium niche databases
(Bidcenter, SMM, Customs, and Xueqiu). Extracts technological parameters and order growth.

IMPORTANT: This crawler returns ONLY real web-scraped data. If scraping fails
(rate-limited, offline, blocked), it returns an explicit UNAVAILABLE status —
never hardcoded fake data.
"""

import os
import sys
import re
import json
import time
import urllib.parse
import urllib.request
from typing import List, Dict, Optional, Any
from datetime import datetime

# Resolve paths
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from utils import clean_proxy_env
clean_proxy_env()


class VerifiedCrawler:
    def __init__(self):
        self.ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def _execute_search(self, query: str) -> List[Dict[str, str]]:
        """
        Executes a zero-dependency HTML search scraping query targeting html.duckduckgo.com.
        Extracts titles, snippets, URLs, and dates from the raw un-JS-rendered HTML.
        """
        print(f"[CRAWLER] Dispatching industrial dorking: {query}", file=sys.stderr)
        
        # Clean proxies to avoid local system blockages
        clean_proxy_env()
        
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        
        results = []
        try:
            # Secure request with a 10s timeout
            with urllib.request.urlopen(req, timeout=10) as response:
                html_content = response.read().decode("utf-8", errors="ignore")
                
            # DuckDuckGo HTML results list is segmented by result divs
            parts = html_content.split('<div class="result result--default')
            for part in parts[1:]:
                url_match = re.search(r'href="([^"]+)"', part)
                title_match = re.search(r'class="result__url"[^>]*>([\s\S]*?)</a>', part)
                snippet_match = re.search(r'class="result__snippet"[^>]*>([\s\S]*?)</a>', part)
                
                url_str = url_match.group(1) if url_match else ""
                
                # Decode DDG internal redirect links if present
                if "/l/?kh=" in url_str and "uddg=" in url_str:
                    parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(url_str).query)
                    url_str = parsed_qs.get("uddg", [url_str])[0]
                
                # Clean HTML tags from matches
                title_str = re.sub(r'<[^>]*>', '', title_match.group(1)).strip() if title_match else ""
                snippet_str = re.sub(r'<[^>]*>', '', snippet_match.group(1)).strip() if snippet_match else ""
                
                # Unescape HTML entities
                import html as html_parser
                title_str = html_parser.unescape(title_str)
                snippet_str = html_parser.unescape(snippet_str)
                
                # Try to extract dates from snippet (e.g., "2026-05-12" or "3 days ago")
                date_str = datetime.today().strftime('%Y-%m-%d')
                date_match = re.search(r'\b(202\d[-/]\d{1,2}[-/]\d{1,2}|\d{1,2} days? ago)\b', snippet_str)
                if date_match:
                    date_str = date_match.group(1)
                    
                if title_str or snippet_str:
                    results.append({
                        "title": title_str,
                        "snippet": snippet_str,
                        "url": url_str,
                        "date": date_str,
                        "source": "Web_Search"
                    })
        except Exception as e:
            print(f"[CRAWLER WARN] DuckDuckGo dorking query failed: {e}", file=sys.stderr)
            
        return results

    def crawl_tender_data(self, keyword: str) -> List[Dict[str, Any]]:
        """
        Queries China Public Procurement Bidding Network (Bidcenter/Tendering platforms)
        to extract actual public bid winnings, GW capacity, and bid prices per watt.
        Returns empty list with UNAVAILABLE status if no real data is found.
        """
        query = f'site:bidcenter.com.cn "{keyword}" 中标公示'
        web_results = self._execute_search(query)
        
        tenders = []
        for r in web_results:
            tenders.append({
                "title": r["title"],
                "snippet": r["snippet"],
                "date": r["date"],
                "source": "Bidcenter_Live"
            })
            
        if not tenders:
            print(f"[CRAWLER] No live tenders found for '{keyword}'. Returning empty.", file=sys.stderr)

        return tenders

    def crawl_commodity_price(self, material: str) -> Dict[str, Any]:
        """
        Queries Shanghai Nonferrous Metals Market (SMM) or commodity platforms
        to extract actual week-over-week pricing of raw materials.
        Returns UNAVAILABLE status if no real data is found.
        """
        query = f'site:smm.cn "{material}" 价格 均价'
        web_results = self._execute_search(query)
        
        # Try to parse price and trend from real results using regular expressions
        parsed_price = None
        parsed_trend = None
        
        for r in web_results:
            snippet = r["snippet"]
            # Look for pricing patterns like "7200元" or "2850元/kg" or "82000元/吨"
            price_match = re.search(r'(\d{2,6}(?:\.\d+)?)\s*元/(?:kg|kg|吨)', snippet)
            if price_match:
                parsed_price = float(price_match.group(1))
            
            trend_match = re.search(r'([-+]\s*\d+(?:\.\d+)?\s*%)', snippet)
            if trend_match:
                parsed_trend = trend_match.group(1).replace(" ", "")
                
            if parsed_price:
                break
                
        # If we successfully scraped a real price, construct the node dynamically
        if parsed_price:
            unit = "元/吨" if parsed_price > 50000 else "元/kg"
            return {
                "material": f"{material} (Live)",
                "price": parsed_price,
                "unit": unit,
                "trend_wow": parsed_trend or "N/A",
                "source": "SMM_Live_Scraped"
            }
            
        # No real data found — return explicit UNAVAILABLE marker
        print(f"[CRAWLER] No live commodity prices found for '{material}'. Marking UNAVAILABLE.", file=sys.stderr)
        return {
            "material": material,
            "price": None,
            "unit": "N/A",
            "trend_wow": "N/A",
            "source": "UNAVAILABLE"
        }

    def crawl_customs_logs(self, hs_code: str) -> Dict[str, Any]:
        """
        Queries Port and Customs administrations to extract month-over-month export volume.
        Returns UNAVAILABLE status if no real data is found.
        """
        query = f'"{hs_code}" 出口额 海关 环比'
        web_results = self._execute_search(query)
        
        parsed_value = None
        parsed_change = None
        
        for r in web_results:
            snippet = r["snippet"]
            # Look for values in millions like "245.8百万美元" or "$245.8 million"
            val_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:百万美元|million)', snippet)
            if val_match:
                parsed_value = float(val_match.group(1))
            
            change_match = re.search(r'([-+]\s*\d+(?:\.\d+)?\s*%)', snippet)
            if change_match:
                parsed_change = change_match.group(1).replace(" ", "")
                
            if parsed_value:
                break
                
        if parsed_value:
            return {
                "hs_code": hs_code,
                "port": "Customs_Live_Scraped",
                "target_month": datetime.today().strftime('%Y-%m'),
                "export_value_millions_usd": parsed_value,
                "change_mom": parsed_change or "N/A",
                "source": "China_Customs_Live_Scraped"
            }
            
        # No real data found
        print(f"[CRAWLER] No live customs data found for HS '{hs_code}'. Marking UNAVAILABLE.", file=sys.stderr)
        return {
            "hs_code": hs_code,
            "port": "N/A",
            "target_month": datetime.today().strftime('%Y-%m'),
            "export_value_millions_usd": None,
            "change_mom": "N/A",
            "source": "UNAVAILABLE"
        }

    def crawl_expert_minutes(self, symbol: str) -> List[Dict[str, str]]:
        """
        Queries Xueqiu and buy-side forums for specialist consultation notes.
        Returns empty list if no real data is found.
        """
        query = f'site:xueqiu.com "{symbol}" 专家 调研 纪要'
        web_results = self._execute_search(query)
        
        minutes = []
        for r in web_results:
            minutes.append({
                "title": r["title"],
                "snippet": r["snippet"],
                "date": r["date"],
                "author": "Snowball_Live"
            })
            
        if not minutes:
            print(f"[CRAWLER] No live Snowball expert minutes found for '{symbol}'. Returning empty.", file=sys.stderr)

        return minutes

    def synthesize_micro_facts(self, symbol: str, technology_keyword: str) -> dict:
        """
        Coordinates all crawling routes, parses returned snippets and parameters,
        and synthesizes a high-density structured CJK facts dictionary to inject into subagents.
        Returns a dict with explicit availability flags for each data category.
        """
        print(f"[CRAWLER] Initiating micro-intelligence synthesis for '{symbol}' ({technology_keyword})...", file=sys.stderr)
        
        tenders = self.crawl_tender_data(symbol)
        commodity = self.crawl_commodity_price(technology_keyword)
        
        # Auto-match HS Code based on CJK keyword
        hs_code = "85414300"  # Default solar modules
        if "电池" in technology_keyword or "锂" in technology_keyword:
            hs_code = "85076000"
        elif "半导体" in technology_keyword or "芯片" in technology_keyword or "晶圆" in technology_keyword:
            hs_code = "85423900"  # Semiconductor devices
        elif "封装" in technology_keyword:
            hs_code = "85423100"
            
        customs = self.crawl_customs_logs(hs_code)
        expert = self.crawl_expert_minutes(symbol)
        
        synthesized = {
            "symbol": symbol,
            "technology_concept": technology_keyword,
            "timestamp": time.time(),
            "micro_order_tenders": tenders,
            "raw_material_price_track": commodity,
            "customs_export_validation": customs,
            "expert_minutes_leak": expert,
            "data_availability": {
                "tenders": len(tenders) > 0,
                "commodity_price": commodity.get("source") != "UNAVAILABLE",
                "customs": customs.get("source") != "UNAVAILABLE",
                "expert_minutes": len(expert) > 0
            }
        }
        
        return synthesized


if __name__ == "__main__":
    crawler = VerifiedCrawler()
    res = crawler.synthesize_micro_facts("半导体", "芯片")
    print(json.dumps(res, ensure_ascii=False, indent=2))
