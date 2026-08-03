"""
tests/test_symbol_normalization.py
------------------------------------
Unit tests for the canonical normalize_symbol() function in utils.py.
These act as the contract specification for symbol normalization across
the entire bot codebase.

Run with:
    python -m pytest tests/test_symbol_normalization.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import normalize_symbol, is_valid_symbol


# ---------------------------------------------------------------------------
# Valid canonical conversions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    # Slash separator
    ("BTC/USD",   "BTCUSDT"),
    ("ETH/USD",   "ETHUSDT"),
    ("SOL/USD",   "SOLUSDT"),
    ("BNB/USD",   "BNBUSDT"),
    # Space separator
    ("BTC USD",   "BTCUSDT"),
    ("ETH USD",   "ETHUSDT"),
    # Dash separator
    ("BTC-USD",   "BTCUSDT"),
    ("ETH-USD",   "ETHUSDT"),
    # Lowercase
    ("btcusd",    "BTCUSDT"),
    ("eth/usd",   "ETHUSDT"),
    ("btc/usdt",  "BTCUSDT"),
    # Already canonical — no-op
    ("BTCUSDT",   "BTCUSDT"),
    ("ETHUSDT",   "ETHUSDT"),
    ("BNBUSDT",   "BNBUSDT"),
    # Dash between base and USDT
    ("ETH-USDT",  "ETHUSDT"),
    ("BTC-USDT",  "BTCUSDT"),
    # Forex / precious metals — not in _USD_TO_USDT_BASES, kept as-is
    ("EUR/USD",   "EURUSD"),
    ("GBP/USD",   "GBPUSD"),
    ("XAU/USD",   "XAUUSD"),
    ("xauusd",    "XAUUSD"),
    # Leading / trailing whitespace
    ("  BTCUSDT  ", "BTCUSDT"),
    ("  btc/usd  ", "BTCUSDT"),
])
def test_normalize_symbol_valid(raw, expected):
    assert normalize_symbol(raw) == expected


# ---------------------------------------------------------------------------
# Invalid inputs must raise ValueError
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    "",
    "   ",
    "!!!",
    "@#$%",
    "VERYLONGSYMBOLNAME123456",   # >20 chars after strip
])
def test_normalize_symbol_invalid(raw):
    with pytest.raises(ValueError):
        normalize_symbol(raw)


# ---------------------------------------------------------------------------
# is_valid_symbol — boolean wrapper
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("BTCUSDT",  True),
    ("BTC/USD",  True),
    ("btcusd",   True),
    ("ETH USD",  True),
    ("EUR/USD",  True),
    ("",         False),
    ("!!!",      False),
    ("VERYLONGSYMBOLNAME123456", False),
])
def test_is_valid_symbol(raw, expected):
    assert is_valid_symbol(raw) == expected


# ---------------------------------------------------------------------------
# normalize_symbol is idempotent on already-canonical symbols
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("symbol", [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "EURUSD", "XAUUSD", "GBPUSD",
])
def test_normalize_symbol_idempotent(symbol):
    assert normalize_symbol(normalize_symbol(symbol)) == normalize_symbol(symbol)
