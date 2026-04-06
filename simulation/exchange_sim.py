import random
import time
import json
import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from core.logger import setup_logger

@dataclass
class Position:
    symbol: str
    amount: float
    entry_price: float
    side: str = "long"
    timestamp: float = 0.0

class SimulatedAccount:
    def __init__(self, account_id: str, initial_balance: float, risk_config: Dict):
        self.account_id = account_id
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.available = initial_balance
        self.position: Optional[Position] = None
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.trades_today = 0
        self.risk_config = risk_config
        self.logger = setup_logger(f"account_{account_id}")

    @property
    def total_balance(self) -> float:
        return round(self.balance, 2)

    def check_risk(self, amount_usdt: float) -> Tuple[bool, str]:
        if self.trades_today >= 10:
            return False, "daily_trade_limit"
        risk_pct = amount_usdt / self.balance
        if risk_pct > self.risk_config.get("per_trade", 0.02):
            return False, f"per_trade_risk: {risk_pct:.2%}"
        if abs(self.daily_pnl) / self.initial_balance > self.risk_config.get("daily", 0.05):
            return False, "daily_loss_limit"
        return True, "ok"

    def execute(self, symbol: str, amount_usdt: float, price: float, side: str = "buy") -> Dict:
        ok, reason = self.check_risk(amount_usdt)
        if not ok:
            return {"success": False, "reason": reason}
        quantity = amount_usdt / price
        if side == "buy":
            if amount_usdt > self.available:
                return {"success": False, "reason": "insufficient_balance"}
            self.available -= amount_usdt
            self.position = Position(symbol, quantity, price, "long", time.time())
        else:
            if not self.position:
                return {"success": False, "reason": "no_position"}
            self.available += amount_usdt
            pnl = (price - self.position.entry_price) * self.position.amount
            self.daily_pnl += pnl
            self.total_pnl += pnl
            self.position = None
        self.trades_today += 1
        self.balance = self.available + (self.position.amount * price if self.position else 0)
        return {
            "success": True,
            "account_id": self.account_id,
            "balance": round(self.balance, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "position": self.position.__dict__ if self.position else None
        }

class SimulatedExchange:
    def __init__(self, state_file: str = "/tmp/irisquant_sim_state.json"):
        self.logger = setup_logger("sim_exchange")
        self.state_file = state_file
        self.accounts = {
            "A": SimulatedAccount("A", 10000.0, {"per_trade": 0.02, "daily": 0.05}),
            "B": SimulatedAccount("B", 50000.0, {"per_trade": 0.01, "daily": 0.03}),
            "C": SimulatedAccount("C", 2000.0, {"per_trade": 0.05, "daily": 0.10}),
            "W": SimulatedAccount("W", 500.0, {"per_trade": 0.10, "daily": 0.20}),
        }
        self.prices = {"BTC/USDT": 65000.0, "BTC-PERP": 65100.0}
        self.load_state()

    def save_state(self):
        state = {
            "accounts": {
                aid: {
                    "balance": acc.balance,
                    "available": acc.available,
                    "daily_pnl": acc.daily_pnl,
                    "total_pnl": acc.total_pnl,
                    "trades_today": acc.trades_today,
                    "position": acc.position.__dict__ if acc.position else None
                } for aid, acc in self.accounts.items()
            },
            "prices": self.prices
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                for aid, data in state["accounts"].items():
                    if aid in self.accounts:
                        acc = self.accounts[aid]
                        acc.balance = data["balance"]
                        acc.available = data["available"]
                        acc.daily_pnl = data["daily_pnl"]
                        acc.total_pnl = data["total_pnl"]
                        acc.trades_today = data["trades_today"]
                        if data["position"]:
                            acc.position = Position(**data["position"])
                self.prices = state.get("prices", self.prices)
            except Exception as e:
                self.logger.error(f"Failed to load state: {e}")
        else:
            # Initial simulation: Start clean without random drift
            for acc in self.accounts.values():
                acc.balance = acc.initial_balance
                acc.daily_pnl = 0.0
                acc.available = acc.balance
            self.save_state()

    def get_price(self, symbol: str) -> float:
        return self.prices.get(symbol, 65000.0)

    def update_price(self, symbol: str, price: float):
        self.prices[symbol] = price
        self.save_state()

    async def fetch_balance(self, account_id: str) -> Dict:
        self.load_state()  # Ensure fresh state
        acc = self.accounts[account_id.upper()]
        return {"account_id": acc.account_id, "total": round(acc.balance, 2), "daily_pnl": round(acc.daily_pnl, 2)}

    async def create_order(self, account_id: str, symbol: str, side: str, amount_usdt: float) -> Dict:
        self.load_state()
        acc = self.accounts[account_id.upper()]
        price = self.get_price(symbol)
        res = acc.execute(symbol, amount_usdt, price, side)
        if res["success"]:
            self.save_state()
        return res

    async def close_position(self, account_id: str, symbol: str) -> Dict:
        self.load_state()
        acc = self.accounts[account_id.upper()]
        if not acc.position:
            return {"success": False, "reason": "no_position"}
        price = self.get_price(symbol)
        res = acc.execute(symbol, acc.position.amount * price, price, "sell")
        if res["success"]:
            self.save_state()
        return res

sim_exchange = SimulatedExchange()
