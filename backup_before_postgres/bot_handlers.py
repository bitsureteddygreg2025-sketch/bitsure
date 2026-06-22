import asyncio
import logging
from datetime import datetime
import matplotlib.pyplot as plt
import io
import pandas as pd
import random
import hashlib
import time
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import ADMIN_ID, DEFAULT_TIMEFRAME, SYMBOL_CONFIGS, ATR_MULTIPLIER_SL, RR_RATIO_TARGET
from data_fetcher import DataFetcher
from signal_engine import SignalEngine
from indicators import atr
from user_manager import UserManager
from alert_manager import AlertManager
from history_manager import HistoryManager
from utils import format_number, is_valid_symbol, normalize_symbol
from i18n import get_text
from payments import generate_binance_payment
from paper_trader import PaperTrader

logger = logging.getLogger(__name__)
fetcher = DataFetcher.get_instance()
user_mgr = UserManager.get_instance()
alert_mgr = AlertManager.get_instance()
history_mgr = HistoryManager.get_instance()
weekly_scheduler = None
paper_trader = PaperTrader()

SYMBOLS_12 = [
    "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "USDJPY",
    "AUDUSD", "XAUUSD", "AAPL", "TSLA", "NVDA"
]

def generate_signal_id():
    raw = f"{time.time()}-{random.random()}"
    return hashlib.md5(raw.encode()).hexdigest()[:6].upper()

def get_user_lang(update: Update) -> str:
    user_id = update.effective_user.id
    return user_mgr.get_setting(user_id, "lang", "en")

async def respond(update: Update, text: str, **kwargs):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, **kwargs)
        except:
            await update.callback_query.message.reply_text(text, **kwargs)
    else:
        await update.message.reply_text(text, **kwargs)

# =========================================================
# ALERT INPUT HANDLER
# =========================================================

