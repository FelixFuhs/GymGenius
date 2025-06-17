import unittest

from engine.progression import (
    calculate_trend_slope,
    detect_plateau,
    generate_deload_protocol,
    confidence_score,
    PlateauStatus,
)


class TestProgressionUtils(unittest.TestCase):
    def test_trend_slope_positive(self):
        self.assertGreater(calculate_trend_slope([1, 2, 3, 4]), 0)

    def test_plateau_detection(self):
        values = [100, 100.02, 99.98, 100.0]
        result = detect_plateau(values)
        self.assertTrue(result["plateauing"])
        self.assertEqual(result["status"], PlateauStatus.STAGNATION)
        self.assertIn("slope", result)
        self.assertIn("duration", result)

    def test_detect_plateau_no_plateau_progression(self):
        values = [100, 102, 104, 106, 108] # Clear progression
        result = detect_plateau(values, min_duration=3, tolerance=0.01)
        self.assertFalse(result["plateauing"])
        self.assertEqual(result["status"], PlateauStatus.NO_PLATEAU)

    def test_detect_plateau_regression(self):
        values = [100, 98, 96, 94, 92] # Clear regression
        result = detect_plateau(values, min_duration=3, tolerance=0.01)
        self.assertTrue(result["plateauing"])
        self.assertEqual(result["status"], PlateauStatus.REGRESSION)

    def test_detect_plateau_stagnation_warning(self):
        # Slight positive slope, but within tolerance for warning
        values = [100, 100.1, 100.2, 100.3, 100.0] # Ends with small drop
        result = detect_plateau(values, min_duration=3, tolerance=0.02, slope_threshold_warning=0.015)
        # Assuming slope of this series is small enough to be stagnation_warning or stagnation.
        # Actual slope calculation depends on the specific linear regression.
        # This test might need adjustment based on actual slope from `calculate_trend_slope`.
        # For now, let's say we expect it to be a warning or stagnation.
        self.assertTrue(result["plateauing"]) # It's some form of plateau
        self.assertIn(result["status"], [PlateauStatus.STAGNATION, PlateauStatus.STAGNATION_WARNING, PlateauStatus.REGRESSION_WARNING])


    def test_detect_plateau_regression_warning(self):
        values = [100, 99.5, 99, 98.5, 99] # Overall downward but ends up
        result = detect_plateau(values, min_duration=3, tolerance=0.02, slope_threshold_warning=-0.015)
        self.assertTrue(result["plateauing"])
        self.assertIn(result["status"], [PlateauStatus.REGRESSION, PlateauStatus.REGRESSION_WARNING])


    def test_detect_plateau_insufficient_data(self):
        values = [100, 102] # Only 2 data points
        result = detect_plateau(values, min_duration=3)
        self.assertFalse(result["plateauing"])
        self.assertEqual(result["status"], PlateauStatus.INSUFFICIENT_DATA)

    def test_detect_plateau_all_same_values(self):
        values = [100, 100, 100, 100, 100]
        result = detect_plateau(values, min_duration=3)
        self.assertTrue(result["plateauing"])
        self.assertEqual(result["status"], PlateauStatus.STAGNATION)
        self.assertAlmostEqual(result["slope"], 0.0, places=5)

    def test_detect_plateau_gradual_increase_no_plateau(self):
        values = [100, 100.5, 101, 101.5, 102] # Gradual increase
        result = detect_plateau(values, min_duration=3, tolerance=0.01, slope_threshold_stagnation=0.02)
        self.assertFalse(result["plateauing"])
        self.assertEqual(result["status"], PlateauStatus.NO_PLATEAU)

    def test_deload_protocol_shape(self):
        proto = generate_deload_protocol()
        self.assertIsInstance(proto, list)
        self.assertGreaterEqual(len(proto), 1)
        self.assertIn("week_number", proto[0])
        self.assertIn("intensity_modifier", proto[0])
        self.assertIn("volume_modifier", proto[0])
        self.assertIn("frequency_modifier", proto[0]) # Assuming this key exists
        self.assertIn("notes", proto[0])

    def test_generate_deload_protocol_mild_stagnation_low_fatigue(self):
        protocol = generate_deload_protocol(plateau_severity=0.3, recent_fatigue_score=20, deload_duration_weeks=1)
        self.assertEqual(len(protocol), 1) # 1 week duration
        # Expect moderate reduction for mild stagnation, low fatigue might mean less aggressive deload
        self.assertTrue(0.85 <= protocol[0]["intensity_modifier"] < 0.95) # e.g. 0.9
        self.assertTrue(0.75 <= protocol[0]["volume_modifier"] < 0.9)    # e.g. 0.8
        # Frequency might not change or reduce slightly
        self.assertTrue(0.8 <= protocol[0]["frequency_modifier"] <= 1.0)

    def test_generate_deload_protocol_severe_regression_high_fatigue(self):
        protocol = generate_deload_protocol(plateau_severity=0.8, recent_fatigue_score=70, deload_duration_weeks=2)
        self.assertEqual(len(protocol), 2) # 2 weeks duration
        # Expect significant reductions for severe regression and high fatigue
        week1 = protocol[0]
        self.assertTrue(0.70 <= week1["intensity_modifier"] < 0.85) # e.g. 0.75-0.8
        self.assertTrue(0.50 <= week1["volume_modifier"] < 0.70)    # e.g. 0.6
        # Frequency likely reduced
        self.assertTrue(0.5 <= week1["frequency_modifier"] < 1.0)

        # Week 2 might be slightly less aggressive than week 1 or similar
        if len(protocol) > 1:
            week2 = protocol[1]
            self.assertTrue(week1["intensity_modifier"] <= week2["intensity_modifier"] <= week1["intensity_modifier"] + 0.1) # Ramp up slightly or stay
            self.assertTrue(week1["volume_modifier"] <= week2["volume_modifier"] <= week1["volume_modifier"] + 0.1)

    def test_generate_deload_protocol_default_values(self):
        # Test with default parameters to ensure it runs and produces a sensible output
        protocol = generate_deload_protocol() # Uses all defaults
        self.assertIsInstance(protocol, list)
        self.assertGreaterEqual(len(protocol), 1) # Default duration is 1 week
        # Check if default severity (0.5) and fatigue (50) produce expected ballpark modifiers
        # These values depend on the internal logic of generate_deload_protocol
        # Example expectations for severity=0.5, fatigue=50:
        self.assertTrue(0.80 <= protocol[0]["intensity_modifier"] <= 0.90)
        self.assertTrue(0.60 <= protocol[0]["volume_modifier"] <= 0.80)


    def test_confidence_score_bounds(self):
        preds = [100, 105, 110]
        actuals = [102, 104, 111]
        score = confidence_score(preds, actuals)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 1)


if __name__ == "__main__":
    unittest.main()
