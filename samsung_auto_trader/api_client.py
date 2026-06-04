from __future__ import annotations

import logging
import time
from typing import Any

import requests

from auth import TokenManager
from config import Settings

logger = logging.getLogger(__name__)


class KisApiError(RuntimeError):
    pass


class KisApiClient:
    def __init__(self, settings: Settings, token_manager: TokenManager) -> None:
        self.settings = settings
        self.token_manager = token_manager

    def get(self, path: str, tr_id: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._request("GET", path, tr_id, params=params)

    def post(self, path: str, tr_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, tr_id, body=body)

    def _request(
        self,
        method: str,
        path: str,
        tr_id: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(1, self.settings.http_retries + 2):
            headers = self._build_headers(tr_id, body if method == "POST" else None)
            try:
                response = requests.request(
                    method=method,
                    url=f"{self.settings.base_url}{path}",
                    headers=headers,
                    params=params,
                    json=body,
                    timeout=self.settings.request_timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("rt_cd") not in (None, "0"):
                    raise KisApiError(
                        f"{payload.get('msg_cd', 'UNKNOWN')}: {payload.get('msg1', 'API call failed')}"
                    )
                return payload
            except (requests.RequestException, ValueError, KisApiError) as exc:
                last_error = exc
                logger.warning(
                    "API %s %s failed on attempt %s/%s: %s",
                    method,
                    path,
                    attempt,
                    self.settings.http_retries + 1,
                    exc,
                )
                if attempt > self.settings.http_retries:
                    break
                time.sleep(self.settings.retry_backoff_seconds)

        raise KisApiError(str(last_error))

    def _build_headers(
        self,
        tr_id: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "accept": "application/json",
            "authorization": f"Bearer {self.token_manager.get_access_token()}",
            "appkey": self.settings.app_key,
            "appsecret": self.settings.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
            "user-agent": self.settings.user_agent,
        }
        if body:
            headers["hashkey"] = self._issue_hashkey(body)
        return headers

    def _issue_hashkey(self, body: dict[str, Any]) -> str:
        response = requests.post(
            f"{self.settings.base_url}/uapi/hashkey",
            headers={
                "content-type": "application/json",
                "accept": "application/json",
                "authorization": f"Bearer {self.token_manager.get_access_token()}",
                "appkey": self.settings.app_key,
                "appsecret": self.settings.app_secret,
                "user-agent": self.settings.user_agent,
            },
            json=body,
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        hashkey = payload.get("HASH")
        if not hashkey:
            raise KisApiError(f"Failed to obtain hashkey: {payload}")
        return hashkey
