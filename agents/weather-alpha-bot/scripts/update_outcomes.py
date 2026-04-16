#!/usr/bin/env python3
import sys
import os

sys.path.append("/root/weather-alpha")
from core.data_recorder import DataRecorder
from core.adaptive_bias import AdaptiveBiasCorrector

def update_market_outcome(market_id: str, actual_yes: int, strategy: str = None, key: str = None, forecast_prob: float = None):
    """
    actual_yes: 1 表示 YES 获胜，0 表示 NO 获胜
    """
    recorder = DataRecorder()
    recorder.update_order_outcome(market_id, actual_yes)
    print(f"✅ 已更新 {market_id} 结算结果: {'YES赢' if actual_yes else 'NO赢'}")
    
    # 如果提供了策略信息，同时更新偏差
    if strategy and key and forecast_prob is not None:
        corrector = AdaptiveBiasCorrector({})
        corrector.update_bias(strategy, key, forecast_prob, actual_yes)
        print(f"✅ 已更新偏差: {strategy}/{key}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python update_outcomes.py <market_id> <1/0> [strategy] [key] [forecast_prob]")
        print("示例: python update_outcomes.py NYC-PRECIP-ID 1 cross_city NYC 0.65")
        sys.exit(1)
    
    market_id = sys.argv[1]
    actual_yes = int(sys.argv[2])
    
    if len(sys.argv) >= 5:
        strategy = sys.argv[3]
        key = sys.argv[4]
        forecast_prob = float(sys.argv[5]) if len(sys.argv) >= 6 else None
        update_market_outcome(market_id, actual_yes, strategy, key, forecast_prob)
    else:
        update_market_outcome(market_id, actual_yes)
