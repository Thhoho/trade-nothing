"""
Trade Nothing v7.0 — Autonomous Agent Daemon Server

Provides a zero-dependency HTTP REST API backend built on Python's native http.server.
Handles async background research simulations, simulated trade execution,
portfolio dashboard reporting, and TradingView webhook alert integrations.

Run:
    python3 scripts/trade_nothing_server.py
"""

import os
import sys
import json
import time
import re
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from typing import Dict, Any

# Resolve paths
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from portfolio_manager import PortfolioManager, PaperTradingConnector
from data_providers import GLOBAL_DATA_GATEWAY
from utils import get_state_dir, generate_topic_slug, save_json

# Global task cache (in-memory tracking of background research runs)
ACTIVE_RESEARCH_SESSIONS: Dict[str, dict] = {}
SESSIONS_LOCK = threading.Lock()


def _simulate_debate_worker(symbol: str, target_price: float, fractional_kelly: float = 0.25):
    """
    Background worker simulating a 3-round adversarial debate
    and triggering automated Kelly execution upon convergence.
    Runs actual deepthink_engine calculations programmatically for mathematical validity.
    """
    topic_name = f"{symbol} analysis"
    slug = generate_topic_slug(topic_name)
    
    with SESSIONS_LOCK:
        ACTIVE_RESEARCH_SESSIONS[symbol] = {
            "symbol": symbol,
            "status": "RUNNING",
            "round": 1,
            "lfi": 0.65,
            "posterior": 0.50,
            "log": ["Phase 1: Negative Priors extracted and injected.", "Phase 2: Detective & Inquisitor sub-agents mobilized."]
        }
    
    try:
        # Import deepthink_engine dynamically
        import deepthink_engine
        
        # Configure state file path for this topic name
        deepthink_engine.resolve_state_file(topic=topic_name)
        
        # 1. Initialize deepthink session state file
        deepthink_engine.cmd_start(topic_name)
        
        # Fetch current price
        quote = GLOBAL_DATA_GATEWAY.fetch_price(symbol)
        curr_price = quote.get("price", 0.0)
        if curr_price <= 0:
            symbol_type, _ = PortfolioManager.classify_symbol(symbol)
            curr_price = 16.41 if symbol_type == "A_SHARE" else (65000.0 if symbol_type == "CRYPTO" else 180.0)

        # Dynamic arguments class definition to mock command-line arguments passed to checkpoint
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

        # Hide prints from the CLI checkpoint output to suppress server stdout pollution
        import io
        from contextlib import redirect_stdout

        # --- Round 1: Detective introduces strong physical proxy data ---
        time.sleep(1.0)
        args_r1 = DummyArgs(
            topic=topic_name,
            round=1,
            arguments_json=json.dumps(["A-shares 300118 component exports Ningbo customs up 8.2% YoY", "Low-temp silver paste raw materials SMM spot price drops 1.2%"]),
            attacks_json=json.dumps([]),
            evidence_json=json.dumps([
                {"category": "Hard Proxy Data", "direction": "Bull", "strength": "Strong"}
            ]),
            forbidden_consensus_json=json.dumps(["光伏行业产能过剩导致组件价格内卷严重"])
        )
        
        f = io.StringIO()
        with redirect_stdout(f):
            deepthink_engine.cmd_checkpoint(args_r1)
            
        r1_state = deepthink_engine.load_state()
        r1_data = r1_state["rounds"][-1]
        
        with SESSIONS_LOCK:
            s = ACTIVE_RESEARCH_SESSIONS[symbol]
            s["round"] = 1
            s["lfi"] = r1_data["lfi"]
            s["posterior"] = r1_data["posterior"] / 100.0
            s["log"].append("Round 1: Detective presented fundamental customs and raw material pricing. Win rate updated.")

        # --- Round 2: Inquisitor strikes back with raw materials squeeze ---
        time.sleep(1.0)
        args_r2 = DummyArgs(
            topic=topic_name,
            round=2,
            arguments_json=json.dumps(["A-shares 300118 component exports Ningbo customs up 8.2% YoY", "Low-temp silver paste raw materials SMM spot price drops 1.2%", "Indium price surge squeeze margins"]),
            attacks_json=json.dumps([
                ["Indium price surge squeeze margins", "A-shares 300118 component exports Ningbo customs up 8.2% YoY"]
            ]),
            evidence_json=json.dumps([
                {"category": "Channel Checks", "direction": "Bear", "strength": "Weak"}
            ]),
            forbidden_consensus_json=json.dumps(["光伏行业产能过剩导致组件价格内卷严重"])
        )
        
        f = io.StringIO()
        with redirect_stdout(f):
            deepthink_engine.cmd_checkpoint(args_r2)
            
        r2_state = deepthink_engine.load_state()
        r2_data = r2_state["rounds"][-1]
        
        with SESSIONS_LOCK:
            s = ACTIVE_RESEARCH_SESSIONS[symbol]
            s["round"] = 2
            s["lfi"] = r2_data["lfi"]
            s["posterior"] = r2_data["posterior"] / 100.0
            s["log"].append("Round 2: Inquisitor audited and attacked with Indium raw material costs.")

        # --- Round 3: Detective counter-attacks with expert recycling proof ---
        time.sleep(1.0)
        args_r3 = DummyArgs(
            topic=topic_name,
            round=3,
            arguments_json=json.dumps(["A-shares 300118 component exports Ningbo customs up 8.2% YoY", "Low-temp silver paste raw materials SMM spot price drops 1.2%", "Indium price surge squeeze margins", "Expert leak confirms Indium recycling rate reaches 92%"]),
            attacks_json=json.dumps([
                ["Indium price surge squeeze margins", "A-shares 300118 component exports Ningbo customs up 8.2% YoY"],
                ["Expert leak confirms Indium recycling rate reaches 92%", "Indium price surge squeeze margins"]
            ]),
            evidence_json=json.dumps([
                {"category": "Hard Proxy Data", "direction": "Bull", "strength": "Strong"}
            ]),
            forbidden_consensus_json=json.dumps(["光伏行业产能过剩导致组件价格内卷严重"])
        )
        
        f = io.StringIO()
        with redirect_stdout(f):
            deepthink_engine.cmd_checkpoint(args_r3)
            
        r3_state = deepthink_engine.load_state()
        r3_data = r3_state["rounds"][-1]
        final_lfi = r3_data["lfi"]
        final_posterior = r3_data["posterior"] / 100.0
        
        with SESSIONS_LOCK:
            s = ACTIVE_RESEARCH_SESSIONS[symbol]
            s["round"] = 3
            s["lfi"] = final_lfi
            s["posterior"] = final_posterior
            s["status"] = "CONVERGED"
            s["log"].append("Round 3: Detective counter-defended with Indium recycling evidence. LFI cleared convergence limit.")

        # Save simulated state to physical file
        state_data = {
            "topic": topic_name,
            "slug": slug,
            "total_rounds": 3,
            "lfi": final_lfi,
            "posterior": f"{final_posterior * 100:.2f}%",
            "timestamp": time.time(),
            "verdict": "CONVERGED"
        }
        state_file_path = os.path.join(get_state_dir(), f"{slug}.json")
        save_json(state_file_path, state_data)

        # 2. Automated trade execution based on convergent Kelly
        pm = PortfolioManager()
        trade_res = pm.execute_kelly_sizing_trade(
            symbol=symbol,
            posterior=final_posterior,
            target_price=target_price,
            current_price=curr_price,
            lfi=final_lfi,
            fractional=fractional_kelly
        )
        
        with SESSIONS_LOCK:
            ACTIVE_RESEARCH_SESSIONS[symbol]["trade_execution"] = trade_res
            ACTIVE_RESEARCH_SESSIONS[symbol]["status"] = "COMPLETED"
            ACTIVE_RESEARCH_SESSIONS[symbol]["log"].append(f"Automated Sizing Triggered: {trade_res.get('action')} - {trade_res.get('note', '')}")

    except Exception as e:
        with SESSIONS_LOCK:
            if symbol in ACTIVE_RESEARCH_SESSIONS:
                ACTIVE_RESEARCH_SESSIONS[symbol]["status"] = "FAILED"
                ACTIVE_RESEARCH_SESSIONS[symbol]["error"] = str(e)


