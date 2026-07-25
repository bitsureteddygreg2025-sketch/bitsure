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
from binance_manager import test_connection, get_full_account_info, BinanceClientError
from position_manager import get_open_trades, close_trade_manual, emergency_stop_all
from execution_engine import execute_signal, mark_signal_status
from database import get_connection
from trading_logger import get_trading_logger

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
        f"Style : {config.trading_style}\n"
        f"Timeframe analyse : {config.analysis_timeframe}\n"
        f"Analyse auto : toutes les {config.analysis_interval_minutes} min\n"
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


async def cmd_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /account — Visualisation complète du solde, PnL et positions Binance."""
    user_id = update.effective_user.id
    config = get_config(user_id)

    try:
        info = get_full_account_info(user_id, market_type=config.market_type)
    except BinanceClientError as e:
        msg = f"❌ {e}"
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    lines = [
        f"💼 *Tableau de Bord Compte Binance ({info['market_type'].upper()})*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"💰 *Solde Total* : `{info['total_wallet_balance']:.2f} USDT`",
        f"💵 *Disponible* : `{info['available_balance']:.2f} USDT`",
        f"📊 *PnL Non Réalisé* : `{info['unrealized_pnl']:+.2f} USDT`",
    ]

    if info["market_type"] == "futures":
        lines.append(f"⚡ *Taux Marge Utilisée* : `{info['margin_used_pct']}%`")

    lines.append("\n🪙 *Détail des Actifs* :")
    if info["assets"]:
        for a in info["assets"][:5]:
            if info["market_type"] == "futures":
                lines.append(f"  • *{a['asset']}* : {a['wallet']:.4f} (PnL: {a.get('unrealized_pnl', 0):+.2f})")
            else:
                lines.append(f"  • *{a['asset']}* : {a['total']:.4f} (~{a.get('usdt_value', 0):.2f} USDT)")
    else:
        lines.append("  *Aucun actif actif.*")

    lines.append("\n📈 *Positions Ouvertes Binance* :")
    if info["positions"]:
        for p in info["positions"]:
            lines.append(
                f"  • *{p['symbol']}* ({p['side']} x{p['leverage']})\n"
                f"    Qty: {p['quantity']} | Entrée: {p['entry_price']:.4f} | Prix: {p['mark_price']:.4f}\n"
                f"    PnL: `{p['unrealized_pnl']:+.2f} USDT` | Liq: {p['liquidation_price']:.4f}"
            )
    else:
        lines.append("  *Aucune position ouverte sur Binance.*")

    if info.get("recent_trades"):
        lines.append(f"\n💸 *Commissions Récentes* : `{info['total_commissions']:.4f} USDT`")

    keyboard = [
        [
            InlineKeyboardButton("🔄 Rafraîchir", callback_data="cmd_account"),
            InlineKeyboardButton("🏠 Menu Principal", callback_data="menu_back"),
        ]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text("\n".join(lines), reply_markup=markup, parse_mode="Markdown")
    else:
        await update.message.reply_text("\n".join(lines), reply_markup=markup, parse_mode="Markdown")


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
            [InlineKeyboardButton(f"Basculer (actuellement {status})", callback_data="toggle_autotrade")],
            [InlineKeyboardButton("Mode spot/futures", callback_data="menu_market_mode")],
            [InlineKeyboardButton("Analyse periodique", callback_data="menu_analysis_config")],
            [InlineKeyboardButton("Configuration", callback_data="menu_trading_config")],
            [InlineKeyboardButton("🏠 Menu Principal", callback_data="menu_back")],
        ])
        await query.edit_message_text(
            f"🤖 *AutoTrade Binance*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Mode automatique : *{status}*\n"
            f"Marché : *{config.market_type.upper()}*\n"
            f"Analyse : *{config.analysis_timeframe} / {config.analysis_interval_minutes} min*\n"
            f"Style : *{config.trading_style}*",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    elif data == "toggle_autotrade":
        config = get_config(user_id)
        update_config(user_id, auto_trade=not config.auto_trade)
        query.data = "menu_autotrade"
        await trading_callback_router(update, context)

    elif data == "menu_market_mode":
        config = get_config(user_id)
        spot_label = "🟢 Spot (Actif)" if config.market_type == "spot" else "Spot"
        futures_label = "🟢 Futures (Actif)" if config.market_type == "futures" else "Futures"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(spot_label, callback_data="set_market_spot"),
                InlineKeyboardButton(futures_label, callback_data="set_market_futures"),
            ],
            [
                InlineKeyboardButton("⬅️ Retour AutoTrade", callback_data="menu_autotrade"),
                InlineKeyboardButton("🏠 Menu Principal", callback_data="menu_back"),
            ],
        ])
        await query.edit_message_text(
            f"🎯 *Mode de Marché Actuel :* `{config.market_type.upper()}`\n\n"
            f"Choisis le mode à utiliser pour les analyses et la prise d'ordres.",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif data.startswith("set_market_"):
        market_type = data.replace("set_market_", "")
        if market_type not in ("spot", "futures"):
            await query.edit_message_text("Mode de marché invalide.")
            return
        update_config(user_id, market_type=market_type)
        query.data = "menu_market_mode"
        await trading_callback_router(update, context)

    elif data == "menu_analysis_config":
        config = get_config(user_id)
        p_status = "ACTIVÉE ✅" if config.periodic_analysis_enabled else "DÉSACTIVÉE ❌"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"Analyse Périodique ({p_status})", callback_data="toggle_periodic_analysis"),
            ],
            [
                InlineKeyboardButton("5 min", callback_data="set_analysis_interval_5"),
                InlineKeyboardButton("10 min", callback_data="set_analysis_interval_10"),
            ],
            [
                InlineKeyboardButton("5m", callback_data="set_analysis_tf_5m"),
                InlineKeyboardButton("15m", callback_data="set_analysis_tf_15m"),
                InlineKeyboardButton("1h", callback_data="set_analysis_tf_1h"),
            ],
            [
                InlineKeyboardButton("Scalping 5m", callback_data="set_analysis_style_scalping"),
                InlineKeyboardButton("Scalping 15m", callback_data="set_analysis_style_scalping_15m"),
            ],
            [
                InlineKeyboardButton("Day", callback_data="set_analysis_style_day"),
                InlineKeyboardButton("Swing", callback_data="set_analysis_style_swing"),
                InlineKeyboardButton("Position", callback_data="set_analysis_style_position"),
            ],
            [
                InlineKeyboardButton("⬅️ Retour AutoTrade", callback_data="menu_autotrade"),
                InlineKeyboardButton("⬅️ Retour Analyse", callback_data="menu_analyse"),
                InlineKeyboardButton("🏠 Menu Principal", callback_data="menu_back"),
            ],
        ])
        await query.edit_message_text(
            f"📊 *Configuration Analyse Périodique*\n\n"
            f"État : *{p_status}*\n"
            f"Intervalle : *{config.analysis_interval_minutes} min*\n"
            f"Timeframe : *{config.analysis_timeframe}*\n"
            f"Style : *{config.trading_style}*",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif data == "toggle_periodic_analysis":
        config = get_config(user_id)
        new_val = not config.periodic_analysis_enabled
        update_config(user_id, periodic_analysis_enabled=new_val)
        query.data = "menu_analysis_config"
        await trading_callback_router(update, context)

    elif data.startswith("set_analysis_interval_"):
        interval = int(data.replace("set_analysis_interval_", ""))
        if interval not in (5, 10):
            await query.edit_message_text("Intervalle invalide.")
            return
        update_config(user_id, analysis_interval_minutes=interval)
        query.data = "menu_analysis_config"
        await trading_callback_router(update, context)

    elif data.startswith("set_analysis_tf_"):
        timeframe = data.replace("set_analysis_tf_", "")
        if timeframe not in ("5m", "15m", "1h", "4h", "1d"):
            await query.edit_message_text("Timeframe invalide.")
            return
        update_config(user_id, analysis_timeframe=timeframe)
        query.data = "menu_analysis_config"
        await trading_callback_router(update, context)

    elif data.startswith("set_analysis_style_"):
        style = data.replace("set_analysis_style_", "")
        if style not in ("scalping", "scalping_15m", "day", "swing", "position"):
            await query.edit_message_text("Style de trading invalide.")
            return
        fields = {"trading_style": style}
        if style == "scalping":
            fields["analysis_timeframe"] = "5m"
        elif style == "scalping_15m":
            fields["analysis_timeframe"] = "15m"
        update_config(user_id, **fields)
        query.data = "menu_analysis_config"
        await trading_callback_router(update, context)

    elif data == "menu_positions":
        trades = get_open_trades(user_id)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Rafraîchir", callback_data="menu_positions")],
            [InlineKeyboardButton("⬅️ Retour AutoTrade", callback_data="menu_autotrade"), InlineKeyboardButton("🏠 Menu Principal", callback_data="menu_back")]
        ])
        if not trades:
            await query.edit_message_text("📈 *Positions ouvertes :*\n\nAucune position ouverte actuellement.", reply_markup=keyboard, parse_mode="Markdown")
            return
        lines = [f"#{t['id']} {t['symbol']} {t['direction']} qty={t['quantity']} (SL {t['sl_price']} / TP {t['tp_price']})" for t in trades]
        await query.edit_message_text("📈 *Positions ouvertes :*\n\n" + "\n".join(lines), reply_markup=keyboard, parse_mode="Markdown")

    elif data == "menu_trading_config":
        config = get_config(user_id)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Retour AutoTrade", callback_data="menu_autotrade"), InlineKeyboardButton("🏠 Menu Principal", callback_data="menu_back")]
        ])
        await query.edit_message_text(
            f"⚙️ *Trading Config*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Levier : x{config.leverage}\n"
            f"Risque/trade : {config.risk_per_trade}%\n"
            f"Marché : {config.market_type}\n"
            f"Analyse : {config.analysis_timeframe}/{config.analysis_interval_minutes}m\n"
            f"Style : {config.trading_style}\n"
            f"Max positions : {config.max_positions}\n\n"
            f"_Utilise /config pour le détail complet._",
            reply_markup=keyboard,
            parse_mode="Markdown"
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
