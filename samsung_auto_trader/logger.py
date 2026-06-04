from __future__ import annotations

import logging
from pathlib import Path


def configure_logging() -> None:
    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                Path(__file__).resolve().parent / "auto_trader.log",
                encoding="utf-8",
            ),
        ],
    )
