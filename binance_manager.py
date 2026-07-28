"""
binance_manager.py
-------------------
Encapsule toute la communication avec l'API Binance (spot + futures).
Ne jamais logguer api_key / api_secret en clair (voir trading_logger.py).

Dépendance : pip install python-binance
"""

import logging
import hashlib
import math
from decimal import Decimal, ROUND_DOWN
from typing import Optional, Literal

import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

from trading_config import get_binance_credentials, mark_credentials_invalid, get_config
from trading_safety import SafetyError, assert_trading_allowed

logger = logging.getLogger("binance_manager")

MarketType = Literal["spot", "futures"]


class BinanceClientError(Exception):
    """Erreur applicative levée par ce module (message safe à afficher à l'utilisateur)."""


ORDER_CONTEXT_AUTOTRADE = "autotrade"
ORDER_CONTEXT_MANUAL_AUTHENTICATED = "manual_authenticated"
ORDER_CONTEXT_EMERGENCY = "emergency_stop"
_ALLOWED_ORDER_CONTEXTS = {
    ORDER_CONTEXT_AUTOTRADE,
    ORDER_CONTEXT_MANUAL_AUTHENTICATED,
    ORDER_CONTEXT_EMERGENCY,
}


def _assert_order_context_allowed(user_id: int, execution_context: Optional[str], *, require_auto_trade: bool) -> None:
    """Fail closed before any real Binance order can be sent.

    Telegram/webhooks/scanners must not rely on their route-level checks only: every
    backend order primitive must receive an explicit, already-authorized execution
    context. AutoTrade contexts do not require a fresh PIN per order, but they are
    accepted only while AutoTrade remains enabled and safety state is valid.
    """
    if execution_context not in _ALLOWED_ORDER_CONTEXTS:
        raise BinanceClientError("Ordre réel refusé: contexte d'exécution non autorisé.")

    config = get_config(user_id)
    try:
        assert_trading_allowed(
            config,
            require_auto_trade=(require_auto_trade or execution_context == ORDER_CONTEXT_AUTOTRADE),
        )
    except SafetyError as e:
        raise BinanceClientError(f"Ordre réel refusé: {e}")

    if execution_context == ORDER_CONTEXT_AUTOTRADE and not config.auto_trade:
        raise BinanceClientError("Ordre automatique refusé: AutoTrade est désactivé.")


def _client_for_user(user_id: int) -> Client:
    creds = get_binance_credentials(user_id)
    if not creds or not creds["api_key"] or not creds["api_secret"]:
        raise BinanceClientError(
            "Aucune clé API Binance configurée. Utilise /setapikeys pour les ajouter."
        )
    if not creds["is_valid"]:
        raise BinanceClientError(
            "Tes clés API Binance semblent invalides. Merci de les reconfigurer."
        )

    client = Client(creds["api_key"], creds["api_secret"], testnet=creds["testnet"])
    return client


def _public_client() -> Client:
    return Client()


def get_tradable_symbols(market_type: MarketType = "futures", quote_asset: str = "USDT") -> list[str]:
    """Return active Binance symbols for the requested market and quote asset."""
    client = _public_client()
    try:
        info = client.futures_exchange_info() if market_type == "futures" else client.get_exchange_info()
        symbols = []
        for item in info.get("symbols", []):
            if item.get("quoteAsset") != quote_asset:
                continue
            if item.get("status") != "TRADING":
                continue
            symbols.append(item["symbol"])
        return sorted(set(symbols))
    except BinanceAPIException as e:
        raise BinanceClientError(f"Erreur Binance (liste symboles) : {e.message}")


def get_klines_dataframe(
    symbol: str,
    timeframe: str,
    market_type: MarketType = "futures",
    limit: int = 500,
) -> Optional[pd.DataFrame]:
    """Fetch public Binance OHLCV data as a DataFrame compatible with SignalEngine."""
    client = _public_client()
    try:
        if market_type == "futures":
            klines = client.futures_klines(symbol=symbol, interval=timeframe, limit=limit)
        else:
            klines = client.get_klines(symbol=symbol, interval=timeframe, limit=limit)
    except BinanceAPIException as e:
        raise BinanceClientError(f"Erreur Binance (historique {symbol}) : {e.message}")

    if not klines:
        return None

    df = pd.DataFrame(
        klines,
        columns=[
            "OpenTime", "Open", "High", "Low", "Close", "Volume",
            "CloseTime", "QuoteAssetVolume", "NumberOfTrades",
            "TakerBuyBaseVolume", "TakerBuyQuoteVolume", "Ignore",
        ],
    )
    df["Date"] = pd.to_datetime(df["OpenTime"], unit="ms")
    df.set_index("Date", inplace=True)
    return df[["Open", "High", "Low", "Close", "Volume"]].astype(float)



