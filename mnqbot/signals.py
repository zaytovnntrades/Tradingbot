"""Signal engine: liquidity sweep + supply/demand + moving-average confluence."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from .config import Config
from .data import Bar, trading_day
from .indicators import ATR, EMA, RSI, SMA, SessionVWAP
from .structure import Level, LiquidityBook, PivotDetector, ZoneBook


@dataclass
class Signal:
    ts: datetime
    bar_index: int
    side: str                 # "long" / "short"
    ref_price: float          # close of the signal bar (entry is next bar's open)
    stop: float
    target_est: float
    stop_points: float
    atr: float
    score: int
    sweep_kind: str
    sweep_price: float
    reasons: list[str] = field(default_factory=list)

    def describe(self) -> str:
        arrow = "BUY " if self.side == "long" else "SELL"
        return (f"{self.ts:%Y-%m-%d %H:%M} {arrow} ~{self.ref_price:.2f}  SL {self.stop:.2f} "
                f"({self.stop_points:.2f} pts)  TP {self.target_est:.2f}  score {self.score}/4  "
                f"[{self.sweep_kind} sweep @ {self.sweep_price:.2f}; {', '.join(self.reasons)}]")


class SignalEngine:
    """Feed closed bars in order; returns a Signal on the bar that qualifies."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.atr = ATR(cfg.atr_len)
        self.ema_f, self.ema_m = EMA(cfg.ema_fast), EMA(cfg.ema_mid)
        self.ema_s, self.ema_t = EMA(cfg.ema_slow), EMA(cfg.ema_trend)
        self.rsi = RSI(cfg.rsi_len)
        self.vol_avg = SMA(cfg.vol_len)
        self.vwap = SessionVWAP()
        self.pivots = PivotDetector(cfg.swing_len)
        self.liq = LiquidityBook(cfg.max_levels, cfg.level_max_age)
        self.zones = ZoneBook(cfg.max_zones, cfg.zone_max_age, cfg.impulse_atr_mult, cfg.base_max_body_atr)
        self._rsi_hist: deque[float] = deque(maxlen=3)
        self._prev: tuple | None = None
        self.i = -1
        self._day = None
        self._day_hi = self._day_lo = None
        self.pdh = self.pdl = None
        self._on_hi = self._on_lo = None
        self._rth_seeded = False
        self._t = {n: cfg.t(n) for n in ("rth_start", "rth_end", "entry_start", "last_entry")}

    # -- helpers --------------------------------------------------------
    def in_rth(self, ts: datetime) -> bool:
        return self._t["rth_start"] <= ts.time() < self._t["rth_end"]

    def in_entry_window(self, ts: datetime) -> bool:
        return self._t["entry_start"] <= ts.time() < self._t["last_entry"]

    def _roll_day(self, key) -> None:
        if self._day is not None:
            self.pdh, self.pdl = self._day_hi, self._day_lo
        self._day = key
        self._day_hi = self._day_lo = None
        self._on_hi = self._on_lo = None
        self._rth_seeded = False

    # -- main -----------------------------------------------------------
    def update(self, bar: Bar) -> Signal | None:
        cfg = self.cfg
        self.i += 1
        i = self.i
        key = trading_day(bar.ts)
        if key != self._day:
            self._roll_day(key)
        self._day_hi = bar.high if self._day_hi is None else max(self._day_hi, bar.high)
        self._day_lo = bar.low if self._day_lo is None else min(self._day_lo, bar.low)
        rth = self.in_rth(bar.ts)
        overnight = bar.ts.time() >= cfg.t("overnight_start") or bar.ts.time() < self._t["rth_start"]
        if overnight:
            self._on_hi = bar.high if self._on_hi is None else max(self._on_hi, bar.high)
            self._on_lo = bar.low if self._on_lo is None else min(self._on_lo, bar.low)

        # seed session liquidity at the RTH open
        if rth and not self._rth_seeded:
            self._rth_seeded = True
            for price, kind, hi in ((self.pdh, "PDH", True), (self.pdl, "PDL", False),
                                    (self._on_hi, "ONH", True), (self._on_lo, "ONL", False)):
                if price is not None:
                    (self.liq.add_high if hi else self.liq.add_low)(Level(price, kind, i))

        atr = self.atr.update(bar.high, bar.low, bar.close)
        ema_f = self.ema_f.update(bar.close)
        ema_m = self.ema_m.update(bar.close)
        ema_s = self.ema_s.update(bar.close)
        self.ema_t.update(bar.close)
        rsi = self.rsi.update(bar.close)
        if rsi is not None:
            self._rsi_hist.append(rsi)
        vol_avg = self.vol_avg.update(bar.volume)
        self.vwap.update(key, bar.high, bar.low, bar.close, bar.volume)

        in_demand, in_supply = self.zones.touches(bar.high, bar.low)
        bull, bear = self.liq.check(bar.high, bar.low, bar.close, i)
        self.zones.update(i, bar.open, bar.high, bar.low, bar.close, self._prev, atr)
        self._prev = (bar.open, bar.high, bar.low, bar.close)

        ph, pl = self.pivots.update(bar.high, bar.low)
        if ph is not None:
            self.liq.add_high(Level(ph, "swing", i))
        if pl is not None:
            self.liq.add_low(Level(pl, "swing", i))

        if atr is None or ema_s is None or rsi is None or not self.in_entry_window(bar.ts):
            return None
        if bull and bear:               # outside bar that ran both sides: ambiguous
            return None

        rng = bar.high - bar.low
        vol_spike = vol_avg is not None and bar.volume > vol_avg * cfg.vol_mult
        if bull:
            wick = min(bar.open, bar.close) - bar.low
            if rng <= 0 or wick / rng < cfg.min_wick_ratio:
                return None
            reasons, score = [], 0
            if in_demand:
                score += 1; reasons.append("demand zone")
            if ema_m > ema_s:
                score += 1; reasons.append("EMA21>EMA50")
            if bar.close > ema_f:
                score += 1; reasons.append("reclaimed EMA9")
            if min(self._rsi_hist) < cfg.rsi_low or vol_spike:
                score += 1; reasons.append("RSI exhaustion" if min(self._rsi_hist) < cfg.rsi_low else "volume spike")
            return self._build("long", bar, i, atr, score, bull, reasons)
        if bear:
            wick = bar.high - max(bar.open, bar.close)
            if rng <= 0 or wick / rng < cfg.min_wick_ratio:
                return None
            reasons, score = [], 0
            if in_supply:
                score += 1; reasons.append("supply zone")
            if ema_m < ema_s:
                score += 1; reasons.append("EMA21<EMA50")
            if bar.close < ema_f:
                score += 1; reasons.append("lost EMA9")
            if max(self._rsi_hist) > cfg.rsi_high or vol_spike:
                score += 1; reasons.append("RSI exhaustion" if max(self._rsi_hist) > cfg.rsi_high else "volume spike")
            return self._build("short", bar, i, atr, score, bear, reasons)
        return None

    def _build(self, side: str, bar: Bar, i: int, atr: float, score: int, lvl: Level,
               reasons: list[str]) -> Signal | None:
        cfg = self.cfg
        if score < cfg.min_score:
            return None
        entry = bar.close
        if side == "long":
            structural = bar.low - cfg.atr_buffer_mult * atr
            stop = min(structural, entry - cfg.atr_stop_mult * atr, entry - cfg.min_stop_points)
            pts = entry - stop
        else:
            structural = bar.high + cfg.atr_buffer_mult * atr
            stop = max(structural, entry + cfg.atr_stop_mult * atr, entry + cfg.min_stop_points)
            pts = stop - entry
        if pts > cfg.max_stop_atr * atr:
            return None
        tick = cfg.tick_size
        stop = round(round(stop / tick) * tick, 2)
        pts = abs(entry - stop)
        target = entry + cfg.reward_risk * pts if side == "long" else entry - cfg.reward_risk * pts
        return Signal(bar.ts, i, side, entry, stop, round(round(target / tick) * tick, 2), pts, atr,
                      score, lvl.kind, lvl.price, reasons)
