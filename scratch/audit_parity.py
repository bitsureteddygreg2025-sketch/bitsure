"""Audit verification script for backtest reliability."""

import pandas as pd
from backtest.strategy import BacktestSignalEngine
from signal_engine import SignalEngine

def run_parity_test():
    df = pd.read_csv("data/binance_futures/BTCUSDT/BTCUSDT_1h.csv").tail(500)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.set_index("timestamp", inplace=True)
    
    mismatches = 0
    total = len(df) - 60
    for i in range(60, len(df)):
        win = df.iloc[:i+1]
        res_bt = BacktestSignalEngine.analyze(win, symbol="BTCUSDT", style="day")
        res_live = SignalEngine.analyze(win, lang="fr", symbol="BTCUSDT", style="day")
        if res_bt["signal"] != res_live["signal"] or res_bt.get("teddy_score") != res_live.get("teddy_score"):
            mismatches += 1
            print(f"Mismatch at bar {i}: BT={res_bt['signal']}/{res_bt.get('teddy_score')} Live={res_live['signal']}/{res_live.get('teddy_score')}")

    print(f"Parity Test Completed: {total} bars tested, {mismatches} mismatches found.")

if __name__ == "__main__":
    run_parity_test()
