#!/usr/bin/env python3
"""
Bitsure Teddy - Main Entry Point
"""

import logging
import os

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from config import TELEGRAM_TOKEN
from data_fetcher import DataFetcher

# Handler /myid accessible à tous sans aucune restriction
async def myid_handler(update, context):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    await update.message.reply_text(
        f"🆔 Your ID: {user.id}\n"
        f"👤 Name: {username}\n\n"
        f"Send this ID to @btsr_teddy09 to get an invitation."
    )

from alert_manager import AlertManager
from database import get_db

# =========================================================
# INIT DATABASE
# =========================================================

get_db()

# =========================================================
# IMPORT HANDLERS - USER
# =========================================================

from bot_handlers import (
    start,
    help_command,
    analyse,
    price,
    alert,
    alerts,
    delalert,
    clearalerts,
    watchlist_command,
    addwatch,
    removewatch,
    scan,
    trend,
    volatility,
    levels,
    settings,
    settimeframe,
    setstyle,
    setlanguage,
    usage,
    upgrade,
    plan_callback,
    pre_checkout,
    successful_payment,
    pay_binance,
    support,
    historique,
    menu_command,
    menu_callback,
    symbol_callback,
    terms_callback,
    handle_pending_alert_input,
    paper,
    start_weekly_report_scheduler,
    start_signal_monitoring,
)

# =========================================================
# IMPORT HANDLERS - ADMIN
# =========================================================

from admin_handlers import (
    deleteuser,
    exportsignals,
    dbquery,
    cleanwaits,
    stats,
    teddy,
    broadcast,
    switchapi,
    find_memo,
    confirm_payment,
    refreshhistory,
    clearhistory,
    admin_cmd_trading_stats,
    admin_cmd_trades,
    admin_cmd_forceclose,
)

from trading_handlers import (
    cmd_setapikeys,
    cmd_autotrade,
    cmd_config,
    cmd_positions,
    cmd_close,
    cmd_pnl,
    cmd_account,
    cmd_trade_history,
    cmd_setleverage,
    cmd_setrisk,
    cmd_whitelist,
    cmd_blacklist,
    cmd_emergency_stop,
    trading_callback_router,
)
from execution_engine import scheduled_market_analysis, scheduled_signal_scan
from position_manager import monitor_open_positions

autotrade_scheduler = None

def start_autotrade_scheduler(app):
    global autotrade_scheduler
    if autotrade_scheduler is not None:
        return
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    autotrade_scheduler = AsyncIOScheduler(timezone="UTC")
    autotrade_scheduler.add_job(
        scheduled_signal_scan, "interval", seconds=20,
        kwargs={"context": app},
        id="scheduled_signal_scan", replace_existing=True
    )
    autotrade_scheduler.add_job(
        scheduled_market_analysis, "interval", minutes=5,
        kwargs={"context": app, "interval_minutes": 5},
        id="market_analysis_5m", replace_existing=True
    )
    autotrade_scheduler.add_job(
        scheduled_market_analysis, "interval", minutes=10,
        kwargs={"context": app, "interval_minutes": 10},
        id="market_analysis_10m", replace_existing=True
    )
    autotrade_scheduler.add_job(
        monitor_open_positions, "interval", seconds=15,
        kwargs={"context": app},
        id="monitor_open_positions", replace_existing=True
    )
    autotrade_scheduler.start()


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# =========================================================
# MAIN
# =========================================================

