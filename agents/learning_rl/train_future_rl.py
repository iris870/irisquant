import sqlite3
import pandas as pd
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from future_env import BTCFutureEnv
import os

# 1. Load Data
db_path = "/root/irisquant/data/knowledge.db"
conn = sqlite3.connect(db_path)
df = pd.read_sql_query("SELECT * FROM btc_1h ORDER BY timestamp ASC", conn)
conn.close()

# 2. Add Basic Indicators
# RSI
def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

df['rsi'] = calculate_rsi(df['close'])
# MACD
exp1 = df['close'].ewm(span=12, adjust=False).mean()
exp2 = df['close'].ewm(span=26, adjust=False).mean()
df['macd'] = exp1 - exp2
# BB Width
df['bb_width'] = (df['close'].rolling(window=20).std() * 4) / df['close'].rolling(window=20).mean()

df.fillna(0, inplace=True)

# 3. Environment & Model Init
env = BTCFutureEnv(df, initial_balance=10000, leverage=3.0)
checkpoint_callback = CheckpointCallback(
  save_freq=100000,
  save_path="/root/irisquant/models/checkpoints_future/",
  name_prefix="rl_btc_future"
)

# Network Architecture
policy_kwargs = dict(net_arch=dict(pi=[256, 256, 256], vf=[256, 256, 256]))

model = PPO(
    "MlpPolicy", 
    env, 
    verbose=1, 
    learning_rate=0.0003, 
    n_steps=4096,
    batch_size=256,
    gamma=0.99, # Long-term reward for futures
    ent_coef=0.02, # High exploration for 5 actions
    policy_kwargs=policy_kwargs
)

# 4. Training
print("Starting RL BTC Future Training (500k steps)...")
model.learn(total_timesteps=500000, callback=checkpoint_callback)

# 5. Save Final Model
model_dir = "/root/irisquant/models/"
os.makedirs(model_dir, exist_ok=True)
model.save(os.path.join(model_dir, "rl_btc_future.zip"))

# 6. Evaluate and Export Signals
print("Training Complete. Exporting Signals...")
obs, _ = env.reset()
signals = []
done = False

while not done:
    action, _states = model.predict(obs, deterministic=True)
    # Extract Confidence (Action Probabilities)
    import torch
    obs_tensor = torch.tensor(obs).unsqueeze(0).to(model.device)
    with torch.no_grad():
        dist = model.policy.get_distribution(obs_tensor)
        probs = dist.distribution.probs[0].cpu().numpy()
        confidence = probs[action]
        
    next_obs, reward, done, truncated, info = env.step(action)
    
    signals.append({
        "timestamp": df.iloc[env.current_step]['timestamp'],
        "action": action,
        "confidence": confidence,
        "price": df.iloc[env.current_step]['close'],
        "position": env.position,
        "equity": info['equity']
    })
    obs = next_obs

# Save Signals
output_dir = "/root/irisquant/outputs/"
os.makedirs(output_dir, exist_ok=True)
pd.DataFrame(signals).to_csv(os.path.join(output_dir, "rl_future_signals.csv"), index=False)
print(f"Signals exported to {output_dir}rl_future_signals.csv")
