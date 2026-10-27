"""CLI: python -m mnqbot {demo,backtest,signals,synth} ..."""

from __future__ import annotations

import argparse
import sys

from .config import load_config
from .data import generate_synthetic, load_csv, write_csv
from .engine import Backtester
from .report import print_summary, summarize, write_outputs
from .risk import RiskManager
from .signals import SignalEngine


def _backtest(bars, cfg, out):
    res = Backtester(cfg).run(bars)
    s = summarize(res, cfg)
    print_summary(s)
    write_outputs(res, out)
    print(f"\n  wrote {out}/trades.csv, daily.csv, blocked_signals.csv")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mnqbot", description="MNQ simulated signal bot (no live orders)")
    ap.add_argument("--config", help="JSON file overriding defaults (see config.example.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="backtest on synthetic data (plumbing check)")
    d.add_argument("--days", type=int, default=60)
    d.add_argument("--seed", type=int, default=7)
    d.add_argument("--out", default="results")

    b = sub.add_parser("backtest", help="backtest a CSV (TradingView 'Export chart data')")
    b.add_argument("--csv", required=True)
    b.add_argument("--data-tz", help="tz for naive timestamps, e.g. UTC (default exchange tz)")
    b.add_argument("--out", default="results")

    s = sub.add_parser("signals", help="print the latest signals with a sized trade plan")
    s.add_argument("--csv", required=True)
    s.add_argument("--data-tz")
    s.add_argument("--last", type=int, default=10)

    g = sub.add_parser("synth", help="write a synthetic MNQ CSV")
    g.add_argument("--days", type=int, default=60)
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--out", default="data/synthetic_mnq_5m.csv")

    a = ap.parse_args(argv)
    cfg = load_config(a.config)

    if a.cmd == "demo":
        print("NOTE: synthetic random-walk data -- verifies the machinery, not the edge.")
        _backtest(generate_synthetic(a.days, a.seed), cfg, a.out)
    elif a.cmd == "backtest":
        _backtest(load_csv(a.csv, cfg.timezone, a.data_tz), cfg, a.out)
    elif a.cmd == "signals":
        eng, risk = SignalEngine(cfg), RiskManager(cfg)
        sigs = [x for x in (eng.update(bar) for bar in load_csv(a.csv, cfg.timezone, a.data_tz)) if x]
        if not sigs:
            print("no signals in this data")
        for sig in sigs[-a.last:]:
            qty = risk.size(sig.stop_points)
            risk_usd = qty * risk.cost_per_contract(sig.stop_points)
            print(f"{sig.describe()}\n    plan: {qty} MNQ, risk ~${risk_usd:,.0f} "
                  f"(fresh day, ${cfg.max_daily_loss:,.0f} hard daily limit)")
    elif a.cmd == "synth":
        bars = generate_synthetic(a.days, a.seed)
        write_csv(bars, a.out)
        print(f"wrote {len(bars)} bars to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
