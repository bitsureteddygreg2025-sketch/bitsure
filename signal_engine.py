import pandas as pd
from typing import Dict, Optional, Tuple

from indicators import rsi, macd, sma, atr, adx, bollinger_bands, support_resistance
from config import (
    ATR_MULTIPLIER_SL, RR_RATIO_TARGET, SYMBOL_CONFIGS
)
from i18n import get_text


# =========================================================
# CONFIG STYLES DE TRADING
# =========================================================

STYLE_CONFIG = {
    "scalping": {"sl_mult": 0.70, "tp_mult": 1.25},
    "scalping_15m": {"sl_mult": 0.85, "tp_mult": 1.55},
    "day":      {"sl_mult": 1.15, "tp_mult": 2.2},
    "swing":    {"sl_mult": 1.75, "tp_mult": 3.5},
    "position": {"sl_mult": 2.5,  "tp_mult": 5.0},
}

# =========================================================
# SCORING
# =========================================================

SCORE_WEIGHTS = {
    "trend": 30,
    "rr":    25,
    "sr":    20,
    "adx":   15,
    "rsi":   10,
}

# Seuils de rejet par style
REJECTION_THRESHOLDS = {
    "scalping": {"min_score": 62, "min_adx": 18, "min_rr": 1.1},
    "scalping_15m": {"min_score": 63, "min_adx": 18, "min_rr": 1.2},
    "day":      {"min_score": 60, "min_adx": 15, "min_rr": 1.3},
    "swing":    {"min_score": 58, "min_adx": 15, "min_rr": 1.5},
    "position": {"min_score": 55, "min_adx": 15, "min_rr": 1.8},
}

# Buffer S/R par style (multiplicateur de l'ATR)
BUFFER_MULTIPLIERS = {
    "scalping": 0.10,
    "scalping_15m": 0.12,
    "day":      0.15,
    "swing":    0.20,
    "position": 0.25,
}

