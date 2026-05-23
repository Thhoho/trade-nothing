#!/usr/bin/env python3
"""
Trade Nothing v0.9 — Polymarket Data Fetcher

Fetches prediction market probabilities for political, economic, or global events.

Usage:
  python3 fetch_polymarket.py --query "Trump"
  python3 fetch_polymarket.py --query "Bitcoin"
"""

import argparse
import requests
import json
import sys


def fetch_events(query: str, limit: int = 100):
    url = f"https://gamma-api.polymarket.com/events?active=true&closed=false&limit={limit}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        events = response.json()
    except Exception as e:
        print(json.dumps({"error": f"Failed to fetch data from Polymarket: {e}"}))
        sys.exit(1)

    results = []
    query_lower = query.lower() if query else ""

    for event in events:
        title = event.get('title', '')
        if query_lower and query_lower not in title.lower():
            continue

        markets = event.get('markets', [])
        event_markets = []
        for market in markets:
            if not market.get('active'):
                continue
            # Safe parsing of outcomes and prices
            raw_outcomes = market.get('outcomes', '[]')
            raw_prices = market.get('outcomePrices', '[]')
            outcomes = json.loads(raw_outcomes) if isinstance(raw_outcomes, str) else raw_outcomes
            prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
            try:
                parsed_prices = [float(p) for p in prices]
            except Exception:
                parsed_prices = prices

            market_data = {
                "question": market.get('question'),
                "outcomes": outcomes,
                "probabilities": parsed_prices,
                "volume": market.get('volume'),
                "end_date_iso": market.get('endDate')
            }
            event_markets.append(market_data)

        if event_markets:
            results.append({
                "title": title,
                "description": event.get('description'),
                "markets": event_markets
            })

    return results


def main():
    parser = argparse.ArgumentParser(description="Polymarket Data Fetcher")
    parser.add_argument("--query", type=str, help="Keyword to search events (e.g., 'Election', 'Bitcoin')")
    parser.add_argument("--limit", type=int, default=500, help="Number of recent active events to fetch before filtering")
    args = parser.parse_args()

    events = fetch_events(args.query, args.limit)

    output = {
        "source": "Polymarket",
        "query": args.query,
        "match_count": len(events),
        "events": events
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
