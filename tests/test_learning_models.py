import unittest
from math import exp
from datetime import datetime, timedelta

from engine.learning_models import (
    update_user_rir_bias,
    calculate_current_fatigue,
    MIN_RIR_BIAS,
    MAX_RIR_BIAS,
)


class TestUpdateUserRirBias(unittest.TestCase):
    def test_bias_adjusts_with_performance(self):
        bias = 2.0
        self.assertAlmostEqual(update_user_rir_bias(bias, 8, 6), 2.2)
        self.assertAlmostEqual(update_user_rir_bias(bias, 6, 8), 1.8)
        self.assertAlmostEqual(update_user_rir_bias(bias, 7, 7), bias)

    def test_bias_clamped_to_bounds(self):
        high = update_user_rir_bias(MAX_RIR_BIAS, 10, 0)
        self.assertEqual(high, MAX_RIR_BIAS)
        low = update_user_rir_bias(MIN_RIR_BIAS, 1, 10)
        self.assertEqual(low, MIN_RIR_BIAS)


class TestCalculateCurrentFatigue(unittest.TestCase):
    def test_basic_fatigue_calculation(self):
        now = datetime.now()
        history = [
            {"session_date": now - timedelta(hours=24), "stimulus": 100.0},
            {"session_date": now - timedelta(hours=48), "stimulus": 50.0},
        ]
        expected = 100.0 * exp(-24 / 48) + 50.0 * exp(-48 / 48)
        result = calculate_current_fatigue("chest", history)
        self.assertAlmostEqual(result, expected, places=5)

    def test_invalid_records_and_default_tau(self):
        now = datetime.now()
        history = [
            {"session_date": now - timedelta(hours=24), "stimulus": 80.0},
            {"session_date": "bad", "stimulus": 80.0},
            {"session_date": now + timedelta(hours=5), "stimulus": 80.0},
            {"session_date": now - timedelta(hours=48), "stimulus": "bad"},
        ]
        expected = 80.0 * exp(-24 / 48)
        result = calculate_current_fatigue(
            "unknown", history, user_recovery_multiplier=0
        )
        self.assertAlmostEqual(result, expected, places=5)


if __name__ == "__main__":
    unittest.main()
