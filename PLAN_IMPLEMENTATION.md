# Plan d'Action & Modifications de Code - Bitsure Trading Bot

Ce document détaille les corrections, améliorations et ajouts de code à apporter au bot de trading Bitsure (dans `bitsure_bot`) pour résoudre l'ensemble des problèmes signalés.

---

## 📋 Synthèse des Problèmes & Solutions

| Module | Problème Identifié | Solution Apportée |
| :--- | :--- | :--- |
| **1. Analyse Périodique** | Non exécutée sans `auto_trade`, pas d'affichage terminal propre. | Ajout du flag `periodic_analysis_enabled`, refonte du job d'analyse automatique pour logger sur le terminal et notifier Telegram, ajout du bouton de commutation dans les menus. |
| **2. Mode Spot / Futures** | Commutation inactive, UI statique, pas d'adaptation des règles par mode. | Mise à jour interactive de l'UI avec coche `[ ✅ Spot ]` / `[ ✅ Futures ]`, verrouillage du levier à 1x en Spot, et adaptation des appels API Binance (`futures_*` vs `spot_*`). |
| **3. Solde & PnL Complet** | Données dispersées et incomplètes, manque le solde par actif, commissions et marge. | Création de `get_full_account_info()` dans `binance_manager.py` et ajout d'un sous-menu/commande `/account` ("💼 Mon Compte"). |
| **4. Paper Trading** | Bug d'ouverture (appel à `RiskManager` invalide), capital virtuel mal géré, pas d'auto-SL/TP. | Correction du calcul des quantités et du capital fictif (marge + frais + slippage), automatisation des sorties SL/TP en arrière-plan, et ajout de la réinitialisation (`/paper reset`). |

---

## 🛠️ Details des Modifications par Fichier

### 1. `trading_config.py` & `database.py`
Ajout de la colonne et du paramètre `periodic_analysis_enabled`.

#### In `database.py` :
```python
"ALTER TABLE trading_config ADD COLUMN IF NOT EXISTS periodic_analysis_enabled BOOLEAN DEFAULT FALSE",
```

#### In `trading_config.py` :
```python
@dataclass
class TradingConfig:
    user_id: int
    auto_trade: bool = DEFAULTS["auto_trade"]
    periodic_analysis_enabled: bool = False
    leverage: int = DEFAULTS["leverage"]
    # ... reste inchangé
```

---

### 2. `execution_engine.py` (Analyse Périodique & Logs Terminal)
Modification pour inclure les utilisateurs ayant activé l'analyse périodique indépendamment de l'auto-trade, et pour afficher les résultats dans le terminal (stdout/logger).

```python
def _get_active_analysis_user_ids(interval_minutes: int) -> list[int]:
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

async def scheduled_market_analysis(context: ContextTypes.DEFAULT_TYPE, interval_minutes: int):
    """
    Exécute l'analyse automatique des marchés et affiche les résultats dans le terminal + Telegram.
    """
    history_mgr = HistoryManager.get_instance()
    user_ids = _get_active_analysis_user_ids(interval_minutes)
    
    print(f"\n================ [ ANALYSE PERIODIQUE ({interval_minutes}m) ] ================")
    logger.info(f"Lancement analyse périodique {interval_minutes}m pour {len(user_ids)} utilisateur(s)")

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

        scanned, rejected_by_risk, errors = 0, 0, 0
        saved = []

        for symbol in symbols:
            try:
                df = get_klines_dataframe(symbol, config.analysis_timeframe, market_type=config.market_type)
                if df is None or df.empty:
                    errors += 1
                    continue

                scanned += 1
                result = SignalEngine.analyze(df, "fr", symbol=symbol, style=config.trading_style)
                
                price = float(result["indicators"]["price"])
                rsi = result["indicators"].get("rsi", "N/A")
                macd = result["indicators"].get("macd", "N/A")
                score = result.get("teddy_score", 0)
                sig = result.get("signal", "WAIT")

                # Affichage dans le terminal
                print(f"[{symbol}] Prix: {price:.4f} | RSI: {rsi} | MACD: {macd} | Score: {score} | Signal: {sig}")

                if sig not in ("BUY", "SELL"):
                    continue

                risk_check = check_can_open_position(user_id, config, symbol)
                if not risk_check.allowed:
                    rejected_by_risk += 1
                    continue

                signal_id = history_mgr.add_signal(
                    symbol=symbol,
                    direction=sig,
                    price=price,
                    timeframe=config.analysis_timeframe,
                    signal_type="periodic_analysis",
                    score=score,
                    sl=result.get("sl"),
                    tp=result.get("tp"),
                    user_id=user_id,
                    validation_status=result.get("validation_status", "VALIDATED"),
                )
                if signal_id:
                    saved.append((symbol, result, signal_id))
            except Exception as e:
                errors += 1
                log_error(logger, user_id, f"scheduled_market_analysis.{symbol}", str(e))

        report = _format_market_scan_report(config, scanned, saved, rejected_by_risk, errors)
        print(f"--- Rapport final User {user_id} ---\n{report}\n========================================================\n")
        
        try:
            if context and hasattr(context, "bot"):
                await context.bot.send_message(chat_id=user_id, text=report, parse_mode="Markdown")
        except Exception as e:
            log_error(logger, user_id, "scheduled_market_analysis.report", str(e))
```

