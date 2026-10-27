"""Performance summary and CSV output."""

from __future__ import annotations

import csv
import os
from dataclasses import asdict

from .config import Config
from .engine import Result


def summarize(res: Result, cfg: Config) -> dict:
    t = res.trades
    wins = [x.pnl for x in t if x.pnl > 0]
    losses = [x.pnl for x in t if x.pnl <= 0]
    equity, peak, max_dd = cfg.starting_balance, cfg.starting_balance, 0.0
    for x in t:
        equity += x.pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    days = [v for v in res.daily.values()]
    traded_days = sum(1 for v in days if v != 0)
    return {
        "trades": len(t),
        "win_rate": round(100 * len(wins) / len(t), 1) if t else 0.0,
        "net_pnl": round(sum(x.pnl for x in t), 2),
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) else float("inf") if wins else 0.0,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0.0,
        "expectancy_R": round(sum(x.r_multiple for x in t) / len(t), 2) if t else 0.0,
        "max_drawdown": round(max_dd, 2),
        "worst_day": round(min(days), 2) if days else 0.0,
        "best_day": round(max(days), 2) if days else 0.0,
        "days": len(days),
        "traded_days": traded_days,
        "daily_limit_breaches": sum(1 for v in days if v <= -cfg.max_daily_loss),
        "final_balance": round(res.final_balance, 2),
        "profit_target": cfg.profit_target,
        "target_hit_on": str(res.target_hit_on) if res.target_hit_on else "not reached",
        "signals": len(res.signals),
        "signals_blocked": len(res.blocked),
    }


def print_summary(s: dict) -> None:
    print("\n=== MNQ simulated backtest (no live orders) ===")
    width = max(len(k) for k in s)
    for k, v in s.items():
        print(f"  {k:<{width}} : {v}")


def write_outputs(res: Result, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "trades.csv"), "w", newline="") as fh:
        if res.trades:
            w = csv.DictWriter(fh, fieldnames=list(asdict(res.trades[0]).keys()))
            w.writeheader()
            for t in res.trades:
                w.writerow(asdict(t))
    with open(os.path.join(out_dir, "daily.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["trading_day", "pnl", "cumulative"])
        cum = 0.0
        for k in sorted(res.daily):
            cum += res.daily[k]
            w.writerow([k, round(res.daily[k], 2), round(cum, 2)])
    with open(os.path.join(out_dir, "blocked_signals.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time", "side", "price", "score", "reason_blocked"])
        for sig, why in res.blocked:
            w.writerow([sig.ts.isoformat(), sig.side, sig.ref_price, sig.score, why])
