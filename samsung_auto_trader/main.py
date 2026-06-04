from __future__ import annotations

import logging
from pathlib import Path

from account import AccountService
from api_client import KisApiClient
from auth import TokenManager
from config import load_settings
from logger import configure_logging
from market_data import MarketDataService
from orders import OrderService
from trader import SamsungAutoTrader


def main() -> None:
    configure_logging()
    settings = load_settings(Path(__file__).resolve().parent)
    token_manager = TokenManager(settings)
    client = KisApiClient(settings, token_manager)
    trader = SamsungAutoTrader(
        settings=settings,
        market_data=MarketDataService(client, settings),
        account_service=AccountService(client, settings),
        order_service=OrderService(client, settings),
    )

    logging.getLogger(__name__).info(
        "Starting mock auto trader for %s (%s).",
        settings.symbol_name,
        settings.symbol,
    )
    trader.run()


if __name__ == "__main__":
    main()
