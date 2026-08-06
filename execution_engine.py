"""
execution_engine.py
---------------------
Cœur de la logique d'exécution des signaux : lit les signaux "pending"/"active",
filtre par score/config, puis :
  - mode automatique : ouvre directement la position
  - mode semi-automatique : envoie un message Telegram avec boutons de confirmation

Ce module est appelé par un job APScheduler (voir main_integration.py) et par
les callbacks des boutons "✅ Ouvrir" / "❌ Refuser".
"""

import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import get_connection
from trading_config import get_config, TradingConfig
from risk_manager import check_can_open_position, calculate_position_size
from binance_manager import (
    open_position, get_price, get_tradable_symbols, get_klines_dataframe,
    make_client_order_id, BinanceClientError, ORDER_CONTEXT_AUTOTRADE,
    ORDER_CONTEXT_MANUAL_AUTHENTICATED,
)
from history_manager import HistoryManager
from signal_engine import SignalEngine
from trading_logger import get_trading_logger, log_trade_opened, log_error
from trading_safety import (
    SafetyError,
    assert_trading_allowed,
    mark_signal_refused,
    reserve_signal_for_execution,
    validate_signal_freshness,
)

logger = get_trading_logger("execution_engine")


def fetch_pending_signals():
    """Récupère les signaux non encore traités (statuts 'pending' ou 'active')."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, symbol, direction, entry_price, sl, tp, score,
                       timeframe, signal_type, created_at
                FROM signals
                WHERE status IN ('pending', 'active')
                  AND direction IN ('BUY', 'SELL')
                ORDER BY id ASC
                """
            )
            cols = [
                "id", "user_id", "symbol", "direction", "entry_price", "sl", "tp", "score",
                "timeframe", "signal_type", "created_at",
            ]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def mark_signal_status(signal_id: str, status: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE signals SET status = %s WHERE id = %s", (status, signal_id))
        conn.commit()
    finally:
        conn.close()



def validate_signal_for_execution(user_id: int, signal: dict, config: TradingConfig) -> tuple[bool, str | None]:
    """Applique les garde-fous juste avant toute ouverture de position."""
    try:
        require_auto = signal.get("status") in ("pending", "active") or signal.get("signal_type") == "market_scan"
        assert_trading_allowed(config, require_auto_trade=require_auto)
        if signal.get("id") and not str(signal["id"]).startswith("manual-"):
            validate_signal_freshness(signal)
    except SafetyError as e:
        return False, str(e)

    if int(signal["user_id"]) != int(user_id):
        return False, "Ce signal ne t'appartient pas."

    if config.market_type == "spot" and signal["direction"] == "SELL":
        return False, "SELL non supporté en mode Spot standard."

    if signal.get("score") is not None and signal["score"] < config.min_score:
        return False, f"Score insuffisant ({signal['score']} < {config.min_score})."

    if signal.get("entry_price") is not None:
        entry = signal["entry_price"]
        sl = signal.get("sl")
        tp = signal.get("tp")
        if sl is None or tp is None:
            return False, "SL/TP manquants."
        if signal["direction"] == "BUY" and not (sl < entry < tp):
            return False, "SL/TP incohérents avec un signal BUY."
        if signal["direction"] == "SELL" and not (tp < entry < sl):
            return False, "SL/TP incohérents avec un signal SELL."

    risk_check = check_can_open_position(user_id, config, signal["symbol"], signal.get("direction"))
    if not risk_check.allowed:
        return False, risk_check.reason or "Règle de risque non respectée."

    return True, None

def insert_trade_row(**fields) -> int:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trades (signal_id, user_id, symbol, direction, entry_price,
                    sl_price, tp_price, quantity, leverage, market_type, status,
                    opened_at, binance_order_id, binance_client_order_id,
                    sl_order_id, tp_order_id, error_message)
                VALUES (%(signal_id)s, %(user_id)s, %(symbol)s, %(direction)s, %(entry_price)s,
                    %(sl_price)s, %(tp_price)s, %(quantity)s, %(leverage)s, %(market_type)s,
                    %(status)s, %(opened_at)s, %(binance_order_id)s, %(binance_client_order_id)s,
                    %(sl_order_id)s, %(tp_order_id)s, %(error_message)s)
                RETURNING id
                """,
                fields,
            )
            trade_id = cur.fetchone()[0]
        conn.commit()
        return trade_id
    finally:
        conn.close()


def _default_trade_fields(signal: dict, config: TradingConfig) -> dict:
    return {
        "signal_id": signal["id"],
        "user_id": signal["user_id"],
        "symbol": signal["symbol"],
        "direction": signal["direction"],
        "entry_price": signal["entry_price"],
        "sl_price": signal["sl"],
        "tp_price": signal["tp"],
        "quantity": None,
        "leverage": config.leverage,
        "market_type": config.market_type,
        "status": "error",
        "opened_at": time.time(),
        "binance_order_id": None,
        "binance_client_order_id": None,
        "sl_order_id": None,
        "tp_order_id": None,
        "error_message": None,
    }


def execute_signal(signal: dict, config: TradingConfig, execution_context: str | None = None) -> dict:
    """
    Exécute réellement l'ordre sur Binance pour un signal donné, en calculant
    la taille de position, puis enregistre le trade en base.
    Retourne le dict de la ligne insérée (utile pour notifier l'utilisateur).
    """
    if not execution_context:
        if str(signal.get("id", "")).startswith("manual-") or signal.get("status") == "awaiting_confirmation":
            execution_context = ORDER_CONTEXT_MANUAL_AUTHENTICATED
        else:
            execution_context = ORDER_CONTEXT_AUTOTRADE

    user_id = signal["user_id"]
    if signal.get("id") and not str(signal["id"]).startswith("manual-"):
        try:
            allowed_statuses = ("awaiting_confirmation",) if signal.get("status") == "awaiting_confirmation" else ("pending", "active")
            signal = reserve_signal_for_execution(signal["id"], user_id, allowed_statuses)
            allowed, reason = validate_signal_for_execution(user_id, signal, config)
            if not allowed:
                mark_signal_refused(signal["id"], reason or "Validation refusée")
                raise SafetyError(reason or "Validation refusée")
        except SafetyError as e:
            fields = _default_trade_fields(signal, config)
            fields["error_message"] = str(e)
            fields["status"] = "skipped"
            return fields

    symbol = signal["symbol"]
    direction = signal["direction"]
    fields = _default_trade_fields(signal, config)

    try:
        entry_price = signal["entry_price"] or get_price(user_id, symbol, config.market_type)
        quantity = calculate_position_size(
            user_id, config, entry_price, signal["sl"], config.market_type
        )

        result = open_position(
            user_id=user_id,
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            sl_price=signal["sl"],
            tp_price=signal["tp"],
            market_type=config.market_type,
            leverage=config.leverage,
            client_order_id=make_client_order_id("sig", signal["id"]),
            execution_context=execution_context,
        )

        fields.update({
            "status": "open",
            "quantity": result["quantity"],
            "binance_order_id": str(result.get("order_id")),
            "binance_client_order_id": result.get("client_order_id"),
            "sl_order_id": str(result.get("sl_order_id")) if result.get("sl_order_id") else None,
            "tp_order_id": str(result.get("tp_order_id")) if result.get("tp_order_id") else None,
        })
        log_trade_opened(logger, user_id, symbol, direction, result["quantity"], entry_price)
        mark_signal_status(signal["id"], "executed")

    except (BinanceClientError, ValueError) as e:
        fields["error_message"] = str(e)
        log_error(logger, user_id, "execute_signal", str(e))
        mark_signal_status(signal["id"], "error")

    trade_id = insert_trade_row(**fields)
    fields["id"] = trade_id
    return fields


async def process_signal_for_user(context: ContextTypes.DEFAULT_TYPE, signal: dict):
    """Point d'entrée appelé par le job planifié pour chaque signal en attente."""
    user_id = signal["user_id"]
    config = get_config(user_id)

    allowed, reason = validate_signal_for_execution(user_id, signal, config)
    if not allowed:
        mark_signal_refused(signal["id"], reason or "Validation refusée")
        return

    if config.auto_trade:
        trade = execute_signal(signal, config)
        await _notify_trade_result(context, user_id, trade)
    else:
        await _send_confirmation_prompt(context, signal, config)


async def _notify_trade_result(context: ContextTypes.DEFAULT_TYPE, user_id: int, trade: dict):
    if trade["status"] == "open":
        text = (
            f"✅ *Position ouverte automatiquement*\n\n"
            f"Symbole : `{trade['symbol']}`\n"
            f"Direction : {trade['direction']}\n"
            f"Quantité : {trade['quantity']}\n"
            f"SL : {trade['sl_price']}  |  TP : {trade['tp_price']}"
        )
    else:
        text = (
            f"⚠️ *Échec d'ouverture de position*\n\n"
            f"Symbole : `{trade['symbol']}`\n"
            f"Erreur : {trade.get('error_message', 'inconnue')}"
        )
    await context.bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")


async def _send_confirmation_prompt(context: ContextTypes.DEFAULT_TYPE, signal: dict, config: TradingConfig):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Ouvrir", callback_data=f"trading_open_{signal['id']}"),
            InlineKeyboardButton("❌ Refuser", callback_data=f"trading_reject_{signal['id']}"),
        ],
        [InlineKeyboardButton("⚙️ Modifier SL/TP", callback_data=f"trading_edit_{signal['id']}")],
    ])
    text = (
        f"📡 *Nouveau signal détecté*\n\n"
        f"Symbole : `{signal['symbol']}`\n"
        f"Direction : {signal['direction']}\n"
        f"Prix d'entrée : {signal['entry_price']}\n"
        f"SL : {signal['sl']}  |  TP : {signal['tp']}\n"
        f"Score : {signal['score']}\n\n"
        f"Que veux-tu faire ?"
    )
    await context.bot.send_message(
        chat_id=signal["user_id"], text=text, reply_markup=keyboard, parse_mode="Markdown"
    )
    mark_signal_status(signal["id"], "awaiting_confirmation")


