"""Performance metrics and export helpers for backtest results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


def build_summary(trades: List[Dict], equity_curve: pd.DataFrame, initial_capital: float) -> Dict:
    closed = [t for t in trades if t.get("status") == "closed"]
    wins = [t for t in closed if t.get("pnl_net", 0) > 0]
    losses = [t for t in closed if t.get("pnl_net", 0) <= 0]
    gross_profit = sum(t.get("pnl_net", 0) for t in wins)
    gross_loss = abs(sum(t.get("pnl_net", 0) for t in losses))
    final_equity = float(equity_curve["equity"].iloc[-1]) if not equity_curve.empty else initial_capital
    returns = equity_curve["equity"].pct_change().replace([np.inf, -np.inf], np.nan).dropna() if not equity_curve.empty else pd.Series(dtype=float)
    sharpe = None
    if not returns.empty and returns.std() != 0:
        sharpe = float((returns.mean() / returns.std()) * np.sqrt(252))
    drawdown = 0.0
    if not equity_curve.empty:
        running_max = equity_curve["equity"].cummax()
        dd = (equity_curve["equity"] - running_max) / running_max
        drawdown = float(dd.min() * 100)
    durations = [t.get("duration_bars", 0) for t in closed]

    period_returns = pd.Series(dtype=float)
    if not equity_curve.empty and isinstance(equity_curve.index, pd.DatetimeIndex):
        period_returns = equity_curve["equity"].resample("M").last().pct_change().dropna()

    return {
        "total_trades": len(closed),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": round((len(wins) / len(closed) * 100), 2) if closed else 0.0,
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 8),
        "net_profit": round(final_equity - initial_capital, 8),
        "net_profit_pct": round(((final_equity - initial_capital) / initial_capital * 100), 4) if initial_capital else 0.0,
        "max_drawdown_pct": round(drawdown, 4),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
        "sharpe_ratio": round(sharpe, 4) if sharpe is not None else None,
        "best_period": str(period_returns.idxmax().date()) if not period_returns.empty else None,
        "worst_period": str(period_returns.idxmin().date()) if not period_returns.empty else None,
        "average_trade_duration_bars": round(float(np.mean(durations)), 2) if durations else 0.0,
    }


def export_results(results_dir: Path, trades: List[Dict], equity_curve: pd.DataFrame, summary: Dict) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(trades).to_csv(results_dir / "trades.csv", index=False)
    equity_curve.to_csv(results_dir / "equity_curve.csv")
    with (results_dir / "summary.json").open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
