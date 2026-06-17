"""
Bitsure Teddy - Admin Handlers
Fonctions réservées à l'administrateur
"""

import logging
import requests
import io
import csv
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import ADMIN_ID
from data_fetcher import DataFetcher
from user_manager import UserManager
from alert_manager import AlertManager
from history_manager import HistoryManager
from i18n import get_text

logger = logging.getLogger(__name__)
user_mgr = UserManager.get_instance()
history_mgr = HistoryManager.get_instance()

def get_user_lang(update: Update) -> str:
    user_id = update.effective_user.id
    return user_mgr.get_setting(user_id, "lang", "en")

def check_limit(func):
    """Version simplifiée pour admin - l'admin passe toujours"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        return await func(update, context, *args, **kwargs)
    return wrapper

# =========================================================
# STATS
# =========================================================

@check_limit
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    lang = user_mgr.get_setting(update.effective_user.id, "lang", "en")
    
    # Statistiques globales
    total_row = user_mgr.conn.execute("SELECT COUNT(*) as total FROM users").fetchone()
    total = total_row["total"] if total_row else 0
    free_row = user_mgr.conn.execute("SELECT COUNT(*) as c FROM users WHERE role='tester'").fetchone()
    free = free_row["c"] if free_row else 0
    pro_row = user_mgr.conn.execute("SELECT COUNT(*) as c FROM users WHERE role='pro'").fetchone()
    pro = pro_row["c"] if pro_row else 0
    
    text = f"📊 *Bitsure Teddy Stats*\n👥 Utilisateurs : {total}\n🧪 Testeurs : {free}\n💎 PRO : {pro}\n\n"
    
    # Détail par utilisateur
    users = user_mgr.conn.execute("SELECT user_id, role, username FROM users ORDER BY role, user_id").fetchall()
    for u in users:
        uid = u["user_id"]
        username = u["username"] or f"ID:{uid}"
        role = u["role"]
        
        # Compter les requêtes du jour
        from datetime import datetime
        today = datetime.utcnow().strftime("%Y-%m-%d")
        usage_row = user_mgr.conn.execute("SELECT count FROM usage WHERE user_id=? AND date=?", (uid, today)).fetchone()
        used = usage_row["count"] if usage_row else 0
        
        # Compter les signaux
        sig_row = user_mgr.conn.execute("SELECT COUNT(*) as c FROM signals WHERE user_id=?", (uid,)).fetchone()
        sig_count = sig_row["c"] if sig_row else 0
        
        emoji = "💎" if role == "pro" else "🧪" if role == "tester" else "👤"
        text += f"{emoji} {uid} {username} | {role} | {used} req | {sig_count} signals\n"
    
    if len(text) > 4000:
        text = text[:4000] + "\n... (truncated)"
    
    await update.message.reply_text(text)

# =========================================================
# APPROUVER UN TESTEUR
# =========================================================

@check_limit
async def teddy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /teddy <user_id>")
        return
    uid = int(context.args[0])
    if user_mgr.confirm_binance_payment(uid):
        await update.message.reply_text(f"✅ Paiement confirmé pour {uid}")
        try:
            await context.bot.send_message(chat_id=uid, text="✅ Your PRO subscription has been activated! Use /menu to start trading.")
        except Exception as e:
            errors.append(str(e))
    elif user_mgr.approve_user(uid):
        await update.message.reply_text(f"✅ Utilisateur {uid} approuvé comme testeur")
        try:
            await context.bot.send_message(chat_id=uid, text="✅ Your access has been approved! Use /menu to start.")
        except Exception as e:
            errors.append(str(e))
    else:
        await update.message.reply_text(f"❌ Utilisateur {uid} introuvable")

# =========================================================
# BROADCAST
# =========================================================

@check_limit
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    lang = user_mgr.get_setting(update.effective_user.id, "lang", "en")
    if not context.args:
        await update.message.reply_text(get_text(lang, "broadcast_usage"))
        return
    user_text = " ".join(context.args)
    header = "📢 *Bitsure Teddy \u2022 Announcement*\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    message = header + user_text
    users = user_mgr.get_all_users()
    success = 0
    errors = []
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=message)
            success += 1
        except Exception as e:
            errors.append(str(e))
    result = f"Broadcast sent to {success}/{len(users)} users."
    if errors:
        result += f"\nErrors: {len(errors)}"
    await update.message.reply_text(result)

# =========================================================
# SWITCH API
# =========================================================

@check_limit
async def switchapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only.")
        return
    lang = user_mgr.get_setting(update.effective_user.id, "lang", "en")
    fetcher = DataFetcher.get_instance()
    current = fetcher.active_source or "none"
    if not context.args:
        await update.message.reply_text(
            f"🔄 Source actuelle : {current}\n"
            f"Usage : /switchapi twelve|fcs|real\n"
            f"Échecs : {fetcher.source_failures}"
        )
        return
    target = context.args[0].lower()
    if target not in ("twelve", "fcs", "real"):
        await update.message.reply_text("❌ twelve, fcs ou real")
        return
    if fetcher.ws:
        fetcher.ws.close()
    if target == "twelve":
        fetcher._start_twelve_ws()
    elif target == "fcs":
        fetcher._start_fcs_ws()
    elif target == "real":
        fetcher._start_real_ws()
    await update.message.reply_text(f"✅ Switch vers {target} effectué.")

# =========================================================
# FIND MEMO
# =========================================================

@check_limit
async def find_memo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /find_memo <memo>")
        return
    memo = context.args[0].upper()
    user_id = user_mgr.find_user_by_memo(memo)
    if user_id:
        await update.message.reply_text(f"✅ Mémo {memo} → User ID: {user_id}")
    else:
        await update.message.reply_text(f"❌ Aucun utilisateur trouvé pour le mémo {memo}")

# =========================================================
# CONFIRM PAYMENT
# =========================================================

@check_limit
async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    lang = user_mgr.get_setting(update.effective_user.id, "lang", "en")
    if not context.args:
        await update.message.reply_text(get_text(lang, "confirm_payment_usage"))
        return
    uid = int(context.args[0])
    if user_mgr.confirm_binance_payment(uid):
        await update.message.reply_text(get_text(lang, "confirm_payment_ok", user_id=uid))
        try:
            await context.bot.send_message(chat_id=uid, text="✅ Your PRO subscription has been activated! Use /menu to start trading.")
        except Exception as e:
            errors.append(str(e))
    else:
        await update.message.reply_text(get_text(lang, "confirm_payment_missing", user_id=uid))

# =========================================================
# REFRESH HISTORY
# =========================================================

@check_limit
# =========================================================
# EXPORT SIGNALS
# =========================================================

@check_limit
# =========================================================
# =========================================================
# CLEAN WAIT SIGNALS
# =========================================================

@check_limit
async def cleanwaits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    from database import get_db
    conn = get_db()
    cursor = conn.execute("DELETE FROM signals WHERE direction = 'WAIT'")
    conn.commit()
    count = cursor.rowcount
    await update.message.reply_text(f"{count} signaux WAIT supprimés")

# DB QUERY
# =========================================================

@check_limit
async def dbquery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /dbquery <SQL>")
        return
    sql = " ".join(context.args)
    try:
        from database import get_db
        conn = get_db()
        rows = conn.execute(sql).fetchall()
        if not rows:
            await update.message.reply_text("Requete OK, 0 resultats")
            return
        text = ""
        for r in rows[:20]:
            text += str(dict(r)) + "\n"
        if len(rows) > 20:
            text += f"\n... et {len(rows) - 20} de plus"
        await update.message.reply_text(text[:4000])
    except Exception as e:
        await update.message.reply_text(f"Erreur: {e}")

async def exportsignals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    lang = get_user_lang(update)
    signals = history_mgr.get_recent_signals(1000)
    if not signals:
        await update.message.reply_text("Aucun signal a exporter")
        return
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Symbole", "Direction", "Entree", "SL", "TP", "Score", "Statut", "PnL%", "Ouvert", "Ferme"])
    for s in signals:
        from datetime import datetime
        created = datetime.utcfromtimestamp(s['created_at']).strftime('%Y-%m-%d %H:%M') if s.get('created_at') else ''
        closed = datetime.utcfromtimestamp(s['closed_at']).strftime('%Y-%m-%d %H:%M') if s.get('closed_at') else ''
        writer.writerow([
            s.get('id', ''),
            s.get('symbol', ''),
            s.get('direction', ''),
            s.get('entry_price', ''),
            s.get('sl', ''),
            s.get('tp', ''),
            s.get('score', ''),
            s.get('status', ''),
            s.get('result_pct', ''),
            created,
            closed
        ])
    output.seek(0)
    await update.message.reply_document(
        document=output.getvalue().encode('utf-8'),
        filename='signals_export.csv',
        caption=f'{len(signals)} signaux exportes'
    )

async def refreshhistory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    lang = user_mgr.get_setting(update.effective_user.id, "lang", "en")
    await update.message.reply_text(get_text(lang, "refreshhistory_start"))
    from bot_handlers import check_signal_outcomes
    await check_signal_outcomes(context.bot)
    await update.message.reply_text(get_text(lang, "refreshhistory_done"))

# =========================================================
# CLEAR HISTORY
# =========================================================

@check_limit
async def clearhistory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    lang = user_mgr.get_setting(update.effective_user.id, "lang", "en")
    history_mgr.clear_all_signals()
    await update.message.reply_text(get_text(lang, "clearhistory_done"))

# =========================================================
# QUOTA
# =========================================================

@check_limit
# DELETE USER
# =========================================================

@check_limit

# =========================================================
# QUOTA
# =========================================================

@check_limit
async def deleteuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /deleteuser <user_id>")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID invalide")
        return
    if user_mgr.delete_user(uid):
        await update.message.reply_text(f"🗑️ Utilisateur {uid} supprimé avec toutes ses données")
    else:
        await update.message.reply_text(f"❌ Utilisateur {uid} introuvable")