async def scheduled_signal_scan(context: ContextTypes.DEFAULT_TYPE):
    """Job APScheduler : à enregistrer toutes les 15-30s dans main.py."""
    for signal in fetch_pending_signals():
        try:
            await process_signal_for_user(context, signal)
        except Exception as e:
            log_error(logger, signal.get("user_id"), "scheduled_signal_scan", str(e))



def get_configured_analysis_intervals() -> list[int]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT analysis_interval_minutes
                FROM trading_config
                WHERE (auto_trade = TRUE OR periodic_analysis_enabled = TRUE)
                  AND analysis_interval_minutes IS NOT NULL
                  AND analysis_interval_minutes > 0
                """
            )
            intervals = {int(row[0]) for row in cur.fetchall()}
    finally:
        conn.close()

    intervals.update({5, 10})
    return sorted(intervals)


def _get_auto_trade_user_ids(interval_minutes: int) -> list[int]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id
                FROM trading_config
                WHERE (auto_trade = TRUE OR periodic_analysis_enabled = TRUE)
                  AND analysis_interval_minutes = %s
                """,
                (interval_minutes,),
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def _format_market_scan_report(
    config: TradingConfig,
    scanned: int,
    saved: list[tuple[str, dict, str]],
    rejected_by_risk: int,
    errors: int,
    rejected_spot_sell: int = 0,
) -> str:
    lines = [
        "📊 *Rapport analyse marché Binance*",
        f"Marché : `{config.market_type}` | TF : `{config.analysis_timeframe}` | Style : `{config.trading_style}`",
        f"Symboles analysés : {scanned}",
        f"Signaux actionnables : {len(saved)}",
        f"Refus risque/config : {rejected_by_risk}",
        f"Erreurs données/API : {errors}",
    ]
    if rejected_spot_sell:
        lines.append(f"SELL ignorés (spot) : {rejected_spot_sell}")
    if saved:
        lines.append("")
        lines.append("*Top signaux sauvegardés*")
        for symbol, result, signal_id in saved[:10]:
            lines.append(
                f"`{symbol}` {result['signal']} score {result['teddy_score']} "
                f"RR {result.get('rr_ratio') or 'N/A'} ID `{signal_id}`"
            )
    else:
        lines.append("")
        lines.append("Aucune position ouvrable sur ce cycle.")
    return "\n".join(lines)


