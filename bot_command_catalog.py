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
        ("/whitelist <symbole> <code>", "Ajouter un symbole autorisé"),
        ("/blacklist <symbole> <code>", "Ajouter un symbole interdit"),
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


def render_help(*, include_admin: bool = False) -> str:
    categories = list(USER_COMMAND_CATEGORIES)
    if include_admin:
        categories += ADMIN_COMMAND_CATEGORIES
    lines = ["📚 *Commandes disponibles*", ""]
    for title, commands in categories:
        lines.append(f"*{title}*")
        for usage, description in commands:
            lines.append(f"`{usage}` — {description}")
        lines.append("")
    lines.append("🔐 Les commandes contenant un code ou des clés doivent être envoyées en privé. Le bot tente de supprimer automatiquement le message après traitement.")
    return "\n".join(lines).strip()
