#!/root/irisquant/venv/bin/python3
import os
import time
import pandas as pd
import numpy as np
import subprocess
import torch
import torch.nn as nn
import torch.optim as optim
from datetime import datetime

# Paths
SIGNAL_FILE = "/root/irisquant/outputs/ops_signals.csv"
MODEL_FILE = "/root/irisquant/models/iris_rl_ops.pth"

# Actions Mapping
ACTIONS = {
    0: "NO_OP",
    1: "RESTART_WEB",
    2: "RESTART_BTC_ROLLING",
    3: "CLEAN_PORTS",
    4: "RESTART_GATEWAY"
}

class IrisRLOps(nn.Module):
    def __init__(self, input_size, output_size):
        super(IrisRLOps, self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(input_size, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, output_size),
            nn.Softmax(dim=-1)
        )

    def forward(self, x):
        return self.fc(x)

def get_system_state():
    """Simple feature extraction for system state"""
    try:
        # Mocking feature extraction: CPU, Memory, Disk, and process status
        # In a real scenario, we'd use psutil or shell commands
        cpu = float(os.popen(r"top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\([0-9.]*\)%* id.*/\1/' | awk '{print 100 - $1}'").read().strip())
        mem = float(os.popen("free | grep Mem | awk '{print $3/$2 * 100.0}'").read().strip())
        
        # Check if specific processes are running
        web_up = 1.0 if os.popen("pgrep nginx").read().strip() else 0.0
        btc_up = 1.0 if "online" in os.popen("pm2 show btc-rolling").read() else 0.0
        gw_up = 1.0 if os.popen("pgrep openclaw").read().strip() else 0.0
        
        return np.array([cpu, mem, web_up, btc_up, gw_up], dtype=np.float32)
    except:
        return np.array([0, 0, 0, 0, 0], dtype=np.float32)

def generate_signal():
    state = get_system_state()
    state_tensor = torch.FloatTensor(state).unsqueeze(0)
    
    # Load model if exists
    input_dim = 5
    output_dim = len(ACTIONS)
    model = IrisRLOps(input_dim, output_dim)
    if os.path.exists(MODEL_FILE):
        model.load_state_dict(torch.load(MODEL_FILE))
    
    with torch.no_grad():
        probs = model(state_tensor).numpy()[0]
    
    action_id = np.argmax(probs)
    confidence = probs[action_id]
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state_str = f"CPU:{state[0]:.1f}%,MEM:{state[1]:.1f}%,WEB:{int(state[2])},BTC:{int(state[3])},GW:{int(state[4])}"
    
    # Save to CSV (placeholder for feedback)
    new_row = {
        "timestamp": timestamp,
        "state": state_str,
        "signal": ACTIONS[action_id],
        "confidence": f"{confidence*100:.2f}%",
        "is_accurate": "", # Pending Iris/User feedback
        "is_executed": "NO" # Phase 1 constraint
    }
    
    df = pd.DataFrame([new_row])
    df.to_csv(SIGNAL_FILE, mode='a', header=not os.path.exists(SIGNAL_FILE), index=False)
    
    return new_row

if __name__ == "__main__":
    result = generate_signal()
    print(f"SIGNAL_TYPE: {result['signal']}")
    print(f"CONFIDENCE: {result['confidence']}")
    print(f"STATE: {result['state']}")
