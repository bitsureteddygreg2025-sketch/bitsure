import time
import threading
import asyncio
from typing import Dict, List

from config import MAX_ALERTS_FREE, MAX_ALERTS_TESTER, MAX_ALERTS_PRO


class AlertManager:
    _instance = None

    def __init__(self):
        from database import get_db
        self.conn = get_db()
        self._init_table()
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        self._loop = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # =========================================================
    # INIT DATABASE
    # =========================================================

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                condition TEXT NOT NULL,
                price REAL NOT NULL,
                triggered INTEGER DEFAULT 0,
                created_at REAL DEFAULT 0,
                triggered_at REAL DEFAULT 0
            )
        """)
        self.conn.commit()

    # =========================================================
    # MONITORING
    # =========================================================

    def start_monitoring(self, bot_app):
        if self.running:
            return
        self.running = True
        self._loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, args=(bot_app,), daemon=True)
        self.thread.start()

    def _run_loop(self, bot_app):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._monitor_loop(bot_app))

    async def _monitor_loop(self, bot_app):
        from data_fetcher import DataFetcher
        fetcher = DataFetcher.get_instance()

        while self.running:
            try:
                # 1. Récupérer toutes les alertes non déclenchées
                with self.lock:
                    rows = self.conn.execute(
                        "SELECT * FROM alerts WHERE triggered = 0"
                    ).fetchall()
                    alerts = [dict(r) for r in rows]

                # 2. Grouper par symbole
                grouped = {}
                for a in alerts:
                    symbol = a["symbol"]
                    if symbol not in grouped:
                        grouped[symbol] = []
                    grouped[symbol].append(a)

                # 3. 1 fetch prix par symbole
                for symbol, alert_list in grouped.items():
                    if not alert_list:
                        continue

                    price_data = await fetcher.get_realtime_price(symbol)
                    if not price_data:
                        continue

                    current_price = float(price_data.get("price", 0))
                    if current_price <= 0:
                        continue

                    # 4. Vérifier chaque alerte
                    for alert in alert_list:
                        target = float(alert["price"])
                        if target <= 0:
                            continue

                        condition_met = False
                        if alert["condition"] == "above" and current_price >= target:
                            condition_met = True
                        elif alert["condition"] == "below" and current_price <= target:
                            condition_met = True

                        if condition_met:
                            alert_id = alert["id"]
                            triggered_at = time.time()
                            with self.lock:
                                self.conn.execute(
                                    "UPDATE alerts SET triggered = 1, triggered_at = ? WHERE id = ?",
                                    (triggered_at, alert_id)
                                )
                                self.conn.commit()
                            alert["triggered"] = True
                            alert["triggered_at"] = triggered_at
                            await self._notify_user(bot_app, alert["user_id"], alert, current_price)

                await asyncio.sleep(60)
            except Exception as e:
                print(f"Alert monitoring error: {e}")
                await asyncio.sleep(30)

    # =========================================================
    # NOTIFICATION
    # =========================================================

    async def _notify_user(self, bot_app, user_id: int, alert: Dict, current_price: float):
        try:
            from user_manager import UserManager
            from i18n import get_text
            user_mgr = UserManager.get_instance()
            lang = user_mgr.get_setting(user_id, "lang", "en")
            text = get_text(lang, "alert_triggered",
                            symbol=alert['symbol'],
                            condition=alert['condition'],
                            price=alert['price'],
                            current_price=current_price)
            await bot_app.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Failed to notify user {user_id}: {e}")

    # =========================================================
    # LIMITES
    # =========================================================

    def get_alert_limit(self, user_id: int) -> int:
        from user_manager import UserManager
        user_mgr = UserManager.get_instance()
        role = user_mgr.get_role(user_id)
        if role == "pro":
            return MAX_ALERTS_PRO
        if role == "tester":
            return MAX_ALERTS_TESTER
        return MAX_ALERTS_FREE

    # =========================================================
    # ADD
    # =========================================================

    def add_alert(self, user_id: int, symbol: str, condition: str, price: float):
        user_id = int(user_id)
        symbol = symbol.upper().strip()

        if condition not in ["above", "below"]:
            return False, "Condition invalide"

        with self.lock:
            # Compter les alertes actives
            active = self.conn.execute(
                "SELECT COUNT(*) as c FROM alerts WHERE user_id = ? AND triggered = 0",
                (user_id,)
            ).fetchone()
            limit = self.get_alert_limit(user_id)
            if active["c"] >= limit:
                return False, limit

            now = time.time()
            cursor = self.conn.execute(
                """
                INSERT INTO alerts (user_id, symbol, condition, price, triggered, created_at, triggered_at)
                VALUES (?, ?, ?, ?, 0, ?, 0)
                """,
                (user_id, symbol, condition, float(price), now)
            )
            self.conn.commit()
            alert_id = cursor.lastrowid
            return True, alert_id

    # =========================================================
    # GET
    # =========================================================

    def get_alerts(self, user_id: int) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM alerts WHERE user_id = ? ORDER BY created_at DESC",
            (int(user_id),)
        ).fetchall()
        return [dict(r) for r in rows]

    # =========================================================
    # DELETE
    # =========================================================

    def delete_alert(self, user_id: int, alert_id: int) -> bool:
        with self.lock:
            cursor = self.conn.execute(
                "DELETE FROM alerts WHERE id = ? AND user_id = ?",
                (alert_id, int(user_id))
            )
            self.conn.commit()
            return cursor.rowcount > 0

    # =========================================================
    # CLEAR
    # =========================================================

    def clear_alerts(self, user_id: int):
        with self.lock:
            self.conn.execute(
                "DELETE FROM alerts WHERE user_id = ?",
                (int(user_id),)
            )
            self.conn.commit()

    # =========================================================
    # GET ALL (pour le moteur WebSocket)
    # =========================================================

    def get_all_alerts(self) -> List[Dict]:
        """Retourne toutes les alertes non déclenchées."""
        rows = self.conn.execute(
            "SELECT * FROM alerts WHERE triggered = 0"
        ).fetchall()
        return [dict(r) for r in rows]

    # =========================================================
    # MARK TRIGGERED
    # =========================================================

    def mark_triggered(self, alert_id: int) -> bool:
        with self.lock:
            cursor = self.conn.execute(
                "UPDATE alerts SET triggered = 1, triggered_at = ? WHERE id = ? AND triggered = 0",
                (time.time(), alert_id)
            )
            self.conn.commit()
            return cursor.rowcount > 0

    # =========================================================
    # CLEANUP
    # =========================================================

    def cleanup_triggered_alerts(self, older_than_hours=24):
        cutoff = time.time() - (older_than_hours * 3600)
        with self.lock:
            self.conn.execute(
                "DELETE FROM alerts WHERE triggered = 1 AND triggered_at < ?",
                (cutoff,)
            )
            self.conn.commit()
