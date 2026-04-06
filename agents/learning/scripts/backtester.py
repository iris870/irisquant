import sqlite3
import pandas as pd
import pandas_ta as ta
import numpy as np
import argparse
import json
import os
from datetime import datetime

class IrisBacktester:
    def __init__(self, db_path="/root/irisquant/data/knowledge.db"):
        self.db_path = db_path
        self.initial_capital = 10000.0
        
    def load_data(self, table="btc_1h", limit=None):
        query = f"SELECT * FROM {table} ORDER BY timestamp ASC"
        if limit:
            query += f" LIMIT {limit}"
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('datetime', inplace=True)
        return df

    def add_indicators(self, df, rsi_period=14, sma_short=20, sma_long=50):
        df.ta.rsi(length=rsi_period, append=True)
        df.ta.sma(length=sma_short, append=True)
        df.ta.sma(length=sma_long, append=True)
        df.ta.macd(append=True)
        return df

    def run_strategy(self, df):
        capital = self.initial_capital
        position = 0.0
        trades = []
        equity_curve = [capital]
        
        sma_s_col = [c for c in df.columns if c.startswith('SMA_')][0]
        sma_l_col = [c for c in df.columns if c.startswith('SMA_')][1]
        
        for i in range(1, len(df)):
            price = df['close'].iloc[i]
            if df[sma_s_col].iloc[i-1] < df[sma_l_col].iloc[i-1] and df[sma_s_col].iloc[i] > df[sma_l_col].iloc[i] and position == 0:
                position = capital / price
                capital = 0
                trades.append({"type": "BUY", "price": price, "time": str(df.index[i])})
            elif df[sma_s_col].iloc[i-1] > df[sma_l_col].iloc[i-1] and df[sma_s_col].iloc[i] < df[sma_l_col].iloc[i] and position > 0:
                capital = position * price
                position = 0
                trades.append({"type": "SELL", "price": price, "time": str(df.index[i])})
            equity_curve.append(capital + (position * price))
        return capital + (position * df['close'].iloc[-1]), trades, equity_curve

    def calculate_metrics(self, final_value, equity_curve):
        returns = (final_value - self.initial_capital) / self.initial_capital
        eq = pd.Series(equity_curve)
        peak = eq.expanding().max()
        dd = (peak - eq) / peak
        max_dd = dd.max()
        daily_ret = eq.pct_change().dropna()
        sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if len(daily_ret) > 0 and daily_ret.std() != 0 else 0
        return {"total_return": round(float(returns * 100), 2), "max_drawdown": round(float(max_dd * 100), 2), "sharpe_ratio": round(float(sharpe), 2), "final_equity": round(float(final_value), 2)}

    def save_results(self, strategy_id, metrics, params):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS backtest_results (id INTEGER PRIMARY KEY AUTOINCREMENT, strategy_id TEXT, params TEXT, total_return REAL, max_drawdown REAL, sharpe_ratio REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute("INSERT INTO backtest_results (strategy_id, params, total_return, max_drawdown, sharpe_ratio) VALUES (?, ?, ?, ?, ?)", (strategy_id, json.dumps(params), metrics['total_return'], metrics['max_drawdown'], metrics['sharpe_ratio']))
        conn.commit()
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", default="btc_1h")
    args = parser.parse_args()
    tester = IrisBacktester()
    data = tester.load_data(table=args.table)
    data = tester.add_indicators(data)
    final_val, trades, equity = tester.run_strategy(data)
    perf = tester.calculate_metrics(final_val, equity)
    tester.save_results("sma_cross", {"table": args.table}, perf)
    print(f"RESULT|{args.table}|{perf['total_return']}|{perf['max_drawdown']}|{perf['sharpe_ratio']}|{len(trades)}")