---

### 3. `binance_manager.py` (Mode Spot/Futures & Dashboard Solde/PnL)

#### Adaptation du mode Spot/Futures :
```python
def open_position(
    user_id: int,
    symbol: str,
    direction: str,
    quantity: float,
    sl_price: Optional[float],
    tp_price: Optional[float],
    market_type: MarketType = "futures",
    leverage: int = 1,
) -> dict:
    client = _client_for_user(user_id)

    # Force le levier à 1 en Spot
    if market_type == "spot":
        leverage = 1
        if direction == "SELL":
            raise BinanceClientError("Vente à découvert (SHORT) non supportée en mode Spot standard.")

    filters = get_symbol_filters(client, symbol, market_type)
    step_size = filters.get("LOT_SIZE", {}).get("stepSize") or filters.get("MARKET_LOT_SIZE", {}).get("stepSize", "0.001")
    quantity = round_step_size(quantity, step_size)
    if quantity <= 0:
        raise BinanceClientError("Quantité calculée trop faible.")

    result = {"quantity": quantity}

    if market_type == "futures":
        if leverage > 1:
            set_leverage(user_id, symbol, leverage)
        order = client.futures_create_order(symbol=symbol, side=direction, type="MARKET", quantity=quantity)
        result["order_id"] = order["orderId"]
        result["client_order_id"] = order.get("clientOrderId")

        opposite = "SELL" if direction == "BUY" else "BUY"
        if sl_price:
            sl_order = client.futures_create_order(symbol=symbol, side=opposite, type="STOP_MARKET", stopPrice=round(sl_price, 6), closePosition=True)
            result["sl_order_id"] = sl_order["orderId"]
        if tp_price:
            tp_order = client.futures_create_order(symbol=symbol, side=opposite, type="TAKE_PROFIT_MARKET", stopPrice=round(tp_price, 6), closePosition=True)
            result["tp_order_id"] = tp_order["orderId"]
    else:  # Spot
        order = client.create_order(symbol=symbol, side=direction, type="MARKET", quantity=quantity)
        result["order_id"] = order["orderId"]
        result["client_order_id"] = order.get("clientOrderId")
        result["sl_order_id"] = None
        result["tp_order_id"] = None

    return result
```

