"""
market_hours.py — Bitsure Teddy
Bloque les signaux hors des heures de trading liquides.
"""

from datetime import datetime, timezone


def is_market_open(symbol: str) -> bool:
    """
    Retourne True si le marché est ouvert et liquide pour le symbole donné.
    Les cryptos (BTC, ETH) sont toujours ouvertes.
    """
    now = datetime.now(timezone.utc)
    day = now.weekday()  # 0 = Lundi, 6 = Dimanche
    hour = now.hour

    symbol = symbol.upper()

    # Crypto : toujours ouvert
    if symbol in ("BTCUSD", "ETHUSD"):
        return True

    # Actions US : Lundi-Vendredi, 14h30-21h UTC
    if symbol in ("AAPL", "TSLA", "NVDA"):
        return day < 5 and 14 <= hour < 21

    # USDJPY : Lundi-Vendredi, ouvert presque 24h (sauf nuit US)
    if symbol == "USDJPY":
        return day < 5

    # Forex et Or : Lundi-Vendredi, 7h-21h UTC
    # Fermé du vendredi 21h au dimanche 21h UTC
    if day >= 5:
        return False
    if day == 4 and hour >= 21:
        return False
    if day == 6 and hour < 21:
        return False
    return 7 <= hour < 21
