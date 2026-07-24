"""
i18n_trading.py
------------------
Traductions des textes du module AutoTrade, à fusionner dans ton i18n.py
existant (par exemple en important TRADING_STRINGS et en l'ajoutant au
dictionnaire principal des traductions).
"""

TRADING_STRINGS = {
    "fr": {
        "no_api_keys": (
            "🔑 Tu n'as pas encore configuré tes clés API Binance.\n"
            "Utilise /setapikeys <api_key> <api_secret> pour les ajouter."
        ),
        "keys_saved_ok": "✅ Clés API validées et enregistrées.",
        "keys_saved_fail": "⚠️ Clés enregistrées mais la connexion a échoué : {error}",
        "autotrade_on": "Mode automatique activé ✅",
        "autotrade_off": "Mode automatique désactivé ❌",
        "no_open_positions": "Aucune position ouverte actuellement.",
        "position_closed": "Position `{symbol}` fermée. PnL : {pnl:.2f} USDT ({pnl_pct:.2f}%)",
        "position_opened_auto": "✅ Position ouverte automatiquement : {symbol} {direction}",
        "position_open_failed": "⚠️ Échec d'ouverture de position : {error}",
        "signal_prompt_title": "📡 Nouveau signal détecté",
        "signal_rejected": "❌ Signal refusé.",
        "emergency_stop_running": "🛑 Fermeture de toutes les positions en cours...",
        "emergency_stop_done": "✅ {count} position(s) fermée(s). Mode automatique désactivé.",
        "max_positions_reached": "Nombre max de positions atteint ({max_positions}).",
        "daily_loss_limit_reached": (
            "Perte quotidienne max atteinte ({max_loss}%). Trading suspendu jusqu'à demain."
        ),
        "symbol_blacklisted": "{symbol} est dans ta blacklist.",
        "symbol_not_whitelisted": "{symbol} n'est pas dans ta whitelist.",
        "cooldown_active": "Cooldown actif, réessaie dans {seconds}s.",
    },
    "en": {
        "no_api_keys": (
            "🔑 You haven't set up your Binance API keys yet.\n"
            "Use /setapikeys <api_key> <api_secret> to add them."
        ),
        "keys_saved_ok": "✅ API keys validated and saved.",
        "keys_saved_fail": "⚠️ Keys saved but connection failed: {error}",
        "autotrade_on": "Automatic mode enabled ✅",
        "autotrade_off": "Automatic mode disabled ❌",
        "no_open_positions": "No open positions right now.",
        "position_closed": "Position `{symbol}` closed. PnL: {pnl:.2f} USDT ({pnl_pct:.2f}%)",
        "position_opened_auto": "✅ Position opened automatically: {symbol} {direction}",
        "position_open_failed": "⚠️ Failed to open position: {error}",
        "signal_prompt_title": "📡 New signal detected",
        "signal_rejected": "❌ Signal rejected.",
        "emergency_stop_running": "🛑 Closing all open positions...",
        "emergency_stop_done": "✅ {count} position(s) closed. Automatic mode disabled.",
        "max_positions_reached": "Max number of positions reached ({max_positions}).",
        "daily_loss_limit_reached": (
            "Max daily loss reached ({max_loss}%). Trading paused until tomorrow."
        ),
        "symbol_blacklisted": "{symbol} is on your blacklist.",
        "symbol_not_whitelisted": "{symbol} is not on your whitelist.",
        "cooldown_active": "Cooldown active, try again in {seconds}s.",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    """Petit helper : t('fr', 'autotrade_on') ou t('en', 'position_closed', symbol='BTCUSDT', pnl=12.3, pnl_pct=1.2)"""
    strings = TRADING_STRINGS.get(lang, TRADING_STRINGS["en"])
    template = strings.get(key, key)
    return template.format(**kwargs) if kwargs else template
