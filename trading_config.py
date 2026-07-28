"""
trading_config.py
------------------
Lecture / écriture de la configuration de trading par utilisateur,
et des identifiants API Binance associés.

Réutilise la connexion PostgreSQL existante du bot (via database.py).
On s'attend à une fonction `get_connection()` disponible dans database.py.
Adapte l'import ci-dessous si ta fonction s'appelle différemment.
"""

import os
import time
from dataclasses import dataclass, field, asdict
from typing import Optional, List

try:
    from database import get_connection  # ta connexion PostgreSQL existante
except ImportError:
    # Fallback si le projet expose une pool différente : adapte ce bloc.
    def get_connection():
        raise RuntimeError(
            "Impossible d'importer get_connection() depuis database.py. "
            "Adapte l'import en haut de trading_config.py."
        )


DEFAULTS = {
    "auto_trade": os.getenv("AUTO_TRADE_DEFAULT", "False") == "True",
    "periodic_analysis_enabled": os.getenv("PERIODIC_ANALYSIS_DEFAULT", "False") == "True",
    "leverage": int(os.getenv("DEFAULT_LEVERAGE", 1)),
    "risk_per_trade": float(os.getenv("DEFAULT_RISK_PER_TRADE", 1.0)),
    "max_positions": int(os.getenv("DEFAULT_MAX_POSITIONS", 3)),
    "min_score": int(os.getenv("DEFAULT_MIN_SCORE", 70)),
    "max_daily_loss": float(os.getenv("DEFAULT_MAX_DAILY_LOSS", 5.0)),
    "trailing_stop": os.getenv("DEFAULT_TRAILING_STOP", "False") == "True",
    "dca_enabled": os.getenv("DEFAULT_DCA_ENABLED", "False") == "True",
    "market_type": os.getenv("DEFAULT_MARKET_TYPE", "futures"),
    "trading_style": os.getenv("DEFAULT_TRADING_STYLE", "day"),
    "analysis_timeframe": os.getenv("DEFAULT_ANALYSIS_TIMEFRAME", "1h"),
    "analysis_interval_minutes": int(os.getenv("DEFAULT_ANALYSIS_INTERVAL_MINUTES", 5)),
    "testnet": os.getenv("BINANCE_TESTNET", "True") == "True",
}


def _coerce_symbol_list(value) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).upper() for item in value if str(item).strip()]
    if isinstance(value, str):
        raw = value.replace(";", ",").split(",")
        return [item.strip().upper() for item in raw if item.strip()]
    return []


@dataclass
class TradingConfig:
    user_id: int
    auto_trade: bool = DEFAULTS["auto_trade"]
    periodic_analysis_enabled: bool = DEFAULTS["periodic_analysis_enabled"]
    leverage: int = DEFAULTS["leverage"]
    risk_per_trade: float = DEFAULTS["risk_per_trade"]
    max_positions: int = DEFAULTS["max_positions"]
    min_score: int = DEFAULTS["min_score"]
    max_daily_loss: float = DEFAULTS["max_daily_loss"]
    trailing_stop: bool = DEFAULTS["trailing_stop"]
    trailing_stop_pct: float = 1.0
    dca_enabled: bool = DEFAULTS["dca_enabled"]
    dca_steps: int = 3
    dca_step_pct: float = 2.0
    symbol_whitelist: List[str] = field(default_factory=list)
    symbol_blacklist: List[str] = field(default_factory=list)
    market_type: str = DEFAULTS["market_type"]
    trading_style: str = DEFAULTS["trading_style"]
    analysis_timeframe: str = DEFAULTS["analysis_timeframe"]
    analysis_interval_minutes: int = DEFAULTS["analysis_interval_minutes"]
    testnet: bool = DEFAULTS["testnet"]
    cooldown_seconds: int = 0
    daily_loss_accum: float = 0.0
    safety_lock: bool = False
    safety_lock_reason: Optional[str] = None
    safety_lock_at: Optional[float] = None


