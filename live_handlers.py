"""
live_handlers.py
----------------
Handlers Telegram du module Live Trading manuel.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from binance_manager import BinanceClientError
from live_trader import (
    build_draft,
    cancel_live_order,
    execute_draft,
    get_live_account,
    get_open_orders,
    validate_draft,
)
from position_manager import get_open_trades, close_trade_manual
from trading_config import get_config, get_binance_credentials
from trading_logger import get_trading_logger
from utils import normalize_symbol

logger = get_trading_logger("live_handlers")

NO_LIVE_KEYS_MESSAGE = (
    "🔑 Live Trading nécessite des clés API Binance valides.\n"
    "Utilise /setapikeys <api_key> <api_secret> en privé avant d'envoyer un ordre réel."
)


def _has_live_keys(user_id: int) -> bool:
    creds = get_binance_credentials(user_id)
    return bool(creds and creds.get("api_key") and creds.get("api_secret") and creds.get("is_valid"))


def _live_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Ouvrir LONG", callback_data="live_open_long"), InlineKeyboardButton("🔴 Ouvrir SHORT", callback_data="live_open_short")],
        [InlineKeyboardButton("❌ Fermer une position", callback_data="live_close_menu"), InlineKeyboardButton("📈 Positions ouvertes", callback_data="live_positions")],
        [InlineKeyboardButton("📋 Ordres ouverts", callback_data="live_orders"), InlineKeyboardButton("🚫 Annuler un ordre", callback_data="live_cancel_menu")],
        [InlineKeyboardButton("🕓 Historique positions", callback_data="live_history"), InlineKeyboardButton("💼 Solde compte", callback_data="live_balance")],
        [InlineKeyboardButton("📊 PnL temps réel", callback_data="live_pnl"), InlineKeyboardButton("🏠 Menu Principal", callback_data="menu_back")],
    ])


def _draft_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirmer ordre réel", callback_data="live_confirm")],
        [InlineKeyboardButton("✏️ Recommencer LONG", callback_data="live_open_long"), InlineKeyboardButton("✏️ Recommencer SHORT", callback_data="live_open_short")],
        [InlineKeyboardButton("⬅️ Live Trading", callback_data="menu_live"), InlineKeyboardButton("🏠 Menu Principal", callback_data="menu_back")],
    ])


def _usage(side: str) -> str:
    return (
        f"⚙️ *Préparer un ordre réel {side}*\n\n"
        f"Commande : `/live_{side.lower()} SYMBOL MONTANT SL TP [LEVIER] [market|limit] [prix_limit] [fixed|percentage] [cross|isolated] [reduce_only]`\n\n"
        f"Exemple : `/live_{side.lower()} BTCUSDT 25 62000 68000 5 market fixed isolated`\n\n"
        "Aucun ordre réel n'est envoyé avant le bouton de confirmation."
    )


async def cmd_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _has_live_keys(user_id):
        await update.message.reply_text(NO_LIVE_KEYS_MESSAGE)
        return
    config = get_config(user_id)
    text = (
        "🚨 *Live Trading — Ordres réels*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"Marché : *{config.market_type.upper()}*\n"
        f"Levier par défaut : *x{config.leverage}*\n"
        f"Testnet : *{'OUI' if config.testnet else 'NON — ARGENT RÉEL'}*\n\n"
        "Chaque ouverture nécessite une confirmation explicite."
    )
    await update.message.reply_text(text, reply_markup=_live_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)


async def cmd_live_long(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _prepare_live_order(update, context, "BUY")


async def cmd_live_short(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _prepare_live_order(update, context, "SELL")


async def _prepare_live_order(update: Update, context: ContextTypes.DEFAULT_TYPE, side: str):
    user_id = update.effective_user.id
    if not _has_live_keys(user_id):
        await update.message.reply_text(NO_LIVE_KEYS_MESSAGE)
        return
    if len(context.args) < 4:
        await update.message.reply_text(_usage("long" if side == "BUY" else "short"), parse_mode=ParseMode.MARKDOWN)
        return
    try:
        symbol = normalize_symbol(context.args[0].upper())
        amount = float(context.args[1])
        sl_price = float(context.args[2])
        tp_price = float(context.args[3])
        leverage = int(context.args[4]) if len(context.args) > 4 and context.args[4].isdigit() else None
        order_type = context.args[5].upper() if len(context.args) > 5 else "MARKET"
        entry_price = float(context.args[6]) if len(context.args) > 6 and order_type == "LIMIT" else None
        amount_mode = context.args[7].lower() if len(context.args) > 7 else "fixed"
        margin_type = context.args[8].upper() if len(context.args) > 8 else "ISOLATED"
        reduce_only = len(context.args) > 9 and context.args[9].lower() in ("reduce_only", "reduceonly", "true", "yes")
        draft = build_draft(
            user_id, symbol, side, amount, leverage=leverage, sl_price=sl_price, tp_price=tp_price,
            amount_mode=amount_mode, order_type=order_type, entry_price=entry_price,
            margin_type=margin_type, reduce_only=reduce_only,
        )
        checks = validate_draft(user_id, draft)
    except (ValueError, BinanceClientError) as e:
        await update.message.reply_text(f"❌ Ordre refusé : {e}")
        return

    context.user_data["live_order_draft"] = draft
    await update.message.reply_text(_format_confirmation(draft, checks), reply_markup=_draft_keyboard(), parse_mode=ParseMode.MARKDOWN)


def _format_confirmation(draft, checks: dict) -> str:
    return (
        "🚨 *Confirmation ordre réel*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"Symbole : `{draft.symbol}`\n"
        f"Sens : *{'LONG / BUY' if draft.side == 'BUY' else 'SHORT / SELL'}*\n"
        f"Type : *{draft.order_type}*\n"
        f"Marge : *{draft.margin_type}* | Reduce only : *{'OUI' if draft.reduce_only else 'NON'}*\n"
        f"Montant engagé : `{checks['margin_amount']:.2f} USDT` ({draft.amount_mode})\n"
        f"Levier : *x{draft.leverage}*\n"
        f"Prix référence : `{checks['price']:.6f}`\n"
        f"Quantité : `{checks['quantity']}` | Notional : `{checks['notional']:.2f} USDT`\n"
        f"SL : `{checks['sl_price']}` | TP : `{checks['tp_price']}`\n\n"
        "⚠️ Appuie sur confirmer uniquement si tu acceptes l'envoi d'un ordre réel."
    )


async def live_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "menu_live":
        if not _has_live_keys(user_id):
            await query.edit_message_text(NO_LIVE_KEYS_MESSAGE)
            return
        config = get_config(user_id)
        await query.edit_message_text(
            f"🚨 *Live Trading — Ordres réels*\nMarché : *{config.market_type.upper()}*\nChoisis une action.",
            reply_markup=_live_menu_keyboard(), parse_mode=ParseMode.MARKDOWN,
        )
    elif data in ("live_open_long", "live_open_short"):
        side = "long" if data == "live_open_long" else "short"
        await query.edit_message_text(_usage(side), reply_markup=_live_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
    elif data == "live_confirm":
        draft = context.user_data.get("live_order_draft")
        if not draft:
            await query.edit_message_text("❌ Aucun ordre Live Trading en attente de confirmation.", reply_markup=_live_menu_keyboard())
            return
        try:
            result = execute_draft(user_id, draft)
        except BinanceClientError as e:
            await query.edit_message_text(f"❌ Ordre non envoyé : {e}", reply_markup=_live_menu_keyboard())
            return
        context.user_data.pop("live_order_draft", None)
        order = result.get("order", {})
        await query.edit_message_text(
            f"✅ Ordre réel envoyé.\nSymbole : {draft.symbol}\nOrder ID : {order.get('orderId', '—')}",
            reply_markup=_live_menu_keyboard(),
        )
    elif data == "live_positions":
        await _show_live_positions(query, user_id)
    elif data == "live_orders":
        await _show_open_orders(query, user_id)
    elif data == "live_close_menu":
        await query.edit_message_text("Commande : `/live_close ID_POSITION`", reply_markup=_live_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
    elif data == "live_cancel_menu":
        await query.edit_message_text("Commande : `/live_cancel SYMBOL ORDER_ID`", reply_markup=_live_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
    elif data == "live_history":
        await _show_history(query, user_id)
    elif data == "live_balance":
        await _show_balance(query, user_id)
    elif data == "live_pnl":
        await _show_pnl(query, user_id)


async def cmd_live_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage : /live_close <id_position>")
        return
    try:
        result = close_trade_manual(int(context.args[0]), update.effective_user.id)
        await update.message.reply_text(f"✅ Position fermée. PnL : {result['pnl_usdt']:.2f} USDT")
    except (ValueError, BinanceClientError) as e:
        await update.message.reply_text(f"❌ Fermeture refusée : {e}")


async def cmd_live_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage : /live_cancel <SYMBOL> <ORDER_ID>")
        return
    try:
        cancel_live_order(update.effective_user.id, context.args[0], context.args[1])
        await update.message.reply_text("✅ Ordre annulé.")
    except BinanceClientError as e:
        await update.message.reply_text(f"❌ Annulation refusée : {e}")


async def _show_live_positions(query, user_id: int):
    trades = get_open_trades(user_id)
    if not trades:
        await query.edit_message_text("📈 Aucune position Live ouverte.", reply_markup=_live_menu_keyboard())
        return
    lines = ["📈 *Positions Live ouvertes*\n"]
    for trade in trades:
        lines.append(f"#{trade['id']} `{trade['symbol']}` {trade['direction']} qty={trade['quantity']} SL={trade['sl_price']} TP={trade['tp_price']}")
    await query.edit_message_text("\n".join(lines), reply_markup=_live_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)


async def _show_open_orders(query, user_id: int):
    try:
        orders = get_open_orders(user_id)
    except BinanceClientError as e:
        await query.edit_message_text(f"❌ {e}", reply_markup=_live_menu_keyboard())
        return
    if not orders:
        await query.edit_message_text("📋 Aucun ordre ouvert.", reply_markup=_live_menu_keyboard())
        return
    lines = ["📋 *Ordres ouverts*\n"]
    for order in orders[:10]:
        lines.append(f"#{order.get('orderId')} `{order.get('symbol')}` {order.get('side')} {order.get('type')} qty={order.get('origQty')}")
    await query.edit_message_text("\n".join(lines), reply_markup=_live_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)


async def _show_history(query, user_id: int):
    from database import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT symbol, direction, pnl_usdt, exit_reason, closed_at FROM trades WHERE user_id=%s AND status='closed' ORDER BY closed_at DESC LIMIT 10",
                (user_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    if not rows:
        await query.edit_message_text("🕓 Aucun historique Live.", reply_markup=_live_menu_keyboard())
        return
    lines = ["🕓 *Historique Live*\n"]
    for symbol, direction, pnl, reason, _closed_at in rows:
        lines.append(f"`{symbol}` {direction} PnL={float(pnl or 0):.2f} USDT ({reason or '—'})")
    await query.edit_message_text("\n".join(lines), reply_markup=_live_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)


async def _show_balance(query, user_id: int):
    try:
        info = get_live_account(user_id)
    except BinanceClientError as e:
        await query.edit_message_text(f"❌ {e}", reply_markup=_live_menu_keyboard())
        return
    await query.edit_message_text(
        f"💼 *Solde Live ({info['market_type'].upper()})*\n"
        f"Total : `{info['total_wallet_balance']:.2f} USDT`\n"
        f"Disponible : `{info['available_balance']:.2f} USDT`\n"
        f"PnL non réalisé : `{info['unrealized_pnl']:+.2f} USDT`",
        reply_markup=_live_menu_keyboard(), parse_mode=ParseMode.MARKDOWN,
    )


async def _show_pnl(query, user_id: int):
    await _show_balance(query, user_id)
