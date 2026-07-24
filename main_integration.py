"""
main_integration.py
----------------------
CE FICHIER N'EST PAS UN MODULE AUTONOME.
Il montre exactement les extraits à copier/coller dans tes fichiers existants
(main.py, bot_handlers.py, admin_handlers.py) pour brancher le module AutoTrade
sans casser l'existant.

Copie les blocs pertinents aux bons endroits, ne remplace pas tes fichiers en entier.
"""

# =============================================================================
# 1) DANS main.py
# =============================================================================

MAIN_PY_IMPORTS = """
from trading_handlers import (
    cmd_setapikeys, cmd_autotrade, cmd_config, cmd_positions, cmd_close,
    cmd_pnl, cmd_trade_history, cmd_setleverage, cmd_setrisk,
    cmd_whitelist, cmd_blacklist, cmd_emergency_stop,
    trading_callback_router,
)
from execution_engine import scheduled_signal_scan
from position_manager import monitor_open_positions
from admin_handlers import (
    admin_cmd_trading_stats, admin_cmd_trades, admin_cmd_forceclose,  # ajoutés dans admin_handlers.py
)
"""

MAIN_PY_REGISTER_HANDLERS = """
def register_trading_handlers(app):
    app.add_handler(CommandHandler("setapikeys", cmd_setapikeys))
    app.add_handler(CommandHandler("autotrade", cmd_autotrade))
    app.add_handler(CommandHandler("config", cmd_config))
    app.add_handler(CommandHandler("positions", cmd_positions))
    app.add_handler(CommandHandler("close", cmd_close))
    app.add_handler(CommandHandler("pnl", cmd_pnl))
    app.add_handler(CommandHandler("history_trades", cmd_trade_history))
    app.add_handler(CommandHandler("setleverage", cmd_setleverage))
    app.add_handler(CommandHandler("setrisk", cmd_setrisk))
    app.add_handler(CommandHandler("whitelist", cmd_whitelist))
    app.add_handler(CommandHandler("blacklist", cmd_blacklist))
    app.add_handler(CommandHandler("emergency_stop", cmd_emergency_stop))

    # Callback router pour tous les boutons du module trading
    app.add_handler(CallbackQueryHandler(
        trading_callback_router,
        pattern="^(menu_autotrade|toggle_autotrade|menu_positions|menu_trading_config|trading_open_|trading_reject_|trading_edit_)"
    ))

    # Admin (vérif ADMIN_ID faite à l'intérieur de admin_handlers.py)
    app.add_handler(CommandHandler("trading_stats", admin_cmd_trading_stats))
    app.add_handler(CommandHandler("trades", admin_cmd_trades))
    app.add_handler(CommandHandler("forceclose", admin_cmd_forceclose))


# Dans ta fonction main() / setup de l'Application, après app = Application.builder()...build() :
#     register_trading_handlers(app)
#
# Puis, avec ton JobQueue existant (APScheduler intégré à python-telegram-bot v20+) :
#     app.job_queue.run_repeating(scheduled_signal_scan, interval=20, first=10)
#     app.job_queue.run_repeating(monitor_open_positions, interval=15, first=15)
"""

# =============================================================================
# 2) DANS bot_handlers.py
# =============================================================================

BOT_HANDLERS_MENU_BUTTONS = """
# Dans ta fonction build_main_menu(), ajoute :
from trading_handlers import build_autotrade_menu_buttons

def build_main_menu():
    keyboard = [
        # ... tes boutons existants ...
    ]
    keyboard.extend(build_autotrade_menu_buttons())
    return InlineKeyboardMarkup(keyboard)

# Le routeur de callback_router existant n'a RIEN à changer : le pattern du
# CallbackQueryHandler du module trading (voir main.py ci-dessus) intercepte
# uniquement les callback_data qui lui appartiennent, donc pas de conflit
# avec ton routeur existant tant que tes callback_data ne commencent pas
# par les mêmes préfixes (menu_autotrade, trading_open_, etc.).
"""

# =============================================================================
# 3) DANS admin_handlers.py
# =============================================================================

ADMIN_HANDLERS_SNIPPET = """
import os
from telegram import Update
from telegram.ext import ContextTypes
from trading_handlers import (
    admin_cmd_trading_stats as _base_trading_stats,
    admin_cmd_trades as _base_trades,
    admin_cmd_forceclose as _base_forceclose,
)

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))


def _check_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID


async def admin_cmd_trading_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_admin(update):
        return
    await _base_trading_stats(update, context)


async def admin_cmd_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_admin(update):
        return
    await _base_trades(update, context)


async def admin_cmd_forceclose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _check_admin(update):
        return
    await _base_forceclose(update, context)
"""

# =============================================================================
# 4) DANS config.py (si tu centralises la config du bot)
# =============================================================================

CONFIG_PY_SNIPPET = """
import os

BINANCE_TESTNET_DEFAULT = os.getenv("BINANCE_TESTNET", "True") == "True"
AUTO_TRADE_DEFAULT = os.getenv("AUTO_TRADE_DEFAULT", "False") == "True"
DEFAULT_LEVERAGE = int(os.getenv("DEFAULT_LEVERAGE", 1))
DEFAULT_RISK_PER_TRADE = float(os.getenv("DEFAULT_RISK_PER_TRADE", 1.0))
DEFAULT_MAX_POSITIONS = int(os.getenv("DEFAULT_MAX_POSITIONS", 3))
DEFAULT_MIN_SCORE = int(os.getenv("DEFAULT_MIN_SCORE", 70))
DEFAULT_MAX_DAILY_LOSS = float(os.getenv("DEFAULT_MAX_DAILY_LOSS", 5.0))
DEFAULT_MARKET_TYPE = os.getenv("DEFAULT_MARKET_TYPE", "futures")
"""

# =============================================================================
# 5) MIGRATION SQL
# =============================================================================

MIGRATION_NOTE = """
Exécute sql/create_tables.sql une seule fois sur ta base PostgreSQL Railway,
par exemple :
    psql "$DATABASE_URL" -f sql/create_tables.sql

Le script est idempotent (CREATE TABLE IF NOT EXISTS), il ne touche pas
à tes tables existantes (users, signals, settings, conversions).
"""