# ─── HTTP REST Request Handler ────────────────────────────────────────────

class TradeNothingRequestHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        # Override to suppress default console clutter unless desired
        pass

    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        # Standard CORS Headers to allow UI integrations
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        # ─── GET /api/status ───
        if path == "/api/status":
            pm = PortfolioManager()
            portfolio = pm.get_summary()
            
            with SESSIONS_LOCK:
                sessions_snapshot = dict(ACTIVE_RESEARCH_SESSIONS)
                
            self._send_json(200, {
                "status": "UP",
                "timestamp": time.time(),
                "portfolio_summary": portfolio,
                "active_research_sessions": sessions_snapshot
            })

        # ─── GET /api/research/status ───
        elif path == "/api/research/status":
            symbol = query.get("symbol", [None])[0]
            if not symbol:
                self._send_json(400, {"error": "Missing required query parameter: symbol"})
                return
                
            with SESSIONS_LOCK:
                session = ACTIVE_RESEARCH_SESSIONS.get(symbol)
                
            if session:
                self._send_json(200, session)
            else:
                self._send_json(404, {"error": f"No active or completed research session found for symbol: {symbol}"})

        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON body"})
            return

        path = self.path

        # ─── POST /api/research/start ───
        if path == "/api/research/start":
            symbol = data.get("symbol")
            target_price = data.get("target_price")
            fractional = data.get("fractional", 0.25)
            
            if not symbol or target_price is None:
                self._send_json(400, {"error": "Missing required parameters: symbol, target_price"})
                return

            try:
                target_price = float(target_price)
            except ValueError:
                self._send_json(400, {"error": "target_price must be a float value"})
                return

            # Start async background research debate
            thread = threading.Thread(target=_simulate_debate_worker, args=(symbol, target_price, fractional))
            thread.daemon = True
            thread.start()

            self._send_json(202, {
                "status": "ACCEPTED",
                "symbol": symbol,
                "message": f"Async background research debate initialized for {symbol} with target {target_price}."
            })

        # ─── POST /api/trade/execute ───
        elif path == "/api/trade/execute":
            symbol = data.get("symbol")
            posterior = data.get("posterior")
            target_price = data.get("target_price")
            current_price = data.get("current_price")
            lfi = data.get("lfi", 0.0)
            fractional = data.get("fractional", 0.25)

            if not symbol or posterior is None or target_price is None or current_price is None:
                self._send_json(400, {"error": "Missing required parameters: symbol, posterior, target_price, current_price"})
                return

            try:
                pm = PortfolioManager()
                trade_res = pm.execute_kelly_sizing_trade(
                    symbol=symbol,
                    posterior=float(posterior),
                    target_price=float(target_price),
                    current_price=float(current_price),
                    lfi=float(lfi),
                    fractional=float(fractional)
                )
                self._send_json(200, trade_res)
            except Exception as e:
                self._send_json(500, {"error": f"Execution failed: {str(e)}"})

        # ─── POST /api/webhook/tradingview ───
        elif path == "/api/webhook/tradingview":
            ticker = data.get("ticker")
            price = data.get("price")
            action = data.get("action", "buy").upper()
            target_price = data.get("target_price")
            
            # Optional pre-calculated parameters
            posterior = data.get("posterior")
            lfi = data.get("lfi", 0.0)

            if not ticker or price is None or target_price is None:
                self._send_json(400, {"error": "Webhook missing critical parameters: ticker, price, target_price"})
                return

            try:
                price = float(price)
                target_price = float(target_price)
            except ValueError:
                self._send_json(400, {"error": "price and target_price must be numeric"})
                return

            # If pre-calculated posterior exists, execute Kelly Sizing trade immediately
            if posterior is not None:
                try:
                    pm = PortfolioManager()
                    trade_res = pm.execute_kelly_sizing_trade(
                        symbol=ticker,
                        posterior=float(posterior),
                        target_price=target_price,
                        current_price=price,
                        lfi=float(lfi)
                    )
                    self._send_json(200, {
                        "webhook_status": "PROCESSED_IMMEDIATELY",
                        "trade_result": trade_res
                    })
                except Exception as e:
                    self._send_json(500, {"error": f"Immediate execution failed: {str(e)}"})
            else:
                # Spawn background research thread to check consensus expectations first
                thread = threading.Thread(target=_simulate_debate_worker, args=(ticker, target_price))
                thread.daemon = True
                thread.start()
                self._send_json(202, {
                    "webhook_status": "DEBATE_SPAWNED",
                    "ticker": ticker,
                    "message": f"Webhook received for {ticker}. Spawning background debate to calculate objective Kelly size."
                })

        else:
            self._send_json(404, {"error": "Endpoint not found"})


# ─── Daemon Server Launch ──────────────────────────────────────────────────

def run_server(port: int = 8000):
    server_address = ("", port)
    httpd = HTTPServer(server_address, TradeNothingRequestHandler)
    print(f"==================================================================", file=sys.stderr)
    print(f"🚀 Trade Nothing v7.0 Standing Autonomous Daemon Server Online", file=sys.stderr)
    print(f"   Listening on: http://localhost:{port}", file=sys.stderr)
    print(f"   Endpoints:", file=sys.stderr)
    print(f"     - GET  /api/status", file=sys.stderr)
    print(f"     - GET  /api/research/status?symbol=...", file=sys.stderr)
    print(f"     - POST /api/research/start", file=sys.stderr)
    print(f"     - POST /api/trade/execute", file=sys.stderr)
    print(f"     - POST /api/webhook/tradingview", file=sys.stderr)
    print(f"==================================================================", file=sys.stderr)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🧹 Shutting down Autonomous Daemon Server gracefully...", file=sys.stderr)
        httpd.server_close()


if __name__ == "__main__":
    port = int(os.environ.get("TRADE_NOTHING_PORT", 8000))
    run_server(port)
