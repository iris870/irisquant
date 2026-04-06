from flask import Flask, jsonify, render_template
from flask_cors import CORS
import sqlite3
import re
import os
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__)
# 彻底禁用严格斜杠匹配
app.url_map.strict_slashes = False
CORS(app)

# 配置
DB_PATH = "/root/irisquant/data/knowledge.db"
WEATHER_LOG_PATH = "/root/weather-alpha/logs/weather_alpha.log"

# 账户映射
ACCOUNT_MAPPING = {
    "binance_main": "ACCOUNT BINANCE_MAIN BALANCE (btc-rolling)",
    "okx_sub1": "ACCOUNT OKX_SUB1 BALANCE (contract-trader)",
    "polymarket": "ACCOUNT POLYMARKET BALANCE (polymarket)",
    "weather_alpha": "ACCOUNT WEATHER_ALPHA BALANCE (weather-alpha-bot)"
}

def get_polymarket_trades(days=30):
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    try:
        # 适配最新的数据库字段：symbol, amount, pnl
        cursor.execute("""
            SELECT timestamp, symbol as market, side, amount as size_usdc, price, pnl as pnl_usdc, agent
            FROM trades 
            WHERE timestamp > ?
            ORDER BY timestamp DESC
        """, (cutoff,))
        return [{
            'timestamp': r['timestamp'],
            'account': ACCOUNT_MAPPING.get(r['agent'], r['agent']),
            'market': r['market'] or 'unknown',
            'side': r['side'],
            'size_usdc': float(r['size_usdc'] or 0),
            'pnl_usdc': float(r['pnl_usdc'] or 0),
            'is_simulated': False
        } for r in cursor.fetchall()]
    except Exception as e:
        print(f"DB Error: {e}")
        return []
    finally:
        conn.close()

def parse_weather_logs(days=30):
    if not os.path.exists(WEATHER_LOG_PATH):
        return []
    trades = []
    cutoff = datetime.now() - timedelta(days=days)
    # 正则修正：匹配 [2026-04-06 03:30:10] DRY_RUN: YES for NYC-PRECIP (Amount: 43.15 USDC)
    log_pattern = re.compile(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] DRY_RUN: (\S+) for (\S+) \(Amount: ([\d\.]+) USDC\)')
    
    try:
        with open(WEATHER_LOG_PATH, 'r') as f:
            for line in f:
                match = log_pattern.search(line)
                if not match:
                    continue
                
                ts_str, side, market, amount = match.groups()
                ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                if ts < cutoff:
                    continue
                
                trades.append({
                    'timestamp': ts.isoformat(),
                    'account': ACCOUNT_MAPPING['weather_alpha'],
                    'market': market,
                    'side': side,
                    'size_usdc': float(amount),
                    'pnl_usdc': 0.0, # 模拟盘暂时记录为 0
                    'is_simulated': True
                })
        return trades
    except Exception as e:
        print(f"Log Error: {e}")
        return []

def get_all_trades():
    # 按照时间降序排列
    all_trades = get_polymarket_trades() + parse_weather_logs()
    return sorted(all_trades, key=lambda x: x['timestamp'], reverse=True)

# 核心页面入口
@app.route('/')
@app.route('/analytics')
def analytics_page():
    return render_template('analytics.html')

# --- API 路由 (修复 NaN 和 路径问题) ---

@app.route('/api/summary')
@app.route('/analytics/api/summary')
def api_summary():
    trades = get_all_trades()
    if not trades:
        return jsonify({'total_pnl': 0, 'total_trades': 0, 'win_rate': 0, 'max_drawdown': 0, 'current_equity': 10000})
    
    total_pnl = sum(t['pnl_usdc'] for t in trades)
    winning = [t for t in trades if t['pnl_usdc'] > 0]
    win_rate = len(winning) / len(trades) if trades else 0
    
    # 计算最大回撤 (防止 NaN)
    cumulative, peak, max_dd = 10000.0, 10000.0, 0.0
    for t in sorted(trades, key=lambda x: x['timestamp']):
        cumulative += t['pnl_usdc']
        peak = max(peak, cumulative)
        dd = (peak - cumulative) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)
        
    return jsonify({
        'total_pnl': round(total_pnl, 2),
        'total_trades': len(trades),
        'win_rate': round(win_rate, 4),
        'max_drawdown': round(max_dd * 100, 2), # 转为百分比
        'current_equity': round(10000 + total_pnl, 2)
    })

@app.route('/api/trades')
@app.route('/analytics/api/trades')
def api_trades():
    return jsonify(get_all_trades()[:200])

@app.route('/api/equity')
@app.route('/analytics/api/equity')
def api_equity():
    trades = sorted(get_all_trades(), key=lambda x: x['timestamp'])
    cumulative, curve = 10000.0, []
    # 每天汇总一次 equity
    daily_equity = {}
    for t in trades:
        cumulative += t['pnl_usdc']
        daily_equity[t['timestamp'][:10]] = cumulative
    
    for date, equity in sorted(daily_equity.items()):
        curve.append({'time': date, 'equity': round(equity, 2)})
    return jsonify(curve)

@app.route('/api/daily')
@app.route('/analytics/api/daily')
def api_daily():
    daily = defaultdict(float)
    for t in get_all_trades():
        daily[t['timestamp'][:10]] += t['pnl_usdc']
    return jsonify([{'date': d, 'pnl': round(p, 2)} for d, p in sorted(daily.items())])

@app.route('/api/distribution')
@app.route('/analytics/api/distribution')
def api_distribution():
    trades = get_all_trades()
    wins = sum(1 for t in trades if t['pnl_usdc'] > 0)
    losses = sum(1 for t in trades if t['pnl_usdc'] <= 0)
    return jsonify({'wins': wins, 'losses': losses})

@app.route('/api/risk')
@app.route('/analytics/api/risk')
def api_risk():
    # 实时风险进度条逻辑
    return jsonify({
        'accounts': [
            {'name': v, 'today_loss': 0, 'daily_limit': 100, 'emergency': False} for v in ACCOUNT_MAPPING.values()
        ]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=False)
