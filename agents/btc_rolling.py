#!/usr/bin/env python3
"""
BTC 5% 滚仓复利系统 v4.6
宏观感知型动态阈值系统
"""

import os
import sys

# Add the project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import asyncio
import time
import random
import math
import httpx
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from agents.base import BaseAgent
from simulation.exchange_sim import sim_exchange


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


class BinanceClient:
    """Binance Public Data Client"""
    def __init__(self):
        self.base_url = "https://api.binance.com"
        self.timeout = 10.0

    async def get_ticker_price(self, symbol: str) -> float:
        """Get latest price for a symbol"""
        clean_symbol = symbol.replace("/", "").upper()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/api/v3/ticker/price", params={"symbol": clean_symbol})
                response.raise_for_status()
                data = response.json()
                return float(data["price"])
            except Exception as e:
                print(f"Error fetching Binance price: {e}")
                return 0.0

    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[KLine]:
        """Get klines from Binance"""
        clean_symbol = symbol.replace("/", "").upper()
        # Binance interval mapping
        binance_interval = interval
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v3/klines", 
                    params={"symbol": clean_symbol, "interval": binance_interval, "limit": limit}
                )
                response.raise_for_status()
                data = response.json()
                klines = []
                for k in data:
                    klines.append(KLine(
                        symbol=symbol,
                        interval=interval,
                        timestamp=int(k[0]),
                        open=float(k[1]),
                        high=float(k[2]),
                        low=float(k[3]),
                        close=float(k[4]),
                        volume=float(k[5])
                    ))
                return klines
            except Exception as e:
                print(f"Error fetching Binance klines: {e}")
                return []


class OBDetector:
    def __init__(self):
        self.klines = {'1m': [], '5m': [], '15m': []}
    
    def detect_bullish_ob(self, interval: str = '5m') -> List[Dict]:
        klines = self.klines.get(interval, [])
        if len(klines) < 30:
            return []
        obs = []
        for i in range(5, len(klines) - 10):
            current = klines[i]
            if current.close >= current.open:
                continue
            prev_highs = [k.high for k in klines[max(0, i-8):i]]
            if len(prev_highs) < 3:
                continue
            descending = all(prev_highs[j] > prev_highs[j+1] for j in range(len(prev_highs)-1))
            if not descending:
                continue
            breakout_idx = None
            for j in range(i+1, min(i+12, len(klines))):
                if klines[j].close > current.high:
                    breakout_idx = j
                    break
            if breakout_idx is None:
                continue
            avg_vol = sum(k.volume for k in klines[max(0, i-20):i]) / 20
            volume_ratio = klines[breakout_idx].volume / avg_vol if avg_vol > 0 else 1.0
            strength = 5
            if volume_ratio > 2.0:
                strength += 3
            elif volume_ratio > 1.5:
                strength += 2
            elif volume_ratio > 1.2:
                strength += 1
            test_count = 0
            for j in range(breakout_idx+1, min(breakout_idx+20, len(klines))):
                if abs(klines[j].low - current.high) / current.high < 0.002:
                    test_count += 1
            strength += min(test_count, 2)
            age_hours = (klines[-1].timestamp - current.timestamp) / 3600
            obs.append({
                "price_high": current.high,
                "price_low": current.low,
                "strength": strength,
                "age_hours": age_hours,
                "interval": interval
            })
        obs.sort(key=lambda x: x['strength'], reverse=True)
        return obs[:3]
    
    def get_ob_score(self) -> int:
        total = 0
        intervals = ['15m', '5m', '1m']
        base_scores = [35, 25, 20]
        for interval, base_score in zip(intervals, base_scores):
            obs = self.detect_bullish_ob(interval)
            if obs:
                ob = obs[0]
                decay = int(ob['age_hours'] * (5 if interval == '15m' else 8 if interval == '5m' else 10))
                total += max(base_score + ob['strength'] - decay, 5)
        return min(total, 80)