#### Nouvelle fonction pour l'affichage complet du Solde & PnL :
```python
def get_full_account_info(user_id: int, market_type: MarketType = "futures") -> dict:
    """
    Récupère toutes les informations du compte Binance :
    - Solde total (USDT + actifs)
    - Détail des actifs
    - Positions ouvertes + PnL non réalisé
    - Taux d'utilisation de la marge (Futures)
    - Historique des ordres récents et commissions
    """
    client = _client_for_user(user_id)
    summary = {
        "market_type": market_type,
        "total_wallet_balance": 0.0,
        "available_balance": 0.0,
        "unrealized_pnl": 0.0,
        "margin_used_pct": 0.0,
        "assets": [],
        "positions": [],
        "recent_trades": [],
        "total_commissions": 0.0,
    }

    try:
        if market_type == "futures":
            acc = client.futures_account()
            summary["total_wallet_balance"] = float(acc.get("totalWalletBalance", 0.0))
            summary["available_balance"] = float(acc.get("availableBalance", 0.0))
            summary["unrealized_pnl"] = float(acc.get("totalUnrealizedProfit", 0.0))

            total_maint_margin = float(acc.get("totalMaintMargin", 0.0))
            total_margin_balance = float(acc.get("totalMarginBalance", 1.0))
            if total_margin_balance > 0:
                summary["margin_used_pct"] = round((total_maint_margin / total_margin_balance) * 100, 2)

            for b in acc.get("assets", []):
                bal = float(b.get("walletBalance", 0.0))
                if bal > 0:
                    summary["assets"].append({
                        "asset": b["asset"],
                        "wallet": bal,
                        "available": float(b.get("availableBalance", 0.0)),
                        "unrealized_pnl": float(b.get("unrealizedProfit", 0.0)),
                    })

            raw_positions = client.futures_position_information()
            for pos in raw_positions:
                amt = float(pos.get("positionAmt", 0.0))
                if amt != 0:
                    entry = float(pos.get("entryPrice", 0.0))
                    mark = float(pos.get("markPrice", 0.0))
                    upnl = float(pos.get("unRealizedProfit", 0.0))
                    side = "BUY (LONG)" if amt > 0 else "SELL (SHORT)"
                    summary["positions"].append({
                        "symbol": pos["symbol"],
                        "side": side,
                        "quantity": abs(amt),
                        "entry_price": entry,
                        "mark_price": mark,
                        "unrealized_pnl": upnl,
                        "leverage": int(pos.get("leverage", 1)),
                        "liquidation_price": float(pos.get("liquidationPrice", 0.0)),
                    })

            # Historique des trades & commissions récents
            user_trades = client.futures_account_trades(limit=10)
            for t in user_trades:
                comm = float(t.get("commission", 0.0))
                summary["total_commissions"] += comm
                summary["recent_trades"].append({
                    "symbol": t["symbol"],
                    "side": t["side"],
                    "price": float(t["price"]),
                    "qty": float(t["qty"]),
                    "commission": comm,
                    "commission_asset": t["commissionAsset"],
                    "time": t["time"],
                })

        else:  # Spot
            acc = client.get_account()
            balances = acc.get("balances", [])
            total_usdt = 0.0

            for b in balances:
                free = float(b.get("free", 0.0))
                locked = float(b.get("locked", 0.0))
                total = free + locked
                if total > 0:
                    asset = b["asset"]
                    usdt_val = total
                    if asset != "USDT":
                        try:
                            price = float(client.get_symbol_ticker(symbol=f"{asset}USDT")["price"])
                            usdt_val = total * price
                        except Exception:
                            usdt_val = 0.0
                    total_usdt += usdt_val
                    summary["assets"].append({
                        "asset": asset,
                        "free": free,
                        "locked": locked,
                        "total": total,
                        "usdt_value": round(usdt_val, 2),
                    })

            summary["total_wallet_balance"] = round(total_usdt, 2)
            summary["available_balance"] = float(client.get_asset_balance(asset="USDT")["free"]) if client.get_asset_balance(asset="USDT") else 0.0

    except BinanceAPIException as e:
        raise BinanceClientError(f"Erreur API Binance Account: {e.message}")

    return summary
```

---

### 4. `paper_trader.py` (Paper Trading Fixes & Reset)

