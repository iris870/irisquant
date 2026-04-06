import asyncio
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from core.logger import setup_logger, new_trace_context
from core.priority_queue import PriorityQueue, Priority
from core.cache import LocalCache

from core.data_recorder import DataRecorder

class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.logger = setup_logger(name)
        self.recorder = DataRecorder() # 注入数据记录器 (DataRecorder injection)
        self.cache = LocalCache(default_ttl=5)
        self.stats = {"win_rate": 0.0, "trades": 0, "wins": 0, "pnl": 0.0}
        self.running = True
        self.task_queue = PriorityQueue()
        self.task_queue.logger = self.logger

    async def start(self):
        self.logger.info("agent_started", simulation=True)
        asyncio.create_task(self._run_queue())
        await self._on_start()

    async def stop(self):
        self.running = False
        self.logger.info("agent_stopped")
        if hasattr(self, "recorder"):
            self.recorder.close() # 显式释放资源 (Explicit resource release)

    async def _run_queue(self):
        while self.running:
            try:
                task = await self.task_queue.get()
                result = await task.coro
                if task.callback:
                    await task.callback(result)
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error("task_failed", error=str(e))

    async def _on_start(self):
        pass

    def update_stats(self, win: bool, pnl: float, data: dict = None):
        self.stats["trades"] += 1
        self.stats["pnl"] += pnl
        if win:
            self.stats["wins"] += 1
        if self.stats["trades"] > 0:
            self.stats["win_rate"] = self.stats["wins"] / self.stats["trades"]
        
        # 核心修复：记录交易数据到数据库 (Core Fix: Record to DB)
        if data:
            try:
                self.recorder.record_trade(self.name, data)
                self.logger.info("trade_recorded", agent=self.name, pnl=pnl)
            except Exception as e:
                self.logger.error("recording_failed", error=str(e))

        if self.stats["win_rate"] < 0.5 and self.stats["trades"] > 10:
            asyncio.create_task(self._self_optimize())

    async def _self_optimize(self):
        pass

    async def send_to_gateway(self, message: dict):
        self.logger.info("gateway_message", type=message.get("type"))

    async def call_service(self, service_name: str, payload: dict, priority: Priority = Priority.P0):
        self.logger.info("calling_service", service=service_name, priority=priority.name)
        return {"success": False, "error": "service_call_not_implemented"}
