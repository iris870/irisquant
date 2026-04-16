import sys
import os
ROOT_DIR = "/root/irisquant"
sys.path.insert(0, ROOT_DIR)

import asyncio
import aiohttp
from datetime import datetime

class MeanReversionBacktest:
    def __init__(self):
        self.balance = 50000
        self.binance_fapi_url = "https://fapi.binance.com"

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

    async def fetch_historical_data(self, interval, limit=5000):
        all_klines = []
        current_end = None
        while len(all_klines) < limit:
            url = f"{self.binance_fapi_url}/fapi/v1/klines?symbol=BTCUSDT&interval={interval}&limit=1000"
            if current_end:
                url += f"&endTime={current_end}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        break
                    klines = await resp.json()
                    if not klines:
                        break
                    all_klines = klines + all_klines
                    current_end = klines[0][0] - 1
        return all_klines[-limit:] if len(all_klines) > limit else all_klines

    def backtest(self, klines_4h):
        margin = 5000
        leverage = 3
        position_size = margin * leverage

        # 最优参数
        pwl_lookback = 42           # 42根4小时K线 = 7天
        break_buffer = 0.008        # 0.8%
        adx_threshold = 35          # ADX < 35
        take_profit_ratio = 0.97    # 止盈 = 前周中点 × 0.97
        stop_loss_atr_mult = 1.3    # 止损 = 1.3倍 ATR
        atr_period = 14

        trades = []
        position = None
        entry_price = 0
        entry_time = None
        entry_side = None
        entry_pwl = 0
        entry_pwh = 0
        entry_atr = 0
        last_entry_pwl = None       # 防止同一PWL重复开仓
        last_entry_pwh = None

        print("开始回测均值回归策略（4小时K线）...\n")
        print(f"参数: break_buffer={break_buffer*100:.1f}%, adx_threshold={adx_threshold}")
        print(f"止盈比例={take_profit_ratio*100:.0f}%, 止损倍数={stop_loss_atr_mult}\n")

        for i in range(pwl_lookback + 50, len(klines_4h)):
            # 取前一周K线（排除当前周）
            week_klines = klines_4h[i - pwl_lookback - 4:i - 4]
            if len(week_klines) < pwl_lookback:
                continue

            lows = [float(k[3]) for k in week_klines]
            highs = [float(k[2]) for k in week_klines]
            pwl = min(lows)
            pwh = max(highs)

            # 当前4小时K线
            current = klines_4h[i]
            current_high = float(current[2])
            current_low = float(current[3])
            current_close = float(current[4])
            current_time = datetime.fromtimestamp(current[0] / 1000)

            # 计算指标
            closes = [float(k[4]) for k in klines_4h[i-100:i+1]]
            high_list = [float(k[2]) for k in klines_4h[i-100:i+1]]
            low_list = [float(k[3]) for k in klines_4h[i-100:i+1]]
            atr = self.calculate_atr(high_list, low_list, closes, atr_period)
            adx = self.calculate_adx(high_list, low_list, closes, atr_period)

            adx_ok = adx < adx_threshold

            # 信号检测：收盘价回归
            buy_signal = (current_close > pwl)
            sell_signal = (current_close < pwh)

            # 开仓（防止同一PWL/PWH重复开仓）
            if position is None and adx_ok:
                if buy_signal and last_entry_pwl != pwl:
                    position = "long"
                    entry_price = pwl
                    entry_time = current_time
                    entry_side = "long"
                    entry_pwl = pwl
                    entry_pwh = pwh
                    entry_atr = atr
                    last_entry_pwl = pwl
                    print(f"开多仓: {current_time} @ {entry_price:.0f}, PWL={pwl:.0f}, PWH={pwh:.0f}, ATR={atr:.0f}, ADX={adx:.1f}")

                elif sell_signal and last_entry_pwh != pwh:
                    position = "short"
                    entry_price = pwh
                    entry_time = current_time
                    entry_side = "short"
                    entry_pwl = pwl
                    entry_pwh = pwh
                    entry_atr = atr
                    last_entry_pwh = pwh
                    print(f"开空仓: {current_time} @ {entry_price:.0f}, PWL={pwl:.0f}, PWH={pwh:.0f}, ATR={atr:.0f}, ADX={adx:.1f}")

            # 持仓管理
            elif position is not None:
                current_price = current_close
                profit_pct = (current_price - entry_price) / entry_price if position == "long" else (entry_price - current_price) / entry_price
                should_close = False
                reason = ""

                if position == "long":
                    stop_price = entry_pwl - entry_atr * stop_loss_atr_mult
                    take_profit = (entry_pwl + entry_pwh) / 2 * take_profit_ratio

                    if current_price <= stop_price:
                        should_close = True
                        reason = "止损"
                    elif current_price >= take_profit:
                        should_close = True
                        reason = "止盈"

                else:
                    stop_price = entry_pwh + entry_atr * stop_loss_atr_mult
                    take_profit = (entry_pwl + entry_pwh) / 2 * take_profit_ratio

                    if current_price >= stop_price:
                        should_close = True
                        reason = "止损"
                    elif current_price <= take_profit:
                        should_close = True
                        reason = "止盈"

                if should_close:
                    pnl = profit_pct * position_size
                    trades.append({
                        "entry_time": entry_time,
                        "exit_time": current_time,
                        "side": position,
                        "entry": entry_price,
                        "exit": current_price,
                        "pnl": pnl,
                        "profit_pct": profit_pct,
                        "reason": reason
                    })
                    print(f"平{position}仓: {current_time} @ {current_price:.0f}, PNL={pnl:.0f}, {reason} (盈亏={profit_pct:.2%})")
                    position = None

        print("\n" + "="*50)
        print("均值回归策略回测结果（4小时K线）")
        print("="*50)
        print(f"总交易次数: {len(trades)}")
        if trades:
            win = sum(1 for t in trades if t["pnl"] > 0)
            loss = sum(1 for t in trades if t["pnl"] <= 0)
            total_pnl = sum(t["pnl"] for t in trades)
            print(f"盈利: {win}, 亏损: {loss}")
            print(f"胜率: {win/len(trades)*100:.1f}%")
            print(f"总盈亏: {total_pnl:.0f} USDT")
            print(f"平均每单: {total_pnl/len(trades):.0f} USDT")

async def main():
    engine = MeanReversionBacktest()
    print("获取4小时数据...")
    klines = await engine.fetch_historical_data("4h", 5000)
    print(f"获取到 {len(klines)} 根4小时K线")
    engine.backtest(klines)

if __name__ == "__main__":
    asyncio.run(main())
