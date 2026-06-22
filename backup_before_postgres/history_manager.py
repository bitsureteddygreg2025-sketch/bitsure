"""
Gestionnaire d'historique des signaux pour Bitsure Teddy.
Stockage SQLite uniquement.
"""

import hashlib
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
        return {
            "id": row["id"],
            "symbol": row["symbol"],
            "direction": row["direction"],
            "entry_price": row["entry_price"],
            "timeframe": "1h",
            "type": "analyse",
            "score": row["score"],
            "timestamp": datetime.utcfromtimestamp(row["created_at"]).isoformat() if row["created_at"] else "",
            "created_at": row["created_at"],
            "closed_at": row["closed_at"] if row["closed_at"] else None,
            "status": row["status"],
            "sl": row["sl"],
            "tp": row["tp"],
            "result_price": row["result_price"] if "result_price" in row.keys() else None,
            "result_pct": row["result_pct"]
        }

    # =========================================================
    # AJOUT
    # =========================================================

    def add_signal(self, symbol: str, direction: str, price: float, timeframe: str,
                   signal_type: str = "analyse", score: int = 0,
                   sl: Optional[float] = None, tp: Optional[float] = None, user_id: int = None) -> str:
        signal_id = hashlib.md5(f"{symbol}{direction}{price}{timeframe}{time.time()}".encode()).hexdigest()[:8]
        now = time.time()
        self.conn.execute(
            "INSERT OR REPLACE INTO signals (id, symbol, direction, entry_price, sl, tp, score, status, result_pct, created_at, user_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (signal_id, symbol.upper(), direction, price, sl, tp, score, "pending", None, now, user_id)
        )
        self.conn.commit()
        return signal_id

    # =========================================================
    # LECTURE
    # =========================================================

    def get_recent_signals(self, limit: int = 10, user_id: int = None) -> List[Dict]:
        if user_id:
            rows = self.conn.execute("SELECT * FROM signals WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM signals ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_signal_by_id(self, signal_id: str) -> Optional[Dict]:
        row = self.conn.execute("SELECT * FROM signals WHERE id=?", (signal_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    # =========================================================
    # MISE À JOUR DU STATUT
    # =========================================================

    def update_signal_status(self, signal_id: str, status: str, result_pct: float):
        """Met à jour le statut d'un signal avec le PnL% et l'heure de clôture."""
        result_pct = max(-100, min(400, result_pct))
        self.conn.execute(
            "UPDATE signals SET status=?, result_pct=?, closed_at=? WHERE id=?",
            (status, result_pct, time.time(), signal_id)
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
                self.update_signal_status(signal_id, "win", result_pct)
                return "win"
            elif sl and current_price <= sl:
                result_pct = round((current_price - entry) / entry * 100, 4)
                self.update_signal_status(signal_id, "loss", result_pct)
                return "loss"
        elif direction == "SELL":
            if tp and current_price <= tp:
                result_pct = round((entry - current_price) / entry * 100, 4)
                self.update_signal_status(signal_id, "win", result_pct)
                return "win"
            elif sl and current_price >= sl:
                result_pct = round((entry - current_price) / entry * 100, 4)
                self.update_signal_status(signal_id, "loss", result_pct)
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
        self.conn.execute("DELETE FROM signals WHERE created_at < ?", (cutoff,))
        self.conn.commit()
        logger.info(f"✅ Signaux de plus de {days} jours supprimés")
