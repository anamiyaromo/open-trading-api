from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

import requests

from config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenRecord:
    access_token: str
    expires_at: str
    issued_date: str


class TokenManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        if self.settings.static_access_token and not force_refresh:
            logger.info("Using access token from credentials.local.json.")
            return self.settings.static_access_token

        if not force_refresh:
            cached = self._load_cached_token()
            if cached and self._is_valid_for_today(cached):
                logger.info("Reusing cached token from %s.", cached.issued_date)
                return cached.access_token

        token = self._issue_new_token()
        self._save_token(token)
        logger.info("Issued a new token for %s.", token.issued_date)
        return token.access_token

    def _issue_new_token(self) -> TokenRecord:
        response = requests.post(
            f"{self.settings.base_url}/oauth2/tokenP",
            headers={
                "content-type": "application/json",
                "accept": "application/json",
                "user-agent": self.settings.user_agent,
            },
            json={
                "grant_type": "client_credentials",
                "appkey": self.settings.app_key,
                "appsecret": self.settings.app_secret,
            },
            timeout=self.settings.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()

        access_token = payload["access_token"]
        expires_at = payload.get("access_token_token_expired")
        if not expires_at:
            expires_at = (
                datetime.now(self.settings.timezone) + timedelta(hours=23)
            ).strftime("%Y-%m-%d %H:%M:%S")

        return TokenRecord(
            access_token=access_token,
            expires_at=expires_at,
            issued_date=datetime.now(self.settings.timezone).strftime("%Y-%m-%d"),
        )

    def _load_cached_token(self) -> TokenRecord | None:
        cache_path = self.settings.token_cache_path
        if not cache_path.exists():
            return None

        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            return TokenRecord(
                access_token=payload["access_token"],
                expires_at=payload["expires_at"],
                issued_date=payload["issued_date"],
            )
        except (KeyError, OSError, ValueError, TypeError) as exc:
            logger.warning("Ignoring unreadable token cache: %s", exc)
            return None

    def _save_token(self, token: TokenRecord) -> None:
        self.settings.token_cache_path.write_text(
            json.dumps(asdict(token), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _is_valid_for_today(self, token: TokenRecord) -> bool:
        if token.issued_date != datetime.now(self.settings.timezone).strftime("%Y-%m-%d"):
            return False

        expires_at = datetime.strptime(token.expires_at, "%Y-%m-%d %H:%M:%S")
        expires_at = expires_at.replace(tzinfo=self.settings.timezone)
        return datetime.now(self.settings.timezone) < (expires_at - timedelta(minutes=5))
