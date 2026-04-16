import logging
import os
from core.weather_client import NOAAClient
from core.risk_manager import WeatherRiskManager

class WeatherAlpha:
    def __init__(self, config, clob, logger):
        self.noaa = NOAAClient(os.getenv('CONTACT_EMAIL'))
        self.risk = WeatherRiskManager(config)
        self.clob = clob
        self.logger = logger
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
            forecast = self.noaa.get_forecast_by_station(m['station_id'])
            if not forecast: continue
            
            prob = forecast['probability']
            price = self.clob.get_market_price(m['id'], 'YES')
            size = self.risk.calculate_kelly_size(prob, price, bankroll)
            
            if size >= 5:
                self.logger.info(f"SIGNAL: {m['id']} | Prob:{prob:.1%} | Price:{price} | Size:${size:.2f}")
                self.clob.place_order(m['id'], 'YES', size, price + 0.01)
