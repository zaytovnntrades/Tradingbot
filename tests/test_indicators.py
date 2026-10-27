import unittest

from mnqbot.indicators import ATR, EMA, RSI, SMA, SessionVWAP


class IndicatorTests(unittest.TestCase):
    def test_ema_constant_series(self):
        e = EMA(5)
        for _ in range(20):
            v = e.update(10.0)
        self.assertAlmostEqual(v, 10.0)

    def test_ema_seed_is_sma(self):
        e = EMA(3)
        self.assertIsNone(e.update(1))
        self.assertIsNone(e.update(2))
        self.assertAlmostEqual(e.update(3), 2.0)
        self.assertAlmostEqual(e.update(4), 3.0)

    def test_atr_constant_range(self):
        a = ATR(3)
        for _ in range(10):
            v = a.update(11, 9, 10)
        self.assertAlmostEqual(v, 2.0)

    def test_rsi_extremes(self):
        up = RSI(3)
        for x in range(10):
            v = up.update(float(x))
        self.assertEqual(v, 100.0)

    def test_sma_and_vwap(self):
        s = SMA(2)
        s.update(1)
        self.assertAlmostEqual(s.update(3), 2.0)
        w = SessionVWAP()
        w.update("d1", 12, 8, 10, 100)
        self.assertAlmostEqual(w.update("d1", 22, 18, 20, 100), 15.0)
        self.assertAlmostEqual(w.update("d2", 6, 4, 5, 1), 5.0)


if __name__ == "__main__":
    unittest.main()
