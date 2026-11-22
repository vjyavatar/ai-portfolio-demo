"""Small in-process cache. One Render instance does not share this across processes."""
from __future__ import annotations

import threading
import time
from typing import Any, Optional


class TTLCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, tuple[float, Any]] = {}

    def get(self, key: str, max_age: float) -> Optional[Any]:
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None
            stored, value = item
            if time.monotonic() - stored > max_age:
                return None
            return value

    def get_stale(self, key: str, max_age: float) -> Optional[Any]:
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None
            stored, value = item
            if time.monotonic() - stored > max_age:
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._items[key] = (time.monotonic(), value)


CACHE = TTLCache()
FETCH_LOCK = threading.Lock()
