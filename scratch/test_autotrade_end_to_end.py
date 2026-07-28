import sys
import os
import types
sys.path.insert(0, os.path.abspath("."))
import time
import sqlite3
from unittest.mock import MagicMock, patch

telegram_stub = types.ModuleType("telegram")
class _Button:
    def __init__(self, *a, **k): pass
class _Markup:
    def __init__(self, *a, **k): pass
telegram_stub.InlineKeyboardButton = _Button
telegram_stub.InlineKeyboardMarkup = _Markup
sys.modules.setdefault("telegram", telegram_stub)
telegram_ext_stub = types.ModuleType("telegram.ext")
class _ContextTypes:
    DEFAULT_TYPE = object
telegram_ext_stub.ContextTypes = _ContextTypes
sys.modules.setdefault("telegram.ext", telegram_ext_stub)

os.environ["TELEGRAM_TOKEN"] = "test-token"
os.environ["ADMIN_ID"] = "1"

# Create sqlite3 DB in memory to serve as mock psycopg2 DB
sqlite_conn = sqlite3.connect(":memory:", check_same_thread=False)
sqlite_conn.row_factory = sqlite3.Row

# Initialize tables
sqlite_conn.executescript("""
CREATE TABLE IF NOT EXISTS trading_config (
    user_id BIGINT PRIMARY KEY,
    auto_trade BOOLEAN DEFAULT FALSE,
    periodic_analysis_enabled BOOLEAN DEFAULT FALSE,
    leverage INTEGER DEFAULT 1,
    risk_per_trade REAL DEFAULT 1.0,
    max_positions INTEGER DEFAULT 3,
    min_score INTEGER DEFAULT 70,
    max_daily_loss REAL DEFAULT 5.0,
    trailing_stop BOOLEAN DEFAULT FALSE,
    trailing_stop_pct REAL DEFAULT 1.0,
    dca_enabled BOOLEAN DEFAULT FALSE,
    dca_steps INTEGER DEFAULT 3,
    dca_step_pct REAL DEFAULT 2.0,
    symbol_whitelist TEXT DEFAULT '',
    symbol_blacklist TEXT DEFAULT '',
    market_type TEXT DEFAULT 'futures',
    trading_style TEXT DEFAULT 'day',
    analysis_timeframe TEXT DEFAULT '1h',
    analysis_interval_minutes INTEGER DEFAULT 5,
    testnet BOOLEAN DEFAULT TRUE,
    cooldown_seconds INTEGER DEFAULT 0,
    daily_loss_accum REAL DEFAULT 0.0,
    safety_lock BOOLEAN DEFAULT FALSE,
    safety_lock_reason TEXT,
    safety_lock_at REAL,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS binance_credentials (
    user_id BIGINT PRIMARY KEY,
    api_key TEXT,
    api_secret TEXT,
    testnet BOOLEAN DEFAULT TRUE,
    is_valid BOOLEAN DEFAULT TRUE,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    user_id BIGINT,
    symbol TEXT,
    direction TEXT,
    entry_price REAL,
    sl REAL,
    tp REAL,
    score INTEGER,
    status TEXT,
    validation_status TEXT,
    validation_reason TEXT,
    rejection_reason TEXT,
    result_price REAL,
    result_pct REAL,
    pnl REAL,
    capital_before REAL,
    capital_after REAL,
    timeframe TEXT,
    signal_type TEXT,
    rr_ratio REAL,
    asset_class TEXT,
    params_used TEXT,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT,
    user_id BIGINT,
    symbol TEXT,
    direction TEXT,
    entry_price REAL,
    sl_price REAL,
    tp_price REAL,
    quantity REAL,
    leverage INTEGER,
    market_type TEXT,
    status TEXT,
    opened_at REAL,
    closed_at REAL,
    exit_reason TEXT,
    pnl_usdt REAL,
    pnl_pct REAL,
    binance_order_id TEXT,
    binance_client_order_id TEXT,
    sl_order_id TEXT,
    tp_order_id TEXT,
    error_message TEXT
);
""")

class SqliteCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
    def execute(self, sql, params=()):
        sql_mod = sql.replace("NOW()", "CURRENT_TIMESTAMP")
        sql_mod = sql_mod.replace("ON CONFLICT (user_id) DO NOTHING", "ON CONFLICT(user_id) DO NOTHING")
        sql_mod = sql_mod.replace("ON CONFLICT (id) DO UPDATE SET", "ON CONFLICT(id) DO UPDATE SET")
        sql_mod = sql_mod.replace("ON CONFLICT (user_id) DO UPDATE", "ON CONFLICT(user_id) DO UPDATE")
        
        returning_cols = None
        if "RETURNING" in sql_mod:
            parts = sql_mod.split("RETURNING")
            sql_mod = parts[0]
            returning_cols = [c.strip() for c in parts[1].split(",")]

        flat_params = []
        if params:
            if isinstance(params, dict):
                import re
                def repl(m):
                    key = m.group(1)
                    flat_params.append(params[key])
                    return "?"
                sql_mod = re.sub(r"%\((.*?)\)s", repl, sql_mod)
            else:
                for p in params:
                    if isinstance(p, (list, tuple)):
                        flat_params.extend(p)
                    else:
                        flat_params.append(p)
                if "status = ANY(%s)" in sql_mod:
                    num_placeholders = len(flat_params) - (len(params) - 1)
                    sql_mod = sql_mod.replace("status = ANY(%s)", f"status IN ({','.join(['?']*num_placeholders)})")
                sql_mod = sql_mod.replace("%s", "?")

        self.cursor.execute(sql_mod, flat_params)
            
        if returning_cols:
            if "INSERT INTO trades" in sql_mod:
                self._last_returning = (self.cursor.lastrowid,)
            elif "UPDATE signals" in sql_mod:
                sig_id = flat_params[0]
                cur2 = sqlite_conn.cursor()
                cur2.execute("SELECT id, user_id, symbol, direction, entry_price, sl, tp, score, status, timeframe, signal_type, created_at FROM signals WHERE id = ?", (sig_id,))
                self._last_returning = cur2.fetchone()
        return self

    def fetchone(self):
        if hasattr(self, "_last_returning"):
            res = self._last_returning
            delattr(self, "_last_returning")
            return res
        row = self.cursor.fetchone()
        if row is None:
            return None
        return tuple(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [tuple(r) for r in rows]

    @property
    def rowcount(self):
        return self.cursor.rowcount

class SqliteConnWrapper:
    def cursor(self):
        return SqliteCursorWrapper(sqlite_conn.cursor())
    def commit(self):
        sqlite_conn.commit()
    def rollback(self):
        sqlite_conn.rollback()
    def close(self):
        pass
    def execute(self, sql, params=()):
        c = SqliteCursorWrapper(sqlite_conn.cursor())
        c.execute(sql, params)
        return c

def mock_get_connection():
    return SqliteConnWrapper()

# Patch database functions before importing history_manager
import database
database.get_connection = mock_get_connection
database.get_db = lambda: SqliteConnWrapper()
database._get_pool = lambda: MagicMock()

import history_manager
history_manager.HistoryManager.get_instance().conn = SqliteConnWrapper()

import trading_config
import trading_safety
import risk_manager
import binance_manager
import execution_engine
import position_manager

from contextlib import contextmanager

@contextmanager
def mock_user_trading_lock(user_id):
    yield mock_get_connection()

trading_safety.user_trading_lock = mock_user_trading_lock
execution_engine.user_trading_lock = mock_user_trading_lock

print("Mock environment setup complete.")

# Insert test credentials
trading_config.save_binance_credentials(12345, "mock_key", "mock_secret", testnet=True)

# Test Step 1: Enable AutoTrade
trading_config.update_config(12345, auto_trade=True, safety_lock=False)
cfg = trading_config.get_config(12345)
print(f"Step 1: AutoTrade status = {cfg.auto_trade}, safety_lock = {cfg.safety_lock}")
assert cfg.auto_trade == True

# Test Step 2: Market analysis scan generating a signal
import pandas as pd
df_mock = pd.DataFrame({
    "OpenTime": [1700000000000 + i*3600000 for i in range(100)],
    "Open": [100.0 + i*0.1 for i in range(100)],
    "High": [105.0 + i*0.1 for i in range(100)],
    "Low": [95.0 + i*0.1 for i in range(100)],
    "Close": [102.0 + i*0.1 for i in range(100)],
    "Volume": [1000.0 for _ in range(100)],
})
df_mock["Date"] = pd.to_datetime(df_mock["OpenTime"], unit="ms")
df_mock.set_index("Date", inplace=True)

mock_signal_result = {
    "signal": "BUY",
    "teddy_score": 85,
    "indicators": {"price": 100.0, "rsi": 55, "macd": 0.5},
    "sl": 95.0,
    "tp": 110.0,
    "validation_status": "VALIDATED",
    "reason": "Bullish trend",
    "rr_ratio": 2.0,
    "asset_class": "crypto",
}

with patch("execution_engine.get_tradable_symbols", return_value=["BTCUSDT"]), \
     patch("execution_engine.get_klines_dataframe", return_value=df_mock), \
     patch("signal_engine.SignalEngine.analyze", return_value=mock_signal_result), \
     patch("risk_manager.count_remote_open_positions", return_value=0), \
     patch("position_manager.get_open_binance_positions", return_value=[]), \
     patch("binance_manager.get_open_binance_positions", return_value=[]):

    import asyncio
    asyncio.run(execution_engine.scheduled_market_analysis(None, 5))

# Check signal in DB
signals = execution_engine.fetch_pending_signals()
print(f"Step 2: Pending signals generated = {len(signals)}")
if signals:
    print(f"Signal 0: {signals[0]}")

# Test Step 3: Scheduled signal scan & execution
mock_binance_open_result = {
    "quantity": 0.1,
    "order_id": "99991111",
    "client_order_id": "sig_123",
    "sl_order_id": "99991112",
    "tp_order_id": "99991113",
}

with patch("risk_manager.get_account_balance", return_value=1000.0), \
     patch("risk_manager.get_available_balance", return_value=1000.0), \
     patch("risk_manager.count_remote_open_positions", return_value=0), \
     patch("binance_manager.get_open_binance_positions", return_value=[]), \
     patch("execution_engine.open_position", return_value=mock_binance_open_result), \
     patch("binance_manager.open_position", return_value=mock_binance_open_result), \
     patch("binance_manager.set_leverage", return_value=None), \
     patch("execution_engine._notify_trade_result", return_value=None):

    asyncio.run(execution_engine.scheduled_signal_scan(None))

cfg_after_exec = trading_config.get_config(12345)
print(f"Step 3: After signal execution, AutoTrade = {cfg_after_exec.auto_trade}, safety_lock = {cfg_after_exec.safety_lock}")

trades = position_manager.get_open_trades(12345)
print(f"Step 3: Local open trades = {len(trades)}")

# Test Step 4: Account reconciliation
with patch("position_manager.get_open_binance_positions", return_value=[{"symbol": "BTCUSDT", "direction": "BUY", "quantity": 0.1}]), \
     patch("position_manager.get_open_binance_orders", return_value=[{"orderId": 99991112}, {"orderId": 99991113}]):
    position_manager.reconcile_all_accounts()

cfg_after_reconcile = trading_config.get_config(12345)
print(f"Step 4: After reconcile, AutoTrade = {cfg_after_reconcile.auto_trade}, safety_lock = {cfg_after_reconcile.safety_lock}")

print("--- DIAGNOSTIC COMPLETED ---")
