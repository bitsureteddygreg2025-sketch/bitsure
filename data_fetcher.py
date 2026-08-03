import json
import time
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
import requests
import websocket
import threading
import pandas as pd

from config import (
    TWELVEDATA_API_KEY,
    PRICE_CACHE_TTL, HISTORY_CACHE_TTL,
    DEFAULT_TIMEFRAME, HISTORY_PERIOD,
    TWELVEDATA_WS_URL
)
from utils import cache_key, normalize_symbol

logger = logging.getLogger(__name__)


class DataFetcher:
    _instance = None

    def __init__(self):
        self.price_cache = {}
        self.history_cache = {}
        self.subscribed_symbols = set([
            "BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "USDJPY",
            "AUDUSD", "XAUUSD", "AAPL", "TSLA", "NVDA"
        ])
        self.ws = None
        self.ws_thread = None
        self.active_source = "binance"

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # =========================================================
    # WEBSOCKET
    # =========================================================

    def start_websocket(self):
        self._start_twelve_ws()

    def _start_twelve_ws(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        self.ws = None
        self.ws_thread = None

        if not TWELVEDATA_API_KEY:
            logger.error("❌ Twelve Data: pas de clé API")
            return

        def on_open(ws):
            formatted = [self._format_symbol(s) for s in sorted(self.subscribed_symbols)]
            ws.send(json.dumps({"action": "subscribe", "params": {"symbols": ",".join(formatted)}}))
            self.active_source = "twelve"
            logger.info("✅ Twelve Data WebSocket actif")

        def on_error(ws, err):
            logger.error(f"Twelve WS error: {err}")

        def on_close(ws, *args):
            logger.warning("⚠️ Twelve Data WebSocket fermé")

        self.ws = websocket.WebSocketApp(
            f"{TWELVEDATA_WS_URL}?apikey={TWELVEDATA_API_KEY}",
            on_open=on_open,
            on_message=lambda ws, msg: self._on_twelve_message(msg),
            on_error=on_error,
            on_close=on_close
        )
        self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.ws_thread.start()

    def _on_twelve_message(self, message):
        """Parse le prix et met à jour le cache. Les alertes sont gérées par AlertManager."""
        try:
            data = json.loads(message)
            if data.get("event") != "price":
                return
            symbol = normalize_symbol(data.get("symbol", ""))
            price = float(data.get("price", 0))
            raw_bid = data.get("bid")
            raw_ask = data.get("ask")
            if raw_bid is not None and raw_ask is not None:
                bid = float(raw_bid)
                ask = float(raw_ask)
            else:
                spread = max(price * 0.0005, 0.0001)
                bid = price - spread / 2
                ask = price + spread / 2

            old_price = self.price_cache.get(symbol, {}).get("price", price)

            self.price_cache[symbol] = {
                "price": price,
                "bid": bid,
                "ask": ask,
                "prev_price": old_price,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.debug(f"Twelve WS parse error: {e}")

    # =========================================================
    # PRIX TEMPS RÉEL
    # =========================================================

    def get_cached_price(self, symbol: str) -> Optional[Dict]:
        symbol = normalize_symbol(symbol)
        if symbol in self.price_cache:
            if time.time() - self.price_cache[symbol]["timestamp"] < PRICE_CACHE_TTL:
                return self.price_cache[symbol]
        return None

    async def get_realtime_price(self, symbol: str, force_fresh: bool = False) -> Optional[Dict]:
        symbol = normalize_symbol(symbol)
        if not force_fresh:
            cached = self.get_cached_price(symbol)
            if cached:
                return cached
        price = await self._fetch_price(symbol)
        if price:
            self.price_cache[symbol] = price
        return price

    async def _fetch_price(self, symbol: str) -> Optional[Dict]:
        # 1. Essayer Binance pour les paires USDT (BTCUSDT, ETHUSDT, etc.)
        if symbol.endswith("USDT") or symbol in ["BTCUSDT", "ETHUSDT"]:
            try:
                url = f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={symbol}"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    bid = float(data.get("bidPrice", 0))
                    ask = float(data.get("askPrice", 0))
                    price = (bid + ask) / 2.0 if (bid and ask) else float(data.get("bidPrice") or 0)
                    return {"price": price, "bid": bid, "ask": ask, "timestamp": time.time()}
            except Exception as e:
                logger.warning(f"Binance Price error {symbol}: {e}")

        # 2. Repli / Source Twelve Data pour les autres symboles
        if not TWELVEDATA_API_KEY:
            return None
        try:
            td_symbol = self._format_symbol(symbol)
            url = f"https://api.twelvedata.com/quote?symbol={td_symbol}&apikey={TWELVEDATA_API_KEY}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                price = float(data.get("close") or data.get("price", 0))
                bid = float(data.get("bid", price - max(price * 0.0005, 0.0001)))
                ask = float(data.get("ask", price + max(price * 0.0005, 0.0001)))
                return {"price": price, "bid": bid, "ask": ask, "timestamp": time.time()}
        except Exception as e:
            logger.warning(f"Price error {symbol}: {e}")
        return None

    # =========================================================
    # DONNÉES HISTORIQUES
    # =========================================================

    async def get_historical_data(self, symbol: str, timeframe: str = DEFAULT_TIMEFRAME, period: str = HISTORY_PERIOD) -> Optional[pd.DataFrame]:
        symbol = normalize_symbol(symbol)
        key = cache_key(symbol, timeframe, period)
        if key in self.history_cache and time.time() - self.history_cache[key]["timestamp"] < HISTORY_CACHE_TTL:
            return self.history_cache[key]["data"]
        df = await self._fetch_history(symbol, timeframe)
        if df is not None and not df.empty:
            self.history_cache[key] = {"data": df, "timestamp": time.time()}
            return df
        return None

    async def _fetch_history(self, symbol: str, timeframe: str):
        # 1. Binance pour les paires USDT (BTCUSDT, ETHUSDT...)
        if symbol.endswith("USDT") or symbol in ["BTCUSDT", "ETHUSDT"]:
            try:
                binance_tf = {
                    "1m": "1m", "5m": "5m", "15m": "15m",
                    "1h": "1h", "4h": "4h", "1d": "1d"
                }.get(timeframe, "1d")
                url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={binance_tf}&limit=1000"
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    raw_data = r.json()
                    if raw_data:
                        records = []
                        for k in raw_data:
                            records.append({
                                "Date": pd.to_datetime(k[0], unit='ms'),
                                "Open": float(k[1]),
                                "High": float(k[2]),
                                "Low": float(k[3]),
                                "Close": float(k[4]),
                                "Volume": float(k[5])
                            })
                        df = pd.DataFrame(records)
                        df.set_index("Date", inplace=True)
                        return df
            except Exception as e:
                logger.warning(f"Binance History error {symbol}: {e}")

        # 2. Twelve Data
        try:
            td_symbol = self._format_symbol(symbol)
            interval = {
                "1m": "1min",
                "5m": "5min",
                "15m": "15min",
                "1h": "1h",
                "4h": "4h",
                "1d": "1day",
            }.get(timeframe, "1day")
            url = f"https://api.twelvedata.com/time_series?symbol={td_symbol}&interval={interval}&outputsize=5000&apikey={TWELVEDATA_API_KEY}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json().get("values", [])
                if not data:
                    return None
                df = pd.DataFrame(data).rename(columns={
                    "datetime": "Date", "open": "Open", "high": "High",
                    "low": "Low", "close": "Close", "volume": "Volume"
                })
                df = df.iloc[::-1]
                df["Date"] = pd.to_datetime(df["Date"])
                df.set_index("Date", inplace=True)
                return df.astype(float)
        except Exception as e:
            logger.warning(f"History error {symbol}: {e}")
        return None

    # =========================================================
    # FORMATAGE SYMBOLES
    # =========================================================

    def _format_symbol(self, symbol: str) -> str:
        s = symbol.upper()
        if len(s) == 6:
            return f"{s[:3]}/{s[3:]}"
        if s in ["AAPL", "TSLA", "NVDA", "SPX", "NDX"]:
            return s
        return s
