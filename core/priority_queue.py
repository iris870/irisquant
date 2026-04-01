import asyncio
import uuid
from enum import IntEnum
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

class Priority(IntEnum):
    P0 = 0
    P1 = 1
    P2 = 2

@dataclass
class Task:
    priority: Priority
    task_id: str
    coro: Awaitable
    callback: Callable | None = None

class PriorityQueue:
    def __init__(self):
        self.queues = {p: asyncio.Queue() for p in Priority}
        self.logger = None

    async def put(self, priority: Priority, coro: Awaitable, task_id: str = None, callback=None):
        if task_id is None:
            task_id = str(uuid.uuid4())[:8]
        task = Task(priority=priority, task_id=task_id, coro=coro, callback=callback)
        await self.queues[priority].put(task)
        if self.logger:
            self.logger.debug("task_queued", task_id=task_id, priority=priority.name)

    async def get(self) -> Task:
        for p in [Priority.P0, Priority.P1, Priority.P2]:
            if not self.queues[p].empty():
                return await self.queues[p].get()
        raise asyncio.QueueEmpty
