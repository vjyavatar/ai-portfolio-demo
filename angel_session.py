"""Angel One SmartAPI session and transport.

Every SmartAPI call — loginByPassword, quotes, the instrument master, and any
order route on the Angel hosts — goes through request_json. The static-IP
proxy is applied only here. Other market providers never see it.

The JWT stays in memory. It is not written to disk or logs.
"""
from __future__ import annotations

import base64
import json
import os
import threading
from datetime import datetime, timedelta
from urllib.error import HTTPError
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import pyotp
import requests

IST = ZoneInfo("Asia/Kolkata")
STATIC_EGRESS_IP = "139.59.38.68"
LOGIN_URL = "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword"
_ANGEL_HOSTS = frozenset({"apiconnect.angelone.in", "margincalculator.angelbroking.com"})
_LOGIN_ENV = ("CELESYS_ANGEL_CLIENT_CODE", "CELESYS_ANGEL_PIN", "CELESYS_ANGEL_TOTP_SECRET")
_DAILY_HOUR = 8
_DAILY_MINUTE = 30

_lock = threading.Lock()
_session_lock = threading.Lock()
_state = {"token": "", "refresh_at": None}
_stop = threading.Event()
_thread = None
_session = None


class Unauthorized(Exception):
    """Bearer token was rejected. The message is intentionally empty."""


def _clean(name: str) -> str:
    return os.getenv(name, "").strip()


def proxy_url() -> str:
    return _clean("CELESYS_ANGEL_PROXY_URL")


def proxy_mapping() -> dict:
    """Return a requests proxies dict, or {} when no proxy is configured.

    An invalid proxy URL fails closed. Calls are not sent directly by mistake.
    """
    raw = proxy_url()
    if not raw:
        return {}
    if any(char in raw for char in "\r\n\x00 "):
        raise ValueError("Angel proxy URL is invalid")
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.hostname or not parts.port:
        raise ValueError("Angel proxy URL is invalid")
    return {"http": raw, "https": raw}


def public_ip() -> str:
    explicit = _clean("CELESYS_ANGEL_CLIENT_PUBLIC_IP")
    if explicit:
        return explicit
    if proxy_url():
        return STATIC_EGRESS_IP
    return ""


def login_configured() -> bool:
    values = [_clean(name) for name in _LOGIN_ENV]
    if not all(values):
        return False
    return not any("\r" in value or "\n" in value for value in values)


def is_angel_url(url: str) -> bool:
    return urlsplit(url).hostname in _ANGEL_HOSTS


def _http() -> requests.Session:
    """A session that ignores HTTP_PROXY so only CELESYS_ANGEL_PROXY_URL applies."""
    global _session
    with _session_lock:
        if _session is None:
            session = requests.Session()
            session.trust_env = False
            _session = session
        return _session


def request_json(url: str, *, payload=None, headers=None, timeout: int = 15):
    """POST or GET an Angel URL. Non-Angel hosts are rejected before any socket opens."""
    if not is_angel_url(url):
        raise ValueError("Unsupported provider resource")
    proxies = proxy_mapping()
    data = None if payload is None else json.dumps(payload).encode()
    try:
        response = _http().request(
            "POST" if payload is not None else "GET",
            url,
            headers=headers or {},
            data=data,
            timeout=timeout,
            allow_redirects=False,
            proxies=proxies or None,
        )
    except requests.RequestException:
        raise ValueError("Angel request failed") from None
    if 300 <= response.status_code < 400:
        raise ValueError("Provider redirect rejected")
    if response.status_code == 401:
        raise Unauthorized()
    if response.status_code >= 400:
        raise HTTPError(url, response.status_code, "provider", dict(response.headers), None)
    raw = response.content or b""
    cap = 64_000_000 if "OpenAPIScripMaster" in url else 2_000_000
    if len(raw) > cap:
        raise ValueError("Oversized provider response")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("Angel response was not JSON") from None


def _jwt_payload(token: str) -> dict:
    try:
        segment = token.split(".")[1]
        segment += "=" * (-len(segment) % 4)
        data = json.loads(base64.urlsafe_b64decode(segment.encode()))
    except (IndexError, ValueError, json.JSONDecodeError, UnicodeError):
        return {}
    return data if isinstance(data, dict) else {}


def token_expired(token: str, now: datetime, skew_seconds: int = 120) -> bool:
    exp = _jwt_payload(token).get("exp")
    if not isinstance(exp, (int, float)):
        return False
    return now.timestamp() >= float(exp) - skew_seconds


def next_daily_refresh(now: datetime) -> datetime:
    """Next 08:30 IST. A login at or after 08:30 waits until the following morning."""
    local = now.astimezone(IST)
    target = local.replace(hour=_DAILY_HOUR, minute=_DAILY_MINUTE, second=0, microsecond=0)
    if local >= target:
        target += timedelta(days=1)
    return target


def _login() -> str:
    secret = _clean("CELESYS_ANGEL_TOTP_SECRET").replace(" ", "")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-UserType": "USER",
        "X-SourceID": "WEB",
        "X-ClientLocalIP": _clean("CELESYS_ANGEL_CLIENT_LOCAL_IP"),
        "X-ClientPublicIP": public_ip(),
        "X-MACAddress": _clean("CELESYS_ANGEL_MAC_ADDRESS"),
        "X-PrivateKey": _clean("CELESYS_ANGEL_API_KEY"),
    }
    body = {
        "clientcode": _clean("CELESYS_ANGEL_CLIENT_CODE"),
        "password": _clean("CELESYS_ANGEL_PIN"),
        "totp": pyotp.TOTP(secret).now(),
    }
    data = request_json(LOGIN_URL, payload=body, headers=headers)
    token = ""
    if isinstance(data, dict):
        nested = data.get("data")
        if isinstance(nested, dict):
            token = str(nested.get("jwtToken") or "").strip()
        if not data.get("status") or not token:
            raise ValueError("Angel login rejected")
        return token
    raise ValueError("Angel login rejected")


def jwt_token(force: bool = False, now: datetime | None = None) -> str:
    """In-memory JWT from loginByPassword, or the static env token when login vars are absent."""
    if not login_configured():
        return _clean("CELESYS_ANGEL_JWT_TOKEN")
    moment = (now or datetime.now(IST)).astimezone(IST)
    with _lock:
        token = _state["token"]
        refresh_at = _state["refresh_at"]
        usable = bool(token) and isinstance(refresh_at, datetime) and moment < refresh_at and not token_expired(token, moment)
        if usable and not force:
            return token
    fresh = _login()
    with _lock:
        _state["token"] = fresh
        _state["refresh_at"] = next_daily_refresh(moment)
        return fresh


def reset_for_tests() -> None:
    with _lock:
        _state["token"] = ""
        _state["refresh_at"] = None


def seconds_until_daily_refresh(now: datetime) -> float:
    return max(1.0, (next_daily_refresh(now) - now.astimezone(IST)).total_seconds())


def run_refresh_loop(stop: threading.Event, sleep) -> None:
    """sleep(seconds) should return True when the loop must stop."""
    while not stop.is_set():
        if sleep(seconds_until_daily_refresh(datetime.now(IST))):
            return
        if login_configured():
            try:
                jwt_token(force=True)
            except Exception:
                pass


def ensure_daily_refresh() -> None:
    """Daemon thread: re-login around 08:30 IST when the login env vars are set."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _thread = threading.Thread(
            target=run_refresh_loop,
            args=(_stop, _stop.wait),
            name="angel-session-refresh",
            daemon=True,
        )
        _thread.start()
