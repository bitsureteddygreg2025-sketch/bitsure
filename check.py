import sys 
from database import get_db 
conn = get_db() 
cur = conn._conn.cursor() 
print("?? 9 SIGNAUX RESTANTS :") 
print("-" * 60) 
cur.execute("SELECT id, symbol, direction, entry_price, status, created_at, closed_at FROM signals ORDER BY created_at DESC") 
for row in cur.fetchall(): 
    created = row[5] 
    closed = row[6] if row[6] else "---" 
    print(f"  {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {created} | {closed}") 
print("-" * 60) 
conn.close() 
