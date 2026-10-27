# Playbook: apprentice to mastery

How to work with this bot in stages. Each stage has a goal, tasks, and a gate to pass before moving on. Don't skip gates. They are where the learning happens.

---

## Stage 1: Read the chart (days 1–3)
**Goal:** see liquidity the way the bot does.

- [ ] Add the indicator to MNQ1! 5m with ETH on. Turn off the EMAs and leave only levels and zones.
- [ ] Each morning before 09:30, write down PDH, PDL, ONH and ONL. Those four lines are where stops sit.
- [ ] Scroll back 20 sessions. For every green/red signal label, find the level it swept and the zone it touched.

**Gate:** you can predict which level will be swept next before price gets there, right on 5 of 10 tries.

**Shortcut:** the highest-value sweeps happen in the first 60–90 minutes, at **ONH/ONL and PDH/PDL**. Swing-level sweeps are more frequent but weaker.

## Stage 2: Understand the score (days 4–7)
**Goal:** know why each signal fired.

- [ ] Run `python3 -m mnqbot backtest --csv <your export>`. Open `results/trades.csv`.
- [ ] Group trades by `score` (2, 3, 4) and by `sweep_kind`. Compare win rate and average R.
- [ ] Read `blocked_signals.csv`. Every row is a trade the risk layer saved you from, or kept you out of. Note which.

**Gate:** you can explain, without looking, each of the 4 confluence points and what each one protects against.

**Template for the journal entry on each signal:**
```
Time | Side | Level swept | Zone? | Trend (21v50) | EMA9 reclaim | RSI/Vol | Score | Result R | Followed rules? Y/N
```

## Stage 3: Paper-trade live (weeks 2–4)
**Goal:** execute signals by hand in TradingView's Paper Trading account, with zero rule breaks.

- [ ] Set the alert to *Any alert() function call*. Keep the phone app on.
- [ ] Take **every** signal at the stated qty, stop and target. No discretion yet.
- [ ] Compare your paper fills against the indicator's virtual tracker each evening.

**Gate:** 20 consecutive signals taken exactly as given. Your P&L should track the panel within slippage.

## Stage 4: Tune with evidence (month 2)
**Goal:** change one variable at a time and keep a change only if it holds up out of sample.

Change one setting at a time, in this order (most to least impact):
1. `min_score` (2 → 3): fewer trades, usually a higher win rate.
2. `reward_risk` (1.5 / 2 / 2.5) together with `breakeven_at_r` (0 / 1).
3. `entry_start` / `last_entry`: try a "first 2 hours only" session (09:35–11:30).
4. `atr_buffer_mult` and `max_stop_atr`: how much room the stop gets.

**Method:** split the data into two halves. Tune on the first half and confirm on the second. If a change only helps the first half, it is curve-fitting. Throw it out.

**Gate:** the edge holds on unseen data, with PF > 1.3 across 100+ trades and no day hitting the daily limit.

## Stage 5: Mastery habits
- **Risk is the only thing you control.** The $3,000 limit is a hard rule and never moves. The $500 risk per trade can drop; it never rises during a drawdown.
- **The target is a finish line, not a quota.** At $7,000 the bot stops. Hitting it in 3 weeks or in 3 months is the same outcome.
- **Pick the stop first, then the size.** The bot never decides "I want 10 contracts." Size always comes from the stop distance.
- **Red days end early.** Three losses in a row means the day is done. Expectancy recovers tomorrow, but your account balance may not.

---

## High-ROI tips and uncommon resources
| Tip | Why it pays |
|---|---|
| Check the TradingView **"Bar Replay"** tool on old sessions with the indicator on | Gives you 20 practice sessions in an hour |
| Turn on ETH even if you only trade RTH | Without it, ONH/ONL (the best sweep levels) don't exist |
| Skip 08:30 data days (CPI/NFP) until 10:00 | The first sweeps on those days are usually news noise, not stop runs |
| Look at `blocked_signals.csv` weekly | Shows whether your lockouts cost you profit or saved you from losses |
| Use the CME **"MNQ contract specs"** page and your broker's fee schedule | Put your real per-side cost into `commission_per_side` |
| Export 1-minute data and set `swing_len` to 10–15 | Finer pivots and more levels. Run the backtest to compare |

## Teaching it to others (staged outline)
1. **Concept:** liquidity sits beyond obvious highs and lows (Stage 1).
2. **Mechanism:** sweep, then rejection, then confluence (Stage 2).
3. **Discipline:** paper-trade with fixed rules (Stage 3).
4. **Science:** one-variable tuning with out-of-sample checks (Stage 4).
5. **Identity:** risk-first habits (Stage 5).
