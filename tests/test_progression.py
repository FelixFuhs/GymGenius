import unittest

from engine.progression import (
    calculate_trend_slope,
    detect_plateau,
    generate_deload_protocol,
    confidence_score,
)


class TestProgressionUtils(unittest.TestCase):
    def test_trend_slope_positive(self):
        self.assertGreater(calculate_trend_slope([1, 2, 3, 4]), 0)

    def test_plateau_detection(self):
        values = [100, 101, 101.1, 101.2]
        self.assertTrue(detect_plateau(values))

    def test_deload_protocol_shape(self):
        proto = generate_deload_protocol()
        self.assertIsInstance(proto, list)
        self.assertGreaterEqual(len(proto), 1)
        self.assertIn("week_number", proto[0])

    def test_confidence_score_bounds(self):
        preds = [100, 105, 110]
        actuals = [102, 104, 111]
        score = confidence_score(preds, actuals)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 1)


if __name__ == "__main__":
    unittest.main()
