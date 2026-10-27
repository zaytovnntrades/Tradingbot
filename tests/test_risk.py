import unittest

from mnqbot.config import Config
from mnqbot.risk import RiskManager


class RiskTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()
        self.r = RiskManager(self.cfg)
        self.r.roll_day("d1")

    def test_size_uses_risk_per_trade(self):
        # 20 pts * $2 = $40 + 1.70 commission + 0.50 slippage = $42.20/contract
        self.assertEqual(self.r.size(20), 11)          # floor(500 / 42.2)

    def test_size_capped_by_max_contracts(self):
        self.assertEqual(self.r.size(1), self.cfg.max_contracts)

    def test_size_shrinks_near_daily_limit(self):
        self.r.day_pnl = -2600                         # room 400, buffer 250 -> $150
        self.assertEqual(self.r.size(20), 3)

    def test_daily_loss_lock(self):
        self.r.day_pnl = -2760
        ok, why = self.r.can_open(0)
        self.assertFalse(ok)
        self.assertEqual(why, "daily loss limit")

    def test_consecutive_losses_and_reduced_risk(self):
        self.r.record(-100, 0)
        self.r.record(-100, 1)
        self.assertEqual(self.r.risk_budget(), 250)
        self.r.record(-100, 2)
        ok, why = self.r.can_open(100)
        self.assertEqual((ok, why), (False, "consecutive losses"))

    def test_giveback_lock(self):
        self.r.record(2000, 0)
        self.r.record(-1100, 1)
        ok, why = self.r.can_open(100)
        self.assertEqual((ok, why), (False, "profit give-back"))

    def test_profit_target_halts(self):
        self.r.record(7000, 0)
        self.assertFalse(self.r.can_open(10)[0])
        self.r.roll_day("d2")
        self.assertFalse(self.r.can_open(10)[0])

    def test_hard_stop_caps_trade_loss_at_room(self):
        self.r.day_pnl = -2500
        qty, entry = 5, 20000.0
        hs = self.r.hard_stop_price("long", entry, qty)
        c = self.cfg
        loss = ((entry - hs) + c.slippage_ticks * c.tick_size) * qty * c.point_value + 2 * c.commission_per_side * qty
        self.assertLessEqual(loss, self.r.daily_room())

    def test_config_validation(self):
        with self.assertRaises(ValueError):
            Config(risk_per_trade=3000).validate()


if __name__ == "__main__":
    unittest.main()
