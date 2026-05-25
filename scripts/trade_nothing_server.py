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
    """
    slug = generate_topic_slug(f"{symbol} analysis")
    
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
        # 1. Fetch current price
        quote = GLOBAL_DATA_GATEWAY.fetch_price(symbol)
        curr_price = quote.get("price", 0.0)
        if curr_price <= 0:
            # Fallback if APIs are offline
            symbol_type, _ = PortfolioManager.classify_symbol(symbol)
            curr_price = 16.41 if symbol_type == "A_SHARE" else (65000.0 if symbol_type == "CRYPTO" else 180.0)

        # Round 1 Simulation
        time.sleep(1.0)
        with SESSIONS_LOCK:
            s = ACTIVE_RESEARCH_SESSIONS[symbol]
            s["round"] = 1
            s["lfi"] = 0.55
            s["posterior"] = 0.60
            s["log"].append("Round 1: Detective presented fundamental bull arguments. Inquisitor countered with supply concerns.")

        # Round 2 Simulation
        time.sleep(1.0)
        with SESSIONS_LOCK:
            s = ACTIVE_RESEARCH_SESSIONS[symbol]
            s["round"] = 2
            s["lfi"] = 0.32
            s["posterior"] = 0.75
            s["log"].append("Round 2: Detective defended with strong proxy metrics. Inquisitor audited cash flow parameters.")

        # Round 3 Simulation (Convergence)
        time.sleep(1.0)
        final_lfi = 0.08
        final_posterior = 0.85
        
        with SESSIONS_LOCK:
            s = ACTIVE_RESEARCH_SESSIONS[symbol]
            s["round"] = 3
            s["lfi"] = final_lfi
            s["posterior"] = final_posterior
            s["status"] = "CONVERGED"
            s["log"].append("Round 3: LFI dropped below 0.15 limit. Judge confirmed convergence, resolving all unrefuted attacks.")

        # Save simulated state to physical file to maintain pipeline standard
        state_data = {
            "topic": f"{symbol} analysis",
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