class MarketStateDetector:
    def __init__(self):
        self.atr_pct = 1.5
        self.adx = 25
        self.trend_state = "neutral"
    
    def calculate_atr(self, klines: List[KLine], period: int = 14) -> float:
        if len(klines) < period + 1:
            return 1.5
        tr_values = []
        for i in range(1, min(period + 1, len(klines))):
            high = klines[-i].high
            low = klines[-i].low
            prev_close = klines[-i-1].close if i < len(klines)-1 else klines[-i].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)
        atr = sum(tr_values) / len(tr_values)
        price = klines[-1].close
        self.atr_pct = (atr / price) * 100
        return self.atr_pct
    
    def get_volatility_factor(self) -> float:
        if self.atr_pct < 1.5:
            return 0.93
        elif self.atr_pct < 1.2:
            return 0.96
        elif self.atr_pct < 2.0:
            return 1.00
        elif self.atr_pct < 3.0:
            return 1.04
        else:
            return 1.08
    
    def calculate_adx(self, klines: List[KLine], period: int = 14) -> float:
        if len(klines) < period + 1:
            return 25
        plus_dm, minus_dm, tr = [], [], []
        for i in range(1, period + 1):
            high_diff = klines[-i].high - klines[-i-1].high
            low_diff = klines[-i-1].low - klines[-i].low
            plus_dm.append(max(high_diff, 0))
            minus_dm.append(max(low_diff, 0))
            tr.append(max(klines[-i].high - klines[-i].low,
                         abs(klines[-i].high - klines[-i-1].close),
                         abs(klines[-i].low - klines[-i-1].close)))
        atr = sum(tr) / period
        plus_di = (sum(plus_dm) / period) / atr * 100
        minus_di = (sum(minus_dm) / period) / atr * 100
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
        self.adx = dx
        return dx
    
    def get_trend_factor(self) -> float:
        if self.adx < 20:
            return 1.02
        elif self.adx < 30:
            return 1.00
        elif self.adx < 40:
            return 0.97
        elif self.adx < 50:
            return 0.94
        else:
            return 0.91


class ScoringSystem:
    def __init__(self):
        self.scores = {"trend": 0, "ob": 0, "tech": 0, "macro": 0}
        self.ob_detector = OBDetector()
    
    def score_trend(self, klines_1h: List[KLine]) -> int:
        if len(klines_1h) < 2:
            return 0
        score = 0
        latest = klines_1h[-1]
        closes = [k.close for k in klines_1h[-55:]]
        if len(closes) >= 55:
            ema30 = self._ema(closes[-30:], 30) if len(closes) >= 30 else closes[-1]
            ema55 = self._ema(closes[-55:], 55) if len(closes) >= 55 else closes[-1]
        else:
            ema30 = latest.close
            ema55 = latest.close
        if ema30 > ema55:
            score += 30
        if len(klines_1h) >= 5:
            slope = (klines_1h[-1].close - klines_1h[-5].close) / klines_1h[-5].close * 100
            if slope > 0.5:
                score += 10
        if len(klines_1h) >= 55:
            closes_4h = [k.close for k in klines_1h[-55:]]
            ema30_4h = self._ema(closes_4h[-30:], 30) if len(closes_4h) >= 30 else latest.close
            ema55_4h = self._ema(closes_4h, 55)
            if ema30_4h > ema55_4h:
                score += 5
        self.scores["trend"] = min(score, 40)
        return self.scores["trend"]
    
    def score_ob(self, klines_by_interval: Dict[str, List[KLine]]) -> int:
        self.ob_detector.klines = klines_by_interval
        score = self.ob_detector.get_ob_score()
        self.scores["ob"] = score
        return score
    
    def score_tech(self, klines: List[KLine], market_state: str = "trend") -> int:
        if len(klines) < 50:
            return 0
        score = 0
        latest = klines[-1]
        closes = [k.close for k in klines[-50:]]
        ema20 = self._ema(closes[-20:], 20) if len(closes) >= 20 else latest.close
        ema50 = self._ema(closes[-50:], 50) if len(closes) >= 50 else latest.close
        if ema20 > ema50:
            ema_score = 15
            if market_state == "trend":
                ema_score += 5
            score += ema_score
        rsi = self._calculate_rsi(closes)
        if market_state == "trend":
            if rsi < 40:
                score += 20
            elif rsi < 50:
                score += 10
        sma20 = sum(closes[-20:]) / 20
        std = (sum((c - sma20) ** 2 for c in closes[-20:]) / 20) ** 0.5
        if sma20 - std < latest.close < sma20:
            boll_score = 15
            if market_state == "ranging":
                boll_score += 10
            score += boll_score
        self.scores["tech"] = min(score, 50)
        return self.scores["tech"]
    
    def score_macro(self, etf_inflow: float, etf_consecutive_days: int, news_sentiment: str) -> int:
        score = 0
        intercept = 0
        if etf_consecutive_days >= 3:
            score += 15
        if etf_inflow > 3.0:
            score += 10
        if etf_inflow < -1.0:
            intercept -= 15
        if news_sentiment == "positive":
            score += 5
        elif news_sentiment == "negative":
            intercept -= 10
        self.scores["macro"] = max(score + intercept, 0)
        return self.scores["macro"]
    
    def calculate_total(self) -> int:
        return sum(self.scores.values())
    
    def _ema(self, values: List[float], period: int) -> float:
        if len(values) < period:
            return values[-1] if values else 0
        multiplier = 2 / (period + 1)
        ema = values[0]
        for val in values[1:]:
            ema = (val - ema) * multiplier + ema
        return ema
    
    def _calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50
        gains, losses = [], []
        for i in range(1, period + 1):
            diff = closes[-i] - closes[-i-1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))


