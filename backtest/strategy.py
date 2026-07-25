"""Standalone strategy clone of signal_engine.SignalEngine for backtests."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import pandas as pd

if __package__:
    from .indicators import adx, atr, bollinger_bands, macd, rsi, sma, support_resistance
else:
    from indicators import adx, atr, bollinger_bands, macd, rsi, sma, support_resistance

ATR_MULTIPLIER_SL = 1.5
RR_RATIO_TARGET = 2.0

SYMBOL_CONFIGS = {
    "BTCUSD": {"adx_min": 23, "rsi_buy_low": 48, "rsi_buy_high": 68, "rsi_sell_low": 32, "rsi_sell_high": 52, "atr_max_pct": 5.5, "min_cond": 4},
    "ETHUSD": {"adx_min": 22, "rsi_buy_low": 47, "rsi_buy_high": 70, "rsi_sell_low": 30, "rsi_sell_high": 56, "atr_max_pct": 6.0, "min_cond": 4},
}

STYLE_CONFIG = {
    "scalping": {"sl_mult": 0.70, "tp_mult": 1.25},
    "scalping_15m": {"sl_mult": 0.85, "tp_mult": 1.55},
    "day": {"sl_mult": 1.15, "tp_mult": 2.2},
    "swing": {"sl_mult": 1.75, "tp_mult": 3.5},
    "position": {"sl_mult": 2.5, "tp_mult": 5.0},
}

REJECTION_THRESHOLDS = {
    "scalping": {"min_score": 62, "min_adx": 18, "min_rr": 1.1},
    "scalping_15m": {"min_score": 63, "min_adx": 18, "min_rr": 1.2},
    "day": {"min_score": 60, "min_adx": 15, "min_rr": 1.3},
    "swing": {"min_score": 58, "min_adx": 15, "min_rr": 1.5},
    "position": {"min_score": 55, "min_adx": 15, "min_rr": 1.8},
}

BUFFER_MULTIPLIERS = {"scalping": 0.10, "scalping_15m": 0.12, "day": 0.15, "swing": 0.20, "position": 0.25}

DEFAULT_ASSET_RULE = {
    "sl_factor": 1.00,
    "tp_factor": 1.00,
    "adx_delta": 1,
    "min_score_delta": 1,
    "min_rr_delta": 0.0,
    "pullback_pct": 0.035,
    "overextension_factor": 1.00,
    "sr_buffer_factor": 1.00,
}

CRYPTO_RULE = {
    "sl_factor": 1.25,
    "tp_factor": 1.15,
    "adx_delta": 0,
    "min_score_delta": 0,
    "min_rr_delta": 0.0,
    "pullback_pct": 0.07,
    "overextension_factor": 1.20,
    "sr_buffer_factor": 1.15,
}

TREND_BULLISH = "HAUSSIER"
TREND_BEARISH = "BAISSIER"
TREND_NEUTRAL = "NEUTRE"


def strategy_symbol(symbol: str) -> str:
    symbol = symbol.upper()
    if symbol.endswith("USDT"):
        return f"{symbol[:-4]}USD"
    return symbol


class BacktestSignalEngine:
    @staticmethod
    def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
        rename = {c: c.capitalize() for c in df.columns if c.lower() in ["open", "high", "low", "close", "volume"]}
        return df.rename(columns=rename) if rename else df

    @staticmethod
    def _valid_df(df: pd.DataFrame, min_len: int = 60) -> bool:
        return df is not None and not df.empty and {"Open", "High", "Low", "Close"}.issubset(df.columns) and len(df) >= min_len

    @staticmethod
    def _clamp_score(score: float) -> int:
        return int(round(max(0, min(100, score))))

    @staticmethod
    def _asset_profile(symbol: str) -> Tuple[str, Dict]:
        normalized = strategy_symbol(symbol)
        if normalized in {"BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD", "XRPUSD", "ADAUSD", "DOGEUSD"}:
            rules = DEFAULT_ASSET_RULE.copy()
            rules.update(CRYPTO_RULE)
            return "crypto", rules
        return "generic", DEFAULT_ASSET_RULE.copy()

    @staticmethod
    def _detect_timeframe_trend(df: Optional[pd.DataFrame]) -> str:
        if df is None or not BacktestSignalEngine._valid_df(df, 50):
            return TREND_NEUTRAL
        close = df["Close"]
        sma20_val = sma(close, 20).iloc[-1]
        sma50_val = sma(close, 50).iloc[-1]
        last_price = close.iloc[-1]
        if pd.isna(last_price) or pd.isna(sma20_val) or pd.isna(sma50_val):
            return TREND_NEUTRAL
        if last_price > sma20_val > sma50_val:
            return TREND_BULLISH
        if last_price < sma20_val < sma50_val:
            return TREND_BEARISH
        return TREND_NEUTRAL

    @staticmethod
    def _resample_ohlc(df: pd.DataFrame, rule: str) -> Optional[pd.DataFrame]:
        if not isinstance(df.index, pd.DatetimeIndex):
            return None
        agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
        if "Volume" in df.columns:
            agg["Volume"] = "sum"
        resampled = df.resample(rule).agg(agg).dropna(subset=["Open", "High", "Low", "Close"])
        return resampled if not resampled.empty else None

    @staticmethod
    def _infer_timeframe_minutes(df: pd.DataFrame) -> Optional[float]:
        if not isinstance(df.index, pd.DatetimeIndex) or len(df.index) < 3:
            return None
        deltas = df.index.to_series().diff().dropna().dt.total_seconds() / 60
        return float(deltas.median()) if not deltas.empty else None

    @staticmethod
    def _compute_timeframe_trends(df: pd.DataFrame) -> Dict[str, str]:
        inferred = BacktestSignalEngine._infer_timeframe_minutes(df)
        frames = {"1h": None, "4h": None, "1d": None}
        if inferred is None:
            frames["1h"] = df
        elif inferred <= 90:
            frames["1h"] = df
            frames["4h"] = BacktestSignalEngine._resample_ohlc(df, "4h")
            frames["1d"] = BacktestSignalEngine._resample_ohlc(df, "1D")
        elif inferred <= 300:
            frames["4h"] = df
            frames["1d"] = BacktestSignalEngine._resample_ohlc(df, "1D")
        else:
            frames["1d"] = df
        return {tf: BacktestSignalEngine._detect_timeframe_trend(frame) for tf, frame in frames.items()}

    @staticmethod
    def check_tf_alignment(tf_1h: str, tf_4h: str, tf_1d: str) -> Dict:
        trends = [tf_1h, tf_4h, tf_1d]
        bullish_count = trends.count(TREND_BULLISH)
        bearish_count = trends.count(TREND_BEARISH)
        if bullish_count == 3:
            return {"status": "TOTAL", "direction": TREND_BULLISH, "modifier": 15}
        if bearish_count == 3:
            return {"status": "TOTAL", "direction": TREND_BEARISH, "modifier": 15}
        if bullish_count > 0 and bearish_count > 0:
            return {"status": "CONFLICT", "direction": TREND_NEUTRAL, "modifier": -15}
        if bullish_count == 2:
            return {"status": "PARTIAL", "direction": TREND_BULLISH, "modifier": 5}
        if bearish_count == 2:
            return {"status": "PARTIAL", "direction": TREND_BEARISH, "modifier": 5}
        return {"status": "NEUTRAL", "direction": TREND_NEUTRAL, "modifier": 0}

    @staticmethod
    def _wait(reason: str, indicators: Optional[Dict] = None, score_detail: Optional[Dict] = None, score: int = 0, params_used: Optional[Dict] = None) -> Dict:
        return {
            "signal": "WAIT",
            "reason": reason,
            "rejection_reason": reason,
            "teddy_score": BacktestSignalEngine._clamp_score(score),
            "sl": None,
            "tp": None,
            "tp1": None,
            "tp2": None,
            "rr_ratio": None,
            "indicators": indicators or {},
            "score_detail": score_detail or {},
            "validation_status": "REJECTED",
            "params_used": params_used or {},
        }

    @staticmethod
    def analyze(df: pd.DataFrame, symbol: str = "", style: str = "day") -> Dict:
        symbol = strategy_symbol(symbol.upper())
        df = BacktestSignalEngine._normalize_df(df)
        if not BacktestSignalEngine._valid_df(df):
            return BacktestSignalEngine._wait("signal_insufficient_data")

        asset_class, asset_rules = BacktestSignalEngine._asset_profile(symbol)
        cfg = SYMBOL_CONFIGS.get(symbol, SYMBOL_CONFIGS["BTCUSD"]).copy()
        cfg["adx_min"] = max(1, int(cfg["adx_min"] + asset_rules["adx_delta"]))

        close, high, low = df["Close"], df["High"], df["Low"]
        last_price = float(close.iloc[-1])
        sma20 = float(sma(close, 20).iloc[-1])
        sma50 = float(sma(close, 50).iloc[-1])
        rsi_val = float(rsi(close, 14).iloc[-1])
        macd_line, macd_sig, hist = macd(close, 12, 26, 9)
        macd_val, macd_sig_val, hist_val = float(macd_line.iloc[-1]), float(macd_sig.iloc[-1]), float(hist.iloc[-1])
        adx_series, plus_di_series, minus_di_series = adx(high, low, close, 14)
        adx_val = float(adx_series.iloc[-1])
        plus_di_val, minus_di_val = float(plus_di_series.iloc[-1]), float(minus_di_series.iloc[-1])
        atr_val = float(atr(high, low, close, 14).iloc[-1])
        upper_bb, _, lower_bb = bollinger_bands(close, 20, 2)
        support, resistance = support_resistance(high, low, 50)
        volume_series = df["Volume"] if "Volume" in df.columns else None
        volume_val = float(volume_series.iloc[-1]) if volume_series is not None and len(volume_series) > 0 else None
        volume_ma20_val = float(sma(volume_series, 20).iloc[-1]) if volume_series is not None and len(volume_series) >= 20 else None

        trend_bull = last_price > sma20 > sma50
        trend_bear = last_price < sma20 < sma50
        timeframe_trends = BacktestSignalEngine._compute_timeframe_trends(df)
        tf_alignment = BacktestSignalEngine.check_tf_alignment(timeframe_trends["1h"], timeframe_trends["4h"], timeframe_trends["1d"])
        atr_ratio = atr_val / last_price if last_price else 0

        buy_cond = [trend_bull, cfg["rsi_buy_low"] <= rsi_val <= cfg["rsi_buy_high"], macd_val > macd_sig_val and hist_val > 0, adx_val >= cfg["adx_min"], atr_ratio <= cfg["atr_max_pct"] / 100]
        sell_cond = [trend_bear, cfg["rsi_sell_low"] <= rsi_val <= cfg["rsi_sell_high"], macd_val < macd_sig_val and hist_val < 0, adx_val >= cfg["adx_min"], atr_ratio <= cfg["atr_max_pct"] / 100]

        indicators = {
            "close_vals": list(close.iloc[-6:]), "price": last_price, "rsi": rsi_val, "adx": adx_val,
            "sma20": sma20, "sma50": sma50, "atr": atr_val, "plus_di": plus_di_val, "minus_di": minus_di_val,
            "macd": macd_val, "macd_signal": macd_sig_val, "macd_hist": hist_val, "volume": volume_val,
            "volume_ma20": volume_ma20_val, "bb_upper": float(upper_bb.iloc[-1]), "bb_lower": float(lower_bb.iloc[-1]),
            "support": support, "resistance": resistance, "timeframe_trends": timeframe_trends, "tf_alignment": tf_alignment,
        }
        return BacktestSignalEngine._finalize(buy_cond, sell_cond, last_price, atr_val, indicators, cfg, support, resistance, rsi_val, adx_val, trend_bull, trend_bear, style, asset_class, asset_rules, tf_alignment)

    @staticmethod
    def _compute_sl_tp(signal: str, price: float, atr_val: float, style: Optional[str], asset_rules: Dict) -> Tuple[float, float]:
        style_cfg = STYLE_CONFIG.get(style) if style else None
        sl_mult = (style_cfg or {}).get("sl_mult", ATR_MULTIPLIER_SL) * asset_rules.get("sl_factor", 1.0)
        tp_mult = (style_cfg or {}).get("tp_mult", RR_RATIO_TARGET) * asset_rules.get("tp_factor", 1.0)
        if signal == "BUY":
            return price - sl_mult * atr_val, price + tp_mult * atr_val
        return price + sl_mult * atr_val, price - tp_mult * atr_val

    @staticmethod
    def _adjust_sl_tp_with_sr(signal: str, price: float, sl: float, tp1: float, atr_val: float, support: Optional[float], resistance: Optional[float], style: Optional[str], min_rr: float, asset_rules: Dict) -> Tuple[float, float]:
        if support is None and resistance is None:
            return sl, tp1
        min_dist = 0.5 * atr_val
        if support is not None and abs(price - support) < min_dist:
            support = None
        if resistance is not None and abs(price - resistance) < min_dist:
            resistance = None
        buffer = BUFFER_MULTIPLIERS.get(style, 0.20) * asset_rules.get("sr_buffer_factor", 1.0) * atr_val
        new_sl, new_tp1 = sl, tp1
        if signal == "BUY":
            wider_sl = support - buffer if support is not None and support < price else None
            if wider_sl is not None and wider_sl < sl:
                new_sl = wider_sl
            if resistance is not None and price < resistance < tp1:
                new_tp1 = resistance - buffer
        else:
            wider_sl = resistance + buffer if resistance is not None and resistance > price else None
            if wider_sl is not None and wider_sl > sl:
                new_sl = wider_sl
            if support is not None and tp1 < support < price:
                new_tp1 = support + buffer
        sl_dist, tp_dist = abs(price - new_sl), abs(price - new_tp1)
        if sl_dist > 0 and tp_dist / sl_dist < min_rr:
            return sl, tp1
        if signal == "BUY" and (new_sl >= price or new_tp1 <= price):
            return sl, tp1
        if signal == "SELL" and (new_sl <= price or new_tp1 >= price):
            return sl, tp1
        return new_sl, new_tp1

    @staticmethod
    def _compute_score(signal: str, price: float, tp1: float, rr: Optional[float], adx_val: float, rsi_val: float, support: Optional[float], resistance: Optional[float], indicators: Dict) -> Tuple[int, Dict]:
        detail = {"trend": 0, "pullback": 0, "momentum": 0, "adx": 0, "rr": 0, "rsi": 0, "sr": 0, "volume": 0}
        if signal == "WAIT":
            return 0, detail
        close = price
        sma20_val, sma50_val = indicators.get("sma20"), indicators.get("sma50")
        if close is not None and sma20_val is not None and sma50_val is not None:
            sma_aligned = (signal == "BUY" and sma20_val > sma50_val) or (signal == "SELL" and sma20_val < sma50_val)
            price_aligned = (signal == "BUY" and close > sma20_val) or (signal == "SELL" and close < sma20_val)
            detail["trend"] = 15 if sma_aligned and price_aligned else (10 if sma_aligned else 5)
            dist_pct = abs(close - sma20_val) / close * 100 if close else 0
            detail["pullback"] = 10 if dist_pct <= 0.25 else 8 if dist_pct <= 0.50 else 5 if dist_pct <= 1.00 else 2 if dist_pct <= 1.50 else 0
        hist, macd_val, macd_sig = indicators.get("macd_hist"), indicators.get("macd"), indicators.get("macd_signal")
        if hist is not None:
            hist_ok = (signal == "BUY" and hist > 0) or (signal == "SELL" and hist < 0)
            line_ok = (signal == "BUY" and macd_val > macd_sig) or (signal == "SELL" and macd_val < macd_sig)
            detail["momentum"] = (12 if line_ok else 0) + (8 if hist_ok else 0)
        plus_di, minus_di = indicators.get("plus_di"), indicators.get("minus_di")
        if adx_val is not None and plus_di is not None and minus_di is not None:
            dir_ok = (signal == "BUY" and plus_di > minus_di) or (signal == "SELL" and minus_di > plus_di)
            if dir_ok:
                di_gap = abs(plus_di - minus_di)
                detail["adx"] = (5 if adx_val >= 25 else 3 if adx_val >= 20 else 0) + (5 if di_gap > 10 else 3 if di_gap > 5 else 0) + (5 if adx_val >= 35 else 0)
        if signal == "BUY":
            detail["rsi"] = 10 if 50 < rsi_val <= 65 else 5 if 40 < rsi_val <= 50 else 3 if 65 < rsi_val <= 75 else 0
        else:
            detail["rsi"] = 10 if 35 <= rsi_val < 50 else 5 if 50 <= rsi_val < 60 else 3 if 25 <= rsi_val < 35 else 0
        if rr is not None:
            detail["rr"] = 10 if rr >= 3.0 else 7 if rr >= 2.0 else 4 if rr >= 1.5 else 0
        relevant = support if signal == "BUY" else resistance
        if relevant is not None and close is not None and close > 0:
            dist_pct = abs(close - relevant) / close * 100
            side_ok = (signal == "BUY" and relevant <= close) or (signal == "SELL" and relevant >= close)
            detail["sr"] = 15 if dist_pct <= 1.0 and side_ok else 10 if dist_pct <= 2.0 and side_ok else 5 if dist_pct <= 3.0 else 0
        volume, volume_ma20 = indicators.get("volume"), indicators.get("volume_ma20")
        if volume is not None and volume_ma20 is not None and volume_ma20 > 0:
            vr = volume / volume_ma20
            detail["volume"] = 5 if vr >= 1.5 else 3 if vr >= 1.2 else 0
        return BacktestSignalEngine._clamp_score(sum(detail.values())), detail

    @staticmethod
    def _finalize(buy_cond: list, sell_cond: list, price: float, atr_val: float, indicators: Dict, cfg: Dict, support: Optional[float], resistance: Optional[float], rsi_val: float, adx_val: float, trend_bull: bool, trend_bear: bool, style: str, asset_class: str, asset_rules: Dict, tf_alignment: Dict) -> Dict:
        min_cond = cfg["min_cond"]
        params_used = {"style": style or "default", "asset_class": asset_class, "sl_factor": asset_rules.get("sl_factor", 1.0), "tp_factor": asset_rules.get("tp_factor", 1.0), "adx_min": cfg.get("adx_min"), "min_cond": min_cond, "pullback_pct": asset_rules.get("pullback_pct")}
        signal = "BUY" if sum(buy_cond) >= min_cond else "SELL" if sum(sell_cond) >= min_cond else "WAIT"
        if signal == "WAIT":
            return BacktestSignalEngine._wait("signal_wait_neutral", indicators, params_used=params_used)
        if atr_val > 0 and len(indicators.get("close_vals", [])) >= 6:
            recent_move = (price - indicators["close_vals"][-6]) / atr_val
            limit = {"scalping": 1.4, "scalping_15m": 1.6, "day": 2.0, "swing": 2.5, "position": 3.0}.get(style, 2.0) * asset_rules.get("overextension_factor", 1.0)
            if signal == "BUY" and recent_move > limit:
                return BacktestSignalEngine._wait(f"Entry too late — price already moved up {recent_move:.1f}xATR (max {limit})", indicators, params_used=params_used)
            if signal == "SELL" and recent_move < -limit:
                return BacktestSignalEngine._wait(f"Entry too late — price already moved down {abs(recent_move):.1f}xATR (max {limit})", indicators, params_used=params_used)
        sma20_val, bb_upper, bb_lower = indicators.get("sma20"), indicators.get("bb_upper"), indicators.get("bb_lower")
        if sma20_val is not None and sma20_val > 0:
            pullback_pct = asset_rules.get("pullback_pct", 0.035)
            if signal == "BUY" and (price > sma20_val * (1 + pullback_pct) or (bb_upper is not None and price > bb_upper)):
                return BacktestSignalEngine._wait("Price extended, wait for pullback", indicators, params_used=params_used)
            if signal == "SELL" and (price < sma20_val * (1 - pullback_pct) or (bb_lower is not None and price < bb_lower)):
                return BacktestSignalEngine._wait("Price extended, wait for pullback", indicators, params_used=params_used)
        thresholds = REJECTION_THRESHOLDS.get(style or "day", REJECTION_THRESHOLDS["day"])
        sl, tp1 = BacktestSignalEngine._compute_sl_tp(signal, price, atr_val, style, asset_rules)
        if atr_val > 0:
            sl, tp1 = BacktestSignalEngine._adjust_sl_tp_with_sr(signal, price, sl, tp1, atr_val, support, resistance, style, thresholds["min_rr"], asset_rules)
        rr = round(abs(tp1 - price) / abs(price - sl), 2) if abs(price - sl) > 0 else None
        score, detail = BacktestSignalEngine._compute_score(signal, price, tp1, rr, adx_val, rsi_val, support, resistance, indicators)
        modifier = int(tf_alignment.get("modifier", 0))
        direction = tf_alignment.get("direction", TREND_NEUTRAL)
        signal_direction = TREND_BULLISH if signal == "BUY" else TREND_BEARISH
        if modifier > 0 and direction != signal_direction:
            modifier = -15
            tf_alignment = {**tf_alignment, "status": "CONFLICT", "modifier": modifier}
        score = BacktestSignalEngine._clamp_score(score + modifier)
        detail["multi_timeframe"] = modifier
        detail["timeframe_alignment"] = tf_alignment.get("status", "NEUTRAL")
        thresholds = {"min_score": thresholds["min_score"] + asset_rules.get("min_score_delta", 0), "min_adx": thresholds["min_adx"] + asset_rules.get("adx_delta", 0), "min_rr": thresholds["min_rr"] + asset_rules.get("min_rr_delta", 0.0)}
        params_used.update(thresholds)
        if adx_val < thresholds["min_adx"]:
            return BacktestSignalEngine._wait(f"Trend too weak — ADX {adx_val:.1f} < {thresholds['min_adx']}", indicators, detail, score, params_used)
        if rr is not None and rr < thresholds["min_rr"]:
            return BacktestSignalEngine._wait(f"RR too low — {rr:.2f} < {thresholds['min_rr']} required for {style or 'default'} style", indicators, detail, score, params_used)
        if score < thresholds["min_score"]:
            return BacktestSignalEngine._wait(f"Score too low — {score}/100 < {thresholds['min_score']} required", indicators, detail, score, params_used)
        return {"signal": signal, "reason": f"{signal} validated", "teddy_score": score, "sl": sl, "tp": tp1, "tp1": tp1, "tp2": tp1 + (atr_val if signal == "BUY" else -atr_val), "rr_ratio": rr, "indicators": indicators, "score_detail": detail, "validation_status": "VALIDATED", "rejection_reason": None, "asset_class": asset_class, "params_used": params_used}
