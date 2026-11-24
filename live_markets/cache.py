"""Bounded per-process cache for public market-board snapshots.

Keep fresh data for its short provider TTL and stale snapshots for at most
30 minutes. Avoid retaining arbitrary user-symbol and chain payloads forever.
"""
from __future__ import annotations

from collections import OrderedDict
import threading
import time
from typing import Any, Optional


class TTLCache:
    def __init__(self, max_entries: int = 128, retention_seconds: float = 1800) -> None:
        if max_entries < 1 or retention_seconds <= 0:
            raise ValueError("Cache limits must be positive")
        self._lock = threading.Lock()
        self._items: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max_entries = max_entries
        self._retention_seconds = retention_seconds

    def _read(self, key: str, max_age: float) -> Optional[Any]:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            stored, value = item
            age = time.monotonic() - stored
            if age > max_age:
                if age > self._retention_seconds:
                    self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return value

    def get(self, key: str, max_age: float) -> Optional[Any]:
        return self._read(key, max_age)

    def get_stale(self, key: str, max_age: float) -> Optional[Any]:
        return self._read(key, max_age)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            now = time.monotonic()
            # Evict fully expired snapshots before applying the capacity limit.
            expired = [item_key for item_key, (stored, _) in self._items.items()
                       if now - stored > self._retention_seconds]
            for item_key in expired:
                self._items.pop(item_key, None)
            self._items[key] = (now, value)
            self._items.move_to_end(key)
            while len(self._items) > self._max_entries:
                self._items.popitem(last=False)


CACHE = TTLCache()
FETCH_LOCK = threading.Lock()
