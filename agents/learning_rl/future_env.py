import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

class BTCFutureEnv(gym.Env):
    def __init__(self, df, initial_balance=10000, leverage=3.0):
        super(BTCFutureEnv, self).__init__()
        self.df = df.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.leverage = leverage
        
        # Action space: 0=Hold, 1=Open Long, 2=Open Short, 3=Close Long, 4=Close Short
        self.action_space = spaces.Discrete(5)
        
        # Obs space: 50 * 5 (OHLCV) + 5 (Indicators/State)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(50 * 5 + 5,), dtype=np.float32
        )
        
        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.position = 0 # -1=Short, 0=None, 1=Long
        self.entry_price = 0
        self.current_step = 50
        self.max_equity = self.initial_balance
        self.trades = []
        self.cumulative_reward = 0
        
        return self._get_observation(), {}

    def _get_observation(self):
        window = self.df.iloc[self.current_step-50:self.current_step].copy()
        first_price = window.iloc[0]['close']
        if first_price == 0: first_price = 1.0
        
        ohlcv = (window[['open', 'high', 'low', 'close', 'volume']].values / 
                 [first_price, first_price, first_price, first_price, max(1.0, window.iloc[0]['volume'])]).flatten()
        ohlcv = np.clip(ohlcv, 0.1, 10.0)
        
        # State indicators
        current_price = self.df.at[self.current_step, 'close']
        unrealized_pnl = 0
        if self.position != 0:
            unrealized_pnl = (current_price - self.entry_price) / self.entry_price * self.position * self.leverage
            
        indicators = np.array([
            np.clip(self.df.at[self.current_step, 'rsi'] / 100.0, 0, 1),
            np.clip(self.df.at[self.current_step, 'macd'] / 10.0, -5, 5),
            self.position,
            np.clip(unrealized_pnl, -1, 1),
            np.clip(self.equity / self.initial_balance, 0, 10)
        ])
        
        return np.concatenate([ohlcv, indicators]).astype(np.float32)

    def step(self, action):
        current_price = self.df.at[self.current_step, 'close']
        reward = 0
        done = False
        truncated = False
        
        prev_equity = self.equity
        
        # 1. Update Equity (Unrealized)
        if self.position != 0:
            pnl_pct = (current_price - self.entry_price) / self.entry_price * self.position * self.leverage
            self.equity = self.balance * (1 + pnl_pct)
            
            # Auto-Stop Loss (5%)
            if pnl_pct <= -0.05:
                action = 3 if self.position == 1 else 4
                reward -= 1.0 # Penalty for hitting SL
            
            # Liquidation check (90% loss)
            if self.equity <= self.initial_balance * 0.1:
                reward -= 10.0
                done = True

        # 2. Execute Action
        # Action space: 0=Hold, 1=Open Long, 2=Open Short, 3=Close Long, 4=Close Short
        if action == 1 and self.position == 0: # Open Long
            self.position = 1
            self.entry_price = current_price
        elif action == 2 and self.position == 0: # Open Short
            self.position = -1
            self.entry_price = current_price
        elif action == 3 and self.position == 1: # Close Long
            realized_pnl = (current_price - self.entry_price) / self.entry_price * self.leverage
            self.balance *= (1 + realized_pnl)
            self.equity = self.balance
            reward += realized_pnl * 100.0 # Reward based on realized PnL
            self.position = 0
            self.entry_price = 0
        elif action == 4 and self.position == -1: # Close Short
            realized_pnl = (self.entry_price - current_price) / self.entry_price * self.leverage
            self.balance *= (1 + realized_pnl)
            self.equity = self.balance
            reward += realized_pnl * 100.0
            self.position = 0
            self.entry_price = 0

        # 3. Intermediate Reward (PnL Change)
        if not done:
            equity_change = (self.equity - prev_equity) / prev_equity
            reward += equity_change * 10.0
            
        # 4. Advance
        self.current_step += 1
        if self.current_step >= len(self.df) - 1:
            done = True
            
        self.max_equity = max(self.max_equity, self.equity)
        
        return self._get_observation(), reward, done, truncated, {"equity": self.equity}
