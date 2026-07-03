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
    "day":      {"min_score": 60, "min_adx": 15, "min_rr": 1.3},
    "swing":    {"min_score": 58, "min_adx": 15, "min_rr": 1.5},
    "position": {"min_score": 55, "min_adx": 15, "min_rr": 1.8},
}

# Buffer S/R par style (multiplicateur de l'ATR)
BUFFER_MULTIPLIERS = {
    "day":      0.15,
    "swing":    0.20,
    "position": 0.25,
}

ASSET_CLASS_RULES = {
    "crypto": {
        "symbols": {"BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD", "XRPUSD", "ADAUSD", "DOGEUSD"},
        "sl_factor": 1.25,
        "tp_factor": 1.15,
        "adx_delta": 0,
        "min_score_delta": 0,
        "min_rr_delta": 0.0,
        "pullback_pct": 0.07,
        "overextension_factor": 1.20,
        "sr_buffer_factor": 1.15,
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
            "teddy_score": score,
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
            style:  Style de trading ("day", "swing", "position", ou None pour fallback config.py).

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
        total = max(0, min(100, total))
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

        # ── 1.5 Filtre de sur-extension (anti-chasing) ─────────────────────
        if signal in ("BUY", "SELL") and atr_val > 0:
            close_vals = indicators.get("close_vals", [])
            if len(close_vals) < 6:
                pass  # pas assez de données, on skip le filtre
            elif len(close_vals) >= 6:
                close_5_ago = close_vals[-6]
                recent_move = (price - close_5_ago) / atr_val
                thresholds = {"day": 2.0, "swing": 2.5, "position": 3.0}
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
            "teddy_score": min(total_score, 95),
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
