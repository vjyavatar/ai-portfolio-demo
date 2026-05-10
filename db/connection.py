"""
r63.71.3 — Neon-resilient database connection pool for Celesys.

Neon's free tier has scale-to-zero at 5 min inactivity. When the
compute suspends, all open connections become invalid. The next
query against a stale connection crashes with:
    "server closed the connection unexpectedly"

This pool defends against that with:

  1. **Pre-ping** (configure check=ConnectionPool.check_connection): every
     borrowed connection runs `SELECT 1` first; broken ones are
     transparently replaced.

  2. **Short max_idle** (60 seconds): connections are recycled long
     before Neon's 5-minute suspend threshold, so the pool never
     holds connections through a suspend event.

  3. **max_lifetime** (10 min): hard cap so even a long-running
     connection gets recycled periodically.

  4. **Retries-friendly**: get_conn() is a context manager; if the
     transaction inside fails on a stale connection, callers get a
     clean exception they can retry once.

Usage unchanged from r63.71.2:
    from db.connection import get_conn
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
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
        from psycopg_pool import ConnectionPool
        _pool = ConnectionPool(
            conninfo=db_url,
            min_size=1,
            max_size=5,
            timeout=30,                # 30s to wait for a pool slot (Neon cold-start can be 1-3s)
            max_idle=60,               # r63.71.3: Recycle idle conns aggressively
                                       #          — must be < Neon's 300s suspend timeout
            max_lifetime=600,          # r63.71.3: Hard 10-min cap on any single conn
            reconnect_timeout=30,      # If a conn fails to reconnect, wait up to 30s
            check=ConnectionPool.check_connection,  # r63.71.3: Pre-ping every borrowed conn
            kwargs={
                # r63.72.2: autocommit=True — no COMMIT call needed, no failure
                # window during commit (which is what crashed the dryrun on
                # SSL drop). Read-heavy workloads don't need transactions.
                "autocommit": True,
                "connect_timeout": 30,
                # libpq-level keepalives — last line of defense if Neon
                # closes a connection mid-query
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 3,
                # r63.72.2: Per-statement timeout — fail loudly instead of
                # hanging if a query exceeds 5 minutes (e.g. unindexed scan)
                "options": "-c statement_timeout=300000",
            },
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


def close_pool():
    """Explicit shutdown. Called by tools at end of run."""
    global _pool
    if _pool is not None:
        try:
            _pool.close()
        except Exception:
            pass
        _pool = None
