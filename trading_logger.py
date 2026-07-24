"""
trading_logger.py
------------------
Logging dédié au module de trading. Écrit dans trading.log ET dans la console.

RÈGLE DE SÉCURITÉ : ne jamais passer api_key / api_secret / secret à ces fonctions.
Le filtre ci-dessous masque aussi toute chaîne qui ressemblerait à une clé API
(par précaution supplémentaire, ne remplace pas la vigilance du développeur).
"""

import logging
import re
import os

LOG_PATH = os.getenv("TRADING_LOG_PATH", "trading.log")

_API_KEY_PATTERN = re.compile(r"[A-Za-z0-9]{40,}")


class RedactSensitiveFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _API_KEY_PATTERN.sub("[REDACTED]", record.msg)
        return True


def get_trading_logger(name: str = "trading") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # déjà configuré

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(RedactSensitiveFilter())

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(RedactSensitiveFilter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def log_trade_opened(logger: logging.Logger, user_id: int, symbol: str, direction: str, quantity: float, entry: float):
    logger.info(
        "TRADE_OPEN user=%s symbol=%s dir=%s qty=%s entry=%s",
        user_id, symbol, direction, quantity, entry,
    )


def log_trade_closed(logger: logging.Logger, user_id: int, symbol: str, exit_reason: str, pnl_usdt: float):
    logger.info(
        "TRADE_CLOSE user=%s symbol=%s reason=%s pnl_usdt=%.2f",
        user_id, symbol, exit_reason, pnl_usdt,
    )


def log_error(logger: logging.Logger, user_id: int, context: str, error: str):
    logger.error("ERROR user=%s context=%s error=%s", user_id, context, error)
