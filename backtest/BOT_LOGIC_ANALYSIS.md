# Analyse de la logique actuelle du bot Bitsure Teddy

Ce document décrit la logique observée dans le repository afin que le moteur de backtest indépendant puisse la reproduire sans modifier le bot de production.

## 1. Fichier principal du bot

Le point d'entrée applicatif est `main.py`.

- Il initialise la base via `get_db()`.
- Il construit l'application Telegram avec `ApplicationBuilder`.
- Il enregistre les commandes utilisateur, admin, AutoTrade et Live Trading.
- Il démarre les tâches planifiées liées au trading automatique :
  - `scheduled_signal_scan` toutes les 20 secondes ;
  - `scheduled_market_analysis` toutes les 5 et 10 minutes ;
  - `monitor_open_positions` toutes les 15 secondes.

## 2. Génération des signaux

La génération principale des signaux est dans `signal_engine.py`, classe `SignalEngine`, méthode `analyze(df, lang, symbol, style)`.

Flux observé :

1. Normalisation des colonnes OHLCV vers `Open`, `High`, `Low`, `Close`, `Volume`.
2. Validation minimale : DataFrame non vide, colonnes `Open`, `High`, `Low`, `Close`, longueur minimale 60 bougies.
3. Détection de la classe d'actif via `_asset_profile(symbol)`.
4. Chargement des seuils symbole depuis `SYMBOL_CONFIGS` dans `config.py`, avec fallback `BTCUSD`.
5. Calcul des indicateurs.
6. Construction des conditions BUY et SELL.
7. Détermination du signal brut si au moins `min_cond` conditions sont vraies.
8. Filtres de rejet supplémentaires : sur-extension, pullback, ADX minimum, RR minimum, score minimum.
9. Retour d'un dictionnaire contenant signal, score, SL, TP, RR, indicateurs et détails.

Les signaux périodiques AutoTrade sont produits dans `execution_engine.py` par `scheduled_market_analysis`, qui récupère les bougies Binance via `get_klines_dataframe`, appelle `SignalEngine.analyze`, puis sauvegarde uniquement les signaux `BUY`/`SELL` ouvrables.

## 3. Indicateurs utilisés

Les indicateurs sont définis dans `indicators.py` et utilisés par `SignalEngine.analyze`.

- RSI : période 14, moyenne simple des gains/pertes, valeurs NaN remplacées par 50.
- MACD : EMA 12, EMA 26, signal 9, histogramme MACD - signal.
- SMA : SMA 20 et SMA 50 pour la tendance.
- ADX : période 14 avec lissage Wilder, retourne ADX, +DI, -DI.
- ATR : période 14 avec lissage Wilder.
- Bollinger Bands : période 20, écart-type 2.
- Support/Résistance : plus bas et plus haut sur les 50 dernières bougies.
- Volume : volume courant et SMA volume 20 si la colonne `Volume` est disponible.
- Multi-timeframe : tendances 1h, 4h, 1d dérivées par resampling quand l'index temporel est disponible.
- Fonctions additionnelles disponibles mais non utilisées dans la décision principale `analyze` : stochastique, divergence RSI, niveaux Fibonacci.

## 4. Conditions exactes d'entrée

### Conditions BUY

Un signal BUY brut est possible si au moins `min_cond` conditions sont vraies :

1. Tendance haussière : `last_price > sma20 > sma50`.
2. RSI dans la plage symbole : `rsi_buy_low <= RSI <= rsi_buy_high`.
3. Momentum MACD haussier : `macd > macd_signal` et `histogram > 0`.
4. ADX suffisant : `ADX >= adx_min`.
5. Volatilité ATR acceptable : `ATR / price <= atr_max_pct / 100`.

### Conditions SELL

Un signal SELL brut est possible si au moins `min_cond` conditions sont vraies :

1. Tendance baissière : `last_price < sma20 < sma50`.
2. RSI dans la plage symbole : `rsi_sell_low <= RSI <= rsi_sell_high`.
3. Momentum MACD baissier : `macd < macd_signal` et `histogram < 0`.
4. ADX suffisant : `ADX >= adx_min`.
5. Volatilité ATR acceptable : `ATR / price <= atr_max_pct / 100`.

### Confirmations et filtres après signal brut

Même si le signal brut est BUY ou SELL, il est rejeté en WAIT si :

- le mouvement récent sur 5 bougies dépasse le seuil de sur-extension en multiples d'ATR ;
- le prix est trop éloigné de la SMA20 selon `pullback_pct` de la classe d'actif ;
- le prix dépasse la bande de Bollinger supérieure pour BUY ou inférieure pour SELL ;
- l'ADX est inférieur au seuil de rejet du style ;
- le ratio risk/reward est inférieur au minimum du style ;
- le score Teddy final est inférieur au minimum du style.

### Multi-timeframe

Les tendances 1h, 4h et 1d sont comparées :

- 3 tendances alignées : bonus +15.
- 2 tendances alignées : bonus +5.
- conflit haussier/baissier : malus -15.
- neutre : 0.

Le bonus positif est inversé en malus si la direction MTF ne correspond pas au signal.

## 5. Gestion des positions

### AutoTrade réel

Dans `execution_engine.py` :

