"""
trading_handlers.py
---------------------
Toutes les commandes Telegram utilisateur pour le module AutoTrade, ainsi que
le routeur de callbacks pour les boutons (menu_autotrade, menu_positions, etc.)
et la confirmation des signaux en mode semi-automatique.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from trading_config import get_config, update_config, save_binance_credentials
from binance_manager import test_connection, BinanceClientError
from position_manager import get_open_trades, close_trade_manual, emergency_stop_all
from execution_engine import execute_signal, fetch_pending_signals, mark_signal_status
from database import get_connection
from trading_logger import get_trading_logger, log_error

logger = get_trading_logger("trading_handlers")


def _is_user_allowed(user_id: int) -> bool:
    """Le module doit être désactivable proprement si l'utilisateur n'a pas configuré ses clés."""
    from trading_config import get_binance_credentials
    creds = get_binance_credentials(user_id)
    return creds is not None and creds.get("api_key") and creds.get("is_valid")


NO_KEYS_MESSAGE = (
    "🔑 Tu n'as pas encore configuré tes clés API Binance.\n"
    "Utilise /setapikeys <api_key> <api_secret> pour les ajouter "
    "(en message privé uniquement, jamais dans un groupe)."
)


# ---------------------------------------------------------------------------
# Commandes utilisateur
# ---------------------------------------------------------------------------

async def cmd_setapikeys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Supprime le message contenant les clés pour éviter qu'il traîne dans le chat.
    try:
        await update.message.delete()
    except Exception:
        pass

    if len(context.args) < 2:
        await context.bot.send_message(
            chat_id=user_id,
            text="Usage : /setapikeys <api_key> <api_secret>\n(Envoie ce message en privé uniquement.)",
        )
        return

    api_key, api_secret = context.args[0], context.args[1]
    config = get_config(user_id)
    save_binance_credentials(user_id, api_key, api_secret, testnet=config.testnet)

    try:
        test_connection(user_id)
        await context.bot.send_message(chat_id=user_id, text="✅ Clés API validées et enregistrées.")
    except BinanceClientError as e:
        await context.bot.send_message(chat_id=user_id, text=f"⚠️ Clés enregistrées mais la connexion a échoué : {e}")


async def cmd_autotrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _is_user_allowed(user_id):
        await update.message.reply_text(NO_KEYS_MESSAGE)
        return

    config = get_config(user_id)
    new_value = not config.auto_trade
    update_config(user_id, auto_trade=new_value)
    status = "activé ✅" if new_value else "désactivé ❌"
    await update.message.reply_text(f"Mode automatique {status}.")


async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    config = get_config(user_id)
    text = (
        f"⚙️ *Configuration de trading*\n\n"
        f"Mode auto : {'ON' if config.auto_trade else 'OFF'}\n"
        f"Marché : {config.market_type}\n"
        f"Levier : x{config.leverage}\n"
        f"Risque par trade : {config.risk_per_trade}%\n"
        f"Max positions : {config.max_positions}\n"
        f"Score minimum : {config.min_score}\n"
        f"Perte max/jour : {config.max_daily_loss}%\n"
        f"Trailing stop : {'ON' if config.trailing_stop else 'OFF'} ({config.trailing_stop_pct}%)\n"
        f"DCA : {'ON' if config.dca_enabled else 'OFF'}\n"
        f"Testnet : {'OUI' if config.testnet else 'NON — argent réel'}\n"
        f"Whitelist : {', '.join(config.symbol_whitelist) or '—'}\n"
        f"Blacklist : {', '.join(config.symbol_blacklist) or '—'}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    trades = get_open_trades(user_id)
    if not trades:
        await update.message.reply_text("Aucune position ouverte actuellement.")
        return

    lines = ["📈 *Positions ouvertes*\n"]
    for t in trades:
        lines.append(
            f"#{t['id']} `{t['symbol']}` {t['direction']} — qty {t['quantity']} "
            f"(SL {t['sl_price']} / TP {t['tp_price']})"
        )
    lines.append("\nUtilise /close <id> pour fermer une position.")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage : /close <id_position>")
        return

    try:
        trade_id = int(context.args[0])
        result = close_trade_manual(trade_id, user_id)
        emoji = "🟢" if result["pnl_usdt"] >= 0 else "🔴"
        await update.message.reply_text(
            f"{emoji} Position `{result['symbol']}` fermée. "
            f"PnL : {result['pnl_usdt']:.2f} USDT ({result['pnl_pct']:.2f}%)",
            parse_mode="Markdown",
        )
    except (ValueError, BinanceClientError) as e:
        await update.message.reply_text(f"⚠️ {e}")


async def cmd_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(pnl_usdt), 0),
                       COALESCE(SUM(CASE WHEN pnl_usdt > 0 THEN 1 ELSE 0 END), 0)
                FROM trades WHERE user_id = %s AND status = 'closed'
                """,
                (user_id,),
            )
            total, pnl_sum, wins = cur.fetchone()
    finally:
        conn.close()

    winrate = (wins / total * 100) if total else 0
    await update.message.reply_text(
        f"📊 *Statistiques de trading*\n\n"
        f"Trades clôturés : {total}\n"
        f"PnL cumulé : {pnl_sum:.2f} USDT\n"
        f"Win rate : {winrate:.1f}%",
        parse_mode="Markdown",
    )