def make_client_order_id(prefix: str, unique_key: str, max_len: int = 36) -> str:
    """Build a deterministic Binance-compatible client order id."""
    safe_prefix = "".join(ch for ch in prefix if ch.isalnum() or ch in "_-")[:8] or "ord"
    digest = hashlib.sha256(str(unique_key).encode("utf-8")).hexdigest()[:24]
    return f"{safe_prefix}_{digest}"[:max_len]


def get_price(user_id: int, symbol: str, market_type: MarketType = "futures") -> float:
    client = _client_for_user(user_id)
    try:
        if market_type == "futures":
            ticker = client.futures_symbol_ticker(symbol=symbol)
        else:
            ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker["price"])
    except BinanceAPIException as e:
        raise BinanceClientError(f"Erreur Binance (prix {symbol}) : {e.message}")


def get_account_balance(user_id: int, asset: str = "USDT", market_type: MarketType = "futures") -> float:
    client = _client_for_user(user_id)
    try:
        if market_type == "futures":
            balances = client.futures_account_balance()
            for b in balances:
                if b["asset"] == asset:
                    return float(b["balance"])
            return 0.0
        else:
            info = client.get_asset_balance(asset=asset)
            return float(info["free"]) if info else 0.0
    except BinanceAPIException as e:
        if e.code in (-2015, -2014):
            mark_credentials_invalid(user_id, str(e))
        raise BinanceClientError(f"Erreur Binance (solde) : {e.message}")


def get_symbol_filters(client: Client, symbol: str, market_type: MarketType) -> dict:
    """Récupère les filtres Binance (PRICE_FILTER, LOT_SIZE, etc.) du symbole."""
    if market_type == "futures":
        info = client.futures_exchange_info()
    else:
        info = client.get_exchange_info()

    for s in info["symbols"]:
        if s["symbol"] == symbol:
            filters = {f["filterType"]: f for f in s["filters"]}
            return filters
    raise BinanceClientError(f"Symbole {symbol} introuvable sur Binance.")


def _quantize_down(value: float, quantum: str) -> Decimal:
    q = Decimal(str(quantum))
    if q <= 0:
        return Decimal(str(value))
    return (Decimal(str(value)) / q).to_integral_value(rounding=ROUND_DOWN) * q


def format_step_value(value: float, quantum: str) -> str:
    rounded = _quantize_down(value, quantum)
    return format(rounded.normalize(), "f")


def round_step_size(quantity: float, step_size: str) -> float:
    return float(_quantize_down(quantity, step_size))


def format_price_for_symbol(price: float, filters: dict) -> str:
    tick_size = filters.get("PRICE_FILTER", {}).get("tickSize", "0.00000001")
    return format_step_value(price, tick_size)


def set_leverage(user_id: int, symbol: str, leverage: int) -> None:
    client = _client_for_user(user_id)
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
    except BinanceAPIException as e:
        raise BinanceClientError(f"Impossible de définir le levier x{leverage} : {e.message}")


