import pandas as pd
import numpy as np
import os
import sys
from typing import List, Dict, Tuple

sys.path.append('/root/irisquant')

def load_data(filepath: str):
    df = pd.read_csv(filepath)
    df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'q_volume', 'trades', 'taker_base', 'taker_quote', 'ignore']
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

class VectorBacktesterV46:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        
    def run_simulation(self, base_threshold: int, atr_period: int, adx_period: int, trend_window: int):
        df = self.df
        df['tr'] = np.maximum(df['high'] - df['low'], 
                             np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                      abs(df['low'] - df['close'].shift(1))))
        df['atr'] = df['tr'].rolling(window=atr_period).mean()
        df['price_change_pct'] = df['close'].pct_change(periods=adx_period) * 100
        df['trend_score'] = np.where(df['close'] > df['close'].shift(trend_window), 25, 0)
        df['tech_score'] = np.where(df['price_change_pct'] > 0.5, 25, 15)
        df['ob_score'] = 15 
        df['macro_score'] = 15
        df['total_score'] = df['trend_score'] + df['tech_score'] + df['ob_score'] + df['macro_score']
        df['vol_mult'] = np.where(df['atr'] / df['close'] > 0.01, 1.2, 1.0)
        df['final_threshold'] = (base_threshold * df['vol_mult']).astype(int)
        df['signal'] = (df['total_score'] >= df['final_threshold']).astype(int)
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = df['signal'].shift(1) * df['returns']
        cumulative_returns = (1 + df['strategy_returns'].fillna(0)).cumprod()
        total_return = cumulative_returns.iloc[-1] - 1
        sharpe = np.sqrt(288 * 365) * df['strategy_returns'].mean() / df['strategy_returns'].std() if df['strategy_returns'].std() != 0 else 0
        return total_return, sharpe

def optimize():
    data_path = "/root/irisquant/data/historical/btc_usdt_5m.csv"
    if not os.path.exists(data_path):
        print(f"Data not found: {data_path}")
        return
    df = load_data(data_path)
    backtester = VectorBacktesterV46(df)
    results = []
    thresholds = [55, 60, 65]
    atr_periods = [10, 14, 20]
    trend_windows = [10, 20, 50]
    for t in thresholds:
        for ap in atr_periods:
            for tw in trend_windows:
                ret, sharpe = backtester.run_simulation(t, ap, ap, tw)
                results.append({'threshold': t, 'atr_period': ap, 'trend_window': tw, 'return': ret, 'sharpe': sharpe})
    res_df = pd.DataFrame(results)
    best = res_df.sort_values(by='sharpe', ascending=False).iloc[0]
    print("
=== Optimization Results (5m) ===")
    print(best)
    print("================================
")
    res_df.to_csv("/root/irisquant/data/opt_results_5m.csv", index=False)
    print(f"Results saved to /root/irisquant/data/opt_results_5m.csv
")

if __name__ == "__main__":
    optimize()
