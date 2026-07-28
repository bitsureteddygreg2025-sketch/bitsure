"""
position_manager.py
---------------------
Suivi des positions ouvertes : PnL en temps réel, détection TP/SL atteints,
trailing stop, DCA, et fermeture (manuelle ou emergency stop).
"""

import time
from typing import Optional

from telegram.ext import ContextTypes

from database import get_connection
from trading_config import get_config, TradingConfig, update_config
from risk_manager import record_trade_loss
from binance_manager import (
    get_price, close_position, cancel_order, get_open_binance_positions,
    get_open_binance_orders, BinanceClientError, ORDER_CONTEXT_AUTOTRADE, ORDER_CONTEXT_MANUAL_AUTHENTICATED, ORDER_CONTEXT_EMERGENCY,
)
from trading_logger import get_trading_logger, log_trade_closed, log_error
from trading_safety import engage_safe_mode

logger = get_trading_logger("position_manager")



def reject_pending_trading_signals(user_id: int) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE signals
                SET status = 'rejected'
                WHERE user_id = %s
                  AND status IN ('pending', 'active', 'awaiting_confirmation')
                """,
                (user_id,),
            )
            count = cur.rowcount
        conn.commit()
        return count
    finally:
        conn.close()

def get_open_trades(user_id: Optional[int] = None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if user_id:
                cur.execute(
                    "SELECT id, user_id, symbol, direction, entry_price, sl_price, tp_price, "
                    "quantity, leverage, market_type, sl_order_id, tp_order_id "
                    "FROM trades WHERE status = 'open' AND user_id = %s",
                    (user_id,),
                )
            else:
                cur.execute(
                    "SELECT id, user_id, symbol, direction, entry_price, sl_price, tp_price, "
                    "quantity, leverage, market_type, sl_order_id, tp_order_id "
                    "FROM trades WHERE status = 'open'"
                )
            cols = ["id", "user_id", "symbol", "direction", "entry_price", "sl_price",
                    "tp_price", "quantity", "leverage", "market_type", "sl_order_id", "tp_order_id"]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def _compute_pnl(direction: str, entry_price: float, current_price: float, quantity: float, leverage: int):
    if direction == "BUY":
        pnl_usdt = (current_price - entry_price) * quantity
    else:
        pnl_usdt = (entry_price - current_price) * quantity
    pnl_pct = (pnl_usdt / (entry_price * quantity)) * 100 * leverage if entry_price and quantity else 0
    return pnl_usdt, pnl_pct


def close_trade(trade: dict, exit_reason: str, current_price: float):
    pnl_usdt, pnl_pct = _compute_pnl(
        trade["direction"], trade["entry_price"], current_price,
        trade["quantity"], trade["leverage"],
    )

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE trades
                SET status = 'closed', closed_at = %s, exit_reason = %s,
                    pnl_usdt = %s, pnl_pct = %s
                WHERE id = %s
                """,
                (time.time(), exit_reason, pnl_usdt, pnl_pct, trade["id"]),
            )
        conn.commit()
    finally:
        conn.close()

    if pnl_usdt < 0:
        record_trade_loss(trade["user_id"], abs(pnl_usdt))

    log_trade_closed(logger, trade["user_id"], trade["symbol"], exit_reason, pnl_usdt)
    return pnl_usdt, pnl_pct


def update_trailing_stop(trade: dict, config: TradingConfig, current_price: float) -> Optional[float]:
    """Retourne le nouveau SL si le trailing doit être mis à jour, sinon None."""
    if not config.trailing_stop:
        return None

    trail_pct = config.trailing_stop_pct / 100
    if trade["direction"] == "BUY":
        new_sl = current_price * (1 - trail_pct)
        if new_sl > (trade["sl_price"] or 0):
            return new_sl
    else:
        new_sl = current_price * (1 + trail_pct)
        if trade["sl_price"] is None or new_sl < trade["sl_price"]:
            return new_sl
    return None