def open_position(
    user_id: int,
    symbol: str,
    direction: str,          # "BUY" ou "SELL"
    quantity: float,
    sl_price: Optional[float],
    tp_price: Optional[float],
    market_type: MarketType = "futures",
    leverage: int = 1,
    client_order_id: Optional[str] = None,
    execution_context: Optional[str] = None,
) -> dict:
    """
    Ouvre une position au marché, puis place SL/TP.
    Retourne un dict avec les IDs d'ordres (à stocker dans la table `trades`).
    Lève BinanceClientError en cas d'échec (message safe pour l'utilisateur).
    """
    _assert_order_context_allowed(user_id, execution_context, require_auto_trade=True)
    client = _client_for_user(user_id)
    symbol = symbol.upper()
    direction = direction.upper()

    # Regles Spot vs Futures
    if market_type == "spot":
        leverage = 1
        if direction == "SELL":
            raise BinanceClientError("Vente à découvert (SHORT) non supportée en mode Spot standard.")

    opened_order = None

    try:
        if market_type == "futures":
            remote_positions = get_open_binance_positions(user_id, market_type=market_type)
            same = [p for p in remote_positions if p["symbol"] == symbol and p["direction"] == direction]
            opposite_positions = [p for p in remote_positions if p["symbol"] == symbol and p["direction"] != direction]
            if same or opposite_positions:
                raise BinanceClientError(
                    f"Ouverture refusée: position Binance existante sur {symbol} "
                    f"({remote_positions})."
                )

        filters = get_symbol_filters(client, symbol, market_type)
        step_size = filters.get("LOT_SIZE", {}).get("stepSize") or filters.get(
            "MARKET_LOT_SIZE", {}
        ).get("stepSize", "0.001")
        quantity = round_step_size(quantity, step_size)
        if quantity <= 0:
            raise BinanceClientError("Quantité calculée trop faible (< step size Binance).")

        result = {"quantity": quantity}

        if market_type == "futures":
            if leverage:
                set_leverage(user_id, symbol, int(leverage))

            order_params = {
                "symbol": symbol, "side": direction, "type": "MARKET", "quantity": quantity,
            }
            if client_order_id:
                order_params["newClientOrderId"] = client_order_id
            order = client.futures_create_order(**order_params)
            opened_order = order
            result["order_id"] = order["orderId"]
            result["client_order_id"] = order.get("clientOrderId")

            opposite = "SELL" if direction == "BUY" else "BUY"

            if sl_price:
                sl_order = client.futures_create_order(
                    symbol=symbol, side=opposite, type="STOP_MARKET",
                    stopPrice=format_price_for_symbol(sl_price, filters), closePosition=True,
                )
                result["sl_order_id"] = sl_order["orderId"]

            if tp_price:
                tp_order = client.futures_create_order(
                    symbol=symbol, side=opposite, type="TAKE_PROFIT_MARKET",
                    stopPrice=format_price_for_symbol(tp_price, filters), closePosition=True,
                )
                result["tp_order_id"] = tp_order["orderId"]

        else:  # spot
            order_params = {"symbol": symbol, "side": direction, "type": "MARKET", "quantity": quantity}
            if client_order_id:
                order_params["newClientOrderId"] = client_order_id
            order = client.create_order(**order_params)
            result["order_id"] = order["orderId"]
            result["client_order_id"] = order.get("clientOrderId")
            result["sl_order_id"] = None
            result["tp_order_id"] = None

        return result

    except (BinanceAPIException, BinanceOrderException) as e:
        if getattr(e, "code", None) in (-2015, -2014):
            mark_credentials_invalid(user_id, str(e))
        if market_type == "futures" and opened_order:
            opposite = "SELL" if direction == "BUY" else "BUY"
            try:
                client.futures_create_order(
                    symbol=symbol, side=opposite, type="MARKET",
                    quantity=quantity, reduceOnly=True,
                )
            except Exception as close_error:
                logger.critical(
                    "Position %s potentiellement ouverte sans protection pour user=%s après échec SL/TP: %s",
                    symbol, user_id, close_error,
                )
                raise BinanceClientError(
                    "Ordre principal ouvert mais protection SL/TP échouée; "
                    "fermeture automatique impossible. Vérifie Binance immédiatement."
                )
            raise BinanceClientError(
                "Ordre principal ouvert puis refermé car la protection SL/TP a échoué."
            )
        raise BinanceClientError(f"Erreur Binance à l'ouverture : {getattr(e, 'message', str(e))}")



def get_available_balance(user_id: int, market_type: MarketType = "futures", asset: str = "USDT") -> float:
    client = _client_for_user(user_id)
    try:
        if market_type == "futures":
            acc = client.futures_account()
            return float(acc.get("availableBalance", 0.0))
        info = client.get_asset_balance(asset=asset)
        return float(info["free"]) if info else 0.0
    except BinanceAPIException as e:
        raise BinanceClientError(f"Erreur Binance (marge disponible) : {e.message}")