async def handle_pending_alert_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.message.text:
        return False
    pending_symbol = context.user_data.get("pending_alert_symbol")
    pending_cond = context.user_data.get("pending_alert_cond")
    if not pending_symbol or not pending_cond:
        return False
    lang = get_user_lang(update)
    try:
        price = float(update.message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(get_text(lang, "alert_price_invalid_retry"))
        return True
    symbol = normalize_symbol(pending_symbol)
    cond_label = get_text(lang, "cond_above") if pending_cond == "above" else get_text(lang, "cond_below")
    ok, result = alert_mgr.add_alert(update.effective_user.id, symbol, pending_cond, price)
    if not ok:
        await update.message.reply_text(f"❌ Limite atteinte ({result} alertes max)")
        return True
    await update.message.reply_text(get_text(lang, "alert_created", id=result, symbol=symbol, cond=cond_label, price=price))
    context.user_data.pop("pending_alert_symbol", None)
    context.user_data.pop("pending_alert_cond", None)
    return True

# =========================================================
# LIMIT CHECK
# =========================================================

def check_limit(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        lang = get_user_lang(update)
        import logging
        logging.getLogger(__name__).warning(f"[check_limit] func={func.__name__}, user={user_id}")
        if not user_mgr.can_access_bot(user_id):
            if update.callback_query:
                await update.callback_query.answer("🚧 Access by invitation only. Contact @btsr_teddy09", show_alert=True)
                return
            else:
                await update.message.reply_text("🚧 Access by invitation only.\n\nContact @btsr_teddy09 to get an invitation.")
                return
        if func.__name__ != "start" and not user_mgr.has_accepted_terms(user_id) and not user_mgr.is_admin(user_id):
            if update.callback_query:
                await update.callback_query.answer(get_text(lang, "terms_must_accept"), show_alert=True)
                return
            else:
                await update.message.reply_text(get_text(lang, "terms_must_accept"))
                return
        if not user_mgr.check_limit(user_id):
            if update.callback_query:
                await update.callback_query.answer(get_text(lang, "limit_reached"), show_alert=True)
                return
            else:
                await update.message.reply_text(get_text(lang, "limit_reached"))
                return
        if not user_mgr.is_admin(user_id):
            user_mgr.increment_usage(user_id)
        return await func(update, context, *args, **kwargs)
    return wrapper

# =========================================================
# NOTIFICATIONS ADMIN
# =========================================================

async def notify_admin_new_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    msg = f"🆕 *Nouvel utilisateur* : {username} (ID: `{user.id}`)"
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.warning(f"Impossible de notifier l'admin : {e}")

async def notify_admin_new_premium(context: ContextTypes.DEFAULT_TYPE, user, role: str, method: str):
    try:
        username = f"@{user.username}" if user.username else user.first_name
        admin_msg = (
            f"💰 *Nouveau PREMIUM !*\n"
            f"• Utilisateur : {username} (ID: `{user.id}`)\n"
            f"• Nouveau rôle : *{role.upper()}*\n"
            f"• Méthode : {method}"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.warning(f"Impossible de notifier l'admin : {e}")

# =========================================================
# START
# =========================================================

@check_limit

@check_limit
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update)
    await update.message.reply_text(get_text(lang, "help_redirect"), parse_mode=ParseMode.MARKDOWN)

@check_limit
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_text(get_user_lang(update), "support"))

# =========================================================
# MENU PRINCIPAL
# =========================================================

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update)
    keyboard = [
        [InlineKeyboardButton(get_text(lang, "menu_analyse"), callback_data="menu_analyse")],
        [InlineKeyboardButton(get_text(lang, "menu_alertes"), callback_data="menu_alertes")],
        [InlineKeyboardButton(get_text(lang, "menu_watchlist"), callback_data="menu_watchlist")],
        [InlineKeyboardButton(get_text(lang, "menu_paper"), callback_data="menu_paper")],
        [InlineKeyboardButton(get_text(lang, "menu_parametres"), callback_data="menu_parametres")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(get_text(lang, "menu_title"), reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

@check_limit
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    lang = get_user_lang(update)
    user_id = update.effective_user.id

    def safe_edit(text, keyboard):
        try:
            return query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        except:
            return query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

    # --- Direction callbacks ---
    if data.startswith("paperdir_"):
        parts = data.split("_")
        if len(parts) >= 3:
            context.args = [parts[2].lower(), parts[1]]
            await paper(update, context)
        return

    # --- Sous-menus ---
    if data == "menu_analyse":
        keyboard = [
            [InlineKeyboardButton(get_text(lang, "btn_analyse"), callback_data="cmd_analyse")],
            [InlineKeyboardButton(get_text(lang, "btn_price"), callback_data="cmd_price")],
            [InlineKeyboardButton(get_text(lang, "btn_trend"), callback_data="cmd_trend")],
            [InlineKeyboardButton(get_text(lang, "btn_volatility"), callback_data="cmd_volatility")],
            [InlineKeyboardButton(get_text(lang, "btn_levels"), callback_data="cmd_levels")],
            [InlineKeyboardButton(get_text(lang, "back"), callback_data="menu_back")]
        ]
        await safe_edit(f"*{get_text(lang, 'menu_analyse')}*\n{get_text(lang, 'menu_choose_command')}", keyboard)

    elif data == "menu_paper":
        keyboard = [
            [InlineKeyboardButton(get_text(lang, "btn_paper_buy"), callback_data="cmd_paper")],
            [InlineKeyboardButton(get_text(lang, "btn_paper_status"), callback_data="cmd_paper_status")],
            [InlineKeyboardButton(get_text(lang, "btn_paper_history"), callback_data="cmd_paper_history")],
            [InlineKeyboardButton(get_text(lang, "btn_paper_stats"), callback_data="cmd_paper_stats")],
            [InlineKeyboardButton(get_text(lang, "back"), callback_data="menu_back")]
        ]
        await safe_edit(f"*{get_text(lang, 'menu_paper')}*\n{get_text(lang, 'menu_choose_command')}", keyboard)

    elif data == "menu_alertes":
        keyboard = [
            [InlineKeyboardButton(get_text(lang, "btn_alert"), callback_data="cmd_alert")],
            [InlineKeyboardButton(get_text(lang, "btn_alerts"), callback_data="cmd_alerts")],
            [InlineKeyboardButton(get_text(lang, "btn_delalert"), callback_data="cmd_delalert")],
            [InlineKeyboardButton(get_text(lang, "btn_clearalerts"), callback_data="cmd_clearalerts")],
            [InlineKeyboardButton(get_text(lang, "back"), callback_data="menu_back")]
        ]
        await safe_edit(f"*{get_text(lang, 'menu_alertes')}*\n{get_text(lang, 'menu_choose_command')}", keyboard)

    elif data == "menu_watchlist":
        keyboard = [
            [InlineKeyboardButton(get_text(lang, "btn_watchlist"), callback_data="cmd_watchlist")],
            [InlineKeyboardButton(get_text(lang, "btn_addwatch"), callback_data="cmd_addwatch")],
            [InlineKeyboardButton(get_text(lang, "btn_removewatch"), callback_data="cmd_removewatch")],
            [InlineKeyboardButton(get_text(lang, "btn_scan"), callback_data="cmd_scan")],
            [InlineKeyboardButton(get_text(lang, "back"), callback_data="menu_back")]
        ]
        await safe_edit(f"*{get_text(lang, 'menu_watchlist')}*\n{get_text(lang, 'menu_choose_command')}", keyboard)

    elif data == "menu_parametres":
        lang = get_user_lang(update)
        uid  = update.effective_user.id
        tf   = user_mgr.get_setting(uid, "timeframe", DEFAULT_TIMEFRAME)
        style = user_mgr.get_setting(uid, "trading_style", "day")
        style_names = {"day": "Day Trader", "swing": "Swing Trader", "position": "Position Trader"}
        style_display = style_names.get(style, style)
        recap = (
            get_text(lang, "settings_title") + "\n"
            + get_text(lang, "settings_timeframe") + " : " + tf + "\n"
            + get_text(lang, "settings_style") + " : " + style_display + "\n"
            + get_text(lang, "settings_lang") + " : " + lang.upper() + "\n\n"
            + get_text(lang, "settings_edit")
        )
        keyboard = [
            [InlineKeyboardButton(get_text(lang, "btn_settimeframe"), callback_data="cmd_settimeframe")],
            [InlineKeyboardButton(get_text(lang, "btn_setlanguage"),  callback_data="cmd_setlanguage")],
            [InlineKeyboardButton("🎯 Trading Style", callback_data="cmd_setstyle")],
            [InlineKeyboardButton(get_text(lang, "btn_historique"), callback_data="cmd_historique")],
            [InlineKeyboardButton(get_text(lang, "btn_support"), callback_data="cmd_support")],
            [InlineKeyboardButton(get_text(lang, "back"), callback_data="menu_back")],
        ]
        await safe_edit(recap, keyboard)
    elif data == "menu_back":
        keyboard = [
            [InlineKeyboardButton(get_text(lang, "menu_analyse"), callback_data="menu_analyse")],
            [InlineKeyboardButton(get_text(lang, "menu_alertes"), callback_data="menu_alertes")],
            [InlineKeyboardButton(get_text(lang, "menu_watchlist"), callback_data="menu_watchlist")],
            [InlineKeyboardButton(get_text(lang, "menu_paper"), callback_data="menu_paper")],
            [InlineKeyboardButton(get_text(lang, "menu_parametres"), callback_data="menu_parametres")],
        ]
        await safe_edit(get_text(lang, "menu_title"), keyboard)

    # --- Command execution ---
    if data.startswith("cmd_"):
        cmd = data.replace("cmd_", "")

        if cmd.startswith("alertcond_"):
            _, symbol, cond = cmd.split("_")
            context.user_data["pending_alert_symbol"] = symbol
            context.user_data["pending_alert_cond"] = cond
            await query.message.reply_text(get_text(lang, "alert_enter_price"))
            return

        if cmd.startswith("settimeframe_"):
            context.args = [cmd.split("_", 1)[1]]
            await settimeframe(update, context)
            return

        if cmd.startswith("setstyle_"):
            style = cmd.split("_", 1)[1]
            user_mgr.set_setting(update.effective_user.id, "trading_style", style)
            style_names = {"day": "📊 Day Trader (1h)", "swing": "📈 Swing Trader (4h)", "position": "🏦 Position Trader (1d)"}
            await query.message.reply_text(f"Style set to: {style_names.get(style, style)}")
            return

        if cmd.startswith("setlanguage_"):
            context.args = [cmd.split("_", 1)[1]]
            await setlanguage(update, context)
            return

        if cmd.startswith("delalert_"):
            context.args = [cmd.split("_", 1)[1]]
            await delalert(update, context)
            return

        if cmd in ["analyse", "price", "trend", "volatility", "levels", "alert", "addwatch", "removewatch", "paper"]:
            await symbol_selection(update, context, cmd)

        elif cmd == "alerts":
            alerts_list = alert_mgr.get_alerts(user_id)
            if not alerts_list:
                await query.message.reply_text(get_text(lang, "alerts_empty"))
            else:
                text = get_text(lang, "alerts_list_title")
                for a in alerts_list:
                    status = "✅" if a.get("triggered") else "⏳"
                    text += f"{status} #{a['id']} {a['symbol']} {a['condition']} {a['price']}\n"
                await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

        elif cmd == "clearalerts":
            keyboard = [
                [InlineKeyboardButton(get_text(lang, "confirm_yes"), callback_data="clearalerts_confirm")],
                [InlineKeyboardButton(get_text(lang, "confirm_no"), callback_data="clearalerts_cancel")]
            ]
            await query.message.reply_text(get_text(lang, "clearalerts_confirm"), reply_markup=InlineKeyboardMarkup(keyboard))

        elif cmd == "watchlist":
            wl = user_mgr.get_watchlist(user_id)
            if not wl:
                await query.message.reply_text(get_text(lang, "watchlist_empty"))
            else:
                await query.message.reply_text(get_text(lang, "watchlist_show", symbols="\n".join(wl)), parse_mode=ParseMode.MARKDOWN)

        elif cmd == "scan":
            wl = user_mgr.get_watchlist(user_id)
            if not wl:
                await query.message.reply_text(get_text(lang, "watchlist_scan_empty"))
            else:
                tf = user_mgr.get_setting(user_id, "timeframe", DEFAULT_TIMEFRAME)
                style = user_mgr.get_setting(user_id, "trading_style", "day")
                results = []
                engine = SignalEngine()
                for sym in wl:
                    df = await fetcher.get_historical_data(sym, timeframe=tf)
                    if df is not None and not df.empty:
                        res = engine.analyze(df, lang, symbol=sym, style=style)
                        results.append(f"{sym}: {res['signal_text']} (Score: {res['teddy_score']})")
                    else:
                        results.append(f"{sym}: {get_text(lang, 'data_unavailable')}")
                await query.message.reply_text(get_text(lang, "watchlist_scan_result", results="\n".join(results)), parse_mode=ParseMode.MARKDOWN)

        elif cmd == "settimeframe":
            kb = [[InlineKeyboardButton("1h", callback_data="cmd_settimeframe_1h"), InlineKeyboardButton("4h", callback_data="cmd_settimeframe_4h"), InlineKeyboardButton("1d", callback_data="cmd_settimeframe_1d")]]
            await query.message.reply_text(get_text(lang, "settimeframe_choose"), reply_markup=InlineKeyboardMarkup(kb))

        elif cmd == "setstyle":
            kb = [
                [InlineKeyboardButton("📊 Day Trader (1h)", callback_data="cmd_setstyle_day")],
                [InlineKeyboardButton("📈 Swing Trader (4h)", callback_data="cmd_setstyle_swing")],
                [InlineKeyboardButton("🏦 Position Trader (1d)", callback_data="cmd_setstyle_position")],
            ]
            await query.message.reply_text("Choose your trading style:", reply_markup=InlineKeyboardMarkup(kb))

        elif cmd == "setlanguage":
            kb = [[InlineKeyboardButton("FR", callback_data="cmd_setlanguage_fr"), InlineKeyboardButton("EN", callback_data="cmd_setlanguage_en")]]
            await query.message.reply_text(get_text(lang, "setlanguage_choose"), reply_markup=InlineKeyboardMarkup(kb))

        elif cmd == "delalert":
            alerts_list = alert_mgr.get_alerts(user_id)
            if not alerts_list:
                await query.message.reply_text(get_text(lang, "alerts_empty"))
            else:
                kb = [[InlineKeyboardButton(f"#{a['id']} {a['symbol']} {a['condition']} {a['price']}", callback_data=f"cmd_delalert_{a['id']}")] for a in alerts_list]
                await query.message.reply_text(get_text(lang, "delalert_pick"), reply_markup=InlineKeyboardMarkup(kb))

        elif cmd == "settings":
            uid = user_id
            lang2 = user_mgr.get_setting(uid, "lang", "en")
            tf = user_mgr.get_setting(uid, "timeframe", DEFAULT_TIMEFRAME)
            role = user_mgr.get_role(uid)
            prem = "✅" if role == "pro" else "❌"
            await query.message.reply_text(get_text(lang2, "settings_info", tf=tf, lang_name=lang2.upper(), role=role.upper(), prem=prem), parse_mode=ParseMode.MARKDOWN)

        elif cmd == "historique":
            kb = [
                [InlineKeyboardButton(get_text(lang, "btn_historique"), callback_data="cmd_historique_view")],
                [InlineKeyboardButton("🗑️ " + get_text(lang, "clearhistory_btn"), callback_data="cmd_historique_clear")],
            ]
            await query.message.reply_text(get_text(lang, "history_menu_title"), reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

        elif cmd == "historique_view":
            await historique(update, context)

        elif cmd == "historique_clear":
            uid = update.effective_user.id
            history_mgr.conn.execute("DELETE FROM signals WHERE user_id = ?", (uid,))
            history_mgr.conn.commit()
            await query.message.reply_text("🗑️ Your history has been cleared.")

        elif cmd == "usage":
            rem = user_mgr.get_remaining_requests(user_id)
            if rem == -1:
                await query.message.reply_text(get_text(lang, "usage_unlimited"))
            else:
                await query.message.reply_text(get_text(lang, "usage_requests_remaining", rem=rem))

        elif cmd == "paper_status":
            context.args = ["status"]
            await paper(update, context)

        elif cmd == "paper_history":
            context.args = ["history"]
            await paper(update, context)

        elif cmd == "paper_stats":
            context.args = ["stats"]
            await paper(update, context)

        elif cmd == "support":
            await query.message.reply_text(get_text(lang, "support"))

        else:
            await query.message.reply_text(get_text(lang, "unknown_command"))

    # --- Callbacks hors cmd_ ---
    if data == "clearalerts_confirm":
        alert_mgr.clear_alerts(user_id)
        await query.edit_message_text(get_text(lang, "alerts_cleared"))
    elif data == "clearalerts_cancel":
        await query.edit_message_text(get_text(lang, "action_cancelled"))

# =========================================================
# SYMBOL SELECTION
# =========================================================

async def symbol_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, command: str, page: int = 0):
    query = update.callback_query
    await query.answer()
    lang = get_user_lang(update)
    symbols = SYMBOLS_12
    per_page = 8
    total_pages = (len(symbols) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = start + per_page
    page_symbols = symbols[start:end]
    keyboard = []
    for sym in page_symbols:
        keyboard.append([InlineKeyboardButton(sym, callback_data=f"symsel_{command}_{sym}")])
    if total_pages > 1:
        page_row = []
        if page > 0:
            page_row.append(InlineKeyboardButton("◀️", callback_data=f"sympage_{command}_{page-1}"))
        page_row.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            page_row.append(InlineKeyboardButton("▶️", callback_data=f"sympage_{command}_{page+1}"))
        keyboard.append(page_row)
    keyboard.append([InlineKeyboardButton(get_text(lang, "back"), callback_data="menu_back")])
    text = get_text(lang, "select_symbol")
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except:
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def symbol_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    lang = get_user_lang(update)
    if data.startswith("sympage_"):
        parts = data.split("_")
        if len(parts) >= 3:
            _, command, page = parts[0], parts[1], parts[2]
            await symbol_selection(update, context, command, int(page))
        return
    elif data.startswith("symsel_"):
        parts = data.split("_", 2)
        if len(parts) >= 3:
            _, command, symbol = parts
            context.args = [symbol]
            if command == "analyse":
                await analyse(update, context, from_callback=True)
            elif command == "price":
                await price(update, context, from_callback=True)
            elif command == "trend":
                await trend(update, context, from_callback=True)
            elif command == "volatility":
                await volatility(update, context, from_callback=True)
            elif command == "levels":
                await levels(update, context, from_callback=True)
            elif command == "alert":
                kb = [[InlineKeyboardButton(get_text(lang, "cond_above"), callback_data=f"cmd_alertcond_{symbol}_above"), InlineKeyboardButton(get_text(lang, "cond_below"), callback_data=f"cmd_alertcond_{symbol}_below")]]
                await query.message.reply_text(get_text(lang, "alert_choose_condition"), reply_markup=InlineKeyboardMarkup(kb))
            elif command == "addwatch":
                context.args = [symbol]
                await addwatch(update, context)
            elif command == "removewatch":
                context.args = [symbol]
                await removewatch(update, context)
            elif command == "paper":
                kb = [
                    [InlineKeyboardButton("BUY 🟢", callback_data=f"paperdir_{symbol}_BUY"),
                     InlineKeyboardButton("SELL 🔴", callback_data=f"paperdir_{symbol}_SELL")]
                ]
                await query.message.reply_text(get_text(lang, "paper_choose_direction", symbol=symbol), reply_markup=InlineKeyboardMarkup(kb))
        return
    elif data == "noop":
        return

# ---------- START ----------
@check_limit
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    lang = user_mgr.get_setting(user_id, "lang", "en")
    was_new = not user_mgr.user_exists(user_id)
    user_mgr.get_user(user_id)
    username = f"@{user.username}" if user.username else user.first_name
    user_mgr.update_username(user_id, username)
    if was_new:
        await notify_admin_new_user(update, context)
    if not user_mgr.has_accepted_terms(user_id):
        keyboard = [
            [InlineKeyboardButton(get_text(lang, "terms_button"), callback_data="terms_show")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        welcome = get_text(lang, "start", status=get_text(lang, "status_free_trial"))
        await update.message.reply_text(
            welcome + "\n\n" + get_text(lang, "terms_must_accept"),
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    if not user_mgr.can_access_bot(user_id):
        await update.message.reply_text("🚧 Access by invitation only.\n\nContact @btsr_teddy09 to get an invitation.")
        return
    role = user_mgr.get_role(user_id)
    if role == "free" and user_mgr.is_trial_valid(user_id):
        status = get_text(lang, "status_free_trial")
    elif role == "free":
        status = get_text(lang, "status_free_ended")
    elif role == "pro":
        status = get_text(lang, "status_pro")
    else:
        status = role.upper()
    welcome = get_text(lang, "start", status=status)
    disclaimer = get_text(lang, "start_disclaimer")
    payment_info = get_text(lang, "international_payment_info") if role == "free" else ""
    full_text = welcome + disclaimer + payment_info
    await update.message.reply_text(full_text, parse_mode=ParseMode.MARKDOWN)

async def terms_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    lang = get_user_lang(update)
    user_id = update.effective_user.id
    if data == "terms_show":
        keyboard = [
            [InlineKeyboardButton(get_text(lang, "terms_accept"), callback_data="terms_accept")],
            [InlineKeyboardButton(get_text(lang, "terms_refuse"), callback_data="terms_refuse")],
        ]
        await query.edit_message_text(
            get_text(lang, "terms_text"),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    elif data == "terms_accept":
        user_mgr.accept_terms(user_id)
        await query.edit_message_text(
            get_text(lang, "terms_accepted"),
            parse_mode=ParseMode.MARKDOWN
        )
        context.args = []
        await start(update, context)
    elif data == "terms_refuse":
        await query.edit_message_text(
            get_text(lang, "terms_refused_msg"),
            parse_mode=ParseMode.MARKDOWN
        )

@check_limit
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update)
    trial_msg = ""
    if user_mgr.get_role(update.effective_user.id) == "free" and user_mgr.is_trial_valid(update.effective_user.id):
        from datetime import datetime
        from config import TRIAL_DAYS
        user_id = update.effective_user.id
        user = user_mgr.get_user(user_id)
        trial_start = user.get("joined", time.time())
        trial_end = trial_start + (TRIAL_DAYS * 24 * 3600)
        trial_days = max(0, int((trial_end - time.time()) / 86400))
        trial_msg = "\n" + get_text(lang, "trial_days_left", days=trial_days)
    await update.message.reply_text(get_text(lang, "help_redirect") + trial_msg, parse_mode=ParseMode.MARKDOWN)

@check_limit
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_text(get_user_lang(update), "support"))

# ---------- UPGRADE ----------
@check_limit
async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update)
    keyboard = [
        [InlineKeyboardButton(get_text(lang, "button_pro_stars"), callback_data="plan_pro_stars")],
        [InlineKeyboardButton(get_text(lang, "button_binance_usdc"), callback_data="plan_binance")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(get_text(lang, "upgrade_title"), parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

@check_limit
async def analyse(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    if await handle_pending_alert_input(update, context):
        return
    lang = get_user_lang(update)
    symbol = context.args[0].upper() if context.args else None
    if not symbol:
        await respond(update, get_text(lang, "analyse_usage"), parse_mode=ParseMode.MARKDOWN)
        return
    if not is_valid_symbol(symbol):
        await respond(update, get_text(lang, "symbole_invalide"))
        return
    symbol = normalize_symbol(symbol)
    if from_callback:
        msg = await update.callback_query.edit_message_text(get_text(lang, "analyse_wait", symbol=symbol))
    else:
        msg = await update.message.reply_text(get_text(lang, "analyse_wait", symbol=symbol))
    tf = user_mgr.get_setting(update.effective_user.id, "timeframe", DEFAULT_TIMEFRAME)
    df = await fetcher.get_historical_data(symbol, timeframe=tf)
    if df is None or df.empty:
        await msg.edit_text(get_text(lang, "analyse_error", symbol=symbol))
        return
    trading_style = user_mgr.get_setting(update.effective_user.id, "trading_style", "day")
    result = SignalEngine.analyze(df, lang, symbol=symbol, style=trading_style)
    ind = result['indicators']
    rsi_val = ind.get('rsi', 50)
    adx_val = ind.get('adx', 20)
    if rsi_val >= 70:
        rsi_state = get_text(lang, "rsi_overbought")
    elif rsi_val <= 30:
        rsi_state = get_text(lang, "rsi_oversold")
    elif rsi_val >= 55:
        rsi_state = get_text(lang, "rsi_bullish")
    elif rsi_val <= 45:
        rsi_state = get_text(lang, "rsi_bearish")
    else:
        rsi_state = get_text(lang, "rsi_neutral")
    if adx_val >= 40:
        adx_state = get_text(lang, "adx_very_strong")
    elif adx_val >= 25:
        adx_state = get_text(lang, "adx_strong")
    elif adx_val >= 20:
        adx_state = get_text(lang, "adx_moderate")
    else:
        adx_state = get_text(lang, "adx_weak")
    plt.style.use('dark_background')
    # Zoom sur les 5 derniers jours
    df_plot = df.iloc[-120:] if len(df) > 120 else df
    close_plot = df_plot['Close']
    # Indicateurs sur la meme periode
    sma20_plot = pd.Series(ind['sma20'], index=df.index).iloc[-120:] if ind['sma20'] else None
    sma50_plot = pd.Series(ind['sma50'], index=df.index).iloc[-120:] if ind['sma50'] else None

    fig, (ax, ax_macd) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [3, 1]})

    # ── Graphique principal ──────────────────────────────────
    ax.plot(df_plot.index, close_plot, color='white', linewidth=1.2, label='Prix')
    if sma20_plot is not None:
        ax.plot(df_plot.index, sma20_plot, color='orange', linestyle='--', linewidth=1, label='SMA20')
    if sma50_plot is not None:
        ax.plot(df_plot.index, sma50_plot, color='cyan', linestyle='--', linewidth=1, label='SMA50')

    bb_lower = ind.get('bb_lower')
    bb_upper = ind.get('bb_upper')
    if bb_lower is not None and bb_upper is not None:
        ax.fill_between(df_plot.index, bb_lower, bb_upper, alpha=0.08, color='gray')

    if result.get('sl'):
        ax.axhline(y=result['sl'], color='red', linestyle='--', linewidth=1.2, alpha=0.8, label='SL')
    if result.get('tp'):
        ax.axhline(y=result['tp'], color='green', linestyle='--', linewidth=1.2, alpha=0.8, label='TP')

    ax.scatter(df_plot.index[-1], float(ind['price']), color='cyan', s=120, marker='v', zorder=5, label='Entree')
    ax.set_title(f"{symbol} – Score: {result['teddy_score']}/100 | {result['signal_text']}", color='white', fontsize=12)
    ax.legend(loc='upper left', fontsize=7)
    ax.set_ylabel('Prix', color='white')

    # Échelle serree : +/- 5% autour du prix actuel
    price = float(ind['price'])
    margin = price * 0.03
    ax.set_ylim(price - margin, price + margin)

    # ── Volume en bas ────────────────────────────────────────
    if 'Volume' in df_plot.columns:
        volume_plot = df_plot['Volume']
        colors_vol = ['green' if close_plot.iloc[i] >= close_plot.iloc[i-1] else 'red' for i in range(1, len(close_plot))]
        colors_vol.insert(0, 'gray')
        ax_macd.bar(df_plot.index, volume_plot, color=colors_vol, alpha=0.5, width=0.8)
        ax_macd.set_ylabel('Volume', color='white', fontsize=8)
    else:
        ax_macd.set_visible(False)

    plt.xticks(rotation=45, fontsize=7)
    fig.tight_layout()
    fig.text(0.5, 0.5, "Bitsure Teddy", fontsize=40, color='gray', ha='center', va='center', alpha=0.06, rotation=30)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close()
    sl_str = format_number(result['sl']) if result['sl'] else "N/A"
    tp_str = format_number(result['tp']) if result['tp'] else "N/A"
    rr_str = f"{result['rr_ratio']:.2f}" if result['rr_ratio'] else "N/A"
    signal_emoji = {"BUY": "🟢", "SELL": "🔴", "WAIT": "⚪"}.get(result["signal"], "⚪")
    caption = get_text(lang, "analyse_caption",
                       symbol=symbol, signal_emoji=signal_emoji, signal=result['signal_text'],
                       confidence=result['confidence'], price=format_number(ind['price']),
                       sl=sl_str, tp=tp_str, rr_ratio=rr_str, reason=result['reason'],
                       risk_advice=result['risk_advice'], rsi=ind['rsi'], rsi_state=rsi_state,
                       adx=ind.get('adx') if pd.notna(ind.get('adx')) else 0.0, adx_state=adx_state,
                       sma20=format_number(ind['sma20']), sma50=format_number(ind['sma50']),
                       teddy_score=result['teddy_score'])
    pending_signals = history_mgr.conn.execute("SELECT COUNT(*) FROM signals WHERE user_id = ? AND status = 'pending'", (update.effective_user.id,)).fetchone()[0]
    if pending_signals >= 50:
        await msg.edit_text('🚫 Max 50 signals pending.')
        return
    pending_signals = history_mgr.conn.execute("SELECT COUNT(*) FROM signals WHERE user_id = ? AND status = 'pending'", (update.effective_user.id,)).fetchone()[0]
    if pending_signals >= 50:
        await msg.edit_text('🚫 Max 50 signals pending.')
        return
    pending_signals = history_mgr.conn.execute("SELECT COUNT(*) FROM signals WHERE user_id = ? AND status = 'pending'", (update.effective_user.id,)).fetchone()[0]
    if pending_signals >= 50:
        await msg.edit_text('🚫 Max 50 signals pending.')
        return
    signal_id = history_mgr.add_signal(symbol, result['signal'], ind['price'], DEFAULT_TIMEFRAME, "analyse", result['teddy_score'], sl=result.get('sl'), tp=result.get('tp'), user_id=update.effective_user.id) if result['signal'] in ('BUY', 'SELL') else 'N/A'
    caption += f"\n\n🔐 ID: `{signal_id}`"
    await msg.delete()
    if from_callback and update.callback_query:
        await update.callback_query.message.reply_photo(photo=buf, caption=caption, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_photo(photo=buf, caption=caption, parse_mode=ParseMode.MARKDOWN)

# =========================================================
# PRIX
# =========================================================

@check_limit
async def price(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    if await handle_pending_alert_input(update, context):
        return
    lang = get_user_lang(update)
    symbol = context.args[0].upper() if context.args else None
    if not symbol:
        await respond(update, get_text(lang, "price_usage"), parse_mode=ParseMode.MARKDOWN)
        return
    if not is_valid_symbol(symbol):
        await respond(update, get_text(lang, "symbole_invalide"))
        return
    symbol = normalize_symbol(symbol)
    price_data = await fetcher.get_realtime_price(symbol, force_fresh=True)
    if price_data:
        text = get_text(lang, "price_format", symbol=symbol, price=format_number(price_data['price']), bid=format_number(price_data['bid']), ask=format_number(price_data['ask']))
        await respond(update, text, parse_mode=ParseMode.MARKDOWN)
    else:
        await respond(update, get_text(lang, "price_error", symbol=symbol))

# =========================================================
# ALERTES
# =========================================================

@check_limit
async def alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_pending_alert_input(update, context):
        return
    lang = get_user_lang(update)
    if len(context.args) < 3:
        await update.message.reply_text(get_text(lang, "alert_usage"))
        return
    symbol = normalize_symbol(context.args[0])
    cond = context.args[1].lower()
    try:
        price = float(context.args[2])
    except ValueError:
        await update.message.reply_text(get_text(lang, "alert_invalid_price"))
        return
    if cond not in ("above", "below"):
        await update.message.reply_text(get_text(lang, "alert_invalid_cond"))
        return
    cond_label = get_text(lang, "cond_above") if cond == "above" else get_text(lang, "cond_below")
    ok, result = alert_mgr.add_alert(update.effective_user.id, symbol, cond, price)
    if not ok:
        await update.message.reply_text(f"❌ Limite atteinte ({result} alertes max)")
        return
    await update.message.reply_text(get_text(lang, "alert_created", id=result, symbol=symbol, cond=cond_label, price=price))

@check_limit
async def alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update)
    alerts_list = alert_mgr.get_alerts(update.effective_user.id)
    if not alerts_list:
        await update.message.reply_text(get_text(lang, "alerts_empty"))
        return
    text = get_text(lang, "alerts_list_title")
    for a in alerts_list:
        status = "✅" if a.get("triggered") else "⏳"
        text += f"{status} #{a['id']} {a['symbol']} {a['condition']} {a['price']}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

@check_limit
async def delalert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update)
    if not context.args:
        await update.message.reply_text(get_text(lang, "delalert_usage"))
        return
    try:
        alert_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(get_text(lang, "alert_invalid_price"))
        return
    if alert_mgr.delete_alert(update.effective_user.id, alert_id):
        await update.message.reply_text(get_text(lang, "alert_deleted", id=alert_id))
    else:
        await update.message.reply_text(get_text(lang, "alert_not_found"))

# =========================================================
# WATCHLIST
# =========================================================

@check_limit
async def addwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update)
    symbol = context.args[0].upper() if context.args else None
    if not symbol:
        await respond(update, get_text(lang, "addwatch_usage"))
        return
    watchlist = user_mgr.get_watchlist(update.effective_user.id)
    if symbol in watchlist:
        await respond(update, get_text(lang, "watchlist_already", symbol=symbol))
        return
    success, limit = user_mgr.add_to_watchlist(update.effective_user.id, symbol)
    if not success:
        await respond(update, f"❌ Limite atteinte ({limit} symboles max)")
        return
    await respond(update, get_text(lang, "watchlist_added_styled", symbol=symbol))

@check_limit
async def removewatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update)
    symbol = context.args[0].upper() if context.args else None
    if not symbol:
        await respond(update, get_text(lang, "removewatch_usage"))
        return
    watchlist = user_mgr.get_watchlist(update.effective_user.id)
    if symbol not in watchlist:
        await respond(update, get_text(lang, "watchlist_missing", symbol=symbol))
        return
    user_mgr.remove_from_watchlist(update.effective_user.id, symbol)
    await respond(update, get_text(lang, "watchlist_removed_styled", symbol=symbol))

# =========================================================
# TENDANCE / VOLATILITÉ / NIVEAUX
# =========================================================

@check_limit
async def trend(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    if await handle_pending_alert_input(update, context):
        return
    lang = get_user_lang(update)
    symbol = context.args[0].upper() if context.args else None
    if not symbol:
        await respond(update, get_text(lang, "trend_usage"), parse_mode=ParseMode.MARKDOWN)
        return
    df = await fetcher.get_historical_data(symbol)
    if df is None or df.empty:
        await respond(update, get_text(lang, "trend_no_data"))
        return
    sma20 = df['Close'].rolling(20).mean().iloc[-1]
    sma50 = df['Close'].rolling(50).mean().iloc[-1]
    price = df['Close'].iloc[-1]
    if price > sma20 > sma50:
        tend = get_text(lang, "trend_haussiere")
    elif price < sma20 < sma50:
        tend = get_text(lang, "trend_baissiere")
    else:
        tend = get_text(lang, "trend_neutre")
    await respond(update, get_text(lang, "trend_result", symbol=symbol, tend=tend), parse_mode=ParseMode.MARKDOWN)

@check_limit
async def volatility(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    if await handle_pending_alert_input(update, context):
        return
    lang = get_user_lang(update)
    symbol = context.args[0].upper() if context.args else None
    if not symbol:
        await respond(update, get_text(lang, "volatility_usage"), parse_mode=ParseMode.MARKDOWN)
        return
    df = await fetcher.get_historical_data(symbol)
    if df is None or df.empty:
        await respond(update, get_text(lang, "trend_no_data"))
        return
    atr_val = atr(df['High'], df['Low'], df['Close'], 14).iloc[-1]
    await respond(update, get_text(lang, "volatility_result", symbol=symbol, atr=format_number(atr_val)), parse_mode=ParseMode.MARKDOWN)

@check_limit
async def levels(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    if await handle_pending_alert_input(update, context):
        return
    lang = get_user_lang(update)
    symbol = context.args[0].upper() if context.args else None
    if not symbol:
        await respond(update, get_text(lang, "levels_usage"), parse_mode=ParseMode.MARKDOWN)
        return
    df = await fetcher.get_historical_data(symbol)
    if df is None or df.empty:
        await respond(update, get_text(lang, "levels_no_data"))
        return
    from indicators import support_resistance, fibonacci_levels
    support, resistance = support_resistance(df['High'], df['Low'], 50)
    if support is None or resistance is None:
        await respond(update, get_text(lang, "levels_no_data"))
        return
    recent_high = df['High'].iloc[-50:].max()
    recent_low = df['Low'].iloc[-50:].min()
    fib = fibonacci_levels(recent_high, recent_low) if recent_high > recent_low else {"0.382": 0, "0.500": 0, "0.618": 0}
    await respond(update, get_text(lang, "levels_result", symbol=symbol, support=format_number(support), resistance=format_number(resistance), fib382=format_number(fib['0.382']), fib500=format_number(fib['0.500']), fib618=format_number(fib['0.618'])), parse_mode=ParseMode.MARKDOWN)

# =========================================================
# PARAMÈTRES
# =========================================================

@check_limit

async def send_settings_menu(lang: str, tf: str, style: str, uid: int,
                             send_fn, edit_fn=None):
    """
    Construit le récapitulatif + les boutons settings.
    - send_fn  : coroutine pour envoyer un nouveau message (ex: update.message.reply_text)
    - edit_fn  : coroutine pour éditer un message existant (ex: safe_edit) — optionnel
    Appelle edit_fn si fourni, sinon send_fn.
    """
    style_names = {
        "day":      "Day Trader",
        "swing":    "Swing Trader",
        "position": "Position Trader",
    }
    style_display = style_names.get(style, style)

    recap_lines = [
        f"*{get_text(lang, 'settings_title')}*",
        f"{get_text(lang, 'settings_timeframe')} : `{tf}`",
        f"{get_text(lang, 'settings_style')} : {style_display}",
        f"{get_text(lang, 'settings_lang')} : {lang.upper()}",
        "",
        get_text(lang, "settings_edit"),
    ]
    recap = "\n".join(recap_lines)

    keyboard = [
        [InlineKeyboardButton(get_text(lang, "btn_settimeframe"), callback_data="cmd_settimeframe")],
        [InlineKeyboardButton(get_text(lang, "btn_setlanguage"),  callback_data="cmd_setlanguage")],
        [InlineKeyboardButton("🎯 Trading Style",                  callback_data="cmd_setstyle")],
        [InlineKeyboardButton(get_text(lang, "btn_historique"),   callback_data="cmd_historique")],
        [InlineKeyboardButton(get_text(lang, "btn_support"),      callback_data="cmd_support")],
        [InlineKeyboardButton(get_text(lang, "back"),             callback_data="menu_back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if edit_fn is not None:
        await edit_fn(recap, keyboard)
    else:
        await send_fn(recap, reply_markup=reply_markup)

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    lang = user_mgr.get_setting(uid, "lang", "en")
    tf   = user_mgr.get_setting(uid, "timeframe", DEFAULT_TIMEFRAME)
    style = user_mgr.get_setting(uid, "trading_style", "day")

    await send_settings_menu(
        lang=lang,
        tf=tf,
        style=style,
        uid=uid,
        send_fn=update.message.reply_text,
    )
@check_limit
async def settimeframe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_pending_alert_input(update, context):
        return
    lang = get_user_lang(update)
    if not context.args:
        await respond(update, get_text(lang, "settimeframe_usage"))
        return
    tf = context.args[0]
    if tf not in ("1h", "4h", "1d"):
        await respond(update, get_text(lang, "settimeframe_invalid"))
        return
    user_mgr.set_setting(update.effective_user.id, "timeframe", tf)
    await respond(update, get_text(lang, "settimeframe_success", tf=tf))

@check_limit
async def setlanguage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_pending_alert_input(update, context):
        return
    lang = get_user_lang(update)
    if not context.args:
        await respond(update, get_text(lang, "setlanguage_usage"))
        return
    new_lang = context.args[0].lower()
    if new_lang not in ("en", "fr"):
        await respond(update, get_text(lang, "setlanguage_invalid"))
        return
    user_mgr.set_setting(update.effective_user.id, "lang", new_lang)
    await respond(update, get_text(new_lang, f"setlanguage_success_{new_lang}"))

@check_limit
async def usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update)
    rem = user_mgr.get_remaining_requests(update.effective_user.id)
    if rem == -1:
        await update.message.reply_text(get_text(lang, "usage_unlimited"))
    else:
        await update.message.reply_text(get_text(lang, "usage_requests_remaining", rem=rem))

# =========================================================
# HISTORIQUE
# =========================================================

@check_limit
async def historique(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_mgr.get_setting(update.effective_user.id, "lang", "en")
    target_message = update.message if update.message else (update.callback_query.message if update.callback_query else None)
    if target_message is None:
        return
    signals = history_mgr.get_recent_signals(10, user_id=update.effective_user.id)
    if not signals:
        await target_message.reply_text(get_text(lang, "history_empty"))
        return
    total = len(signals)
    completed = [s for s in signals if s.get("status") in ("win", "loss")]
    wins = sum(1 for s in completed if s.get("status") == "win")
    losses = sum(1 for s in completed if s.get("status") == "loss")
    win_rate = (wins / len(completed) * 100) if completed else 0
    total_pnl_value = 0.0
    for s in completed:
        try:
            total_pnl_value += float(s.get("result_pct") or 0)
        except (TypeError, ValueError):
            continue

    def fmt_ts(ts):
        if ts is None:
            return "--:--"
        try:
            return datetime.utcfromtimestamp(float(ts)).strftime("%H:%M UTC")
        except (TypeError, ValueError):
            return "--:--"

    def fmt_pnl(result_pct, result_price):
        parts = []
        if result_price is not None:
            parts.append(f"@ {format_number(result_price)}")
        if result_pct is not None:
            try:
                pct = float(result_pct)
                sign = "+" if pct >= 0 else ""
                parts.append(f"({sign}{pct:.2f}%)")
            except (TypeError, ValueError):
                pass
        return " ".join(parts) if parts else ""

    lines = []
    for s in signals:
        status = s.get("status")
        emoji = "✅" if status == "win" else "❌" if status == "loss" else "⏳"
        symbol = s.get("symbol", "?")
        direction = s.get("direction", "?")
        entry = s.get("entry_price", 0)
        sl_val = s.get("sl")
        tp_val = s.get("tp")
        open_ts = s.get("created_at")
        close_ts = s.get("closed_at")
        open_str = fmt_ts(open_ts)
        sl_str = format_number(sl_val) if sl_val is not None else "—"
        tp_str = format_number(tp_val) if tp_val is not None else "—"
        target_str = f"SL {sl_str} | TP {tp_str}"

        if status in ("win", "loss"):
            close_str = fmt_ts(close_ts)
            pnl_str = fmt_pnl(s.get("result_pct"), s.get("result_price"))
            close_part = f"→ Closed: {close_str} {pnl_str}".strip()
            lines.append(f"{emoji} {symbol} {direction}")
            lines.append(f"   Open: {open_str} @ {format_number(entry)} {close_part}")
            lines.append(f"   Target: {target_str}")
        else:
            lines.append(f"{emoji} {open_str} {symbol} {direction}")
            lines.append(f"   Open: {open_str} @ {format_number(entry)}")
            lines.append(f"   Target: {target_str}")
        lines.append("")

    open_count = total - len(completed)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    text = "\n".join([
        get_text(lang, "history_title", date=today_str),
        "━━━━━━━━━━━━━━━━━━━━━",
        *lines,
        "━━━━━━━━━━━━━━━━━━━━━",
        get_text(lang, "history_summary", total=total, wins=wins, win_rate=f"{win_rate:.0f}", losses=losses, open_count=open_count, total_pnl=f"{total_pnl_value:+.2f}%"),
    ])
    if len(text) > 4000:
        text = text[:3997] + "…"
    await target_message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
# =========================================================
# PAPER TRADING
# =========================================================

@check_limit
async def paper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_pending_alert_input(update, context):
        return
    lang = get_user_lang(update)
    user_id = update.effective_user.id
    if not context.args:
        await respond(update, get_text(lang, "paper_usage"))
        return
    action = context.args[0].lower()
    if action == "start":
        paper_trader.init_capital(user_id)
        await respond(update, get_text(lang, "paper_started", capital=10000))
    elif action == "status":
        stats = paper_trader.get_stats(user_id)
        positions = paper_trader.get_positions(user_id)
        msg = get_text(lang, "paper_status", capital=round(stats["capital"], 4), equity=round(stats["equity"], 4), open_positions=stats["open_positions"], total_pnl=round(stats["total_pnl"], 4))
        if positions:
            for p in positions:
                msg += f"\n{p['symbol']} @ {p['entry_price']:.4f} | SL: {p['sl']:.4f} | TP: {p['tp']:.4f} | PnL: {p['pnl_usdt']:.4f}$"
        else:
            msg += "\n" + get_text(lang, "paper_no_open_positions")
        await respond(update, msg, parse_mode=ParseMode.MARKDOWN)
    elif action == "buy":
        if len(context.args) < 2:
            await respond(update, get_text(lang, "paper_buy_usage"))
            return
        symbol = normalize_symbol(context.args[1].upper())
        df = await fetcher.get_historical_data(symbol)
        if df is None or df.empty:
            await respond(update, get_text(lang, "data_unavailable"))
            return
        trading_style = user_mgr.get_setting(update.effective_user.id, "trading_style", "day")
        result = SignalEngine.analyze(df, lang, symbol=symbol, style=trading_style)
        price = float(result["indicators"]["price"])
        atr_val = float(result["indicators"].get("atr", price * 0.01))
        sl = price - ATR_MULTIPLIER_SL * atr_val
        tp = price + RR_RATIO_TARGET * atr_val
        capital = paper_trader.get_capital(user_id)
        qty = capital / price if price > 0 else 1
        pos = paper_trader.open_position(user_id, symbol, price, sl, tp, qty)
        await respond(update, get_text(lang, "paper_opened", symbol=symbol, price=round(price, 4), sl=round(sl, 4), tp=round(tp, 4)))
    elif action == "sell":
        if len(context.args) < 2:
            await respond(update, get_text(lang, "paper_sell_usage"))
            return
        symbol = normalize_symbol(context.args[1].upper())
        positions = paper_trader.get_positions(user_id)
        closed = False
        for pos in list(positions):
            if pos["symbol"] == symbol:
                price_data = fetcher.get_cached_price(symbol)
                exit_price = float(price_data["price"]) if (price_data and "price" in price_data) else float(pos["current_price"])
                paper_trader.close_position(user_id, pos["id"], exit_price)
                closed = True
        if closed:
            await respond(update, get_text(lang, "paper_closed", symbol=symbol))
        else:
            await respond(update, get_text(lang, "paper_no_open_position", symbol=symbol))
    elif action == "history":
        closed = paper_trader.get_closed_positions(user_id)
        if not closed:
            await respond(update, get_text(lang, "paper_history_empty"))
            return
        msg = get_text(lang, "paper_history_title")
        for p in closed[-10:]:
            emoji = "🟢" if p.get("pnl_usdt", 0) > 0 else "🔴"
            msg += f"\n{emoji} {p['symbol']} @ {p['entry_price']:.4f} -> {p.get('exit_reason', '?')} ({p.get('pnl_usdt', 0):.4f}$)"
        await respond(update, msg, parse_mode=ParseMode.MARKDOWN)
    elif action == "stats":
        stats = paper_trader.get_stats(user_id)
        await respond(update, get_text(lang, "paper_stats", capital=stats["capital"], equity=stats["equity"], total_pnl=stats["total_pnl"], total_trades=stats["total_trades"], wins=stats["wins"], losses=stats["losses"], win_rate=stats["win_rate"]))
    else:
        await respond(update, get_text(lang, "paper_usage"))

# =========================================================
# SIGNAL MONITORING
# =========================================================

async def check_signal_outcomes(bot):
    signals = history_mgr.get_recent_signals(50)
    logger.info(f"check_signal_outcomes: {len(signals)} signaux trouvés")
    for s in signals:
        if s.get("status") not in (None, "pending"):
            continue
        symbol = s["symbol"]
        entry = float(s["entry_price"])
        sl = float(s.get("sl", 0) or 0)
        tp = float(s.get("tp", 0) or 0)
        if sl == 0 or tp == 0:
            logger.info(f"Signal {s['id']} {symbol} ignoré: SL={sl}, TP={tp}")
            continue
        logger.info(f"Vérification {s['id']} {symbol} {s['direction']} SL={sl} TP={tp}")
        price_data = await fetcher.get_realtime_price(symbol)
        if not price_data:
            continue
        current_price = float(price_data["price"])
        direction = s["direction"]
        
        if direction == "BUY":
            if current_price >= tp:
                pnl_pct = round((current_price - entry) / entry * 100, 4)
                history_mgr.update_signal_status(s["id"], "win", pnl_pct)
            elif current_price <= sl:
                pnl_pct = round((current_price - entry) / entry * 100, 4)
                history_mgr.update_signal_status(s["id"], "loss", pnl_pct)
                
        elif direction == "SELL":
            if current_price <= tp:
                pnl_pct = round((entry - current_price) / entry * 100, 4)
                history_mgr.update_signal_status(s["id"], "win", pnl_pct)
            elif current_price >= sl:
                pnl_pct = round((entry - current_price) / entry * 100, 4)
                history_mgr.update_signal_status(s["id"], "loss", pnl_pct)

def start_signal_monitoring(app):
    global signal_scheduler
    if signal_scheduler is not None:
        return
    signal_scheduler = AsyncIOScheduler(timezone="UTC")
    signal_scheduler.add_job(check_signal_outcomes, "interval", minutes=15, kwargs={"bot": app.bot}, id="signal_monitor", replace_existing=True)
    signal_scheduler.start()

signal_scheduler = None

# =========================================================
# UPGRADE & PAYMENTS
# =========================================================

@check_limit
async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update)
    keyboard = [
        [InlineKeyboardButton(get_text(lang, "button_pro_stars"), callback_data="plan_pro_stars")],
        [InlineKeyboardButton(get_text(lang, "button_binance_usdc"), callback_data="plan_binance")],
    ]
    await update.message.reply_text(get_text(lang, "upgrade_title"), parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

@check_limit
async def plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    lang = get_user_lang(update)
    if data == "plan_pro_stars":
        await send_invoice(query, "PRO 19,99€/mois", 1999, "pro_monthly")
    elif data == "plan_binance":
        await plan_binance_callback(update, context)
    else:
        await query.edit_message_text(get_text(lang, "unavailable_option"))

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def send_invoice(query, title: str, price_eur: int, payload: str):
    prices = [LabeledPrice(label=title, amount=price_eur)]
    await query.message.reply_invoice(title="Bitsure Teddy PRO", description=title, payload=payload, provider_token="", currency="XTR", prices=prices)

@check_limit
async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user
    payload = update.message.successful_payment.invoice_payload
    user_mgr.set_role(user_id, "pro")
    lang = user_mgr.get_setting(user_id, "lang", "en")
    await update.message.reply_text(get_text(lang, "payment_success", role="PRO"), parse_mode=ParseMode.MARKDOWN)
    await notify_admin_new_premium(context, user, "pro", "Telegram Stars")

@check_limit
async def plan_binance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update)
    user_id = update.effective_user.id
    ident, text = generate_binance_payment(user_id, lang)
    user_mgr.add_pending_binance(user_id, ident)
    await update.callback_query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

@check_limit
async def pay_binance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await plan_binance_callback(update, context)

# =========================================================
# WEEKLY REPORTS
# =========================================================

async def send_weekly_reports(bot):
    pro_users = user_mgr.get_premium_users()
    signals = history_mgr.get_recent_signals(50)
    completed = [s for s in signals if s.get("status") in ("win", "loss")]
    total = len(completed)
    wins = sum(1 for s in completed if s.get("status") == "win")
    win_rate = (wins / total * 100) if total else 0
    pcts = [float(s.get("result_pct") or 0) for s in completed]
    best = max(pcts) if pcts else 0
    worst = min(pcts) if pcts else 0
    msg = (
        "📊 RAPPORT HEBDOMADAIRE\n━━━━━━━━━━━━━━━━━━━\n"
        f"📈 Signaux reçus : {len(signals)}\n"
        f"✅ Gagnés : {wins} ({win_rate:.0f}%)\n"
        f"📉 Meilleur : {best:+.1f}%\n"
        f"💸 Pire : {worst:+.1f}%\n"
        "💡 Conseil : attends un score > 70"
    )
    for uid in pro_users:
        try:
            await bot.send_message(chat_id=uid, text=msg)
        except Exception as e:
            logger.warning(f"Weekly report failed for {uid}: {e}")

def start_weekly_report_scheduler(app):
    global weekly_scheduler
    if weekly_scheduler is not None:
        return
    weekly_scheduler = AsyncIOScheduler(timezone="UTC")
    weekly_scheduler.add_job(send_weekly_reports, "cron", day_of_week="sun", hour=18, minute=0, kwargs={"bot": app.bot}, id="weekly_report_job", replace_existing=True)
    weekly_scheduler.start()
