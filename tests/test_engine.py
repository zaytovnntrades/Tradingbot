import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from mnqbot.config import Config
from mnqbot.data import Bar, generate_synthetic
from mnqbot.engine import Backtester, _Position
from mnqbot.report import summarize
from mnqbot.signals import Signal

ET = ZoneInfo("America/New_York")


def bar(h, m, o, hi, lo, c):
    return Bar(datetime(2026, 3, 3, h, m, tzinfo=ET), o, hi, lo, c, 1000)


class EngineTests(unittest.TestCase):
    def _pos(self, bt, side="long"):
        sig = Signal(datetime(2026, 3, 3, 10, 0, tzinfo=ET), 0, side, 100, 90, 120, 10, 10, 2, "swing", 91)
        if side == "long":
            return _Position(sig, side, 1, 100, 90, 120, 90, 10, 50, sig.ts)
        return _Position(sig, side, 1, 100, 110, 80, 110, 10, 150, sig.ts)

    def test_stop_beats_target_in_same_bar(self):
        bt = Backtester(Config())
        px, why = bt._manage(self._pos(bt), bar(10, 5, 100, 125, 85, 100))
        self.assertEqual(why, "stop")
        self.assertEqual(px, 89.75)

    def test_target_and_gap(self):
        bt = Backtester(Config())
        self.assertEqual(bt._manage(self._pos(bt), bar(10, 5, 101, 121, 99, 118)), (120, "target"))
        self.assertEqual(bt._manage(self._pos(bt), bar(10, 5, 85, 86, 80, 82))[1], "stop (gap)")
        self.assertEqual(bt._manage(self._pos(bt, "short"), bar(10, 5, 99, 101, 79, 85)), (80, "target"))

    def test_breakeven_moves_stop_next_bar(self):
        bt = Backtester(Config())
        p = self._pos(bt)
        self.assertIsNone(bt._manage(p, bar(10, 5, 101, 111, 99, 108)))
        self.assertTrue(p.be_done)
        self.assertEqual(p.stop, 100.25)
        self.assertEqual(bt._manage(p, bar(10, 10, 104, 105, 100, 101))[1], "breakeven")

    def test_flatten(self):
        bt = Backtester(Config())
        self.assertEqual(bt._manage(self._pos(bt), bar(15, 50, 101, 105, 99, 104))[1], "end-of-day flatten")

    def test_synthetic_run_respects_all_rules(self):
        cfg = Config()
        for seed in range(5):
            res = Backtester(cfg).run(generate_synthetic(40, seed))
            s = summarize(res, cfg)
            self.assertEqual(s["daily_limit_breaches"], 0)
            for t in res.trades:
                self.assertGreaterEqual(t.entry_ts.time(), cfg.t("entry_start"))
                self.assertLessEqual(t.exit_ts.time(), cfg.t("flatten_time"))
                self.assertEqual(t.entry_ts.date(), t.exit_ts.date())      # never held overnight
                self.assertLessEqual(t.qty, cfg.max_contracts)
                self.assertGreaterEqual(t.pnl, -cfg.risk_per_trade * 1.1)  # sizing holds (1 tick slip)

    def test_hard_daily_limit_under_stress(self):
        cfg = Config(risk_per_trade=2750, daily_loss_buffer=0, max_trades_per_day=50,
                     max_consecutive_losses=99, giveback_activate=1e9, cooldown_bars_after_loss=0,
                     min_score=0, reduced_risk_after_losses=99, max_contracts=200,
                     stop_at_profit_target=False)
        for seed in range(5):
            res = Backtester(cfg).run(generate_synthetic(40, seed))
            self.assertGreater(min(res.daily.values()), -cfg.max_daily_loss)


if __name__ == "__main__":
    unittest.main()
