"""Bar loading (TradingView CSV export) and a synthetic MNQ data generator."""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass
class Bar:
    ts: datetime      # tz-aware, bar OPEN time, exchange tz (America/New_York)
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def trading_day(ts: datetime) -> date:
    """CME trading day: a session that opens 18:00 ET belongs to the next date."""
    return (ts + timedelta(hours=6)).date()


def _parse_ts(raw: str, tz: ZoneInfo, data_tz: ZoneInfo) -> datetime:
    raw = raw.strip()
    try:
        num = float(raw)
        if num > 1e12:          # milliseconds
            num /= 1000.0
        return datetime.fromtimestamp(num, tz=timezone.utc).astimezone(tz)
    except ValueError:
        pass
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=data_tz)
    return dt.astimezone(tz)


def load_csv(path: str, tz: str = "America/New_York", data_tz: str | None = None) -> list[Bar]:
    """Load OHLCV bars. Works with TradingView 'Export chart data' files.

    Accepted time columns: time / timestamp / datetime, or date + time.
    Numeric times are treated as unix epoch (UTC). Naive ISO strings are read
    in `data_tz` (default: the exchange tz).
    """
    ztz = ZoneInfo(tz)
    zdata = ZoneInfo(data_tz) if data_tz else ztz
    bars: list[Bar] = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        cols = {c.lower().strip(): c for c in (reader.fieldnames or [])}

        def col(*names):
            for n in names:
                if n in cols:
                    return cols[n]
            return None

        tcol = col("time", "timestamp", "datetime", "date_time")
        dcol = col("date")
        o, h, l, c = col("open"), col("high"), col("low"), col("close")
        v = col("volume", "vol")
        if not all([o, h, l, c]) or not (tcol or dcol):
            raise ValueError(f"CSV needs time/open/high/low/close columns, got {reader.fieldnames}")
        for row in reader:
            if not row.get(c):
                continue
            raw_t = row[tcol] if tcol else row[dcol]
            if dcol and tcol and dcol != tcol and ":" not in raw_t:
                raw_t = f"{row[dcol]} {row[tcol]}"
            bars.append(Bar(_parse_ts(raw_t, ztz, zdata), float(row[o]), float(row[h]),
                            float(row[l]), float(row[c]), float(row[v]) if v and row.get(v) else 0.0))
    bars.sort(key=lambda b: b.ts)
    return bars


def write_csv(bars: list[Bar], path: str) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time", "open", "high", "low", "close", "volume"])
        for b in bars:
            w.writerow([b.ts.isoformat(), b.open, b.high, b.low, b.close, int(b.volume)])


def _round_tick(x: float, tick: float = 0.25) -> float:
    return round(round(x / tick) * tick, 2)


def generate_synthetic(days: int = 60, seed: int = 7, start_price: float = 25_000.0,
                       minutes: int = 5, tz: str = "America/New_York") -> list[Bar]:
    """Random-walk MNQ-like bars with an RTH volatility profile and stop-run spikes.

    For plumbing tests and demos only -- results on synthetic data say nothing
    about real-market edge.
    """
    rng = random.Random(seed)
    ztz = ZoneInfo(tz)
    bars: list[Bar] = []
    price = start_price
    d = date(2026, 1, 5)
    made = 0
    while made < days:
        if d.weekday() < 5:
            start = datetime(d.year, d.month, d.day, 18, 0, tzinfo=ztz) - timedelta(days=1)
            end = datetime(d.year, d.month, d.day, 17, 0, tzinfo=ztz)
            drift = rng.gauss(0, 0.02)
            t = start
            while t < end:
                hm = t.hour * 60 + t.minute
                rth = 570 <= hm < 960
                base_vol = 9.0 if rth else 3.5
                if 570 <= hm < 630:
                    base_vol *= 1.6                      # opening hour
                sigma = base_vol * math.sqrt(minutes / 5)
                o = price
                c = o + rng.gauss(drift * sigma, sigma)
                wick_up = abs(rng.gauss(0, sigma * 0.6))
                wick_dn = abs(rng.gauss(0, sigma * 0.6))
                if rth and rng.random() < 0.04:          # stop run: long wick, close back
                    if rng.random() < 0.5:
                        wick_dn += sigma * rng.uniform(2, 4)
                    else:
                        wick_up += sigma * rng.uniform(2, 4)
                h = max(o, c) + wick_up
                lo = min(o, c) - wick_dn
                vol = max(1.0, rng.gauss(4000 if rth else 600, 800 if rth else 150))
                if wick_up + wick_dn > 3 * sigma:
                    vol *= 2.0
                bars.append(Bar(t, _round_tick(o), _round_tick(h), _round_tick(lo), _round_tick(c), vol))
                price = _round_tick(c)
                t += timedelta(minutes=minutes)
            made += 1
        d += timedelta(days=1)
    return bars
