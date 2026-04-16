import json
import os
from core.weather_client import NOAAClient
from core.adaptive_bias import AdaptiveBiasCorrector
from core.data_recorder import DataRecorder

class CrossCityArbitrage:
    def __init__(self, config, clob, logger):
        self.noaa = NOAAClient()
        self.clob = clob
        self.logger = logger
        self.config = config
        
        self.cities = [
            {"name": "NYC", "station": "KJFK", "market_id": config.get("NYC_MARKET_ID", "NYC-PRECIP-ID")},
            {"name": "CHI", "station": "KORD", "market_id": config.get("CHI_MARKET_ID", "CHI-PRECIP-ID")},
            {"name": "MIA", "station": "KMIA", "market_id": config.get("MIA_MARKET_ID", "MIA-PRECIP-ID")},
        ]
        
        self.total_budget = float(config.get("ARB_BUDGET", 100))
        self.kelly_fraction = float(config.get("KELLY_FRACTION", 0.2))
        self.min_edge = float(config.get("MIN_EDGE", 0.10))  # 从5%提高到10%
        self.max_position = float(config.get("MAX_POSITION_USD", 100))
        
        self.bias_corrector = AdaptiveBiasCorrector(config)
        self.recorder = DataRecorder()
        self.bias_file = "/root/weather-alpha/data/city_bias.json"
        self.city_bias = self._load_bias()
    
    def _load_bias(self):
        if os.path.exists(self.bias_file):
            with open(self.bias_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_bias(self):
        with open(self.bias_file, 'w') as f:
            json.dump(self.city_bias, f, indent=2)
    
    def _calculate_size(self, prob: float, price: float) -> float:
        edge = prob - price
        if edge <= 0 or price >= 1.0:
            return 0
        b = (1.0 - price) / price
        q = 1.0 - prob
        kelly = (prob * b - q) / b
        size = self.total_budget * kelly * self.kelly_fraction
        return max(0, min(size, self.max_position))
    
    def run_once(self):
        for city in self.cities:
            try:
                forecast = self.noaa.get_forecast_by_station(city['station'])
                if not forecast:
                    continue
                
                noaa_prob = forecast.get('probability', 0.5)
                if noaa_prob is None:
                    continue
                
                market_price = self.clob.get_market_price(city['market_id'], 'YES')
                
                bias = self.city_bias.get(city['name'], 0.0)
                adjusted_prob = max(0.05, min(0.95, noaa_prob - bias))
                
                edge = adjusted_prob - market_price
                
                self.recorder.record_prediction(
                    "cross_city", city['market_id'], adjusted_prob, market_price,
                    {"city": city['name'], "noaa_prob": noaa_prob, "bias": bias}
                )
                
                self.logger.info(f"[跨城市套利] {city['name']}: NOAA={noaa_prob:.1%}, 偏差={bias:.1%}, 修正={adjusted_prob:.1%}, 市价={market_price:.1%}, 优势={edge:.1%}")
                
                # 双向交易：优势 > 10% 买入 YES，优势 < -10% 买入 NO
                if edge >= self.min_edge:
                    size = self._calculate_size(adjusted_prob, market_price)
                    if size >= 2.0:
                        self.logger.info(f"[跨城市套利] ✅ {city['name']} 买入YES: ${size:.2f}")
                        self.recorder.record_order(
                            "cross_city", city['market_id'], "YES",
                            size, market_price + 0.01, adjusted_prob, market_price
                        )
                        self.clob.place_order(city['market_id'], "YES", size, market_price + 0.01)
                elif edge <= -self.min_edge:
                    no_prob = 1 - adjusted_prob
                    no_price = 1 - market_price
                    size = self._calculate_size(no_prob, no_price)
                    if size >= 2.0:
                        self.logger.info(f"[跨城市套利] ✅ {city['name']} 买入NO: ${size:.2f}")
                        self.recorder.record_order(
                            "cross_city", city['market_id'], "NO",
                            size, no_price + 0.01, no_prob, no_price
                        )
                        self.clob.place_order(city['market_id'], "NO", size, no_price + 0.01)
                            
            except Exception as e:
                self.logger.error(f"[跨城市套利] {city['name']} 出错: {e}")
