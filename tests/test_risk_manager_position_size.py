import os
import sys
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("ADMIN_ID", "1")

database_stub = types.ModuleType("database")
database_stub.get_connection = lambda: (_ for _ in ()).throw(RuntimeError("DB not available in unit test"))
sys.modules.setdefault("database", database_stub)

binance_manager_stub = types.ModuleType("binance_manager")
class _BinanceClientError(Exception):
    pass
binance_manager_stub.BinanceClientError = _BinanceClientError
binance_manager_stub.open_position = lambda *a, **k: {"quantity": a[3] if len(a) > 3 else k.get("quantity", 0), "order_id": "1", "client_order_id": k.get("client_order_id")}
binance_manager_stub.get_price = lambda *a, **k: 100.0
binance_manager_stub.get_tradable_symbols = lambda *a, **k: []
binance_manager_stub.get_klines_dataframe = lambda *a, **k: None
binance_manager_stub.make_client_order_id = lambda prefix, unique_key: f"{prefix}_{unique_key}"
binance_manager_stub.close_position = lambda *a, **k: {"order_id": "close"}
binance_manager_stub.cancel_order = lambda *a, **k: None
binance_manager_stub.get_account_balance = lambda *a, **k: 0
binance_manager_stub.get_available_balance = lambda *a, **k: 0
binance_manager_stub.get_open_binance_positions = lambda *a, **k: []
binance_manager_stub.get_open_binance_orders = lambda *a, **k: []
binance_manager_stub.ORDER_CONTEXT_AUTOTRADE = "autotrade"
binance_manager_stub.ORDER_CONTEXT_MANUAL_AUTHENTICATED = "manual_authenticated"
binance_manager_stub.ORDER_CONTEXT_EMERGENCY = "emergency_stop"
sys.modules.setdefault("binance_manager", binance_manager_stub)

from trading_config import TradingConfig
import risk_manager


class PositionSizeExposureTests(unittest.TestCase):
    def test_futures_exposure_cap_is_leverage_adjusted_notional(self):
        config = TradingConfig(user_id=1, market_type="futures", leverage=50, risk_per_trade=1.0)
        with patch.object(risk_manager, "get_account_balance", return_value=4525.82), \
             patch.object(risk_manager, "get_available_balance", return_value=4525.82):
            quantity = risk_manager.calculate_position_size(
                user_id=1,
                config=config,
                entry_price=3000.0,
                sl_price=2998.0,
                market_type="futures",
            )
        self.assertAlmostEqual(quantity, 22.6291, places=4)

    def test_spot_exposure_cap_remains_unleveraged(self):
        config = TradingConfig(user_id=1, market_type="spot", leverage=50, risk_per_trade=1.0)
        with patch.object(risk_manager, "get_account_balance", return_value=4525.82):
            with self.assertRaisesRegex(ValueError, "Exposition trop élevée"):
                risk_manager.calculate_position_size(
                    user_id=1,
                    config=config,
                    entry_price=3000.0,
                    sl_price=2998.0,
                    market_type="spot",
                )


if __name__ == "__main__":
    unittest.main()
