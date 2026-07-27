# i18n.py - Traductions FR / EN pour Bitsure Teddy

TEXTS = {
    "fr": {
        # ----- Accueil / Statuts -----
        "start": (
            "🐻 *Bitsure Teddy* — Assistant de trading transparent\n\n"
            "📊 Analyse technique avec Teddy Score (0-95)\n"
            "🎯 SL & TP calculés automatiquement\n"
            "📋 Historique public vérifiable\n\n"
            "🟢 *Phase de test publique* — Tout est gratuit\n\n"
            "🔹 /menu — Menu principal\n\n"
            "Bons trades ! 🧸"
        ),
        "start_disclaimer": "",
        "status_free_trial": "🆓 Essai gratuit (3 jours)",
        "status_free_ended": "🆓 Gratuit (essai terminé)",
        "status_pro": "💎 PRO",
        "international_payment_info": "",
        "terms_title": "*📋 Conditions d'utilisation*",
        "terms_text": (
            "Avant d'utiliser Bitsure Teddy, tu dois lire et accepter les conditions suivantes :\n\n"
            "1. Ce bot fournit des signaux de trading à titre indicatif uniquement. Aucun conseil financier n'est donné.\n"
            "2. Les performances passées (backtests) ne garantissent pas les résultats futurs.\n"
            "3. Tu es seul responsable de tes décisions de trading. Ne trade jamais plus que ce que tu es prêt à perdre.\n"
            "4. Le trading comporte des risques élevés. Bitsure Teddy et son créateur ne pourront être tenus responsables de tes pertes.\n"
            "5. En utilisant ce bot, tu confirmes avoir compris et accepté ces conditions."
        ),
        "terms_accept": "✅ J'accepte",
        "terms_refuse": "❌ Je refuse",
        "terms_accepted": "✅ Conditions acceptées. Bienvenue sur Bitsure Teddy ! Utilise /menu pour commencer.",
        "terms_refused_msg": "❌ Tu ne peux pas utiliser le bot sans accepter les conditions. Retape /start quand tu seras prêt.",
        "terms_must_accept": "⚠️ Tu dois d'abord accepter les conditions d'utilisation. Tape /start pour les consulter.",
        "terms_button": "📋 Lire les conditions d'utilisation",

        # ----- Aide -----
        "help_redirect": "Utilisez /menu pour accéder au menu interactif. Fonctionnalités clés : analyse technique avec score Teddy, paper trading intégré et backtest public vérifiable.",
        "help_full": (
            "🧸 *Commandes disponibles :*\n\n"
            "📌 *Général & Analyse*\n"
            "/menu – Menu principal interactif\n"
            "/help – Liste des commandes\n"
            "/analyse SYMBOLE – Analyse technique complète\n"
            "/price SYMBOLE – Prix en temps réel\n"
            "/trend SYMBOLE – Analyse de la tendance\n"
            "/volatility SYMBOLE – Volatilité (ATR)\n"
            "/levels SYMBOLE – Supports, résistances et Fibonacci\n"
            "/myid – Afficher votre ID Telegram\n\n"

            "🔔 *Alertes & Watchlist*\n"
            "/alert SYMBOLE condition PRIX – Créer une alerte (ex: /alert BTCUSD above 65000)\n"
            "/alerts – Afficher vos alertes actives\n"
            "/delalert ID – Supprimer une alerte\n"
            "/clearalerts – Supprimer toutes vos alertes\n"
            "/watchlist – Afficher votre liste de suivi\n"
            "/addwatch SYMBOLE – Ajouter à la liste de suivi\n"
            "/removewatch SYMBOLE – Retirer de la liste de suivi\n"
            "/scan – Scanner manuellement la liste de suivi\n\n"

            "📜 *Paper Trading & Historique*\n"
            "/paper [start|status|buy|short|close|history|stats|reset] – Paper trading\n"
            "/historique – Historique récent des signaux\n\n"

            "🤖 *AutoTrade Binance*\n"
            "/autotrade – Activer/Désactiver l'AutoTrade\n"
            "/setapikeys CLE SECRET – Configurer vos clés API Binance\n"
            "/config – Voir la configuration d'AutoTrade\n"
            "/positions – Voir vos positions ouvertes\n"
            "/close ID – Fermer une position\n"
            "/pnl – Statistique PnL de votre compte\n"
            "/account – Tableau de bord complet du compte Binance\n"
            "/history_trades – Historique des 10 derniers trades Binance\n"
            "/setleverage LEVIER – Configurer le levier (1-125)\n"
            "/setrisk % – Configurer le risque par trade (%)\n"
            "/whitelist SYMBOLE – Ajouter un symbole autorisé\n"
            "/blacklist SYMBOLE – Exclure un symbole\n"
            "/emergency_stop – Arrêt d'urgence et fermeture de toutes les positions\n\n"

            "🚨 *Live Trading*\n"
            "/live – Menu Live Trading réel\n"
            "/live_long SYMBOLE MONTANT SL TP [LEVIER] – Préparer un LONG réel\n"
            "/live_short SYMBOLE MONTANT SL TP [LEVIER] – Préparer un SHORT réel\n"
            "/live_close ID – Fermer une position réelle suivie\n"
            "/live_cancel SYMBOLE ORDER_ID – Annuler un ordre ouvert\n\n"

            "⚙️ *Paramètres & Compte*\n"
            "/settings – Afficher vos paramètres actuels\n"
            "/settimeframe TF – Définir l'unité de temps (5m, 15m, 1h, 4h, 1d)\n"
            "/setstyle STYLE – Définir le style (day, swing, position, scalping)\n"
            "/setlanguage LANG – Changer la langue (fr/en)\n"
            "/usage – Nombre de requêtes restantes\n"
            "/upgrade – Passer à la version PRO\n"
            "/support – Support & contact admin"
        ),
        "help_admin": "\n\n🛠 *Commandes Admin :*\n/stats, /teddy, /broadcast, /switchapi, /find_memo, /confirm_payment, /refreshhistory, /clearhistory, /deleteuser, /exportsignals, /dbquery, /cleanwaits, /trading_stats, /trades, /forceclose",

        # ----- Support / Upgrade -----
        "support": "📞 Besoin d'aide ?\n\nContactez l'administrateur : @btsr_teddy09",
        "upgrade_title": (
            "💳 *Passez à Bitsure Teddy PRO*\n\n"
            "• Analyses illimitées avec score Teddy\n"
            "• Paper trading intégré\n"
            "• Backtests publics vérifiables\n"
            "• Watchlist étendue et support prioritaire\n\n"
            "*Choisissez votre mode de paiement :*"
        ),
        "button_pro_stars": "⭐ PRO 19,99€/mois (Telegram Stars)",
        "button_binance_usdc": "🟡 Binance USDC",
        "binance_payment_info": (
            "🟡 Paiement Binance (USDC)\n\n"
            "1. Ouvre Binance → Portefeuille → Envoyer\n"
            "2. Entre l'ID Binance : {binance_id}\n"
            "3. Montant : {amount} USDC\n"
            "4. Vérifie que le pseudo affiché est bien le tien\n\n"
            "Ton ID de transaction : {memo}\n\n"
            "⚠️ Copie cet ID et envoie-le à l'admin après avoir payé."
        ),
        "confirm_payment_usage": "Usage: /confirm_payment <user_id>",
        "confirm_payment_ok": "✅ Paiement confirmé pour l'utilisateur {user_id}.",
        "confirm_payment_missing": "❌ Aucun paiement Binance en attente pour {user_id}.",
        "premium_required": "🔒 *Fonctionnalité Premium*\n\nCette commande est réservée aux membres PRO.\nUtilisez /upgrade pour découvrir l'offre.",
        "payment_success": "✅ *Paiement réussi !*\nVous êtes maintenant *PRO*.\nMerci de votre confiance ! 🧸",
        "unavailable_option": "Option non disponible.",

        # ----- Limites -----
        "limit_reached": "❌ Vous avez atteint votre limite quotidienne de requêtes. Passez PRO pour un accès illimité : /upgrade",
        "watchlist_limit": "❌ Vous avez atteint la limite de 3 symboles en mode gratuit.\nPassez PRO pour en ajouter plus : /upgrade",

        # ----- Watchlist -----
        "watchlist_added": "✅ {symbol} ajouté à votre watchlist.",
        "watchlist_removed": "✅ {symbol} retiré de votre watchlist.",
        "watchlist_empty": "Votre watchlist est vide.",
        "watchlist_scan_empty": "Watchlist vide.",
        "watchlist_scan_result": "📊 *Scan watchlist:*\n{results}",
        "watchlist_show": "📋 *Watchlist:*\n{symbols}",
        "addwatch_usage": "Usage: /addwatch SYMBOLE",
        "removewatch_usage": "Usage: /removewatch SYMBOLE",
        "watchlist_already": "ℹ️ {symbol} est déjà dans ta watchlist.",
        "watchlist_missing": "ℹ️ {symbol} n'est pas dans ta watchlist.",
        "watchlist_added_styled": "✅ {symbol} ajouté à ta watchlist",
        "watchlist_removed_styled": "🗑️ {symbol} retiré de ta watchlist",

        # ----- Alertes -----
        "alert_usage": "Usage: /alert SYMBOLE above/below PRIX",
        "alert_invalid_price": "Prix invalide.",
        "alert_invalid_cond": "Condition doit être 'above' ou 'below'.",
        "alert_created": "✅ Alerte #{id} créée : {symbol} {cond} {price}",
        "alerts_empty": "Aucune alerte active.",
        "alerts_list_title": "*Vos alertes :*\n",
        "alert_deleted": "✅ Alerte #{id} supprimée.",
        "alert_not_found": "❌ Alerte non trouvée.",
        "alerts_cleared": "✅ Toutes vos alertes ont été supprimées.",
        "alert_triggered": "🚨 *Alerte déclenchée* : {symbol} a atteint {condition} {price}\nPrix actuel : {current_price}",
        "clearalerts_confirm": "⚠️ Êtes-vous sûr de vouloir supprimer TOUTES vos alertes ?",
        "clearhistory_confirm": "Supprimer tout l'historique des signaux ?",
        "clearhistory_done": "✅ Historique effacé.",
        "clearhistory_btn": "Effacer mon historique",
        "history_menu_title": "*📋 Historique*",
        "confirm_yes": "✅ Oui",
        "confirm_no": "❌ Non",
        "delalert_usage": "Usage: /delalert ID",
        "delalert_pick": "Choisissez une alerte à supprimer :",
        "cond_above": "Au-dessus",
        "cond_below": "En-dessous",
        "alert_choose_condition": "Choisissez une condition :",
        "alert_enter_price": "Entrez le prix cible après la condition.",
        "alert_price_invalid_retry": "Prix invalide, réessayez.",

        # ----- Symboles -----
        "symbole_invalide": "Symbole invalide.",
        "symboles_list": (
            "📊 *SYMBOLES POPULAIRES*\n\n"
            "🪙 *Cryptos*\nBTCUSD – Bitcoin\nETHUSD – Ethereum\n\n"
            "💱 *Devises*\nEURUSD – Euro/Dollar\nGBPUSD – Livre/Dollar\nUSDJPY – Dollar/Yen\nAUDUSD – Dollar Australien\n\n"
            "✨ *Matières premières*\nXAUUSD – Or\n\n"
            "📈 *Actions*\nAAPL – Apple\nTSLA – Tesla\nNVDA – NVIDIA\n\n"
            "💡 Exemple : /analyse BTCUSD"
        ),
        "symbol_not_found": "Symbole non trouvé.",

        # ----- Analyse -----
        "analyse_usage": "Usage: /analyse SYMBOLE",
        "analyse_wait": "🔍 Analyse de {symbol} en cours...",
        "analyse_error": "❌ Impossible de récupérer les données pour {symbol}.",
        "analyse_caption": (
            "📊 *ANALYSE {symbol}*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🎯 Signal    : {signal_emoji} {signal}\n"
            "📈 Score     : {teddy_score}/100 ({confidence})\n"
            "💵 Prix      : {price}\n"
            "🛑 SL        : {sl}\n"
            "🎯 TP        : {tp} (RR: {rr_ratio})\n"
            "📊 RSI       : {rsi:.1f}\n"
            "   État RSI  : {rsi_state}\n"
            "📏 ADX       : {adx:.1f} ({adx_state})\n"
            "📉 SMA20/50  : {sma20} / {sma50}\n"
            "💡 Raison    : {reason}\n"
            "⚠️ Conseil   : {risk_advice}\n"
            "━━━━━━━━━━━━━━━━━━━"
        ),
        "rsi_overbought": "Surachat",
        "rsi_oversold": "Survente",
        "rsi_bullish": "Haussier",
        "rsi_bearish": "Baissier",
        "rsi_neutral": "Neutre",
        "adx_very_strong": "Très forte",
        "adx_strong": "Forte",
        "adx_moderate": "Modérée",
        "adx_weak": "Faible",
        "price_usage": "Usage: /price SYMBOLE",
        "price_error": "❌ Prix non disponible pour {symbol}.",
        "price_format": "💵 *{symbol}*\n━━━━━━━━━━━━━━━━━━━\n💰 Prix : {price}\n📉 Bid  : {bid}\n📈 Ask  : {ask}",

        # ----- Tendance / Volatilité / Corrélation / Niveaux -----
        "trend_usage": "Usage: /trend SYMBOLE",
        "trend_no_data": "Données non disponibles.",
        "trend_haussiere": "Haussière",
        "trend_baissiere": "Baissière",
        "trend_neutre": "Neutre",
        "trend_bullish": "Haussière",
        "trend_bearish": "Baissière",
        "trend_neutral": "Neutre",
        "trend_result": "*{symbol}* Tendance: {tend}",
        "volatility_usage": "Usage: /volatility SYMBOLE",
        "volatility_result": "*{symbol}* Volatilité (ATR 14): {atr}",
        "correlation_usage": "Usage: /correlation SYMBOLE1 SYMBOLE2",
        "correlation_result": "*{symbol1} vs {symbol2}* Corrélation 30j: {corr:.2f}",
        "levels_usage": "Usage: /levels SYMBOLE",
        "levels_no_data": "Données non disponibles.",
        "levels_result": (
            "📏 *NIVEAUX {symbol}*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🟢 Support    : {support}\n"
            "🔴 Résistance : {resistance}\n"
            "📐 Fib 38.2%  : {fib382}\n"
            "📐 Fib 50.0%  : {fib500}\n"
            "📐 Fib 61.8%  : {fib618}"
        ),

        # ----- Sentiment / Compare / Top / Fav -----
        "sentiment_result": "📊 *Fear & Greed Index Crypto*\n\nValeur actuelle: {value}\nClassification: {classification}",
        "sentiment_error": "Impossible de récupérer le Fear & Greed Index.",
        "compare_usage": "Usage: /compare SYM1 SYM2",
        "compare_result": "*{symbol1} vs {symbol2}*\nTendance: {trend1} vs {trend2}",
        "top_crypto": "🚀 *Top 5 Crypto en hausse (24h)*\n\n{list}",
        "fav_usage": "Usage: /fav add|remove|list [symbole]",
        "fav_add_usage": "Usage: /fav add SYMBOLE",
        "fav_remove_usage": "Usage: /fav remove SYMBOLE",
        "fav_added": "✅ {symbol} ajouté aux favoris.",
        "fav_removed": "✅ {symbol} retiré des favoris.",
        "fav_list": "⭐ *Vos favoris:*\n{symbols}",
        "fav_empty": "Aucun favori enregistré.",
        "insufficient_data": "Données insuffisantes.",
        "insufficient_common_data": "Pas assez de données communes.",
        "data_unavailable": "Données indisponibles.",

        # ----- Learn -----
        "learn_usage": "Usage: /learn [terme]\nTermes disponibles: rsi, macd, sma, support, resistance, fibonacci, atr, adx, stochastic",
        "learn_rsi": "*RSI*\nIndicateur de momentum mesurant vitesse et ampleur des mouvements de prix. >70 surachat, <30 survente.",
        "learn_macd": "*MACD*\nConvergence/divergence de moyennes mobiles. Croisements utilisés pour signaux d'achat/vente.",
        "learn_sma": "*SMA*\nMoyenne mobile simple. SMA20 et SMA50 sont des références courantes de tendance.",
        "learn_support": "*Support*\nNiveau de prix où la demande stoppe une baisse.",
        "learn_resistance": "*Résistance*\nNiveau de prix où l'offre stoppe une hausse.",
        "learn_fibonacci": "*Fibonacci*\nNiveaux de retracement (38.2%, 50%, 61.8%) utilisés pour zones de support/résistance.",
        "learn_atr": "*ATR*\nMesure de la volatilité moyenne. Utilisé pour placer des stop-loss.",
        "learn_adx": "*ADX*\nMesure la force d'une tendance (>25 = tendance forte).",
        "learn_stochastic": "*Stochastic*\nCompare le prix de clôture à la fourchette de prix. >80 surachat, <20 survente.",
        "learn_spread": "*Écart de prix*\nDifférence entre prix acheteur et vendeur.",

        # ----- Paramètres -----
        "settings_title": "*⚙️ Vos paramètres actuels*",
        'settings_timeframe': '⏱️ Timeframe',
        'settings_style': '🎯 Style de trading',
        'settings_lang': '🌐 Langue',
        'settings_edit': 'Que voulez-vous modifier ?',

        "settings_info": "⚙️ *Paramètres*\nTimeframe: {tf}\nRisque: {risk}\nLangue: {lang_name}\nRôle: {role}\nPremium: {prem}",
        "settimeframe_usage": "Usage: /settimeframe 1h|4h|1d",
        "settimeframe_invalid": "Timeframe invalide.",
        "settimeframe_success": "✅ Timeframe par défaut: {tf}",
        "settimeframe_choose": "Choisissez un timeframe :",
        "setrisk_usage": "Usage: /setrisk low|medium|high",
        "setrisk_invalid": "Risque invalide.",
        "setrisk_success": "✅ Profil de risque: {risk}",
        "setlanguage_usage": "Usage: /setlanguage en|fr",
        "setlanguage_invalid": "Langue invalide. Utilisez 'en' ou 'fr'.",
        "setlanguage_success_fr": "✅ Langue définie sur Français.",
        "setlanguage_success_en": "✅ Langue définie sur Anglais.",
        "setlanguage_choose": "Choisissez une langue :",
        "usage_requests_remaining": "📊 Requêtes restantes aujourd'hui: {rem}",
        "usage_unlimited": "✅ Premium: requêtes illimitées.",

        # ----- Infos -----
        "status_ok": "✅ Bot opérationnel.",
        "about": "Teddy Trading Bot v2.0 – Bitsure Teddy",
        "myid": "Votre ID Telegram: `{user_id}`",

        # ----- Admin -----
        "admin_only": "⛔ Commande réservée à l'administrateur.",
        "broadcast_admin_only": "⛔ Commande réservée à l'administrateur.",
        "broadcast_usage": "Usage: /broadcast MESSAGE",
        "broadcast_sent": "✅ Broadcast envoyé à {success}/{total} utilisateurs.",
        "reload_success": "✅ Configuration rechargée.",
        "action_cancelled": "❌ Action annulée.",

        # ----- Switch API -----
        "switchapi_usage": "Usage : /switchapi twelve|fcs|real",
        "switchapi_current": "Source actuelle : {source}",
        "switchapi_switched": "✅ Basculement vers {source} effectué.",

        # ----- Refresh History -----
        "refreshhistory_start": "🔄 Mise à jour de l'historique en cours...",
        "refreshhistory_done": "✅ Historique mis à jour.",

        # ----- Historique -----
        "history_title": "*📋 HISTORIQUE — {date}*",
        "history_summary": "📊 {total} signaux · {wins} gagnés ({win_rate}%) · {losses} perdus · {open_count} en cours · {total_pnl}",
        "history_empty": "Aucun signal enregistré.",
        "no_recent_analysis": "Aucune analyse récente.",

        # ----- Signal Engine -----
        "signal_insufficient_data": "Données insuffisantes",
        "signal_buy_reason": "📈 Signaux haussiers détectés",
        "signal_buy_advice": "⚠️ Entrée progressive conseillée",
        "signal_sell_reason": "📉 Signaux baissiers détectés",
        "signal_sell_advice": "⚠️ Risque de continuation",
        "signal_wait_neutral": "Aucun signal clair – phase de consolidation",
        "signal_wait_advice": "⏳ Attendre une confirmation",
        "confidence_high": "FORTE",
        "confidence_medium": "MOYENNE",
        "confidence_low": "FAIBLE",
        "signal_buy": "ACHETER",
        "signal_sell": "VENDRE",
        "signal_wait": "ATTENDRE",
        "na": "N/A",

        # ----- Menu interactif -----
        "menu_title": "🧸 *MENU PRINCIPAL*\nSélectionnez une catégorie :",
        "menu_analyse": "📊 Analyse",
        "menu_paper": "📈 Paper Trading",
        "menu_alertes": "🚨 Alertes",
        "menu_watchlist": "📋 Watchlist",
        "menu_parametres": "⚙️ Paramètres",
        "menu_upgrade": "💎 Upgrade",
        "back": "⬅️ Retour",
        "menu_choose_command": "Choisissez une commande :",
        "btn_analyse": "📊 Analyse",
        "btn_price": "💰 Prix",
        "btn_trend": "📈 Tendance",
        "btn_volatility": "🌪 Volatilité",
        "btn_levels": "📍 Niveaux",
        "btn_paper": "📈 Paper Trading",
        "btn_paper_buy": "🟢 Acheter / Vendre",
        "btn_paper_status": "📊 Positions ouvertes",
        "btn_paper_history": "📋 Historique",
        "btn_paper_stats": "📈 Statistiques",
        "btn_alert": "➕ Alerte",
        "btn_alerts": "📑 Alertes",
        "btn_delalert": "➖ Supprimer alerte",
        "btn_clearalerts": "🧹 Effacer alertes",
        "btn_watchlist": "📋 Watchlist",
        "btn_addwatch": "➕ Ajouter",
        "btn_removewatch": "➖ Retirer",
        "btn_scan": "🔎 Scanner",
        "btn_settings": "⚙️ Paramètres",
        "btn_settimeframe": "⏱ Timeframe",
        "btn_setlanguage": "🌐 Langue",
        "btn_usage": "📊 Usage",
        "btn_historique": "📜 Historique",
        "btn_clearhistory": "🧹 Effacer l'historique",
        "btn_support": "📞 Support",
        "btn_upgrade": "💎 Upgrade",
        "help_redirect": "Utilisez /menu pour accéder au menu interactif.",
        "trial_days_left": "Essai gratuit : {days} jours restants",
        "btn_upgrade_stars": "Telegram Stars (19,99€/mois)",
        "btn_upgrade_binance": "Binance Junior (USDC)",
        "select_symbol": "Sélectionnez un symbole :",
        "unknown_command": "Commande non reconnue.",
        "unknown_option": "Option non reconnue.",

        # ----- Backtest -----
        "backtest_start": "🚀 Lancement du backtest...",
        "backtest_downloading": "⬇️ Téléchargement des données pour {symbol}...",
        "backtest_no_data": "⚠️ Pas de données pour {symbol}",
        "backtest_no_trades": "ℹ️ {symbol}: Aucun trade.",
        "backtest_title": "*📊 {symbol} – Résultats du backtest*",
        "separator_line": "━━━━━━━━━━━━━━━━━━━━━━━━",
        "backtest_trades": "🔢 Trades        : {total}",
        "backtest_wins": "✅ Gagnants      : {wins} ({win_rate:.1f}%)",
        "backtest_losses": "❌ Perdants      : {losses}",
        "backtest_avg_gain": "📈 Gain moyen    : {avg_pnl:.4f}%",
        "backtest_total_gain": "💰 Gain total    : {total_pnl:.2f}%",
        "backtest_best": "🏆 Meilleur      : {best:.4f}%",
        "backtest_worst": "📉 Pire          : {worst:.4f}%",
        "backtest_drawdown": "📊 Max drawdown  : {max_drawdown:.2f}%",
        "backtest_avg_duration": "⏳ Durée moyenne : {avg_bars:.0f} bougies",

        # ----- Paper Trading -----
        "paper_usage": "Usage: /paper start|buy <symbole>|sell <symbole>|status|history|stats",
        "paper_started": "✅ Paper trading activé avec {capital}$ virtuels.",
        "paper_status": "📊 CAPITAL: {capital}$ | ÉQUITÉ: {equity}$ | PnL: {total_pnl}$ | Ouvertes: {open_positions}",
        "paper_buy_usage": "Usage: /paper buy <symbole>",
        "paper_opened": "✅ Position ouverte sur {symbol} à {price}$ | SL: {sl}$ | TP: {tp}$",
        "paper_sell_usage": "Usage: /paper sell <symbole>",
        "paper_closed": "✅ Position fermée sur {symbol}.",
        "paper_no_open_position": "Aucune position ouverte sur {symbol}.",
        "paper_history_empty": "Aucun trade fermé.",
        "paper_history_title": "*📋 HISTORIQUE PAPER TRADING*",
        "paper_choose_direction": "📈 {symbol} – Choisis la direction :",
        "paper_no_open_positions": "Aucune position ouverte.",
        "paper_stats": "📊 STATS PAPER TRADING\n💰 Capital: {capital}$\n📈 Équité: {equity}$\n💵 PnL: {total_pnl}$\n🔢 Trades: {total_trades}\n✅ Wins: {wins}\n❌ Losses: {losses}\n📊 Win rate: {win_rate:.1f}%",

        # ----- Snapshot / Verify -----
        "snapshot_caption": "🐻 *Bitsure Teddy*\n{symbol} – {signal}\nTeddy Score: {score}/100\nPrix: {price}",
        "verify_not_found": "❌ Aucun signal trouvé avec l'ID `{signal_id}`.",
        "verify_result": "🔍 *Signal #{signal_id}*\nÉmis le : {timestamp}\nSymbole : {symbol}\nSignal : {signal}\nPrix d'entrée : {price}\nRésultat : {result}",
        "verify_usage": "Usage: /verify SIGNAL_ID",
    },

    "en": {
        # ----- Welcome / Status -----
        "start": (
            "🐻 *Bitsure Teddy* — Transparent trading assistant\n\n"
            "📊 Technical analysis with Teddy Score (0-95)\n"
            "🎯 SL & TP calculated automatically\n"
            "📋 Public verifiable history\n\n"
            "🟢 *Public testing phase* — Everything is free\n\n"
            "🔹 /menu — Main menu\n\n"
            "Happy trading! 🧸"
        ),
        "start_disclaimer": "",
        "status_free_trial": "🆓 Free trial (3 days)",
        "status_free_ended": "🆓 Free (trial ended)",
        "status_pro": "💎 PRO",
        "international_payment_info": "",
        "terms_title": "*📋 Terms of Use*",
        "terms_text": (
            "Before using Bitsure Teddy, you must read and accept the following terms:\n\n"
            "1. This bot provides trading signals for informational purposes only. No financial advice is given.\n"
            "2. Past performance (backtests) does not guarantee future results.\n"
            "3. You are solely responsible for your trading decisions. Never trade more than you can afford to lose.\n"
            "4. Trading involves high risk. Bitsure Teddy and its creator cannot be held liable for your losses.\n"
            "5. By using this bot, you confirm that you have read, understood, and accepted these terms."
        ),
        "terms_accept": "✅ I Accept",
        "terms_refuse": "❌ I Refuse",
        "terms_accepted": "✅ Terms accepted. Welcome to Bitsure Teddy! Use /menu to get started.",
        "terms_refused_msg": "❌ You cannot use the bot without accepting the terms. Type /start when you are ready.",
        "terms_must_accept": "⚠️ You must first accept the terms of use. Type /start to review them.",
        "terms_button": "📋 Read Terms of Use",

        # ----- Help -----
        "help_redirect": "Use /menu to access the interactive menu. Key features: technical analysis with Teddy score, integrated paper trading, and verifiable public backtest.",
        "help_full": (
            "🧸 *Available commands:*\n\n"
            "📌 *General & Analysis*\n"
            "/menu – Interactive main menu\n"
            "/help – Command list\n"
            "/analyse SYMBOL – Full technical analysis\n"
            "/price SYMBOL – Real-time price\n"
            "/trend SYMBOL – Global trend analysis\n"
            "/volatility SYMBOL – Volatility (ATR)\n"
            "/levels SYMBOL – Support, resistance & Fibonacci\n"
            "/myid – View your Telegram ID\n\n"

            "🔔 *Alerts & Watchlist*\n"
            "/alert SYMBOL condition PRICE – Create price alert (e.g., /alert BTCUSD above 65000)\n"
            "/alerts – List your active alerts\n"
            "/delalert ID – Delete an alert\n"
            "/clearalerts – Delete all active alerts\n"
            "/watchlist – View your watchlist\n"
            "/addwatch SYMBOL – Add symbol to watchlist\n"
            "/removewatch SYMBOL – Remove symbol from watchlist\n"
            "/scan – Manually scan your watchlist\n\n"

            "📜 *Paper Trading & History*\n"
            "/paper [start|status|buy|short|close|history|stats|reset] – Paper trading\n"
            "/historique – Recent signal history\n\n"

            "🤖 *AutoTrade Binance*\n"
            "/autotrade – Toggle AutoTrade on/off\n"
            "/setapikeys KEY SECRET – Configure Binance API keys\n"
            "/config – View AutoTrade configuration\n"
            "/positions – View open positions\n"
            "/close ID – Close a position\n"
            "/pnl – Account PnL statistics\n"
            "/account – Full Binance account dashboard\n"
            "/history_trades – Last 10 Binance trades history\n"
            "/setleverage LEVERAGE – Set leverage (1-125)\n"
            "/setrisk % – Set risk per trade (%)\n"
            "/whitelist SYMBOL – Add whitelisted symbol\n"
            "/blacklist SYMBOL – Blacklist a symbol\n"
            "/emergency_stop – Emergency stop & close all positions\n\n"

            "🚨 *Live Trading*\n"
            "/live – Real Live Trading menu\n"
            "/live_long SYMBOL AMOUNT SL TP [LEVERAGE] – Prepare a real LONG\n"
            "/live_short SYMBOL AMOUNT SL TP [LEVERAGE] – Prepare a real SHORT\n"
            "/live_close ID – Close a tracked real position\n"
            "/live_cancel SYMBOL ORDER_ID – Cancel an open order\n\n"

            "⚙️ *Settings & Account*\n"
            "/settings – View current settings\n"
            "/settimeframe TF – Set timeframe (5m, 15m, 1h, 4h, 1d)\n"
            "/setstyle STYLE – Set trading style (day, swing, position, scalping)\n"
            "/setlanguage LANG – Change language (fr/en)\n"
            "/usage – Remaining requests\n"
            "/upgrade – Upgrade to PRO\n"
            "/support – Contact support/admin"
        ),
        "help_admin": "\n\n🛠 *Admin Commands:*\n/stats, /teddy, /broadcast, /switchapi, /find_memo, /confirm_payment, /refreshhistory, /clearhistory, /deleteuser, /exportsignals, /dbquery, /cleanwaits, /trading_stats, /trades, /forceclose",

        # ----- Support / Upgrade -----
        "support": "📞 Need help?\n\nContact admin: @btsr_teddy09",
        "upgrade_title": (
            "💳 *Upgrade to Bitsure Teddy PRO*\n\n"
            "• Unlimited analyses with Teddy score\n"
            "• Integrated paper trading\n"
            "• Verifiable public backtests\n"
            "• Extended watchlist and priority support\n\n"
            "*Choose your payment method:*"
        ),
        "button_pro_stars": "⭐ PRO €19.99/month (Telegram Stars)",
        "button_binance_usdc": "🟡 Binance USDC",
        "binance_payment_info": (
            "🟡 Binance Payment (USDC)\n\n"
            "1. Open Binance → Wallet → Send\n"
            "2. Enter Binance ID: {binance_id}\n"
            "3. Amount: {amount} USDC\n"
            "4. Verify the displayed username is correct\n\n"
            "Your transaction ID: {memo}\n\n"
            "⚠️ Copy this ID and send it to the admin after paying."
        ),
        "confirm_payment_usage": "Usage: /confirm_payment <user_id>",
        "confirm_payment_ok": "✅ Payment confirmed for user {user_id}.",
        "confirm_payment_missing": "❌ No pending Binance payment for {user_id}.",
        "premium_required": "🔒 *Premium Feature*\n\nThis command is reserved for PRO members.\nUse /upgrade to discover the offer.",
        "payment_success": "✅ *Payment successful!*\nYou are now *PRO*.\nThank you for your trust! 🧸",
        "unavailable_option": "Unavailable option.",

        # ----- Limits -----
        "limit_reached": "❌ You have reached your daily request limit. Upgrade to PRO for unlimited access: /upgrade",
        "watchlist_limit": "❌ You have reached the limit of 3 symbols in free mode.\nUpgrade to PRO to add more: /upgrade",

        # ----- Watchlist -----
        "watchlist_added": "✅ {symbol} added to your watchlist.",
        "watchlist_removed": "✅ {symbol} removed from your watchlist.",
        "watchlist_empty": "Your watchlist is empty.",
        "watchlist_scan_empty": "Watchlist empty.",
        "watchlist_scan_result": "📊 *Watchlist scan:*\n{results}",
        "watchlist_show": "📋 *Watchlist:*\n{symbols}",
        "addwatch_usage": "Usage: /addwatch SYMBOL",
        "removewatch_usage": "Usage: /removewatch SYMBOL",
        "watchlist_already": "ℹ️ {symbol} is already in your watchlist.",
        "watchlist_missing": "ℹ️ {symbol} is not in your watchlist.",
        "watchlist_added_styled": "✅ {symbol} added to your watchlist",
        "watchlist_removed_styled": "🗑️ {symbol} removed from your watchlist",

        # ----- Alerts -----
        "alert_usage": "Usage: /alert SYMBOL above/below PRICE",
        "alert_invalid_price": "Invalid price format.",
        "alert_invalid_cond": "Condition must be 'above' or 'below'.",
        "alert_created": "✅ Alert #{id} created: {symbol} {cond} {price}",
        "alerts_empty": "No active alerts.",
        "alerts_list_title": "*Your alerts:*\n",
        "alert_deleted": "✅ Alert #{id} deleted.",
        "alert_not_found": "❌ Alert not found.",
        "alerts_cleared": "✅ All your alerts have been deleted.",
        "alert_triggered": "🚨 *Alert triggered*: {symbol} reached {condition} {price}\nCurrent price: {current_price}",
        "clearalerts_confirm": "⚠️ Are you sure you want to delete ALL your alerts?",
        "clearhistory_confirm": "Delete all signal history?",
        "clearhistory_done": "✅ History cleared.",
        "clearhistory_btn": "Clear my history",
        "history_menu_title": "*📋 History*",
        "confirm_yes": "✅ Yes",
        "confirm_no": "❌ No",
        "delalert_usage": "Usage: /delalert ID",
        "delalert_pick": "Choose an alert to delete:",
        "cond_above": "Above",
        "cond_below": "Below",
        "alert_choose_condition": "Choose a condition:",
        "alert_enter_price": "Enter the target price after selecting condition.",
        "alert_price_invalid_retry": "Invalid price, please try again.",

        # ----- Symbols -----
        "symbole_invalide": "Invalid symbol.",
        "symboles_list": (
            "📊 *POPULAR SYMBOLS*\n\n"
            "🪙 *Cryptos*\nBTCUSD – Bitcoin\nETHUSD – Ethereum\n\n"
            "💱 *Currencies*\nEURUSD – Euro/Dollar\nGBPUSD – Pound/Dollar\nUSDJPY – Dollar/Yen\nAUDUSD – Australian Dollar\n\n"
            "✨ *Commodities*\nXAUUSD – Gold\n\n"
            "📈 *Stocks*\nAAPL – Apple\nTSLA – Tesla\nNVDA – NVIDIA\n\n"
            "💡 Example: /analyse BTCUSD"
        ),
        "symbol_not_found": "Symbol not found.",

        # ----- Analysis -----
        "analyse_usage": "Usage: /analyse SYMBOL",
        "analyse_wait": "🔍 Analyzing {symbol}...",
        "analyse_error": "❌ Could not retrieve data for {symbol}.",
        "analyse_caption": (
            "📊 *ANALYSIS {symbol}*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🎯 Signal    : {signal_emoji} {signal}\n"
            "📈 Score     : {teddy_score}/100 ({confidence})\n"
            "💵 Price     : {price}\n"
            "🛑 SL        : {sl}\n"
            "🎯 TP        : {tp} (RR: {rr_ratio})\n"
            "📊 RSI       : {rsi:.1f}\n"
            "   RSI state : {rsi_state}\n"
            "📏 ADX       : {adx:.1f} ({adx_state})\n"
            "📉 SMA20/50  : {sma20} / {sma50}\n"
            "💡 Reason    : {reason}\n"
            "⚠️ Advice    : {risk_advice}\n"
            "━━━━━━━━━━━━━━━━━━━"
        ),
        "rsi_overbought": "Overbought",
        "rsi_oversold": "Oversold",
        "rsi_bullish": "Bullish",
        "rsi_bearish": "Bearish",
        "rsi_neutral": "Neutral",
        "adx_very_strong": "Very Strong",
        "adx_strong": "Strong",
        "adx_moderate": "Moderate",
        "adx_weak": "Weak",
        "price_usage": "Usage: /price SYMBOL",
        "price_error": "❌ Price not available for {symbol}.",
        "price_format": "💵 *{symbol}*\n━━━━━━━━━━━━━━━━━━━\n💰 Price : {price}\n📉 Bid   : {bid}\n📈 Ask   : {ask}",

        # ----- Trend / Volatility / Correlation / Levels -----
        "trend_usage": "Usage: /trend SYMBOL",
        "trend_no_data": "No data available.",
        "trend_haussiere": "Bullish",
        "trend_baissiere": "Bearish",
        "trend_neutre": "Neutral",
        "trend_bullish": "Bullish",
        "trend_bearish": "Bearish",
        "trend_neutral": "Neutral",
        "trend_result": "*{symbol}* Trend: {tend}",
        "volatility_usage": "Usage: /volatility SYMBOL",
        "volatility_result": "*{symbol}* Volatility (ATR 14): {atr}",
        "correlation_usage": "Usage: /correlation SYMBOL1 SYMBOL2",
        "correlation_result": "*{symbol1} vs {symbol2}* 30d Correlation: {corr:.2f}",
        "levels_usage": "Usage: /levels SYMBOL",
        "levels_no_data": "No data available.",
        "levels_result": (
            "📏 *LEVELS {symbol}*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "🟢 Support    : {support}\n"
            "🔴 Resistance : {resistance}\n"
            "📐 Fib 38.2%  : {fib382}\n"
            "📐 Fib 50.0%  : {fib500}\n"
            "📐 Fib 61.8%  : {fib618}"
        ),

        # ----- Sentiment / Compare / Top / Fav -----
        "sentiment_result": "📊 *Crypto Fear & Greed Index*\n\nCurrent value: {value}\nClassification: {classification}",
        "sentiment_error": "Could not retrieve Fear & Greed Index.",
        "compare_usage": "Usage: /compare SYM1 SYM2",
        "compare_result": "*{symbol1} vs {symbol2}*\nTrend: {trend1} vs {trend2}",
        "top_crypto": "🚀 *Top 5 Crypto Gainers (24h)*\n\n{list}",
        "fav_usage": "Usage: /fav add|remove|list [symbol]",
        "fav_add_usage": "Usage: /fav add SYMBOL",
        "fav_remove_usage": "Usage: /fav remove SYMBOL",
        "fav_added": "✅ {symbol} added to favorites.",
        "fav_removed": "✅ {symbol} removed from favorites.",
        "fav_list": "⭐ *Your favorites:*\n{symbols}",
        "fav_empty": "No favorites saved.",
        "insufficient_data": "Insufficient data.",
        "insufficient_common_data": "Not enough common data.",
        "data_unavailable": "Data unavailable.",

        # ----- Learn -----
        "learn_usage": "Usage: /learn [term]\nAvailable terms: rsi, macd, sma, support, resistance, fibonacci, atr, adx, stochastic",
        "learn_rsi": "*RSI*\nMomentum indicator measuring speed and magnitude of price moves. >70 overbought, <30 oversold.",
        "learn_macd": "*MACD*\nMoving Average Convergence Divergence. Crossovers used for buy/sell signals.",
        "learn_sma": "*SMA*\nSimple Moving Average. SMA20 and SMA50 are common trend references.",
        "learn_support": "*Support*\nPrice level where demand stops a decline.",
        "learn_resistance": "*Resistance*\nPrice level where supply stops a rally.",
        "learn_fibonacci": "*Fibonacci*\nRetracement levels (38.2%, 50%, 61.8%) used for support/resistance zones.",
        "learn_atr": "*ATR*\nAverage True Range. Measures volatility, used for stop-losses.",
        "learn_adx": "*ADX*\nAverage Directional Index. Measures trend strength (>25 = strong trend).",
        "learn_stochastic": "*Stochastic*\nCompares closing price to price range. >80 overbought, <20 oversold.",
        "learn_spread": "*Price gap*\nDifference between buyer and seller prices.",

        # ----- Settings -----
        "settings_title": "*⚙️ Your current settings*",
        'settings_timeframe': '⏱️ Timeframe',
        'settings_style': '🎯 Trading Style',
        'settings_lang': '🌐 Language',
        'settings_edit': 'What do you want to change?',

        "settings_info": "⚙️ *Settings*\nTimeframe: {tf}\nRisk: {risk}\nLanguage: {lang_name}\nRole: {role}\nPremium: {prem}",
        "settimeframe_usage": "Usage: /settimeframe 1h|4h|1d",
        "settimeframe_invalid": "Invalid timeframe.",
        "settimeframe_success": "✅ Default timeframe: {tf}",
        "settimeframe_choose": "Choose a timeframe:",
        "setrisk_usage": "Usage: /setrisk low|medium|high",
        "setrisk_invalid": "Invalid risk.",
        "setrisk_success": "✅ Risk profile: {risk}",
        "setlanguage_usage": "Usage: /setlanguage en|fr",
        "setlanguage_invalid": "Invalid language. Use 'en' or 'fr'.",
        "setlanguage_success_fr": "✅ Language set to French.",
        "setlanguage_success_en": "✅ Language set to English.",
        "setlanguage_choose": "Choose a language:",
        "usage_requests_remaining": "📊 Requests remaining today: {rem}",
        "usage_unlimited": "✅ Premium: unlimited requests.",

        # ----- Info -----
        "status_ok": "✅ Bot operational.",
        "about": "Teddy Trading Bot v2.0 – Bitsure Teddy",
        "myid": "Your Telegram ID: `{user_id}`",

        # ----- Admin -----
        "admin_only": "⛔ Admin only command.",
        "broadcast_admin_only": "⛔ Admin only command.",
        "broadcast_usage": "Usage: /broadcast MESSAGE",
        "broadcast_sent": "✅ Broadcast sent to {success}/{total} users.",
        "reload_success": "✅ Configuration reloaded.",
        "action_cancelled": "❌ Action cancelled.",

        # ----- Switch API -----
        "switchapi_usage": "Usage: /switchapi twelve|fcs|real",
        "switchapi_current": "Current source: {source}",
        "switchapi_switched": "✅ Switched to {source}.",

        # ----- Refresh History -----
        "refreshhistory_start": "🔄 Updating history...",
        "refreshhistory_done": "✅ History updated.",

        # ----- History -----
        "history_title": "*📋 HISTORY — {date}*",
        "history_summary": "📊 {total} signals · {wins} wins ({win_rate}%) · {losses} losses · {open_count} open · {total_pnl}",
        "history_empty": "No signals recorded.",
        "no_recent_analysis": "No recent analysis.",

        # ----- Signal Engine -----
        "signal_insufficient_data": "Insufficient data",
        "signal_buy_reason": "📈 Bullish signals detected",
        "signal_buy_advice": "⚠️ Consider gradual entry",
        "signal_sell_reason": "📉 Bearish signals detected",
        "signal_sell_advice": "⚠️ Continuation risk",
        "signal_wait_neutral": "No clear signal – consolidation phase",
        "signal_wait_advice": "⏳ Wait for confirmation",
        "confidence_high": "HIGH",
        "confidence_medium": "MEDIUM",
        "confidence_low": "LOW",
        "signal_buy": "BUY",
        "signal_sell": "SELL",
        "signal_wait": "WAIT",
        "na": "N/A",

        # ----- Interactive Menu -----
        "menu_title": "🧸 *MAIN MENU*\nSelect a category:",
        "menu_analyse": "📊 Analysis",
        "menu_paper": "📈 Paper Trading",
        "menu_alertes": "🚨 Alerts",
        "menu_watchlist": "📋 Watchlist",
        "menu_parametres": "⚙️ Settings",
        "menu_upgrade": "💎 Upgrade",
        "back": "⬅️ Back",
        "menu_choose_command": "Choose a command:",
        "btn_analyse": "📊 Analysis",
        "btn_price": "💰 Price",
        "btn_trend": "📈 Trend",
        "btn_volatility": "🌪 Volatility",
        "btn_levels": "📍 Levels",
        "btn_paper": "📈 Paper Trading",
        "btn_paper_buy": "🟢 Buy / Sell",
        "btn_paper_status": "📊 Open Positions",
        "btn_paper_history": "📋 History",
        "btn_paper_stats": "📈 Statistics",
        "btn_alert": "➕ Alert",
        "btn_alerts": "📑 Alerts",
        "btn_delalert": "➖ Delete alert",
        "btn_clearalerts": "🧹 Clear alerts",
        "btn_watchlist": "📋 Watchlist",
        "btn_addwatch": "➕ Add",
        "btn_removewatch": "➖ Remove",
        "btn_scan": "🔎 Scan",
        "btn_settings": "⚙️ Settings",
        "btn_settimeframe": "⏱ Timeframe",
        "btn_setlanguage": "🌐 Language",
        "btn_usage": "📊 Usage",
        "btn_historique": "📜 History",
        "btn_clearhistory": "🧹 Clear History",
        "btn_support": "📞 Support",
        "btn_upgrade": "💎 Upgrade",
        "help_redirect": "Use /menu to access the interactive menu.",
        "trial_days_left": "Free trial: {days} days remaining",
        "btn_upgrade_stars": "Telegram Stars (19.99€/month)",
        "btn_upgrade_binance": "Binance Junior (USDC)",
        "select_symbol": "Select a symbol:",
        "unknown_command": "Unknown command.",
        "unknown_option": "Unknown option.",

        # ----- Backtest -----
        "backtest_start": "🚀 Starting backtest...",
        "backtest_downloading": "⬇️ Downloading data for {symbol}...",
        "backtest_no_data": "⚠️ No data available for {symbol}",
        "backtest_no_trades": "ℹ️ {symbol}: No trades.",
        "backtest_title": "*📊 {symbol} – Backtest Results*",
        "separator_line": "━━━━━━━━━━━━━━━━━━━━━━━━",
        "backtest_trades": "🔢 Trades        : {total}",
        "backtest_wins": "✅ Winners       : {wins} ({win_rate:.1f}%)",
        "backtest_losses": "❌ Losers        : {losses}",
        "backtest_avg_gain": "📈 Average gain  : {avg_pnl:.4f}%",
        "backtest_total_gain": "💰 Total gain    : {total_pnl:.2f}%",
        "backtest_best": "🏆 Best          : {best:.4f}%",
        "backtest_worst": "📉 Worst         : {worst:.4f}%",
        "backtest_drawdown": "📊 Max drawdown  : {max_drawdown:.2f}%",
        "backtest_avg_duration": "⏳ Avg duration  : {avg_bars:.0f} candles",

        # ----- Paper Trading -----
        "paper_usage": "Usage: /paper start|buy <symbol>|sell <symbol>|status|history|stats",
        "paper_started": "✅ Paper trading activated with ${capital} virtual.",
        "paper_status": "📊 CAPITAL: ${capital} | EQUITY: ${equity} | PnL: ${total_pnl} | Open: {open_positions}",
        "paper_buy_usage": "Usage: /paper buy <symbol>",
        "paper_opened": "✅ Position opened on {symbol} at ${price} | SL: ${sl} | TP: ${tp}",
        "paper_sell_usage": "Usage: /paper sell <symbol>",
        "paper_closed": "✅ Position closed on {symbol}.",
        "paper_no_open_position": "No open position on {symbol}.",
        "paper_history_empty": "No closed trades.",
        "paper_history_title": "*📋 PAPER TRADING HISTORY*",
        "paper_choose_direction": "📈 {symbol} – Choose direction:",
        "paper_no_open_positions": "No open positions.",
        "paper_stats": "📊 PAPER TRADING STATS\n💰 Capital: ${capital}\n📈 Equity: ${equity}\n💵 PnL: ${total_pnl}\n🔢 Trades: {total_trades}\n✅ Wins: {wins}\n❌ Losses: {losses}\n📊 Win rate: {win_rate:.1f}%",

        # ----- Snapshot / Verify -----
        "snapshot_caption": "🐻 *Bitsure Teddy*\n{symbol} – {signal}\nTeddy Score: {score}/100\nPrice: {price}",
        "verify_not_found": "❌ No signal found with ID `{signal_id}`.",
        "verify_result": "🔍 *Signal #{signal_id}*\nIssued on: {timestamp}\nSymbol: {symbol}\nSignal: {signal}\nEntry Price: {price}\nResult: {result}",
        "verify_usage": "Usage: /verify SIGNAL_ID",
    }
}

def get_text(lang: str, key: str, **kwargs) -> str:
    texts = TEXTS.get(lang, TEXTS["en"])
    text = texts.get(key, TEXTS["en"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text