def _persist_new_sl(trade_id: int, new_sl: float):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE trades SET sl_price = %s WHERE id = %s", (new_sl, trade_id))
        conn.commit()
    finally:
        conn.close()





def _remote_position_exists(user_id: int, symbol: str, direction: str) -> bool:
    positions = get_open_binance_positions(user_id, market_type="futures")
    return any(p["symbol"] == symbol and p["direction"] == direction for p in positions)


def _cancel_remaining_protection(trade: dict, executed_reason: str) -> None:
    # Si TP exécuté, annuler le SL restant; si SL exécuté, annuler le TP restant.
    oid = trade.get("sl_order_id") if executed_reason == "TP" else trade.get("tp_order_id")
    if oid:
        cancel_order(trade["user_id"], trade["symbol"], oid, trade["market_type"], execution_context=ORDER_CONTEXT_AUTOTRADE)

def _trade_key(trade: dict) -> tuple[str, str]:
    return (trade["symbol"], trade["direction"])


def reconcile_user_positions(user_id: int, startup_mode: bool = False) -> dict:
    """Reconcile local open futures trades with real Binance positions/orders.

    Args:
        startup_mode: When True (used at bot startup), Binance positions with no
            local record are only logged — safe mode is NOT triggered.  This
            avoids permanently disabling AutoTrade because of pre-existing manual
            positions or leftover positions from a previous bot session.
    """
    local_trades = [t for t in get_open_trades(user_id) if t["market_type"] == "futures"]
    if not local_trades:
        local_by_key = {}
    else:
        local_by_key = {_trade_key(t): t for t in local_trades}

    remote_positions = get_open_binance_positions(user_id, market_type="futures")
    remote_by_key = {(p["symbol"], p["direction"]): p for p in remote_positions}

    repaired = 0
    missing_remote = []
    missing_local = []

    for key, trade in local_by_key.items():
        if key in remote_by_key:
            continue
        missing_remote.append(key)
        try:
            current_price = get_price(user_id, trade["symbol"], trade["market_type"])
            close_trade(trade, "reconciled_missing_remote", current_price)
            repaired += 1
        except Exception as e:
            log_error(logger, user_id, "reconcile.close_local", str(e))

    for key in remote_by_key:
        if key not in local_by_key:
            missing_local.append(key)

    if missing_local:
        log_error(
            logger, user_id, "reconcile.missing_local",
            f"Positions Binance sans trade local: {missing_local}",
        )
        if startup_mode:
            # At startup, orphaned Binance positions are simply pre-existing (manual
            # trades, previous session).  Only log — do not lock the user out.
            logger.warning(
                "reconcile startup_mode user=%s: ignoring %d orphaned Binance position(s) %s",
                user_id, len(missing_local), missing_local,
            )
        else:
            engage_safe_mode(user_id, f"Positions Binance sans trade local: {missing_local}")
            reject_pending_trading_signals(user_id)

    try:
        open_orders = get_open_binance_orders(user_id, market_type="futures")
        open_order_ids = {str(order.get("orderId")) for order in open_orders if order.get("orderId") is not None}
        for trade in local_trades:
            for field in ("sl_order_id", "tp_order_id"):
                oid = trade.get(field)
                if oid and str(oid) not in open_order_ids and _trade_key(trade) in remote_by_key:
                    log_error(
                        logger, user_id, f"reconcile.{field}",
                        f"Ordre protecteur absent côté Binance pour trade {trade['id']}: {oid}",
                    )
                    engage_safe_mode(user_id, f"Ordre protecteur absent pour trade {trade['id']}")
    except BinanceClientError as e:
        log_error(logger, user_id, "reconcile.orders", str(e))

    return {
        "user_id": user_id,
        "local_open": len(local_trades),
        "remote_open": len(remote_positions),
        "missing_remote": missing_remote,
        "missing_local": missing_local,
        "repaired": repaired,
    }