- Les signaux `pending` ou `active` et de direction `BUY`/`SELL` sont traités.
- Un signal est ignoré si son score est inférieur à `TradingConfig.min_score`.
- Les règles de risque sont vérifiées par `risk_manager.check_can_open_position` : blacklist, whitelist, `max_positions`, perte journalière maximale et cooldown.
- En mode futures, BUY et SELL sont autorisés. En spot, SELL est rejeté car le short spot standard n'est pas supporté.
- La taille de position réelle est calculée par `calculate_position_size` :

```text
risk_amount = balance * risk_per_trade / 100
quantity = risk_amount / abs(entry_price - sl_price)
```

Le commentaire du code précise que le levier change la marge, pas cette quantité notionnelle calculée par le risque.

### Paramètres de risque configurables

`trading_config.py` définit notamment :

- `leverage`, défaut env `DEFAULT_LEVERAGE` ou 1 ;
- `risk_per_trade`, défaut 1% ;
- `max_positions`, défaut 3 ;
- `min_score`, défaut 70 ;
- `max_daily_loss`, défaut 5% ;
- `trailing_stop`, défaut false ;
- `trailing_stop_pct`, défaut 1% ;
- `dca_enabled`, défaut false ;
- `dca_steps`, défaut 3 ;
- `dca_step_pct`, défaut 2% ;
- `market_type`, défaut futures ;
- `trading_style`, défaut day ;
- `analysis_timeframe`, défaut 1h.

## 6. Gestion de sortie

Dans `position_manager.py` :

- Les positions ouvertes sont surveillées par `monitor_open_positions`.
- Pour BUY : TP si prix courant >= TP, SL si prix courant <= SL.
- Pour SELL : TP si prix courant <= TP, SL si prix courant >= SL.
- Si TP ou SL est touché, la position est clôturée avec raison `TP` ou `SL`.
- En spot, le bot ferme explicitement au marché ; en futures, SL/TP sont placés côté Binance lors de l'ouverture.
- Le PnL est calculé ainsi :
  - BUY : `(current_price - entry_price) * quantity` ;
  - SELL : `(entry_price - current_price) * quantity` ;
  - `pnl_pct = pnl_usdt / (entry_price * quantity) * 100 * leverage`.
- Le trailing stop est optionnel :
  - BUY : nouveau SL = `current_price * (1 - trailing_stop_pct / 100)` si supérieur au SL courant ;
  - SELL : nouveau SL = `current_price * (1 + trailing_stop_pct / 100)` si inférieur au SL courant.
- Le DCA est configurable mais aucune logique DCA active n'a été trouvée dans `monitor_open_positions`.
- La fermeture forcée existe via `emergency_stop_all`, qui ferme toutes les positions de l'utilisateur et désactive l'auto-trade.

## 7. Paramètres de stratégie

### `SYMBOL_CONFIGS` dans `config.py`

Les symboles natifs de la stratégie sont des formats de type `BTCUSD`, `ETHUSD`, etc. Pour Binance futures `BTCUSDT` et `ETHUSDT`, le backtest utilise un mapping vers `BTCUSD` et `ETHUSD` pour reprendre les seuils existants.

Exemples :

- BTCUSD : ADX min 23, RSI BUY 48-68, RSI SELL 32-52, ATR max 5.5%, min conditions 4.
- ETHUSD : ADX min 22, RSI BUY 47-70, RSI SELL 30-56, ATR max 6.0%, min conditions 4.

### Styles dans `signal_engine.py`

- scalping : SL 0.70 ATR, TP 1.25 ATR.
- scalping_15m : SL 0.85 ATR, TP 1.55 ATR.
- day : SL 1.15 ATR, TP 2.2 ATR.
- swing : SL 1.75 ATR, TP 3.5 ATR.
- position : SL 2.5 ATR, TP 5.0 ATR.

### Rejets par style

- scalping : score min 62, ADX min 18, RR min 1.1.
- scalping_15m : score min 63, ADX min 18, RR min 1.2.
- day : score min 60, ADX min 15, RR min 1.3.
- swing : score min 58, ADX min 15, RR min 1.5.
- position : score min 55, ADX min 15, RR min 1.8.

### Classes d'actifs

Les cryptos listées incluent BTCUSD et ETHUSD. Elles appliquent notamment :

- `sl_factor` 1.25 ;
- `tp_factor` 1.15 ;
- pas de delta ADX/score/RR ;
- `pullback_pct` 0.07 ;
- `overextension_factor` 1.20 ;
- `sr_buffer_factor` 1.15.

## 8. Hypothèses retenues pour le backtest

Le simulateur reproduit la logique de signal du bot sans importer `config.py`, car ce fichier exige des variables d'environnement Telegram/Admin au moment de l'import. Les constantes nécessaires sont donc recopiées dans `backtest/strategy.py` pour garder le simulateur indépendant.

Le backtest exécute les signaux à la clôture de la bougie qui les génère, puis teste SL/TP sur les bougies suivantes. Si SL et TP sont touchés sur la même bougie, la configuration `same_bar_exit_policy` décide du comportement. Par défaut, `conservative` priorise le SL.

Le moteur n'est pas un optimiseur : il charge une configuration JSON, rejoue les bougies, exporte les résultats et expose un mode debug de comparaison signal bot vs signal simulateur.
