"""Market structure: swing pivots, liquidity levels (sweeps) and supply/demand zones."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class Level:
    price: float
    kind: str          # "swing", "PDH", "PDL", "ONH", "ONL"
    bar: int           # bar index where the level became active


@dataclass
class Zone:
    top: float
    bottom: float
    side: str          # "demand" or "supply"
    bar: int


class PivotDetector:
    """Confirms a swing high/low `n` bars after it prints (no lookahead)."""

    def __init__(self, n: int):
        self.n = n
        self._win: deque[tuple[float, float]] = deque(maxlen=2 * n + 1)

    def update(self, high: float, low: float) -> tuple[float | None, float | None]:
        self._win.append((high, low))
        if len(self._win) < self._win.maxlen:
            return None, None
        highs = [h for h, _ in self._win]
        lows = [lo for _, lo in self._win]
        c_hi, c_lo = highs[self.n], lows[self.n]
        right_hi, right_lo = highs[self.n + 1:], lows[self.n + 1:]
        ph = c_hi if c_hi == max(highs) and all(c_hi > h for h in right_hi) else None
        pl = c_lo if c_lo == min(lows) and all(c_lo < lo for lo in right_lo) else None
        return ph, pl


class LiquidityBook:
    """Resting liquidity: stops sit beyond swing points and prior-session extremes.

    A *sweep* is a bar that trades through a level and closes back on the
    original side -- the stops were run and price was rejected.
    """

    def __init__(self, max_levels: int, max_age: int):
        self.max_levels = max_levels
        self.max_age = max_age
        self.highs: list[Level] = []   # buy-side liquidity (above)
        self.lows: list[Level] = []    # sell-side liquidity (below)

    def add_high(self, lvl: Level) -> None:
        self.highs.append(lvl)
        if len(self.highs) > self.max_levels:
            self.highs.pop(0)

    def add_low(self, lvl: Level) -> None:
        self.lows.append(lvl)
        if len(self.lows) > self.max_levels:
            self.lows.pop(0)

    def check(self, high: float, low: float, close: float, bar: int) -> tuple[Level | None, Level | None]:
        """Returns (bullish sweep of a low, bearish sweep of a high) for this bar."""
        bull: Level | None = None
        keep: list[Level] = []
        for lvl in self.lows:
            if bar - lvl.bar > self.max_age:
                continue
            if low < lvl.price and close > lvl.price:
                if bull is None or lvl.price < bull.price:
                    bull = lvl
                continue
            if close < lvl.price:          # broken and accepted: no longer liquidity
                continue
            keep.append(lvl)
        self.lows = keep

        bear: Level | None = None
        keep = []
        for lvl in self.highs:
            if bar - lvl.bar > self.max_age:
                continue
            if high > lvl.price and close < lvl.price:
                if bear is None or lvl.price > bear.price:
                    bear = lvl
                continue
            if close > lvl.price:
                continue
            keep.append(lvl)
        self.highs = keep
        return bull, bear


class ZoneBook:
    """Supply/demand zones = the small base candle before an impulsive candle."""

    def __init__(self, max_zones: int, max_age: int, impulse_mult: float, base_max_body: float):
        self.max_zones = max_zones
        self.max_age = max_age
        self.impulse_mult = impulse_mult
        self.base_max_body = base_max_body
        self.demand: list[Zone] = []
        self.supply: list[Zone] = []

    @staticmethod
    def _overlaps(z: Zone, high: float, low: float) -> bool:
        return low <= z.top and high >= z.bottom

    def touches(self, high: float, low: float) -> tuple[Zone | None, Zone | None]:
        d = next((z for z in reversed(self.demand) if self._overlaps(z, high, low)), None)
        s = next((z for z in reversed(self.supply) if self._overlaps(z, high, low)), None)
        return d, s

    def update(self, bar: int, o: float, h: float, lo: float, c: float, prev: tuple | None,
               atr: float | None) -> None:
        # invalidate zones that price closed through, and old zones
        self.demand = [z for z in self.demand if c >= z.bottom and bar - z.bar <= self.max_age]
        self.supply = [z for z in self.supply if c <= z.top and bar - z.bar <= self.max_age]
        if atr is None or prev is None:
            return
        po, ph, pl, pc = prev
        body = abs(c - o)
        base_ok = abs(pc - po) <= self.base_max_body * atr
        if body >= self.impulse_mult * atr and base_ok:
            if c > o:
                self.demand.append(Zone(ph, pl, "demand", bar - 1))
                if len(self.demand) > self.max_zones:
                    self.demand.pop(0)
            else:
                self.supply.append(Zone(ph, pl, "supply", bar - 1))
                if len(self.supply) > self.max_zones:
                    self.supply.pop(0)
