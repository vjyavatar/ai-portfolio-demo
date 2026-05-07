"""
r63.71 — Database connection pool for Celesys positioning data.

Lazily initializes a psycopg connection pool against NEON_DATABASE_URL.
Importing this module does NOT open connections — that happens on first
get_pool() call. This keeps the existing Celesys boot path unaffected
when the env var is missing (e.g. local dev without DB).

Usage:
    from db.connection import get_conn

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
"""

import os
import threading
from contextlib import contextmanager
from typing import Optional

_pool = None
_pool_lock = threading.Lock()
_pool_init_error: Optional[str] = None


def _init_pool():
    """Create the connection pool. Called once, lazily."""
    global _pool, _pool_init_error
    db_url = os.environ.get("NEON_DATABASE_URL", "").strip()
    if not db_url:
        _pool_init_error = "NEON_DATABASE_URL not set"
        return
    try:
        # Use psycopg_pool (separate package from psycopg)
        from psycopg_pool import ConnectionPool
        _pool = ConnectionPool(
            conninfo=db_url,
            min_size=1,
            max_size=5,
            timeout=10,             # seconds to wait for a connection from pool
            max_idle=300,           # close idle conns after 5 min (Neon scales-to-zero friendly)
            kwargs={"autocommit": False},
            open=True,
        )
    except ImportError:
        _pool_init_error = "psycopg_pool not installed; pip install 'psycopg[binary,pool]'"
    except Exception as e:
        _pool_init_error = f"pool init failed: {e}"


def get_pool():
    """Return the global pool, initializing on first call. May return None."""
    global _pool
    if _pool is None and _pool_init_error is None:
        with _pool_lock:
            if _pool is None and _pool_init_error is None:
                _init_pool()
    return _pool


@contextmanager
def get_conn():
    """Context manager yielding a pooled connection. Raises if pool unavailable."""
    pool = get_pool()
    if pool is None:
        raise RuntimeError(
            f"Database not available: {_pool_init_error or 'unknown'}"
        )
    with pool.connection() as conn:
        yield conn


def health_check() -> dict:
    """Lightweight check used by api.py boot logging. Never raises."""
    pool = get_pool()
    if pool is None:
        return {"ok": False, "reason": _pool_init_error or "pool not initialized"}
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "reason": f"query failed: {e}"}
