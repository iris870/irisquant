import pandas as pd
import sqlite3
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands
from stable_baselines3 import PPO
from rl_env import BTCCoinpoundEnv
import os

# 1. Data Loading (Extract 1h BTC Data from knowledge.db)
db_path = '/root/irisquant/data/knowledge.db'
conn = sqlite3.connect(db_path)
query = "SELECT timestamp, open, high, low, close, volume FROM btc_1h ORDER BY timestamp ASC"
df = pd.read_sql_query(query, conn)
conn.close()

# 2. Indicator Calculation
df['rsi'] = RSIIndicator(close=df['close'], window=14).rsi()
df['macd'] = MACD(close=df['close']).macd()
bb = BollingerBands(close=df['close'], window=20, window_dev=2)
df['bb_width'] = bb.bollinger_wband()
df = df.dropna().reset_index(drop=True)

from stable_baselines3.common.callbacks import CheckpointCallback

# ... (prior code)

# 3. Environment & Model Init
env = BTCCoinpoundEnv(df)
checkpoint_callback = CheckpointCallback(
  save_freq=100000,
  save_path="/root/irisquant/models/checkpoints/",
  name_prefix="rl_btc_compound"
)

# Optimized for 1h BTC compounding
policy_kwargs = dict(net_arch=dict(pi=[256, 256], vf=[256, 256]))

model = PPO(
    "MlpPolicy", 
    env, 
    verbose=1, 
    learning_rate=0.0005, 
    n_steps=4096,
    batch_size=256,
    gamma=0.98,
    ent_coef=0.01,
    policy_kwargs=policy_kwargs
)

# 4. Training (500k steps)
print("Starting High-Performance RL Training (500k steps)...")
model.learn(total_timesteps=500000, callback=checkpoint_callback)

# 5. Save Model
os.makedirs('/root/irisquant/models/', exist_ok=True)
model.save("/root/irisquant/models/rl_btc_spot_compound")
print("Model Saved: /root/irisquant/models/rl_btc_spot_compound.zip")

# 6. Evaluation & Signal Output
os.makedirs('/root/irisquant/outputs/', exist_ok=True)
obs, _ = env.reset()
signals = []
benchmark_start = df.at[50, 'close']

for i in range(50, len(df)-1):
    action, _states = model.predict(obs, deterministic=True)
    obs, reward, done, truncated, info = env.step(action)
    
    current_price = info['price']
    benchmark_return = (current_price - benchmark_start) / benchmark_start
    
    signals.append({
        'timestamp': df.at[i, 'timestamp'],
        'signal': int(action),
        'confidence': 1.0,  # Placeholder
        'price': current_price,
        'position_ratio': info['pos'],
        'cumulative_return': info['cum_return'],
        'benchmark_return': benchmark_return
    })
    if done:
        break

# Save CSV
signals_df = pd.DataFrame(signals)
signals_df.to_csv('/root/irisquant/outputs/rl_compound_signals.csv', index=False)
print(f"Signals Saved: /root/irisquant/outputs/rl_compound_signals.csv ({len(signals_df)} entries)")

# 7. Final Report
total_ret = signals_df['cumulative_return'].iloc[-1]
bench_ret = signals_df['benchmark_return'].iloc[-1]
max_dd = env.max_drawdown
print("-" * 20)
print("Evaluation Report")
print("-" * 20)
print(f"Total Compound Return: {total_ret:.2%}")
print(f"Benchmark (Buy & Hold): {bench_ret:.2%}")
print(f"Max Drawdown: {max_dd:.2%}")
print(f"Signal Generation Complete.")
