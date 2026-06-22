import os
import sqlite3
import psycopg2
from psycopg2.extras import DictCursor

BASE_DIR = os.path.dirname(__file__)
SQLITE_PATH = os.path.join(BASE_DIR, "data", "bitsure.db")


TABLES = {
    "users": ["user_id", "role", "lang", "timeframe", "risk", "terms_accepted",
              "trial_start", "created_at", "approved", "memo", "username", "pin"],

    "usage": ["user_id", "date", "count"],

    "settings": ["user_id", "key", "value"],

    "watchlist": ["user_id", "symbol"],

    "alerts": ["id", "user_id", "symbol", "condition", "price", "triggered",
               "created_at", "triggered_at"],

    "signals": ["id", "user_id", "symbol", "direction", "entry_price", "sl", "tp",
                "score", "status", "result_pct", "created_at", "closed_at"],

    "paper_positions": ["id", "user_id", "symbol", "entry_price", "sl", "tp", "qty",
                        "current_price", "pnl_usdt", "pnl_pct", "status", "exit_reason",
                        "opened_at", "closed_at", "peak_price"],

    "paper_capitals": ["user_id", "capital"]
}


CREATE_SQL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        role TEXT,
        lang TEXT,
        timeframe TEXT,
        risk TEXT,
        terms_accepted INTEGER,
        trial_start DOUBLE PRECISION,
        created_at DOUBLE PRECISION,
        approved INTEGER,
        memo TEXT,
        username TEXT,
        pin TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usage (
        user_id BIGINT,
        date TEXT,
        count INTEGER,
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
        id BIGINT PRIMARY KEY,
        user_id BIGINT,
        symbol TEXT,
        condition TEXT,
        price DOUBLE PRECISION,
        triggered INTEGER,
        created_at DOUBLE PRECISION,
        triggered_at DOUBLE PRECISION
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
        status TEXT,
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
        status TEXT,
        exit_reason TEXT,
        opened_at DOUBLE PRECISION,
        closed_at DOUBLE PRECISION,
        peak_price DOUBLE PRECISION
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_capitals (
        user_id BIGINT PRIMARY KEY,
        capital DOUBLE PRECISION
    )
    """
]


def load_db():
    db = os.getenv("DATABASE_URL")
    if not db:
        raise RuntimeError("DATABASE_URL manquant")
    return db


def create_tables(pg):
    print("📦 Création des tables...")
    cur = pg.cursor()
    for i, sql in enumerate(CREATE_SQL):
        print(f"  → Table step {i+1}")
        cur.execute(sql)
    pg.commit()
    print("✅ Tables OK")


def migrate_table(sqlite_conn, pg_conn, table, columns):
    print(f"\n🚀 Migration table: {table}")

    cur_sqlite = sqlite_conn.cursor()
    cur_sqlite.execute(f"SELECT * FROM {table}")
    rows = cur_sqlite.fetchall()

    print(f"  📊 {len(rows)} lignes trouvées")

    placeholders = ",".join(["%s"] * len(columns))
    cols = ",".join(columns)

    sql = f"""
        INSERT INTO {table} ({cols})
        VALUES ({placeholders})
        ON CONFLICT DO NOTHING
    """

    cur_pg = pg_conn.cursor()

    inserted = 0

    for idx, row in enumerate(rows):
        values = []
        for c in columns:
            try:
                values.append(row[c])
            except:
                values.append(None)

        cur_pg.execute(sql, values)
        inserted += 1

        if idx % 500 == 0:
            print(f"   ... {idx}/{len(rows)}")

    pg_conn.commit()
    print(f"✅ {table} terminé ({inserted} lignes)")
    return inserted


def main():
    print("=== START MIGRATION ===")

    if not os.path.exists(SQLITE_PATH):
        raise RuntimeError(f"SQLite introuvable: {SQLITE_PATH}")

    print("📁 SQLite OK")

    db_url = load_db()
    print("🔗 DATABASE_URL OK")

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    pg_conn = psycopg2.connect(db_url, cursor_factory=DictCursor)

    try:
        create_tables(pg_conn)

        total = 0

        for table, cols in TABLES.items():
            total += migrate_table(sqlite_conn, pg_conn, table, cols)

        print("\n🎉 MIGRATION TERMINÉE")
        print(f"📦 Total lignes migrées: {total}")

    except Exception as e:
        print("❌ ERREUR:", str(e))
        pg_conn.rollback()
        raise

    finally:
        sqlite_conn.close()
        pg_conn.close()
        print("🔒 Connexions fermées")


if __name__ == "__main__":
    main()