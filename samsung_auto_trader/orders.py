from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from api_client import KisApiClient
from config import Settings


@dataclass(frozen=True)
class OrderSubmission:
    side: str
    symbol: str
    quantity: int
    price: int
    order_number: str
    branch_number: str
    raw: dict


@dataclass(frozen=True)
class OrderExecutionStatus:
    order_number: str
    filled_quantity: int
    remaining_quantity: int
    raw: dict

    @property
    def is_filled(self) -> bool:
        return self.filled_quantity > 0 and self.remaining_quantity == 0

    @property
    def is_open(self) -> bool:
        return self.remaining_quantity > 0


@dataclass(frozen=True)
class OpenOrder:
    side: str
    symbol: str
    order_number: str
    branch_number: str
    ordered_at: str
    order_price: int
    order_quantity: int
    filled_quantity: int
    remaining_quantity: int
    raw: dict


class OrderService:
    def __init__(self, client: KisApiClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def place_limit_buy(self, symbol: str, quantity: int, price: int) -> OrderSubmission:
        return self._place_limit_order("buy", symbol, quantity, price)

    def place_limit_sell(self, symbol: str, quantity: int, price: int) -> OrderSubmission:
        return self._place_limit_order("sell", symbol, quantity, price)

    def get_execution_status(
        self,
        order_number: str,
        symbol: str,
    ) -> OrderExecutionStatus | None:
        today = datetime.now(self.settings.timezone).strftime("%Y%m%d")
        payload = self.client.get(
            "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
            self.settings.tr_id_daily_ccld,
            {
                "CANO": self.settings.account.cano,
                "ACNT_PRDT_CD": self.settings.account.product_code,
                "INQR_STRT_DT": today,
                "INQR_END_DT": today,
                "SLL_BUY_DVSN_CD": "00",
                "PDNO": symbol,
                "CCLD_DVSN": "00",
                "INQR_DVSN": "00",
                "INQR_DVSN_3": "00",
                "ORD_GNO_BRNO": "",
                "ODNO": order_number,
                "INQR_DVSN_1": "",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
                "EXCG_ID_DVSN_CD": "KRX",
            },
        )

        rows = payload.get("output1", [])
        if not isinstance(rows, list):
            rows = []

        row = next(
            (
                item
                for item in rows
                if str(_pick_first(item, "odno", "ODNO", "order_no", "ord_no")) == order_number
            ),
            None,
        )
        if row is None:
            return None

        return OrderExecutionStatus(
            order_number=order_number,
            filled_quantity=_to_int(_pick_first(row, "tot_ccld_qty", "ccld_qty", "filled_qty")),
            remaining_quantity=_to_int(_pick_first(row, "rmn_qty", "ord_remn_qty", "unfilled_qty")),
            raw=row,
        )

    def get_open_orders(self, symbol: str) -> list[OpenOrder]:
        today = datetime.now(self.settings.timezone).strftime("%Y%m%d")
        payload = self.client.get(
            "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
            self.settings.tr_id_daily_ccld,
            {
                "CANO": self.settings.account.cano,
                "ACNT_PRDT_CD": self.settings.account.product_code,
                "INQR_STRT_DT": today,
                "INQR_END_DT": today,
                "SLL_BUY_DVSN_CD": "00",
                "PDNO": symbol,
                "CCLD_DVSN": "00",
                "INQR_DVSN": "00",
                "INQR_DVSN_3": "00",
                "ORD_GNO_BRNO": "",
                "ODNO": "",
                "INQR_DVSN_1": "",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
                "EXCG_ID_DVSN_CD": "KRX",
            },
        )

        rows = payload.get("output1", [])
        if not isinstance(rows, list):
            return []

        open_orders: list[OpenOrder] = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            remaining_quantity = _to_int(
                _pick_first(row, "rmn_qty", "ord_remn_qty", "unfilled_qty")
            )
            if remaining_quantity <= 0:
                continue

            order_symbol = str(_pick_first(row, "pdno", "mksc_shrn_iscd", "symbol") or symbol)
            if order_symbol != symbol:
                continue

            open_orders.append(
                OpenOrder(
                    side=_parse_side(row),
                    symbol=order_symbol,
                    order_number=str(_pick_first(row, "odno", "ODNO", "order_no", "ord_no") or ""),
                    branch_number=str(
                        _pick_first(
                            row,
                            "ord_gno_brno",
                            "KRX_FWDG_ORD_ORGNO",
                            "ord_orgno",
                            "branch_no",
                        )
                        or ""
                    ),
                    ordered_at=_parse_ordered_at(row, self.settings),
                    order_price=_to_int(
                        _pick_first(row, "ord_unpr", "avg_prvs", "order_price", "price")
                    ),
                    order_quantity=_to_int(_pick_first(row, "ord_qty", "order_qty", "quantity")),
                    filled_quantity=_to_int(
                        _pick_first(row, "tot_ccld_qty", "ccld_qty", "filled_qty")
                    ),
                    remaining_quantity=remaining_quantity,
                    raw=row,
                )
            )

        return [order for order in open_orders if order.order_number and order.side in ("buy", "sell")]

    def _place_limit_order(
        self,
        side: str,
        symbol: str,
        quantity: int,
        price: int,
    ) -> OrderSubmission:
        payload = self.client.post(
            "/uapi/domestic-stock/v1/trading/order-cash",
            self.settings.tr_id_order_buy if side == "buy" else self.settings.tr_id_order_sell,
            {
                "CANO": self.settings.account.cano,
                "ACNT_PRDT_CD": self.settings.account.product_code,
                "PDNO": symbol,
                "ORD_DVSN": "00",
                "ORD_QTY": str(quantity),
                "ORD_UNPR": str(price),
                "EXCG_ID_DVSN_CD": "KRX",
                "SLL_TYPE": "",
                "CNDT_PRIC": "",
            },
        )
        output = payload.get("output", {})
        return OrderSubmission(
            side=side,
            symbol=symbol,
            quantity=quantity,
            price=price,
            order_number=str(_pick_first(output, "ODNO", "odno", "order_no", "ord_no") or ""),
            branch_number=str(_pick_first(output, "KRX_FWDG_ORD_ORGNO", "ord_gno_brno", "branch_no") or ""),
            raw=payload,
        )


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


def _parse_side(row: dict) -> str:
    value = str(
        _pick_first(
            row,
            "sll_buy_dvsn_cd",
            "SLL_BUY_DVSN_CD",
            "sll_buy_dvsn_name",
            "trad_dvsn_name",
            "side",
        )
        or ""
    ).strip().lower()
    if value in ("02", "buy", "매수"):
        return "buy"
    if value in ("01", "sell", "매도"):
        return "sell"
    if "매수" in value or "buy" in value:
        return "buy"
    if "매도" in value or "sell" in value:
        return "sell"
    return ""


def _parse_ordered_at(row: dict, settings: Settings) -> str:
    order_date = str(_pick_first(row, "ord_dt", "ORD_DT") or "")
    order_time = str(_pick_first(row, "ord_tmd", "ORD_TMD") or "")
    if len(order_date) == 8 and len(order_time) >= 6:
        try:
            parsed = datetime.strptime(order_date + order_time[:6], "%Y%m%d%H%M%S")
            return parsed.replace(tzinfo=settings.timezone).isoformat(timespec="seconds")
        except ValueError:
            pass
    return datetime.now(settings.timezone).isoformat(timespec="seconds")
