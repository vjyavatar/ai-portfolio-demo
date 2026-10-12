"""Bounded per-process cache for legacy Yahoo adapters; never extends source times.

This reduces duplicate yfinance work. It is not a feed entitlement, a distributed
cache, or a replacement for the separately guarded Trading Desk transport.
"""
from collections import OrderedDict
from copy import deepcopy
import threading
import time


class RequestCache:
    def __init__(self, capacity=128, clock=time.monotonic, wait_seconds=12):
        self.capacity = capacity
        self.clock = clock
        self.wait_seconds = wait_seconds
        self.lock = threading.Lock()
        self.entries = OrderedDict()
        self.pending = {}
        self.cooldown_until = 0
        self.counts = dict(hits=0, loads=0, coalesced=0, failures=0, cooldown_skips=0)

    def get(self, key, loader, ttl=60, default=None):
        with self.lock:
            now = self.clock()
            hit = self.entries.get(key)
            if hit and now < hit[0]:
                self.entries.move_to_end(key)
                self.counts['hits'] += 1
                return deepcopy(hit[1])
            if now < self.cooldown_until:
                self.counts['cooldown_skips'] += 1
                return deepcopy(default)
            event = self.pending.get(key)
            owner = event is None
            if owner:
                event = self.pending[key] = threading.Event()
                self.counts['loads'] += 1
            else:
                self.counts['coalesced'] += 1
        if not owner:
            event.wait(self.wait_seconds)
            with self.lock:
                hit = self.entries.get(key)
                return deepcopy(hit[1]) if hit and self.clock() < hit[0] else deepcopy(default)
        value = default
        lifetime = ttl
        try:
            value = loader()
            empty = value is None or getattr(value, 'empty', False) or (isinstance(value, (dict, list, tuple)) and not value)
            if empty:
                value = default
                lifetime = 15
        except Exception as exc:
            lifetime = 15
            # Never persist or expose provider exception text or credentials.
            limited = '429' in str(exc) or 'rate limit' in str(exc).lower() or 'ratelimit' in type(exc).__name__.lower()
            with self.lock:
                self.counts['failures'] += 1
                if limited:
                    self.cooldown_until = max(self.cooldown_until, self.clock() + 300)
        finally:
            with self.lock:
                try:
                    self.entries[key] = (self.clock() + lifetime, deepcopy(value))
                    self.entries.move_to_end(key)
                    while len(self.entries) > self.capacity:
                        self.entries.popitem(last=False)
                finally:
                    self.pending.pop(key, None)
                    event.set()
        return deepcopy(value)

    def snapshot(self):
        with self.lock:
            return dict(self.counts, entries=len(self.entries), in_flight=len(self.pending),
                        cooldown_seconds=max(0, self.cooldown_until-self.clock()),
                        scope='Legacy SafeTicker / one server process')


legacy_cache = RequestCache()
