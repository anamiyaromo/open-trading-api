from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

KST: Final = ZoneInfo("Asia/Seoul")
MOCK_BASE_URL: Final = "https://openapivts.koreainvestment.com:29443"
PROD_BASE_URL: Final = "https://openapi.koreainvestment.com:9443"


@dataclass(frozen=True)
class AccountCredentials:
    cano: str
    product_code: str


@dataclass(frozen=True)
class Settings:
    account: AccountCredentials
    app_key: str
    app_secret: str
    static_access_token: str
    base_url: str
    user_agent: str
    symbol: str
    symbol_name: str
    buy_offset_krw: int
    sell_offset_krw: int
    order_quantity: int
    poll_interval_seconds: int
    post_order_wait_seconds: int
    volatility_window_size: int
    volatility_range_threshold_krw: int
    volatility_offset_krw: int
    trend_window_size: int
    trend_sell_offset_multiplier: int
    trend_buy_pause_enabled: bool
    dip_average_window_size: int
    dip_buy_threshold_bps: int
    dip_buy_offset_krw: int
    breakout_window_size: int
    breakout_range_max_krw: int
    breakout_buy_offset_krw: int
    max_open_buy_orders: int
    request_timeout_seconds: int
    http_retries: int
    retry_backoff_seconds: float
    trading_start_hhmm: str
    trading_end_hhmm: str
    timezone: ZoneInfo
    token_cache_path: Path
    tr_id_price: str
    tr_id_balance: str
    tr_id_order_buy: str
    tr_id_order_sell: str
    tr_id_daily_ccld: str


