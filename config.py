import os

# =========================================================
# IDENTIFIANTS
# =========================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN manquant dans l'environnement")

ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
if ADMIN_ID == 0:
    raise ValueError("❌ ADMIN_ID manquant ou invalide dans l'environnement")

# =========================================================
# CLÉS API
# =========================================================

TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY")

# =========================================================
# ACCÈS & UTILISATEURS
# =========================================================

ACCESS_MODE = "approved_only"
ALLOW_AUTO_REGISTER = True
TRIAL_DAYS = 30

USER_ROLES = ["tester", "pro", "admin"]
PREMIUM_ROLES = ["pro", "admin"]

# =========================================================
# LIMITES UTILISATEURS
# =========================================================

FREE_DAILY_REQUESTS = 5
MAX_WATCHLIST_SYMBOLS_FREE = 5
MAX_WATCHLIST_SYMBOLS_TESTER = 25
MAX_WATCHLIST_SYMBOLS_PRO = 100
MAX_ALERTS_FREE = 3
MAX_ALERTS_TESTER = 20
MAX_ALERTS_PRO = 100

# =========================================================
# CACHE
# =========================================================

PRICE_CACHE_TTL = 900
HISTORY_CACHE_TTL = 300

# =========================================================
# ANALYSE TECHNIQUE
# =========================================================

DEFAULT_TIMEFRAME = "1h"
HISTORY_PERIOD = "6mo"
ATR_PERIOD = 14
ATR_MULTIPLIER_SL = 1.5
RR_RATIO_TARGET = 2.0

# =========================================================
# CONFIGURATION DES SYMBOLS
# =========================================================

SYMBOL_CONFIGS = {
    "BTCUSD": {"adx_min": 23, "rsi_buy_low": 48, "rsi_buy_high": 68, "rsi_sell_low": 32, "rsi_sell_high": 52, "atr_max_pct": 5.5, "min_cond": 4},
    "ETHUSD": {"adx_min": 22, "rsi_buy_low": 47, "rsi_buy_high": 70, "rsi_sell_low": 30, "rsi_sell_high": 56, "atr_max_pct": 6.0, "min_cond": 4},
    # Configs directes USDT — calibration affinée (RSI resserré, ADX relevé)
    "BTCUSDT": {"adx_min": 25, "rsi_buy_low": 50, "rsi_buy_high": 65, "rsi_sell_low": 35, "rsi_sell_high": 50, "atr_max_pct": 4.5, "min_cond": 4},
    "ETHUSDT": {"adx_min": 24, "rsi_buy_low": 50, "rsi_buy_high": 67, "rsi_sell_low": 33, "rsi_sell_high": 50, "atr_max_pct": 5.0, "min_cond": 4},
    "EURUSD": {"adx_min": 21, "rsi_buy_low": 43, "rsi_buy_high": 63, "rsi_sell_low": 37, "rsi_sell_high": 57, "atr_max_pct": 0.90, "min_cond": 4},
    "GBPUSD": {"adx_min": 22, "rsi_buy_low": 42, "rsi_buy_high": 64, "rsi_sell_low": 36, "rsi_sell_high": 58, "atr_max_pct": 1.1, "min_cond": 4},
    "USDJPY": {"adx_min": 21, "rsi_buy_low": 45, "rsi_buy_high": 67, "rsi_sell_low": 33, "rsi_sell_high": 58, "atr_max_pct": 1.3, "min_cond": 4},
    "AUDUSD": {"adx_min": 20, "rsi_buy_low": 42, "rsi_buy_high": 62, "rsi_sell_low": 38, "rsi_sell_high": 54, "atr_max_pct": 0.85, "min_cond": 4},
    "XAUUSD": {"adx_min": 24, "rsi_buy_low": 48, "rsi_buy_high": 74, "rsi_sell_low": 26, "rsi_sell_high": 52, "atr_max_pct": 3.0, "min_cond": 4},
    "AAPL": {"adx_min": 20, "rsi_buy_low": 42, "rsi_buy_high": 62, "rsi_sell_low": 38, "rsi_sell_high": 58, "atr_max_pct": 3.0, "min_cond": 4},
    "TSLA": {"adx_min": 26, "rsi_buy_low": 42, "rsi_buy_high": 64, "rsi_sell_low": 36, "rsi_sell_high": 55, "atr_max_pct": 5.5, "min_cond": 4},
    "NVDA": {"adx_min": 24, "rsi_buy_low": 45, "rsi_buy_high": 70, "rsi_sell_low": 30, "rsi_sell_high": 58, "atr_max_pct": 5.8, "min_cond": 4},
}

# =========================================================
# DOSSIERS & FICHIERS
# =========================================================

DATA_DIR = "data"

# =========================================================
# WEBSOCKETS
# =========================================================

TWELVEDATA_WS_URL = "wss://ws.twelvedata.com/v1/quotes/price"

# =========================================================
# PAPER TRADING
# =========================================================

# Capital virtuel initial (en USDT)
PAPER_DEFAULT_CAPITAL  = 10_000_000_000.0

# Frais de trading simulés (en %) appliqués à l'entrée ET à la sortie
# Exemple : 0.10 = 0.10% par trade (maker/taker crypto standard)
PAPER_FEES_PCT         = 0.10

# Slippage simulé (en %) — écart entre le prix théorique et le prix d'exécution réel
# Exemple : 0.05 = 0.05% (très conservateur pour du crypto liquide)
PAPER_SLIPPAGE_PCT     = 0.05

# Levier par défaut (1.0 = sans levier)
PAPER_DEFAULT_LEVERAGE = 1.0

# Levier maximum autorisé
PAPER_MAX_LEVERAGE     = 10.0

# =========================================================
# AUTRES
# =========================================================

BINANCE_ID = os.environ.get("BINANCE_ID", "")
