import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)
VENV_SITE = os.path.join(ROOT_DIR, "venv/lib/python3.12/site-packages")
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

import asyncio
import time
import aiohttp
from agents.base import BaseAgent
from simulation.exchange_sim import sim_exchange


class ContractTraderAgent(BaseAgent):
    def __init__(self):
        super().__init__("contract-trader")
        self.account_id = "B"
        self.symbol = "BTCUSDT"

        # ========== 仓位参数 ==========
        self.margin = 1000           # 保证金 10000 USDT
        self.leverage = 5             # 5 倍杠杆
        self.position_size = self.margin * self.leverage

        self.last_trade_time = 0
        self.binance_fapi_url = "https://fapi.binance.com"
        self._session = None

        # ========== 策略参数（最优参数） ==========
        self.rsi_period = 14
        self.rsi_bullish = 40
        self.rsi_bearish = 60
        self.trend_stop_pct = 0.005    # 趋势止损 0.5%
        self.signal_buffer_pct = 0.02  # 信号缓冲 2%
        self.profit_target = 0.03      # 止盈目标 3%
        self.trailing_stop_pct = 0.015 # 移动止盈回撤 1.5%
        self.fixed_stop_pct = 0.05     # 固定止损 5%

    async def _on_start(self):
        self._session = aiohttp.ClientSession()
        self.logger.info("agent_started")
        asyncio.create_task(self._strategy_loop())

    async def stop(self):
        self.running = False
        if self._session:
            await self._session.close()
        await super().stop()

    async def _get_realtime_price(self):
        try:
            url = f"{self.binance_fapi_url}/fapi/v1/ticker/price?symbol={self.symbol}"
            async with self._session.get(url, timeout=3) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data["price"])
        except Exception as e:
            self.logger.error(f"获取实时价格失败: {e}")
        return None

    def _calculate_ema(self, data, period):
        if len(data) < period:
            return data[-1] if data else 0
        alpha = 2 / (period + 1)
        ema = data[0]
        for price in data[1:]:
            ema = alpha * price + (1 - alpha) * ema
        return ema

    def _calculate_rsi(self, closes, period=14):
        if len(closes) < period + 1:
            return 50
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    async def _get_market_indicators(self):
        try:
            url = f"{self.binance_fapi_url}/fapi/v1/klines?symbol={self.symbol}&interval=1h&limit=100"
            async with self._session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    return None
                klines = await resp.json()

            closes = [float(k[4]) for k in klines]
            current_price = closes[-1]

            ema20 = self._calculate_ema(closes, 20)
            ema50 = self._calculate_ema(closes, 50)

            if ema20 > ema50 and current_price > ema20:
                trend = "bullish"
            elif ema20 < ema50 and current_price < ema20:
                trend = "bearish"
            else:
                trend = "neutral"

            rsi = self._calculate_rsi(closes, self.rsi_period)

            return {"price": current_price, "trend": trend, "rsi": rsi}
        except Exception as e:
            self.logger.error(f"获取指标失败: {e}")
            return None

    async def _get_trend_4h(self):
        try:
            url = f"{self.binance_fapi_url}/fapi/v1/klines?symbol={self.symbol}&interval=4h&limit=100"
            async with self._session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    return "neutral"
                klines = await resp.json()
            closes = [float(k[4]) for k in klines]
            current_price = closes[-1]
            ema20 = self._calculate_ema(closes, 20)
            ema50 = self._calculate_ema(closes, 50)
            if ema20 > ema50 and current_price > ema20:
                return "bullish"
            elif ema20 < ema50 and current_price < ema20:
                return "bearish"
            return "neutral"
        except Exception as e:
            self.logger.error(f"获取4小时趋势失败: {e}")
            return "neutral"

    async def _strategy_loop(self):
        self.logger.info("strategy_loop_started")
        while self.running:
            await asyncio.sleep(60)

            trend_4h = await self._get_trend_4h()
            data = await self._get_market_indicators()
            if not data:
                continue

            price = data["price"]
            rsi = data["rsi"]

            self.logger.info(f"市场: price={price:.0f}, trend_4h={trend_4h}, rsi={rsi:.1f}")

            pos = sim_exchange.accounts[self.account_id].position

            if pos is None:
                if trend_4h == "bullish" and rsi > self.rsi_bullish:
                    self.logger.info(f"开多仓: amount=${self.position_size:.0f}")
                    result = await sim_exchange.create_order(self.account_id, self.symbol, "buy", self.position_size)
                    if result["success"]:
                        self.last_trade_time = time.time()
                        self.logger.info(f"开仓成功: buy @ {price:.0f}")
                    else:
                        self.logger.info(f"开仓失败: {result}")

                elif trend_4h == "bearish" and rsi < self.rsi_bearish:
                    self.logger.info(f"开空仓: amount=${self.position_size:.0f}")
                    result = await sim_exchange.create_order(self.account_id, self.symbol, "sell", self.position_size)
                    if result["success"]:
                        self.last_trade_time = time.time()
                        self.logger.info(f"开仓成功: sell @ {price:.0f}")
                    else:
                        self.logger.info(f"开仓失败: {result}")

            else:
                entry = pos.entry_price
                side = pos.side
                current_price = await self._get_realtime_price()
                if not current_price:
                    continue

                if not hasattr(self, 'highest_price'):
                    self.highest_price = entry
                    self.lowest_price = entry

                if side == "long":
                    self.highest_price = max(self.highest_price, current_price)
                    drawdown = (self.highest_price - current_price) / self.highest_price
                    profit_pct = (current_price - entry) / entry

                    should_close = False
                    reason = ""

                    if drawdown >= self.trend_stop_pct:
                        should_close = True
                        reason = "趋势止损"
                    elif profit_pct >= self.profit_target:
                        trailing = (self.highest_price - current_price) / self.highest_price
                        if trailing >= self.trailing_stop_pct:
                            should_close = True
                            reason = "移动止盈"
                    elif profit_pct <= -self.fixed_stop_pct:
                        should_close = True
                        reason = "固定止损"

                    if not should_close:
                        buffer_price = entry * (1 - self.signal_buffer_pct)
                        if current_price <= buffer_price:
                            should_close = True
                            reason = "信号止损"

                else:
                    self.lowest_price = min(self.lowest_price, current_price)
                    drawup = (current_price - self.lowest_price) / self.lowest_price
                    profit_pct = (entry - current_price) / entry

                    should_close = False
                    reason = ""

                    if drawup >= self.trend_stop_pct:
                        should_close = True
                        reason = "趋势止损"
                    elif profit_pct >= self.profit_target:
                        trailing = (current_price - self.lowest_price) / self.lowest_price
                        if trailing >= self.trailing_stop_pct:
                            should_close = True
                            reason = "移动止盈"
                    elif profit_pct <= -self.fixed_stop_pct:
                        should_close = True
                        reason = "固定止损"

                    if not should_close:
                        buffer_price = entry * (1 + self.signal_buffer_pct)
                        if current_price >= buffer_price:
                            should_close = True
                            reason = "信号止损"

                if should_close:
                    result = await sim_exchange.close_position(self.account_id, self.symbol)
                    if result["success"]:
                        pnl = result.get("pnl", 0)
                        self.logger.info(f"平仓成功, pnl={pnl:.2f}, {reason}")
                        delattr(self, 'highest_price')
                        delattr(self, 'lowest_price')


async def main():
    agent = ContractTraderAgent()
    try:
        await agent.start()
        while agent.running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
