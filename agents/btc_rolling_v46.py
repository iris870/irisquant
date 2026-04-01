import sys
import asyncio
import time
import random
import math
import httpx
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Mock or Import base components
# From your existing code structure
try:
    from agents.base import BaseAgent
    from simulation.exchange_sim import sim_exchange
except ImportError:
    # Fallback for standalone testing or if paths differ
    class BaseAgent:
        def __init__(self, name):
            self.name = name
            self.running = False
            self.logger = logging.getLogger(name)
        async def start(self): 
            self.running = True
            await self._on_start()
        async def stop(self): self.running = False
        async def _on_start(self): pass

    class MockAccount:
        def __init__(self):
            self.total_balance = 10000.0
            self.position = None
    
    class MockExchange:
        def __init__(self):
            self.prices = {}
            self.accounts = {"A": MockAccount()}
        def update_price(self, s, p): self.prices[s] = p
        def get_price(self, s): return self.prices.get(s, 0.0)
        async def create_order(self, aid, s, side, amt):
            self.accounts[aid].position = {"side": side, "amt": amt}
            return {"success": True}
    
    sim_exchange = MockExchange()

@dataclass
class KLine:
    symbol: str
    interval: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

class MarketStateDetector:
    def __init__(self):
        self.atr = 0.0
        self.adx = 0.0
        self.trend_state = "neutral" # bull, bear, neutral
        self.volatility_state = "low" # high, mid, low

    def calculate_atr(self, klines: List[KLine], period: int = 14):
        if len(klines) < period + 1: return
        tr_sum = 0
        for i in range(1, period + 1):
            h, l, pc = klines[-i].high, klines[-i].low, klines[-i-1].close
            tr = max(h - l, abs(h - pc), abs(l - pc))
            tr_sum += tr
        self.atr = tr_sum / period
        # Simple volatility classification
        avg_price = klines[-1].close
        if self.atr / avg_price > 0.02: self.volatility_state = "high"
        elif self.atr / avg_price > 0.005: self.volatility_state = "mid"
        else: self.volatility_state = "low"

    def calculate_adx(self, klines: List[KLine], period: int = 14):
        # Simplified trend strength
        if len(klines) < period: return
        change = klines[-1].close - klines[-period].close
        self.adx = abs(change) / klines[-period].close * 100
        if change > 0 and self.adx > 1.5: self.trend_state = "bull"
        elif change < 0 and self.adx > 1.5: self.trend_state = "bear"
        else: self.trend_state = "neutral"

class ScoringSystem:
    def __init__(self):
        self.scores = {"trend": 0, "ob": 0, "tech": 0, "macro": 0}
        
    def score_trend(self, klines: List[KLine]):
        if not klines: return
        # Logic: 1h EMA cross or slope
        self.scores["trend"] = 25 if klines[-1].close > klines[-10].close else 0

    def score_ob(self, market_data: Dict):
        # Orderbook / Volume logic
        self.scores["ob"] = random.randint(10, 20) # Placeholder for real OB depth analysis

    def score_tech(self, klines: List[KLine], trend: str):
        # RSI/BOLL logic
        score = 15
        if trend == "bull": score += 10
        self.scores["tech"] = score

    def score_macro(self, eth_flow: float, btc_etf: int, news_sent: str):
        score = 10
        if news_sent == "positive": score += 10
        self.scores["macro"] = score
        return score

    def calculate_total(self) -> int:
        return sum(self.scores.values())

class DynamicThreshold:
    def __init__(self, base_threshold: int = 60):
        self.base = base_threshold
        self.multiplier = 1.0

    def update_factors(self, market: MarketStateDetector, macro_score: int):
        mult = 1.0
        if market.volatility_state == "high": mult += 0.2
        if market.trend_state == "neutral": mult += 0.1
        if macro_score < 10: mult += 0.1
        self.multiplier = mult

    def calculate_final_threshold(self) -> int:
        return int(self.base * self.multiplier)

class RiskManager:
    def __init__(self, initial_balance: float):
        self.initial_balance = initial_balance

    def macro_filter(self, macro_score: int) -> Tuple[bool, float]:
        if macro_score < 5: return False, 0.0
        return True, 1.0

    def check_cost_protection(self, daily_pnl: float) -> Tuple[bool, float]:
        loss_ratio = -daily_pnl / self.initial_balance
        if loss_ratio < 0.03: return True, 1.0
        elif loss_ratio < 0.06: return True, 0.5
        else: return False, 0.0
    
    def get_position_size(self, signal_score: int, macro_multiplier: float) -> float:
        if signal_score >= 90: base_size = 5.0
        elif signal_score >= 75: base_size = 3.0
        elif signal_score >= 60: base_size = 2.0
        elif signal_score >= 50: base_size = 1.0
        else: return 0.0
        return base_size * macro_multiplier

