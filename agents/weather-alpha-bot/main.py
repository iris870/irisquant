import os
import time
import logging
import signal
import sys
import json
import threading
from flask import Flask, jsonify
from dotenv import load_dotenv

# 确保使用本地的 core 模块，而不是 irisquant 的
sys.path.insert(0, "/root/weather-alpha")

from strategies.weather_alpha import WeatherAlpha
from strategies.temperature_ladder import TemperatureLadderStrategy
from strategies.temperature_direction import TemperatureDirectionStrategy
from strategies.cross_city_arbitrage import CrossCityArbitrage

from core.data_recorder import DataRecorder
from core.w_account_adapter import WAccountAdapter
from core.adaptive_bias import AdaptiveBiasCorrector
from core.result_tracker import ResultTracker

load_dotenv()

class StandaloneCLOBClient:
    def get_balance(self): 
        return float(os.getenv("SIMULATED_BALANCE", 10000.0))
    
    def get_market_price(self, mid, side): 
        return 0.65
    
    def place_order(self, mid, side, size, price):
        print(f"📋 ORDER: {side} {size:.2f} @ {price:.3f} on {mid}")
        with open("logs/orders.log", "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {mid} | {side} | {size:.2f} | {price:.3f}\n")
        return {"status": "success"}

def setup_logging():
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler("logs/weather_alpha.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("MultiStrategy")

def main():
    logger = setup_logging()
    logger.info("=" * 60)
    threading.Thread(target=start_http_server, daemon=True).start()
    logger.info("✅ 余额 HTTP 服务已启动在端口 8081")
    logger.info("多策略天气机器人 - 独立版本")
    logger.info("=" * 60)
    
    clob = WAccountAdapter(account_id="W")
    
    config = {
        "MAX_POSITION_USD": float(os.getenv("MAX_POSITION_USD", 100)),
        "KELLY_FRACTION": float(os.getenv("KELLY_FRACTION", 0.25)),
        "MIN_EDGE": float(os.getenv("MIN_EDGE", 0.05)),
        "DAILY_LOSS_LIMIT": float(os.getenv("DAILY_LOSS_LIMIT", 100)),
        "STATION_ID": os.getenv("STATION_ID", "KJFK"),
        "LADDER_BUDGET": float(os.getenv("LADDER_BUDGET", 50)),
        "DIRECTION_BUDGET": float(os.getenv("DIRECTION_BUDGET", 50)),
        "ARB_BUDGET": float(os.getenv("ARB_BUDGET", 100)),
        "DIRECTION_MARKET_ID": os.getenv("DIRECTION_MARKET_ID", "TEMP-DIRECTION-ID"),
        "BIAS_LEARNING_RATE": float(os.getenv("BIAS_LEARNING_RATE", 0.1)),
        "TEMP_LADDER_ID_1": os.getenv("TEMP_LADDER_ID_1", "TEMP-30-35-ID"),
        "TEMP_LADDER_ID_2": os.getenv("TEMP_LADDER_ID_2", "TEMP-35-40-ID"),
        "TEMP_LADDER_ID_3": os.getenv("TEMP_LADDER_ID_3", "TEMP-40-45-ID"),
        "TEMP_LADDER_ID_4": os.getenv("TEMP_LADDER_ID_4", "TEMP-45-50-ID"),
        "TEMP_LADDER_ID_5": os.getenv("TEMP_LADDER_ID_5", "TEMP-50-55-ID"),
        "TEMP_LADDER_ID_6": os.getenv("TEMP_LADDER_ID_6", "TEMP-55PLUS-ID"),
        "NYC_MARKET_ID": os.getenv("NYC_MARKET_ID", "NYC-PRECIP-ID"),
        "CHI_MARKET_ID": os.getenv("CHI_MARKET_ID", "CHI-PRECIP-ID"),
        "MIA_MARKET_ID": os.getenv("MIA_MARKET_ID", "MIA-PRECIP-ID"),
    }
    
 
    # 初始化结果追踪器
    bias_corrector = AdaptiveBiasCorrector(config)
    result_tracker = ResultTracker(bias_corrector)
    result_tracker.start(interval_seconds=300)

    strategies = [
        ("🌧️ 降雨策略", WeatherAlpha(config, clob, logger)),
        # ("🌡️ 温度阶梯", TemperatureLadderStrategy(config, clob, logger)),
        ("📈 升降温方向", TemperatureDirectionStrategy(config, clob, logger)),
        ("🏙️ 跨城市套利", CrossCityArbitrage(config, clob, logger)),
    ]
    
    def shutdown_handler(signum, frame):
        logger.info("正在关闭...")
        recorder = DataRecorder()
        stats = recorder.get_statistics()
        logger.info(f"最终统计: 预测={stats['total_predictions']}, 订单={stats['total_orders']}, 胜率={stats['win_rate']:.1%}")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    scan_interval = int(os.getenv("SCAN_INTERVAL", 300))
    logger.info(f"扫描间隔: {scan_interval} 秒")
    logger.info(f"已加载 {len(strategies)} 个策略")
    
    iteration = 0
    while True:
        # 同步余额到统一服务（供其他 Agent 使用）
        try:
            with open("data/w_balance.json", "r") as f:
                data = json.load(f)
                current_balance = data.get("balance", 0.0)
            import asyncio
            #             asyncio.run(balance_service.update_balance("W", current_balance, source="weather_alpha"))
        except Exception as e:
            logger.warning(f"同步余额失败: {e}")

        iteration += 1
        logger.info(f"=== 第 {iteration} 轮扫描 ===")
        
        for name, strategy in strategies:
            try:
                logger.info(f"执行: {name}")
                strategy.run_once()
            except Exception as e:
                logger.error(f"策略 [{name}] 错误: {e}")
        
        logger.info(f"等待 {scan_interval} 秒...")
        time.sleep(scan_interval)

balance_app = Flask(__name__)

@balance_app.route('/balance')
def get_balance():
    try:
        with open('data/w_balance.json', 'r') as f:
            data = json.load(f)
        return jsonify({"balance": data.get("balance", 500.0), "account": "W"})
    except Exception as e:
        return jsonify({"balance": 500.0, "error": str(e)})

def start_http_server():
    balance_app.run(host='0.0.0.0', port=8082, debug=False, use_reloader=False)

if __name__ == "__main__":
    main()
