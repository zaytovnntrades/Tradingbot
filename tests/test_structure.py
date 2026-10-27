import unittest

from mnqbot.structure import Level, LiquidityBook, PivotDetector, ZoneBook


class StructureTests(unittest.TestCase):
    def test_pivot_low_confirmed_after_n_bars(self):
        p = PivotDetector(2)
        lows = [10, 9, 5, 8, 9]
        out = [p.update(lo + 5, lo)[1] for lo in lows]
        self.assertEqual(out[-1], 5)
        self.assertTrue(all(x is None for x in out[:-1]))

    def test_sweep_and_break(self):
        book = LiquidityBook(10, 100)
        book.add_low(Level(100.0, "swing", 0))
        bull, _ = book.check(high=105, low=99, close=101, bar=1)   # wick through, close back
        self.assertIsNotNone(bull)
        self.assertEqual(book.lows, [])                             # consumed
        book.add_low(Level(100.0, "swing", 2))
        bull, _ = book.check(high=101, low=97, close=98, bar=3)    # closed below: broken
        self.assertIsNone(bull)
        self.assertEqual(book.lows, [])

    def test_demand_zone_created_and_invalidated(self):
        zb = ZoneBook(5, 100, impulse_mult=1.5, base_max_body=0.6)
        zb.update(1, o=100, h=116, lo=99, c=115, prev=(100, 101, 98, 100.5), atr=10)
        self.assertEqual(len(zb.demand), 1)
        self.assertEqual((zb.demand[0].top, zb.demand[0].bottom), (101, 98))
        d, _ = zb.touches(high=105, low=100)
        self.assertIsNotNone(d)
        zb.update(2, o=100, h=100, lo=95, c=96, prev=(100, 116, 99, 115), atr=10)
        self.assertEqual(zb.demand, [])


if __name__ == "__main__":
    unittest.main()
