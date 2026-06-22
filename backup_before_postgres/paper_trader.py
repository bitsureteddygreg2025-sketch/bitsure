import json
import os
import time
from typing import Dict, List, Optional


class PaperTrader:
    def __init__(self, data_dir: str = "data"):
        from database import get_db
        self.data_dir = data_dir
        self.conn = get_db()
        self.positions: Dict[str, List[Dict]] = {}
        self.closed_positions: Dict[str, List[Dict]] = {}
        self.capitals: Dict[str, float] = {}
        self._load()

    def _load(self):
        rows = self.conn.execute("SELECT * FROM paper_positions WHERE status='open'").fetchall()
        for r in rows:
            uid = str(r["user_id"])
            if uid not in self.positions:
                self.positions[uid] = []
            self.positions[uid].append({
                "id": r["id"],
                "symbol": r["symbol"],
                "entry_price": r["entry_price"],
                "sl": r["sl"],
                "tp": r["tp"],
                "qty": r["qty"],
                "current_price": r["current_price"],
                "pnl_usdt": r["pnl_usdt"],
                "pnl_pct": r["pnl_pct"],
                "status": "open",
                "opened_at": r["opened_at"],
                "closed_at": None,
                "exit_reason": None,
                "peak_price": r["peak_price"] if r["peak_price"] else r["entry_price"],
            })
        rows2 = self.conn.execute("SELECT * FROM paper_positions WHERE status='closed' ORDER BY closed_at DESC LIMIT 100").fetchall()
        for r in rows2:
            uid = str(r["user_id"])
            if uid not in self.closed_positions:
                self.closed_positions[uid] = []
            self.closed_positions[uid].append({
                "id": r["id"],
                "symbol": r["symbol"],
                "entry_price": r["entry_price"],
                "sl": r["sl"],
                "tp": r["tp"],
                "qty": r["qty"],
                "current_price": r["current_price"],
                "pnl_usdt": r["pnl_usdt"],
                "pnl_pct": r["pnl_pct"],
                "status": "closed",
                "opened_at": r["opened_at"],
                "closed_at": r["closed_at"],
                "exit_reason": r["exit_reason"],
            })
        caps = self.conn.execute("SELECT * FROM paper_capitals").fetchall()
        for c in caps:
            self.capitals[str(c["user_id"])] = c["capital"]

    def _save(self):
        for uid, plist in self.positions.items():
            for p in plist:
                self.conn.execute(
                    "INSERT OR REPLACE INTO paper_positions (id, user_id, symbol, entry_price, sl, tp, qty, current_price, pnl_usdt, pnl_pct, status, opened_at, peak_price) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (p["id"], int(uid), p["symbol"], p["entry_price"], p["sl"], p["tp"], p["qty"], p["current_price"], p["pnl_usdt"], p["pnl_pct"], p["status"], p["opened_at"], p.get("peak_price", p["entry_price"]))
                )
        for uid, plist in self.closed_positions.items():
            for p in plist:
                self.conn.execute(
                    "INSERT OR REPLACE INTO paper_positions (id, user_id, symbol, entry_price, sl, tp, qty, current_price, pnl_usdt, pnl_pct, status, opened_at, closed_at, exit_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (p["id"], int(uid), p["symbol"], p["entry_price"], p["sl"], p["tp"], p["qty"], p["current_price"], p["pnl_usdt"], p["pnl_pct"], "closed", p["opened_at"], p["closed_at"], p["exit_reason"])
                )
        for uid, capital in self.capitals.items():
            self.conn.execute(
                "INSERT OR REPLACE INTO paper_capitals (user_id, capital) VALUES (?,?)",
                (int(uid), capital)
            )
        self.conn.commit()

    def _uid(self, user_id) -> str:
        return str(user_id)

    def init_capital(self, user_id, amount: float = 10000.0):
        uid = self._uid(user_id)
        if uid not in self.capitals:
            self.capitals[uid] = amount
            self.positions[uid] = []
            self.closed_positions[uid] = []
            self._save()

    def get_capital(self, user_id) -> float:
        return self.capitals.get(self._uid(user_id), 10000.0)

    def open_position(self, user_id, symbol: str, entry_price: float, sl: float, tp: float, qty: float) -> Dict:
        uid = self._uid(user_id)
        if uid not in self.capitals:
            self.init_capital(user_id)
        if uid not in self.positions:
            self.positions[uid] = []
        pos = {
            "id": str(int(time.time() * 1000)),
            "symbol": symbol.upper(),
            "entry_price": entry_price,
            "sl": sl,
            "tp": tp,
            "qty": qty,
            "current_price": entry_price,
            "pnl_usdt": 0.0,
            "pnl_pct": 0.0,
            "status": "open",
            "opened_at": time.time(),
            "closed_at": None,
            "exit_reason": None,
        }
        self.positions[uid].append(pos)
        self._save()
        return pos

    def update_price(self, symbol: str, price: float):
        symbol = symbol.upper()
        for uid in self.positions:
            for pos in self.positions[uid]:
                if pos["symbol"] == symbol and pos["status"] == "open":
                    pos["current_price"] = price
                    pos["pnl_usdt"] = (price - pos["entry_price"]) * pos["qty"]
                    pos["pnl_pct"] = ((price - pos["entry_price"]) / pos["entry_price"]) * 100 if pos["entry_price"] > 0 else 0
        self._save()

    def check_exits(self) -> List[Dict]:
        closed = []
        for uid in self.positions:
            for pos in self.positions[uid]:
                if pos["status"] != "open":
                    continue
                price = pos["current_price"]
                if pos["tp"] and price >= pos["tp"]:
                    pos["status"] = "closed"
                    pos["closed_at"] = time.time()
                    pos["exit_reason"] = "TP"
                    pos["pnl_usdt"] = (pos["tp"] - pos["entry_price"]) * pos["qty"]
                    pos["pnl_pct"] = ((pos["tp"] - pos["entry_price"]) / pos["entry_price"]) * 100
                    if uid not in self.closed_positions:
                        self.closed_positions[uid] = []
                    self.closed_positions[uid].append(pos)
                    closed.append(pos)
                elif pos["sl"] and price <= pos["sl"]:
                    pos["status"] = "closed"
                    pos["closed_at"] = time.time()
                    pos["exit_reason"] = "SL"
                    pos["pnl_usdt"] = (pos["sl"] - pos["entry_price"]) * pos["qty"]
                    pos["pnl_pct"] = ((pos["sl"] - pos["entry_price"]) / pos["entry_price"]) * 100
                    if uid not in self.closed_positions:
                        self.closed_positions[uid] = []
                    self.closed_positions[uid].append(pos)
                    closed.append(pos)
        self.positions = {uid: [p for p in plist if p["status"] == "open"] for uid, plist in self.positions.items()}
        self._save()
        return closed

    def get_positions(self, user_id) -> List[Dict]:
        return self.positions.get(self._uid(user_id), [])

    def get_closed_positions(self, user_id) -> List[Dict]:
        return self.closed_positions.get(self._uid(user_id), [])

    def get_stats(self, user_id) -> Dict:
        uid = self._uid(user_id)
        capital = self.get_capital(user_id)
        closed = self.closed_positions.get(uid, [])
        open_pos = self.positions.get(uid, [])
        total_pnl = sum(p.get("pnl_usdt", 0) for p in closed)
        wins = sum(1 for p in closed if p.get("pnl_usdt", 0) > 0)
        total_closed = len(closed)
        return {
            "capital": capital,
            "equity": capital + total_pnl + sum(p.get("pnl_usdt", 0) for p in open_pos),
            "total_pnl": total_pnl,
            "open_positions": len(open_pos),
            "total_trades": total_closed + len(open_pos),
            "wins": wins,
            "losses": total_closed - wins,
            "win_rate": (wins / total_closed * 100) if total_closed > 0 else 0,
        }

    def close_position(self, user_id, position_id: str, exit_price: float) -> Optional[Dict]:
        uid = self._uid(user_id)
        for pos in self.positions.get(uid, []):
            if pos["id"] == position_id and pos["status"] == "open":
                pos["status"] = "closed"
                pos["closed_at"] = time.time()
                pos["exit_reason"] = "MANUAL"
                pos["current_price"] = exit_price
                pos["pnl_usdt"] = (exit_price - pos["entry_price"]) * pos["qty"]
                pos["pnl_pct"] = ((exit_price - pos["entry_price"]) / pos["entry_price"]) * 100 if pos["entry_price"] > 0 else 0
                if uid not in self.closed_positions:
                    self.closed_positions[uid] = []
                self.closed_positions[uid].append(pos)
                self.positions[uid] = [p for p in self.positions[uid] if p["id"] != position_id]
                self._save()
                return pos
        return None
