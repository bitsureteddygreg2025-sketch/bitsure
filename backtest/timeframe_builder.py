"""
timeframe_builder.py

Génère les timeframes 15m, 1h, 4h et 1D à partir des données 5m
Binance Futures.

Source :
data/binance_futures/{SYMBOL}/{SYMBOL}_5m.csv

Sorties :
data/binance_futures/{SYMBOL}/{SYMBOL}_{15m,1h,4h,1d}.csv

Usage :
python backtest/timeframe_builder.py
"""

import os
import pandas as pd


DATA_DIR = "data/binance_futures"

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT"
]

SOURCE_TIMEFRAME = "5m"
SOURCE_TIMEFRAME_MINUTES = 5


TARGET_TIMEFRAMES = {
    "15m": {
        "rule": "15min",
        "min_candles": 3
    },
    "1h": {
        "rule": "1h",
        "min_candles": 12
    },
    "4h": {
        "rule": "4h",
        "min_candles": 48
    },
    "1d": {
        "rule": "1D",
        "min_candles": 288
    },
}


NUMERIC_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "volume"
]

REQUIRED_COLUMNS = [
    "timestamp"
] + NUMERIC_COLUMNS


def get_file_path(symbol, timeframe):
    folder = os.path.join(
        DATA_DIR,
        symbol
    )

    return os.path.join(
        folder,
        f"{symbol}_{timeframe}.csv"
    )


def load_data(symbol):

    file_path = get_file_path(
        symbol,
        SOURCE_TIMEFRAME
    )

    print(
        f"Chargement {symbol} {SOURCE_TIMEFRAME}..."
    )

    if not os.path.exists(file_path):
        print(
            f"⚠️ Fichier introuvable : {file_path}"
        )
        return None


    df = pd.read_csv(file_path)


    missing = [
        col
        for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]


    if missing:
        print(
            f"⚠️ Colonnes manquantes : {missing}"
        )
        return None


    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True
    )


    print(
        f"{len(df)} bougies chargées."
    )

    return df



def validate_data(df, symbol):

    df = df.sort_values(
        "timestamp"
    )


    df = df.drop_duplicates(
        subset="timestamp",
        keep="last"
    )


    for col in NUMERIC_COLUMNS:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )


    before = len(df)


    df = df.dropna(
        subset=NUMERIC_COLUMNS
    )


    removed = before - len(df)


    if removed:
        print(
            f"⚠️ {symbol}: {removed} lignes invalides supprimées"
        )


    gaps = (
        df["timestamp"]
        .diff()
        .dropna()
    )


    expected = pd.Timedelta(
        minutes=SOURCE_TIMEFRAME_MINUTES
    )


    missing = gaps[gaps > expected]


    if not missing.empty:

        print(
            f"⚠️ {symbol}: {len(missing)} trous détectés dans les données 5m"
        )


    return df.reset_index(drop=True)



def resample_timeframe(df, rule, min_candles):

    indexed = df.set_index(
        "timestamp"
    )


    candle_count = (
        indexed["close"]
        .resample(
            rule,
            label="left",
            closed="left"
        )
        .count()
    )


    result = (
        indexed
        .resample(
            rule,
            label="left",
            closed="left"
        )
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum"
            }
        )
    )


    result["candle_count"] = candle_count


    incomplete = result[
        result["candle_count"] < min_candles
    ]


    if not incomplete.empty:

        print(
            f"⚠️ {len(incomplete)} bougies incomplètes supprimées"
        )


    result = result[
        result["candle_count"] >= min_candles
    ]


    result = result.drop(
        columns=["candle_count"]
    )


    result = result.dropna()


    result = result.reset_index()


    for col in NUMERIC_COLUMNS:

        result[col] = result[col].astype(float)


    return result



def save_timeframe(df, symbol, timeframe):

    file_path = get_file_path(
        symbol,
        timeframe
    )


    os.makedirs(
        os.path.dirname(file_path),
        exist_ok=True
    )


    output = df.copy()


    output["timestamp"] = (
        output["timestamp"]
        .dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )


    output.to_csv(
        file_path,
        index=False
    )


    print(
        f"✅ Sauvegarde : {file_path}"
    )



def process_symbol(symbol):

    print(
        f"\n===== {symbol} ====="
    )


    df = load_data(symbol)


    if df is None:
        return


    df = validate_data(
        df,
        symbol
    )


    for timeframe, config in TARGET_TIMEFRAMES.items():


        print(
            f"\nCréation {symbol} {timeframe}..."
        )


        result = resample_timeframe(
            df,
            config["rule"],
            config["min_candles"]
        )


        print(
            f"{len(result)} bougies créées."
        )


        save_timeframe(
            result,
            symbol,
            timeframe
        )



if __name__ == "__main__":

    for symbol in SYMBOLS:

        process_symbol(symbol)