def _active_trading_user_ids() -> list[int]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT c.user_id
                FROM binance_credentials c
                LEFT JOIN trading_config t ON t.user_id = c.user_id
                WHERE c.is_valid = TRUE
                  AND COALESCE(t.market_type, 'futures') = 'futures'
                """
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def reconcile_all_accounts(context=None, startup_mode: bool = False) -> list[dict]:
    reports = []
    for user_id in _active_trading_user_ids():
        try:
            reports.append(reconcile_user_positions(user_id, startup_mode=startup_mode))
        except BinanceClientError as e:
            log_error(logger, user_id, "reconcile_all", str(e))
        except Exception as e:
            log_error(logger, user_id, "reconcile_all_unexpected", str(e))
    return reports

async def monitor_open_positions(context: ContextTypes.DEFAULT_TYPE):
    """Job APScheduler : à appeler toutes les 10-20s (surveille les positions réelles Binance).

    Note : la surveillance du paper trading (SL/TP) est gérée séparément par
    bot_handlers.check_paper_exits(), qui rafraîchit les prix avant de vérifier
    les déclenchements. Elle n'est pas dupliquée ici.
    """
    for trade in get_open_trades():
        try:
            config = get_config(trade["user_id"])
            current_price = get_price(trade["user_id"], trade["symbol"], trade["market_type"])

            hit_tp = (
                trade["tp_price"] and (
                    (trade["direction"] == "BUY" and current_price >= trade["tp_price"]) or
                    (trade["direction"] == "SELL" and current_price <= trade["tp_price"])
                )
            )
            hit_sl = (
                trade["sl_price"] and (
                    (trade["direction"] == "BUY" and current_price <= trade["sl_price"]) or
                    (trade["direction"] == "SELL" and current_price >= trade["sl_price"])
                )
            )

            if hit_tp or hit_sl:
                reason = "TP" if hit_tp else "SL"
                # En spot, le bot doit fermer lui-même (pas d'ordre stop natif posé).
                # En futures, si aucun ordre protecteur correspondant n'est connu, on
                # ferme aussi explicitement pour éviter une clôture seulement locale.
                protective_order_id = trade.get("tp_order_id") if hit_tp else trade.get("sl_order_id")
                if trade["market_type"] == "spot" or not protective_order_id:
                    close_position(
                        trade["user_id"], trade["symbol"], trade["direction"],
                        trade["quantity"], trade["market_type"],
                        execution_context=ORDER_CONTEXT_AUTOTRADE,
                    )
                elif _remote_position_exists(trade["user_id"], trade["symbol"], trade["direction"]):
                    # Un prix local a touché SL/TP, mais Binance indique que la position existe encore:
                    # ne jamais clôturer localement par supposition.
                    continue
                _cancel_remaining_protection(trade, reason)
                pnl_usdt, pnl_pct = close_trade(trade, reason, current_price)
                await context.bot.send_message(
                    chat_id=trade["user_id"],
                    text=(
                        f"{'🟢' if pnl_usdt >= 0 else '🔴'} *Position fermée ({reason})*\n"
                        f"Symbole : `{trade['symbol']}`\n"
                        f"PnL : {pnl_usdt:.2f} USDT ({pnl_pct:.2f}%)"
                    ),
                    parse_mode="Markdown",
                )
                continue

            new_sl = update_trailing_stop(trade, config, current_price)
            if new_sl:
                if trade["market_type"] == "spot":
                    _persist_new_sl(trade["id"], new_sl)
                else:
                    log_error(
                        logger, trade["user_id"], "trailing_stop",
                        "Trailing stop futures ignoré: mise à jour d'ordre Binance non implémentée.",
                    )

        except BinanceClientError as e:
            log_error(logger, trade["user_id"], "monitor_open_positions", str(e))
        except Exception as e:
            log_error(logger, trade["user_id"], "monitor_open_positions_unexpected", str(e))


def close_trade_manual(trade_id: int, user_id: int) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, symbol, direction, entry_price, sl_price, tp_price, "
                "quantity, leverage, market_type, sl_order_id, tp_order_id "
                "FROM trades WHERE id = %s AND user_id = %s AND status = 'open'",
                (trade_id, user_id),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise ValueError("Position introuvable ou déjà fermée.")

    cols = ["id", "user_id", "symbol", "direction", "entry_price", "sl_price",
            "tp_price", "quantity", "leverage", "market_type", "sl_order_id", "tp_order_id"]
    trade = dict(zip(cols, row))

    if trade["market_type"] == "futures":
        remote_positions = get_open_binance_positions(user_id, market_type="futures")
        remote = next(
            (
                p for p in remote_positions
                if p["symbol"] == trade["symbol"]
                and p["direction"] == trade["direction"]
                and abs(float(p["quantity"]) - float(trade["quantity"])) <= max(float(trade["quantity"]) * 0.001, 1e-12)
            ),
            None,
        )
        if not remote:
            engage_safe_mode(user_id, f"Fermeture refusée: position Binance non conforme pour trade {trade_id}")
            raise ValueError("Fermeture refusée: position Binance correspondante introuvable ou taille différente.")

    current_price = get_price(user_id, trade["symbol"], trade["market_type"])
    close_position(user_id, trade["symbol"], trade["direction"], trade["quantity"], trade["market_type"], execution_context=ORDER_CONTEXT_MANUAL_AUTHENTICATED)

    for oid in (trade.get("sl_order_id"), trade.get("tp_order_id")):
        if oid:
            cancel_order(user_id, trade["symbol"], oid, trade["market_type"], execution_context=ORDER_CONTEXT_MANUAL_AUTHENTICATED)

    pnl_usdt, pnl_pct = close_trade(trade, "manual", current_price)
    return {"pnl_usdt": pnl_usdt, "pnl_pct": pnl_pct, "symbol": trade["symbol"]}


def emergency_stop_all(user_id: int) -> int:
    """Ferme toutes les positions ouvertes localement et réellement ouvertes sur Binance."""
    from trading_config import update_config

    closed = 0
    local_trades = get_open_trades(user_id)
    local_keys = {(t["symbol"], t["direction"]): t for t in local_trades}

    for trade in local_trades:
        try:
            current_price = get_price(user_id, trade["symbol"], trade["market_type"])
            close_position(user_id, trade["symbol"], trade["direction"], trade["quantity"], trade["market_type"], execution_context=ORDER_CONTEXT_EMERGENCY)
            for oid in (trade.get("sl_order_id"), trade.get("tp_order_id")):
                if oid:
                    cancel_order(user_id, trade["symbol"], oid, trade["market_type"], execution_context=ORDER_CONTEXT_EMERGENCY)
            close_trade(trade, "emergency", current_price)
            closed += 1
        except Exception as e:
            log_error(logger, user_id, "emergency_stop_all.local", str(e))

    try:
        for pos in get_open_binance_positions(user_id, market_type="futures"):
            key = (pos["symbol"], pos["direction"])
            if key in local_keys:
                continue
            close_position(user_id, pos["symbol"], pos["direction"], pos["quantity"], "futures", execution_context=ORDER_CONTEXT_EMERGENCY)
            for order in get_open_binance_orders(user_id, market_type="futures", symbol=pos["symbol"]):
                cancel_order(user_id, pos["symbol"], order.get("orderId"), "futures", execution_context=ORDER_CONTEXT_EMERGENCY)
            closed += 1
    except Exception as e:
        log_error(logger, user_id, "emergency_stop_all.remote", str(e))

    reject_pending_trading_signals(user_id)
    update_config(user_id, auto_trade=False, periodic_analysis_enabled=False)
    return closed