def get_open_binance_positions(user_id: int, market_type: MarketType = "futures") -> list[dict]:
    """Return real open positions from Binance for reconciliation/risk checks."""
    if market_type != "futures":
        return []
    client = _client_for_user(user_id)
    try:
        positions = []
        for pos in client.futures_position_information():
            amt = float(pos.get("positionAmt", 0.0))
            if amt == 0:
                continue
            positions.append({
                "symbol": pos["symbol"],
                "direction": "BUY" if amt > 0 else "SELL",
                "quantity": abs(amt),
                "entry_price": float(pos.get("entryPrice", 0.0)),
                "mark_price": float(pos.get("markPrice", 0.0)),
            })
        return positions
    except BinanceAPIException as e:
        raise BinanceClientError(f"Erreur Binance (positions ouvertes) : {e.message}")


def get_open_binance_orders(user_id: int, market_type: MarketType = "futures", symbol: Optional[str] = None) -> list[dict]:
    """Return open Binance orders for reconciliation."""
    client = _client_for_user(user_id)
    try:
        if market_type == "futures":
            return client.futures_get_open_orders(symbol=symbol) if symbol else client.futures_get_open_orders()
        return client.get_open_orders(symbol=symbol) if symbol else client.get_open_orders()
    except BinanceAPIException as e:
        raise BinanceClientError(f"Erreur Binance (ordres ouverts) : {e.message}")


def close_position(
    user_id: int,
    symbol: str,
    direction: str,
    quantity: float,
    market_type: MarketType = "futures",
    execution_context: Optional[str] = None,
) -> dict:
    """Ferme une position au marché (côté opposé à l'ouverture)."""
    _assert_order_context_allowed(user_id, execution_context, require_auto_trade=(execution_context == ORDER_CONTEXT_AUTOTRADE))
    client = _client_for_user(user_id)
    symbol = symbol.upper()
    direction = direction.upper()
    opposite = "SELL" if direction == "BUY" else "BUY"

    try:
        if market_type == "futures":
            remote_positions = get_open_binance_positions(user_id, market_type=market_type)
            matching = [
                p for p in remote_positions
                if p["symbol"] == symbol
                and p["direction"] == direction
                and abs(float(p["quantity"]) - float(quantity)) <= max(float(quantity) * 0.001, 1e-12)
            ]
            if not matching:
                raise BinanceClientError(
                    f"Fermeture refusée: aucune position Binance {symbol} {direction} "
                    f"avec quantité attendue {quantity}."
                )
        filters = get_symbol_filters(client, symbol, market_type)
        step_size = filters.get("LOT_SIZE", {}).get("stepSize") or filters.get("MARKET_LOT_SIZE", {}).get("stepSize", "0.001")
        qty = format_step_value(quantity, step_size)
        if market_type == "futures":
            order = client.futures_create_order(
                symbol=symbol, side=opposite, type="MARKET",
                quantity=qty, reduceOnly=True,
            )
        else:
            order = client.create_order(
                symbol=symbol, side=opposite, type="MARKET", quantity=qty
            )
        return {"order_id": order["orderId"]}
    except (BinanceAPIException, BinanceOrderException) as e:
        raise BinanceClientError(f"Erreur Binance à la fermeture : {getattr(e, 'message', str(e))}")


def cancel_order(user_id: int, symbol: str, order_id: str, market_type: MarketType = "futures", execution_context: Optional[str] = None) -> None:
    _assert_order_context_allowed(user_id, execution_context, require_auto_trade=(execution_context == ORDER_CONTEXT_AUTOTRADE))
    client = _client_for_user(user_id)
    try:
        if market_type == "futures":
            client.futures_cancel_order(symbol=symbol, orderId=order_id)
        else:
            client.cancel_order(symbol=symbol, orderId=order_id)
    except BinanceAPIException as e:
        # Non bloquant : l'ordre est peut-être déjà exécuté/annulé.
        logger.warning("Annulation ordre %s (%s) impossible : %s", order_id, symbol, e.message)


def test_connection(user_id: int) -> bool:
    """Utilisé par /setapikeys pour valider les clés dès leur saisie."""
    client = _client_for_user(user_id)
    try:
        client.get_account()
        return True
    except BinanceAPIException as e:
        mark_credentials_invalid(user_id, str(e))
        raise BinanceClientError(f"Connexion Binance échouée : {e.message}")


