import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "bitsure.db")

_conn = None

def get_db():
    """Retourne une connexion persistante, thread-safe."""
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _ensure_schema(_conn)
    return _conn

def _ensure_schema(conn):
    """Crée les tables et ajoute les colonnes manquantes si nécessaire."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT 'tester',
            lang TEXT DEFAULT 'en',
            timeframe TEXT DEFAULT '1h',
            risk TEXT DEFAULT 'medium',
            terms_accepted INTEGER DEFAULT 0,
            trial_start REAL DEFAULT 0,
            created_at REAL DEFAULT 0,
            approved INTEGER DEFAULT 0,
            memo TEXT,
                username TEXT
        );

        CREATE TABLE IF NOT EXISTS usage (
            user_id INTEGER,
            date TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, date)
        );

        CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER,
            key TEXT,
            value TEXT,
            PRIMARY KEY (user_id, key)
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            user_id INTEGER,
            symbol TEXT,
            PRIMARY KEY (user_id, symbol)
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            symbol TEXT,
            condition TEXT,
            price REAL,
            triggered INTEGER DEFAULT 0,
            created_at REAL DEFAULT 0,
            triggered_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS signals (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            sl REAL,
            tp REAL,
            score INTEGER,
            status TEXT DEFAULT 'pending',
            result_pct REAL,
            created_at REAL,
            closed_at REAL
        );

        CREATE TABLE IF NOT EXISTS paper_positions (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            symbol TEXT,
            entry_price REAL,
            sl REAL,
            tp REAL,
            qty REAL,
            current_price REAL,
            pnl_usdt REAL,
            pnl_pct REAL,
            status TEXT DEFAULT 'open',
            exit_reason TEXT,
            opened_at REAL,
            closed_at REAL,
            peak_price REAL
        );

        CREATE TABLE IF NOT EXISTS paper_capitals (
            user_id INTEGER PRIMARY KEY,
            capital REAL DEFAULT 10000
        );
    """)

    # Migrations ponctuelles (colonnes manquantes sur bases existantes)
    _add_column_if_missing(conn, "users", "approved", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "users", "memo", "TEXT")
    _add_column_if_missing(conn, "users", "username", "TEXT")
    _add_column_if_missing(conn, "alerts", "created_at", "REAL DEFAULT 0")
    _add_column_if_missing(conn, "alerts", "triggered_at", "REAL DEFAULT 0")

    conn.commit()

def _add_column_if_missing(conn, table, column, definition):
    """Ajoute une colonne si elle n'existe pas déjà."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except sqlite3.OperationalError:
        pass  # colonne déjà présente
