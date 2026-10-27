"""Streaming (bar-by-bar) indicators that mirror TradingView's ta.* functions."""

from __future__ import annotations

from collections import deque


class EMA:
    """ta.ema: seeded with an SMA of the first `length` values."""

    def __init__(self, length: int):
        self.length = length
        self.alpha = 2.0 / (length + 1)
        self._seed: list[float] = []
        self.value: float | None = None

    def update(self, x: float) -> float | None:
        if self.value is None:
            self._seed.append(x)
            if len(self._seed) == self.length:
                self.value = sum(self._seed) / self.length
            return self.value
        self.value += self.alpha * (x - self.value)
        return self.value


class RMA:
    """Wilder's moving average (ta.rma), SMA-seeded."""

    def __init__(self, length: int):
        self.length = length
        self._seed: list[float] = []
        self.value: float | None = None

    def update(self, x: float) -> float | None:
        if self.value is None:
            self._seed.append(x)
            if len(self._seed) == self.length:
                self.value = sum(self._seed) / self.length
            return self.value
        self.value = (self.value * (self.length - 1) + x) / self.length
        return self.value


class ATR:
    def __init__(self, length: int):
        self._rma = RMA(length)
        self._prev_close: float | None = None
        self.value: float | None = None

    def update(self, high: float, low: float, close: float) -> float | None:
        if self._prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - self._prev_close), abs(low - self._prev_close))
        self._prev_close = close
        self.value = self._rma.update(tr)
        return self.value


class RSI:
    def __init__(self, length: int):
        self._up = RMA(length)
        self._dn = RMA(length)
        self._prev: float | None = None
        self.value: float | None = None

    def update(self, close: float) -> float | None:
        if self._prev is None:
            self._prev = close
            return None
        change = close - self._prev
        self._prev = close
        up = self._up.update(max(change, 0.0))
        dn = self._dn.update(max(-change, 0.0))
        if up is None or dn is None:
            return None
        if dn == 0:
            self.value = 100.0
        elif up == 0:
            self.value = 0.0
        else:
            self.value = 100.0 - 100.0 / (1.0 + up / dn)
        return self.value


class SMA:
    def __init__(self, length: int):
        self.length = length
        self._buf: deque[float] = deque(maxlen=length)
        self._sum = 0.0
        self.value: float | None = None

    def update(self, x: float) -> float | None:
        if len(self._buf) == self.length:
            self._sum -= self._buf[0]
        self._buf.append(x)
        self._sum += x
        self.value = self._sum / self.length if len(self._buf) == self.length else None
        return self.value


class SessionVWAP:
    """VWAP of hlc3 that resets each trading day (like ta.vwap on futures)."""

    def __init__(self):
        self._key = None
        self._pv = 0.0
        self._v = 0.0
        self.value: float | None = None

    def update(self, key, high: float, low: float, close: float, volume: float) -> float | None:
        if key != self._key:
            self._key, self._pv, self._v = key, 0.0, 0.0
        tp = (high + low + close) / 3.0
        vol = max(volume, 0.0)
        self._pv += tp * vol
        self._v += vol
        self.value = self._pv / self._v if self._v > 0 else tp
        return self.value