class DynamicThreshold:
    def __init__(self, base_threshold: int = 60):
        self.base_threshold = base_threshold
        self.volatility_factor = 1.0
        self.trend_factor = 1.0
        self.macro_factor = 1.0
        self.orderflow_factor = 1.0
    
    def calculate_final_threshold(self) -> int:
        multiplier = self.volatility_factor * self.trend_factor * self.macro_factor * self.orderflow_factor
        return int(self.base_threshold * multiplier)

    def update_factors(self, market_state: MarketStateDetector, macro_score: int, orderflow_ratio: float = 50.0):
        self.volatility_factor = market_state.get_volatility_factor()
        self.trend_factor = market_state.get_trend_factor()
        self.macro_factor = self._get_macro_factor(macro_score)
        self.orderflow_factor = self._get_orderflow_factor(orderflow_ratio)
    
    def _get_macro_factor(self, macro_score: int) -> float:
        if macro_score >= 10:
            return 0.92
        elif macro_score >= 0:
            return 0.98
        elif macro_score >= -10:
            return 1.02
        else:
            return 1.05
    
    def _get_orderflow_factor(self, buy_ratio: float) -> float:
        if buy_ratio > 65:
            return 0.94
        elif buy_ratio > 55:
            return 0.98
        elif buy_ratio > 45:
            return 1.00
        elif buy_ratio > 35:
            return 1.02
        else:
            return 1.05
    
    def calculate_final_threshold(self) -> int:
        product = self.volatility_factor * self.trend_factor * self.macro_factor * self.orderflow_factor
        final = int(self.base_threshold * product)
        return max(40, min(final, 80))


class RiskManager:
    def __init__(self, account_balance: float = 10000):
        self.initial_balance = account_balance
        self.daily_pnl = 0.0
    
    def macro_filter(self, macro_score: int) -> Tuple[bool, float]:
        if macro_score >= 10:
            return True, 1.0
        elif macro_score >= 0:
            return True, 0.5
        elif macro_score >= -10:
            return True, 0.25
        else:
            return False, 0.0
    
    def check_cost_protection(self, daily_pnl: float) -> Tuple[bool, float]:
        loss_ratio = -daily_pnl / self.initial_balance
        if loss_ratio < 0.03:
            return True, 1.0
        elif loss_ratio < 0.06:
            return True, 0.5
        else:
            return False, 0.0
    
    def get_position_size(self, signal_score: int, macro_multiplier: float) -> float:
        if signal_score >= 90:
            base_size = 5.0
        elif signal_score >= 75:
            base_size = 3.0
        elif signal_score >= 60:
            base_size = 2.0
        elif signal_score >= 50:
            base_size = 1.0
        else:
            return 0.0
        return base_size * macro_multiplier


class ExecutionPlanner:
    def select_plan(self, score: int, dynamic_threshold: int) -> Tuple[Optional[str], int, float]:
        if score >= max(dynamic_threshold, 60):
            return "A", 5, 0.05
        elif score >= max(dynamic_threshold, 50):
            return "B", 3, 0.03
        else:
            return None, 0, 0.0


import asyncio
import time
import random
import math
import httpx
import os
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import BaseAgent
from simulation.exchange_sim import sim_exchange
from core.telegram import send_alert_async


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


