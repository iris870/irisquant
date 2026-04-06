#!/usr/bin/env python3
"""
推理服务 - 为 leader.py 提供 RL 建议
"""

import json
import logging
from flask import Flask, request, jsonify
from pathlib import Path
import sys

# Ensure parent directory is in path for relative imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import encoders
from rl_trade.state_encoder import TradeStateEncoder
from rl.state_encoder import StateEncoder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from core.telegram import send_alert

app = Flask(__name__)

# Initialize encoders (TradeStateEncoder uses 64 dim based on implementation)
trade_encoder = TradeStateEncoder(state_dim=64)
ops_encoder = StateEncoder(state_dim=64)

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'healthy'})

@app.route('/advice/position', methods=['POST'])
def position_advice():
    """
    仓位建议接口

    请求体:
    {
        "market": {...},
        "onchain": {...},
        "sentiment": {...},
        "position": {...}
    }

    响应:
    {
        "position_multiplier": 0.6,
        "confidence": 0.75,
        "reason": "波动率偏高，建议减仓"
    }
    """
    try:
        data = request.get_json() or {}

        # 编码状态
        state = trade_encoder.encode_combined(
            market=data.get('market', {}),
            onchain=data.get('onchain', {}),
            sentiment=data.get('sentiment', {}),
            position=data.get('position', {})
        )

        # TODO: 这里调用 RL 模型推理 (e.g., model.predict(state))
        # 当前使用规则演示
        volatility = data.get('market', {}).get('volatility', 20)
        if volatility > 30:
            multiplier = 0.5
            reason = "高波动环境，建议减仓"
        elif volatility > 20:
            multiplier = 0.7
            reason = "中等波动，正常仓位"
        else:
            multiplier = 1.0
            reason = "低波动，可满仓"

        return jsonify({
            'position_multiplier': multiplier,
            'confidence': 0.7,
            'reason': reason,
            'state_shape': list(state.shape)
        })

    except Exception as e:
        logger.error(f"仓位建议失败: {e}", exc_info=True)
        send_alert(f"🚨 [InferenceAPI] Position advice error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/advice/timing', methods=['POST'])
def timing_advice():
    """时机建议接口"""
    try:
        data = request.get_json() or {}
        market = data.get('market', {})

        # 简单规则
        rsi = market.get('rsi', 50)
        if rsi > 70:
            advice = "wait"
            reason = "RSI 超买，建议等待"
        elif rsi < 30:
            advice = "immediate"
            reason = "RSI 超卖，可入场"
        else:
            advice = "immediate"
            reason = "中性区域，正常执行"

        return jsonify({
            'timing': advice,
            'confidence': 0.6,
            'reason': reason
        })

    except Exception as e:
        logger.error(f"时机建议失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/advice/stop_loss', methods=['POST'])
def stop_loss_advice():
    """止损建议接口"""
    try:
        data = request.get_json() or {}
        market = data.get('market', {})
        position = data.get('position', {})

        volatility = market.get('volatility', 20)
        entry_price = position.get('entry_price', 0)

        if volatility > 30:
            stop_pct = 0.03  # 3% 止损
        elif volatility > 20:
            stop_pct = 0.025
        else:
            stop_pct = 0.02

        stop_price = entry_price * (1 - stop_pct) if entry_price > 0 else 0

        return jsonify({
            'stop_loss_pct': stop_pct,
            'stop_loss_price': stop_price,
            'confidence': 0.65,
            'reason': f"波动率 {volatility}%，建议止损 {stop_pct*100:.1f}%"
        })

    except Exception as e:
        logger.error(f"止损建议失败: {e}", exc_info=True)
        send_alert(f"🚨 [InferenceAPI] Stop loss advice error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    # In production, use Gunicorn or similar. Flask's built-in server is for dev.
    app.run(host='0.0.0.0', port=5001, debug=False)
