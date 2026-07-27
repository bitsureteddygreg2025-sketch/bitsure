"""
risk_manager.py
----------------
Toute la logique de gestion du risque :
- calcul de la taille de position
- vérification des limites (max positions, perte max journalière, cooldown)
- whitelist / blacklist de symboles
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from trading_config import TradingConfig, record_daily_loss
from binance_manager import get_account_balance, get_open_binance_positions, BinanceClientError
from database import get_connection
from utils import normalize_symbol

logger = logging.getLogger("risk_manager")


@dataclass
class RiskCheckResult:
    allowed: bool
    reason: Optional[str] = None


def count_local_open_positions(user_id: int) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM trades WHERE user_id = %s AND status = 'open'",
                (user_id,),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()



def count_open_positions(user_id: int) -> int:
    return count_local_open_positions(user_id)


def count_remote_open_positions(user_id: int, market_type: str = "futures") -> int:
    if market_type != "futures":
        return 0
    return len(get_open_binance_positions(user_id, market_type=market_type))


def get_last_trade_time(user_id: int) -> Optional[float]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT opened_at FROM trades WHERE user_id = %s ORDER BY opened_at DESC LIMIT 1",
                (user_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def check_symbol_allowed(config: TradingConfig, symbol: str) -> RiskCheckResult:
    normalized_symbol = normalize_symbol(symbol or "")
    if config.symbol_blacklist and normalized_symbol in config.symbol_blacklist:
        return RiskCheckResult(False, f"{normalized_symbol} est dans ta blacklist.")
    if config.symbol_whitelist and normalized_symbol not in config.symbol_whitelist:
        return RiskCheckResult(False, f"{normalized_symbol} n'est pas dans ta whitelist.")
    return RiskCheckResult(True)


def check_can_open_position(user_id: int, config: TradingConfig, symbol: str) -> RiskCheckResult:
    """Vérifie toutes les règles de risque avant d'ouvrir une nouvelle position."""

    symbol_check = check_symbol_allowed(config, symbol)
    if not symbol_check.allowed:
        return symbol_check

    local_open_count = count_local_open_positions(user_id)
    remote_open_count = 0
    if config.market_type == "futures":
        try:
            remote_open_count = count_remote_open_positions(user_id, config.market_type)
        except BinanceClientError as e:
            logger.warning("Risk check blocked user=%s: Binance positions unavailable: %s", user_id, e)
            return RiskCheckResult(False, "Positions Binance impossibles à vérifier, ouverture suspendue par sécurité.")
        if remote_open_count != local_open_count:
            logger.warning(
                "Risk divergence user=%s local_open=%s remote_open=%s",
                user_id, local_open_count, remote_open_count,
            )
            return RiskCheckResult(False, "Divergence positions locales/Binance, ouverture suspendue par sécurité.")

    open_count = max(local_open_count, remote_open_count)
    if open_count >= config.max_positions:
        return RiskCheckResult(
            False, f"Nombre max de positions atteint ({config.max_positions})."
        )

    if config.daily_loss_accum and config.max_daily_loss:
        try:
            balance = get_account_balance(user_id, market_type=config.market_type)
        except Exception:
            balance = None
        if balance:
            loss_pct = (config.daily_loss_accum / balance) * 100
            if loss_pct >= config.max_daily_loss:
                return RiskCheckResult(
                    False,
                    f"Perte quotidienne max atteinte ({config.max_daily_loss}%). "
                    f"Trading suspendu jusqu'à demain.",
                )

    if config.cooldown_seconds:
        last_trade = get_last_trade_time(user_id)
        if last_trade and (time.time() - last_trade) < config.cooldown_seconds:
            remaining = int(config.cooldown_seconds - (time.time() - last_trade))
            return RiskCheckResult(False, f"Cooldown actif, réessaie dans {remaining}s.")

    return RiskCheckResult(True)


def calculate_position_size(
    user_id: int,
    config: TradingConfig,
    entry_price: float,
    sl_price: float,
    market_type: str = "futures",
) -> float:
    """
    Taille de position basée sur le risque en % du capital et la distance au SL.
    quantity = (capital * risk_per_trade%) / |entry_price - sl_price|
    Pour futures, la quantité est ensuite multipliée virtuellement par le levier
    (le levier change la marge utilisée, pas la taille notionnelle calculée ici).
    """
    balance = get_account_balance(user_id, market_type=market_type)
    if balance <= 0:
        raise ValueError("Solde insuffisant ou introuvable sur le compte Binance.")

    risk_amount = balance * (config.risk_per_trade / 100)
    price_distance = abs(entry_price - sl_price)

    if price_distance <= 0:
        raise ValueError("SL invalide : distance nulle avec le prix d'entrée.")

    quantity = risk_amount / price_distance
    return quantity


def record_trade_loss(user_id: int, loss_usdt: float) -> float:
    """À appeler quand un trade se ferme en perte (SL touché)."""
    if loss_usdt <= 0:
        return 0.0
    return record_daily_loss(user_id, loss_usdt)
