"""
Trade Nothing v7.0 — Quantitative Portfolio & Trade Gateway

Provides a thread-safe, process-safe portfolio ledger ('portfolio_state.json'),
implements the dynamic fractional Kelly sizing engine, and dispatches orders
to pluggable simulated or real broker trade connectors.
"""

import os
import sys
import re
import json
import fcntl
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

# Resolve paths
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)

from utils import get_scratch_dir, load_json_safe, save_json

PORTFOLIO_LOCK = threading.RLock()


class BaseTradeConnector(ABC):
    """Abstract class defining standard interface for broker connectors"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def execute_order(self, symbol: str, target_qty: int, price: float, order_type: str, currency: str) -> dict:
        """
        Executes an order (Buy/Sell) through the broker gateway.
        Returns order status dictionary.
        """
        pass


class PaperTradingConnector(BaseTradeConnector):
    """Zero-dependency high-fidelity simulated trading gateway"""
    
    @property
    def name(self) -> str:
        return "Simulated_Paper_Trading"

    def execute_order(self, symbol: str, target_qty: int, price: float, order_type: str, currency: str) -> dict:
        # Returns standard receipt
        import time
        return {
            "status": "FILLED",
            "order_id": f"SIM_{int(time.time())}_{symbol}",
            "symbol": symbol,
            "quantity": target_qty,
            "price": price,
            "type": order_type,
            "currency": currency,
            "timestamp": time.time(),
            "connector": self.name
        }


class FutuConnector(BaseTradeConnector):
    """Futu OpenAPI Mock/Preset Connector for domestic A-shares and HK shares"""
    
    @property
    def name(self) -> str:
        return "Futu_Open_API"

    def execute_order(self, symbol: str, target_qty: int, price: float, order_type: str, currency: str) -> dict:
        # In a real environment, developers would import FutuOpenAPI libraries:
        # from futu import OpenUSTradeContext, OrderType
        print(f"[MOCK FUTU] Dispatching {order_type} order of {target_qty} shares of {symbol} at {price} {currency} to Futu OpenAPI...", file=sys.stderr)
        import time
        return {
            "status": "FILLED",
            "order_id": f"FUTU_MOCK_{int(time.time())}",
            "symbol": symbol,
            "quantity": target_qty,
            "price": price,
            "type": order_type,
            "currency": currency,
            "timestamp": time.time(),
            "connector": self.name
        }


class IBKRConnector(BaseTradeConnector):
    """Interactive Brokers API Mock/Preset Connector for US equities and Cryptocurrencies"""
    
    @property
    def name(self) -> str:
        return "IBKR_TWS_Gateway"

    def execute_order(self, symbol: str, target_qty: int, price: float, order_type: str, currency: str) -> dict:
        # In a real environment, developers would import ibapi:
        # from ibapi.client import EClient
        # from ibapi.wrapper import EWrapper
        print(f"[MOCK IBKR] Dispatching {order_type} order of {target_qty} shares of {symbol} at {price} {currency} to IBKR TWS Gateway...", file=sys.stderr)
        import time
        return {
            "status": "FILLED",
            "order_id": f"IBKR_MOCK_{int(time.time())}",
            "symbol": symbol,
            "quantity": target_qty,
            "price": price,
            "type": order_type,
            "currency": currency,
            "timestamp": time.time(),
            "connector": self.name
        }


# ─── Thread-Safe & Process-Safe State Manager ─────────────────────────────

class PortfolioManager:
    def __init__(self):
        self.state_file = os.path.join(get_scratch_dir(), "portfolio_state.json")
        self.lock_file = self.state_file + ".lock"
        self._init_default_state()

    def _init_default_state(self):
        """Creates standard ledger state if not already initialized"""
        with PORTFOLIO_LOCK:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            if not os.path.exists(self.state_file):
                default_data = {
                    "cash": {
                        "CNY": 1000000.00,  # Default 1 million CNY for A-shares
                        "USD": 100000.00    # Default 100k USD for Crypto/US shares
                    },
                    "holdings": {},  # Format: {"AAPL": {"qty": 100, "entry_price": 180.0, "currency": "USD"}}
                    "transactions": []
                }
                save_json(self.state_file, default_data)

    def _state_transaction(self, read_only: bool = False):
        """
        Guarantees process-level flock and thread-level reentrant locks.
        Yields state dictionary to preserve transactional integrity across read-write gaps.
        """
        class TransactionContext:
            def __init__(self, manager):
                self.manager = manager
                self.lock_fd = None

            def __enter__(self) -> dict:
                PORTFOLIO_LOCK.acquire()
                # Open/create lock file
                self.lock_fd = open(self.manager.lock_file, "w")
                # Wait for exclusive flock
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX)
                # Load current state safely
                self.state = load_json_safe(self.manager.state_file)
                return self.state

            def __exit__(self, exc_type, exc_val, exc_tb):
                try:
                    if not read_only and exc_type is None:
                        # Save modified state
                        save_json(self.manager.state_file, self.state)
                finally:
                    # Release flock
                    if self.lock_fd:
                        fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                        self.lock_fd.close()
                    # Release thread lock
                    PORTFOLIO_LOCK.release()

        return TransactionContext(self)

    def get_summary(self) -> dict:
        """Returns a snapshot of the portfolio cash and active position sizes"""
        with self._state_transaction(read_only=True) as state:
            return state

    def adjust_cash(self, currency: str, amount: float) -> float:
        """Updates cash balance safely (e.g. deposits/withdrawals)"""
        with self._state_transaction(read_only=False) as state:
            current = state["cash"].get(currency, 0.0)
            new_bal = current + amount
            state["cash"][currency] = round(new_bal, 2)
            return new_bal

    # ─── Dynamic Kelly Sizing Engine ──────────────────────────────────────

    @staticmethod
    def calculate_kelly_size(
        posterior: float, 
        target_price: float, 
        current_price: float, 
        fractional: float = 0.25,
        lfi: float = 0.0
    ) -> float:
        """
        Computes dynamic fractional Kelly allocation.
        Formula:
            f* = fractional * (p * b - q) / b
        Where:
            p = posterior probability (Judge consensus win rate)
            b = asymmetric risk-reward ratio: abs(target - current) / current
            q = 1 - p
        """
        # 1. Capital Protection Circuit Breakers
        if lfi >= 0.15:
            # High LFI conflict means severe argumentation friction. Absolute hard stop!
            return 0.0
        if posterior < 0.50:
            # Win probability below 50% does not present edge. Hard stop!
            return 0.0
        if current_price <= 0:
            return 0.0

        p = posterior
        b = abs(target_price - current_price) / current_price
        q = 1.0 - p

        if b <= 0:
            return 0.0

        # Raw Kelly Sizing
        f_star = (p * b - q) / b
        
        if f_star <= 0:
            return 0.0

        # Apply fractional allocation multiplier (e.g. Quarter-Kelly) for capital conservation
        allocation = f_star * fractional
        
        # Max cap allocation for single ticker is 50% to prevent over-leverage
        return min(allocation, 0.50)

    # ─── Standard Order Sizing Rules ──────────────────────────────────────

    @staticmethod
    def classify_symbol(symbol: str) -> Tuple[str, str]:
        """Classifies symbol format into asset type and currency"""
        symbol_clean = symbol.strip()
        if re.match(r"^\d{6}$", symbol_clean):
            return "A_SHARE", "CNY"
        elif symbol_clean.lower() in {"bitcoin", "ethereum", "btc", "eth"} or re.match(r"^[A-Z]{3,5}USDT$", symbol_clean):
            return "CRYPTO", "USD"
        else:
            return "GLOBAL_US", "USD"

    @staticmethod
    def round_order_lot(symbol_type: str, raw_qty: float) -> float:
        """Applies realistic asset-specific rounding rules"""
        if symbol_type == "A_SHARE":
            # A-shares require 100 share board lots
            rounded = (int(raw_qty) // 100) * 100
            return float(rounded)
        elif symbol_type == "CRYPTO":
            # Cryptocurrencies permit fractional lots
            return round(raw_qty, 4)
        else:
            # Standard US equities require integer shares
            return float(round(raw_qty))

    # ─── Core Execution Pipeline ──────────────────────────────────────────

    def execute_kelly_sizing_trade(
        self,
        symbol: str,
        posterior: float,
        target_price: float,
        current_price: float,
        lfi: float = 0.0,
        fractional: float = 0.25,
        connector: BaseTradeConnector = None
    ) -> dict:
        """
        Evaluates current holdings, computes Kelly target position value,
        rounds quantities to standard asset lot sizes, and executes standard order.
        """
        if connector is None:
            connector = PaperTradingConnector()

        symbol_type, currency = self.classify_symbol(symbol)
        
        # Calculate target Kelly fraction
        k_fraction = self.calculate_kelly_size(posterior, target_price, current_price, fractional, lfi)

        with self._state_transaction(read_only=False) as state:
            cash_bal = state["cash"].get(currency, 0.0)
            
            # Compute total equity in this currency sector (Cash + current value of all holdings in this currency)
            total_holdings_value = 0.0
            for ticker, data in state["holdings"].items():
                t_type, t_currency = self.classify_symbol(ticker)
                if t_currency == currency:
                    # For active valuation, we use current price for target calculations
                    # If ticker is the target symbol, we use the passed current_price
                    c_pr = current_price if ticker == symbol else data.get("entry_price", 0.0)
                    total_holdings_value += data["qty"] * c_pr

            total_equity = cash_bal + total_holdings_value
            
            # Target holding value based on Kelly size
            target_value = total_equity * k_fraction
            target_qty = target_value / current_price if current_price > 0 else 0.0
            
            # Apply asset rounding rules
            target_qty_rounded = self.round_order_lot(symbol_type, target_qty)
            
            # Get current holding qty
            current_qty = state["holdings"].get(symbol, {}).get("qty", 0.0)
            
            qty_diff = target_qty_rounded - current_qty
            
            if qty_diff == 0:
                return {
                    "action": "HOLD",
                    "symbol": symbol,
                    "target_kelly": k_fraction,
                    "current_qty": current_qty,
                    "target_qty": target_qty_rounded,
                    "note": "No transaction required, current position matches target sizing."
                }

            order_type = "BUY" if qty_diff > 0 else "SELL"
            trade_qty = abs(qty_diff)
            cost = trade_qty * current_price

            # Check cash availability for BUYS
            if order_type == "BUY" and cost > cash_bal:
                # Constrain buy to remaining cash
                trade_qty = self.round_order_lot(symbol_type, cash_bal / current_price)
                cost = trade_qty * current_price
                if trade_qty <= 0:
                    return {
                        "action": "REJECT",
                        "symbol": symbol,
                        "reason": "Insufficient cash balance to buy minimal board lot."
                    }

            # Execute via connector
            receipt = connector.execute_order(symbol, int(trade_qty) if symbol_type != "CRYPTO" else trade_qty, current_price, order_type, currency)
            
            if receipt.get("status") == "FILLED":
                # Update Ledger
                if order_type == "BUY":
                    state["cash"][currency] = round(cash_bal - cost, 2)
                    
                    if symbol not in state["holdings"]:
                        state["holdings"][symbol] = {
                            "qty": trade_qty,
                            "entry_price": current_price,
                            "currency": currency
                        }
                    else:
                        h = state["holdings"][symbol]
                        # Compute weighted average cost base
                        total_qty = h["qty"] + trade_qty
                        avg_price = ((h["qty"] * h["entry_price"]) + cost) / total_qty
                        h["qty"] = total_qty
                        h["entry_price"] = round(avg_price, 4)
                else:
                    # SELL
                    state["cash"][currency] = round(cash_bal + cost, 2)
                    h = state["holdings"].get(symbol)
                    if h:
                        h["qty"] -= trade_qty
                        if h["qty"] <= 0:
                            del state["holdings"][symbol]

                # Append transaction to history logs
                state["transactions"].append(receipt)
                
                return {
                    "action": "EXECUTE",
                    "symbol": symbol,
                    "target_kelly": k_fraction,
                    "order_type": order_type,
                    "executed_qty": trade_qty,
                    "price": current_price,
                    "cost": cost,
                    "remaining_cash": state["cash"][currency],
                    "receipt": receipt
                }
            
            return {
                "action": "FAILED",
                "symbol": symbol,
                "reason": f"Trade connector {connector.name} failed execution."
            }


if __name__ == "__main__":
    # Standard health-check CLI tool representation
    mgr = PortfolioManager()
    print(json.dumps(mgr.get_summary(), ensure_ascii=False, indent=2))
