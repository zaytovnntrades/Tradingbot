"""All tunable parameters in one place. Override any field with a JSON file."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from datetime import time


@dataclass
class Config:
    # --- Account / prop-style rules ($100k simulated) ---
    starting_balance: float = 100_000.0
    profit_target: float = 7_000.0          # account-level goal; trading halts once hit
    stop_at_profit_target: bool = True
    max_daily_loss: float = 3_000.0         # HARD limit, never sized past
    daily_loss_buffer: float = 250.0        # stop opening trades this far before the hard limit
    risk_per_trade: float = 500.0           # 0.5% of $100k ("balanced")
    reduced_risk_after_losses: int = 2      # after N straight losses...
    reduced_risk_factor: float = 0.5        # ...risk this fraction per trade
    max_trades_per_day: int = 6
    max_consecutive_losses: int = 3         # day ends after N straight losses
    giveback_activate: float = 1_500.0      # once the day is up this much...
    giveback_pct: float = 0.5               # ...stop if it gives back this fraction of the peak
    cooldown_bars_after_loss: int = 3

    # --- Contract (CME Micro E-mini Nasdaq-100) ---
    point_value: float = 2.0                # $2 per index point
    tick_size: float = 0.25                 # $0.50 per tick
    max_contracts: int = 15
    commission_per_side: float = 0.85       # per contract, incl. exchange fees (estimate)
    slippage_ticks: int = 1                 # applied to market entries and stop exits

    # --- Stops / targets (volatility based) ---
    atr_len: int = 14
    atr_stop_mult: float = 1.0              # stop is at least this many ATRs from entry
    atr_buffer_mult: float = 0.25           # extra ATR beyond the sweep wick
    max_stop_atr: float = 3.0               # skip setups needing a wider stop
    min_stop_points: float = 6.0
    reward_risk: float = 2.0
    breakeven_at_r: float = 1.0             # move stop to entry+1 tick at +1R (0 disables)

    # --- Signal engine ---
    ema_fast: int = 9
    ema_mid: int = 21
    ema_slow: int = 50
    ema_trend: int = 200
    swing_len: int = 5                      # pivot strength (bars each side)
    level_max_age: int = 400                # bars a liquidity level stays active
    max_levels: int = 20
    min_wick_ratio: float = 0.25            # rejection wick / bar range on the sweep bar
    impulse_atr_mult: float = 1.5           # body size that defines an impulsive move
    base_max_body_atr: float = 0.6          # base candle must be small
    max_zones: int = 6
    zone_max_age: int = 300
    rsi_len: int = 14
    rsi_low: float = 35.0
    rsi_high: float = 65.0
    vol_len: int = 20
    vol_mult: float = 1.5
    min_score: int = 2                      # confluence points required (0-4)

    # --- Session (exchange local time, America/New_York) ---
    timezone: str = "America/New_York"
    rth_start: str = "09:30"
    rth_end: str = "16:00"
    entry_start: str = "09:35"
    last_entry: str = "15:30"               # no new signals from this bar on
    flatten_time: str = "15:50"             # flatten on the close of the first bar starting here
    overnight_start: str = "18:00"          # CME trading day begins

    def t(self, name: str) -> time:
        hh, mm = getattr(self, name).split(":")
        return time(int(hh), int(mm))

    def validate(self) -> None:
        if self.risk_per_trade + self.daily_loss_buffer > self.max_daily_loss:
            raise ValueError("risk_per_trade + daily_loss_buffer must not exceed max_daily_loss")
        if self.max_daily_loss <= 0 or self.risk_per_trade <= 0:
            raise ValueError("risk values must be positive")
        if self.reward_risk <= 0:
            raise ValueError("reward_risk must be positive")
        for name in ("rth_start", "rth_end", "entry_start", "last_entry", "flatten_time", "overnight_start"):
            self.t(name)

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(path: str | None = None) -> Config:
    cfg = Config()
    if path:
        with open(path) as fh:
            overrides = json.load(fh)
        known = {f.name for f in fields(Config)}
        unknown = set(overrides) - known
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        for k, v in overrides.items():
            setattr(cfg, k, v)
    cfg.validate()
    return cfg
