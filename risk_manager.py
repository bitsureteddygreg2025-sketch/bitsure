from dataclasses import dataclass
from typing import Optional, Tuple


DEFAULT_RISK_PERCENTAGE = 0.01
MAX_RISK_PERCENTAGE = 0.02


@dataclass(frozen=True)
class PositionSizing:
    qty: float
    risk_amount: float
    sl_distance: float
    notional: float
    margin_required: float
    risk_percentage: float


class RiskManager:
    @staticmethod
    def normalize_risk_percentage(risk_percentage: Optional[float]) -> float:
        if risk_percentage is None:
            return DEFAULT_RISK_PERCENTAGE
        risk = float(risk_percentage)
        if risk > 1:
            risk = risk / 100.0
        return max(0.0, min(risk, MAX_RISK_PERCENTAGE))

    @staticmethod
    def calculate_position_size(
        capital: float,
        entry_price: float,
        sl: float,
        leverage: float = 1.0,
        risk_percentage: Optional[float] = None,
    ) -> Tuple[Optional[PositionSizing], Optional[str]]:
        risk = RiskManager.normalize_risk_percentage(risk_percentage)
        if capital <= 0:
            return None, "Capital invalide"
        if entry_price <= 0:
            return None, "Prix d'entree invalide"
        if leverage <= 0:
            return None, "Levier invalide"
        if sl is None or sl <= 0:
            return None, "Stop Loss invalide"
        if risk <= 0:
            return None, "Risque par trade invalide"

        sl_distance = abs(entry_price - sl)
        if sl_distance <= 0:
            return None, "Distance SL invalide"

        risk_amount = capital * risk
        qty = risk_amount / sl_distance
        notional = qty * entry_price
        margin_required = notional / leverage

        if qty <= 0 or notional <= 0 or margin_required <= 0:
            return None, "Taille de position incoherente"
        if margin_required > capital:
            scale = capital / margin_required
            qty *= scale
            notional = qty * entry_price
            margin_required = capital
            risk_amount = qty * sl_distance
            if qty <= 0:
                return None, "Capital insuffisant pour cette distance SL"

        return PositionSizing(
            qty=qty,
            risk_amount=risk_amount,
            sl_distance=sl_distance,
            notional=notional,
            margin_required=margin_required,
            risk_percentage=risk,
        ), None
