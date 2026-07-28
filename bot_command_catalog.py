"""Central catalogue for Telegram /help command descriptions."""

USER_COMMAND_CATEGORIES = [
    ("🚀 Général", [
        ("/start", "Démarrer le bot et afficher l'état du compte"),
        ("/help", "Afficher cette aide"),
        ("/menu", "Ouvrir le menu interactif"),
        ("/myid", "Afficher ton identifiant Telegram"),
        ("/support", "Contacter le support"),
        ("/usage", "Voir l'utilisation et les quotas"),
        ("/upgrade", "Voir les offres d'abonnement"),
        ("/pay_binance", "Instructions de paiement Binance/USDC"),
        ("/historique", "Historique d'utilisation du bot"),
    ]),
    ("📊 Analyse marché", [
        ("/analyse <symbole>", "Analyse complète d'un actif"),
        ("/price <symbole>", "Prix actuel"),
        ("/trend <symbole>", "Tendance actuelle"),
        ("/volatility <symbole>", "Volatilité"),
        ("/levels <symbole>", "Supports et résistances"),
        ("/scan", "Scanner les opportunités suivies"),
    ]),
    ("🔔 Alertes & watchlist", [
        ("/alert <symbole> <prix>", "Créer une alerte de prix"),
        ("/alerts", "Lister les alertes actives"),
        ("/delalert <id>", "Supprimer une alerte"),
        ("/clearalerts", "Supprimer toutes les alertes"),
        ("/watchlist", "Afficher la watchlist"),
        ("/addwatch <symbole>", "Ajouter un symbole à la watchlist"),
        ("/removewatch <symbole>", "Retirer un symbole de la watchlist"),
    ]),
    ("🧪 Paper trading", [
        ("/paper", "Gérer le portefeuille de simulation"),
    ]),
    ("⚙️ Paramètres", [
        ("/settings", "Afficher les paramètres"),
        ("/settimeframe <tf>", "Modifier le timeframe par défaut"),
        ("/setstyle <style>", "Modifier le style de trading"),
        ("/setlanguage <fr|en>", "Modifier la langue"),
    ]),
    ("🔐 Sécurité", [
        ("/setsecurity <code>", "Créer le code sécurité"),
        ("/setsecurity <ancien> <nouveau>", "Modifier le code sécurité"),
    ]),
    ("🤖 AutoTrade Binance", [
        ("/setapikeys <api_key> <api_secret> <code>", "Enregistrer les clés Binance en privé"),
        ("/autotrade", "Ouvrir le menu AutoTrade"),
        ("/autotrade on <code>", "Activer AutoTrade après authentification"),
        ("/autotrade off", "Désactiver AutoTrade"),
        ("/periodic_analysis on <code>", "Activer l'analyse automatique du marché"),
        ("/periodic_analysis on <5|10> <code>", "Activer l'analyse avec intervalle"),
        ("/periodic_analysis off", "Désactiver l'analyse automatique"),

        ("/config", "Afficher la configuration de trading"),
        ("/positions", "Lister les positions ouvertes"),
        ("/close <id> <code>", "Fermer manuellement une position"),
        ("/pnl", "Statistiques PnL"),
        ("/account", "Tableau de bord Binance"),
        ("/history_trades", "Historique des trades"),
        ("/setleverage <n> <code>", "Modifier le levier"),
        ("/setrisk <pct> <code>", "Modifier le risque par trade"),
        ("/setmaxpos <1-10> <code>", "Modifier le nombre maximum de positions"),
        ("/setminscore <0-100> <code>", "Modifier le score minimum des signaux"),
        ("/setdailymaxloss <pct> <code>", "Modifier la perte maximale journalière"),
        ("/setmarket <spot|futures> <code>", "Modifier le marché AutoTrade autorisé"),
        ("/settradingstyle <style> <code>", "Modifier le style AutoTrade"),
        ("/setanalysistf <tf> <code>", "Modifier le timeframe d’analyse AutoTrade"),
        ("/setanalysisinterval <5|10> <code>", "Modifier l’intervalle d’analyse"),
        ("/settrailing <on|off> [pct] <code>", "Activer/désactiver le trailing stop"),
        ("/settrailing pct <pct> <code>", "Modifier la distance du trailing stop"),
        ("/setcooldown <secondes> <code>", "Modifier le délai entre ouvertures"),
        ("/settestnet <on|off> <code>", "Basculer testnet/mainnet"),
        ("/setdca <off|on> [steps] [step_pct] <code>", "Configurer le DCA (si activé côté moteur)"),
        ("/whitelist <add|remove|clear> <symbole> <code>", "Gérer les symboles autorisés"),
        ("/blacklist <add|remove|clear> <symbole> <code>", "Gérer les symboles interdits"),
        ("/emergency_stop <code>", "Désactiver AutoTrade et fermer les positions"),
        ("/confirmmanual <token> <code>", "Confirmer un trade réel préparé"),
        ("/editsignal <id> <sl> <tp>", "Modifier SL/TP d'un signal en attente"),
    ]),
    ("🚨 Live trading manuel", [
        ("/live", "Menu Live Trading"),
        ("/live_long", "Préparer un ordre LONG réel"),
        ("/live_short", "Préparer un ordre SHORT réel"),
        ("/live_close <id>", "Fermer une position live"),
        ("/live_cancel <symbole> <order_id>", "Annuler un ordre live"),
    ]),
]

