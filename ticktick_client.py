"""Thin HTTP client for the TickTick Open API.

Wraps a `requests.Session` with the bearer-token auth header pre-set, and
exposes `get`/`post` helpers that prepend the base URL, raise on non-2xx
responses, and return decoded JSON.
"""

from __future__ import annotations

import requests

from constants import HTTP_TIMEOUT, TICKTICK_API_BASE_URL


class TickTickClient:
    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def get(self, path: str):
        response = self.session.get(f"{TICKTICK_API_BASE_URL}{path}", timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload):
        response = self.session.post(f"{TICKTICK_API_BASE_URL}{path}", json=payload, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        return response.json() if response.text else None
