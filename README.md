# MNQ Sweep + Supply/Demand Signal Bot (simulated only)

A paper-trading **signal bot** for **MNQ** (Micro E-mini Nasdaq-100) on **TradingView**:

| Setting | Value |
|---|---|
| Account | $100,000 simulated |
| Profit target | $7,000 (signals stop once reached) |
| Hard max daily loss | $3,000 (never sized past; trading stops $250 before it) |
| Style | Balanced: $500 risk per trade (0.5%), 2R target, 2 of 4 confluence points |
| Mode | Signals + alerts. **No live orders, no broker connection.** |

The repo has two parts that run the same rules:

1. **`pine/`**: TradingView scripts you paste into the Pine Editor.
   - `mnq_sweep_sd_signals.pine`: **indicator** with signals, zones, levels, a risk panel and alerts. It paper-trades its own signals, so a daily lockout blocks the signals that come after it.
   - `mnq_sweep_sd_strategy.pine`: the same engine as a **strategy**, for TradingView's Strategy Tester (backtest only).
2. **`mnqbot/`**: a Python simulator with no dependencies. It backtests TradingView CSV exports, prints sized trade plans and enforces every risk rule. It has unit tests.

> ⚠️ Education and simulation only. This is not financial advice. Nothing here is proven profitable. The demo uses random-walk data, which only shows the machinery works and says nothing about edge.

---

## How a signal forms

```
1. LIQUIDITY      Find resting stops: swing highs/lows (pivots), prior-day high/low (PDH/PDL),
                  overnight high/low (ONH/ONL).
2. SWEEP          A bar trades through a level and CLOSES BACK on the other side,
                  with a rejection wick of at least 25% of the bar's range. Stops got run.
3. CONFLUENCE     Score 0-4. Balanced mode needs 2 or more:
                  +1 sweep bar touches a demand (long) / supply (short) zone
                  +1 EMA21 above EMA50 (long) / below (short)
                  +1 close back above EMA9 (long) / below (short)
                  +1 RSI exhaustion in the last 3 bars (<35 / >65) OR a volume spike (1.5x avg)
4. STOP (vol.)    The farther of: sweep wick plus 0.25 ATR, 1.0 ATR, or 6 pts.
                  Setups that need more than 3 ATR are skipped.
5. TARGET         2R. The stop moves to breakeven at +1R.
6. ENTRY          At the next bar's open, during 09:35-15:30 NY time. Flat by 15:50.
```

**Supply/demand zones:** a small "base" candle (body ≤ 0.6 ATR) followed by an impulsive candle (body ≥ 1.5 ATR). The zone is the base candle's high-to-low range. It is removed when price closes through it, or after 300 bars.

## Risk safeguards

| Safeguard | Default | What it does |
|---|---|---|
| Position sizing | $500 risk | `contracts = floor(risk / (stop_pts × $2 + commission + slippage))`, capped at 15 |
| Hard daily loss | $3,000 | Each trade is sized so even a full stop can't cross the limit. Every position also carries a computed **hard-stop price** at the limit |
| Loss buffer | $250 | No new trades once the day is at −$2,750 |
| Shrinking risk | — | Risk per trade is also capped by `room left − buffer` |
| Loss streak | 2 → half size, 3 → done for the day | Stops tilt spirals |
| Give-back guard | at +$1,500 | Stops for the day after giving back 50% of the day's peak |
| Max trades | 6/day | Prevents overtrading |
| Cooldown | 3 bars after a loss | Prevents instant revenge entries |
| Profit target | $7,000 | All signals halt once total P&L reaches it |
| Session | 09:35–15:30 entries, flat at 15:50 | Never holds overnight |
| Fill realism | — | 1 tick slippage, $0.85/side commission. When a bar hits both stop and target, the stop counts first. Gaps fill at the open |
| TradingView backstop | `strategy.risk.max_intraday_loss(3000)` | The platform also enforces the daily limit (strategy version) |

---

## Quick start

### A) TradingView (signals)
1. Open an **MNQ1!** chart on **5-minute** bars. Turn on the extended session (ETH) so overnight levels exist.
2. Pine Editor → paste `pine/mnq_sweep_sd_signals.pine` → **Add to chart**.
3. Create alerts:
   - *Alert → Condition: MNQ Sweep SD → "Any alert() function call"*. This sends a JSON payload with side, stop, target and qty.
   - Or use the named conditions: `MNQ long signal`, `MNQ short signal`, `MNQ daily loss lock`, `MNQ profit target hit`.
4. To backtest in TradingView, add `pine/mnq_sweep_sd_strategy.pine` and open **Strategy Tester**.

Example alert payload (`"live": false` on purpose):
```json
{"mode":"signal","live":false,"symbol":"MNQ1!","side":"long","ref":25202,"stop":25186.5,"target":25233,"qty":15,"score":2,"sweep":"swing","dayPnl":0}
```

### B) Python simulator
Requires Python 3.10+. No packages to install.
```bash
python3 -m mnqbot demo                                   # synthetic data, checks the machinery
python3 -m mnqbot backtest --csv data/MNQ_5m.csv         # your TradingView export
python3 -m mnqbot signals  --csv data/MNQ_5m.csv --last 10
python3 -m mnqbot --config config.example.json backtest --csv data/MNQ_5m.csv
python3 -m unittest discover -s tests                    # 23 tests
```
To get real data: on the TradingView chart, open **⋯ → Export chart data…**. Save the file to `data/`. Unix or ISO timestamps both work. For naive timestamps that aren't New York time, pass `--data-tz UTC`.

The backtest writes `results/trades.csv`, `results/daily.csv` and `results/blocked_signals.csv`. The last file records every signal the risk layer refused, and why.

## Configuration
Every parameter is in `mnqbot/config.py`. Override any of them with a JSON file (see `config.example.json`). The Pine inputs use the same names and defaults, so a change tested in Python can be copied into TradingView.

Config validation refuses settings where `risk_per_trade + buffer > max_daily_loss`.

## Project layout
```
pine/mnq_sweep_sd_signals.pine    TradingView indicator: signals + alerts + virtual risk tracker
pine/mnq_sweep_sd_strategy.pine   TradingView strategy: Strategy Tester simulation
mnqbot/config.py                  every parameter
mnqbot/indicators.py              EMA/ATR/RSI/SMA/VWAP (match ta.*)
mnqbot/structure.py               pivots, liquidity sweeps, supply/demand zones
mnqbot/signals.py                 confluence scoring, volatility stops
mnqbot/risk.py                    sizing + every safeguard
mnqbot/engine.py                  bar-by-bar paper fills (no lookahead)
mnqbot/report.py                  stats + CSV output
docs/PLAYBOOK.md                  staged path from first run to tuning
```

## Known limits
- Results depend on bar data. With OHLC bars, what happened inside a bar is unknown, which is why the stop-first rule is used.
- The Python and Pine versions follow the same rules. Small differences are expected around pivot tie-breaks, the first bars of history, and the strategy version sizing from the signal close rather than the fill.
- No news filter is built in. Skip FOMC, CPI and NFP windows yourself, or narrow the entry session on those days.
