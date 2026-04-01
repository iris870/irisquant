import time
from typing import Any, Dict

class LocalCache:
    def __init__(self, default_ttl: int = 5):
        self._cache: Dict[str, tuple] = {}
        self.default_ttl = default_ttl

    def set(self, key: str, value: Any, ttl: int = None):
        if ttl is None:
            ttl = self.default_ttl
        self._cache[key] = (value, time.time() + ttl)

    def get(self, key: str) -> Any:
        if key in self._cache:
            value, expire = self._cache[key]
            if time.time() < expire:
                return value
            del self._cache[key]
        return None

    def clear(self):
        self._cache.clear()
