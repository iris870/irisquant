import json
import os
from datetime import datetime
from typing import Dict

class AdaptiveBiasCorrector:
    def __init__(self, config: Dict, data_dir="/root/weather-alpha/data"):
        self.learning_rate = float(config.get("BIAS_LEARNING_RATE", 0.1))
        self.data_dir = data_dir
        self.bias_file = os.path.join(data_dir, "adaptive_bias.json")
        self.biases = self._load_biases()

    def _load_biases(self) -> Dict:
        if os.path.exists(self.bias_file):
            with open(self.bias_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_biases(self):
        with open(self.bias_file, 'w') as f:
            json.dump(self.biases, f, indent=2)

    def get_adjusted_prob(self, strategy: str, key: str, forecast_prob: float) -> float:
        """获取调整后的概率"""
        bias_key = f"{strategy}_{key}"
        bias = self.biases.get(bias_key, 0.0)
        adjusted = forecast_prob - bias
        return max(0.05, min(0.95, adjusted))

    def update_bias(self, strategy: str, key: str, forecast_prob: float, actual_outcome: float):
        """
        更新偏差（实际结算后调用）
        actual_outcome: 1表示事件发生，0表示未发生
        """
        bias_key = f"{strategy}_{key}"
        error = actual_outcome - forecast_prob
        old_bias = self.biases.get(bias_key, 0.0)
        new_bias = old_bias * (1 - self.learning_rate) + error * self.learning_rate
        self.biases[bias_key] = new_bias
        self._save_biases()
        return new_bias

    def get_bias(self, strategy: str, key: str) -> float:
        bias_key = f"{strategy}_{key}"
        return self.biases.get(bias_key, 0.0)
