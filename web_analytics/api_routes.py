import os
import sqlite3
import re
from datetime import datetime

# 配置路径
DB_PATH = '/root/irisquant/data/knowledge.db'
WEATHER_LOG_PATH = '/root/weather-alpha/logs/weather_alpha.log'

# 账户完整名称映射
ACCOUNT_MAPPING = {
    'btc-rolling': 'ACCOUNT BINANCE_MAIN BALANCE (btc-rolling)',
    'contract-trader': 'ACCOUNT OKX_SUB1 BALANCE (contract-trader)',
    'polymarket': 'ACCOUNT POLYMARKET BALANCE (polymarket)',
    'weather-alpha': 'ACCOUNT WEATHER_ALPHA BALANCE (weather-alpha-bot)'
}

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def parse_weather_logs():
    """解析 weather_alpha.log 中的 DRY_RUN 记录"""
    trades = []
    if not os.path.exists(WEATHER_LOG_PATH):
        return trades
    
    # 示例日志行: 2026-04-05 15:30:01 - INFO - [DRY_RUN] ORDER: BUY 10.0 NYC-PRECIP @ 0.45 (Edge: 0.12)
    # 我们将其模拟为交易记录展示
    try:
        with open(WEATHER_LOG_PATH, 'r') as f:
            for line in f:
                if '[DRY_RUN]' in line:
                    parts = line.split(' - ')
                    timestamp = parts[0]
                    content = parts[-1]
                    
                    # 提取关键信息
                    match = re.search(r'ORDER: (\w+) ([\d.]+) ([\w-]+) @ ([\d.]+)', content)
                    if match:
                        direction, size, market, price = match.groups()
                        trades.append({
                            'timestamp': timestamp,
                            'agent': 'weather-alpha',
                            'account_name': ACCOUNT_MAPPING['weather-alpha'],
                            'market': market,
                            'side': direction,
                            'amount': float(size),
                            'pnl': 0.0, # 模拟盘暂不计算实时盈亏
                            'status': '模拟交易'
                        })
    except Exception as e:
        print(f"Error parsing weather logs: {e}")
    
    return sorted(trades, key=lambda x: x['timestamp'], reverse=True)

def get_account_summary(agent=None):
    """获取账户汇总信息"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM trades"
    params = []
    if agent:
        query += " WHERE agent = ?"
        params.append(agent)
    
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    # 转换为列表并附加完整名称
    trades = []
    for row in rows:
        agent_id = row['agent']
        trades.append({
            'timestamp': row['timestamp'],
            'agent': agent_id,
            'account_name': ACCOUNT_MAPPING.get(agent_id, agent_id),
            'market': row['market'],
            'side': row['side'],
            'amount': row['amount'],
            'pnl': row['pnl'],
            'status': '模拟交易'
        })
    
    # 如果包含天气机器人，合并日志数据
    if not agent or agent == 'weather-alpha':
        trades.extend(parse_weather_logs())
        
    return sorted(trades, key=lambda x: x['timestamp'], reverse=True)
