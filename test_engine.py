import unittest
from datetime import datetime, timezone
import numpy as np
from data import demo
from engine import simulate, signal, penalty

class ModelTests(unittest.TestCase):
    def test_repeatability_and_inventory_bounds(self):
        inputs, history, _ = demo()
        a = simulate(inputs, history, hours=5, paths=500)
        b = simulate(inputs, history, hours=5, paths=500)
        self.assertTrue(np.array_equal(a["samples"], b["samples"]))
        self.assertTrue(np.isfinite(a["samples"]).all())
        self.assertGreaterEqual(a["inventory"].min(), 0)
        self.assertLessEqual(a["inventory"].max(), 76)

    def test_capacity_penalty(self):
        self.assertGreater(penalty(75.9, 76, 20), penalty(20, 76, 20))
        self.assertGreater(penalty(75.9, 76, 1), penalty(75.9, 76, 180))

    def test_negative_prices_allowed(self):
        inputs, history, _ = demo()
        inputs["price"]["value"] = -20.
        sim = simulate(inputs, history, hours=1, paths=500)
        self.assertLess(sim["samples"].min(), 0)

    def test_missing_freight_forces_public_hold(self):
        inputs, history, _ = demo()
        inputs["freight"]["value"] = None
        sim = simulate(inputs, history, hours=5, paths=500)
        result = signal(inputs, history, sim, datetime.now(timezone.utc),
                        76, 20, demo_mode=False, verified=True)
        self.assertEqual(result["action"], "HOLD")
        self.assertIsNone(result["tp"])

if __name__ == "__main__":
    unittest.main()