#### Ajout de la méthode `reset_account()` :
```python
def reset_account(self, user_id, amount: float = 10000.0) -> float:
    """Réinitialise totalement le compte Paper Trading de l'utilisateur."""
    uid = self._uid(user_id)
    self.capitals[uid] = amount
    self.positions[uid] = []
    self.closed_positions[uid] = []
    
    try:
        self.conn.execute("DELETE FROM paper_positions WHERE user_id = %s", (int(uid),))
        self.conn.execute("DELETE FROM paper_capitals WHERE user_id = %s", (int(uid),))
        self.conn.execute("INSERT INTO paper_capitals (user_id, capital) VALUES (%s, %s)", (int(uid), amount))
        self.conn.commit()
    except Exception as e:
        logger.error(f"[PaperTrader.reset_account] Erreur: {e}")
        try:
            self.conn.rollback()
        except Exception:
            pass
    return amount
```

---

### 5. `bot_handlers.py` (Correction Bug Paper Trading & Ajout de `/account`)

#### Fix de l'ouverture d'ordre paper (lignes 1278 et 1342) :
Remplacement de l'appel erroné à `RiskManager.calculate_position_size(...)` par une méthode de dimensionnement sûre :

```python
        # Quantité simulée basée sur le levier et la marge engagée (ex: 5% du capital)
        margin_to_use = capital * 0.05
        notional_value = margin_to_use * leverage
        qty = notional_value / price if price > 0 else 0

        if qty <= 0:
            await respond(update, "❌ Capital insuffisant pour ouvrir une position simulée.")
            return
```

#### Ajout de l'action `/paper reset` :
```python
    elif action == "reset":
        new_cap = paper_trader.reset_account(user_id)
        await respond(
            update,
            f"🔄 *Compte Paper Trading réinitialisé !*\n\n"
            f"💰 Capital réinitialisé à : *{new_cap:.2f} USDT*\n"
            f"🗑️ Toutes les positions ouvertes et l'historique ont été effacés.",
            parse_mode=ParseMode.MARKDOWN,
        )
```

#### Nouvelle commande `/account` (et `/solde`) :
```python
@check_limit
async def account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /account — Visualisation complète du solde, PnL et positions Binance."""
    user_id = update.effective_user.id
    config = get_config(user_id)
    
    try:
        info = get_full_account_info(user_id, market_type=config.market_type)
    except BinanceClientError as e:
        await respond(update, f"❌ {e}")
        return

    lines = [
        f"💼 *Tableau de Bord Compte Binance ({info['market_type'].upper()})*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"💰 *Solde Total* : `{info['total_wallet_balance']:.2f} USDT`",
        f"💵 *Disponible* : `{info['available_balance']:.2f} USDT`",
        f"📊 *PnL Non Réalisé* : `{info['unrealized_pnl']:+.2f} USDT`",
    ]

    if info["market_type"] == "futures":
        lines.append(f"⚡ *Taux Marge Utilisée* : `{info['margin_used_pct']}%`")

    lines.append("\n🪙 *Détail des Actifs* :")
    for a in info["assets"][:5]:
        if info["market_type"] == "futures":
            lines.append(f"  • *{a['asset']}* : {a['wallet']:.4f} (PnL: {a['unrealized_pnl']:+.2f})")
        else:
            lines.append(f"  • *{a['asset']}* : {a['total']:.4f} (~{a['usdt_value']:.2f} USDT)")

    lines.append("\n📈 *Positions Ouvertes Binance* :")
    if info["positions"]:
        for p in info["positions"]:
            lines.append(
                f"  • *{p['symbol']}* ({p['side']} x{p['leverage']})\n"
                f"    Qty: {p['quantity']} | Entrée: {p['entry_price']:.4f} | Prix: {p['mark_price']:.4f}\n"
                f"    PnL: `{p['unrealized_pnl']:+.2f} USDT` | Liq: {p['liquidation_price']:.4f}"
            )
    else:
        lines.append("  *Aucune position ouverte sur Binance.*")

    if info.get("recent_trades"):
        lines.append(f"\n💸 *Commissions Récentes* : `{info['total_commissions']:.4f} USDT`")

    keyboard = [[InlineKeyboardButton("🔄 Rafraîchir", callback_data="cmd_account")]]
    await respond(update, "\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
```