class BinanceClient:
    """Binance Public Data Client"""
    def __init__(self):
        self.base_url = "https://api.binance.com"
        self.timeout = 10.0

    async def get_ticker_price(self, symbol: str) -> float:
        """Get latest price for a symbol"""
        clean_symbol = symbol.replace("/", "").upper()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/api/v3/ticker/price", params={"symbol": clean_symbol})
                response.raise_for_status()
                data = response.json()
                return float(data["price"])
            except Exception as e:
                print(f"Error fetching Binance price: {e}")
                return 0.0

    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> List[KLine]:
        """Get klines from Binance"""
        clean_symbol = symbol.replace("/", "").upper()
        # Binance interval mapping
        binance_interval = interval
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v3/klines", 
                    params={"symbol": clean_symbol, "interval": binance_interval, "limit": limit}
                )
                response.raise_for_status()
                data = response.json()
                klines = []
                for k in data:
                    klines.append(KLine(
                        symbol=symbol,
                        interval=interval,
                        timestamp=int(k[0]),
                        open=float(k[1]),
                        high=float(k[2]),
                        low=float(k[3]),
                        close=float(k[4]),
                        volume=float(k[5])
                    ))
                return klines
            except Exception as e:
                print(f"Error fetching Binance klines: {e}")
                return []


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
        asyncio.create_task(self._strategy_loop())
        self.logger.info("btc_rolling_v46_started")
    
    async def _strategy_loop(self):
        while self.running:
            try:
                # 1. Fetch Current State
                price = await self.binance.get_ticker_price(self.symbol)
                if price == 0:
                    await asyncio.sleep(5)
                    continue
                
                # Update exchange simulation with real price
                sim_exchange.update_price(self.symbol, price)
                
                # Get account balance from simulation
                account = sim_exchange.accounts.get(self.account_id)
                if not account:
                    await asyncio.sleep(5)
                    continue
                
                current_balance = {
                    "total": account.total_balance,
                    "daily_pnl": account.total_balance - self.risk.initial_balance # Simple PnL calc
                }

                # 2. Update Market Data (KLines)
                for interval in ['1m', '5m', '15m', '1h']:
                    real_klines = await self.binance.get_klines(self.symbol, interval, 100)
                    if real_klines:
                        self.market_klines[interval] = real_klines

                klines_1h = self.market_klines.get('1h', [])
                klines_15m = self.market_klines.get('15m', [])
                
                if len(klines_1h) < 30 or len(klines_15m) < 20:
                    self.logger.warning("insufficient_data_waiting", h1_len=len(klines_1h), m15_len=len(klines_15m))
                    await asyncio.sleep(10)
                    continue

                # 3. Market Analysis & Scoring
                self.market_detector.calculate_atr(klines_1h)
                self.market_detector.calculate_adx(klines_1h)
                
                # Update scores
                self.scoring.score_trend(klines_1h)
                self.scoring.score_ob(self.market_klines)
                self.scoring.score_tech(klines_15m, self.market_detector.trend_state)
                
                # Get macro score (placeholder values for now, could be linked to news agent later)
                macro_score = self.scoring.score_macro(0.0, 0, "neutral")
                
                total_score = self.scoring.calculate_total()
                
                # 4. Dynamic Threshold Calculation
                self.threshold.update_factors(self.market_detector, macro_score)
                final_threshold = self.threshold.calculate_final_threshold()
                
                # 5. Risk & Execution Logic
                macro_ok, macro_multiplier = self.risk.macro_filter(macro_score)
                cost_ok, cost_multiplier = self.risk.check_cost_protection(current_balance["daily_pnl"])
                
                self.logger.info("strategy_tick", 
                                price=price, 
                                score=total_score, 
                                threshold=final_threshold, 
                                trend=self.market_detector.trend_state)

                if total_score >= final_threshold and macro_ok and cost_ok:
                    if not self._has_position():
                        if time.time() - self.last_trade >= self.trade_interval:
                            plan_name, _, target_return = self.executor.select_plan(total_score, final_threshold)
                            if plan_name:
                                pos_size_pct = self.risk.get_position_size(total_score, macro_multiplier * cost_multiplier)
                                if pos_size_pct > 0:
                                    await self._trade("buy", current_balance["total"], pos_size_pct, total_score, target_return)
                    else:
                        # Logic for potential exit or monitoring could go here
                        pass

                await asyncio.sleep(30) # Tick every 30 seconds
                
            except Exception as e:
                error_msg = f"Error in strategy loop: {e}"
                self.logger.error(error_msg, exc_info=True)
                await send_alert_async(f"🚨 [BTCRollingAgent] Loop error: {e}")
                await asyncio.sleep(10)
    
    def _update_simulated_klines(self, price: float):
        timestamp = int(time.time())
        for interval in ['1m', '5m', '15m', '1h']:
            kline = KLine(
                symbol=self.symbol,
                interval=interval,
                timestamp=timestamp,
                open=price * 0.999,
                high=price * 1.002,
                low=price * 0.998,
                close=price,
                volume=random.uniform(10, 100)
            )
            self.market_klines[interval].append(kline)
            if len(self.market_klines[interval]) > 200:
                self.market_klines[interval] = self.market_klines[interval][-200:]
    
    def _has_position(self) -> bool:
        return sim_exchange.accounts[self.account_id].position is not None
    
    async def _trade(self, side: str, balance: float, position_percent: float, score: int, target_return: float):
        amount = balance * position_percent / 100
        # Precision Guard: Binance typically uses 3-5 decimals for BTC
        amount = round(amount, 4)
        if amount < 0.0001:  # Absolute Minimum Lot Size check
            self.logger.warning("trade_skipped_too_small", amount=amount)
            return

        price = sim_exchange.get_price(self.symbol)
        result = await sim_exchange.create_order(self.account_id, self.symbol, side, amount)
        if result["success"]:
            self.last_trade = time.time()
            self.logger.info("v46_trade_executed", side=side, amount=amount, price=price, score=score, target=target_return)
            await send_alert_async(f"🚀 [BTCRollingAgent] Trade Executed: {side} {amount} {self.symbol} @ {price}")

async def main():
    import asyncio
    agent = BTCRollingAgent()
    await agent.start()
    try:
        while agent.running:
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        await agent.stop()

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
