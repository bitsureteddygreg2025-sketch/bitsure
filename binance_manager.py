"""
binance_manager.py
-------------------
Encapsule toute la communication avec l'API Binance (spot + futures).
Ne jamais logguer api_key / api_secret en clair (voir trading_logger.py).

Dépendance : pip install python-binance
"""

import logging
import math
from typing import Optional, Literal

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

from trading_config import get_binance_credentials, mark_credentials_invalid

logger = logging.getLogger("binance_manager")

MarketType = Literal["spot", "futures"]


class BinanceClientError(Exception):
    """Erreur applicative levée par ce module (message safe à afficher à l'utilisateur)."""


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
    """Récupère step size / min notional pour arrondir correctement les quantités."""
    if market_type == "futures":
        info = client.futures_exchange_info()
    else:
        info = client.get_exchange_info()

    for s in info["symbols"]:
        if s["symbol"] == symbol:
            filters = {f["filterType"]: f for f in s["filters"]}
            return filters
    raise BinanceClientError(f"Symbole {symbol} introuvable sur Binance.")


def round_step_size(quantity: float, step_size: str) -> float:
    precision = int(round(-math.log10(float(step_size))))
    return math.floor(quantity * (10 ** precision)) / (10 ** precision)


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
) -> dict:
    """
    Ouvre une position au marché, puis place SL/TP.
    Retourne un dict avec les IDs d'ordres (à stocker dans la table `trades`).
    Lève BinanceClientError en cas d'échec (message safe pour l'utilisateur).
    """
    client = _client_for_user(user_id)

    try:
        filters = get_symbol_filters(client, symbol, market_type)
        step_size = filters.get("LOT_SIZE", {}).get("stepSize") or filters.get(
            "MARKET_LOT_SIZE", {}
        ).get("stepSize", "0.001")
        quantity = round_step_size(quantity, step_size)
        if quantity <= 0:
            raise BinanceClientError("Quantité calculée trop faible (< step size Binance).")

        result = {"quantity": quantity}

        if market_type == "futures":
            if leverage and leverage > 1:
                set_leverage(user_id, symbol, leverage)

            order = client.futures_create_order(
                symbol=symbol, side=direction, type="MARKET", quantity=quantity
            )
            result["order_id"] = order["orderId"]
            result["client_order_id"] = order.get("clientOrderId")

            opposite = "SELL" if direction == "BUY" else "BUY"

            if sl_price:
                sl_order = client.futures_create_order(
                    symbol=symbol, side=opposite, type="STOP_MARKET",
                    stopPrice=round(sl_price, 6), closePosition=True,
                )
                result["sl_order_id"] = sl_order["orderId"]

            if tp_price:
                tp_order = client.futures_create_order(
                    symbol=symbol, side=opposite, type="TAKE_PROFIT_MARKET",
                    stopPrice=round(tp_price, 6), closePosition=True,
                )
                result["tp_order_id"] = tp_order["orderId"]

        else:  # spot
            order = client.create_order(
                symbol=symbol, side=direction, type="MARKET", quantity=quantity
            )
            result["order_id"] = order["orderId"]
            result["client_order_id"] = order.get("clientOrderId")

            # En spot, SL/TP sont simulés côté bot (voir position_manager.py),
            # car Binance spot ne supporte pas nativement OCO sur toutes les paires testnet.
            result["sl_order_id"] = None
            result["tp_order_id"] = None

        return result

    except (BinanceAPIException, BinanceOrderException) as e:
        if getattr(e, "code", None) in (-2015, -2014):
            mark_credentials_invalid(user_id, str(e))
        raise BinanceClientError(f"Erreur Binance à l'ouverture : {getattr(e, 'message', str(e))}")


def close_position(
    user_id: int,
    symbol: str,
    direction: str,
    quantity: float,
    market_type: MarketType = "futures",
) -> dict:
    """Ferme une position au marché (côté opposé à l'ouverture)."""
    client = _client_for_user(user_id)
    opposite = "SELL" if direction == "BUY" else "BUY"

    try:
        if market_type == "futures":
            order = client.futures_create_order(
                symbol=symbol, side=opposite, type="MARKET",
                quantity=quantity, reduceOnly=True,
            )
        else:
            order = client.create_order(
                symbol=symbol, side=opposite, type="MARKET", quantity=quantity
            )
        return {"order_id": order["orderId"]}
    except (BinanceAPIException, BinanceOrderException) as e:
        raise BinanceClientError(f"Erreur Binance à la fermeture : {getattr(e, 'message', str(e))}")


def cancel_order(user_id: int, symbol: str, order_id: str, market_type: MarketType = "futures") -> None:
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
