from __future__ import annotations

from dataclasses import dataclass

from api_client import KisApiClient
from config import Settings


@dataclass(frozen=True)
class Quote:
    symbol: str
    current_price: int
    raw: dict


class MarketDataService:
    def __init__(self, client: KisApiClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def get_current_price(self, symbol: str) -> Quote:
        payload = self.client.get(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            self.settings.tr_id_price,
            {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
            },
        )
        output = payload.get("output", {})
        current_price = _to_int(
            _pick_first(output, "stck_prpr", "current_price", "price", "stck_oprc")
        )
        return Quote(symbol=symbol, current_price=current_price, raw=payload)


def _pick_first(payload: dict, *keys: str) -> str | int | None:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    return None


def _to_int(value: str | int | None) -> int:
    if value in (None, ""):
        return 0
    return int(str(value).replace(",", ""))
