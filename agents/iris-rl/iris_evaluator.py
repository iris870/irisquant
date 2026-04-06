import os
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from datetime import datetime

# Paths
SIGNAL_FILE = "/root/irisquant/outputs/ops_signals.csv"
MODEL_FILE = "/root/irisquant/models/iris_rl_ops.pth"
VENV_PYTHON = "/root/irisquant/venv/bin/python3"

# Actions Mapping (Must match signal_gen.py)
ACTIONS = {
    0: "NO_OP",
    1: "RESTART_WEB",
    2: "RESTART_BTC_ROLLING",
    3: "CLEAN_PORTS",
    4: "RESTART_GATEWAY"
}

def execute_action(action_name):
    """Execute the system command for the given action name."""
    print(f"Executing action: {action_name}")
    try:
        if action_name == "RESTART_WEB":
            os.system("systemctl restart nginx")
        elif action_name == "RESTART_BTC_ROLLING":
            os.system("pm2 restart btc-rolling")
        elif action_name == "CLEAN_PORTS":
            os.system("fuser -k 80/tcp 443/tcp 18789/tcp")
        elif action_name == "RESTART_GATEWAY":
            os.system("openclaw gateway restart")
        return "SUCCESS"
    except Exception as e:
        print(f"Execution failed: {str(e)}")
        return "FAILED"

def process_latest_signal():
    if not os.path.exists(SIGNAL_FILE):
        return
    
    df = pd.read_csv(SIGNAL_FILE)
    if df.empty:
        return
    
    # Get the latest row that hasn't been evaluated (is_accurate is empty or NaN)
    df['is_accurate'] = df['is_accurate'].astype(str).replace('nan', '')
    pending_idx = df[df['is_accurate'] == ''].index
    if len(pending_idx) == 0:
        return
    
    idx = pending_idx[-1]
    signal = df.at[idx, 'signal']
    state_str = df.at[idx, 'state']
    
    # --- IRIS EVALUATION LOGIC ---
    # Parse state: CPU:100.0%,MEM:49.5%,WEB:0,BTC:1,GW:0
    state_dict = {}
    for part in state_str.split(','):
        key, val = part.split(':')
        state_dict[key] = val
    
    is_accurate = "NO"
    should_execute = False
    
    # Simple Heuristic Rules for Iris Evaluation
    if signal == "NO_OP":
        if float(state_dict['CPU'].replace('%','')) < 90 and state_dict['WEB'] == '1' and state_dict['GW'] == '1':
            is_accurate = "YES"
    elif signal == "RESTART_WEB" and state_dict['WEB'] == '0':
        is_accurate = "YES"
        should_execute = True
    elif signal == "RESTART_GATEWAY" and state_dict['GW'] == '0':
        is_accurate = "YES"
        should_execute = True
    elif signal == "CLEAN_PORTS" and (state_dict['WEB'] == '0' or state_dict['GW'] == '0' or float(state_dict['CPU'].replace('%','')) > 95):
        is_accurate = "YES"
        should_execute = True
    elif signal == "RESTART_BTC_ROLLING" and state_dict['BTC'] == '0':
        is_accurate = "YES"
        should_execute = True

    # Mark feedback
    df.at[idx, 'is_accurate'] = is_accurate
    
    # Execute if accurate and allowed
    if should_execute:
        exec_status = execute_action(signal)
        df.at[idx, 'is_executed'] = exec_status
    else:
        df.at[idx, 'is_executed'] = "NO"
        
    df.to_csv(SIGNAL_FILE, index=False)
    print(f"Signal {signal} evaluated as accurate: {is_accurate}. Executed: {df.at[idx, 'is_executed']}")

    # --- TRAINING STEP (Self-Improvement) ---
    # In a real RL agent, we'd do a policy gradient update here based on is_accurate reward
    # For now, we simulate the 'learning' by updating the model weights (omitted for brevity in this script)

if __name__ == "__main__":
    process_latest_signal()
