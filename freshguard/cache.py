"""Small in-process TTL + LRU cache (carried over from the original engine.py)."""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Optional, Tuple


class TTLCache:
    def __init__(self, maxsize: int = 256, ttl_seconds: int = 900):
        self.maxsize = maxsize
        self.ttl = ttl_seconds
        self._store: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()
        self.hits = 0
        self.misses = 0

    def _purge_expired(self) -> None:
        now = time.monotonic()
        for k in [k for k, (ts, _) in self._store.items() if now - ts >= self.ttl]:
            del self._store[k]

    def get(self, key: str, default: Any = None) -> Optional[Any]:
        item = self._store.get(key)
        if item is not None:
            ts, val = item
            if time.monotonic() - ts < self.ttl:
                self._store.move_to_end(key)
                self.hits += 1
                return val
            del self._store[key]
        self.misses += 1
        return default

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)
        self._store.move_to_end(key)
        while len(self._store) > self.maxsize:
            self._store.popitem(last=False)

    def clear(self) -> int:
        n = len(self._store)
        self._store.clear()
        return n

    def size(self) -> int:
        self._purge_expired()
        return len(self._store)

    def __len__(self) -> int:
        return self.size()
