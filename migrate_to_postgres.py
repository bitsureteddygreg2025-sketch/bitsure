import os
import sqlite3
import sys

import psycopg2
from psycopg2.extras import DictCursor

BASE_DIR = os.path.dirname(__file__)
SQLITE_PATH = os.path.join(BASE_DIR, "data", "bitsure.db")

TABLES = {
    "users": {
        "columns": [
            "user_id", "role", "lang", "timeframe", "risk", "terms_accepted",
            "trial_start", "created_at", "approved", "memo", "username", "pin",
        ],
        "pk": ["user_id"],
    },
    "usage": {
        "columns": ["user_id", "date", "count"],
        "pk": ["user_id", "date"],
    },
    "settings": {
        "columns": ["user_id", "key", "value"],
        "pk": ["user_id", "key"],
    },
    "watchlist": {
        "columns": ["user_id", "symbol"],
        "pk": ["user_id", "symbol"],
    },
    "alerts": {
        "columns": ["id", "user_id", "symbol", "condition", "price", "triggered", "created_at", "triggered_at"],
        "pk": ["id"],
    },
    "signals": {
        "columns": [
            "id", "user_id", "symbol", "direction", "entry_price", "sl", "tp",
            "score", "status", "result_pct", "created_at", "closed_at",
        ],
        "pk": ["id"],
    },
    "paper_positions": {
        "columns": [
            "id", "user_id", "symbol", "entry_price", "sl", "tp", "qty",
            "current_price", "pnl_usdt", "pnl_pct", "status", "exit_reason",
            "opened_at", "closed_at", "peak_price",
        ],
        "pk": ["id"],
    },
    "paper_capitals": {
        "columns": ["user_id", "capital"],
        "pk": ["user_id"],
    },
}

CREATE_SCHEMA_SQL = [
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
        entry_price DOUBLE PRECISION,
        sl DOUBLE PRECISION,
        tp DOUBLE PRECISION,
        qty DOUBLE PRECISION,
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
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS pin TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS approved INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS memo TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT",
    "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS created_at DOUBLE PRECISION DEFAULT 0",
    "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS triggered_at DOUBLE PRECISION DEFAULT 0",
    "ALTER TABLE signals ADD COLUMN IF NOT EXISTS user_id BIGINT",
    "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS peak_price DOUBLE PRECISION",
]


def load_database_url():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    env_path = os.path.join(BASE_DIR, ".env")
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


def table_exists(sqlite_conn, table):
    row = sqlite_conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def sqlite_columns(sqlite_conn, table):
    return {row["name"] for row in sqlite_conn.execute(f"PRAGMA table_info({table})").fetchall()}


def build_upsert_sql(table, columns, pk_columns):
    names = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    conflict = ", ".join(pk_columns)
    update_columns = [column for column in columns if column not in pk_columns]
    if update_columns:
        updates = ", ".join(f"{column} = EXCLUDED.{column}" for column in update_columns)
        conflict_action = f"DO UPDATE SET {updates}"
    else:
        conflict_action = "DO NOTHING"
    return (
        f"INSERT INTO {table} ({names}) VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict}) {conflict_action}"
    )


def create_schema(pg_conn):
    with pg_conn.cursor() as cursor:
        for statement in CREATE_SCHEMA_SQL:
            cursor.execute(statement)
    pg_conn.commit()


def migrate_table(sqlite_conn, pg_conn, table, spec):
    if not table_exists(sqlite_conn, table):
        return 0, 0, "missing in SQLite"

    available_columns = sqlite_columns(sqlite_conn, table)
    rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
    sql = build_upsert_sql(table, spec["columns"], spec["pk"])

    with pg_conn.cursor() as cursor:
        for row in rows:
            values = [row[column] if column in available_columns else None for column in spec["columns"]]
            cursor.execute(sql, values)

    pg_conn.commit()
    return len(rows), verify_imported_count(pg_conn, table, spec["pk"], rows), "OK"


def verify_imported_count(pg_conn, table, pk_columns, rows):
    if not rows:
        return 0

    count = 0
    with pg_conn.cursor() as cursor:
        for row in rows:
            predicates = " AND ".join(f"{column} = %s" for column in pk_columns)
            values = [row[column] for column in pk_columns]
            cursor.execute(f"SELECT 1 FROM {table} WHERE {predicates}", values)
            if cursor.fetchone():
                count += 1
    return count


def reset_alert_sequence(pg_conn):
    with pg_conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('alerts', 'id'),
                COALESCE((SELECT MAX(id) FROM alerts), 1),
                (SELECT COUNT(*) FROM alerts) > 0
            )
            """
        )
    pg_conn.commit()


def main():
    if not os.path.exists(SQLITE_PATH):
        print(f"SQLite source not found: {SQLITE_PATH}", file=sys.stderr)
        return 1

    database_url = load_database_url()
    if not database_url:
        print("DATABASE_URL is required for PostgreSQL migration", file=sys.stderr)
        return 1

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg2.connect(database_url, cursor_factory=DictCursor)

    try:
        create_schema(pg_conn)
        report = []
        for table, spec in TABLES.items():
            source_count, imported_count, status = migrate_table(sqlite_conn, pg_conn, table, spec)
            if status == "OK" and source_count != imported_count:
                raise RuntimeError(
                    f"{table}: expected {source_count} imported rows, verified {imported_count}"
                )
            report.append((table, status, imported_count))
        reset_alert_sequence(pg_conn)
    except Exception:
        pg_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()

    for table, status, count in report:
        if status == "OK":
            print(f"{table} : OK ({count} lignes)")
        else:
            print(f"{table} : SKIPPED ({status})")
    print("Migration successful")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
