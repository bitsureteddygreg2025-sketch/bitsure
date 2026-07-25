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
from trading_config import get_config, TradingConfig
from risk_manager import record_trade_loss
from binance_manager import get_price, close_position, cancel_order, BinanceClientError
from trading_logger import get_trading_logger, log_trade_closed, log_error

logger = get_trading_logger("position_manager")


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
                if trade["market_type"] == "spot":
                    close_position(
                        trade["user_id"], trade["symbol"], trade["direction"],
                        trade["quantity"], trade["market_type"],
                    )
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
                _persist_new_sl(trade["id"], new_sl)

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

    current_price = get_price(user_id, trade["symbol"], trade["market_type"])
    close_position(user_id, trade["symbol"], trade["direction"], trade["quantity"], trade["market_type"])

    for oid in (trade.get("sl_order_id"), trade.get("tp_order_id")):
        if oid:
            cancel_order(user_id, trade["symbol"], oid, trade["market_type"])

    pnl_usdt, pnl_pct = close_trade(trade, "manual", current_price)
    return {"pnl_usdt": pnl_usdt, "pnl_pct": pnl_pct, "symbol": trade["symbol"]}


def emergency_stop_all(user_id: int) -> int:
    """Ferme toutes les positions ouvertes d'un utilisateur et désactive l'auto-trade."""
    from trading_config import update_config

    closed = 0
    for trade in get_open_trades(user_id):
        try:
            current_price = get_price(user_id, trade["symbol"], trade["market_type"])
            close_position(user_id, trade["symbol"], trade["direction"], trade["quantity"], trade["market_type"])
            for oid in (trade.get("sl_order_id"), trade.get("tp_order_id")):
                if oid:
                    cancel_order(user_id, trade["symbol"], oid, trade["market_type"])
            close_trade(trade, "emergency", current_price)
            closed += 1
        except Exception as e:
            log_error(logger, user_id, "emergency_stop_all", str(e))

    update_config(user_id, auto_trade=False)
    return closed