ASSET_CLASS_RULES = {
    "crypto": {
        "symbols": {"BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD", "XRPUSD", "ADAUSD", "DOGEUSD",
                    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"},
        "sl_factor": 1.25,
        "tp_factor": 1.15,
        "adx_delta": 0,
        "min_score_delta": 3,  # Score minimal plus élevé pour crypto (plus de bruit)
        "min_rr_delta": 0.10,  # RR minimum légèrement plus élevé pour crypto
        "pullback_pct": 0.04,  # Réduit de 7% → 4% pour éviter entrées trop tardives
        "overextension_factor": 1.20,
        "sr_buffer_factor": 1.15,
        "atr_min_pct": 0.003,  # ATR minimum 0.3% du prix (marché actif)
    },
    "forex": {
        "symbols": {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"},
        "sl_factor": 0.90,
        "tp_factor": 1.00,
        "adx_delta": 3,
        "min_score_delta": 4,
        "min_rr_delta": 0.10,
        "pullback_pct": 0.025,
        "overextension_factor": 0.90,
        "sr_buffer_factor": 0.85,
    },
    "metal": {
        "symbols": {"XAUUSD", "GOLD"},
        "sl_factor": 1.15,
        "tp_factor": 1.10,
        "adx_delta": 1,
        "min_score_delta": 2,
        "min_rr_delta": 0.05,
        "pullback_pct": 0.045,
        "overextension_factor": 1.10,
        "sr_buffer_factor": 1.20,
    },
    "equity_index": {
        "symbols": {"AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "SPY", "QQQ", "NAS100", "US30", "SPX500"},
        "sl_factor": 1.05,
        "tp_factor": 1.05,
        "adx_delta": 1,
        "min_score_delta": 1,
        "min_rr_delta": 0.0,
        "pullback_pct": 0.045,
        "overextension_factor": 1.00,
        "sr_buffer_factor": 1.00,
    },
}

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

TREND_BULLISH = "HAUSSIER"
TREND_BEARISH = "BAISSIER"
TREND_NEUTRAL = "NEUTRE"


class SignalEngine:

    @staticmethod
    def _asset_profile(symbol: str) -> Tuple[str, Dict]:
        symbol = (symbol or "").upper()
        for asset_class, rules in ASSET_CLASS_RULES.items():
            if symbol in rules["symbols"]:
                profile = DEFAULT_ASSET_RULE.copy()
                profile.update({k: v for k, v in rules.items() if k != "symbols"})
                return asset_class, profile
        return "generic", DEFAULT_ASSET_RULE.copy()

    @staticmethod
    def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
        """Normalise les noms de colonnes en Capitalize (Open, High, Low, Close, Volume)."""
        rename = {}
        for c in df.columns:
            if c.lower() in ["open", "high", "low", "close", "volume"]:
                rename[c] = c.capitalize()
        return df.rename(columns=rename) if rename else df

    @staticmethod
    def _valid_df(df: pd.DataFrame, min_len: int = 60) -> bool:
        """Vérifie que le DataFrame est valide et suffisamment long."""
        required = {"Open", "High", "Low", "Close"}
        return (
            df is not None
            and not df.empty
            and required.issubset(df.columns)
            and len(df) >= min_len
        )

    @staticmethod
    def _clamp_score(score: float) -> int:
        score = max(0, min(100, score))
        return int(round(score))

    @staticmethod
    def _detect_timeframe_trend(df: Optional[pd.DataFrame]) -> str:
        """Detecte la tendance avec la logique SMA deja utilisee par le moteur."""
        if df is None or not SignalEngine._valid_df(df, min_len=50):
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
        if deltas.empty:
            return None
        return float(deltas.median())

    @staticmethod
    def _compute_timeframe_trends(df: pd.DataFrame) -> Dict[str, str]:
        """
        Construit les tendances 1H, 4H, 1D a partir des donnees disponibles.

        Quand l'index temporel est disponible, les timeframes superieurs sont
        derives par resampling. Si la granularite source est plus haute que 1H,
        les timeframes indisponibles restent neutres pour eviter une fausse
        precision.
        """
        inferred_minutes = SignalEngine._infer_timeframe_minutes(df)
        frames = {"1h": None, "4h": None, "1d": None}

        if inferred_minutes is None:
            frames["1h"] = df
        elif inferred_minutes <= 90:
            frames["1h"] = df
            frames["4h"] = SignalEngine._resample_ohlc(df, "4h")
            frames["1d"] = SignalEngine._resample_ohlc(df, "1D")
        elif inferred_minutes <= 300:
            frames["4h"] = df
            frames["1d"] = SignalEngine._resample_ohlc(df, "1D")
        else:
            frames["1d"] = df

        return {
            "1h": SignalEngine._detect_timeframe_trend(frames["1h"]),
            "4h": SignalEngine._detect_timeframe_trend(frames["4h"]),
            "1d": SignalEngine._detect_timeframe_trend(frames["1d"]),
        }

    @staticmethod
    def check_tf_alignment(tf_1h, tf_4h, tf_1d):
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
    def _apply_tf_alignment_score(score: int, signal: str, tf_alignment: Dict) -> Tuple[int, Dict]:
        alignment = (tf_alignment or {}).copy()
        modifier = int(alignment.get("modifier", 0))
        direction = alignment.get("direction", TREND_NEUTRAL)
        signal_direction = TREND_BULLISH if signal == "BUY" else TREND_BEARISH

        if modifier > 0 and direction != signal_direction:
            modifier = -15
            alignment["status"] = "CONFLICT"
            alignment["modifier"] = modifier

        return SignalEngine._clamp_score(score + modifier), alignment

    @staticmethod
    def _wait(
        lang: str,
        reason_key: str = "signal_insufficient_data",
        indicators: Optional[Dict] = None,
        score_detail: Optional[Dict] = None,
        score: int = 0,
        asset_class: str = "generic",
        params_used: Optional[Dict] = None,
    ) -> Dict:
        """
        Retourne un signal WAIT.

        - reason_key peut être une clé i18n (ex: "signal_insufficient_data")
          ou un texte lisible direct (ex: "RR too low for this style").
        - indicators est conservé pour que le graphique s'affiche même en cas de rejet.
        - score_detail est conservé pour la transparence.
        """
        # Distingue clé i18n vs texte brut
        _KNOWN_REASON_KEYS = {
            "signal_insufficient_data",
            "signal_wait_neutral",
        }
        if reason_key in _KNOWN_REASON_KEYS:
            reason_text = get_text(lang, reason_key)
        else:
            # Texte lisible direct (rejets de filtres)
            reason_text = reason_key

        return {
            "signal": "WAIT",
            "signal_text": get_text(lang, "signal_wait"),
            "reason": reason_text,
            "rejection_reason": reason_text,
            "risk_advice": "",
            "teddy_score": SignalEngine._clamp_score(score),
            "confidence": get_text(lang, "confidence_low"),
            "sl": None,
            "tp": None,
            "tp1": None,
            "tp2": None,
            "rr_ratio": None,
            "indicators": indicators or {},
            "score_detail": score_detail or {},
            "validation_status": "REJECTED",
            "asset_class": asset_class,
            "params_used": params_used or {},
        }

    @staticmethod
    def analyze(df: pd.DataFrame, lang: str = "en", symbol: str = "", style: str = "day") -> Dict:
        """
        Point d'entrée principal.

        Args:
            df:     DataFrame OHLC (minimum 60 bougies).
            lang:   Code langue ("en" ou "fr").
            symbol: Symbole (ex: "EURUSD", "BTCUSD").
            style:  Style de trading ("scalping", "scalping_15m", "day", "swing", "position", ou None pour fallback config.py).

        Returns:
            Dict contenant signal, SL, TP, teddy_score, indicators, score_detail, etc.
        """
        symbol = symbol.upper()
        df = SignalEngine._normalize_df(df)

        if not SignalEngine._valid_df(df):
            return SignalEngine._wait(lang)

        asset_class, asset_rules = SignalEngine._asset_profile(symbol)
        cfg = SYMBOL_CONFIGS.get(symbol, SYMBOL_CONFIGS["BTCUSD"]).copy()
        cfg["adx_min"] = max(1, int(cfg["adx_min"] + asset_rules["adx_delta"]))

        close = df["Close"]
        high  = df["High"]
        low   = df["Low"]
        last_price = float(close.iloc[-1])

        # ── Indicateurs ────────────────────────────────────────────────────────
        sma20 = float(sma(close, 20).iloc[-1])
        sma50 = float(sma(close, 50).iloc[-1])

        rsi_val               = float(rsi(close, 14).iloc[-1])
        macd_line, macd_sig, hist = macd(close, 12, 26, 9)
        macd_val              = float(macd_line.iloc[-1])
        macd_sig_val          = float(macd_sig.iloc[-1])
        hist_val              = float(hist.iloc[-1])

        adx_series, plus_di_series, minus_di_series = adx(high, low, close, 14)
        adx_val  = float(adx_series.iloc[-1])
        plus_di_val  = float(plus_di_series.iloc[-1])
        minus_di_val = float(minus_di_series.iloc[-1])
        atr_val  = float(atr(high, low, close, 14).iloc[-1])

        upper_bb, _, lower_bb = bollinger_bands(close, 20, 2)
        upper_bb = float(upper_bb.iloc[-1])
        lower_bb = float(lower_bb.iloc[-1])

        atr_ratio = atr_val / last_price if last_price else 0

        # Volume
        volume_series = df["Volume"] if "Volume" in df.columns else None
        volume_val = float(volume_series.iloc[-1]) if volume_series is not None and len(volume_series) > 0 else None
        volume_ma20_val = float(sma(volume_series, 20).iloc[-1]) if volume_series is not None and len(volume_series) >= 20 else None

        # ── Support / Résistance (peut retourner None) ─────────────────────────
        sr_result = support_resistance(high, low, 50)
        if sr_result is not None:
            support, resistance = sr_result
        else:
            support, resistance = None, None

        # ── Tendances ──────────────────────────────────────────────────────────
        trend_bull = last_price > sma20 > sma50
        trend_bear = last_price < sma20 < sma50
        timeframe_trends = SignalEngine._compute_timeframe_trends(df)
        tf_alignment = SignalEngine.check_tf_alignment(
            timeframe_trends["1h"],
            timeframe_trends["4h"],
            timeframe_trends["1d"],
        )

        # ── Conditions de signal (seuils config.py intacts) ───────────────────
        buy_cond = [
            trend_bull,
            cfg["rsi_buy_low"] <= rsi_val <= cfg["rsi_buy_high"],
            macd_val > macd_sig_val and hist_val > 0,
            adx_val >= cfg["adx_min"],
            atr_ratio <= cfg["atr_max_pct"] / 100,
        ]

        sell_cond = [
            trend_bear,
            cfg["rsi_sell_low"] <= rsi_val <= cfg["rsi_sell_high"],
            macd_val < macd_sig_val and hist_val < 0,
            adx_val >= cfg["adx_min"],
            atr_ratio <= cfg["atr_max_pct"] / 100,
        ]

        # ── Indicators dict (toujours rempli pour le graphique) ───────────────
        indicators = {
            "close_vals": list(close.iloc[-6:]),
            "price":      last_price,
            "rsi":        rsi_val,
            "adx":        adx_val,
            "sma20":      sma20,
            "sma50":      sma50,
            "atr":        atr_val,
            "plus_di":    plus_di_val,
            "minus_di":   minus_di_val,
            "macd":       macd_val,
            "macd_signal": macd_sig_val,
            "macd_hist":  hist_val,
            "volume":     volume_val,
            "volume_ma20": volume_ma20_val,
            "bb_upper":   upper_bb,
            "bb_lower":   lower_bb,
            "support":    support,
            "resistance": resistance,
            "timeframe_trends": timeframe_trends,
            "tf_alignment": tf_alignment,
        }

        return SignalEngine._finalize(
            buy_cond=buy_cond,
            sell_cond=sell_cond,
            price=last_price,
            atr_val=atr_val,
            indicators=indicators,
            lang=lang,
            min_cond=cfg["min_cond"],
            cfg=cfg,
            support=support,
            resistance=resistance,
            rsi_val=rsi_val,
            adx_val=adx_val,
            trend_bull=trend_bull,
            trend_bear=trend_bear,
            style=style,
            symbol=symbol,
            asset_class=asset_class,
            asset_rules=asset_rules,
            tf_alignment=tf_alignment,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # MÉTHODES INTERNES
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_sl_tp(
        signal: str,
        price: float,
        atr_val: float,
        style: Optional[str],
        asset_rules: Optional[Dict] = None,
    ) -> Tuple[float, float]:
        """
        Calcule SL et TP bruts selon le style de trading.

        Fallback : ATR_MULTIPLIER_SL / RR_RATIO_TARGET (config.py) si style=None.
        """
        if style and style in STYLE_CONFIG:
            sl_mult = STYLE_CONFIG[style]["sl_mult"]
            tp_mult = STYLE_CONFIG[style]["tp_mult"]
        else:
            sl_mult = ATR_MULTIPLIER_SL
            tp_mult = RR_RATIO_TARGET

        asset_rules = asset_rules or DEFAULT_ASSET_RULE
        sl_mult *= asset_rules.get("sl_factor", 1.0)
        tp_mult *= asset_rules.get("tp_factor", 1.0)

        if signal == "BUY":
            sl  = price - sl_mult * atr_val
            tp1 = price + tp_mult * atr_val
        else:  # SELL
            sl  = price + sl_mult * atr_val
            tp1 = price - tp_mult * atr_val

        return sl, tp1

    @staticmethod
    def _adjust_sl_tp_with_sr(
        signal: str,
        price: float,
        sl: float,
        tp1: float,
        atr_val: float,
        support: Optional[float],
        resistance: Optional[float],
        style: Optional[str],
        min_rr: float = 1.0,
        asset_rules: Optional[Dict] = None,
    ) -> Tuple[float, float]:
        """
        Ajuste SL et TP en fonction des niveaux Support/Résistance.

        Guard : ne dégrade jamais le RR en dessous de min_rr.
        Si l'ajustement casse le RR, retourne les valeurs ATR brutes.
        """
        if support is None and resistance is None:
            return sl, tp1

        # Validation des niveaux S/R : ignorer si trop proches du prix
        min_dist = 0.5 * atr_val
        if support is not None and abs(price - support) < min_dist:
            support = None
        if resistance is not None and abs(price - resistance) < min_dist:
            resistance = None

        asset_rules = asset_rules or DEFAULT_ASSET_RULE
        buffer_base = BUFFER_MULTIPLIERS.get(style, 0.20) if style else 0.20
        buffer = buffer_base * asset_rules.get("sr_buffer_factor", 1.0) * atr_val

        new_sl, new_tp1 = sl, tp1

        if signal == "BUY":
            wider_sl = support - buffer if support is not None and support < price else None
            if wider_sl is not None and wider_sl < sl:
                new_sl = wider_sl
            if resistance is not None and price < resistance < tp1:
                new_tp1 = resistance - buffer

        elif signal == "SELL":
            wider_sl = resistance + buffer if resistance is not None and resistance > price else None
            if wider_sl is not None and wider_sl > sl:
                new_sl = wider_sl
            if support is not None and tp1 < support < price:
                new_tp1 = support + buffer

        # Guard : ne pas dégrader le RR en dessous du seuil
        sl_dist = abs(price - new_sl)
        tp_dist = abs(price - new_tp1)

        if sl_dist > 0:
            new_rr = tp_dist / sl_dist
            if new_rr < min_rr:
                return sl, tp1  # garder les valeurs ATR brutes

        # Sanity check directionnel
        if signal == "BUY" and (new_sl >= price or new_tp1 <= price):
            return sl, tp1
        if signal == "SELL" and (new_sl <= price or new_tp1 >= price):
            return sl, tp1

        return new_sl, new_tp1

    @staticmethod
    def _compute_score(
        signal: str,
        price: float,
        tp1: float,
        rr: Optional[float],
        adx_val: float,
        rsi_val: float,
        trend_bull: bool,
        trend_bear: bool,
        support: Optional[float],
        resistance: Optional[float],
        style: Optional[str],
        indicators: Dict,
    ) -> Tuple[int, Dict]:
        """Nouveau scoring V3 — 8 critères sur 100 points."""
        detail = {"trend": 0, "pullback": 0, "momentum": 0, "adx": 0, "rr": 0, "rsi": 0, "sr": 0, "volume": 0}
        
        if signal == "WAIT":
            return 0, detail

        def clamp(x, low=0.0, high=1.0):
            return max(low, min(high, x))

        close = price
        sma20 = indicators.get("sma20")
        sma50 = indicators.get("sma50")
        bb_mid = indicators.get("bb_mid", (indicators.get("bb_upper", 0) + indicators.get("bb_lower", 0)) / 2 if indicators.get("bb_upper") and indicators.get("bb_lower") else None)
        plus_di = indicators.get("plus_di")
        minus_di = indicators.get("minus_di")
        macd_val = indicators.get("macd")
        macd_sig = indicators.get("macd_signal")
        macd_hist = indicators.get("macd_hist")
        volume = indicators.get("volume")
        volume_ma20 = indicators.get("volume_ma20")

        # ── 1) Trend + Pullback (max 25) ────────────────────────
        trend_score = 0
        if close is not None and sma20 is not None and sma50 is not None:
            sma_aligned = (signal == "BUY" and sma20 > sma50) or (signal == "SELL" and sma20 < sma50)
            price_aligned = (signal == "BUY" and close > sma20) or (signal == "SELL" and close < sma20)
            trend_score = 15 if sma_aligned and price_aligned else (10 if sma_aligned else 5)

        pullback_score = 0
        if close is not None and sma20 is not None and close > 0:
            dist_pct = abs(close - sma20) / close * 100
            if dist_pct <= 0.25:
                pullback_score = 10
            elif dist_pct <= 0.50:
                pullback_score = 8
            elif dist_pct <= 1.00:
                pullback_score = 5
            elif dist_pct <= 1.50:
                pullback_score = 2

        # ── 2) Momentum MACD (max 20) ───────────────────────────
        momentum_score = 0
        if macd_hist is not None:
            hist_ok = (signal == "BUY" and macd_hist > 0) or (signal == "SELL" and macd_hist < 0)
            if macd_val is not None and macd_sig is not None:
                line_ok = (signal == "BUY" and macd_val > macd_sig) or (signal == "SELL" and macd_val < macd_sig)
            else:
                line_ok = hist_ok
            if line_ok:
                momentum_score += 12
            if hist_ok:
                momentum_score += 8

        # ── 3) ADX directionnel (max 15) ────────────────────────
        adx_score = 0
        if adx_val is not None and plus_di is not None and minus_di is not None:
            dir_ok = (signal == "BUY" and plus_di > minus_di) or (signal == "SELL" and minus_di > plus_di)
            if dir_ok:
                adx_score = 5 if adx_val >= 25 else (3 if adx_val >= 20 else 0)
                di_gap = abs(plus_di - minus_di)
                adx_score += 5 if di_gap > 10 else (3 if di_gap > 5 else 0)
                adx_score += 5 if adx_val >= 35 else 0

        # ── 4) RSI directionnel (max 10) ────────────────────────
        rsi_score = 0
        if rsi_val is not None:
            if signal == "BUY":
                if 50 < rsi_val <= 65:
                    rsi_score = 10
                elif 40 < rsi_val <= 50:
                    rsi_score = 5
                elif 65 < rsi_val <= 75:
                    rsi_score = 3
            else:
                if 35 <= rsi_val < 50:
                    rsi_score = 10
                elif 50 <= rsi_val < 60:
                    rsi_score = 5
                elif 25 <= rsi_val < 35:
                    rsi_score = 3

        # ── 5) RR (max 10) ─────────────────────────────────────
        rr_score = 0
        if rr is not None:
            if rr >= 3.0:
                rr_score = 10
            elif rr >= 2.0:
                rr_score = 7
            elif rr >= 1.5:
                rr_score = 4

        # ── 6) S/R (max 15) ────────────────────────────────────
        sr_score = 0
        relevant = support if signal == "BUY" else resistance
        if relevant is not None and close is not None and close > 0:
            dist_pct = abs(close - relevant) / close * 100
            side_ok = (signal == "BUY" and relevant <= close) or (signal == "SELL" and relevant >= close)
            if dist_pct <= 1.0 and side_ok:
                sr_score = 15
            elif dist_pct <= 2.0 and side_ok:
                sr_score = 10
            elif dist_pct <= 3.0:
                sr_score = 5

        # ── 7) Volume bonus (max 5) ────────────────────────────
        volume_score = 0
        if volume is not None and volume_ma20 is not None and volume_ma20 > 0:
            vr = volume / volume_ma20
            if vr >= 1.5:
                volume_score = 5
            elif vr >= 1.2:
                volume_score = 3

        total = trend_score + pullback_score + momentum_score + adx_score + rr_score + rsi_score + sr_score + volume_score
        total = SignalEngine._clamp_score(total)
        detail = {"trend": trend_score, "pullback": pullback_score, "momentum": momentum_score, "adx": adx_score, "rr": rr_score, "rsi": rsi_score, "sr": sr_score, "volume": volume_score}

        return total, detail

    @staticmethod
    def _finalize(
        buy_cond: list,
        sell_cond: list,
        price: float,
        atr_val: float,
        indicators: Dict,
        lang: str,
        min_cond: int = 4,
        cfg: Optional[Dict] = None,
        support: Optional[float] = None,
        resistance: Optional[float] = None,
        rsi_val: float = 50,
        adx_val: float = 20,
        trend_bull: bool = False,
        trend_bear: bool = False,
        style: Optional[str] = "day",
        symbol: str = "",
        asset_class: str = "generic",
        asset_rules: Optional[Dict] = None,
        tf_alignment: Optional[Dict] = None,
    ) -> Dict:
        """
        Finalise le signal : SL/TP, scoring pondéré, filtres de rejet.

        Toutes les étapes sont indépendantes et testables séparément.
        """
        asset_rules = asset_rules or DEFAULT_ASSET_RULE
        buy_count  = sum(buy_cond)
        sell_count = sum(sell_cond)
        params_used = {
            "style": style or "default",
            "asset_class": asset_class,
            "sl_factor": asset_rules.get("sl_factor", 1.0),
            "tp_factor": asset_rules.get("tp_factor", 1.0),
            "adx_min": cfg.get("adx_min") if cfg else None,
            "min_cond": min_cond,
            "pullback_pct": asset_rules.get("pullback_pct"),
        }

        # ── 1. Détermination du signal brut ───────────────────────────────────
        signal = "WAIT"
        if buy_count >= min_cond:
            signal = "BUY"
        elif sell_count >= min_cond:
            signal = "SELL"

        # Signal WAIT direct (pas assez de conditions)
        if signal == "WAIT":
            return SignalEngine._wait(
                lang,
                reason_key="signal_wait_neutral",
                indicators=indicators,
                score_detail={},
                asset_class=asset_class,
                params_used=params_used,
            )

        # ── 1.5 Filtre régime ATR minimal (marché trop plat) ────────────────────
        atr_min_pct = asset_rules.get("atr_min_pct", 0.0)
        if atr_min_pct > 0 and price > 0:
            atr_ratio_now = atr_val / price
            if atr_ratio_now < atr_min_pct:
                return SignalEngine._wait(
                    lang,
                    f"Market too flat — ATR {atr_ratio_now*100:.3f}% < {atr_min_pct*100:.3f}% min",
                    indicators, asset_class=asset_class, params_used=params_used
                )

        # ── 1.6 Filtre MTF hard : blocage si 4h ET 1d sont contra-tendance ────
        # Plus fort que le modifier de score : bloque le signal quand
        # au moins 2 timeframes supérieurs confirment la direction opposée.
        timeframe_trends = indicators.get("timeframe_trends", {})
        tf_4h = timeframe_trends.get("4h", TREND_NEUTRAL)
        tf_1d = timeframe_trends.get("1d", TREND_NEUTRAL)
        if signal == "BUY":
            contra_count = sum(1 for t in [tf_4h, tf_1d] if t == TREND_BEARISH)
            if contra_count >= 2:
                return SignalEngine._wait(
                    lang,
                    f"MTF hard block — 4h={tf_4h} 1d={tf_1d} contra BUY",
                    indicators, asset_class=asset_class, params_used=params_used
                )
        elif signal == "SELL":
            contra_count = sum(1 for t in [tf_4h, tf_1d] if t == TREND_BULLISH)
            if contra_count >= 2:
                return SignalEngine._wait(
                    lang,
                    f"MTF hard block — 4h={tf_4h} 1d={tf_1d} contra SELL",
                    indicators, asset_class=asset_class, params_used=params_used
                )

        # ── 1.7 Filtre de sur-extension (anti-chasing) ─────────────────────
        if signal in ("BUY", "SELL") and atr_val > 0:
            close_vals = indicators.get("close_vals", [])
            if len(close_vals) < 6:
                pass  # pas assez de données, on skip le filtre
            elif len(close_vals) >= 6:
                close_5_ago = close_vals[-6]
                recent_move = (price - close_5_ago) / atr_val
                thresholds = {"scalping": 1.4, "scalping_15m": 1.6, "day": 2.0, "swing": 2.5, "position": 3.0}
                limit = thresholds.get(style, 2.0) * asset_rules.get("overextension_factor", 1.0)
                if signal == "BUY" and recent_move > limit:
                    return SignalEngine._wait(
                        lang,
                        f"Entry too late — price already moved up {recent_move:.1f}xATR (max {limit})",
                        indicators,
                        asset_class=asset_class,
                        params_used=params_used,
                    )
                if signal == "SELL" and recent_move < -limit:
                    return SignalEngine._wait(
                        lang,
                        f"Entry too late — price already moved down {abs(recent_move):.1f}xATR (max {limit})",
                        indicators,
                        asset_class=asset_class,
                        params_used=params_used,
                    )

        # ── 1.6 Pullback filter souple (par symbole) ──────────────────────
        sma20 = indicators.get("sma20")
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        if signal in ("BUY", "SELL") and sma20 is not None and sma20 > 0:
            pullback_pct = asset_rules.get("pullback_pct", 0.035)
            if signal == "BUY":
                if price > sma20 * (1 + pullback_pct):
                    return SignalEngine._wait(lang, "Price extended, wait for pullback", indicators, asset_class=asset_class, params_used=params_used)
                if bb_upper is not None and price > bb_upper:
                    return SignalEngine._wait(lang, "Price extended, wait for pullback", indicators, asset_class=asset_class, params_used=params_used)
            if signal == "SELL":
                if price < sma20 * (1 - pullback_pct):
                    return SignalEngine._wait(lang, "Price extended, wait for pullback", indicators, asset_class=asset_class, params_used=params_used)
                if bb_lower is not None and price < bb_lower:
                    return SignalEngine._wait(lang, "Price extended, wait for pullback", indicators, asset_class=asset_class, params_used=params_used)

        # ── 2. Calcul SL/TP selon le style ────────────────────────────────────
        sl, tp1 = SignalEngine._compute_sl_tp(signal, price, atr_val, style, asset_rules)

        # ── 3. Ajustement S/R ─────────────────────────────────────────────────
        if atr_val > 0:
            sl, tp1 = SignalEngine._adjust_sl_tp_with_sr(
                signal, price, sl, tp1, atr_val, support, resistance, style,
                min_rr=REJECTION_THRESHOLDS.get(style or "day", REJECTION_THRESHOLDS["day"])["min_rr"],
                asset_rules=asset_rules,
            )

        tp  = tp1
        tp2 = tp1 + (atr_val if signal == "BUY" else -atr_val)

        # ── 4. Ratio RR ───────────────────────────────────────────────────────
        rr: Optional[float] = None
        if sl is not None and tp1 is not None and abs(price - sl) > 0:
            rr = round(abs(tp1 - price) / abs(price - sl), 2)

        # ── 5. Score pondéré ─────────────────────────────────────────────────
        total_score, score_detail = SignalEngine._compute_score(
            signal=signal,
            price=price,
            tp1=tp1,
            rr=rr,
            adx_val=adx_val,
            rsi_val=rsi_val,
            trend_bull=trend_bull,
            trend_bear=trend_bear,
            support=support,
            resistance=resistance,
            style=style,
            indicators=indicators,
        )
        total_score, tf_alignment = SignalEngine._apply_tf_alignment_score(
            total_score,
            signal,
            tf_alignment or indicators.get("tf_alignment", {}),
        )
        score_detail["multi_timeframe"] = tf_alignment.get("modifier", 0)
        score_detail["timeframe_alignment"] = tf_alignment.get("status", "NEUTRAL")

        # ── 6. Filtres de rejet (retourne WAIT avec indicateurs conservés) ────
        base_thresholds = REJECTION_THRESHOLDS.get(style or "day", REJECTION_THRESHOLDS["day"])
        thresholds = {
            "min_score": base_thresholds["min_score"] + asset_rules.get("min_score_delta", 0),
            "min_adx": base_thresholds["min_adx"] + asset_rules.get("adx_delta", 0),
            "min_rr": base_thresholds["min_rr"] + asset_rules.get("min_rr_delta", 0.0),
        }
        params_used.update(thresholds)

        if adx_val < thresholds["min_adx"]:
            return SignalEngine._wait(
                lang,
                reason_key=f"Trend too weak — ADX {adx_val:.1f} < {thresholds['min_adx']}",
                indicators=indicators,
                score_detail=score_detail,
                score=total_score,
                asset_class=asset_class,
                params_used=params_used,
            )

        if rr is not None and rr < thresholds["min_rr"]:
            return SignalEngine._wait(
                lang,
                reason_key=f"RR too low — {rr:.2f} < {thresholds['min_rr']} required for {style or 'default'} style",
                indicators=indicators,
                score_detail=score_detail,
                score=total_score,
                asset_class=asset_class,
                params_used=params_used,
            )

        if total_score < thresholds["min_score"]:
            return SignalEngine._wait(
                lang,
                reason_key=f"Score too low — {total_score}/100 < {thresholds['min_score']} required",
                indicators=indicators,
                score_detail=score_detail,
                score=total_score,
                asset_class=asset_class,
                params_used=params_used,
            )

        # ── 7. Textes i18n ────────────────────────────────────────────────────
        reason   = get_text(lang, f"signal_{signal.lower()}_reason")
        risk     = get_text(lang, f"signal_{signal.lower()}_advice")
        conf_key = (
            "confidence_high"   if total_score >= 75 else
            "confidence_medium" if total_score >= 55 else
            "confidence_low"
        )

        # ── 8. Retour final ───────────────────────────────────────────────────
        return {
            "signal":      signal,
            "signal_text": get_text(lang, f"signal_{signal.lower()}"),
            "reason":      reason,
            "risk_advice": risk,
            "teddy_score": SignalEngine._clamp_score(total_score),
            "confidence":  get_text(lang, conf_key),
            "sl":          sl,
            "tp":          tp,
            "tp1":         tp1,
            "tp2":         tp2,
            "rr_ratio":    rr,
            "indicators":  indicators,
            "score_detail": score_detail,
            "validation_status": "VALIDATED",
            "rejection_reason": None,
            "asset_class": asset_class,
            "params_used": params_used,
        }
