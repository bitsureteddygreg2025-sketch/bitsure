"""Backtest-only risk and position sizing helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskSettings:
    initial_capital: float = 10_000.0
    risk_per_trade_pct: float = 1.0
    leverage: float = 1.0
    max_positions: int = 3
    max_daily_loss_pct: float = 5.0
    fees_pct: float = 0.04
    slippage_pct: float = 0.02
    trailing_stop: bool = False
    trailing_stop_pct: float = 1.0


def calculate_quantity(equity: float, risk_per_trade_pct: float, entry_price: float, sl_price: float) -> float:
    risk_amount = equity * (risk_per_trade_pct / 100.0)
    distance = abs(entry_price - sl_price)
    if equity <= 0 or distance <= 0 or entry_price <= 0:
        return 0.0
    return risk_amount / distance


def apply_slippage(price: float, side: str, slippage_pct: float) -> float:
    factor = slippage_pct / 100.0
    return price * (1.0 + factor) if side.upper() == "BUY" else price * (1.0 - factor)


def fee(notional: float, fees_pct: float) -> float:
    return abs(notional) * fees_pct / 100.0