def load_settings(project_dir: Path | None = None) -> Settings:
    project_dir = project_dir or Path(__file__).resolve().parent
    credentials = _load_local_credentials(project_dir)
    account = _parse_account(
        _setting(credentials, "CANO", "GH_ACCOUNT"),
        credentials.get("ACNT_PRDT_CD", os.getenv("GH_ACNT_PRDT_CD", "")).strip(),
    )

    return Settings(
        account=account,
        app_key=_setting(credentials, "VTS_APPKEY", "GH_APPKEY"),
        app_secret=_setting(credentials, "VTS_APPSECRET", "GH_APPSECRET"),
        static_access_token=_setting(credentials, "VTS_TOKEN", "GH_ACCESS_TOKEN", default=""),
        base_url=_base_url(credentials).rstrip("/"),
        user_agent=os.getenv(
            "GH_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        ),
        symbol=os.getenv("GH_SYMBOL", "005930"),
        symbol_name=os.getenv("GH_SYMBOL_NAME", "Samsung Electronics"),
        buy_offset_krw=int(os.getenv("GH_BUY_OFFSET_KRW", "2000")),
        sell_offset_krw=int(os.getenv("GH_SELL_OFFSET_KRW", "2000")),
        order_quantity=int(os.getenv("GH_ORDER_QUANTITY", "1")),
        poll_interval_seconds=int(os.getenv("GH_POLL_INTERVAL_SECONDS", "60")),
        post_order_wait_seconds=int(os.getenv("GH_POST_ORDER_WAIT_SECONDS", "15")),
        volatility_window_size=int(os.getenv("GH_VOLATILITY_WINDOW_SIZE", "10")),
        volatility_range_threshold_krw=int(os.getenv("GH_VOLATILITY_RANGE_THRESHOLD_KRW", "3000")),
        volatility_offset_krw=int(os.getenv("GH_VOLATILITY_OFFSET_KRW", "4000")),
        trend_window_size=int(os.getenv("GH_TREND_WINDOW_SIZE", "5")),
        trend_sell_offset_multiplier=int(os.getenv("GH_TREND_SELL_OFFSET_MULTIPLIER", "2")),
        trend_buy_pause_enabled=_to_bool(os.getenv("GH_TREND_BUY_PAUSE_ENABLED", "true")),
        dip_average_window_size=int(os.getenv("GH_DIP_AVERAGE_WINDOW_SIZE", "10")),
        dip_buy_threshold_bps=int(os.getenv("GH_DIP_BUY_THRESHOLD_BPS", "50")),
        dip_buy_offset_krw=int(os.getenv("GH_DIP_BUY_OFFSET_KRW", "1000")),
        breakout_window_size=int(os.getenv("GH_BREAKOUT_WINDOW_SIZE", "10")),
        breakout_range_max_krw=int(os.getenv("GH_BREAKOUT_RANGE_MAX_KRW", "1500")),
        breakout_buy_offset_krw=int(os.getenv("GH_BREAKOUT_BUY_OFFSET_KRW", "0")),
        max_open_buy_orders=int(os.getenv("GH_MAX_OPEN_BUY_ORDERS", "5")),
        request_timeout_seconds=int(os.getenv("GH_REQUEST_TIMEOUT_SECONDS", "10")),
        http_retries=int(os.getenv("GH_HTTP_RETRIES", "2")),
        retry_backoff_seconds=float(os.getenv("GH_RETRY_BACKOFF_SECONDS", "1.5")),
        trading_start_hhmm=os.getenv("GH_TRADING_START", "09:10"),
        trading_end_hhmm=os.getenv("GH_TRADING_END", "15:30"),
        timezone=KST,
        token_cache_path=project_dir / "token_cache.json",
        tr_id_price=os.getenv("GH_TR_ID_PRICE", "FHKST01010100"),
        tr_id_balance=os.getenv("GH_TR_ID_BALANCE", "VTTC8434R"),
        tr_id_order_buy=os.getenv("GH_TR_ID_ORDER_BUY", "VTTC0012U"),
        tr_id_order_sell=os.getenv("GH_TR_ID_ORDER_SELL", "VTTC0011U"),
        tr_id_daily_ccld=os.getenv("GH_TR_ID_DAILY_CCLD", "VTTC0081R"),
    )


def _load_local_credentials(project_dir: Path) -> dict[str, str]:
    credentials_path = project_dir / "credentials.local.json"
    if not credentials_path.exists():
        return {}

    payload = json.loads(credentials_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("credentials.local.json must contain a JSON object.")

    return {str(key): str(value).strip() for key, value in payload.items() if value is not None}


def _setting(
    credentials: dict[str, str],
    local_key: str,
    env_key: str,
    *,
    default: str | None = None,
) -> str:
    local_value = credentials.get(local_key, "").strip()
    if local_value:
        return local_value

    env_value = os.getenv(env_key, "").strip()
    if env_value:
        return env_value

    if default is not None:
        return default

    raise KeyError(f"Set {local_key} in credentials.local.json or {env_key} as an environment variable.")


def _base_url(credentials: dict[str, str]) -> str:
    explicit_base_url = os.getenv("GH_BASE_URL", "").strip()
    if explicit_base_url:
        return explicit_base_url

    vts_url = credentials.get("VTS", "").strip()
    if vts_url:
        return vts_url

    return MOCK_BASE_URL


def _parse_account(raw_value: str, product_code: str = "") -> AccountCredentials:
    normalized = raw_value.strip()
    if product_code:
        return AccountCredentials(cano=normalized, product_code=product_code)

    for separator in ("-", ":", "/", " "):
        if separator in normalized:
            left, right = normalized.split(separator, 1)
            return AccountCredentials(cano=left.strip(), product_code=right.strip())

    digits_only = "".join(ch for ch in normalized if ch.isdigit())
    if len(digits_only) == 8:
        return AccountCredentials(cano=digits_only, product_code="01")

    if len(digits_only) == 10:
        return AccountCredentials(cano=digits_only[:8], product_code=digits_only[8:])

    raise ValueError(
        "GH_ACCOUNT must be formatted like '12345678', '12345678-01', or '1234567801'."
    )


def _to_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "y", "on")