ADMIN_COMMAND_CATEGORIES = [
    ("🛠 Administration", [
        ("/stats", "Statistiques globales"),
        ("/teddy", "Tableau de bord admin"),
        ("/broadcast <message>", "Envoyer un message global"),
        ("/switchapi", "Basculer de fournisseur API"),
        ("/find_memo <memo>", "Retrouver un paiement par mémo"),
        ("/confirm_payment <user_id>", "Valider un paiement"),
        ("/refreshhistory", "Rafraîchir l'historique"),
        ("/clearhistory", "Nettoyer l'historique"),
        ("/deleteuser <user_id>", "Supprimer un utilisateur"),
        ("/exportsignals", "Exporter les signaux"),
        ("/dbquery <sql>", "Exécuter une requête DB admin"),
        ("/cleanwaits", "Nettoyer les attentes expirées"),
        ("/trading_stats", "Statistiques AutoTrade"),
        ("/trades", "Lister les trades réels"),
        ("/forceclose <trade_id>", "Forcer une fermeture admin"),
    ]),
]


HELP_FOOTER = "🔐 Les commandes contenant un code ou des clés doivent être envoyées en privé. Le bot tente de supprimer automatiquement le message après traitement."
TELEGRAM_SAFE_MESSAGE_LIMIT = 3500


def _help_categories(*, include_admin: bool = False):
    categories = list(USER_COMMAND_CATEGORIES)
    if include_admin:
        categories += ADMIN_COMMAND_CATEGORIES
    return categories


def render_help_pages(*, include_admin: bool = False, max_chars: int = TELEGRAM_SAFE_MESSAGE_LIMIT) -> list[str]:
    """Render /help as Telegram-safe Markdown pages.

    Telegram rejects messages over 4096 characters. Keep a lower ceiling so
    trial text or future command descriptions cannot make /help fail at send
    time. Category blocks are kept intact unless a single future category grows
    beyond max_chars, in which case it is split by command line.
    """
    pages: list[str] = []
    current = "📚 *Commandes disponibles*"

    def flush_current():
        nonlocal current
        if current.strip():
            pages.append(current.strip())
        current = ""

    def append_block(block: str):
        nonlocal current
        separator = "\n\n" if current else ""
        if current and len(current) + len(separator) + len(block) > max_chars:
            flush_current()
        current = f"{current}{separator}{block}" if current else block

    for title, commands in _help_categories(include_admin=include_admin):
        header = f"*{title}*"
        lines = [header] + [f"`{usage}` — {description}" for usage, description in commands]
        block = "\n".join(lines)
        if len(block) <= max_chars:
            append_block(block)
            continue

        append_block(header)
        for line in lines[1:]:
            append_block(line)

    append_block(HELP_FOOTER)
    if current.strip():
        pages.append(current.strip())
    return pages


def render_help(*, include_admin: bool = False) -> str:
    return "\n\n".join(render_help_pages(include_admin=include_admin))
