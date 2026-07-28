"""Safety-first guards for real trading actions.

This module centralizes checks that must run before sending orders to Binance.
It deliberately fails closed: if state cannot be verified, it disables automatic
trading and rejects the action.
"""

import os
import time
from contextlib import contextmanager
from typing import Optional

from database import get_connection
from trading_config import TradingConfig, update_config
from trading_logger import get_trading_logger

logger = get_trading_logger("trading_safety")

SIGNAL_VALIDITY_SECONDS = int(os.getenv("SIGNAL_VALIDITY_SECONDS", "900"))


class SafetyError(Exception):
    """Raised when a critical action must be refused for safety."""


def engage_safe_mode(user_id: int, reason: str) -> None:
    """Disable all automated entry points for a user and persist the reason."""
    logger.critical("SAFE_MODE user=%s reason=%s", user_id, reason)
    update_config(
        user_id,
        auto_trade=False,
        periodic_analysis_enabled=False,
        safety_lock=True,
        safety_lock_reason=reason,
        safety_lock_at=time.time(),
    )
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE signals
                SET status = 'rejected', rejection_reason = %s
                WHERE user_id = %s
                  AND status IN ('pending', 'active', 'awaiting_confirmation', 'processing')
                """,
                (f"safe_mode: {reason}", user_id),
            )
        conn.commit()
    finally:
        conn.close()


def assert_trading_allowed(config: TradingConfig, *, require_auto_trade: bool = False) -> None:
    if getattr(config, "safety_lock", False):
        raise SafetyError(f"Mode sûr actif: {config.safety_lock_reason or 'raison non précisée'}")
    if require_auto_trade and not config.auto_trade:
        raise SafetyError("AutoTrade est désactivé.")


def signal_age_seconds(signal: dict) -> Optional[float]:
    created_at = signal.get("created_at")
    if created_at in (None, ""):
        return None
    try:
        return time.time() - float(created_at)
    except (TypeError, ValueError):
        return None


def validate_signal_freshness(signal: dict, *, max_age_seconds: int = SIGNAL_VALIDITY_SECONDS) -> None:
    age = signal_age_seconds(signal)
    if age is None:
        raise SafetyError("Signal sans horodatage fiable.")
    if age < -5:
        raise SafetyError("Signal horodaté dans le futur.")
    if age > max_age_seconds:
        raise SafetyError(f"Signal obsolète ({int(age)}s > {max_age_seconds}s).")


@contextmanager
def user_trading_lock(user_id: int):
    """PostgreSQL advisory lock serializing critical trading operations per user."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (int(user_id),))
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reserve_signal_for_execution(signal_id: str, user_id: int, allowed_statuses: tuple[str, ...]) -> dict:
    """Atomically move a signal to processing and return its current row.

    If another worker/button already consumed it, no row is returned and the
    caller must not send any order.
    """
    with user_trading_lock(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE signals
                SET status = 'processing'
                WHERE id = %s
                  AND user_id = %s
                  AND status = ANY(%s)
                RETURNING id, user_id, symbol, direction, entry_price, sl, tp, score,
                          status, timeframe, signal_type, created_at
                """,
                (signal_id, user_id, list(allowed_statuses)),
            )
            row = cur.fetchone()
            if not row:
                raise SafetyError("Signal déjà traité, expiré ou dans un état non exécutable.")
            cols = [
                "id", "user_id", "symbol", "direction", "entry_price", "sl", "tp", "score",
                "status", "timeframe", "signal_type", "created_at",
            ]
            return dict(zip(cols, row))


def mark_signal_refused(signal_id: str, reason: str) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE signals SET status = 'skipped', rejection_reason = %s WHERE id = %s",
                (reason, signal_id),
            )
        conn.commit()
    finally:
        conn.close()
