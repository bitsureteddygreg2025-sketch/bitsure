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
    trend,
    volatility,
    levels,
    settings,
    settimeframe,
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
)

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

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
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

        ("paper", paper),

        ("settings", settings),
        ("settimeframe", settimeframe),
        ("setlanguage", setlanguage),

        ("usage", usage),
        ("upgrade", upgrade),
        ("support", support),
        ("pay_binance", pay_binance),
        ("historique", historique),

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
            pattern="^(menu_|cmd_|paperdir_|check_subscription|clearhistory_)"
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
