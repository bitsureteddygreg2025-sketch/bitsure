import os
import time
import unittest
import sys
import types
from unittest.mock import patch

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("ADMIN_ID", "1")

# Unit tests avoid requiring local PostgreSQL/psycopg2 dependencies.
database_stub = types.ModuleType("database")
database_stub.get_connection = lambda: (_ for _ in ()).throw(RuntimeError("DB not available in unit test"))
sys.modules.setdefault("database", database_stub)
logger_stub = types.ModuleType("trading_logger")
class _Logger:
    def critical(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def info(self, *a, **k): pass
    def debug(self, *a, **k): pass
logger_stub.get_trading_logger = lambda name: _Logger()
logger_stub.log_trade_opened = lambda *a, **k: None
logger_stub.log_trade_closed = lambda *a, **k: None
logger_stub.log_error = lambda *a, **k: None
sys.modules.setdefault("trading_logger", logger_stub)

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

binance_stub = types.ModuleType("binance")
binance_exceptions_stub = types.ModuleType("binance.exceptions")
class _BinanceAPIException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)
        self.message = str(args[0]) if args else ""
class _BinanceOrderException(Exception): pass
binance_exceptions_stub.BinanceAPIException = _BinanceAPIException
binance_exceptions_stub.BinanceOrderException = _BinanceOrderException
sys.modules.setdefault("binance", binance_stub)
sys.modules.setdefault("binance.exceptions", binance_exceptions_stub)
binance_client_stub = types.ModuleType("binance.client")
class _Client: pass
binance_client_stub.Client = _Client
sys.modules.setdefault("binance.client", binance_client_stub)

binance_manager_stub = types.ModuleType("binance_manager")
class _BinanceClientError(Exception): pass
binance_manager_stub.BinanceClientError = _BinanceClientError
binance_manager_stub.open_position = lambda *a, **k: {"quantity": a[3] if len(a) > 3 else k.get("quantity", 0), "order_id": "1", "client_order_id": k.get("client_order_id")}
binance_manager_stub.get_price = lambda *a, **k: 100.0
binance_manager_stub.get_tradable_symbols = lambda *a, **k: []
binance_manager_stub.get_klines_dataframe = lambda *a, **k: None
binance_manager_stub.make_client_order_id = lambda prefix, unique_key: f"{prefix}_{unique_key}"
binance_manager_stub.close_position = lambda *a, **k: {"order_id": "close"}
binance_manager_stub.cancel_order = lambda *a, **k: None
binance_manager_stub.get_open_binance_positions = lambda *a, **k: []
binance_manager_stub.get_open_binance_orders = lambda *a, **k: []
sys.modules.setdefault("binance_manager", binance_manager_stub)

risk_manager_stub = types.ModuleType("risk_manager")
class _RiskResult:
    def __init__(self, allowed=True, reason=None):
        self.allowed = allowed
        self.reason = reason
risk_manager_stub.check_can_open_position = lambda *a, **k: _RiskResult(True)
risk_manager_stub.calculate_position_size = lambda *a, **k: 0.1
risk_manager_stub.record_trade_loss = lambda *a, **k: 0.0
sys.modules.setdefault("risk_manager", risk_manager_stub)

history_manager_stub = types.ModuleType("history_manager")
class _HistoryManager:
    @classmethod
    def get_instance(cls): return cls()
history_manager_stub.HistoryManager = _HistoryManager
sys.modules.setdefault("history_manager", history_manager_stub)

signal_engine_stub = types.ModuleType("signal_engine")
class _SignalEngine: pass
signal_engine_stub.SignalEngine = _SignalEngine
sys.modules.setdefault("signal_engine", signal_engine_stub)

from trading_config import TradingConfig
from trading_safety import SafetyError, validate_signal_freshness


class TradingSafetyTests(unittest.TestCase):
    def test_stale_signal_is_rejected(self):
        signal = {"created_at": time.time() - 901}
        with self.assertRaises(SafetyError):
            validate_signal_freshness(signal, max_age_seconds=900)

    def test_duplicate_reserved_signal_does_not_open_order(self):
        import execution_engine

        signal = {
            "id": "sig-1",
            "user_id": 42,
            "symbol": "BTCUSDT",
            "direction": "BUY",
            "entry_price": 100.0,
            "sl": 95.0,
            "tp": 110.0,
            "score": 90,
            "status": "pending",
            "created_at": time.time(),
        }
        config = TradingConfig(user_id=42, auto_trade=True)
        with patch.object(execution_engine, "reserve_signal_for_execution", side_effect=SafetyError("already used")), \
             patch.object(execution_engine, "open_position") as open_position:
            result = execution_engine.execute_signal(signal, config)

        open_position.assert_not_called()
        self.assertEqual(result["status"], "skipped")
        self.assertIn("already used", result["error_message"])

    def test_safety_lock_blocks_open_validation(self):
        from execution_engine import validate_signal_for_execution

        signal = {
            "id": "sig-2",
            "user_id": 42,
            "symbol": "BTCUSDT",
            "direction": "BUY",
            "entry_price": 100.0,
            "sl": 95.0,
            "tp": 110.0,
            "score": 90,
            "status": "pending",
            "created_at": time.time(),
        }
        config = TradingConfig(user_id=42, auto_trade=True, safety_lock=True, safety_lock_reason="divergence")
        allowed, reason = validate_signal_for_execution(42, signal, config)
        self.assertFalse(allowed)
        self.assertIn("Mode sûr", reason)

    def test_close_requires_matching_remote_position(self):
        import position_manager

        row = (1, 42, "BTCUSDT", "BUY", 100.0, 95.0, 110.0, 0.5, 1, "futures", None, None)

        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def execute(self, *args, **kwargs): pass
            def fetchone(self): return row

        class Conn:
            def cursor(self): return Cursor()
            def close(self): pass

        with patch.object(position_manager, "get_connection", return_value=Conn()), \
             patch.object(position_manager, "get_open_binance_positions", return_value=[]), \
             patch.object(position_manager, "engage_safe_mode") as safe_mode, \
             patch.object(position_manager, "close_position") as close_position:
            with self.assertRaises(ValueError):
                position_manager.close_trade_manual(1, 42)

        safe_mode.assert_called_once()
        close_position.assert_not_called()


if __name__ == "__main__":
    unittest.main()
