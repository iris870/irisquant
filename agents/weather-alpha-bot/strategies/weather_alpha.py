import logging
import os
from core.weather_client import NOAAClient
from core.risk_manager import WeatherRiskManager

class WeatherAlpha:
    def is_market_expired(self, market_id):
        import re
        from datetime import datetime
        match = re.search(r"(\d{4}-\d{2}-\d{2})", market_id)
        if match:
            end_date = datetime.strptime(match.group(1), "%Y-%m-%d")
            return datetime.now() > end_date
        return False
    def __init__(self, config, clob, logger):
        self.noaa = NOAAClient(os.getenv('CONTACT_EMAIL'))
        self.risk = WeatherRiskManager(config)
        self.clob = clob
        self.logger = logger
        self.min_edge = float(config.get("MIN_EDGE", 0.10))
        self.markets = [
            {"id": "NYC-PRECIP-2026-04-10", "station_id": "KJFK"},
            {"id": "CHI-RAIN-2026-04-10", "station_id": "KORD"}
        ]

    def run_once(self):
        if not self.risk.can_trade():
            self.logger.warning("Daily loss limit reached. Trading paused.")
            return
        
        bankroll = self.clob.get_balance()
        for m in self.markets:
            if self.is_market_expired(m["id"]):
                self.logger.info(f"跳过过期市场: {m["id"]}")
                continue
            forecast = self.noaa.get_forecast_by_station(m['station_id'])
            if not forecast: continue
            
            prob = forecast['probability']
            price = self.clob.get_market_price(m['id'], 'YES')
            edge = prob - price
            
            # 双向交易
            if edge >= self.min_edge:
                size = self.risk.calculate_kelly_size(prob, price, bankroll)
                if size >= 5:
                    self.logger.info(f"SIGNAL: {m['id']} | Prob:{prob:.1%} | Price:{price} | 优势:{edge:.1%} | Size:${size:.2f}")
                    self.clob.place_order(m['id'], 'YES', size, price + 0.01)
            elif edge <= -self.min_edge:
                no_prob = 1 - prob
                no_price = 1 - price
                size = self.risk.calculate_kelly_size(no_prob, no_price, bankroll)
                if size >= 5:
                    self.logger.info(f"SIGNAL: {m['id']} | 买入NO | 概率:{no_prob:.1%} | 价格:{no_price:.2f} | Size:${size:.2f}")
                    self.clob.place_order(m['id'], 'NO', size, no_price + 0.01)
