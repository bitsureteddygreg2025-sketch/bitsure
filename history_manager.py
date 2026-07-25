"""
Gestionnaire d'historique des signaux pour Bitsure Teddy.
Stockage PostgreSQL uniquement.
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class HistoryManager:
    _instance = None

    def __init__(self):
        from database import get_db
        self.conn = get_db()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # =========================================================
    # HELPERS
    # =========================================================

    def _row_to_dict(self, row) -> Dict:
        keys = row.keys()
        params_used = row["params_used"] if "params_used" in keys else None
        if isinstance(params_used, str):
            try:
                params_used = json.loads(params_used)
            except json.JSONDecodeError:
                pass
        result = row["status"].upper() if row["status"] in ("win", "loss") else None
        return {
            "id": row["id"],
            "symbol": row["symbol"],
            "direction": row["direction"],
            "entry_price": row["entry_price"],
            "timeframe": row["timeframe"] if "timeframe" in keys and row["timeframe"] else "1h",
            "type": row["signal_type"] if "signal_type" in keys and row["signal_type"] else "analyse",
            "score": row["score"],
            "timestamp": datetime.utcfromtimestamp(row["created_at"]).isoformat() if row["created_at"] else "",
            "created_at": row["created_at"],
            "closed_at": row["closed_at"] if row["closed_at"] else None,
            "status": row["status"],
            "result": result,
            "validation_status": row["validation_status"] if "validation_status" in keys else None,
            "validation_reason": row["validation_reason"] if "validation_reason" in keys else None,
            "rejection_reason": row["rejection_reason"] if "rejection_reason" in keys else None,
            "sl": row["sl"],
            "tp": row["tp"],
            "result_price": row["result_price"] if "result_price" in keys else None,
            "result_pct": row["result_pct"],
            "pnl": row["pnl"] if "pnl" in keys else None,
            "capital_before": row["capital_before"] if "capital_before" in keys else None,
            "capital_after": row["capital_after"] if "capital_after" in keys else None,
            "rr_ratio": row["rr_ratio"] if "rr_ratio" in keys else None,
            "asset_class": row["asset_class"] if "asset_class" in keys else None,
            "params_used": params_used,
        }

    # =========================================================
    # AJOUT
    # =========================================================

    def add_signal(self, symbol: str, direction: str, price: float, timeframe: str,
                   signal_type: str = "analyse", score: int = 0,
                   sl: Optional[float] = None, tp: Optional[float] = None, user_id: int = None,
                   validation_status: str = "VALIDATED",
                   validation_reason: Optional[str] = None,
                   rejection_reason: Optional[str] = None,
                   rr_ratio: Optional[float] = None,
                   asset_class: Optional[str] = None,
                   params_used: Optional[Dict] = None,
                   leverage: Optional[float] = None,
                   capital_before: Optional[float] = None,
                   capital_after: Optional[float] = None,
                   pnl: Optional[float] = None) -> Optional[str]:
        if (direction or "").upper() == "WAIT":
            logger.info("Signal WAIT ignore: %s %s", symbol, timeframe)
            return None

        direction = (direction or "").upper()
        signal_id = hashlib.md5(f"{symbol}{direction}{price}{timeframe}{time.time()}".encode()).hexdigest()[:8]
        now = time.time()
        validation_status = (validation_status or "VALIDATED").upper()
        status = "pending" if validation_status == "VALIDATED" and direction in ("BUY", "SELL") else "rejected"
        params_snapshot = dict(params_used or {})
        params_snapshot.update({
            "sl": sl,
            "tp": tp,
            "leverage": leverage,
        })
        params_json = json.dumps(params_snapshot, sort_keys=True, default=str)
        self.conn.execute(
            """
            INSERT INTO signals (
                id, symbol, direction, entry_price, sl, tp, score, status,
                validation_status, validation_reason, rejection_reason, result_price, result_pct, pnl,
                capital_before, capital_after, timeframe, signal_type,
                rr_ratio, asset_class, params_used, created_at, user_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                symbol = excluded.symbol,
                direction = excluded.direction,
                entry_price = excluded.entry_price,
                sl = excluded.sl,
                tp = excluded.tp,
                score = excluded.score,
                status = excluded.status,
                validation_status = excluded.validation_status,
                validation_reason = excluded.validation_reason,
                rejection_reason = excluded.rejection_reason,
                result_price = excluded.result_price,
                result_pct = excluded.result_pct,
                pnl = excluded.pnl,
                capital_before = excluded.capital_before,
                capital_after = excluded.capital_after,
                timeframe = excluded.timeframe,
                signal_type = excluded.signal_type,
                rr_ratio = excluded.rr_ratio,
                asset_class = excluded.asset_class,
                params_used = excluded.params_used,
                created_at = excluded.created_at,
                user_id = excluded.user_id
            """,
            (
                signal_id, symbol.upper(), direction, price, sl, tp, score, status,
                validation_status, validation_reason, rejection_reason, None, None, pnl,
                capital_before, capital_after, timeframe, signal_type,
                rr_ratio, asset_class, params_json, now, user_id
            )
        )
        self.conn.commit()
        return signal_id

    # =========================================================
    # LECTURE
    # =========================================================

    def get_recent_signals(self, limit: int = 10, user_id: int = None) -> List[Dict]:
        if user_id:
            rows = self.conn.execute("SELECT * FROM signals WHERE user_id = %s AND direction <> %s ORDER BY created_at DESC LIMIT %s", (user_id, "WAIT", limit)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM signals WHERE direction <> %s ORDER BY created_at DESC LIMIT %s", ("WAIT", limit)).fetchall()
        return [self._row_to_dict(r) for r in rows]


    def get_user_signals(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Retourne l'historique utilisateur sans inclure les signaux WAIT."""
        return self.get_recent_signals(limit=limit, user_id=user_id)

    def get_signal_by_id(self, signal_id: str) -> Optional[Dict]:
        row = self.conn.execute("SELECT * FROM signals WHERE id = %s AND direction <> %s", (signal_id, "WAIT")).fetchone()
        return self._row_to_dict(row) if row else None

    # =========================================================
    # MISE À JOUR DU STATUT
    # =========================================================

    def update_signal_status(self, signal_id: str, status: str, result_pct: float,
                             result_price: Optional[float] = None,
                             pnl: Optional[float] = None,
                             capital_before: Optional[float] = None,
                             capital_after: Optional[float] = None):
        """Met à jour le statut d'un signal avec le PnL% et l'heure de clôture."""
        result_pct = max(-100, min(400, result_pct))
        self.conn.execute(
            """
            UPDATE signals
            SET status = %s,
                result_price = COALESCE(%s, result_price),
                result_pct = %s,
                pnl = COALESCE(%s, pnl),
                capital_before = COALESCE(%s, capital_before),
                capital_after = COALESCE(%s, capital_after),
                closed_at = %s
            WHERE id = %s
            """,
            (status, result_price, result_pct, pnl, capital_before, capital_after, time.time(), signal_id)
        )
        self.conn.commit()

    # =========================================================
    # MISE À JOUR DU RÉSULTAT (via prix actuel)
    # =========================================================

    def update_signal_result(self, signal_id: str, current_price: float) -> Optional[str]:
        """Vérifie si le signal a touché SL ou TP et met à jour son statut."""
        signal = self.get_signal_by_id(signal_id)
        if not signal or signal["status"] != "pending":
            return None
        entry = signal["entry_price"]
        sl = signal.get("sl")
        tp = signal.get("tp")
        direction = signal["direction"]
        if direction == "BUY":
            if tp and current_price >= tp:
                result_pct = round((current_price - entry) / entry * 100, 4)
                self.update_signal_status(signal_id, "win", result_pct, result_price=current_price)
                return "win"
            elif sl and current_price <= sl:
                result_pct = round((current_price - entry) / entry * 100, 4)
                self.update_signal_status(signal_id, "loss", result_pct, result_price=current_price)
                return "loss"
        elif direction == "SELL":
            if tp and current_price <= tp:
                result_pct = round((entry - current_price) / entry * 100, 4)
                self.update_signal_status(signal_id, "win", result_pct, result_price=current_price)
                return "win"
            elif sl and current_price >= sl:
                result_pct = round((entry - current_price) / entry * 100, 4)
                self.update_signal_status(signal_id, "loss", result_pct, result_price=current_price)
                return "loss"
        return None

    # =========================================================
    # NETTOYAGE
    # =========================================================

    def clear_all_signals(self):
        self.conn.execute("DELETE FROM signals")
        self.conn.commit()
        logger.info("✅ Tous les signaux ont été effacés")

    def clear_old_signals(self, days: int = 30):
        cutoff = time.time() - (days * 86400)
        self.conn.execute("DELETE FROM signals WHERE created_at < %s", (cutoff,))
        self.conn.commit()
        logger.info(f"✅ Signaux de plus de {days} jours supprimés")
