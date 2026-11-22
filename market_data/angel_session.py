"""Angel One SmartAPI session lifecycle; authentication only, no order APIs.

TOTP is generated in-process from a Render secret. Never log credentials or tokens.
"""
from __future__ import annotations

import os
from typing import Optional

import pyotp
import requests


class AngelOneSession:
    LOGIN_URL = "https://apiconnect.angelone.in/rest/auth/angelbroking/user/v1/loginByPassword"
    REFRESH_URL = "https://apiconnect.angelone.in/rest/auth/angelbroking/jwt/v1/generateTokens"
    PROFILE_URL = "https://apiconnect.angelone.in/rest/secure/angelbroking/user/v1/getProfile"

    def __init__(self, session: Optional[requests.Session] = None):
        self.api_key = os.getenv("CELESYS_ANGEL_API_KEY", "").strip()
        self.client_code = os.getenv("CELESYS_ANGEL_CLIENT_CODE", "").strip()
        self.pin = os.getenv("CELESYS_ANGEL_PIN", "").strip()
        self.totp_secret = os.getenv("CELESYS_ANGEL_TOTP_SECRET", "").replace(" ", "").strip()
        self.local_ip = os.getenv("CELESYS_ANGEL_CLIENT_LOCAL_IP", "").strip()
        self.public_ip = os.getenv("CELESYS_ANGEL_CLIENT_PUBLIC_IP", "").strip()
        self.mac = os.getenv("CELESYS_ANGEL_MAC_ADDRESS", "").strip()
        self.http = session or requests.Session()
        self.jwt: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.feed_token: Optional[str] = None

    @property
    def configured(self) -> bool:
        return all((self.api_key, self.client_code, self.pin, self.totp_secret,
                    self.local_ip, self.public_ip, self.mac))

    def _headers(self) -> dict:
        if not self.api_key:
            raise RuntimeError("Angel One API key is not configured")
        return {
            "Content-Type": "application/json", "Accept": "application/json",
            "X-PrivateKey": self.api_key, "X-ClientLocalIP": self.local_ip,
            "X-ClientPublicIP": self.public_ip, "X-MACAddress": self.mac,
            "X-UserType": "USER", "X-SourceID": "WEB",
        }

    def _post(self, url: str, payload: dict, authenticated: bool = False) -> dict:
        headers = self._headers()
        if authenticated:
            if not self.jwt:
                raise RuntimeError("Angel One session is not authenticated")
            headers["Authorization"] = "Bearer " + self.jwt
        response = self.http.post(url, json=payload, headers=headers, timeout=(3.05, 12))
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or data.get("status") is not True:
            raise RuntimeError("Angel One authentication/provider request rejected")
        return data

    def login(self) -> None:
        if not self.configured:
            raise RuntimeError("Angel One credentials are not configured")
        payload = self._post(self.LOGIN_URL, {
            "clientcode": self.client_code, "password": self.pin,
            "totp": pyotp.TOTP(self.totp_secret).now(),
        })
        result = payload.get("data") or {}
        self.jwt = result.get("jwtToken")
        self.refresh_token = result.get("refreshToken")
        self.feed_token = result.get("feedToken")
        if not all((self.jwt, self.refresh_token, self.feed_token)):
            self.close()
            raise RuntimeError("Angel One login response omitted required session tokens")

    def refresh(self) -> None:
        if not self.refresh_token:
            raise RuntimeError("Angel One refresh token is unavailable")
        payload = self._post(self.REFRESH_URL, {"refreshToken": self.refresh_token})
        result = payload.get("data") or {}
        self.jwt = result.get("jwtToken") or self.jwt
        self.refresh_token = result.get("refreshToken") or self.refresh_token
        self.feed_token = result.get("feedToken") or self.feed_token

    def verify(self) -> bool:
        if not self.jwt:
            return False
        headers = self._headers()
        headers["Authorization"] = "Bearer " + self.jwt
        response = self.http.get(self.PROFILE_URL, headers=headers, timeout=(3.05, 10))
        if response.status_code == 401:
            return False
        response.raise_for_status()
        payload = response.json()
        return isinstance(payload, dict) and payload.get("status") is True

    def close(self) -> None:
        self.jwt = self.refresh_token = self.feed_token = None
