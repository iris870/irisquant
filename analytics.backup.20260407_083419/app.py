from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import sqlite3
import re
import os
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__)
CORS(app)

# 配置
KNOWLEDGE_DB = "/root/irisquant/data/knowledge.db"
WEATHER_LOG_PATH = "/root/weather-alpha/logs/weather_alpha.log"

# 四个账户的完整名称和内部标识
ACCOUNTS = [
 {"id": "BINANCE_MAIN", "name": "ACCOUNT BINANCE_MAIN BALANCE (btc-rolling)", "color": "#3b82f6"},
 {"id": "OKX_SUB1", "name": "ACCOUNT OKX_SUB1 BALANCE (contract-trader)", "color": "#10b981"},
 {"id": "POLYMARKET", "name": "ACCOUNT POLYMARKET BALANCE (polymarket)", "color": "#f59e0b"},
 {"id": "WEATHER_ALPHA", "name": "ACCOUNT WEATHER_ALPHA BALANCE (weather-alpha-bot)", "color": "#ef4444"}
]

def get_balance_from_db(account_id):
 """从 knowledge.db 读取余额"""
 try:
  conn = sqlite3.connect(KNOWLEDGE_DB)
  c = conn.cursor()
  # 尝试多种 key 格式
  keys = [f"account:{account_id.lower()}:balance", f"{account_id.lower()}_balance", f"balance_{account_id.lower()}"]
  for key in keys:
   c.execute("SELECT value FROM knowledge WHERE key = ?", (key,))
   row = c.fetchone()
   if row:
    conn.close()
    return float(row[0])
  conn.close()
  return 0.0
 except:
  return 0.0

def get_pnl_from_db(account_id):
 """从 knowledge.db 读取盈亏"""
 try:
  conn = sqlite3.connect(KNOWLEDGE_DB)
  c = conn.cursor()
  keys = [f"account:{account_id.lower()}:pnl_24h", f"{account_id.lower()}_pnl", f"pnl_{account_id.lower()}"]
  for key in keys:
   c.execute("SELECT value FROM knowledge WHERE key = ?", (key,))
   row = c.fetchone()
   if row:
    conn.close()
    return float(row[0])
  conn.close()
  return 0.0
 except:
  return 0.0

def parse_weather_logs(days=30):
 """解析天气日志获取模拟交易"""
 trades = []
 if not os.path.exists(WEATHER_LOG_PATH):
  return trades
 
 cutoff = datetime.now() - timedelta(days=days)
 with open(WEATHER_LOG_PATH, 'r') as f:
  for line in f:
   if 'DRY_RUN' not in line and 'SIGNAL' not in line:
    continue
   time_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
   if not time_match:
    continue
   ts = datetime.strptime(time_match.group(1), '%Y-%m-%d %H:%M:%S')
   if ts < cutoff:
    continue
   size_match = re.search(r'Size:([\d\.]+) USDC', line)
   size = float(size_match.group(1)) if size_match else 0
   market_match = re.search(r'on (\S+)', line)
   market = market_match.group(1) if market_match else 'unknown'
   trades.append({
    'timestamp': ts.isoformat(),
    'account': 'WEATHER_ALPHA',
    'account_name': 'ACCOUNT WEATHER_ALPHA BALANCE (weather-alpha-bot)',
    'market': market,
    'side': 'YES',
    'size_usdc': size,
    'pnl_usdc': 0,
    'is_simulated': True
   })
 return trades

def get_trades_from_db(days=30):
 """从数据库获取交易记录"""
 trades = []
 if not os.path.exists(KNOWLEDGE_DB):
  return trades
 
 conn = sqlite3.connect(KNOWLEDGE_DB)
 conn.row_factory = sqlite3.Row
 cursor = conn.cursor()
 cutoff = (datetime.now() - timedelta(days=days)).isoformat()
 
 try:
  cursor.execute("""
  SELECT timestamp, agent, symbol, side, amount, pnl
  FROM trades 
  WHERE timestamp > ?
  ORDER BY timestamp DESC
  """, (cutoff,))
  rows = cursor.fetchall()
  for r in rows:
   agent = r['agent'].upper() if r['agent'] else 'UNKNOWN'
   account_name = next((acc['name'] for acc in ACCOUNTS if acc['id'] == agent), agent)
   trades.append({
    'timestamp': r['timestamp'],
    'account': agent,
    'account_name': account_name,
    'market': r['symbol'],
    'side': r['side'],
    'size_usdc': r['amount'] or 0,
    'pnl_usdc': r['pnl'] or 0,
    'is_simulated': True
   })
 except Exception as e:
  print(f"DB error: {e}")
 finally:
  conn.close()
 
 return trades