def main():

    if not TELEGRAM_TOKEN:
        raise ValueError("❌ TELEGRAM_TOKEN manquant.")

    logger.info("Initializing services...")

    alert_mgr = AlertManager.get_instance()

    async def post_init(application):
        from telegram import BotCommand
        commands = [
            BotCommand("menu", "Menu principal interactif"),
            BotCommand("help", "Liste de toutes les commandes"),
            BotCommand("analyse", "Analyse technique complète"),
            BotCommand("price", "Prix en temps réel"),
            BotCommand("trend", "Analyse de tendance"),
            BotCommand("volatility", "Volatilité (ATR)"),
            BotCommand("levels", "Supports, résistances & Fib"),
            BotCommand("alert", "Créer une alerte de prix"),
            BotCommand("alerts", "Afficher vos alertes"),
            BotCommand("delalert", "Supprimer une alerte"),
            BotCommand("clearalerts", "Effacer toutes les alertes"),
            BotCommand("watchlist", "Afficher votre liste de suivi"),
            BotCommand("addwatch", "Ajouter un symbole à la liste"),
            BotCommand("removewatch", "Retirer un symbole de la liste"),
            BotCommand("scan", "Scanner votre liste de suivi"),
            BotCommand("paper", "Module de paper trading"),
            BotCommand("autotrade", "Activer/désactiver l'AutoTrade"),
            BotCommand("account", "Tableau de bord Binance"),
            BotCommand("positions", "Positions ouvertes Binance"),
            BotCommand("close", "Fermer une position Binance"),
            BotCommand("pnl", "Statistiques PnL"),
            BotCommand("history_trades", "Historique trades Binance"),
            BotCommand("config", "Configuration AutoTrade"),
            BotCommand("setapikeys", "Configurer vos clés API Binance"),
            BotCommand("setleverage", "Définir le levier"),
            BotCommand("setrisk", "Définir le risque par trade"),
            BotCommand("whitelist", "Ajouter un symbole à la whitelist"),
            BotCommand("blacklist", "Exclure un symbole"),
            BotCommand("emergency_stop", "Fermer toutes les positions"),
            BotCommand("settings", "Afficher vos paramètres"),
            BotCommand("settimeframe", "Définir l'unité de temps"),
            BotCommand("setstyle", "Définir le style de trading"),
            BotCommand("setlanguage", "Changer la langue (fr/en)"),
            BotCommand("historique", "Historique récent des signaux"),
            BotCommand("usage", "Requêtes restantes"),
            BotCommand("upgrade", "Offre PRO"),
            BotCommand("support", "Support & contact"),
            BotCommand("myid", "Mon ID Telegram"),
        ]
        try:
            await application.bot.set_my_commands(commands)
            logger.info("Telegram menu commands updated.")
        except Exception as e:
            logger.warning(f"Failed to set Telegram commands: {e}")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.bot_data["data_fetcher"] = DataFetcher.get_instance()

    # =====================================================
    # BACKGROUND TASKS
    # =====================================================

    try:
        start_weekly_report_scheduler(app)
        logger.info("Weekly scheduler started.")
    except Exception as e:
        logger.warning(f"Scheduler start failed: {e}")

    try:
        start_signal_monitoring(app)
        logger.info("Signal monitoring started.")
    except Exception as e:
        logger.warning(f"Signal monitoring failed: {e}")

    try:
        alert_mgr.start_monitoring(app)
        logger.info("Alert monitoring started.")
    except Exception as e:
        logger.warning(f"Alert monitoring failed: {e}")

    try:
        start_autotrade_scheduler(app)
        logger.info("AutoTrade scheduler started.")
    except Exception as e:
        logger.warning(f"AutoTrade scheduler failed: {e}")

    # =====================================================
    # COMMANDS
    # =====================================================

    handlers = [

        # ================= USER =================

        ("start", start),
        ("help", help_command),
        ("menu", menu_command),

        ("analyse", analyse),
        ("price", price),
        ("trend", trend),
        ("volatility", volatility),
        ("levels", levels),

        ("alert", alert),
        ("alerts", alerts),
        ("delalert", delalert),
        ("clearalerts", clearalerts),

        ("watchlist", watchlist_command),
        ("addwatch", addwatch),
        ("removewatch", removewatch),
        ("scan", scan),

        ("paper", paper),

        ("settings", settings),
        ("settimeframe", settimeframe),
        ("setstyle", setstyle),
        ("setlanguage", setlanguage),

        ("usage", usage),
        ("upgrade", upgrade),
        ("support", support),
        ("pay_binance", pay_binance),
        ("historique", historique),

        # ================= AUTOTRADE =================

        ("setapikeys", cmd_setapikeys),
        ("autotrade", cmd_autotrade),
        ("config", cmd_config),
        ("positions", cmd_positions),
        ("close", cmd_close),
        ("pnl", cmd_pnl),
        ("account", cmd_account),
        ("history_trades", cmd_trade_history),
        ("setleverage", cmd_setleverage),
        ("setrisk", cmd_setrisk),
        ("whitelist", cmd_whitelist),
        ("blacklist", cmd_blacklist),
        ("emergency_stop", cmd_emergency_stop),

        # ================= ADMIN =================

        ("stats", stats),
        ("teddy", teddy),
        ("broadcast", broadcast),
        ("switchapi", switchapi),
        ("find_memo", find_memo),
        ("confirm_payment", confirm_payment),
        ("refreshhistory", refreshhistory),
        ("clearhistory", clearhistory),
        ("deleteuser", deleteuser),
        ("exportsignals", exportsignals),
        ("dbquery", dbquery),
        ("cleanwaits", cleanwaits),
        ("trading_stats", admin_cmd_trading_stats),
        ("trades", admin_cmd_trades),
        ("forceclose", admin_cmd_forceclose),
    ]

    # =====================================================
    # REGISTER COMMANDS
    # =====================================================

    seen = set()

    # Handler spécial sans restriction d'accès

    # Handler public accessible sans restriction
    app.add_handler(CommandHandler("myid", myid_handler))

    for cmd, func in handlers:

        if cmd in seen:
            logger.warning(f"Duplicate command skipped: /{cmd}")
            continue

        seen.add(cmd)

        app.add_handler(CommandHandler(cmd, func))

    # =====================================================
    # TEXT INPUTS
    # =====================================================

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_pending_alert_input
        )
    )

    # =====================================================
    # CALLBACKS
    # =====================================================

    app.add_handler(
        CallbackQueryHandler(
            menu_callback,
            pattern="^(menu_(?!autotrade|positions|trading_config)|cmd_|paperdir_|check_subscription|clearhistory_|clearalerts_)"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            symbol_callback,
            pattern="^(sympage_|symsel_|noop)"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            plan_callback,
            pattern="^plan_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            trading_callback_router,
            pattern="^(menu_autotrade|toggle_autotrade|menu_market_mode|set_market_|menu_analysis_config|set_analysis_|menu_positions|menu_trading_config|trading_open_|trading_reject_|trading_edit_)"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            terms_callback,
            pattern="^terms_"
        )
    )

    # =====================================================
    # PAYMENTS
    # =====================================================

    app.add_handler(
        MessageHandler(
            filters.SUCCESSFUL_PAYMENT,
            successful_payment
        )
    )

    # =====================================================
    # START BOT
    # =====================================================

    logger.info("Bitsure Teddy started successfully.")

    # =====================================================
    # START WEBSOCKET
    # =====================================================

    try:
        DataFetcher.get_instance().start_websocket()
        logger.info("Realtime websocket started.")
    except Exception as e:
        logger.warning(f"Websocket startup failed: {e}")

    # =====================================================
    # WEBHOOK / POLLING
    # =====================================================

    webhook_url = os.environ.get("WEBHOOK_URL")

    if webhook_url:

        logger.info(f"Starting webhook mode: {webhook_url}")

        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", "8443")),
            url_path=TELEGRAM_TOKEN,
            webhook_url=f"{webhook_url}/{TELEGRAM_TOKEN}",
        )

    else:

        logger.info("Starting polling mode.")

        app.run_polling(
            drop_pending_updates=True
        )
# =========================================================
# ENTRYPOINT
# =========================================================

if __name__ == "__main__":
    main()
