"""Angel session proxy and login. No network, no real secrets."""
import base64
import json
import os
import unittest
from datetime import datetime
from unittest.mock import call, patch
import requests
from urllib.error import HTTPError

import angel_options as options
import angel_session as session

PROXY = "http://user:pass@139.59.38.68:8888"
API = {
    "CELESYS_ANGEL_API_KEY": "api-key",
    "CELESYS_ANGEL_CLIENT_LOCAL_IP": "10.0.0.8",
    "CELESYS_ANGEL_MAC_ADDRESS": "00:11:22:33:44:55",
    "CELESYS_ANGEL_CLIENT_CODE": "A123",
    "CELESYS_ANGEL_PIN": "998877",
    "CELESYS_ANGEL_TOTP_SECRET": "JBSWY3DPEHPK3PXP",
}


class Response:
    def __init__(self, status, payload, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self.content = json.dumps(payload).encode()


class FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


class AngelSessionTests(unittest.TestCase):
    def setUp(self):
        session.reset_for_tests()

    def test_public_ip_defaults_only_when_proxy_is_set(self):
        with patch.dict(os.environ, {"CELESYS_ANGEL_PROXY_URL": PROXY}, clear=True):
            self.assertEqual(session.public_ip(), "139.59.38.68")
        with patch.dict(os.environ, {"CELESYS_ANGEL_PROXY_URL": PROXY, "CELESYS_ANGEL_CLIENT_PUBLIC_IP": "192.0.2.9"}, clear=True):
            self.assertEqual(session.public_ip(), "192.0.2.9")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(session.public_ip(), "")

    def test_proxy_default_satisfies_configuration(self):
        env = {
            "CELESYS_ANGEL_API_KEY": "api-key",
            "CELESYS_ANGEL_JWT_TOKEN": "static-jwt",
            "CELESYS_ANGEL_CLIENT_LOCAL_IP": "10.0.0.8",
            "CELESYS_ANGEL_MAC_ADDRESS": "00:11:22:33:44:55",
            "CELESYS_ANGEL_PROXY_URL": PROXY,
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(options.configured())
            self.assertEqual(options._headers()["X-ClientPublicIP"], "139.59.38.68")
            self.assertEqual(options._headers()["Authorization"], "Bearer static-jwt")

    def test_static_jwt_used_when_login_vars_absent(self):
        env = {
            "CELESYS_ANGEL_API_KEY": "api-key",
            "CELESYS_ANGEL_JWT_TOKEN": "static-jwt",
            "CELESYS_ANGEL_CLIENT_LOCAL_IP": "10.0.0.8",
            "CELESYS_ANGEL_CLIENT_PUBLIC_IP": "192.0.2.1",
            "CELESYS_ANGEL_MAC_ADDRESS": "00:11:22:33:44:55",
            "CELESYS_ANGEL_CLIENT_CODE": "ONLY-ONE",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(session.login_configured())
            self.assertEqual(session.jwt_token(), "static-jwt")
            self.assertTrue(options.configured())

    def test_login_posts_totp_through_proxy_and_caches_jwt(self):
        issued = {"status": True, "data": {"jwtToken": "minted-jwt"}}
        http = FakeHttp([Response(200, issued)])
        now = datetime(2026, 11, 22, 9, 0, tzinfo=session.IST)
        with patch.dict(os.environ, {**API, "CELESYS_ANGEL_PROXY_URL": PROXY, "CELESYS_ANGEL_JWT_TOKEN": "static-jwt"}, clear=True), \
             patch.object(session, "_http", return_value=http):
            first = session.jwt_token(now=now)
            second = session.jwt_token(now=now)
        self.assertEqual(first, "minted-jwt")
        self.assertEqual(second, "minted-jwt")
        self.assertEqual(len(http.calls), 1)
        method, url, kwargs = http.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, session.LOGIN_URL)
        self.assertEqual(kwargs["proxies"], {"http": PROXY, "https": PROXY})
        body = json.loads(kwargs["data"].decode())
        self.assertEqual(body["clientcode"], "A123")
        self.assertEqual(body["password"], "998877")
        import pyotp
        totp = pyotp.TOTP(API["CELESYS_ANGEL_TOTP_SECRET"])
        self.assertIn(body["totp"], {totp.now(), totp.at(int(__import__("time").time()) - 30)})
        self.assertNotIn("static-jwt", kwargs["headers"].get("Authorization", ""))

    def test_daily_boundary_and_expiry_force_another_login(self):
        http = FakeHttp([
            Response(200, {"status": True, "data": {"jwtToken": "morning"}}),
            Response(200, {"status": True, "data": {"jwtToken": "next-morning"}}),
            Response(200, {"status": True, "data": {"jwtToken": "after-expiry"}}),
        ])
        early = datetime(2026, 11, 22, 8, 0, tzinfo=session.IST)
        later = datetime(2026, 11, 22, 8, 30, tzinfo=session.IST)
        with patch.dict(os.environ, API, clear=True), patch.object(session, "_http", return_value=http):
            self.assertEqual(session.next_daily_refresh(early), datetime(2026, 11, 22, 8, 30, tzinfo=session.IST))
            self.assertEqual(session.jwt_token(now=early), "morning")
            self.assertEqual(session.jwt_token(now=later), "next-morning")
        self.assertEqual(len(http.calls), 2)
        past = datetime(2026, 11, 22, 10, 0, tzinfo=session.IST)
        expired = "h." + base64.urlsafe_b64encode(json.dumps({"exp": int(past.timestamp()) - 10}).encode()).decode().rstrip("=") + ".s"
        session._state["token"] = expired
        session._state["refresh_at"] = datetime(2026, 11, 23, 8, 30, tzinfo=session.IST)
        self.assertTrue(session.token_expired(expired, past))
        with patch.dict(os.environ, API, clear=True), patch.object(session, "_http", return_value=http):
            self.assertEqual(session.jwt_token(now=past), "after-expiry")
        self.assertEqual(len(http.calls), 3)

    def test_non_angel_url_is_not_sent_and_proxy_failure_hides_credentials(self):
        http = FakeHttp([])
        with patch.dict(os.environ, {"CELESYS_ANGEL_PROXY_URL": PROXY}, clear=True), patch.object(session, "_http", return_value=http):
            with self.assertRaises(ValueError):
                session.request_json("https://query1.finance.yahoo.com/v8/finance/chart/AAPL")
            self.assertEqual(http.calls, [])
            def explode(*args, **kwargs):
                raise requests.RequestException("http://user:s3cret@139.59.38.68:8888 down")
            http.request = explode
            with self.assertRaises(ValueError) as caught:
                session.request_json(session.LOGIN_URL, payload={"clientcode": "A"})
        self.assertEqual(str(caught.exception), "Angel request failed")
        self.assertNotIn("s3cret", str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)

    def test_order_route_on_angel_host_uses_the_proxy(self):
        http = FakeHttp([Response(200, {"status": True})])
        url = "https://apiconnect.angelone.in/rest/secure/angelbroking/order/v1/placeOrder"
        with patch.dict(os.environ, {"CELESYS_ANGEL_PROXY_URL": PROXY}, clear=True), patch.object(session, "_http", return_value=http):
            session.request_json(url, payload={"variety": "NORMAL"})
        self.assertEqual(http.calls[0][1], url)
        self.assertEqual(http.calls[0][2]["proxies"]["https"], PROXY)

    def test_quote_401_refreshes_jwt_once(self):
        calls = {"n": 0}

        def fake(url, payload=None, headers=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise session.Unauthorized()
            return {"status": True, "data": {"fetched": []}}

        with patch.dict(os.environ, {**API, "CELESYS_ANGEL_CLIENT_PUBLIC_IP": "192.0.2.1"}, clear=True), \
             patch.object(session, "request_json", side_effect=fake), \
             patch.object(session, "jwt_token", return_value="minted") as token:
            result = options._request(options.QUOTE_URL, {"mode": "FULL"})
        self.assertEqual(result["status"], True)
        self.assertEqual(calls["n"], 2)
        self.assertIn(call(force=True), token.call_args_list)

    def test_login_rejection_does_not_echo_the_provider_message(self):
        http = FakeHttp([Response(200, {"status": False, "message": "bad pin 998877", "data": {}})])
        with patch.dict(os.environ, API, clear=True), patch.object(session, "_http", return_value=http):
            with self.assertRaises(ValueError) as caught:
                session.jwt_token(now=datetime(2026, 11, 22, 9, 0, tzinfo=session.IST))
        self.assertEqual(str(caught.exception), "Angel login rejected")
        self.assertNotIn("998877", str(caught.exception))

    def test_invalid_proxy_does_not_fall_open(self):
        http = FakeHttp([])
        with patch.dict(os.environ, {"CELESYS_ANGEL_PROXY_URL": "not a proxy"}, clear=True), patch.object(session, "_http", return_value=http):
            with self.assertRaises(ValueError):
                session.request_json(session.LOGIN_URL, payload={})
        self.assertEqual(http.calls, [])

    def test_refresh_loop_survives_a_login_error(self):
        seen = []

        def sleep(seconds):
            seen.append(seconds)
            return len(seen) > 1

        def fail(force=False):
            raise ValueError("pin 998877 rejected")

        with patch.dict(os.environ, API, clear=True), patch.object(session, "login_configured", return_value=True), \
             patch.object(session, "jwt_token", side_effect=fail), self.assertLogs("angel_session", level="WARNING") as logs:
            session.run_refresh_loop(session._stop, sleep)
        self.assertEqual(len(seen), 2)
        text = "\n".join(logs.output)
        self.assertIn("Angel session refresh failed", text)
        self.assertIn("ValueError", text)
        self.assertNotIn("998877", text)
        self.assertFalse(session.login_status()["ok"])
        self.assertNotIn("998877", session.login_status()["error"])

    def test_probe_logs_success_once_and_records_status(self):
        with patch.dict(os.environ, API, clear=True), patch.object(session, "jwt_token", return_value="minted") as token, \
             self.assertLogs("angel_session", level="INFO") as logs:
            session.probe_login()
        token.assert_called_once_with(force=True)
        self.assertTrue(session.login_status()["ok"])
        self.assertIsNone(session.login_status()["error"])
        self.assertEqual(sum("Angel login ok" in line for line in logs.output), 1)

    def test_probe_failure_redacts_secrets(self):
        def fail(force=False):
            raise ValueError("bad pin 998877 totp JBSWY3DPEHPK3PXP")

        with patch.dict(os.environ, API, clear=True), patch.object(session, "jwt_token", side_effect=fail), \
             self.assertLogs("angel_session", level="WARNING") as logs:
            session.probe_login()
        text = "\n".join(logs.output)
        self.assertIn("Angel login failed", text)
        self.assertIn("ValueError", text)
        self.assertNotIn("998877", text)
        self.assertNotIn("JBSWY3DPEHPK3PXP", text)
        self.assertNotIn("998877", session.login_status()["error"])
        self.assertFalse(session.login_status()["ok"])

    def test_probe_skips_when_login_is_not_configured(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(session, "jwt_token") as token:
            session.probe_login()
        token.assert_not_called()
        self.assertIsNone(session.login_status()["ok"])
        self.assertIsNone(session.login_status()["error"])

    def test_login_probe_thread_does_not_block_startup(self):
        import threading
        started = threading.Event()
        release = threading.Event()

        def hang(force=False):
            started.set()
            release.wait(2)
            return "minted"

        session._probe_thread = None
        with patch.dict(os.environ, API, clear=True), patch.object(session, "jwt_token", side_effect=hang):
            session.ensure_login_probe()
            self.assertTrue(started.wait(1))
        self.assertTrue(session._probe_thread.daemon)
        release.set()
        session._probe_thread.join(2)
        self.assertTrue(session.login_status()["ok"])

    def test_session_transport_ignores_generic_proxy_env(self):
        session._session = None
        client = session._http()
        self.assertFalse(client.trust_env)

    def test_other_provider_modules_do_not_read_the_angel_proxy(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        offenders = []
        for path in root.rglob("*.py"):
            if path.name in {"angel_session.py", "test_trading_angel_session.py"}:
                continue
            if "CELESYS_ANGEL_PROXY_URL" in path.read_text(encoding="utf-8", errors="ignore"):
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_quote_401_without_login_vars_does_not_loop(self):
        env = {
            "CELESYS_ANGEL_API_KEY": "api-key",
            "CELESYS_ANGEL_JWT_TOKEN": "static-jwt",
            "CELESYS_ANGEL_CLIENT_LOCAL_IP": "10.0.0.8",
            "CELESYS_ANGEL_CLIENT_PUBLIC_IP": "192.0.2.1",
            "CELESYS_ANGEL_MAC_ADDRESS": "00:11:22:33:44:55",
        }
        with patch.dict(os.environ, env, clear=True), patch.object(session, "request_json", side_effect=session.Unauthorized()):
            with self.assertRaises(HTTPError) as caught:
                options._request(options.QUOTE_URL, {"mode": "FULL"})
        self.assertEqual(caught.exception.code, 401)


if __name__ == "__main__":
    unittest.main()
