import json
import os
from typing import Dict

BALANCE_MODE = "simulation"
SIM_STATE_FILE = "/tmp/irisquant_sim_state.json"
WEATHER_BALANCE_FILE = "/root/weather-alpha/data/w_balance.json"

class BalanceService:
    def __init__(self):
        self.mode = BALANCE_MODE
    
    def get_all_balances(self) -> Dict[str, float]:
        if self.mode == "simulation":
            return self._get_sim_balances()
        else:
            return self._get_exchange_balances()
    
    def _get_sim_balances(self) -> Dict[str, float]:
        try:
            with open(SIM_STATE_FILE, 'r') as f:
                data = json.load(f)
                accounts = data.get("accounts", {})
                result = {aid: acc.get("balance", 0.0) for aid, acc in accounts.items()}
                
                # 覆盖 W 账户为真实余额
                if os.path.exists(WEATHER_BALANCE_FILE):
                    with open(WEATHER_BALANCE_FILE, 'r') as f:
                        weather_data = json.load(f)
                        result["W"] = weather_data.get("balance", result.get("W", 0.0))
                
                return result
        except Exception as e:
            print(f"读取余额失败: {e}")
            return {}
    
    def _get_exchange_balances(self) -> Dict[str, float]:
        return {}

balance_service = BalanceService()
