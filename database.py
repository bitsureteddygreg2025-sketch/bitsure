import atexit
import os
import threading

import psycopg2
from psycopg2.extras import DictCursor

_conn = None
_lock = threading.RLock()


def _load_database_url():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return None

    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "DATABASE_URL":
                return value.strip().strip('"').strip("'")
    return None


class PostgresConnection:
    """Small compatibility wrapper for the existing manager classes."""

    def __init__(self, database_url):
        self._conn = psycopg2.connect(database_url, cursor_factory=DictCursor)
        self._conn.autocommit = False

    def execute(self, sql, params=None):
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql, params or ())
            return cursor
        except Exception:
            cursor.close()
            self.rollback()
            raise

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_db():
    """Return a persistent PostgreSQL connection backed by DATABASE_URL."""
    global _conn
    with _lock:
        if _conn is None:
            database_url = _load_database_url()
            if not database_url:
                raise RuntimeError("DATABASE_URL is required for PostgreSQL access")
            _conn = PostgresConnection(database_url)
            _ensure_schema(_conn)
        return _conn


def close_db():
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def _ensure_schema(conn):
    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            role TEXT DEFAULT 'tester',
            lang TEXT DEFAULT 'en',
            timeframe TEXT DEFAULT '1h',
            risk TEXT DEFAULT 'medium',
            terms_accepted INTEGER DEFAULT 0,
            trial_start DOUBLE PRECISION DEFAULT 0,
            created_at DOUBLE PRECISION DEFAULT 0,
            approved INTEGER DEFAULT 0,
            memo TEXT,
            username TEXT,
            pin TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS usage (
            user_id BIGINT,
            date TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS settings (
            user_id BIGINT,
            key TEXT,
            value TEXT,
            PRIMARY KEY (user_id, key)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS watchlist (
            user_id BIGINT,
            symbol TEXT,
            PRIMARY KEY (user_id, symbol)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            symbol TEXT,
            condition TEXT,
            price DOUBLE PRECISION,
            triggered INTEGER DEFAULT 0,
            created_at DOUBLE PRECISION DEFAULT 0,
            triggered_at DOUBLE PRECISION DEFAULT 0
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS signals (
            id TEXT PRIMARY KEY,
            user_id BIGINT,
            symbol TEXT,
            direction TEXT,
            entry_price DOUBLE PRECISION,
            sl DOUBLE PRECISION,
            tp DOUBLE PRECISION,
            score INTEGER,
            status TEXT DEFAULT 'pending',
            result_pct DOUBLE PRECISION,
            created_at DOUBLE PRECISION,
            closed_at DOUBLE PRECISION
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS paper_positions (
            id TEXT PRIMARY KEY,
            user_id BIGINT,
            symbol TEXT,
            side TEXT DEFAULT 'BUY',
            entry_price DOUBLE PRECISION,
            exit_price DOUBLE PRECISION,
            sl DOUBLE PRECISION,
            tp DOUBLE PRECISION,
            qty DOUBLE PRECISION,
            leverage DOUBLE PRECISION DEFAULT 1,
            fees_total DOUBLE PRECISION DEFAULT 0,
            slippage DOUBLE PRECISION DEFAULT 0,
            capital_before DOUBLE PRECISION,
            capital_after DOUBLE PRECISION,
            current_price DOUBLE PRECISION,
            pnl_usdt DOUBLE PRECISION,
            pnl_pct DOUBLE PRECISION,
            status TEXT DEFAULT 'open',
            exit_reason TEXT,
            opened_at DOUBLE PRECISION,
            closed_at DOUBLE PRECISION,
            peak_price DOUBLE PRECISION
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS paper_capitals (
            user_id BIGINT PRIMARY KEY,
            capital DOUBLE PRECISION DEFAULT 10000
        )
        """,
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS approved INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS memo TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS pin TEXT",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS created_at DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS triggered_at DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE signals ADD COLUMN IF NOT EXISTS user_id BIGINT",
        "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS peak_price DOUBLE PRECISION",
        # Nouvelles colonnes paper trading v2
        "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS side TEXT DEFAULT 'BUY'",
        "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS exit_price DOUBLE PRECISION",
        "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS leverage DOUBLE PRECISION DEFAULT 1",
        "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS fees_total DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS slippage DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS capital_before DOUBLE PRECISION",
        "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS capital_after DOUBLE PRECISION",
    ]
    for statement in statements:
        conn.execute(statement)
    conn.commit()


atexit.register(close_db)
