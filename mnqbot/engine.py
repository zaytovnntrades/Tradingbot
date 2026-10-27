"""Bar-by-bar paper-trading simulator. Signals on bar close, fills on next bar open.

Conservative fill rules: if a bar touches both stop and target, the stop wins;
stop and market exits pay slippage; gaps fill at the open.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .config import Config
from .data import Bar, trading_day
from .risk import RiskManager
from .signals import Signal, SignalEngine


@dataclass
class Trade:
    entry_ts: datetime
    exit_ts: datetime
    side: str
    qty: int
    entry: float
    exit: float
    stop_initial: float
    target: float
    pnl: float
    r_multiple: float
    exit_reason: str
    score: int
    sweep_kind: str


@dataclass
class _Position:
    sig: Signal
    side: str
    qty: int
    entry: float
    stop: float
    target: float
    stop_initial: float
    risk_pts: float
    hard_stop: float
    entry_ts: datetime
    be_done: bool = False


@dataclass
class Result:
    trades: list[Trade] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    blocked: list[tuple[Signal, str]] = field(default_factory=list)
    daily: dict = field(default_factory=dict)          # trading day -> pnl
    final_balance: float = 0.0
    target_hit_on: object = None


class Backtester:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.engine = SignalEngine(cfg)
        self.risk = RiskManager(cfg)
        self._flatten = cfg.t("flatten_time")
        self._overnight = cfg.t("overnight_start")

    def _slip(self) -> float:
        return self.cfg.slippage_ticks * self.cfg.tick_size

    def _pnl(self, side: str, entry: float, exit_px: float, qty: int) -> float:
        d = 1 if side == "long" else -1
        return (exit_px - entry) * d * qty * self.cfg.point_value - 2 * self.cfg.commission_per_side * qty

    def _is_flatten_bar(self, bar: Bar) -> bool:
        return self._flatten <= bar.ts.time() < self._overnight

    def _fill(self, sig: Signal, bar: Bar, res: Result) -> _Position | None:
        cfg, risk = self.cfg, self.risk
        ok, why = risk.can_open(sig.bar_index + 1)
        if not ok:
            res.blocked.append((sig, why))
            return None
        if self._is_flatten_bar(bar):
            res.blocked.append((sig, "too close to flatten"))
            return None
        long = sig.side == "long"
        fill = bar.open + self._slip() if long else bar.open - self._slip()
        pts = fill - sig.stop if long else sig.stop - fill
        if pts <= 0 or pts > cfg.max_stop_atr * sig.atr:
            res.blocked.append((sig, "gap invalidated setup"))
            return None
        qty = risk.size(pts)
        if qty < 1:
            res.blocked.append((sig, "size < 1 contract"))
            return None
        target = fill + cfg.reward_risk * pts if long else fill - cfg.reward_risk * pts
        hard = risk.hard_stop_price(sig.side, fill, qty)
        stop = max(sig.stop, hard) if long else min(sig.stop, hard)
        return _Position(sig, sig.side, qty, fill, stop, target, sig.stop, pts, hard, bar.ts)

    def _manage(self, p: _Position, bar: Bar) -> tuple[float, str] | None:
        slip, long = self._slip(), p.side == "long"
        stop_reason = "hard daily stop" if p.stop == p.hard_stop else ("breakeven" if p.be_done else "stop")
        if long:
            if bar.open <= p.stop:
                return bar.open - slip, stop_reason + " (gap)"
            if bar.low <= p.stop:
                return p.stop - slip, stop_reason
            if bar.open >= p.target:
                return bar.open, "target (gap)"
            if bar.high >= p.target:
                return p.target, "target"
        else:
            if bar.open >= p.stop:
                return bar.open + slip, stop_reason + " (gap)"
            if bar.high >= p.stop:
                return p.stop + slip, stop_reason
            if bar.open <= p.target:
                return bar.open, "target (gap)"
            if bar.low <= p.target:
                return p.target, "target"
        if self._is_flatten_bar(bar):
            return (bar.close - slip if long else bar.close + slip), "end-of-day flatten"
        # breakeven takes effect from the next bar (no intrabar path assumptions)
        be = self.cfg.breakeven_at_r
        if be > 0 and not p.be_done:
            tick = self.cfg.tick_size
            if long and bar.high >= p.entry + be * p.risk_pts:
                p.stop, p.be_done = max(p.stop, p.entry + tick), True
            elif not long and bar.low <= p.entry - be * p.risk_pts:
                p.stop, p.be_done = min(p.stop, p.entry - tick), True
        return None

    def run(self, bars: list[Bar]) -> Result:
        res = Result()
        pos: _Position | None = None
        pending: Signal | None = None
        for idx, bar in enumerate(bars):
            key = trading_day(bar.ts)
            if key != self.risk.day_key:
                pending = None
                self.risk.roll_day(key)
                res.daily.setdefault(key, 0.0)

            if pending is not None and pos is None:
                pos = self._fill(pending, bar, res)
                pending = None

            if pos is not None:
                out = self._manage(pos, bar)
                if out:
                    px, reason = out
                    pnl = self._pnl(pos.side, pos.entry, px, pos.qty)
                    risk_dollars = pos.risk_pts * pos.qty * self.cfg.point_value
                    res.trades.append(Trade(pos.entry_ts, bar.ts, pos.side, pos.qty, round(pos.entry, 2),
                                            round(px, 2), pos.stop_initial, round(pos.target, 2),
                                            round(pnl, 2), round(pnl / risk_dollars, 2), reason,
                                            pos.sig.score, pos.sig.sweep_kind))
                    self.risk.record(pnl, idx)
                    res.daily[key] = res.daily.get(key, 0.0) + pnl
                    if self.risk.target_hit and res.target_hit_on is None:
                        res.target_hit_on = key
                    pos = None

            sig = self.engine.update(bar)
            if sig is not None:
                res.signals.append(sig)
                if pos is None and pending is None:
                    ok, why = self.risk.can_open(idx)
                    if ok:
                        pending = sig
                    else:
                        res.blocked.append((sig, why))
        res.final_balance = self.risk.balance
        return res
