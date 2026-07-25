import os
import time
import requests
import pandas as pd
from datetime import datetime

BASE_URL = "https://fapi.binance.com/fapi/v1/klines"
DATA_DIR = "data/binance_futures"
SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT"
]
INTERVAL = "5m"
INTERVAL_MS = 5 * 60 * 1000  # durée d'une bougie 5m en millisecondes
LIMIT = 1500  # maximum Binance par requête
MAX_RETRIES = 5
SLEEP_BETWEEN_PAGES = 0.2

COLUMNS = [
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "trades",
    "taker_buy_base",
    "taker_buy_quote",
    "ignore"
]

KEEP_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume"]

METADATA = {
    symbol: {
        "exchange": "Binance Futures",
        "market": "USD-M",
        "timeframe": INTERVAL
    }
    for symbol in SYMBOLS
}


def write_metadata():
    """Écrit data/binance_futures/metadata.json pour tracer exchange/market/timeframe par symbole."""
    import json
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, "metadata.json")
    with open(path, "w") as f:
        json.dump(METADATA, f, indent=4)
    print(f"Metadata écrite : {path}")


def get_klines(params):
    """Appelle l'API Binance avec retry/backoff en cas de rate limit ou d'erreur."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(BASE_URL, params=params, timeout=10)
        except requests.RequestException as e:
            wait = min(2 ** attempt, 30)
            print(f"Erreur réseau ({e}), nouvelle tentative dans {wait}s...")
            time.sleep(wait)
            continue

        if response.status_code == 200:
            return response.json()

        if response.status_code in (429, 418):
            wait = int(response.headers.get("Retry-After", 5))
            print(f"Rate limité (HTTP {response.status_code}), attente {wait}s...")
            time.sleep(wait)
            continue

        # Autre erreur (400, 500, etc.) : on log et on arrête proprement
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            print(f"Erreur HTTP {response.status_code}: {e} — {response.text}")
        return None

    print("Nombre maximum de tentatives atteint, abandon de cette requête.")
    return None


def get_file_path(symbol):
    folder = os.path.join(DATA_DIR, symbol)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{symbol}_5m.csv")


def load_existing_data(file_path):
    """Charge le CSV existant s'il existe, retourne (df, last_timestamp_ms) ou (None, None)."""
    if not os.path.exists(file_path):
        return None, None
    df = pd.read_csv(file_path, parse_dates=["timestamp"])
    if df.empty:
        return None, None
    last_ts = int(df["timestamp"].max().timestamp() * 1000)
    return df, last_ts


def fetch_new_candles(symbol, start_time=None):
    """Récupère les bougies depuis start_time (ms) jusqu'à maintenant.
    Si start_time est None, remonte l'historique complet depuis maintenant."""
    all_data = []

    if start_time is not None:
        # Mode incrémental : on avance dans le temps avec startTime
        current_start = start_time
        while True:
            params = {
                "symbol": symbol,
                "interval": INTERVAL,
                "limit": LIMIT,
                "startTime": current_start
            }
            candles = get_klines(params)
            if candles is None:
                break
            if not candles:
                break
            all_data.extend(candles)
            newest = candles[-1][0]
            print(f"{symbol}: {len(all_data)} nouvelles bougies récupérées")
            if len(candles) < LIMIT:
                break
            current_start = newest + 1
            time.sleep(SLEEP_BETWEEN_PAGES)
    else:
        # Mode historique complet : on remonte dans le temps avec endTime
        end_time = int(datetime.now().timestamp() * 1000)
        while True:
            params = {
                "symbol": symbol,
                "interval": INTERVAL,
                "limit": LIMIT,
                "endTime": end_time
            }
            candles = get_klines(params)
            if candles is None:
                break
            if not candles:
                break
            all_data.extend(candles)
            oldest = candles[0][0]
            print(f"{symbol}: {len(all_data)} bougies récupérées")
            end_time = oldest - 1
            if len(candles) < LIMIT:
                break
            time.sleep(SLEEP_BETWEEN_PAGES)

    return all_data


def to_dataframe(raw_candles):
    df = pd.DataFrame(raw_candles, columns=COLUMNS)
    df = df[KEEP_COLUMNS].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    for col in NUMERIC_COLUMNS:
        df[col] = df[col].astype(float)
    return df


def download_symbol(symbol):
    print(f"\nTéléchargement {symbol} Futures {INTERVAL}...")
    file_path = get_file_path(symbol)
    existing_df, last_ts = load_existing_data(file_path)

    if last_ts is not None:
        print(f"Données existantes trouvées, dernière bougie : {existing_df['timestamp'].max()}")
        raw_candles = fetch_new_candles(symbol, start_time=last_ts + INTERVAL_MS)
    else:
        print("Aucune donnée existante, téléchargement de l'historique complet.")
        raw_candles = fetch_new_candles(symbol, start_time=None)

    if not raw_candles:
        print(f"Aucune nouvelle donnée pour {symbol}")
        return

    new_df = to_dataframe(raw_candles)

    if existing_df is not None:
        df = pd.concat([existing_df, new_df], ignore_index=True)
        df = df.drop_duplicates(subset="timestamp", keep="last")
    else:
        df = new_df

    df = df.sort_values("timestamp").reset_index(drop=True)

    # Validation : élimine toute ligne avec valeur manquante ou non numérique
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna().reset_index(drop=True)

    df.to_csv(file_path, index=False)

    print(f"✅ Sauvegardé : {file_path}")
    print(f"Période : {df['timestamp'].min()} → {df['timestamp'].max()}")
    print(f"Total bougies : {len(df)}")


if __name__ == "__main__":
    write_metadata()
    for symbol in SYMBOLS:
        download_symbol(symbol)