class ExecutionPlanner:
    def select_plan(self, score: int, dynamic_threshold: int) -> Tuple[Optional[str], int, float]:
        if score >= max(dynamic_threshold, 60): return "A", 5, 0.05
        elif score >= max(dynamic_threshold, 50): return "B", 3, 0.03
        else: return None, 0, 0.0

class BinanceClient:
    def __init__(self):
        self.base_url = "https://api.binance.com"
        self.timeout = 10.0

    async def get_ticker_price(self, symbol: str) -> float:
        clean_symbol = symbol.replace("/", "").upper()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/api/v3/ticker/price", params={"symbol": clean_symbol})
                response.raise_for_status()
                return float(response.json()["price"])
            except: return 0.0

    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[KLine]:
        clean_symbol = symbol.replace("/", "").upper()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/api/v3/klines", params={"symbol": clean_symbol, "interval": interval, "limit": limit})
                response.raise_for_status()
                return [KLine(symbol, interval, int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])) for k in response.json()]
            except: return []

class BTCRollingAgent(BaseAgent):
    def __init__(self):
        super().__init__("btc-rolling-v46")
        self.account_id = "A"
        self.symbol = "BTC/USDT"
        self.binance = BinanceClient()
        self.market_detector = MarketStateDetector()
        self.scoring = ScoringSystem()
        self.threshold = DynamicThreshold(base_threshold=60)
        self.risk = RiskManager(10000)
        self.executor = ExecutionPlanner()
        self.last_trade = 0
        self.trade_interval = 300
        self.market_klines = {'1m': [], '5m': [], '15m': [], '1h': []}
    
    async def _on_start(self):
        self.logger.info("btc_rolling_v46_started")
        asyncio.create_task(self._strategy_loop())
    
    async def _strategy_loop(self):
        while self.running:
            try:
                price = await self.binance.get_ticker_price(self.symbol)
                if price == 0:
                    await asyncio.sleep(5); continue
                
                sim_exchange.update_price(self.symbol, price)
                account = sim_exchange.accounts.get(self.account_id)
                if not account:
                    await asyncio.sleep(5); continue
                
                current_balance = {"total": account.total_balance, "daily_pnl": account.total_balance - self.risk.initial_balance}

                for interval in ['1m', '5m', '15m', '1h']:
                    kl = await self.binance.get_klines(self.symbol, interval, 50)
                    if kl: self.market_klines[interval] = kl

                klines_1h = self.market_klines.get('1h', [])
                klines_15m = self.market_klines.get('15m', [])
                
                if len(klines_1h) < 20 or len(klines_15m) < 15:
                    await asyncio.sleep(10); continue

                self.market_detector.calculate_atr(klines_1h)
                self.market_detector.calculate_adx(klines_1h)
                self.scoring.score_trend(klines_1h)
                self.scoring.score_ob(self.market_klines)
                self.scoring.score_tech(klines_15m, self.market_detector.trend_state)
                macro_score = self.scoring.score_macro(0.0, 0, "neutral")
                total_score = self.scoring.calculate_total()
                
                self.threshold.update_factors(self.market_detector, macro_score)
                final_threshold = self.threshold.calculate_final_threshold()
                
                macro_ok, macro_multiplier = self.risk.macro_filter(macro_score)
                cost_ok, cost_multiplier = self.risk.check_cost_protection(current_balance["daily_pnl"])
                
                print(f"[TICK] Price: {price} | Score: {total_score}/{final_threshold} | Trend: {self.market_detector.trend_state}")
                sys.stdout.flush()

                if total_score >= final_threshold and macro_ok and cost_ok:
                    if not self._has_position() and (time.time() - self.last_trade >= self.trade_interval):
                        plan_name, _, target_return = self.executor.select_plan(total_score, final_threshold)
                        pos_size_pct = self.risk.get_position_size(total_score, macro_multiplier * cost_multiplier)
                        if pos_size_pct > 0:
                            await self._trade("buy", current_balance["total"], pos_size_pct, total_score, target_return)

                await asyncio.sleep(30)
            except Exception as e:
                print(f"Loop Error: {e}")
                await asyncio.sleep(10)
    
    def _has_position(self) -> bool:
        return sim_exchange.accounts[self.account_id].position is not None
    
    async def _trade(self, side: str, balance: float, position_percent: float, score: int, target_return: float):
        amount = balance * position_percent / 100
        price = sim_exchange.get_price(self.symbol)
        result = await sim_exchange.create_order(self.account_id, self.symbol, side, amount)
        if result["success"]:
            self.last_trade = time.time()
            print(f"🚀 [TRADE] {side} {amount} at {price} (Score: {score})")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = BTCRollingAgent()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(agent.start())
        loop.run_forever()
    except KeyboardInterrupt:
        pass
