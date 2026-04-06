from dataclasses import dataclass
from typing import Dict
import threading
from datetime import date

class WeatherRiskManager:
    def __init__(self, config: Dict):
        self.lock = threading.Lock()
        self.max_position_usd = float(config.get('MAX_POSITION_USD', 100))
        self.kelly_fraction = float(config.get('KELLY_FRACTION', 0.5))
        self.min_edge = float(config.get('MIN_EDGE', 0.05))
        self.daily_loss_limit = float(config.get('DAILY_LOSS_LIMIT', 100))
        self._today_loss = 0.0
        self._current_date = date.today()

    def calculate_kelly_size(self, win_prob: float, market_price: float, bankroll: float) -> float:
        if market_price <= 0 or market_price >= 1: return 0
        edge = win_prob - market_price
        if edge < self.min_edge: return 0
        b = (1 - market_price) / market_price
        f_star = (b * win_prob - (1 - win_prob)) / b if b > 0 else 0
        size = bankroll * max(0, f_star * self.kelly_fraction)
        return min(size, self.max_position_usd)

    def can_trade(self) -> bool:
        with self.lock:
            if date.today() != self._current_date:
                self._today_loss = 0
                self._current_date = date.today()
            return self._today_loss < self.daily_loss_limit
