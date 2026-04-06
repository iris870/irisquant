import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands

class BTCCoinpoundEnv(gym.Env):
    def __init__(self, df, initial_balance=10000, trade_ratio=0.25):
        super(BTCCoinpoundEnv, self).__init__()
        self.df = df.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.trade_ratio = trade_ratio
        
        # Action space: 0=Hold, 1=Buy x%, 2=Sell x%
        self.action_space = spaces.Discrete(3)
        
        # Observation space: 50 Klines + Indicators + Position + Returns
        # (Simplified for first iteration: RSI, MACD, BB, Pos, Returns)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(50 * 5 + 5,), dtype=np.float32
        )
        
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 50
        self.balance = self.initial_balance
        self.shares = 0
        self.cumulative_return = 0
        self.position_ratio = 0
        self.max_drawdown = 0
        self.peak_balance = self.initial_balance
        self.prev_step_return = 0
        
        return self._get_observation(), {}

    def _get_observation(self):
        # Slice last 50 OHLCV
        # Normalize OHLCV by dividing by first price in window
        window = self.df.iloc[self.current_step-50:self.current_step].copy()
        first_price = window.iloc[0]['close']
        
        # Avoid zero price division
        if first_price == 0: first_price = 1.0
        
        # Scaling and clipping to prevent NaN
        ohlcv = (window[['open', 'high', 'low', 'close', 'volume']].values / [first_price, first_price, first_price, first_price, max(1.0, window.iloc[0]['volume'])]).flatten()
        ohlcv = np.clip(ohlcv, 0.1, 10.0) # Clip range
        
        # Indicators at current step
        indicators = np.array([
            np.clip(self.df.at[self.current_step, 'rsi'] / 100.0, 0, 1),
            np.clip(self.df.at[self.current_step, 'macd'] / 10.0, -5, 5), # Smaller scaling
            np.clip(self.df.at[self.current_step, 'bb_width'], 0, 1),
            self.position_ratio,
            np.clip(self.cumulative_return, -1, 10)
        ])
        
        return np.concatenate([ohlcv, indicators]).astype(np.float32)

    def step(self, action):
        current_price = self.df.at[self.current_step, 'close']
        prev_total_value = self.balance + self.shares * current_price
        
        # Execute Action (Signal Only Logic)
        if action == 1:  # Buy 25% of balance
            buy_amount = self.balance * self.trade_ratio
            self.shares += buy_amount / current_price
            self.balance -= buy_amount
        elif action == 2:  # Sell 25% of holdings
            sell_shares = self.shares * self.trade_ratio
            self.balance += sell_shares * current_price
            self.shares -= sell_shares
            
        self.current_step += 1
        done = self.current_step >= len(self.df) - 1
        
        # Metrics
        new_price = self.df.at[self.current_step, 'close']
        total_value = self.balance + self.shares * new_price
        self.cumulative_return = (total_value - self.initial_balance) / self.initial_balance
        self.position_ratio = (self.shares * new_price) / total_value if total_value > 0 else 0
        
        # Step return calculation
        step_return = (total_value - prev_total_value) / prev_total_value if prev_total_value > 0 else 0
        
        # 1. Using Log Returns for reward stability
        # Log return is safer for RL than raw percentage
        log_return = np.log(total_value / prev_total_value) if prev_total_value > 0 and total_value > 0 else 0
        reward = log_return * 10.0 # Moderate scaling
        
        # 2. Holding friction (Very Low)
        if self.position_ratio > 0:
            reward -= 0.0001 
        
        # 3. Trend Bonus (Reduced to prevent dominance)
        if step_return > 0 and self.prev_step_return > 0:
            reward += 0.005 
            
        self.prev_step_return = step_return
        
        # Drawdown Penalty (Exponential to prevent blowup)
        if total_value > self.peak_balance:
            self.peak_balance = total_value
        drawdown = (self.peak_balance - total_value) / self.peak_balance
        self.max_drawdown = max(self.max_drawdown, drawdown)
        
        if drawdown > 0.10: 
            reward -= (drawdown * 2.0) # Scaled penalty
            
        return self._get_observation(), reward, done, False, {
            'total_value': total_value,
            'price': new_price,
            'pos': self.position_ratio,
            'cum_return': self.cumulative_return
        }
