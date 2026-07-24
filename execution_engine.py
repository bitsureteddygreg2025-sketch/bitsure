"""
execution_engine.py
---------------------
Cœur de la logique d'exécution des signaux : lit les signaux "pending"/"active",
filtre par score/config, puis :
  - mode automatique : ouvre directement la position
  - mode semi-automatique : envoie un message Telegram avec boutons de confirmation

Ce module est appelé par un job APScheduler (voir main_integration.py) et par
les callbacks des boutons "✅ Ouvrir" / "❌ Refuser".
"""

import time
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import get_connection
from trading_config import get_config, TradingConfig
from risk_manager import check_can_open_position, calculate_position_size
from binance_manager import open_position, get_price, BinanceClientError
from trading_logger import get_trading_logger, log_trade_opened, log_error

logger = get_trading_logger("execution_engine")


def fetch_pending_signals():
    """Récupère les signaux non encore traités (statuts 'pending' ou 'active')."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, symbol, direction, entry_price, sl, tp, score
                FROM signals
                WHERE status IN ('pending', 'active')
                ORDER BY id ASC
                """
            )
            cols = ["id", "user_id", "symbol", "direction", "entry_price", "sl", "tp", "score"]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def mark_signal_status(signal_id: str, status: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE signals SET status = %s WHERE id = %s", (status, signal_id))
        conn.commit()
    finally:
        conn.close()


def insert_trade_row(**fields) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trades (signal_id, user_id, symbol, direction, entry_price,
                    sl_price, tp_price, quantity, leverage, market_type, status,
                    opened_at, binance_order_id, binance_client_order_id,
                    sl_order_id, tp_order_id, error_message)
                VALUES (%(signal_id)s, %(user_id)s, %(symbol)s, %(direction)s, %(entry_price)s,
                    %(sl_price)s, %(tp_price)s, %(quantity)s, %(leverage)s, %(market_type)s,
                    %(status)s, %(opened_at)s, %(binance_order_id)s, %(binance_client_order_id)s,
                    %(sl_order_id)s, %(tp_order_id)s, %(error_message)s)
                RETURNING id
                """,
                fields,
            )
            trade_id = cur.fetchone()[0]
        conn.commit()
        return trade_id
    finally:
        conn.close()


def _default_trade_fields(signal: dict, config: TradingConfig) -> dict:
    return {
        "signal_id": signal["id"],
        "user_id": signal["user_id"],
        "symbol": signal["symbol"],
        "direction": signal["direction"],
        "entry_price": signal["entry_price"],
        "sl_price": signal["sl"],
        "tp_price": signal["tp"],
        "quantity": None,
        "leverage": config.leverage,
        "market_type": config.market_type,
        "status": "error",
        "opened_at": time.time(),
        "binance_order_id": None,
        "binance_client_order_id": None,
        "sl_order_id": None,
        "tp_order_id": None,
        "error_message": None,
    }


def execute_signal(signal: dict, config: TradingConfig) -> dict:
    """
    Exécute réellement l'ordre sur Binance pour un signal donné, en calculant
    la taille de position, puis enregistre le trade en base.
    Retourne le dict de la ligne insérée (utile pour notifier l'utilisateur).
    """
    user_id = signal["user_id"]
    symbol = signal["symbol"]
    direction = signal["direction"]
    fields = _default_trade_fields(signal, config)

    try:
        entry_price = signal["entry_price"] or get_price(user_id, symbol, config.market_type)
        quantity = calculate_position_size(
            user_id, config, entry_price, signal["sl"], config.market_type
        )

        result = open_position(
            user_id=user_id,
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            sl_price=signal["sl"],
            tp_price=signal["tp"],
            market_type=config.market_type,
            leverage=config.leverage,
        )

        fields.update({
            "status": "open",
            "quantity": result["quantity"],
            "binance_order_id": str(result.get("order_id")),
            "binance_client_order_id": result.get("client_order_id"),
            "sl_order_id": str(result.get("sl_order_id")) if result.get("sl_order_id") else None,
            "tp_order_id": str(result.get("tp_order_id")) if result.get("tp_order_id") else None,
        })
        log_trade_opened(logger, user_id, symbol, direction, result["quantity"], entry_price)
        mark_signal_status(signal["id"], "executed")

    except (BinanceClientError, ValueError) as e:
        fields["error_message"] = str(e)
        log_error(logger, user_id, "execute_signal", str(e))
        mark_signal_status(signal["id"], "error")

    trade_id = insert_trade_row(**fields)
    fields["id"] = trade_id
    return fields


async def process_signal_for_user(context: ContextTypes.DEFAULT_TYPE, signal: dict):
    """Point d'entrée appelé par le job planifié pour chaque signal en attente."""
    user_id = signal["user_id"]
    config = get_config(user_id)

    if signal["score"] is not None and signal["score"] < config.min_score:
        return  # score trop faible, on ignore silencieusement

    risk_check = check_can_open_position(user_id, config, signal["symbol"])
    if not risk_check.allowed:
        mark_signal_status(signal["id"], "skipped")
        return

    if config.auto_trade:
        trade = execute_signal(signal, config)
        await _notify_trade_result(context, user_id, trade)
    else:
        await _send_confirmation_prompt(context, signal, config)


async def _notify_trade_result(context: ContextTypes.DEFAULT_TYPE, user_id: int, trade: dict):
    if trade["status"] == "open":
        text = (
            f"✅ *Position ouverte automatiquement*\n\n"
            f"Symbole : `{trade['symbol']}`\n"
            f"Direction : {trade['direction']}\n"
            f"Quantité : {trade['quantity']}\n"
            f"SL : {trade['sl_price']}  |  TP : {trade['tp_price']}"
        )
    else:
        text = (
            f"⚠️ *Échec d'ouverture de position*\n\n"
            f"Symbole : `{trade['symbol']}`\n"
            f"Erreur : {trade.get('error_message', 'inconnue')}"
        )
    await context.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")


async def _send_confirmation_prompt(context: ContextTypes.DEFAULT_TYPE, signal: dict, config: TradingConfig):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Ouvrir", callback_data=f"trading_open_{signal['id']}"),
            InlineKeyboardButton("❌ Refuser", callback_data=f"trading_reject_{signal['id']}"),
        ],
        [InlineKeyboardButton("⚙️ Modifier SL/TP", callback_data=f"trading_edit_{signal['id']}")],
    ])
    text = (
        f"📡 *Nouveau signal détecté*\n\n"
        f"Symbole : `{signal['symbol']}`\n"
        f"Direction : {signal['direction']}\n"
        f"Prix d'entrée : {signal['entry_price']}\n"
        f"SL : {signal['sl']}  |  TP : {signal['tp']}\n"
        f"Score : {signal['score']}\n\n"
        f"Que veux-tu faire ?"
    )
    await context.bot.send_message(
        chat_id=signal["user_id"], text=text, reply_markup=keyboard, parse_mode="Markdown"
    )
    mark_signal_status(signal["id"], "awaiting_confirmation")


async def scheduled_signal_scan(context: ContextTypes.DEFAULT_TYPE):
    """Job APScheduler : à enregistrer toutes les 15-30s dans main.py."""
    for signal in fetch_pending_signals():
        try:
            await process_signal_for_user(context, signal)
        except Exception as e:
            log_error(logger, signal.get("user_id"), "scheduled_signal_scan", str(e))
