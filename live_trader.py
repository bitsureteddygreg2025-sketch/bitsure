"""
live_trader.py
----------------
Module indépendant pour le Live Trading manuel depuis Telegram.
Les ordres réels ne sont envoyés qu'après validation et confirmation explicite.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

from binance.exceptions import BinanceAPIException, BinanceOrderException

from binance_manager import (
    BinanceClientError,
    _client_for_user,
    get_account_balance,
    get_full_account_info,
    get_price,
    get_symbol_filters,
    round_step_size,
    set_leverage,
)
from database import get_connection
from trading_config import get_config
from risk_manager import check_can_open_position
from trading_logger import get_trading_logger
from utils import normalize_symbol

logger = get_trading_logger("live_trader")


@dataclass
class LiveOrderDraft:
    symbol: str
    side: str
    amount: float
    amount_mode: str = "fixed"
    leverage: int = 1
    sl_price: Optional[float] = None
    tp_price: Optional[float] = None
    trailing_stop: bool = False
    order_type: str = "MARKET"
    entry_price: Optional[float] = None
    margin_type: str = "ISOLATED"
    reduce_only: bool = False
    market_type: str = "futures"


def _filter_float(filters: dict, filter_type: str, key: str, default: float = 0.0) -> float:
    try:
        return float(filters.get(filter_type, {}).get(key, default))
    except (TypeError, ValueError):
        return default




def _get_max_leverage(client, symbol: str) -> Optional[int]:
    try:
        brackets = client.futures_leverage_bracket(symbol=symbol)
        if brackets and brackets[0].get("brackets"):
            return int(brackets[0]["brackets"][0].get("initialLeverage", 125))
    except Exception as e:
        logger.debug("Leverage bracket unavailable for %s: %s", symbol, e)
    return None

def _round_tick(value: Optional[float], tick_size: float) -> Optional[float]:
    if value is None or tick_size <= 0:
        return value
    precision = max(0, int(round(-math.log10(tick_size))))
    return round(math.floor(float(value) / tick_size) * tick_size, precision)


def build_draft(
    user_id: int,
    symbol: str,
    side: str,
    amount: float,
    leverage: Optional[int] = None,
    sl_price: Optional[float] = None,
    tp_price: Optional[float] = None,
    amount_mode: str = "fixed",
    order_type: str = "MARKET",
    entry_price: Optional[float] = None,
    margin_type: str = "ISOLATED",
    reduce_only: bool = False,
    trailing_stop: bool = False,
) -> LiveOrderDraft:
    config = get_config(user_id)
    side = side.upper()
    if side not in ("BUY", "SELL"):
        raise ValueError("Le sens doit être BUY ou SELL.")
    amount_mode = amount_mode.lower()
    if amount_mode not in ("fixed", "percentage"):
        raise ValueError("Le mode montant doit être fixed ou percentage.")
    order_type = order_type.upper()
    if order_type not in ("MARKET", "LIMIT"):
        raise ValueError("Le type d'ordre doit être MARKET ou LIMIT.")
    margin_type = margin_type.upper()
    if margin_type not in ("CROSS", "ISOLATED"):
        raise ValueError("Le mode marge doit être CROSS ou ISOLATED.")
    if order_type == "LIMIT" and not entry_price:
        raise ValueError("Un prix d'entrée est requis pour un ordre LIMIT.")

    return LiveOrderDraft(
        symbol=normalize_symbol(symbol.upper()),
        side=side,
        amount=float(amount),
        amount_mode=amount_mode,
        leverage=int(leverage if leverage is not None else config.leverage),
        sl_price=sl_price,
        tp_price=tp_price,
        trailing_stop=trailing_stop,
        order_type=order_type,
        entry_price=entry_price,
        margin_type=margin_type,
        reduce_only=reduce_only,
        market_type=config.market_type,
    )


def validate_draft(user_id: int, draft: LiveOrderDraft) -> dict:
    if draft.market_type != "futures" and draft.side == "SELL" and not draft.reduce_only:
        raise BinanceClientError("SHORT non supporté en Spot standard. Utilise Futures.")
    if draft.leverage < 1 or draft.leverage > 125:
        raise BinanceClientError("Le levier doit être entre 1 et 125.")
    if draft.amount <= 0:
        raise BinanceClientError("Le montant doit être supérieur à 0.")

    config = get_config(user_id)
    risk_check = check_can_open_position(user_id, config, draft.symbol)
    if not risk_check.allowed:
        raise BinanceClientError(risk_check.reason or "Règle de risque non respectée.")

    client = _client_for_user(user_id)
    max_leverage = _get_max_leverage(client, draft.symbol) if draft.market_type == "futures" else 1
    if max_leverage and draft.leverage > max_leverage:
        raise BinanceClientError(f"Levier x{draft.leverage} supérieur au maximum Binance autorisé pour {draft.symbol} (x{max_leverage}).")
    filters = get_symbol_filters(client, draft.symbol, draft.market_type)
    balance = get_account_balance(user_id, market_type=draft.market_type)
    if balance <= 0:
        raise BinanceClientError("Solde disponible insuffisant.")

    margin_amount = balance * draft.amount / 100 if draft.amount_mode == "percentage" else draft.amount
    if margin_amount <= 0 or margin_amount > balance:
        raise BinanceClientError("Montant supérieur au solde disponible.")

    price = float(draft.entry_price or get_price(user_id, draft.symbol, draft.market_type))
    notional = margin_amount * draft.leverage
    raw_qty = notional / price if price else 0.0
    step_size = filters.get("LOT_SIZE", {}).get("stepSize") or filters.get("MARKET_LOT_SIZE", {}).get("stepSize", "0.001")
    quantity = round_step_size(raw_qty, step_size)
    min_qty = _filter_float(filters, "LOT_SIZE", "minQty", 0.0)
    min_notional = _filter_float(filters, "MIN_NOTIONAL", "notional", 0.0) or _filter_float(filters, "NOTIONAL", "minNotional", 0.0)
    tick_size = _filter_float(filters, "PRICE_FILTER", "tickSize", 0.0)

    if quantity <= 0 or (min_qty and quantity < min_qty):
        raise BinanceClientError("Taille de position inférieure au minimum Binance.")
    if min_notional and quantity * price < min_notional:
        raise BinanceClientError("Notional inférieur au minimum Binance.")

    entry_price = _round_tick(draft.entry_price, tick_size)
    sl_price = _round_tick(draft.sl_price, tick_size)
    tp_price = _round_tick(draft.tp_price, tick_size)

    return {
        "balance": balance,
        "margin_amount": margin_amount,
        "price": price,
        "quantity": quantity,
        "notional": quantity * price,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
    }


def execute_draft(user_id: int, draft: LiveOrderDraft) -> dict:
    checks = validate_draft(user_id, draft)
    client = _client_for_user(user_id)
    result = {"checks": checks}
    opposite = "SELL" if draft.side == "BUY" else "BUY"

    try:
        if draft.market_type == "futures":
            try:
                client.futures_change_margin_type(symbol=draft.symbol, marginType=draft.margin_type)
            except BinanceAPIException as e:
                if getattr(e, "code", None) != -4046:  # No need to change margin type.
                    raise
            set_leverage(user_id, draft.symbol, draft.leverage)
            params = {
                "symbol": draft.symbol,
                "side": draft.side,
                "type": draft.order_type,
                "quantity": checks["quantity"],
            }
            if draft.order_type == "LIMIT":
                params.update({"price": checks["entry_price"], "timeInForce": "GTC"})
            if draft.reduce_only:
                params["reduceOnly"] = True
            order = client.futures_create_order(**params)
            result["order"] = order
            if checks["sl_price"] and not draft.reduce_only:
                result["sl_order"] = client.futures_create_order(
                    symbol=draft.symbol, side=opposite, type="STOP_MARKET",
                    stopPrice=checks["sl_price"], closePosition=True,
                )
            if checks["tp_price"] and not draft.reduce_only:
                result["tp_order"] = client.futures_create_order(
                    symbol=draft.symbol, side=opposite, type="TAKE_PROFIT_MARKET",
                    stopPrice=checks["tp_price"], closePosition=True,
                )
        else:
            if draft.order_type == "LIMIT":
                order = client.create_order(
                    symbol=draft.symbol, side=draft.side, type="LIMIT",
                    quantity=checks["quantity"], price=checks["entry_price"], timeInForce="GTC",
                )
            else:
                order = client.create_order(
                    symbol=draft.symbol, side=draft.side, type="MARKET", quantity=checks["quantity"]
                )
            result["order"] = order
    except (BinanceAPIException, BinanceOrderException) as e:
        logger.warning("Live order failed user=%s symbol=%s: %s", user_id, draft.symbol, getattr(e, "message", str(e)))
        raise BinanceClientError(f"Erreur Binance Live Trading : {getattr(e, 'message', str(e))}")

    _save_live_trade(user_id, draft, result)
    return result


def _save_live_trade(user_id: int, draft: LiveOrderDraft, result: dict) -> None:
    order = result.get("order", {})
    checks = result["checks"]
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trades (signal_id, user_id, symbol, direction, entry_price, sl_price, tp_price,
                    quantity, leverage, market_type, status, opened_at, binance_order_id,
                    binance_client_order_id, sl_order_id, tp_order_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open', %s, %s, %s, %s, %s)
                """,
                (
                    "live_manual", user_id, draft.symbol, draft.side, checks["price"], checks["sl_price"],
                    checks["tp_price"], checks["quantity"], draft.leverage, draft.market_type, time.time(),
                    str(order.get("orderId")) if order.get("orderId") else None,
                    order.get("clientOrderId"),
                    str(result.get("sl_order", {}).get("orderId")) if result.get("sl_order") else None,
                    str(result.get("tp_order", {}).get("orderId")) if result.get("tp_order") else None,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def get_open_orders(user_id: int, symbol: Optional[str] = None) -> list[dict]:
    config = get_config(user_id)
    client = _client_for_user(user_id)
    try:
        if config.market_type == "futures":
            return client.futures_get_open_orders(symbol=symbol) if symbol else client.futures_get_open_orders()
        return client.get_open_orders(symbol=symbol) if symbol else client.get_open_orders()
    except BinanceAPIException as e:
        raise BinanceClientError(f"Erreur Binance ordres ouverts : {e.message}")


def cancel_live_order(user_id: int, symbol: str, order_id: str) -> None:
    config = get_config(user_id)
    client = _client_for_user(user_id)
    try:
        if config.market_type == "futures":
            client.futures_cancel_order(symbol=normalize_symbol(symbol.upper()), orderId=order_id)
        else:
            client.cancel_order(symbol=normalize_symbol(symbol.upper()), orderId=order_id)
    except BinanceAPIException as e:
        raise BinanceClientError(f"Erreur Binance annulation ordre : {e.message}")


def get_live_account(user_id: int) -> dict:
    config = get_config(user_id)
    return get_full_account_info(user_id, market_type=config.market_type)
