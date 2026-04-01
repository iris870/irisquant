import asyncio
import time
from collections import deque

class RateLimiter:
    def __init__(self, config: dict):
        self.per_source_limit = config.get('per_source', 5)
        self.global_limit = config.get('global', 15)
        self.concurrency = config.get('concurrency', 3)
        self.queue_size = config.get('queue_size', 50)
        self.timeout = config.get('timeout', 5)
        self.buckets = {}
        self.global_bucket = deque()
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self.queue = asyncio.Queue(maxsize=self.queue_size)
        self.circuit_open = False
        self.error_count = 0
        self.last_error_time = 0

    async def acquire(self, source: str = "default") -> bool:
        now = time.time()
        if self.circuit_open:
            return False
        if source not in self.buckets:
            self.buckets[source] = deque()
        bucket = self.buckets[source]
        while bucket and bucket[0] < now - 1:
            bucket.popleft()
        if len(bucket) >= self.per_source_limit:
            return False
        bucket.append(now)
        while self.global_bucket and self.global_bucket[0] < now - 1:
            self.global_bucket.popleft()
        if len(self.global_bucket) >= self.global_limit:
            return False
        self.global_bucket.append(now)
        try:
            await self.semaphore.acquire()
            try:
                await asyncio.wait_for(self.queue.put(now), timeout=0.1)
            except asyncio.TimeoutError:
                self.semaphore.release()
                return False
            return True
        except:
            self.semaphore.release()
            return False

    def release(self, success: bool = True):
        self.semaphore.release()
        try:
            self.queue.get_nowait()
        except:
            pass
        if not success:
            self.error_count += 1
            self.last_error_time = time.time()
            if self.error_count > 10 and (time.time() - self.last_error_time) < 60:
                self.circuit_open = True
                asyncio.create_task(self._reset_circuit())

    async def _reset_circuit(self):
        await asyncio.sleep(60)
        self.circuit_open = False
        self.error_count = 0
