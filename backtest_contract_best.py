import sys
import os
ROOT_DIR = "/root/irisquant"
sys.path.insert(0, ROOT_DIR)

import asyncio
import aiohttp
from datetime import datetime

class BacktestEngine:
    def __init__(self):
        self.balance = 50000
        self.position = None
        self.trades = []
        self.binance_fapi_url = "https://fapi.binance.com"

    def calculate_ema(self, data, period):
        if len(data) < period:
            return data[-1] if data else 0
        alpha = 2 / (period + 1)
        ema = data[0]
        for price in data[1:]:
            ema = alpha * price + (1 - alpha) * ema
        return ema

    def calculate_rsi(self, closes, period=14):
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

    async def fetch_historical_data(self, interval, limit=20000):
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

    def backtest(self, klines_1h, klines_4h):
        closes_1h = [float(k[4]) for k in klines_1h]
        highs_1h = [float(k[2]) for k in klines_1h]
        lows_1h = [float(k[3]) for k in klines_1h]
        timestamps = [datetime.fromtimestamp(k[0] / 1000) for k in klines_1h]

        margin = 10000
        leverage = 5
        position_size = margin * leverage

        position = None
        balance = 50000
        trades = []
        entry_time = None
        highest_price = 0
        lowest_price = 0

        closes_4h = [float(k[4]) for k in klines_4h]
        trend_4h = []
        for i in range(len(closes_4h)):
            if i < 50:
                trend_4h.append("neutral")
                continue
            current_closes = closes_4h[:i+1]
            price = current_closes[-1]
            ema20 = self.calculate_ema(current_closes, 20)
            ema50 = self.calculate_ema(current_closes, 50)
            if ema20 > ema50 and price > ema20:
                trend_4h.append("bullish")
            elif ema20 < ema50 and price < ema20:
                trend_4h.append("bearish")
            else:
                trend_4h.append("neutral")

        for i in range(100, len(closes_1h)):
            current_closes = closes_1h[:i+1]
            price = closes_1h[i]
            timestamp = timestamps[i]

            idx_4h = i // 4
            if idx_4h >= len(trend_4h):
                idx_4h = len(trend_4h) - 1
            trend_4h_current = trend_4h[idx_4h] if idx_4h >= 0 else "neutral"

            rsi = self.calculate_rsi(current_closes, 14)

            if position is None:
                if trend_4h_current == "bullish" and rsi > 40:
                    position = {"side": "long", "entry": price, "time": timestamp}
                    entry_time = timestamp
                    highest_price = price
                    lowest_price = price
                    print(f"开多仓: {timestamp} @ {price:.0f}")

                elif trend_4h_current == "bearish" and rsi < 60:
                    position = {"side": "short", "entry": price, "time": timestamp}
                    entry_time = timestamp
                    highest_price = price
                    lowest_price = price
                    print(f"开空仓: {timestamp} @ {price:.0f}")

            elif position is not None:
                should_close = False
                reason = ""

                if position["side"] == "long":
                    highest_price = max(highest_price, price)
                    drawdown = (highest_price - price) / highest_price
                    profit_pct = (price - position["entry"]) / position["entry"]

                    if drawdown >= 0.005:
                        should_close = True
                        reason = "趋势止损"
                    elif profit_pct >= 0.03:
                        trailing_drawdown = (highest_price - price) / highest_price
                        if trailing_drawdown >= 0.015:
                            should_close = True
                            reason = "移动止盈"
                    elif profit_pct <= -0.05:
                        should_close = True
                        reason = "固定止损"

                    if not should_close:
                        signal_price = position["entry"]
                        buffer_price = signal_price * 0.98
                        if price <= buffer_price:
                            should_close = True
                            reason = "信号止损+2%缓冲"

                else:
                    lowest_price = min(lowest_price, price)
                    drawup = (price - lowest_price) / lowest_price
                    profit_pct = (position["entry"] - price) / position["entry"]

                    if drawup >= 0.005:
                        should_close = True
                        reason = "趋势止损"
                    elif profit_pct >= 0.03:
                        trailing_drawup = (price - lowest_price) / lowest_price
                        if trailing_drawup >= 0.015:
                            should_close = True
                            reason = "移动止盈"
                    elif profit_pct <= -0.05:
                        should_close = True
                        reason = "固定止损"

                    if not should_close:
                        signal_price = position["entry"]
                        buffer_price = signal_price * 1.02
                        if price >= buffer_price:
                            should_close = True
                            reason = "信号止损+2%缓冲"

                if should_close:
                    if position["side"] == "long":
                        pnl = (price - position["entry"]) / position["entry"] * position_size
                    else:
                        pnl = (position["entry"] - price) / position["entry"] * position_size

                    balance += pnl
                    trades.append({
                        "entry_time": entry_time.strftime("%Y-%m-%d %H:%M"),
                        "exit_time": timestamp.strftime("%Y-%m-%d %H:%M"),
                        "side": position["side"],
                        "entry": position["entry"],
                        "exit": price,
                        "pnl": pnl,
                        "reason": reason
                    })
                    print(f"平仓: {timestamp} @ {price:.0f}, PNL={pnl:.0f}, {reason}")
                    position = None

        return trades, balance

async def main():
    engine = BacktestEngine()
    print("获取1小时数据...")
    klines_1h = await engine.fetch_historical_data("1h", 20000)
    print(f"获取到 {len(klines_1h)} 根1小时K线")
    print("获取4小时数据...")
    klines_4h = await engine.fetch_historical_data("4h", 5000)
    print(f"获取到 {len(klines_4h)} 根4小时K线")
    print("开始回测...\n")
    trades, final_balance = engine.backtest(klines_1h, klines_4h)

    print("\n" + "="*50)
    print("回测结果")
    print("="*50)
    print(f"总交易次数: {len(trades)}")
    if trades:
        total_pnl = sum(t["pnl"] for t in trades)
        win_trades = [t for t in trades if t["pnl"] > 0]
        loss_trades = [t for t in trades if t["pnl"] <= 0]
        print(f"盈利次数: {len(win_trades)}")
        print(f"亏损次数: {len(loss_trades)}")
        print(f"胜率: {len(win_trades)/len(trades)*100:.1f}%")
        print(f"总盈亏: {total_pnl:.0f} USDT")
        print(f"初始余额: 50000 USDT")
        print(f"最终余额: {final_balance:.0f} USDT")
        print(f"收益率: {(final_balance-50000)/50000*100:.1f}%")

        print("\n交易明细(最近20笔):")
        for t in trades[-20:]:
            print(f"  {t['entry_time']} {t['side']} @{t['entry']:.0f} -> {t['exit_time']} @{t['exit']:.0f} PNL={t['pnl']:.0f} {t['reason']}")
    else:
        print("无交易记录")

if __name__ == "__main__":
    asyncio.run(main())
