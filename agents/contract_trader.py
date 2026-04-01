import os
import sys

# Ensure irisquant root and venv site-packages are in the path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)
VENV_SITE = os.path.join(ROOT_DIR, "venv/lib/python3.12/site-packages")
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

import asyncio
import time
import aiohttp
import math
from datetime import datetime
from agents.base import BaseAgent
from simulation.exchange_sim import sim_exchange

class ContractTraderAgent(BaseAgent):
    def __init__(self):
        super().__init__("contract-trader")
        self.account_id = "B"
        self.symbol = "BTCUSDT"
        self.leverage = 5
        self.position_ratio = 0.15
        self.last_trade = 0
        self.binance_fapi_url = "https://fapi.binance.com"
        self._session = None
        
        # Strategy Parameters
        self.volatility_threshold = 2.2
        self.rsi_period = 14
        self.atr_period = 14
        self.atr_sl_mult = 2.0
        self.atr_tp_mult = 4.0

    async def _on_start(self):
        self._session = aiohttp.ClientSession()
        self.logger.info("agent_started", agent=self.name)
        asyncio.create_task(self._strategy_loop())

    async def stop(self):
        self.running = False
        if self._session:
            await self._session.close()
        await super().stop()

    def _calculate_ema(self, data, period):
        if len(data) < period:
            return data[-1]
        alpha = 2 / (period + 1)
        ema = data[0]
        for price in data[1:]:
            ema = alpha * price + (1 - alpha) * ema
        return ema

    def _calculate_rsi(self, closes, period=14):
        if len(closes) < period + 1:
            return 50
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calculate_atr(self, highs, lows, closes, period=14):
        if len(closes) < period + 1:
            return 0
        tr_list = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        return sum(tr_list[-period:]) / period

    async def _get_market_indicators(self):
        """Fetch data and calculate technical indicators"""
        try:
            url = f"{self.binance_fapi_url}/fapi/v1/klines?symbol={self.symbol}&interval=1h&limit=100"
            async with self._session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    return None
                klines = await resp.json()
                
            closes = [float(k[4]) for k in klines]
            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            current_price = closes[-1]

            ema20 = self._calculate_ema(closes, 20)
            ema50 = self._calculate_ema(closes, 50)
            
            trend = "neutral"
            if ema20 > ema50 and current_price > ema20:
                trend = "bullish"
            elif ema20 < ema50 and current_price < ema20:
                trend = "bearish"

            rsi = self._calculate_rsi(closes, self.rsi_period)
            vol_highs = highs[-24:]
            vol_lows = lows[-24:]
            volatilities = [(h - l) / l * 100 for h, l in zip(vol_highs, vol_lows)]
            avg_volatility = sum(volatilities) / len(volatilities)
            atr = self._calculate_atr(highs, lows, closes, self.atr_period)

            return {
                "price": current_price,
                "trend": trend,
                "rsi": rsi,
                "volatility": avg_volatility,
                "atr": atr
            }
        except Exception as e:
            self.logger.error(f"Error fetching indicators: {e}")
            return None

    async def _strategy_loop(self):
        self.logger.info("strategy_loop_started")
        while self.running:
            await asyncio.sleep(45)
            
            data = await self._get_market_indicators()
            if not data:
                continue

            price = data["price"]
            trend = data["trend"]
            rsi = data["rsi"]
            vol = data["volatility"]
            atr = data["atr"]

            if time.time() - self.last_trade < 300:
                continue

            balance = await sim_exchange.fetch_balance(self.account_id)
            if balance["daily_pnl"] / 50000 < -0.03:
                await self._close_position("daily_stop_loss")
                continue

            pos = sim_exchange.accounts[self.account_id].position
            
            if not pos:
                if vol > self.volatility_threshold:
                    continue

                if trend == "bullish" and rsi < 40:
                    sl = price - (self.atr_sl_mult * atr)
                    tp = price + (self.atr_tp_mult * atr)
                    await self._trade("buy", balance["total"], price, tp, sl)
                
                elif trend == "bearish" and rsi > 60:
                    sl = price + (self.atr_sl_mult * atr)
                    tp = price - (self.atr_tp_mult * atr)
                    await self._trade("sell", balance["total"], price, tp, sl)
            
            else:
                side = pos.side
                entry = pos.entry_price
                if side == "buy":
                    curr_sl = entry - (self.atr_sl_mult * atr)
                    curr_tp = entry + (self.atr_tp_mult * atr)
                    if price >= curr_tp or price <= curr_sl:
                        await self._close_position(f"exit_{'tp' if price >= curr_tp else 'sl'}")
                else:
                    curr_sl = entry + (self.atr_sl_mult * atr)
                    curr_tp = entry - (self.atr_tp_mult * atr)
                    if price <= curr_tp or price >= curr_sl:
                        await self._close_position(f"exit_{'tp' if price <= curr_tp else 'sl'}")

    async def _trade(self, side: str, balance: float, price: float, tp: float, sl: float):
        amount = balance * self.position_ratio * self.leverage
        result = await sim_exchange.create_order(self.account_id, self.symbol, side, amount)
        if result["success"]:
            self.last_trade = time.time()
            self.logger.info("entry_opened", side=side, price=price, tp=tp, sl=sl, vol=self.volatility_threshold)

    async def _close_position(self, reason: str):
        if sim_exchange.accounts[self.account_id].position:
            await sim_exchange.close_position(self.account_id, self.symbol)
            self.logger.info("position_closed", reason=reason)

async def main():
    agent = ContractTraderAgent()
    try:
        await agent.start()
        while agent.running:
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await agent.stop()

if __name__ == "__main__":
    import sys
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
