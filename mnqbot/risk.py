"""Risk safeguards: sizing, hard daily loss, lockouts, profit target."""

from __future__ import annotations

import math

from .config import Config


class RiskManager:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.balance = cfg.starting_balance
        self.total_pnl = 0.0
        self.target_hit = False
        self.day_key = None
        self.day_pnl = 0.0
        self.day_peak = 0.0
        self.trades_today = 0
        self.consec_losses = 0
        self.lock_reason: str | None = None
        self.cooldown_until = -1

    def roll_day(self, key) -> None:
        self.day_key = key
        self.day_pnl = 0.0
        self.day_peak = 0.0
        self.trades_today = 0
        self.consec_losses = 0
        self.lock_reason = None
        self.cooldown_until = -1

    def daily_room(self) -> float:
        """Dollars left before the HARD daily loss limit."""
        return self.cfg.max_daily_loss + self.day_pnl

    def can_open(self, bar_index: int) -> tuple[bool, str]:
        c = self.cfg
        if self.target_hit and c.stop_at_profit_target:
            return False, "profit target reached"
        if self.lock_reason:
            return False, self.lock_reason
        if self.day_pnl <= -(c.max_daily_loss - c.daily_loss_buffer):
            self.lock_reason = "daily loss limit"
            return False, self.lock_reason
        if self.trades_today >= c.max_trades_per_day:
            return False, "max trades per day"
        if self.consec_losses >= c.max_consecutive_losses:
            self.lock_reason = "consecutive losses"
            return False, self.lock_reason
        if self.day_peak >= c.giveback_activate and self.day_pnl <= self.day_peak * (1 - c.giveback_pct):
            self.lock_reason = "profit give-back"
            return False, self.lock_reason
        if bar_index < self.cooldown_until:
            return False, "cooldown after loss"
        return True, "ok"

    def cost_per_contract(self, stop_points: float) -> float:
        c = self.cfg
        return (stop_points * c.point_value + 2 * c.commission_per_side
                + c.slippage_ticks * c.tick_size * c.point_value)

    def risk_budget(self) -> float:
        c = self.cfg
        risk = c.risk_per_trade
        if self.consec_losses >= c.reduced_risk_after_losses:
            risk *= c.reduced_risk_factor
        return max(0.0, min(risk, self.daily_room() - c.daily_loss_buffer))

    def size(self, stop_points: float) -> int:
        if stop_points <= 0:
            return 0
        n = math.floor(self.risk_budget() / self.cost_per_contract(stop_points))
        return max(0, min(n, self.cfg.max_contracts))

    def hard_stop_price(self, side: str, entry: float, qty: int) -> float:
        """Price at which this trade alone would breach the hard daily limit."""
        c = self.cfg
        room = self.daily_room() - 2 * c.commission_per_side * qty
        pts = room / (qty * c.point_value) - c.slippage_ticks * c.tick_size
        pts = math.floor(pts / c.tick_size) * c.tick_size
        return entry - pts if side == "long" else entry + pts

    def record(self, pnl: float, bar_index: int) -> None:
        c = self.cfg
        self.balance += pnl
        self.total_pnl += pnl
        self.day_pnl += pnl
        self.day_peak = max(self.day_peak, self.day_pnl)
        self.trades_today += 1
        if pnl < 0:
            self.consec_losses += 1
            self.cooldown_until = bar_index + c.cooldown_bars_after_loss
        else:
            self.consec_losses = 0
        if self.total_pnl >= c.profit_target:
            self.target_hit = True
