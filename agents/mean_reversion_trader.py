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
from datetime import datetime
from agents.base import BaseAgent
from simulation.exchange_sim import sim_exchange


class MeanReversionTrader(BaseAgent):
    def __init__(self):
        super().__init__("mean-reversion")
        self.account_id = "B"
        self.symbol = "BTCUSDT"

        # ========== 仓位参数 ==========
        self.margin = 5000
        self.leverage = 3
        self.position_size = self.margin * self.leverage

        self.binance_fapi_url = "https://fapi.binance.com"
        self._session = None

        # ========== 策略参数（最优参数） ==========
        self.pwl_lookback = 42           # 42根4小时K线 = 7天
        self.break_buffer = 0.008        # 0.8%
        self.adx_threshold = 40          # ADX < 40
        self.take_profit_ratio = 0.98    # 止盈 = 前周中点 × 0.98
        self.stop_loss_atr_mult = 0.25   # 止损 = 0.25倍 ATR
        self.atr_period = 14

        # 状态跟踪
        self.last_entry_pwl = None
        self.last_entry_pwh = None
        self.entry_time = None
        self.highest_price = 0
        self.lowest_price = 0
        self.daily_pnl = 0.0
        self.last_reset_day = None

    async def _on_start(self):
        self._session = aiohttp.ClientSession()
        self.logger.info("均值回归策略启动")
        asyncio.create_task(self._strategy_loop())

    async def stop(self):
        self.running = False
        if self._session:
            await self._session.close()
        await super().stop()

    # ========== 技术指标 ==========
    def calculate_ema(self, data, period):
        if len(data) < period:
            return data[-1] if data else 0
        k = 2 / (period + 1)
        ema = data[0]
        for price in data[1:]:
            ema = price * k + ema * (1 - k)
        return ema

    def calculate_atr(self, highs, lows, closes, period=14):
        if len(closes) < period + 1:
            return 0
        tr_list = []
        for i in range(1, len(closes)):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            tr_list.append(tr)
        return sum(tr_list[-period:]) / period

    def calculate_adx(self, highs, lows, closes, period=14):
        if len(closes) < period * 2:
            return 0
        plus_dm = []
        minus_dm = []
        tr_list = []
        for i in range(1, len(closes)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]
            if high_diff > low_diff and high_diff > 0:
                plus_dm.append(high_diff)
            else:
                plus_dm.append(0)
            if low_diff > high_diff and low_diff > 0:
                minus_dm.append(low_diff)
            else:
                minus_dm.append(0)
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            tr_list.append(tr)
        atr = sum(tr_list[-period:]) / period if tr_list else 1
        plus_di = 100 * (sum(plus_dm[-period:]) / period) / atr if atr > 0 else 0
        minus_di = 100 * (sum(minus_dm[-period:]) / period) / atr if atr > 0 else 0
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
        return dx

    # ========== 数据获取 ==========
    async def get_klines(self, interval, limit=200):
        try:
            url = f"{self.binance_fapi_url}/fapi/v1/klines?symbol={self.symbol}&interval={interval}&limit={limit}"
            async with self._session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            self.logger.error(f"获取K线失败: {e}")
        return None

    async def get_realtime_price(self):
        try:
            url = f"{self.binance_fapi_url}/fapi/v1/ticker/price?symbol={self.symbol}"
            async with self._session.get(url, timeout=3) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data["price"])
        except Exception as e:
            self.logger.error(f"获取价格失败: {e}")
        return None

    # ========== 日盈亏重置 ==========
    def check_daily_reset(self):
        current_day = datetime.now().date()
        if self.last_reset_day != current_day:
            self.daily_pnl = 0.0
            self.last_reset_day = current_day

    # ========== 策略主循环 ==========
    async def _strategy_loop(self):
        self.logger.info("均值回归策略循环启动")
        await asyncio.sleep(10)

        while self.running:
            await asyncio.sleep(3600)  # 每小时检查一次

            self.check_daily_reset()

            klines_4h = await self.get_klines("4h", 200)
            if not klines_4h or len(klines_4h) < self.pwl_lookback + 50:
                continue

            current_price = await self.get_realtime_price()
            if not current_price:
                continue

            # 取前一周K线（排除当前周）
            week_klines = klines_4h[-self.pwl_lookback - 4:-4]
            if len(week_klines) < self.pwl_lookback:
                continue

            lows = [float(k[3]) for k in week_klines]
            highs = [float(k[2]) for k in week_klines]
            pwl = min(lows)
            pwh = max(highs)

            # 当前4小时K线
            current = klines_4h[-1]
            current_close = float(current[4])
            current_time = datetime.fromtimestamp(current[0] / 1000)

            # 计算指标
            closes = [float(k[4]) for k in klines_4h[-100:]]
            high_list = [float(k[2]) for k in klines_4h[-100:]]
            low_list = [float(k[3]) for k in klines_4h[-100:]]
            atr = self.calculate_atr(high_list, low_list, closes, self.atr_period)
            adx = self.calculate_adx(high_list, low_list, closes, self.atr_period)

            adx_ok = adx < self.adx_threshold

            # 信号检测
            buy_signal = current_close > pwl
            sell_signal = current_close < pwh

            pos = sim_exchange.accounts[self.account_id].position

            # 开仓
            if pos is None and adx_ok:
                if buy_signal and self.last_entry_pwl != pwl:
                    result = await sim_exchange.create_order(
                        self.account_id, self.symbol, "buy", self.position_size
                    )
                    if result["success"]:
                        self.last_entry_pwl = pwl
                        self.entry_time = time.time()
                        self.logger.info(f"开多仓 @ {pwl:.0f}, PWL={pwl:.0f}, PWH={pwh:.0f}, ADX={adx:.1f}")

                elif sell_signal and self.last_entry_pwh != pwh:
                    result = await sim_exchange.create_order(
                        self.account_id, self.symbol, "sell", self.position_size
                    )
                    if result["success"]:
                        self.last_entry_pwh = pwh
                        self.entry_time = time.time()
                        self.logger.info(f"开空仓 @ {pwh:.0f}, PWL={pwl:.0f}, PWH={pwh:.0f}, ADX={adx:.1f}")

            # 持仓管理
            elif pos is not None:
                entry_price = pos.entry_price
                side = pos.side
                profit_pct = (current_price - entry_price) / entry_price if side == "long" else (entry_price - current_price) / entry_price

                should_close = False
                reason = ""

                if side == "long":
                    stop_price = pwl - atr * self.stop_loss_atr_mult
                    take_profit = (pwl + pwh) / 2 * self.take_profit_ratio

                    if current_price <= stop_price:
                        should_close = True
                        reason = f"止损"
                    elif current_price >= take_profit:
                        should_close = True
                        reason = f"止盈"

                else:
                    stop_price = pwh + atr * self.stop_loss_atr_mult
                    take_profit = (pwl + pwh) / 2 * self.take_profit_ratio

                    if current_price >= stop_price:
                        should_close = True
                        reason = f"止损"
                    elif current_price <= take_profit:
                        should_close = True
                        reason = f"止盈"

                if should_close:
                    result = await sim_exchange.close_position(self.account_id, self.symbol)
                    if result["success"]:
                        pnl = result.get("pnl", 0)
                        self.daily_pnl += pnl
                        self.logger.info(f"平仓成功, PNL={pnl:.2f}, {reason}")


async def main():
    agent = MeanReversionTrader()
    try:
        await agent.start()
        while agent.running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
