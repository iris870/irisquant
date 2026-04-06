import os
import time
import logging
import signal
import sys
from dotenv import load_dotenv
from strategies.weather_alpha import WeatherAlpha

load_dotenv()

class StandaloneCLOBClient:
    """Boss: 部署后在此处填入真实的 Polymarket CLOB 接入代码"""
    def get_balance(self): return 1000.0
    def get_market_price(self, mid, side): return 0.65
    def place_order(self, mid, side, size, price):
        print(f"WEATHER_ORDER: {side} {size:.2f} @ {price:.3f} on {mid}")
        return {"status": "success"}

def setup_logging():
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.FileHandler("logs/weather_alpha.log"), logging.StreamHandler()]
    )
    return logging.getLogger("WeatherAlpha")

def main():
    logger = setup_logging()
    logger.info("Weather Alpha Standalone Engine Starting...")
    
    clob = StandaloneCLOBClient()
    config = {
        "MAX_POSITION_USD": float(os.getenv("MAX_POSITION_USD", 100)),
        "KELLY_FRACTION": float(os.getenv("KELLY_FRACTION", 0.5)),
        "MIN_EDGE": float(os.getenv("MIN_EDGE", 0.05)),
        "DAILY_LOSS_LIMIT": float(os.getenv("DAILY_LOSS_LIMIT", 100))
    }
    
    engine = WeatherAlpha(config, clob, logger)
    
    def shutdown_handler(signum, frame):
        logger.info("Graceful shutdown initiated...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    while True:
        try:
            logger.info("Running scan iteration (NYC, LDN, CHI)...")
            engine.run_once()
        except Exception as e:
            logger.error(f"Engine Loop Error: {e}")
        time.sleep(int(os.getenv("SCAN_INTERVAL", 300)))

if __name__ == "__main__":
    main()
