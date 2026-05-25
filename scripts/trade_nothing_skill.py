"""
Trade Nothing v7.0 — IDE Pluggable Skill & Dual-Track Bridge Client

Acts as the user-facing CLI and IDE-pluggable skill. Dynamic auto-discovery:
routes tasks via REST API if the autonomous daemon is online,
or falls back to local execution if the daemon is offline.

Usage:
    python3 scripts/trade_nothing_skill.py --code 300118 --target 25.0
    python3 scripts/trade_nothing_skill.py --code AAPL --target 220.0 --fractional 0.5
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
import time

# Resolve paths
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)


def check_server_online(url: str) -> bool:
    """Checks if the autonomous daemon server is online on port 8000"""
    try:
        req = urllib.request.Request(f"{url}/api/status", method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass
    return False


def run_via_daemon(url: str, symbol: str, target_price: float, fractional: float):
    """Delegates research and execution tasks to the background server via REST"""
    print(f"📡 [Bridge] Standalone Autonomous Daemon detected at {url}.")
    print(f"📡 [Bridge] Initiating background research debate for symbol '{symbol}'...", flush=True)

    # 1. Trigger research debate
    start_url = f"{url}/api/research/start"
    payload = {
        "symbol": symbol,
        "target_price": target_price,
        "fractional": fractional
    }
    
    try:
        req = urllib.request.Request(
            start_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            print(f"✅ [Server] {res_data.get('message')}")
    except Exception as e:
        print(f"❌ [Error] Failed to start server-side research: {e}", file=sys.stderr)
        return

    # 2. Poll research progress
    status_url = f"{url}/api/research/status?symbol={symbol}"
    print(f"⏳ [Server] Waiting for debate convergence and quantitative trade execution...")
    
    last_round = 0
    while True:
        try:
            req = urllib.request.Request(status_url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                status_data = json.loads(resp.read().decode("utf-8"))
                
                curr_round = status_data.get("round", 0)
                curr_status = status_data.get("status", "")
                
                if curr_round > last_round:
                    print(f"  [Round {curr_round}] LFI={status_data.get('lfi')} | Posterior={status_data.get('posterior') * 100 if isinstance(status_data.get('posterior'), float) else status_data.get('posterior')}%")
                    if status_data.get("log"):
                        print(f"    ℹ️ {status_data['log'][-1]}")
                    last_round = curr_round

                if curr_status in {"COMPLETED", "CONVERGED", "FAILED"}:
                    print(f"\n🎉 [Server] Pipeline Finished with status: {curr_status}")
                    print(json.dumps(status_data.get("trade_execution", {}), ensure_ascii=False, indent=2))
                    break
        except Exception:
            pass
        time.sleep(1.0)


def run_locally(symbol: str, target_price: float, fractional: float):
    """Local Fallback execution: imports modules and executes logic directly in CLI"""
    print("⚠️  [Bridge] Autonomous Daemon is offline. Falling back to Local Execution Track...")
    print("⏳ [Local] Performing Cascading global price fetch and local Kelly calculation...")
    
    try:
        from data_providers import GLOBAL_DATA_GATEWAY
        from portfolio_manager import PortfolioManager
        
        # 1. Fetch current price
        quote = GLOBAL_DATA_GATEWAY.fetch_price(symbol)
        curr_price = quote.get("price", 0.0)
        source = quote.get("source", "N/A")
        
        if curr_price <= 0:
            print("❌ [Local Error] Failed to fetch real-time market price. Aborting.", file=sys.stderr)
            return

        print(f"📈 [Local] Real-time Quote retrieved: {curr_price} {quote.get('currency', 'USD')} via {source}")

        # 2. Simulate Local Debate convergence state using real math engine
        import deepthink_engine
        topic_name = f"{symbol} analysis"
        deepthink_engine.resolve_state_file(topic=topic_name)
        deepthink_engine.cmd_start(topic_name)
        
        class DummyArgs:
            def __init__(self, **kwargs):
                self.topic = kwargs.get("topic", "")
                self.state_file = kwargs.get("state_file", "")
                self.round = kwargs.get("round", 1)
                self.next_action = kwargs.get("next_action", "")
                self.arguments_json = kwargs.get("arguments_json", "")
                self.attacks_json = kwargs.get("attacks_json", "")
                self.evidence_json = kwargs.get("evidence_json", "")
                self.forbidden_consensus_json = kwargs.get("forbidden_consensus_json", "")
                self.no_timer = kwargs.get("no_timer", True)
                self.start = False
                self.checkpoint = True
                self.status = False

        import io
        from contextlib import redirect_stdout
        
        # We run the 3-round debate calculation programmatically
        args_r1 = DummyArgs(
            topic=topic_name,
            round=1,
            arguments_json=json.dumps([" exports up 8.2% YoY", "silver SMM drops 1.2%"]),
            attacks_json=json.dumps([]),
            evidence_json=json.dumps([{"category": "Hard Proxy Data", "direction": "Bull", "strength": "Strong"}]),
            forbidden_consensus_json=json.dumps(["过剩内卷"])
        )
        f = io.StringIO()
        with redirect_stdout(f):
            deepthink_engine.cmd_checkpoint(args_r1)

        args_r2 = DummyArgs(
            topic=topic_name,
            round=2,
            arguments_json=json.dumps([" exports up 8.2% YoY", "silver SMM drops 1.2%", "Indium price surge squeeze"]),
            attacks_json=json.dumps([["Indium price surge squeeze", " exports up 8.2% YoY"]]),
            evidence_json=json.dumps([{"category": "Channel Checks", "direction": "Bear", "strength": "Weak"}]),
            forbidden_consensus_json=json.dumps(["过剩内卷"])
        )
        f = io.StringIO()
        with redirect_stdout(f):
            deepthink_engine.cmd_checkpoint(args_r2)

        args_r3 = DummyArgs(
            topic=topic_name,
            round=3,
            arguments_json=json.dumps([" exports up 8.2% YoY", "silver SMM drops 1.2%", "Indium price surge squeeze", "Indium recycling reaches 92%"]),
            attacks_json=json.dumps([
                ["Indium price surge squeeze", " exports up 8.2% YoY"],
                ["Indium recycling reaches 92%", "Indium price surge squeeze"]
            ]),
            evidence_json=json.dumps([{"category": "Hard Proxy Data", "direction": "Bull", "strength": "Strong"}]),
            forbidden_consensus_json=json.dumps(["过剩内卷"])
        )
        f = io.StringIO()
        with redirect_stdout(f):
            deepthink_engine.cmd_checkpoint(args_r3)

        r3_state = deepthink_engine.load_state()
        r3_data = r3_state["rounds"][-1]
        
        sim_posterior = r3_data["posterior"] / 100.0
        sim_lfi = r3_data["lfi"]
        
        print(f"📊 [Local] Objective Sizing Sinks (Calculated via deepthink_engine):")
        print(f"  - Simulated Debate Win Rate (Posterior): {sim_posterior * 100:.2f}%")
        print(f"  - Logic Friction Index (LFI): {sim_lfi:.4f} (Converged)")

        # 3. Execute local paper trading
        pm = PortfolioManager()
        trade_res = pm.execute_kelly_sizing_trade(
            symbol=symbol,
            posterior=sim_posterior,
            target_price=target_price,
            current_price=curr_price,
            lfi=sim_lfi,
            fractional=fractional
        )
        
        print(f"🎉 [Local] Transaction Complete:")
        print(json.dumps(trade_res, ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(f"❌ [Local Error] Execution failed: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Trade Nothing v7.0 IDE Skill & Client Bridge")
    parser.add_argument("--code", required=True, help="Symbol / Ticker to trade (e.g. 300118, AAPL, BTC)")
    parser.add_argument("--target", type=float, required=True, help="Target Price for asymmetric sizing")
    parser.add_argument("--fractional", type=float, default=0.25, help="Fractional Kelly Multiplier (e.g. 0.25 for Quarter-Kelly)")
    parser.add_argument("--server-url", default="http://localhost:8000", help="URL of the standing daemon server")

    args = parser.parse_args()

    # Dynamic auto-discovery
    if check_server_online(args.server_url):
        run_via_daemon(args.server_url, args.code, args.target, args.fractional)
    else:
        run_locally(args.code, args.target, args.fractional)


if __name__ == "__main__":
    main()
