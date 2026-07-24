from database import get_db

conn = get_db()
cur = conn._conn.cursor()

cur.execute("""
    SELECT column_name, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'signals'
    AND column_name = 'user_id';
""")

print(cur.fetchall())

cur.close()
conn.close()