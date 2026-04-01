import asyncio
import sys
import os
import structlog
from datetime import datetime

# 基础路径配置
file_path = os.path.abspath(__file__)
agents_dir = os.path.dirname(file_path)
root_dir = os.path.dirname(agents_dir)

# 确保项目根目录在 sys.path 中
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# 调试导入
try:
    from agents.base import BaseAgent
    print("Successfully imported agents.base")
    from simulation.exchange_sim import sim_exchange
    print(f"Successfully imported sim_exchange: {type(sim_exchange)}")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    sys.exit(1)

class LeaderAgent(BaseAgent):
    def __init__(self):
        super().__init__("leader")
        # 强制配置 structlog 以确保 stdlib.LoggerFactory 能工作
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(), # 降级使用 print 记录，避免 stdlib 未配置的错误
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        self.accounts = {
            "A": {"balance": 10000, "daily_pnl": 0, "risk": "low"},
            "B": {"balance": 50000, "daily_pnl": 0, "risk": "low"},
            "C": {"balance": 2000, "daily_pnl": 0, "risk": "low"}
        }
        self.start_time = datetime.now()

    async def _on_start(self):
        print("DEBUG: _on_start called")
        asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        print("DEBUG: _monitor_loop started")
        while self.running:
            try:
                for acc_id in self.accounts:
                    status = await sim_exchange.fetch_balance(acc_id)
                    self.accounts[acc_id]["balance"] = status["total"]
                    self.accounts[acc_id]["daily_pnl"] = status["daily_pnl"]
                    if abs(status["daily_pnl"]) > 500:
                        self.accounts[acc_id]["risk"] = "high"
                    elif abs(status["daily_pnl"]) > 200:
                        self.accounts[acc_id]["risk"] = "medium"
                    else:
                        self.accounts[acc_id]["risk"] = "low"
                
                # 打印当前状态到 stdout，方便 PM2 日志查看
                print(f"[{datetime.now().isoformat()}] Monitoring: {self.accounts}")
                self.logger.info("monitor", accounts=self.accounts)
            except Exception as e:
                print(f"ERROR in _monitor_loop: {e}")
                self.logger.error("monitor_loop_failed", error=str(e))
            await asyncio.sleep(5)

async def main():
    print("DEBUG: main() called")
    agent = LeaderAgent()
    print(f"DEBUG: agent {agent.name} created")
    await agent.start()
    print("DEBUG: agent.start() completed")
    try:
        while True:
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.telegram import send_alert

def check_risk():
    # ... hypothetical risk logic ...
    loss_percent = 5.1 # Example trigger
    if loss_percent >= 5:
        send_alert(f"⚠️ <b>[Leader]</b> Risk Alert: Daily loss reached {loss_percent}%")

if __name__ == "__main__":
    print("ENTRY: Starting __main__")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("ENTRY: KeyboardInterrupt")
    except Exception as e:
        print(f"ENTRY ERROR: {e}")