---

### 6. `trading_handlers.py` (Mise à jour dynamique du Mode Spot/Futures dans les Menus)

```python
    elif data == "menu_market_mode":
        config = get_config(user_id)
        spot_label = "🟢 Spot (Actif)" if config.market_type == "spot" else "Spot"
        futures_label = "🟢 Futures (Actif)" if config.market_type == "futures" else "Futures"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(spot_label, callback_data="set_market_spot"),
                InlineKeyboardButton(futures_label, callback_data="set_market_futures"),
            ],
            [InlineKeyboardButton("⬅️ Retour", callback_data="menu_autotrade")],
        ])
        await query.edit_message_text(
            f"🎯 *Mode de Marché Actuel :* `{config.market_type.upper()}`\n\n"
            f"Choisis le mode à utiliser pour les analyses et les ordres.",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif data.startswith("set_market_"):
        market_type = data.replace("set_market_", "")
        if market_type not in ("spot", "futures"):
            await query.edit_message_text("Mode de marché invalide.")
            return
        update_config(user_id, market_type=market_type)
        # Rafraîchit le menu directement avec le nouvel état
        await trading_callback_router(update, context)
```

---

### 7. `position_manager.py` (Execution Automatique SL/TP pour le Paper Trading)

Afin que le paper trading applique le Stop Loss et le Take Profit automatiquement en tâche de fond :

```python
async def monitor_open_positions(context: ContextTypes.DEFAULT_TYPE):
    """Job APScheduler : surveille les positions réelles ET simulées."""
    # 1. Mise à jour et fermeture des positions Paper Trading
    try:
        from paper_trader import paper_trader
        closed_paper = paper_trader.check_exits()
        for pos in closed_paper:
            uid = int(pos["user_id"])
            pnl_net = pos.get("pnl_usdt", 0) - pos.get("fees_total", 0)
            emoji = "🟢" if pnl_net >= 0 else "🔴"
            if context and hasattr(context, "bot"):
                await context.bot.send_message(
                    chat_id=uid,
                    text=(
                        f"{emoji} *[PAPER TRADING] Position Fermée ({pos.get('exit_reason')})*\n"
                        f"Symbole : `{pos['symbol']}` ({pos.get('side')})\n"
                        f"Prix Sortie : {pos['exit_price']:.4f}\n"
                        f"PnL Net : `{pnl_net:+.2f} USDT`\n"
                        f"Capital Virtuel : `{pos.get('capital_after', 0):.2f} USDT`"
                    ),
                    parse_mode="Markdown",
                )
    except Exception as e:
        log_error(logger, 0, "monitor_paper_positions", str(e))

    # 2. Surveillance des positions Binance réelles (code existant)
    # ...
```

---

## 🎯 Résumé des Ajouts de Commandes et Boutons du Menu

1. **Menu Principal (`menu_command`)** :
   - Ajout du bouton `💼 Mon Compte (Solde & PnL)` (`menu_account`).
   - Bouton `🤖 AutoTrade Binance` mis à jour.
   - Bouton `📝 Paper Trading` avec option de réinitialisation.

2. **Nouvelles Commandes Telegram & CLI** :
   - `/account` (ou `/solde`) : Affiche le bilan complet du compte (Wallet USDT, actifs, positions réelles, commissions, taux de marge).
   - `/paper reset` : Réinitialise le portefeuille virtuel à 10 000 USDT et efface les anciennes positions.
   - `/paper buy SYMBOL [levier]` / `/paper short SYMBOL [levier]` : Ouverture simulée fluide LONG ou SHORT.

3. **Console / Terminal** :
   - L'analyse périodique (`scheduled_market_analysis`) écrit en continu l'avancement des scans avec les métriques techniques (Prix, RSI, MACD, Teddy Score) directement dans le terminal.
