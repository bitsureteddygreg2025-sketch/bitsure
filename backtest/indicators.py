"""Standalone indicator calculations mirroring the production bot."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)


def _wilder_smooth(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(alpha=1 / period, adjust=False).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    if len(high) < period + 1:
        zeros = pd.Series([0.0] * len(high), index=high.index)
        return zeros, zeros, zeros

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)

    atr_smooth = _wilder_smooth(tr, period)
    plus_dm_smooth = _wilder_smooth(plus_dm, period)
    minus_dm_smooth = _wilder_smooth(minus_dm, period)

    plus_di = 100 * (plus_dm_smooth / atr_smooth.replace(0, np.nan)).fillna(0)
    minus_di = 100 * (minus_dm_smooth / atr_smooth.replace(0, np.nan)).fillna(0)
    denom = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (abs(plus_di - minus_di) / denom)
    return _wilder_smooth(dx.replace([np.inf, -np.inf], 0).fillna(0), period), plus_di, minus_di


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return _wilder_smooth(tr, period)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line


def bollinger_bands(close: pd.Series, period: int = 20, std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    middle = close.rolling(window=period).mean()
    rolling_std = close.rolling(window=period).std()
    return middle + (rolling_std * std), middle, middle - (rolling_std * std)


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def support_resistance(high: pd.Series, low: pd.Series, lookback: int = 50) -> Tuple[Optional[float], Optional[float]]:
    if len(high) < lookback:
        return None, None
    return float(low.iloc[-lookback:].min()), float(high.iloc[-lookback:].max())