def get_full_account_info(user_id: int, market_type: MarketType = "futures") -> dict:
    """
    Récupère toutes les informations du compte Binance :
    - Solde total (USDT + actifs)
    - Détail des actifs
    - Positions ouvertes + PnL non réalisé
    - Taux d'utilisation de la marge (Futures)
    - Historique des ordres récents et commissions
    """
    client = _client_for_user(user_id)
    summary = {
        "market_type": market_type,
        "total_wallet_balance": 0.0,
        "available_balance": 0.0,
        "unrealized_pnl": 0.0,
        "margin_used_pct": 0.0,
        "assets": [],
        "positions": [],
        "recent_trades": [],
        "total_commissions": 0.0,
    }

    try:
        if market_type == "futures":
            acc = client.futures_account()
            summary["total_wallet_balance"] = float(acc.get("totalWalletBalance", 0.0))
            summary["available_balance"] = float(acc.get("availableBalance", 0.0))
            summary["unrealized_pnl"] = float(acc.get("totalUnrealizedProfit", 0.0))

            total_maint_margin = float(acc.get("totalMaintMargin", 0.0))
            total_margin_balance = float(acc.get("totalMarginBalance", 1.0))
            if total_margin_balance > 0:
                summary["margin_used_pct"] = round((total_maint_margin / total_margin_balance) * 100, 2)

            for b in acc.get("assets", []):
                bal = float(b.get("walletBalance", 0.0))
                if bal > 0:
                    summary["assets"].append({
                        "asset": b["asset"],
                        "wallet": bal,
                        "available": float(b.get("availableBalance", 0.0)),
                        "unrealized_pnl": float(b.get("unrealizedProfit", 0.0)),
                    })

            raw_positions = client.futures_position_information()
            for pos in raw_positions:
                amt = float(pos.get("positionAmt", 0.0))
                if amt != 0:
                    entry = float(pos.get("entryPrice", 0.0))
                    mark = float(pos.get("markPrice", 0.0))
                    upnl = float(pos.get("unRealizedProfit", 0.0))
                    side = "BUY (LONG)" if amt > 0 else "SELL (SHORT)"
                    summary["positions"].append({
                        "symbol": pos["symbol"],
                        "side": side,
                        "quantity": abs(amt),
                        "entry_price": entry,
                        "mark_price": mark,
                        "unrealized_pnl": upnl,
                        "leverage": int(pos.get("leverage", 1)),
                        "liquidation_price": float(pos.get("liquidationPrice", 0.0)),
                    })

            # Historique des trades & commissions récents
            try:
                user_trades = client.futures_account_trades(limit=10)
                for t in user_trades:
                    comm = float(t.get("commission", 0.0))
                    summary["total_commissions"] += comm
                    summary["recent_trades"].append({
                        "symbol": t["symbol"],
                        "side": t["side"],
                        "price": float(t["price"]),
                        "qty": float(t["qty"]),
                        "commission": comm,
                        "commission_asset": t["commissionAsset"],
                        "time": t["time"],
                    })
            except Exception:
                pass

        else:  # Spot
            acc = client.get_account()
            balances = acc.get("balances", [])
            total_usdt = 0.0

            for b in balances:
                free = float(b.get("free", 0.0))
                locked = float(b.get("locked", 0.0))
                total = free + locked
                if total > 0:
                    asset = b["asset"]
                    usdt_val = total
                    if asset != "USDT":
                        try:
                            price = float(client.get_symbol_ticker(symbol=f"{asset}USDT")["price"])
                            usdt_val = total * price
                        except Exception:
                            usdt_val = 0.0
                    total_usdt += usdt_val
                    summary["assets"].append({
                        "asset": asset,
                        "free": free,
                        "locked": locked,
                        "total": total,
                        "usdt_value": round(usdt_val, 2),
                    })

            summary["total_wallet_balance"] = round(total_usdt, 2)
            try:
                summary["available_balance"] = float(client.get_asset_balance(asset="USDT")["free"]) if client.get_asset_balance(asset="USDT") else 0.0
            except Exception:
                summary["available_balance"] = summary["total_wallet_balance"]

    except BinanceAPIException as e:
        if getattr(e, "code", None) in (-2015, -2014):
            mark_credentials_invalid(user_id, str(e))
        raise BinanceClientError(f"Erreur API Binance Account: {e.message}")

    return summary
