"""Central catalogue for Telegram /help command descriptions."""

USER_COMMAND_CATEGORIES = [
    ("🚀 Général", [
        ("/start", "Démarrer le bot et afficher l'état du compte"),
        ("/help", "Afficher cette aide et les commandes disponibles"),
        ("/menu", "Ouvrir le menu principal interactif"),
        ("/myid", "Afficher ton identifiant Telegram"),
        ("/support", "Contacter l'administrateur / support"),
        ("/usage", "Voir votre consommation et quota de requêtes"),
        ("/upgrade", "Découvrir et souscrire aux offres PRO"),
        ("/pay_binance", "Instructions de paiement direct via Binance USDC"),
        ("/historique", "Consulter vos 10 derniers signaux enregistrés"),
    ]),
    ("📊 Analyse & Marché", [
        ("/analyse <symbole>", "Analyse technique complète avec Teddy Score"),
        ("/price <symbole>", "Obtenir le prix en temps réel"),
        ("/trend <symbole>", "Analyse de la tendance globale et sous-jacente"),
        ("/volatility <symbole>", "Indicateurs de volatilité (ATR, bandes)"),
        ("/levels <symbole>", "Niveaux clés (Supports, Résistances, Fibonacci)"),
        ("/scan", "Lancer un scan manuel de votre watchlist"),
    ]),
    ("🔔 Alertes & Watchlist", [
        ("/alert <symbole> <above|below> <prix>", "Créer une alerte de prix"),
        ("/alerts", "Afficher vos alertes de prix actives"),
        ("/delalert <id>", "Supprimer une alerte spécifique par son ID"),
        ("/clearalerts", "Supprimer toutes vos alertes de prix"),
        ("/watchlist", "Afficher vos symboles suivis"),
        ("/addwatch <symbole>", "Ajouter un symbole à votre watchlist"),
        ("/removewatch <symbole>", "Retirer un symbole de votre watchlist"),
    ]),
    ("🧪 Paper Trading", [
        ("/paper", "Ouvrir la sélection de symbole paper trading"),
        ("/paper status", "Afficher le bilan du portefeuille virtuel"),
        ("/paper buy <symbole>", "Ouvrir une position virtuelle LONG"),
        ("/paper short <symbole>", "Ouvrir une position virtuelle SHORT"),
        ("/paper close <symbole>", "Fermer une position virtuelle"),
        ("/paper history", "Historique des trades virtuels fermés"),
        ("/paper stats", "Statistiques détaillées de performance paper"),
        ("/paper reset", "Réinitialiser le compte virtuel ($10,000)"),
    ]),
    ("⚙️ Paramètres utilisateur", [
        ("/settings", "Afficher vos préférences actuelles"),
        ("/settimeframe <5m|15m|1h|4h|1d>", "Modifier le timeframe par défaut"),
        ("/setstyle <scalping|day|swing|position>", "Modifier votre style de trading"),
        ("/setlanguage <fr|en>", "Changer la langue de l'interface"),
    ]),
    ("🔐 Sécurité (AutoTrade)", [
        ("/setsecurity <code>", "Créer un code de sécurité (ex: 4827BZ)"),
        ("/setsecurity <ancien_code> <nouveau_code>", "Modifier votre code de sécurité"),
    ]),
    ("🤖 AutoTrade Binance", [
        ("/setapikeys <api_key> <api_secret> <code>", "Enregistrer vos clés API Binance 🔒"),
        ("/autotrade", "Ouvrir le menu de contrôle AutoTrade"),
        ("/autotrade on <code>", "Activer l'exécution automatique des trades 🔒"),
        ("/autotrade off", "Désactiver l'AutoTrade"),
        ("/periodic_analysis on [5|10] <code>", "Activer le scanner de marché auto 🔒"),
        ("/periodic_analysis off", "Désactiver le scanner automatique"),
        ("/config", "Afficher la configuration courante d'AutoTrade"),
        ("/positions", "Lister vos positions AutoTrade ouvertes"),
        ("/close <id> <code>", "Fermer une position AutoTrade 🔒"),
        ("/pnl", "Statistiques PnL globale du compte"),
        ("/account", "Tableau de bord et solde du compte Binance"),
        ("/history_trades", "Historique des 10 derniers trades réels"),
        ("/setleverage <1-125> <code>", "Définir le levier AutoTrade 🔒"),
        ("/setrisk <pct> <code>", "Définir le risque % par trade 🔒"),
        ("/setmaxpos <1-10> <code>", "Définir le nombre max de positions 🔒"),
        ("/setminscore <0-100> <code>", "Définir le score minimal requis 🔒"),
        ("/setdailymaxloss <pct> <code>", "Définir la perte journalière max % 🔒"),
        ("/setmarket <spot|futures> <code>", "Basculer entre Spot et Futures 🔒"),
        ("/settradingstyle <style> <code>", "Style de trading AutoTrade 🔒"),
        ("/setanalysistf <5m|15m|1h|4h|1d> <code>", "Timeframe du scanner AutoTrade 🔒"),
        ("/setanalysisinterval <5|10> <code>", "Intervalle de scan (minutes) 🔒"),
        ("/settrailing <on|off> [pct] <code>", "Configurer le Trailing Stop 🔒"),
        ("/setcooldown <secondes> <code>", "Délai de sécurité entre trades 🔒"),
        ("/settestnet <on|off> <code>", "Activer/désactiver le mode Testnet 🔒"),
        ("/setdca <off|on> [steps] [step_pct] <code>", "Configurer la stratégie DCA 🔒"),
        ("/whitelist <add|remove|clear> <symbole> <code>", "Gérer les symboles autorisés 🔒"),
        ("/blacklist <add|remove|clear> <symbole> <code>", "Gérer les symboles exclus 🔒"),
        ("/emergency_stop <code>", "🚨 Arrêt d'urgence et fermeture globale 🔒"),
        ("/confirmmanual <token> <code>", "Valider un trade suggéré par /analyse 🔒"),
        ("/editsignal <id> <sl> <tp>", "Ajuster SL/TP d'un signal en attente"),
    ]),
    ("🚨 Live Trading Manuel", [
        ("/live", "Menu interactif Live Trading"),
        ("/live_long <symbole> <montant> <sl> <tp> [options]", "Préparer un ordre réel LONG"),
        ("/live_short <symbole> <montant> <sl> <tp> [options]", "Préparer un ordre réel SHORT"),
        ("/live_close <id>", "Fermer une position réelle spécifique"),
        ("/live_cancel <symbole> <order_id>", "Annuler un ordre limite ouvert"),
    ]),
]

ADMIN_COMMAND_CATEGORIES = [
    ("🛠 Administration (Réservé Admin)", [
        ("/stats", "Statistiques globales du bot et des utilisateurs"),
        ("/teddy", "Tableau de bord de gestion des autorisations"),
        ("/broadcast <message>", "Diffuser un message à tous les utilisateurs"),
        ("/switchapi", "Basculer la source de données (Binance/CoinGecko)"),
        ("/find_memo <memo>", "Rechercher une transaction par mémo"),
        ("/confirm_payment <user_id>", "Valider manuellement un abonnement PRO"),
        ("/refreshhistory", "Rafraîchir les historiques de signaux"),
        ("/clearhistory", "Purger l'historique des signaux"),
        ("/deleteuser <user_id>", "Supprimer un compte utilisateur"),
        ("/exportsignals", "Exporter la base de signaux en CSV"),
        ("/dbquery <sql>", "Exécuter une requête SQL sur la base"),
        ("/cleanwaits", "Nettoyer les états d'attente utilisateur expirés"),
        ("/trading_stats", "Statistiques d'exécution AutoTrade global"),
        ("/trades", "Lister tous les trades réels enregistrés"),
        ("/forceclose <trade_id>", "Forcer la clôture administrative d'un trade"),
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
