"""
paper_trader.py — Module de paper trading realiste pour Bitsure Teddy.

Fonctionnalites :
- Positions BUY (long) et SELL (short)
- Levier configurable par position
- Frais de trading (entree + sortie) configurables via config.py
- Slippage configurable via config.py
- Mise a jour automatique du capital apres chaque cloture
- Declenchement automatique du SL et du TP (BUY et SELL)
- PnL correct selon le sens (long vs short)
- Plusieurs positions ouvertes simultanement par utilisateur
- Guards : capital insuffisant, double fermeture, position invalide
- Historique complet : date, symbole, sens, prix entree/sortie, qty, levier,
  frais, slippage, PnL brut, PnL net, capital avant/apres
"""

import logging
import time
from typing import Dict, List, Optional, Tuple

from config import (
    PAPER_DEFAULT_CAPITAL,
    PAPER_FEES_PCT,
    PAPER_SLIPPAGE_PCT,
    PAPER_DEFAULT_LEVERAGE,
    PAPER_MAX_LEVERAGE,
)

logger = logging.getLogger(__name__)


class PaperTrader:
    """
    Simulateur de trading realiste.

    Chaque position est un dict avec les cles suivantes :
        id, user_id, symbol, side, entry_price, exit_price, sl, tp,
        qty, leverage, fees_total, slippage, capital_before, capital_after,
        current_price, pnl_usdt, pnl_pct, status, exit_reason,
        opened_at, closed_at, peak_price
    """

    def __init__(self):
        from database import get_db
        self.conn = get_db()
        self.positions: Dict[str, List[Dict]] = {}
        self.closed_positions: Dict[str, List[Dict]] = {}
        self.capitals: Dict[str, float] = {}
        self._load()

    # ------------------------------------------------------------------
    # CHARGEMENT / SAUVEGARDE
    # ------------------------------------------------------------------

    def _load(self):
        """Charge les positions ouvertes et les capitaux depuis la BDD."""
        try:
            rows = self.conn.execute(
                "SELECT * FROM paper_positions WHERE status='open'"
            ).fetchall()
            for r in rows:
                uid = str(r["user_id"])
                if uid not in self.positions:
                    self.positions[uid] = []
                self.positions[uid].append(self._row_to_dict(r))

            rows2 = self.conn.execute(
                "SELECT * FROM paper_positions WHERE status='closed'"
                " ORDER BY closed_at DESC LIMIT 200"
            ).fetchall()
            for r in rows2:
                uid = str(r["user_id"])
                if uid not in self.closed_positions:
                    self.closed_positions[uid] = []
                self.closed_positions[uid].append(self._row_to_dict(r))

            caps = self.conn.execute("SELECT * FROM paper_capitals").fetchall()
            for c in caps:
                self.capitals[str(c["user_id"])] = float(c["capital"])
        except Exception as e:
            logger.error(f"[PaperTrader._load] Erreur : {e}")

    def _row_to_dict(self, r) -> Dict:
        """Convertit une row psycopg2 en dict normalise."""
        return {
            "id":             r["id"],
            "symbol":         r["symbol"],
            "side":           r["side"] if r["side"] else "BUY",
            "entry_price":    float(r["entry_price"] or 0),
            "exit_price":     float(r["exit_price"]) if r["exit_price"] else None,
            "sl":             float(r["sl"]) if r["sl"] else None,
            "tp":             float(r["tp"]) if r["tp"] else None,
            "qty":            float(r["qty"] or 0),
            "leverage":       float(r["leverage"]) if r["leverage"] else 1.0,
            "fees_total":     float(r["fees_total"]) if r["fees_total"] else 0.0,
            "slippage":       float(r["slippage"]) if r["slippage"] else 0.0,
            "capital_before": float(r["capital_before"]) if r["capital_before"] else None,
            "capital_after":  float(r["capital_after"]) if r["capital_after"] else None,
            "current_price":  float(r["current_price"] or 0),
            "pnl_usdt":       float(r["pnl_usdt"] or 0),
            "pnl_pct":        float(r["pnl_pct"] or 0),
            "status":         r["status"],
            "exit_reason":    r["exit_reason"],
            "opened_at":      r["opened_at"],
            "closed_at":      r["closed_at"],
            "peak_price":     float(r["peak_price"]) if r["peak_price"] else float(r["entry_price"] or 0),
        }

    def _save_position(self, uid: str, pos: Dict):
        """Upsert d'une position dans la BDD."""
        try:
            self.conn.execute(
                """
                INSERT INTO paper_positions (
                    id, user_id, symbol, side, entry_price, exit_price,
                    sl, tp, qty, leverage, fees_total, slippage,
                    capital_before, capital_after,
                    current_price, pnl_usdt, pnl_pct,
                    status, exit_reason, opened_at, closed_at, peak_price
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (id) DO UPDATE SET
                    side           = excluded.side,
                    exit_price     = excluded.exit_price,
                    sl             = excluded.sl,
                    tp             = excluded.tp,
                    qty            = excluded.qty,
                    leverage       = excluded.leverage,
                    fees_total     = excluded.fees_total,
                    slippage       = excluded.slippage,
                    capital_before = excluded.capital_before,
                    capital_after  = excluded.capital_after,
                    current_price  = excluded.current_price,
                    pnl_usdt       = excluded.pnl_usdt,
                    pnl_pct        = excluded.pnl_pct,
                    status         = excluded.status,
                    exit_reason    = excluded.exit_reason,
                    closed_at      = excluded.closed_at,
                    peak_price     = excluded.peak_price
                """,
                (
                    pos["id"], int(uid), pos["symbol"], pos["side"],
                    pos["entry_price"], pos.get("exit_price"),
                    pos.get("sl"), pos.get("tp"),
                    pos["qty"], pos.get("leverage", 1.0),
                    pos.get("fees_total", 0.0), pos.get("slippage", 0.0),
                    pos.get("capital_before"), pos.get("capital_after"),
                    pos["current_price"], pos["pnl_usdt"], pos["pnl_pct"],
                    pos["status"], pos.get("exit_reason"),
                    pos["opened_at"], pos.get("closed_at"),
                    pos.get("peak_price", pos["entry_price"]),
                )
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"[PaperTrader._save_position] {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass

    def _save_capital(self, uid: str):
        """Upsert du capital d'un utilisateur."""
        try:
            self.conn.execute(
                """
                INSERT INTO paper_capitals (user_id, capital) VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET capital = excluded.capital
                """,
                (int(uid), self.capitals[uid])
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"[PaperTrader._save_capital] {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _uid(self, user_id) -> str:
        return str(user_id)

    @staticmethod
    def _calc_pnl(side: str, entry: float, exit_p: float,
                  qty: float, leverage: float) -> Tuple[float, float]:
        """
        Calcule le PnL brut (avant frais de sortie).

        Returns:
            (pnl_usdt, pnl_pct)
        """
        if entry <= 0:
            return 0.0, 0.0
        if side == "BUY":
            pnl_usdt = (exit_p - entry) * qty * leverage
            pnl_pct  = (exit_p - entry) / entry * 100 * leverage
        else:  # SELL / short
            pnl_usdt = (entry - exit_p) * qty * leverage
            pnl_pct  = (entry - exit_p) / entry * 100 * leverage
        return pnl_usdt, pnl_pct

    @staticmethod
    def _apply_slippage(price: float, side: str, slippage_pct: float) -> float:
        """
        Applique le slippage au prix d'execution.
        - Achat (BUY entree ou SELL sortie) : prix legerement plus haut
        - Vente (SELL entree ou BUY sortie) : prix legerement plus bas
        """
        factor = slippage_pct / 100.0
        if side == "BUY":
            return price * (1.0 + factor)
        else:
            return price * (1.0 - factor)

    # ------------------------------------------------------------------
    # API PUBLIQUE
    # ------------------------------------------------------------------

    def init_capital(self, user_id, amount: float = None):
        """Initialise le capital virtuel si inexistant."""
        uid = self._uid(user_id)
        if amount is None:
            amount = PAPER_DEFAULT_CAPITAL
        if uid not in self.capitals:
            self.capitals[uid] = amount
            self.positions.setdefault(uid, [])
            self.closed_positions.setdefault(uid, [])
            self._save_capital(uid)

    def reset_account(self, user_id, amount: float = 10000.0) -> float:
        """Réinitialise totalement le compte Paper Trading de l'utilisateur."""
        uid = self._uid(user_id)
        self.capitals[uid] = amount
        self.positions[uid] = []
        self.closed_positions[uid] = []

        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM paper_positions WHERE user_id = %s", (int(uid),))
                cur.execute("DELETE FROM paper_capitals WHERE user_id = %s", (int(uid),))
                cur.execute("INSERT INTO paper_capitals (user_id, capital) VALUES (%s, %s)", (int(uid), amount))
            self.conn.commit()
        except Exception as e:
            logger.error(f"[PaperTrader.reset_account] Erreur: {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass
        return amount

    def get_capital(self, user_id) -> float:
        return self.capitals.get(self._uid(user_id), PAPER_DEFAULT_CAPITAL)

    def open_position(
        self,
        user_id,
        symbol: str,
        entry_price: float,
        sl: float,
        tp: float,
        qty: float,
        side: str = "BUY",
        leverage: float = None,
        fees_pct: float = None,
        slippage_pct: float = None,
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Ouvre une nouvelle position paper trading.

        Returns:
            (position_dict, None)        en cas de succes
            (None, "message_erreur")     en cas d'echec
        """
        uid = self._uid(user_id)

        if leverage is None:
            leverage = PAPER_DEFAULT_LEVERAGE
        if fees_pct is None:
            fees_pct = PAPER_FEES_PCT
        if slippage_pct is None:
            slippage_pct = PAPER_SLIPPAGE_PCT

        side = side.upper()
        if side not in ("BUY", "SELL"):
            return None, f"Direction invalide : {side}"
        leverage = max(1.0, min(float(leverage), PAPER_MAX_LEVERAGE))
        if entry_price <= 0 or qty <= 0:
            return None, "Prix ou quantite invalide"

        if uid not in self.capitals:
            self.init_capital(user_id)
        self.positions.setdefault(uid, [])
        self.closed_positions.setdefault(uid, [])

        capital_before = self.capitals[uid]

        # Slippage a l'entree
        exec_price = self._apply_slippage(entry_price, side, slippage_pct)
        slip_amount = abs(exec_price - entry_price) * qty

        # Margin et frais d'entree
        notional  = exec_price * qty
        margin    = notional / leverage
        fee_entry = notional * (fees_pct / 100.0)
        cost      = margin + fee_entry

        if cost > capital_before:
            return None, (
                f"Capital insuffisant : besoin de {cost:.2f} USDT "
                f"(margin {margin:.2f} + frais {fee_entry:.2f}) "
                f"mais capital = {capital_before:.2f} USDT."
            )

        # Deduction des frais et de la margin du capital disponible
        self.capitals[uid] = capital_before - margin - fee_entry
        self._save_capital(uid)

        pos_id = str(int(time.time() * 1000))
        pos = {
            "id":             pos_id,
            "symbol":         symbol.upper(),
            "side":           side,
            "entry_price":    exec_price,
            "exit_price":     None,
            "sl":             sl,
            "tp":             tp,
            "qty":            qty,
            "leverage":       leverage,
            "fees_total":     fee_entry,
            "slippage":       slip_amount,
            "capital_before": capital_before,
            "capital_after":  None,
            "current_price":  exec_price,
            "pnl_usdt":       0.0,
            "pnl_pct":        0.0,
            "status":         "open",
            "exit_reason":    None,
            "opened_at":      time.time(),
            "closed_at":      None,
            "peak_price":     exec_price,
        }

        self.positions[uid].append(pos)
        self._save_position(uid, pos)

        logger.info(
            f"[PaperTrader] Ouverture {side} #{pos_id} {symbol} "
            f"@ {exec_price:.4f} | qty={qty:.6f} | lev={leverage}x | "
            f"margin={margin:.2f} | frais={fee_entry:.4f} | capital={self.capitals[uid]:.2f}"
        )
        return pos, None

    def close_position(
        self,
        user_id,
        position_id: str,
        exit_price: float,
        reason: str = "MANUAL",
        fees_pct: float = None,
        slippage_pct: float = None,
    ) -> Optional[Dict]:
        """
        Ferme une position ouverte au prix donne.

        Returns:
            La position cloturee, ou None si introuvable / deja fermee.
        """
        uid = self._uid(user_id)
        if fees_pct is None:
            fees_pct = PAPER_FEES_PCT
        if slippage_pct is None:
            slippage_pct = PAPER_SLIPPAGE_PCT

        pos = None
        for p in self.positions.get(uid, []):
            if p["id"] == position_id and p["status"] == "open":
                pos = p
                break

        if pos is None:
            logger.warning(
                f"[PaperTrader.close_position] Position {position_id} introuvable ou deja fermee."
            )
            return None

        # Slippage a la sortie (sens oppose de l'entree)
        exit_side_for_slip = "SELL" if pos["side"] == "BUY" else "BUY"
        exec_exit = self._apply_slippage(exit_price, exit_side_for_slip, slippage_pct)

        # PnL brut
        pnl_usdt, pnl_pct = self._calc_pnl(
            pos["side"], pos["entry_price"], exec_exit,
            pos["qty"], pos.get("leverage", 1.0)
        )

        # Frais de sortie
        notional_exit = exec_exit * pos["qty"]
        fee_exit  = notional_exit * (fees_pct / 100.0)
        fees_total = pos.get("fees_total", 0.0) + fee_exit

        # PnL net
        pnl_net = pnl_usdt - fee_exit

        # Margin liberee
        margin = pos["entry_price"] * pos["qty"] / pos.get("leverage", 1.0)

        # Nouveau capital = capital courant + margin + PnL net
        capital_now   = self.capitals.get(uid, PAPER_DEFAULT_CAPITAL)
        capital_after = max(0.0, capital_now + margin + pnl_net)

        # Mise a jour de la position
        pos["status"]        = "closed"
        pos["exit_price"]    = exec_exit
        pos["current_price"] = exec_exit
        pos["exit_reason"]   = reason
        pos["closed_at"]     = time.time()
        pos["pnl_usdt"]      = pnl_usdt
        pos["pnl_pct"]       = pnl_pct
        pos["fees_total"]    = fees_total
        pos["capital_after"] = capital_after

        # Mise a jour du capital
        self.capitals[uid] = capital_after
        self._save_capital(uid)

        # Deplacement vers closed_positions
        self.positions[uid] = [
            p for p in self.positions[uid] if p["id"] != position_id
        ]
        self.closed_positions.setdefault(uid, []).append(pos)
        self._save_position(uid, pos)

        logger.info(
            f"[PaperTrader] Cloture {pos['side']} #{position_id} {pos['symbol']} "
            f"@ {exec_exit:.4f} | PnL brut={pnl_usdt:.4f} | "
            f"frais sortie={fee_exit:.4f} | PnL net={pnl_net:.4f} | "
            f"capital={capital_after:.2f} | raison={reason}"
        )
        return pos

    def update_price(self, symbol: str, price: float):
        """
        Met a jour le prix courant et recalcule le PnL non realise
        pour toutes les positions ouvertes sur ce symbole.
        """
        symbol = symbol.upper()
        for uid, plist in self.positions.items():
            for pos in plist:
                if pos["symbol"] == symbol and pos["status"] == "open":
                    pos["current_price"] = price
                    pnl_usdt, pnl_pct = self._calc_pnl(
                        pos["side"], pos["entry_price"], price,
                        pos["qty"], pos.get("leverage", 1.0)
                    )
                    pos["pnl_usdt"] = pnl_usdt
                    pos["pnl_pct"]  = pnl_pct
                    if pos["side"] == "BUY":
                        if price > pos.get("peak_price", 0):
                            pos["peak_price"] = price
                    else:
                        if price < pos.get("peak_price", float("inf")):
                            pos["peak_price"] = price
                    self._save_position(uid, pos)

    def check_exits(self) -> List[Dict]:
        """
        Verifie SL et TP pour toutes les positions ouvertes.
        Compatible BUY et SELL. Met a jour le capital automatiquement.

        Returns:
            Liste des positions qui viennent d'etre cloturees.
        """
        closed = []
        for uid in list(self.positions.keys()):
            for pos in list(self.positions.get(uid, [])):
                if pos["status"] != "open":
                    continue

                price = pos["current_price"]
                side  = pos.get("side", "BUY")
                tp    = pos.get("tp")
                sl    = pos.get("sl")

                hit_tp = False
                hit_sl = False

                if side == "BUY":
                    if tp is not None and price >= tp:
                        hit_tp = True
                    elif sl is not None and price <= sl:
                        hit_sl = True
                else:  # SELL / short
                    if tp is not None and price <= tp:
                        hit_tp = True
                    elif sl is not None and price >= sl:
                        hit_sl = True

                if not hit_tp and not hit_sl:
                    continue

                exit_p = tp if hit_tp else sl
                reason = "TP" if hit_tp else "SL"

                # Prix SL/TP = prix garanti, pas de slippage supplementaire
                result = self.close_position(
                    int(uid), pos["id"], exit_p,
                    reason=reason,
                    slippage_pct=0.0,
                )
                if result is not None:
                    closed.append(result)

        return closed

    # ------------------------------------------------------------------
    # ACCESSEURS
    # ------------------------------------------------------------------

    def get_positions(self, user_id) -> List[Dict]:
        return self.positions.get(self._uid(user_id), [])

    def get_closed_positions(self, user_id) -> List[Dict]:
        uid = self._uid(user_id)
        if uid not in self.closed_positions:
            try:
                rows = self.conn.execute(
                    "SELECT * FROM paper_positions WHERE status='closed' AND user_id=%s"
                    " ORDER BY closed_at DESC LIMIT 200",
                    (int(uid),)
                ).fetchall()
                self.closed_positions[uid] = [self._row_to_dict(r) for r in rows]
            except Exception as e:
                logger.error(f"[PaperTrader.get_closed_positions] {e}")
                self.closed_positions[uid] = []
        return self.closed_positions.get(uid, [])

    def get_stats(self, user_id) -> Dict:
        """
        Retourne un recapitulatif des performances paper trading.

        capital : solde disponible (margin liberee + PnL net accumule)
        equity  : capital + PnL non realise des positions ouvertes
        """
        capital  = self.get_capital(user_id)
        closed   = self.get_closed_positions(user_id)
        open_pos = self.get_positions(user_id)

        # PnL net realise = pnl_usdt brut - fees_total (qui inclut entree+sortie)
        total_pnl = sum(
            p.get("pnl_usdt", 0) - p.get("fees_total", 0) for p in closed
        )
        wins     = sum(1 for p in closed if p.get("pnl_usdt", 0) > 0)
        total_cl = len(closed)

        unrealized = sum(p.get("pnl_usdt", 0) for p in open_pos)
        equity = capital + unrealized

        return {
            "capital":        round(capital, 4),
            "equity":         round(equity, 4),
            "total_pnl":      round(total_pnl, 4),
            "open_positions": len(open_pos),
            "total_trades":   total_cl + len(open_pos),
            "wins":           wins,
            "losses":         total_cl - wins,
            "win_rate":       round(wins / total_cl * 100, 2) if total_cl > 0 else 0.0,
        }


# =========================================================
# SINGLETON PARTAGÉ
# =========================================================
# Instance unique importée par bot_handlers.py et position_manager.py.
# Important : ne pas instancier PaperTrader() ailleurs dans le code, sinon
# chaque instance aurait son propre cache mémoire (self.positions, etc.)
# désynchronisé des autres, même si toutes lisent/écrivent la même base.
paper_trader = PaperTrader()