def ensure_config_row(user_id: int) -> None:
    """Crée une ligne de config par défaut si elle n'existe pas encore."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trading_config (user_id, auto_trade, periodic_analysis_enabled, leverage, risk_per_trade,
                    max_positions, min_score, max_daily_loss, trailing_stop, dca_enabled,
                    market_type, trading_style, analysis_timeframe,
                    analysis_interval_minutes, testnet)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (
                    user_id, DEFAULTS["auto_trade"], DEFAULTS["periodic_analysis_enabled"], DEFAULTS["leverage"],
                    DEFAULTS["risk_per_trade"], DEFAULTS["max_positions"],
                    DEFAULTS["min_score"], DEFAULTS["max_daily_loss"],
                    DEFAULTS["trailing_stop"], DEFAULTS["dca_enabled"],
                    DEFAULTS["market_type"], DEFAULTS["trading_style"],
                    DEFAULTS["analysis_timeframe"],
                    DEFAULTS["analysis_interval_minutes"], DEFAULTS["testnet"],
                ),
            )
        conn.commit()
    finally:
        conn.close()


def get_config(user_id: int) -> TradingConfig:
    ensure_config_row(user_id)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, auto_trade, leverage, risk_per_trade, max_positions,
                       min_score, max_daily_loss, trailing_stop, trailing_stop_pct,
                       dca_enabled, dca_steps, dca_step_pct, symbol_whitelist,
                       symbol_blacklist, market_type, trading_style,
                       analysis_timeframe, analysis_interval_minutes, testnet,
                       cooldown_seconds, daily_loss_accum, periodic_analysis_enabled,
                       safety_lock, safety_lock_reason, safety_lock_at
                FROM trading_config WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return TradingConfig(user_id=user_id)

    return TradingConfig(
        user_id=row[0], auto_trade=row[1], leverage=row[2], risk_per_trade=row[3],
        max_positions=row[4], min_score=row[5], max_daily_loss=row[6],
        trailing_stop=row[7], trailing_stop_pct=row[8], dca_enabled=row[9],
        dca_steps=row[10], dca_step_pct=row[11],
        symbol_whitelist=_coerce_symbol_list(row[12]),
        symbol_blacklist=_coerce_symbol_list(row[13]),
        market_type=row[14] or DEFAULTS["market_type"],
        trading_style=row[15] or DEFAULTS["trading_style"],
        analysis_timeframe=row[16] or DEFAULTS["analysis_timeframe"],
        analysis_interval_minutes=row[17] or DEFAULTS["analysis_interval_minutes"],
        testnet=row[18], cooldown_seconds=row[19] or 0,
        daily_loss_accum=row[20] or 0.0,
        periodic_analysis_enabled=bool(row[21]) if len(row) > 21 and row[21] is not None else False,
        safety_lock=bool(row[22]) if len(row) > 22 and row[22] is not None else False,
        safety_lock_reason=row[23] if len(row) > 23 else None,
        safety_lock_at=row[24] if len(row) > 24 else None,
    )


def update_config(user_id: int, **fields) -> TradingConfig:
    """Met à jour un ou plusieurs champs de configuration."""
    ensure_config_row(user_id)
    if not fields:
        return get_config(user_id)

    allowed = set(asdict(TradingConfig(user_id=0)).keys()) - {"user_id"}
    set_clauses = []
    values = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key in {"symbol_whitelist", "symbol_blacklist"} and isinstance(value, list):
            value = ",".join(str(item).upper() for item in value if str(item).strip())
        set_clauses.append(f"{key} = %s")
        values.append(value)

    if not set_clauses:
        return get_config(user_id)

    set_clauses.append("updated_at = NOW()")
    values.append(user_id)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE trading_config SET {', '.join(set_clauses)} WHERE user_id = %s",
                values,
            )
        conn.commit()
    finally:
        conn.close()

    return get_config(user_id)


def save_binance_credentials(user_id: int, api_key: str, api_secret: str, testnet: bool = True) -> None:
    """Stocke les clés API. Ne jamais logguer api_key / api_secret en clair."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO binance_credentials (user_id, api_key, api_secret, testnet, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET api_key = EXCLUDED.api_key,
                    api_secret = EXCLUDED.api_secret,
                    testnet = EXCLUDED.testnet,
                    is_valid = TRUE,
                    updated_at = NOW()
                """,
                (user_id, api_key, api_secret, testnet),
            )
        conn.commit()
    finally:
        conn.close()


def get_binance_credentials(user_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT api_key, api_secret, testnet, is_valid FROM binance_credentials WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    return {"api_key": row[0], "api_secret": row[1], "testnet": row[2], "is_valid": row[3]}


def mark_credentials_invalid(user_id: int, reason: str = "") -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE binance_credentials SET is_valid = FALSE, updated_at = NOW() WHERE user_id = %s",
                (user_id,),
            )
        conn.commit()
    finally:
        conn.close()


def record_daily_loss(user_id: int, loss_usdt: float) -> float:
    """Ajoute une perte au cumul journalier, en le réinitialisant si un nouveau jour a commencé."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT daily_loss_accum, daily_loss_reset_at FROM trading_config WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            now = time.time()
            accum, reset_at = (row[0] or 0.0, row[1]) if row else (0.0, None)

            if reset_at is None or (now - reset_at) > 86400:
                accum = 0.0
                reset_at = now

            accum += max(loss_usdt, 0)

            cur.execute(
                "UPDATE trading_config SET daily_loss_accum = %s, daily_loss_reset_at = %s WHERE user_id = %s",
                (accum, reset_at, user_id),
            )
        conn.commit()
        return accum
    finally:
        conn.close()
