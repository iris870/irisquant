#!/usr/bin/env python3
"""
监控 Agent - 采集系统状态和 Agent 健康度
"""

import sys
import time
import json
import psutil
import logging
import subprocess
import sqlite3
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 path 中
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.data_recorder import get_recorder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MonitorAgent:
    def __init__(self, interval=60):
        self.interval = interval
        self.recorder = get_recorder()
        self.enabled = True
        self.db_path = project_root / "data" / "rl_data.db"

    def collect_system(self):
        """采集系统指标"""
        return {
            'timestamp': int(datetime.now().timestamp()),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
        }

    def check_agent(self, name):
        """检查单个 Agent 状态"""
        result = {'name': name, 'status': 'unknown', 'pid': None}

        try:
            # 通过 pm2 检查
            proc = subprocess.run(
                ['pm2', 'jlist'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc.returncode == 0:
                processes = json.loads(proc.stdout)
                for p in processes:
                    if name == p.get('name', ''):  # 精确匹配名字
                        result['status'] = p.get('pm2_env', {}).get('status', 'unknown')
                        result['pid'] = p.get('pid')
                        break

            # 降级：检查普通进程 (如果 pm2 没找到)
            if result['status'] == 'unknown':
                for p in psutil.process_iter(['pid', 'cmdline']):
                    try:
                        cmd = ' '.join(p.info['cmdline'] or [])
                        if name in cmd and "monitor_agent" not in cmd:
                            result['status'] = 'running'
                            result['pid'] = p.info['pid']
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                else:
                    result['status'] = 'stopped'

        except Exception as e:
            result['status'] = 'error'
            logger.error(f"检查 {name} 失败: {e}")

        # 记录异常事件
        if result['status'] not in ['online', 'running']:
            self.recorder.record_system_event(
                'agent_down',
                name,
                f"Status: {result['status']}"
            )

        return result

    def collect_trades(self):
        """采集交易指标"""
        try:
            # 确保数据库路径正确
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            day_ago = int(datetime.now().timestamp()) - 86400

            # 检查 trades 表是否存在
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades'")
            if not cur.fetchone():
                conn.close()
                return {'info': 'trades table not found'}

            cur.execute("""
                SELECT 
                    COUNT(*) as trade_count,
                    COALESCE(SUM(pnl), 0) as total_pnl,
                    COALESCE(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), 0) as win_count
                FROM trades
                WHERE timestamp > ?
            """, (day_ago,))

            row = cur.fetchone()
            conn.close()

            trade_count = row[0] or 0
            win_rate = row[2] / trade_count if trade_count > 0 else 0

            return {
                'daily_trades': trade_count,
                'daily_pnl': row[1],
                'win_rate': win_rate
            }
        except Exception as e:
            logger.error(f"采集交易指标失败: {e}")
            return {'error': str(e)}

    def run_once(self):
        """执行一次完整监控"""
        logger.info("开始采集监控数据...")

        # 1. 系统指标
        system = self.collect_system()
        self.recorder.record_agent_output(
            'monitor',
            'system_metrics',
            system['cpu_percent'],
            system
        )

        # 2. Agent 健康检查
        # 获取 pm2 list 中的所有 agent 名
        agents = ['leader', 'news', 'onchain', 'btc-rolling', 'contract-trader', 'polymarket', 'learning']
        agent_status = [self.check_agent(a) for a in agents]

        # 3. 交易指标
        trades = self.collect_trades()

        # 4. 异常检测
        anomalies = []
        if system['cpu_percent'] > 80:
            anomalies.append(f"CPU过高: {system['cpu_percent']}%")
        if system['memory_percent'] > 85:
            anomalies.append(f"内存过高: {system['memory_percent']}%")
        
        # 检查关键 Agent
        for a in agent_status:
            if a['status'] not in ['online', 'running'] and a['name'] in ['leader', 'news', 'btc-rolling']:
                anomalies.append(f"关键Agent离线: {a['name']} ({a['status']})")

        if trades.get('daily_pnl', 0) < -1000:
            anomalies.append(f"日亏损过大: {trades['daily_pnl']}")

        for a in anomalies:
            self.recorder.record_system_event('anomaly', 'monitor', a)

        healthy = sum(1 for a in agent_status if a['status'] in ['online', 'running'])

        logger.info(f"监控完成: 健康Agent {healthy}/{len(agents)}, 异常 {len(anomalies)}")

        return {
            'system': system,
            'agents': agent_status,
            'trades': trades,
            'anomalies': anomalies,
            'summary': {
                'healthy_agents': healthy,
                'total_agents': len(agents),
                'anomaly_count': len(anomalies)
            }
        }

    def run(self):
        """持续运行监控循环"""
        logger.info(f"启动监控循环，间隔 {self.interval} 秒")
        while self.enabled:
            try:
                self.run_once()
                time.sleep(self.interval)
            except KeyboardInterrupt:
                logger.info("收到中断信号，停止监控")
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                time.sleep(10)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='只运行一次')
    parser.add_argument('--interval', type=int, default=60, help='监控间隔（秒）')
    args = parser.parse_args()

    agent = MonitorAgent(args.interval)

    if args.once:
        result = agent.run_once()
        print(json.dumps(result, indent=2, default=str))
    else:
        agent.run()