async def scheduled_market_analysis(context: ContextTypes.DEFAULT_TYPE, interval_minutes: int):
    """
    Analyse tous les symboles tradables Binance pour les utilisateurs AutoTrade
    et Analyse Périodique configurés sur l'intervalle demandé.
    Affiche les résultats détaillés dans le terminal et envoie le rapport Telegram.
    """
    history_mgr = HistoryManager.get_instance()
    user_ids = _get_auto_trade_user_ids(interval_minutes)
    if not user_ids:
        return

    logger.info(f"=== [ ANALYSE PERIODIQUE ({interval_minutes}m) ] === Démarrage pour {len(user_ids)} utilisateur(s)")

    for user_id in user_ids:
        config = get_config(user_id)
        try:
            symbols = get_tradable_symbols(config.market_type)
        except Exception as e:
            log_error(logger, user_id, "scheduled_market_analysis.symbols", str(e))
            continue

        if config.symbol_whitelist:
            symbols = [s for s in symbols if s in config.symbol_whitelist]
        if config.symbol_blacklist:
            symbols = [s for s in symbols if s not in config.symbol_blacklist]

        scanned = 0
        rejected_by_risk = 0
        errors = 0
        rejected_spot_sell = 0
        saved: list[tuple[str, dict, str]] = []

        for symbol in symbols:
            try:
                df = get_klines_dataframe(
                    symbol,
                    config.analysis_timeframe,
                    market_type=config.market_type,
                    limit=1000,  # aligné sur DataFetcher pour des indicateurs identiques
                )
                if df is None or df.empty:
                    errors += 1
                    continue

                scanned += 1
                result = SignalEngine.analyze(
                    df,
                    "fr",
                    symbol=symbol,
                    style=config.trading_style,
                )

                price = float(result["indicators"]["price"])
                rsi = result["indicators"].get("rsi", "N/A")
                macd = result["indicators"].get("macd", "N/A")
                score = result.get("teddy_score", 0)
                sig = result.get("signal", "WAIT")

                # Affichage dans le terminal
                logger.info(f"[{symbol}] Prix: {price:.4f} | RSI: {rsi} | MACD: {macd} | Score: {score} | Signal: {sig}")

                if sig not in ("BUY", "SELL"):
                    continue

                if score < config.min_score:
                    rejected_by_risk += 1
                    continue

                if config.market_type == "spot" and sig == "SELL":
                    # Binance Spot standard ne supporte pas le short : inutile de
                    # sauvegarder un signal qui ne pourra jamais être exécuté.
                    rejected_spot_sell += 1
                    continue

                risk_check = check_can_open_position(user_id, config, symbol, sig)
                if not risk_check.allowed:
                    rejected_by_risk += 1
                    continue

                signal_id = history_mgr.add_signal(
                    symbol=symbol,
                    direction=sig,
                    price=price,
                    timeframe=config.analysis_timeframe,
                    signal_type="market_scan",
                    score=score,
                    sl=result.get("sl"),
                    tp=result.get("tp"),
                    user_id=user_id,
                    validation_status=result.get("validation_status", "VALIDATED"),
                    validation_reason=result.get("reason"),
                    rejection_reason=result.get("rejection_reason"),
                    rr_ratio=result.get("rr_ratio"),
                    asset_class=result.get("asset_class"),
                    params_used={
                        **(result.get("params_used") or {}),
                        "market_type": config.market_type,
                        "analysis_interval_minutes": interval_minutes,
                    },
                )
                if signal_id:
                    saved.append((symbol, result, signal_id))
            except Exception as e:
                errors += 1
                log_error(logger, user_id, f"scheduled_market_analysis.{symbol}", str(e))

        report = _format_market_scan_report(config, scanned, saved, rejected_by_risk, errors, rejected_spot_sell)
        logger.info(f"--- Rapport final User {user_id} ---\n{report}")
        try:
            if context and hasattr(context, "bot"):
                await context.bot.send_message(chat_id=user_id, text=report, parse_mode="Markdown")
        except Exception as e:
            log_error(logger, user_id, "scheduled_market_analysis.report", str(e))
