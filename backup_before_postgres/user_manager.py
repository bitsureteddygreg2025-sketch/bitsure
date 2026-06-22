import time
from datetime import datetime
from typing import Dict, List, Optional

from config import (
    FREE_DAILY_REQUESTS,
    ADMIN_ID,
    TRIAL_DAYS,
    ACCESS_MODE,
    ALLOW_AUTO_REGISTER,
    MAX_WATCHLIST_SYMBOLS_FREE,
    MAX_WATCHLIST_SYMBOLS_TESTER,
    MAX_WATCHLIST_SYMBOLS_PRO,
)

from i18n import get_text


class UserManager:

    _instance = None

    def __init__(self):
        from database import get_db
        self.conn = get_db()   # database.py gère tout le schéma

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # =========================================================
    # SAFE GET USER
    # =========================================================

    def get_user(self, user_id: int) -> Optional[Dict]:
        """Récupère un utilisateur depuis SQLite, ou le crée si autorisé."""
        row = self.conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()

        if row:
            return dict(row)

        if not ALLOW_AUTO_REGISTER:
            return None

        now = time.time()
        self.conn.execute(
            """
            INSERT INTO users (user_id, role, lang, timeframe, risk, terms_accepted, trial_start, created_at, approved, username)
            VALUES (?, 'tester', 'en', '1h', 'medium', 0, ?, ?, 0, ?)
            """,
            (user_id, now, now, None)
        )
        self.conn.commit()
        return self.get_user(user_id)

    # =========================================================
    # ACCESS
    # =========================================================

    def user_exists(self, user_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row is not None

    def is_admin(self, user_id: int) -> bool:
        return int(user_id) == ADMIN_ID

    def is_approved(self, user_id: int) -> bool:
        if self.is_admin(user_id):
            return True
        if self.is_premium(user_id):
            return True
        user = self.get_user(user_id)
        return bool(user and user.get("approved", 0))

    def can_access_bot(self, user_id: int) -> bool:
        if ACCESS_MODE == "open":
            return True
        return self.is_approved(user_id)

    # =========================================================
    # ROLE
    # =========================================================

    def get_role(self, user_id: int) -> str:
        user = self.get_user(user_id)
        if not user:
            return "blocked"
        return user.get("role", "tester")

    def is_premium(self, user_id: int) -> bool:
        if self.is_admin(user_id):
            return True
        return self.get_role(user_id) in ["pro", "admin"]

    # =========================================================
    # TRIAL
    # =========================================================

    def is_trial_valid(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        start = user.get("trial_start", 0)
        try:
            start = float(start)
        except (TypeError, ValueError):
            start = time.time()
            self.conn.execute(
                "UPDATE users SET trial_start = ? WHERE user_id = ?",
                (start, user_id)
            )
            self.conn.commit()
        return time.time() < start + (TRIAL_DAYS * 86400)

    def can_use_premium_feature(self, user_id: int) -> bool:
        return self.is_premium(user_id) or self.is_trial_valid(user_id)

    # =========================================================
    # TERMS
    # =========================================================

    def has_accepted_terms(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        return bool(user and user.get("terms_accepted", 0))

    def update_username(self, user_id: int, username: str):
        if username:
            self.conn.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
            self.conn.commit()

    def accept_terms(self, user_id: int):
        self.conn.execute(
            "UPDATE users SET terms_accepted = 1 WHERE user_id = ?",
            (user_id,)
        )
        self.conn.commit()

    # =========================================================
    # LIMITS
    # =========================================================

    def _get_today(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _get_usage(self, user_id: int) -> int:
        today = self._get_today()
        row = self.conn.execute(
            "SELECT count FROM usage WHERE user_id = ? AND date = ?",
            (user_id, today)
        ).fetchone()
        return row["count"] if row else 0

    def _set_usage(self, user_id: int, count: int):
        today = self._get_today()
        self.conn.execute(
            """
            INSERT INTO usage (user_id, date, count) VALUES (?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET count = excluded.count
            """,
            (user_id, today, count)
        )
        self.conn.commit()

    def check_limit(self, user_id: int) -> bool:
        if self.is_admin(user_id) or self.is_premium(user_id):
            return True
        used = self._get_usage(user_id)
        return used < FREE_DAILY_REQUESTS

    def increment_usage(self, user_id: int):
        if self.is_admin(user_id) or self.is_premium(user_id):
            return
        used = self._get_usage(user_id)
        self._set_usage(user_id, used + 1)

    def get_remaining_requests(self, user_id: int) -> int:
        if self.is_premium(user_id) or self.is_admin(user_id):
            return -1
        used = self._get_usage(user_id)
        return max(0, FREE_DAILY_REQUESTS - used)

    # =========================================================
    # WATCHLIST
    # =========================================================

    def get_watchlist(self, user_id: int) -> List[str]:
        rows = self.conn.execute(
            "SELECT symbol FROM watchlist WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        return [row["symbol"] for row in rows]

    def get_watchlist_limit(self, user_id: int) -> int:
        role = self.get_role(user_id)
        if role == "pro":
            return MAX_WATCHLIST_SYMBOLS_PRO
        if role == "tester":
            return MAX_WATCHLIST_SYMBOLS_TESTER
        return MAX_WATCHLIST_SYMBOLS_FREE

    def add_to_watchlist(self, user_id: int, symbol: str):
        current = self.get_watchlist(user_id)
        limit = self.get_watchlist_limit(user_id)
        if len(current) >= limit:
            return False, limit
        try:
            self.conn.execute(
                "INSERT INTO watchlist (user_id, symbol) VALUES (?, ?)",
                (user_id, symbol.upper())
            )
            self.conn.commit()
        except Exception:
            pass  # déjà présent
        return True, limit

    def remove_from_watchlist(self, user_id: int, symbol: str):
        self.conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND symbol = ?",
            (user_id, symbol.upper())
        )
        self.conn.commit()

    # =========================================================
    # SETTINGS
    # =========================================================

    def get_setting(self, user_id: int, key: str, default=None):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE user_id = ? AND key = ?",
            (user_id, key)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, user_id: int, key: str, value):
        self.conn.execute(
            """
            INSERT INTO settings (user_id, key, value) VALUES (?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value
            """,
            (user_id, key, str(value))
        )
        self.conn.commit()

    # =========================================================
    # PROMO
    # =========================================================

    def redeem_promo(self, user_id: int, code: str):
        promos = {"TRADERBURUNDI": {"days": 5}}
        code = code.upper()
        lang = self.get_setting(user_id, "lang", "en")
        if code not in promos:
            return False, get_text(lang, "redeem_invalid")
        user = self.get_user(user_id)
        if not user:
            return False, "User not found"
        new_trial = user.get("trial_start", time.time()) - promos[code]["days"] * 86400
        self.conn.execute(
            "UPDATE users SET trial_start = ? WHERE user_id = ?",
            (new_trial, user_id)
        )
        self.conn.commit()
        return True, get_text(lang, "redeem_success")

    # =========================================================
    # ADMIN: GET ALL USERS
    # =========================================================

    def get_all_users(self) -> List[int]:
        """Retourne la liste de tous les user_id."""
        rows = self.conn.execute("SELECT user_id FROM users").fetchall()
        return [row["user_id"] for row in rows]

    # =========================================================
    # ADMIN: CONFIRM PAYMENT
    # =========================================================

    def confirm_binance_payment(self, user_id: int) -> bool:
        """Passe un utilisateur en rôle 'pro' après paiement confirmé."""
        user = self.get_user(user_id)
        if not user:
            return False
        self.conn.execute(
            "UPDATE users SET role = 'pro' WHERE user_id = ?",
            (user_id,)
        )
        self.conn.commit()
        return True

    # =========================================================
    # ADMIN: APPROVE TESTER
    # =========================================================

    def approve_user(self, user_id: int) -> bool:
        """Approuve un utilisateur comme testeur."""
        user = self.get_user(user_id)
        if not user:
            return False
        self.conn.execute(
            "UPDATE users SET role = 'tester', approved = 1 WHERE user_id = ?",
            (user_id,)
        )
        self.conn.commit()
        return True

    # =========================================================
    # ADMIN: FIND USER BY MEMO
    # =========================================================

    def find_user_by_memo(self, memo: str) -> Optional[int]:
        """Retrouve un user_id à partir de son mémo de paiement Binance."""
        row = self.conn.execute(
            "SELECT user_id FROM users WHERE memo = ?",
            (memo,)
        ).fetchone()
        return row["user_id"] if row else None

    # =========================================================
    # ADMIN: DELETE USER
    # =========================================================

    def delete_user(self, user_id: int) -> bool:
        """Supprime un utilisateur et toutes ses données associées."""
        user = self.get_user(user_id)
        if not user:
            return False
        self.conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        self.conn.execute("DELETE FROM usage WHERE user_id = ?", (user_id,))
        self.conn.execute("DELETE FROM settings WHERE user_id = ?", (user_id,))
        self.conn.execute("DELETE FROM watchlist WHERE user_id = ?", (user_id,))
        self.conn.execute("DELETE FROM alerts WHERE user_id = ?", (user_id,))
        self.conn.execute("DELETE FROM signals WHERE user_id = ?", (user_id,))
        self.conn.execute("DELETE FROM paper_positions WHERE user_id = ?", (user_id,))
        self.conn.execute("DELETE FROM paper_capitals WHERE user_id = ?", (user_id,))
        self.conn.commit()
        return True
