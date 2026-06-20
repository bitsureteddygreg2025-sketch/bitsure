"""
API interne pour Teddy-web
Tourne sur le port 9000, lit la base SQLite du bot
"""

import os
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "bitsure.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/api/login")
def login():
    user_id = request.args.get("user_id", "").strip()
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE CAST(user_id AS TEXT)=?", (user_id,)).fetchone()
    if not row:
        return jsonify({"success": False, "error": "User not found"}), 404
    return jsonify({"success": True, "user_id": user_id, "username": row["username"] or f"@{user_id}"})


@app.route("/api/signals")
def signals():
    user_id = request.args.get("user_id", "").strip()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM signals WHERE CAST(user_id AS TEXT)=? AND status='pending' ORDER BY created_at DESC LIMIT 100",
        (user_id,)
    ).fetchall()
    return jsonify({"success": True, "count": len(rows), "items": [dict(r) for r in rows]})


@app.route("/api/history")
def history():
    user_id = request.args.get("user_id", "").strip()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM signals WHERE CAST(user_id AS TEXT)=? AND status IN ('win','loss') ORDER BY closed_at DESC LIMIT 100",
        (user_id,)
    ).fetchall()
    return jsonify({"success": True, "count": len(rows), "items": [dict(r) for r in rows]})


@app.route("/api/stats")
def stats():
    user_id = request.args.get("user_id", "").strip()
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM signals WHERE CAST(user_id AS TEXT)=? AND status IN ('win','loss')", (user_id,)).fetchone()[0]
    wins = conn.execute("SELECT COUNT(*) FROM signals WHERE CAST(user_id AS TEXT)=? AND status='win'", (user_id,)).fetchone()[0]
    return jsonify({"success": True, "total_trades": total, "wins": wins, "win_rate": round(wins/total*100, 2) if total else 0})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)