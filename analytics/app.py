from flask import Flask, jsonify, render_template
from flask_cors import CORS
import sys
import os
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append('/root/irisquant')

from simulation.exchange_sim import sim_exchange

app = Flask(__name__)
CORS(app)

# 账户映射 (exchange_sim ID -> 前端显示)
ACCOUNT_MAPPING = {
    "A": {"id": "BINANCE_MAIN", "name": "ACCOUNT BINANCE_MAIN BALANCE (btc-rolling)"},
    "B": {"id": "OKX_SUB1", "name": "ACCOUNT OKX_SUB1 BALANCE (contract-trader)"},
    "C": {"id": "POLYMARKET", "name": "ACCOUNT POLYMARKET BALANCE (polymarket)"},
    "W": {"id": "WEATHER_ALPHA", "name": "ACCOUNT WEATHER_ALPHA BALANCE (weather-alpha-bot)"}
}

def get_accounts_data():
    """从 exchange_sim 获取四个账户的余额和盈亏"""
    accounts = []
    for sim_id, info in ACCOUNT_MAPPING.items():
        acc = sim_exchange.accounts.get(sim_id)
        if acc:
            accounts.append({
                "id": info["id"],
                "name": info["name"],
                "balance": acc.balance,
                "daily_pnl": acc.daily_pnl,
                "color": "#3b82f6" if sim_id == "A" else "#10b981" if sim_id == "B" else "#f59e0b" if sim_id == "C" else "#ef4444"
            })
    return accounts

def generate_equity_data():
    """生成四个账户的资金曲线"""
    dates = [(datetime.now() - timedelta(days=i)).strftime("%m-%d") for i in range(29, -1, -1)]
    accounts_data = {}
    for sim_id, info in ACCOUNT_MAPPING.items():
        acc = sim_exchange.accounts.get(sim_id)
        base = acc.balance if acc else 10000
        accounts_data[info["id"]] = [{"date": d, "equity": base + (i * 5)} for i, d in enumerate(dates)]
    return accounts_data

def generate_trades():
    """生成模拟交易记录"""
    return []

def calculate_summary():
    """计算汇总统计"""
    accounts = get_accounts_data()
    total_equity = sum(a["balance"] for a in accounts)
    total_pnl = sum(a["daily_pnl"] for a in accounts)
    return {
        "total_equity": total_equity,
        "total_pnl": total_pnl,
        "win_rate": 0,
        "max_drawdown": 0
    }

@app.route('/analytics')
def analytics():
    return render_template('analytics.html')

@app.route('/api/analytics/accounts')
def api_accounts():
    return jsonify(get_accounts_data())

@app.route('/api/analytics/summary')
def api_summary():
    return jsonify(calculate_summary())

@app.route('/api/analytics/equity/all')
def api_equity_all():
    return jsonify(generate_equity_data())

@app.route('/api/analytics/daily')
def api_daily():
    return jsonify([])

@app.route('/api/analytics/distribution')
def api_distribution():
    return jsonify({"wins": 0, "losses": 0})

@app.route('/api/analytics/trades')
def api_trades():
    return jsonify(generate_trades())

@app.route('/api/analytics/risk')
def api_risk():
    return jsonify({
        "accounts": [
            {"name": "ACCOUNT BINANCE_MAIN BALANCE (btc-rolling)", "today_loss": 0, "daily_limit": 100, "emergency": False},
            {"name": "ACCOUNT OKX_SUB1 BALANCE (contract-trader)", "today_loss": 0, "daily_limit": 100, "emergency": False},
            {"name": "ACCOUNT POLYMARKET BALANCE (polymarket)", "today_loss": 0, "daily_limit": 100, "emergency": False},
            {"name": "ACCOUNT WEATHER_ALPHA BALANCE (weather-alpha-bot)", "today_loss": 0, "daily_limit": 100, "emergency": False}
        ]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=False)
