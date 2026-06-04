from __future__ import annotations

from dataclasses import dataclass

from api_client import KisApiClient
from config import Settings


@dataclass(frozen=True)
class Holding:
    symbol: str
    quantity: int
    name: str


@dataclass(frozen=True)
class AccountSnapshot:
    holding: Holding
    available_cash: int
    raw: dict


class AccountService:
    def __init__(self, client: KisApiClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def get_snapshot(self, symbol: str) -> AccountSnapshot:
        payload = self.client.get(
            "/uapi/domestic-stock/v1/trading/inquire-balance",
            self.settings.tr_id_balance,
            {
                "CANO": self.settings.account.cano,
                "ACNT_PRDT_CD": self.settings.account.product_code,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "01",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )

        holdings_rows = _as_list(payload.get("output1"))
        summary_rows = _as_list(payload.get("output2"))

        holding_row = next(
            (
                row
                for row in holdings_rows
                if str(_pick_first(row, "pdno", "mksc_shrn_iscd", "symbol", "stock_code")) == symbol
            ),
            {},
        )
        summary_row = summary_rows[0] if summary_rows else {}

        holding = Holding(
            symbol=symbol,
            quantity=_to_int(_pick_first(holding_row, "hldg_qty", "hold_qty", "quantity")),
            name=str(_pick_first(holding_row, "prdt_name", "hts_kor_isnm", "name") or ""),
        )
        available_cash = _to_int(
            _pick_first(
                summary_row,
                "ord_psbl_cash",
                "dnca_tot_amt",
                "nrcvb_buy_amt",
                "cash",
            )
        )

        return AccountSnapshot(holding=holding, available_cash=available_cash, raw=payload)


def _as_list(value: object) -> list[dict]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        return [value]
    return []


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