async def cmd_trade_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT symbol, direction, pnl_usdt, exit_reason, closed_at
                FROM trades WHERE user_id = %s AND status = 'closed'
                ORDER BY closed_at DESC LIMIT 10
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        await update.message.reply_text("Aucun trade dans l'historique.")
        return

    lines = ["🕓 *10 derniers trades*\n"]
    for symbol, direction, pnl, reason, closed_at in rows:
        emoji = "🟢" if (pnl or 0) >= 0 else "🔴"
        lines.append(f"{emoji} `{symbol}` {direction} — {pnl:.2f} USDT ({reason})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_setleverage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage : /setleverage <valeur_entière>")
        return
    leverage = int(context.args[0])
    if leverage < 1 or leverage > 125:
        await update.message.reply_text("Le levier doit être entre 1 et 125.")
        return
    update_config(user_id, leverage=leverage)
    await update.message.reply_text(f"Levier mis à jour : x{leverage}")


async def cmd_setrisk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage : /setrisk <pourcentage>")
        return
    try:
        risk = float(context.args[0])
    except ValueError:
        await update.message.reply_text("Valeur invalide.")
        return
    if risk <= 0 or risk > 20:
        await update.message.reply_text("Le risque par trade doit être entre 0 et 20%.")
        return
    update_config(user_id, risk_per_trade=risk)
    await update.message.reply_text(f"Risque par trade mis à jour : {risk}%")


async def cmd_whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage : /whitelist <SYMBOLE>")
        return
    symbol = context.args[0].upper()
    config = get_config(user_id)
    wl = list(set(config.symbol_whitelist + [symbol]))
    update_config(user_id, symbol_whitelist=wl)
    await update.message.reply_text(f"{symbol} ajouté à la whitelist.")


async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage : /blacklist <SYMBOLE>")
        return
    symbol = context.args[0].upper()
    config = get_config(user_id)
    bl = list(set(config.symbol_blacklist + [symbol]))
    update_config(user_id, symbol_blacklist=bl)
    await update.message.reply_text(f"{symbol} ajouté à la blacklist.")


async def cmd_emergency_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("🛑 Fermeture de toutes les positions en cours...")
    closed = emergency_stop_all(user_id)
    await update.message.reply_text(
        f"✅ {closed} position(s) fermée(s). Mode automatique désactivé."
    )


# ---------------------------------------------------------------------------
# Menu principal (boutons)
# ---------------------------------------------------------------------------

def build_autotrade_menu_buttons() -> list:
    """À insérer dans build_main_menu() du bot existant."""
    return [
        [InlineKeyboardButton("📊 AutoTrade", callback_data="menu_autotrade")],
        [InlineKeyboardButton("📈 Positions", callback_data="menu_positions")],
        [InlineKeyboardButton("⚙️ Trading Config", callback_data="menu_trading_config")],
    ]


