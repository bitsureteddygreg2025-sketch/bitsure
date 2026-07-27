"""Code de sécurité utilisateur pour les actions de trading sensibles."""

import hashlib
import hmac
import os
import re
import time

from database import get_connection

CODE_RE = re.compile(r"^\d{4}[A-Z]{2}$")
MAX_ATTEMPTS = int(os.getenv("SECURITY_CODE_MAX_ATTEMPTS", "5"))
LOCK_SECONDS = int(os.getenv("SECURITY_CODE_LOCK_SECONDS", "900"))


def _hash_code(code: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", code.encode(), salt.encode(), 120_000).hex()
    return salt, digest


def _row(user_id: int):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT code_hash, salt, failed_attempts, locked_until FROM user_security_codes WHERE user_id = %s", (user_id,))
            return cur.fetchone()
    finally:
        conn.close()


def has_security_code(user_id: int) -> bool:
    return _row(user_id) is not None


def set_initial_code(user_id: int, code: str) -> None:
    if not CODE_RE.match(code or ""):
        raise ValueError("Format invalide: 4 chiffres puis 2 lettres majuscules (ex: 4827BZ).")
    salt, digest = _hash_code(code)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_security_codes (user_id, code_hash, salt, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id, digest, salt, time.time()),
            )
        conn.commit()
    finally:
        conn.close()


def verify_code(user_id: int, code: str) -> bool:
    row = _row(user_id)
    now = time.time()
    if not row:
        return False
    code_hash, salt, failed, locked_until = row
    if locked_until and now < float(locked_until):
        return False
    _, digest = _hash_code(code or "", salt)
    ok = hmac.compare_digest(digest, code_hash)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if ok:
                cur.execute("UPDATE user_security_codes SET failed_attempts = 0, locked_until = NULL WHERE user_id = %s", (user_id,))
            else:
                failed = int(failed or 0) + 1
                lock = now + LOCK_SECONDS if failed >= MAX_ATTEMPTS else None
                cur.execute("UPDATE user_security_codes SET failed_attempts = %s, locked_until = %s WHERE user_id = %s", (failed, lock, user_id))
        conn.commit()
    finally:
        conn.close()
    return ok


def change_code(user_id: int, old_code: str, new_code: str) -> None:
    if not verify_code(user_id, old_code):
        raise ValueError("Ancien code invalide ou compte temporairement verrouillé.")
    if not CODE_RE.match(new_code or ""):
        raise ValueError("Format invalide: 4 chiffres puis 2 lettres majuscules.")
    salt, digest = _hash_code(new_code)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE user_security_codes SET code_hash = %s, salt = %s, updated_at = %s WHERE user_id = %s", (digest, salt, time.time(), user_id))
        conn.commit()
    finally:
        conn.close()
