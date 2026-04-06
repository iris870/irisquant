#!/usr/bin/env python3
"""
协调器 (Coordinator) - IrisRL 的决策大脑
功能：监控系统状态，自动发现并重启异常 Agent，触发告警。
"""

import time
import logging
import sqlite3
import json
import re
import sys
from pathlib import Path

# 环境设置
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.data_recorder import get_recorder

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Coordinator")

class Coordinator:
    def __init__(self):
        self.recorder = get_recorder()
        self.db_path = project_root / "data" / "rl_data.db"
        self.rules = {
            'cpu_high': {'threshold': 80, 'action': 'alert'},
            'memory_high': {'threshold': 85, 'action': 'alert'},
            'agent_down': {'action': 'restart'},
            'large_loss': {'threshold': -1000, 'action': 'alert'},
        }

    def get_db_conn(self):
        return sqlite3.connect(self.db_path)

    def get_latest_monitor_data(self):
        """获取最新的系统监控指标"""
        try:
            with self.get_db_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT metadata FROM agent_outputs
                    WHERE agent_name='monitor' AND output_type='system_metrics'
                    ORDER BY timestamp DESC LIMIT 1
                """)
                row = cur.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
        except Exception as e:
            logger.error(f"获取监控数据失败: {e}")
        return {}

    def get_down_agents(self):
        """从 system_events 中获取尚未处理的 agent_down 事件"""
        down_agents = []
        try:
            with self.get_db_conn() as conn:
                cur = conn.cursor()
                # 查找未解决的 agent_down 事件
                cur.execute("""
                    SELECT id, agent_name FROM system_events
                    WHERE event_type='agent_down' AND resolved=0
                    ORDER BY timestamp DESC
                """)
                rows = cur.fetchall()
                for row in rows:
                    event_id, name = row
                    if name:
                        down_agents.append({'id': event_id, 'name': name})
        except Exception as e:
            logger.error(f"获取异常 Agent 失败: {e}")
        return down_agents

    def mark_event_resolved(self, event_id):
        """将事件标记为已解决，防止重复操作"""
        try:
            with self.get_db_conn() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE system_events SET resolved=1 WHERE id=?", (event_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"标记事件 {event_id} 失败: {e}")

    def decide(self):
        """决策逻辑：判断需要执行哪些操作"""
        decisions = []

        # 1. 检查异常 Agent (需要重启)
        down_list = self.get_down_agents()
        # 去重处理，避免同一 Agent 多个事件导致并发重启
        seen_agents = set()
        for item in down_list:
            if item['name'] not in seen_agents:
                decisions.append({
                    'action': 'restart',
                    'target': item['name'],
                    'event_id': item['id'],
                    'reason': f"检测到 {item['name']} 状态异常"
                })
                seen_agents.add(item['name'])
            else:
                # 重复的旧事件直接标记为解决
                self.mark_event_resolved(item['id'])

        # 2. 检查系统性能指标 (告警)
        metrics = self.get_latest_monitor_data()
        cpu = metrics.get('cpu_percent', 0)
        if cpu > self.rules['cpu_high']['threshold']:
            decisions.append({
                'action': 'alert',
                'target': 'system',
                'reason': f'CPU 负载过高: {cpu}%'
            })

        mem = metrics.get('memory_percent', 0)
        if mem > self.rules['memory_high']['threshold']:
            decisions.append({
                'action': 'alert',
                'target': 'system',
                'reason': f'内存占用过高: {mem}%'
            })

        return decisions

    def execute(self, decisions):
        """执行决策"""
        if not decisions:
            return []

        from agents.executor_agent import ExecutorAgent
        executor = ExecutorAgent()
        results = []

        for d in decisions:
            if d['action'] == 'restart':
                logger.info(f"🚀 正在执行重启决策: {d['target']} (原因: {d['reason']})")
                res = executor.restart_agent(d['target'])
                # 不管重启是否成功，都标记该事件已处理，如果还挂着，下一次 Monitor 会产生新事件
                self.mark_event_resolved(d['event_id'])
                results.append({**d, 'result': res})
            
            elif d['action'] == 'alert':
                logger.warning(f"⚠️ 触发告警决策: {d['reason']}")
                # 此处未来可接入 Telegram 推送
                results.append({**d, 'result': 'alerted'})

        return results

    def run_once(self):
        """执行单次决策循环"""
        decisions = self.decide()
        if decisions:
            logger.info(f"做出决策: 发现 {len(decisions)} 个待处理项")
            return self.execute(decisions)
        return []

    def run_loop(self, interval=30):
        """持续运行协调器"""
        logger.info(f"启动协调器主循环，监测间隔: {interval}s")
        while True:
            try:
                self.run_once()
                time.sleep(interval)
            except KeyboardInterrupt:
                logger.info("协调器已停止")
                break
            except Exception as e:
                logger.error(f"协调器运行异常: {e}", exc_info=True)
                time.sleep(10)

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--once', action='store_true', help="执行一次后退出")
    p.add_argument('--interval', type=int, default=30, help="循环间隔(秒)")
    args = p.parse_args()

    coordinator = Coordinator()
    if args.once:
        res = coordinator.run_once()
        print(json.dumps(res, indent=2, default=str))
    else:
        coordinator.run_loop(args.interval)
