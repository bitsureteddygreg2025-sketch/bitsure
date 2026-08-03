import hashlib
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


import re

# ---------------------------------------------------------------------------
# SYMBOL NORMALIZATION — single source of truth for every Binance code path
# ---------------------------------------------------------------------------
#
# All user-facing symbols must pass through normalize_symbol() before hitting
# analysis, storage, signal confirmation, AutoTrade, Live Trading or any
# Binance API call.
#
# Rules applied in order:
#   1. Strip surrounding whitespace, convert to UPPERCASE
#   2. Remove separators: spaces, slashes, dashes, underscores
#   3. Map common USD-denominated base assets to their USDT Binance ticker
#      (BTC → BTCUSDT, ETH → ETHUSDT, etc.)
#   4. Reject symbols that are still not alphanumeric after the above steps
#
# Examples:
#   "BTC USD"  → "BTCUSDT"
#   "BTC/USD"  → "BTCUSDT"
#   "BTC-USD"  → "BTCUSDT"
#   "btcusd"   → "BTCUSDT"
#   "ETHUSDT"  → "ETHUSDT"   (already canonical, no-op)
#   "EUR/USD"  → "EURUSD"    (forex pair — passed through as-is for DataFetcher)
#   "XAU/USD"  → "XAUUSD"
# ---------------------------------------------------------------------------

# Well-known base assets that Binance lists as <BASE>USDT, not <BASE>USD.
# Extend this list when new perpetual-only assets are added.
_USD_TO_USDT_BASES = {
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT", "MATIC",
    "AVAX", "LINK", "UNI", "ATOM", "LTC", "ETC", "BCH", "NEAR", "APT",
    "OP", "ARB", "INJ", "SUI", "SEI", "TIA", "PYTH", "ORDI", "SATS",
    "SHIB", "PEPE", "FLOKI", "BONK", "WIF", "JUP", "W", "STRK",
    "MANTA", "ALT", "PIXEL", "PORTAL", "AEVO", "ETHFI", "ENA",
}

# Separator characters to strip before comparing tokens
_SEPARATOR_RE = re.compile(r"[\s/\-_]+")


def normalize_symbol(symbol: str) -> str:
    """Convert a user-supplied symbol string to a Binance-ready ticker.

    Raises ValueError with a clear message if the result is still invalid
    after all normalization steps, so the caller can immediately reject it
    without attempting any API call.
    """
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("Le symbole ne peut pas être vide.")

    # Step 1 — uppercase and strip
    s = symbol.strip().upper()

    # Step 2 — remove separators (spaces, /, -, _)
    s = _SEPARATOR_RE.sub("", s)

    # Step 3 — map *USD suffix to *USDT for known crypto bases
    if s.endswith("USD") and not s.endswith("USDT"):
        base = s[:-3]  # everything before "USD"
        if base in _USD_TO_USDT_BASES:
            s = base + "USDT"

    # Step 4 — final sanity check: only alphanumeric characters allowed
    if not re.match(r"^[A-Z0-9]{2,20}$", s):
        raise ValueError(
            f"Symbole invalide : « {symbol} ». "
            "Exemples valides : BTCUSDT, ETHUSDT, EURUSD, XAUUSD."
        )

    return s


def is_valid_symbol(symbol: str) -> bool:
    """Return True only if symbol passes normalize_symbol without error."""
    try:
        normalize_symbol(symbol)
        return True
    except ValueError:
        return False


def format_number(num: float, decimals: int = 2) -> str:
    """Formate un nombre avec séparateur de milliers."""
    if abs(num) < 0.01 and num != 0:
        return f"{num:.8f}".rstrip('0').rstrip('.')
    # Pour le Forex, on veut souvent 4 décimales
    if 0.01 <= abs(num) < 1000:
        decimals = max(decimals, 4)
    return f"{num:,.{decimals}f}"


def format_timestamp(ts: float) -> str:
    """Convertit timestamp en date lisible"""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def get_date_days_ago(days: int) -> datetime:
    """Retourne la date il y a N jours"""
    return datetime.now() - timedelta(days=days)


def escape_markdown(text: str) -> str:
    """Escapes characters that have special meaning in Telegram Markdown."""
    res = str(text)
    for char in ["_", "*", "`", "["]:
        res = res.replace(char, f"\\{char}")
    return res


def cache_key(*args) -> str:
    """Génère une clé de cache unique"""
    raw = "|".join(str(a) for a in args)
    return hashlib.md5(raw.encode()).hexdigest()
