import requests
import time
import logging
from typing import Optional, Dict
from datetime import datetime

class NOAAClient:
    def __init__(self, contact_email="weather-bot@example.com"):
        self.base_url = "https://api.weather.gov"
        self.headers = {
            "User-Agent": f"(WeatherBot, {contact_email})",
            "Accept": "application/geo+json"
        }
        self.cache = {}

    def get_forecast_by_station(self, station_id: str) -> Optional[Dict]:
        try:
            resp = requests.get(f"{self.base_url}/stations/{station_id}", headers=self.headers, timeout=10)
            if resp.status_code != 200: return None
            coords = resp.json()['geometry']['coordinates']
            return self.get_forecast_by_coords(coords[1], coords[0])
        except Exception as e:
            logging.error(f"Station lookup error: {e}")
            return None

    def get_forecast_by_coords(self, lat: float, lon: float) -> Optional[Dict]:
        cache_key = f"{lat:.2f},{lon:.2f}"
        if cache_key in self.cache and (time.time() - self.cache[cache_key]['time'] < 3600):
            return self.cache[cache_key]['data']
        try:
            p_resp = requests.get(f"{self.base_url}/points/{lat},{lon}", headers=self.headers, timeout=10)
            if p_resp.status_code != 200: return None
            prop = p_resp.json()['properties']
            f_url = f"{self.base_url}/gridpoints/{prop['gridId']}/{prop['gridX']},{prop['gridY']}/forecast/hourly"
            f_resp = requests.get(f_url, headers=self.headers, timeout=10)
            if f_resp.status_code != 200: return None
            data = self._parse_forecast(f_resp.json())
            self.cache[cache_key] = {'data': data, 'time': time.time()}
            return data
        except Exception as e:
            logging.error(f"NOAA API error: {e}")
            return None

    def _parse_forecast(self, data: Dict) -> Dict:
        periods = data.get('properties', {}).get('periods', [])
        if not periods: return {}
        p = periods[0]
        pop = p.get('probabilityOfPrecipitation', {}).get('value', 0)
        prob = pop / 100.0 if pop is not None else 0.5
        return {
            'temp_f': p.get('temperature'),
            'probability': prob,
            'forecast_text': p.get('shortForecast'),
            'start_time': p.get('startTime')
        }
