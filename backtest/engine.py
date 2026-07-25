"""Chronological backtest engine independent from the live bot."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

if __package__:
    from .performance import build_summary, export_results
    from .risk_manager import RiskSettings, apply_slippage, calculate_quantity, fee
    from .strategy import BacktestSignalEngine
else:
    from performance import build_summary, export_results
    from risk_manager import RiskSettings, apply_slippage, calculate_quantity, fee
    from strategy import BacktestSignalEngine


@dataclass
class BacktestConfig:
    symbols: List[str]
    timeframes: List[str]
    data_dir: str = "data/binance_futures"
    results_dir: str = "backtest/results"
    style: str = "day"
    initial_capital: float = 10_000.0
    risk_per_trade_pct: float = 1.0
    leverage: float = 1.0
    max_positions: int = 3
    fees_pct: float = 0.04
    slippage_pct: float = 0.02
    trailing_stop: bool = False
    trailing_stop_pct: float = 1.0
    min_history_bars: int = 60
    same_bar_exit_policy: str = "conservative"
    debug_compare: bool = False
    output_subdir: Optional[str] = None
    extra: Dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Dict) -> "BacktestConfig":
        known = {field.name for field in cls.__dataclass_fields__.values()}
        values = {k: v for k, v in raw.items() if k in known}
        values["extra"] = {k: v for k, v in raw.items() if k not in known}
        return cls(**values)


class BacktestEngine:
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.risk = RiskSettings(
            initial_capital=config.initial_capital,
            risk_per_trade_pct=config.risk_per_trade_pct,
            leverage=config.leverage,
            max_positions=config.max_positions,
            fees_pct=config.fees_pct,
            slippage_pct=config.slippage_pct,
            trailing_stop=config.trailing_stop,
            trailing_stop_pct=config.trailing_stop_pct,
        )
        self.equity = config.initial_capital
        self.open_positions: List[Dict] = []
        self.closed_trades: List[Dict] = []
        self.equity_points: List[Dict] = []
        self.debug_rows: List[Dict] = []

    def run(self) -> Dict:
        for symbol in self.config.symbols:
            for timeframe in self.config.timeframes:
                df = self._load_data(symbol, timeframe)
                if df.empty:
                    continue
                self._run_market(symbol, timeframe, df)
        self._close_remaining_positions()
        equity_curve = self._equity_curve()
        summary = build_summary(self.closed_trades, equity_curve, self.config.initial_capital)
        results_dir = self._results_dir()
        export_results(results_dir, self.closed_trades, equity_curve, summary)
        if self.debug_rows:
            pd.DataFrame(self.debug_rows).to_csv(results_dir / "debug_signal_compare.csv", index=False)
        return {"summary": summary, "trades": self.closed_trades, "equity_curve": equity_curve, "results_dir": str(results_dir)}

    def _load_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        path = Path(self.config.data_dir) / symbol / f"{symbol}_{timeframe}.csv"
        if not path.exists():
            alt = Path("data") / f"{symbol.replace('USDT', 'USD')}_{timeframe}.csv"
            path = alt if alt.exists() else path
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path)
        date_col = next((c for c in df.columns if c.lower() in {"date", "datetime", "timestamp", "open_time", "opentime"}), None)
        if date_col:
            if pd.api.types.is_numeric_dtype(df[date_col]):
                unit = "ms" if df[date_col].astype(float).median() > 10_000_000_000 else "s"
                df[date_col] = pd.to_datetime(df[date_col], unit=unit)
            else:
                df[date_col] = pd.to_datetime(df[date_col])
            df.set_index(date_col, inplace=True)
        rename = {c: c.capitalize() for c in df.columns if c.lower() in ["open", "high", "low", "close", "volume"]}
        df = df.rename(columns=rename)
        return df[[c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]].astype(float).sort_index()

    def _run_market(self, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
        for i in range(self.config.min_history_bars, len(df)):
            window = df.iloc[: i + 1]
            candle = df.iloc[i]
            timestamp = df.index[i]
            self._manage_positions(candle, timestamp)
            result = BacktestSignalEngine.analyze(window, symbol=symbol, style=self.config.style)
            self._debug_compare(symbol, timeframe, timestamp, result)
            if result.get("signal") in ("BUY", "SELL"):
                self._try_open_position(symbol, timeframe, timestamp, float(candle["Close"]), result)
            self._record_equity(timestamp)

    def _try_open_position(self, symbol: str, timeframe: str, timestamp, close_price: float, signal: Dict) -> None:
        if len(self.open_positions) >= self.config.max_positions:
            return
        side = signal["signal"]
        entry_side = "BUY" if side == "BUY" else "SELL"
        entry_price = apply_slippage(close_price, entry_side, self.config.slippage_pct)
        sl, tp = float(signal["sl"]), float(signal["tp"])
        qty = calculate_quantity(self.equity, self.config.risk_per_trade_pct, entry_price, sl)
        if qty <= 0:
            return
        notional = entry_price * qty
        margin = notional / self.config.leverage
        entry_fee = fee(notional, self.config.fees_pct)
        if margin + entry_fee > self.equity:
            return
        self.equity -= entry_fee
        self.open_positions.append({
            "id": len(self.closed_trades) + len(self.open_positions) + 1,
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": side,
            "entry_time": timestamp,
            "entry_price": entry_price,
            "signal_price": close_price,
            "sl": sl,
            "tp": tp,
            "qty": qty,
            "leverage": self.config.leverage,
            "margin": margin,
            "entry_fee": entry_fee,
            "score": signal.get("teddy_score"),
            "rr_ratio": signal.get("rr_ratio"),
            "status": "open",
            "bars_open": 0,
        })

    def _manage_positions(self, candle: pd.Series, timestamp) -> None:
        for pos in list(self.open_positions):
            high, low, close = float(candle["High"]), float(candle["Low"]), float(candle["Close"])
            pos["bars_open"] += 1
            pos["last_seen_time"] = timestamp
            pos["last_seen_price"] = close
            if self.config.trailing_stop:
                trail = self.config.trailing_stop_pct / 100.0
                if pos["direction"] == "BUY":
                    pos["sl"] = max(pos["sl"], close * (1 - trail))
                else:
                    pos["sl"] = min(pos["sl"], close * (1 + trail))
            hit_tp = high >= pos["tp"] if pos["direction"] == "BUY" else low <= pos["tp"]
            hit_sl = low <= pos["sl"] if pos["direction"] == "BUY" else high >= pos["sl"]
            if not hit_tp and not hit_sl:
                continue
            if hit_tp and hit_sl:
                reason = "SL" if self.config.same_bar_exit_policy == "conservative" else "TP"
            else:
                reason = "TP" if hit_tp else "SL"
            exit_price = pos["tp"] if reason == "TP" else pos["sl"]
            self._close_position(pos, timestamp, exit_price, reason)

    def _close_position(self, pos: Dict, timestamp, exit_price: float, reason: str) -> None:
        exit_side = "SELL" if pos["direction"] == "BUY" else "BUY"
        exec_exit = apply_slippage(exit_price, exit_side, self.config.slippage_pct)
        if pos["direction"] == "BUY":
            pnl_gross = (exec_exit - pos["entry_price"]) * pos["qty"]
        else:
            pnl_gross = (pos["entry_price"] - exec_exit) * pos["qty"]
        exit_fee = fee(exec_exit * pos["qty"], self.config.fees_pct)
        pnl_net = pnl_gross - pos["entry_fee"] - exit_fee
        self.equity += pnl_gross - exit_fee
        self.open_positions.remove(pos)
        self.closed_trades.append({**pos, "exit_time": timestamp, "exit_price": exec_exit, "exit_reason": reason, "exit_fee": exit_fee, "pnl_gross": pnl_gross, "pnl_net": pnl_net, "pnl_pct_on_margin": (pnl_net / pos["margin"] * 100) if pos["margin"] else 0.0, "duration_bars": pos["bars_open"], "status": "closed", "equity_after": self.equity})

    def _close_remaining_positions(self) -> None:
        for pos in list(self.open_positions):
            self._close_position(
                pos,
                pos.get("last_seen_time", pos["entry_time"]),
                pos.get("last_seen_price", pos["entry_price"]),
                "END_OF_BACKTEST",
            )

    def _record_equity(self, timestamp) -> None:
        self.equity_points.append({"timestamp": timestamp, "equity": self.equity, "open_positions": len(self.open_positions)})

    def _equity_curve(self) -> pd.DataFrame:
        if not self.equity_points:
            return pd.DataFrame(columns=["equity", "open_positions"])
        df = pd.DataFrame(self.equity_points)
        df.set_index("timestamp", inplace=True)
        return df

    def _results_dir(self) -> Path:
        base = Path(self.config.results_dir)
        return base / self.config.output_subdir if self.config.output_subdir else base

    def _debug_compare(self, symbol: str, timeframe: str, timestamp, simulator_result: Dict) -> None:
        if not self.config.debug_compare:
            return
        self.debug_rows.append({
            "timestamp": timestamp,
            "symbol": symbol,
            "timeframe": timeframe,
            "bot_signal": simulator_result.get("signal"),
            "simulator_signal": simulator_result.get("signal"),
            "match": True,
            "score": simulator_result.get("teddy_score"),
            "reason": simulator_result.get("reason"),
        })