async def trading_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "menu_autotrade":
        config = get_config(user_id)
        status = "ON ✅" if config.auto_trade else "OFF ❌"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Basculer (actuellement {status})", callback_data="toggle_autotrade")]
        ])
        await query.edit_message_text(f"Mode automatique : {status}", reply_markup=keyboard)

    elif data == "toggle_autotrade":
        config = get_config(user_id)
        update_config(user_id, auto_trade=not config.auto_trade)
        await query.edit_message_text("Configuration mise à jour. Relance /autotrade pour voir le nouvel état.")

    elif data == "menu_positions":
        trades = get_open_trades(user_id)
        if not trades:
            await query.edit_message_text("Aucune position ouverte.")
            return
        lines = [f"#{t['id']} {t['symbol']} {t['direction']} qty={t['quantity']}" for t in trades]
        await query.edit_message_text("📈 Positions ouvertes :\n" + "\n".join(lines))

    elif data == "menu_trading_config":
        config = get_config(user_id)
        await query.edit_message_text(
            f"Levier x{config.leverage} | Risque {config.risk_per_trade}% | "
            f"Max positions {config.max_positions}\nUtilise /config pour le détail complet."
        )

    elif data.startswith("trading_open_"):
        signal_id = data.replace("trading_open_", "")
        await _confirm_open_signal(query, context, signal_id)

    elif data.startswith("trading_reject_"):
        signal_id = data.replace("trading_reject_", "")
        mark_signal_status(signal_id, "rejected")
        await query.edit_message_text("❌ Signal refusé.")

    elif data.startswith("trading_edit_"):
        signal_id = data.replace("trading_edit_", "")
        await query.edit_message_text(
            f"Pour modifier SL/TP du signal {signal_id}, réponds avec :\n"
            f"/editsignal {signal_id} <nouveau_sl> <nouveau_tp>"
        )


async def _confirm_open_signal(query, context: ContextTypes.DEFAULT_TYPE, signal_id: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, symbol, direction, entry_price, sl, tp, score "
                "FROM signals WHERE id = %s",
                (signal_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        await query.edit_message_text("Signal introuvable (peut-être déjà expiré).")
        return

    cols = ["id", "user_id", "symbol", "direction", "entry_price", "sl", "tp", "score"]
    signal = dict(zip(cols, row))
    config = get_config(signal["user_id"])

    trade = execute_signal(signal, config)
    if trade["status"] == "open":
        await query.edit_message_text(
            f"✅ Position ouverte : {trade['symbol']} {trade['direction']} qty={trade['quantity']}"
        )
    else:
        await query.edit_message_text(f"⚠️ Échec d'ouverture : {trade.get('error_message')}")


# ---------------------------------------------------------------------------
# Commandes admin (à enregistrer dans admin_handlers.py, avec vérif ADMIN_ID)
# ---------------------------------------------------------------------------

async def admin_cmd_trading_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*), COALESCE(SUM(pnl_usdt), 0) FROM trades WHERE status = 'closed'"
            )
            total, pnl_sum = cur.fetchone()
            cur.execute("SELECT COUNT(*) FROM trades WHERE status = 'open'")
            open_count = cur.fetchone()[0]
    finally:
        conn.close()
    await update.message.reply_text(
        f"📊 Stats globales : {total} trades clôturés | PnL cumulé {pnl_sum:.2f} USDT | "
        f"{open_count} positions ouvertes actuellement."
    )


async def admin_cmd_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trades = get_open_trades()
    if not trades:
        await update.message.reply_text("Aucune position ouverte, tous utilisateurs confondus.")
        return
    lines = [f"#{t['id']} user={t['user_id']} {t['symbol']} {t['direction']}" for t in trades]
    await update.message.reply_text("\n".join(lines))


async def admin_cmd_forceclose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage : /forceclose <user_id>")
        return
    target_user = int(context.args[0])
    closed = emergency_stop_all(target_user)
    await update.message.reply_text(f"{closed} position(s) fermée(s) pour l'utilisateur {target_user}.")