def get_all_trades():
 """获取所有交易"""
 db_trades = get_trades_from_db()
 weather_trades = parse_weather_logs()
 return db_trades + weather_trades

@app.route('/analytics', strict_slashes=False)
@app.route('/analytics/', strict_slashes=False)
def analytics_page():
 return render_template('analytics.html')

@app.route('/api/analytics/summary', strict_slashes=False)
def api_summary():
 trades = get_all_trades()
 total_pnl = sum(t['pnl_usdc'] for t in trades)
 total_trades = len(trades)
 winning = [t for t in trades if t['pnl_usdc'] > 0]
 win_rate = len(winning) / total_trades if total_trades > 0 else 0
 
 # 计算当前总净值
 total_balance = 0
 for acc in ACCOUNTS:
  balance = get_balance_from_db(acc['id'])
  if balance == 0:
   # 模拟数据
   if acc['id'] == 'BINANCE_MAIN': balance = 10000
   elif acc['id'] == 'OKX_SUB1': balance = 50000
   elif acc['id'] == 'POLYMARKET': balance = 2000
   elif acc['id'] == 'WEATHER_ALPHA': balance = 500
  total_balance += balance
 
 return jsonify({
  'total_equity': total_balance,
  'total_pnl': total_pnl,
  'total_trades': total_trades,
  'win_rate': win_rate,
  'max_drawdown': 0
 })

@app.route('/api/analytics/accounts')
def api_accounts():
 """返回四个账户的余额和盈亏"""
 result = []
 for acc in ACCOUNTS:
  balance = get_balance_from_db(acc['id'])
  pnl = get_pnl_from_db(acc['id'])
  # 模拟数据兜底
  if balance == 0:
   if acc['id'] == 'BINANCE_MAIN': balance = 10000
   elif acc['id'] == 'OKX_SUB1': balance = 50000
   elif acc['id'] == 'POLYMARKET': balance = 2000
   elif acc['id'] == 'WEATHER_ALPHA': balance = 500
  result.append({
   'id': acc['id'],
   'name': acc['name'],
   'balance': balance,
   'daily_pnl': pnl,
   'color': acc['color']
  })
 return jsonify(result)

@app.route('/api/analytics/trades')
def api_trades():
 trades = get_all_trades()
 return jsonify(trades[:200])

@app.route('/api/analytics/equity')
def api_equity():
 trades = get_all_trades()
 if not trades:
  return jsonify([])
 sorted_trades = sorted(trades, key=lambda x: x['timestamp'])
 cumulative = 10000
 curve = []
 for t in sorted_trades:
  cumulative += t['pnl_usdc']
  curve.append({'time': t['timestamp'][:10], 'equity': cumulative})
 return jsonify(curve)

@app.route('/api/analytics/daily')
def api_daily():
 trades = get_all_trades()
 daily = defaultdict(float)
 for t in trades:
  date = t['timestamp'][:10]
  daily[date] += t['pnl_usdc']
 return jsonify([{'date': d, 'pnl': p} for d, p in sorted(daily.items())])

@app.route('/api/analytics/distribution')
def api_distribution():
 trades = get_all_trades()
 wins = sum(1 for t in trades if t['pnl_usdc'] > 0)
 losses = sum(1 for t in trades if t['pnl_usdc'] <= 0)
 return jsonify({'wins': wins, 'losses': losses})

@app.route('/api/analytics/risk')
def api_risk():
 return jsonify({
  'accounts': [
   {'name': 'ACCOUNT BINANCE_MAIN BALANCE (btc-rolling)', 'today_loss': 0, 'daily_limit': 100, 'emergency': False},
   {'name': 'ACCOUNT OKX_SUB1 BALANCE (contract-trader)', 'today_loss': 0, 'daily_limit': 100, 'emergency': False},
   {'name': 'ACCOUNT POLYMARKET BALANCE (polymarket)', 'today_loss': 0, 'daily_limit': 100, 'emergency': False},
   {'name': 'ACCOUNT WEATHER_ALPHA BALANCE (weather-alpha-bot)', 'today_loss': 0, 'daily_limit': 100, 'emergency': False}
  ]
 })

if __name__ == '__main__':
 app.run(host='0.0.0.0', port=8081, debug=False)
