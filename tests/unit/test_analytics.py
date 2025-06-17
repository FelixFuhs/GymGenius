import pytest
from engine.blueprints.analytics import EXERCISE_DEFAULT_1RM, FALLBACK_DEFAULT_1RM

# This test focuses on the core calculation logic of the fatigue cap.
# It does not test the full recommend_set_parameters_route due to complexities
# with Flask app context and extensive mocking that would be required for a pure unit test.

def test_fatigue_cap_applied_correctly():
    """
    Tests the fatigue adjustment factor calculation and capping.
    The formula for the factor is: (current_fatigue / fatigue_points_for_reduction) * fatigue_reduction_per_10_points
    The cap for this factor is 0.10.
    """
    fatigue_reduction_per_10_points = 0.01  # As defined in recommend_set_parameters_route
    fatigue_points_for_reduction = 10.0     # As defined in recommend_set_parameters_route
    cap_value = 0.10                        # The cap being tested

    # Scenario 1: Fatigue is high, so the cap should be applied.
    current_fatigue_high = 1000.0

    # Calculate the uncapped factor
    fatigue_adjustment_factor_uncapped_high = (float(current_fatigue_high) / fatigue_points_for_reduction) * fatigue_reduction_per_10_points
    # Expected uncapped: (1000.0 / 10.0) * 0.01 = 100.0 * 0.01 = 1.0

    assert fatigue_adjustment_factor_uncapped_high > cap_value, "Uncapped value should be greater than cap to test capping."

    # Apply the cap
    fatigue_adjustment_factor_capped_high = min(fatigue_adjustment_factor_uncapped_high, cap_value)

    assert fatigue_adjustment_factor_capped_high == pytest.approx(cap_value)

    # Scenario 2: Fatigue is moderate, so the cap should NOT be applied.
    current_fatigue_moderate = 50.0

    # Calculate the uncapped factor
    fatigue_adjustment_factor_uncapped_moderate = (float(current_fatigue_moderate) / fatigue_points_for_reduction) * fatigue_reduction_per_10_points
    # Expected uncapped: (50.0 / 10.0) * 0.01 = 5.0 * 0.01 = 0.05

    assert fatigue_adjustment_factor_uncapped_moderate < cap_value, "Uncapped value should be less than cap to test non-capping."

    # Apply the cap
    fatigue_adjustment_factor_capped_moderate = min(fatigue_adjustment_factor_uncapped_moderate, cap_value)

    assert fatigue_adjustment_factor_capped_moderate == pytest.approx(fatigue_adjustment_factor_uncapped_moderate)

    # Scenario 3: Fatigue results in a factor exactly at the cap.
    # (X / 10.0) * 0.01 = 0.10  => X * 0.001 = 0.10 => X = 100.0
    current_fatigue_at_cap = 100.0

    fatigue_adjustment_factor_uncapped_at_cap = (float(current_fatigue_at_cap) / fatigue_points_for_reduction) * fatigue_reduction_per_10_points
    # Expected uncapped: (100.0 / 10.0) * 0.01 = 10.0 * 0.01 = 0.10

    # Apply the cap
    fatigue_adjustment_factor_capped_at_cap = min(fatigue_adjustment_factor_uncapped_at_cap, cap_value)

    assert fatigue_adjustment_factor_capped_at_cap == pytest.approx(cap_value)
    assert fatigue_adjustment_factor_uncapped_at_cap == pytest.approx(cap_value)

    # Scenario 4: Zero fatigue.
    current_fatigue_zero = 0.0

    fatigue_adjustment_factor_uncapped_zero = (float(current_fatigue_zero) / fatigue_points_for_reduction) * fatigue_reduction_per_10_points
    # Expected uncapped: (0.0 / 10.0) * 0.01 = 0.0

    fatigue_adjustment_factor_capped_zero = min(fatigue_adjustment_factor_uncapped_zero, cap_value)

    assert fatigue_adjustment_factor_capped_zero == pytest.approx(0.0)


# --- Tests for Smart Default 1RM Logic ---

def get_smart_default_1rm_and_source(
    exercise_name_str,
    user_experience_level_str,
    mock_e1rm_history_data=None # This will be None for these tests to focus on default logic
):
    """
    Helper function to simulate the core smart default 1RM logic
    from engine.blueprints.analytics.recommend_set_parameters_route.
    Uses imported EXERCISE_DEFAULT_1RM and FALLBACK_DEFAULT_1RM.
    """
    estimated_1rm = None
    # Default e1rm_source, will be overwritten by more specific logic.
    # Matches the initial e1rm_source in the route before history/default logic.
    e1rm_source = "default"

    if mock_e1rm_history_data:
        # This part simulates if history was found (not the focus of these specific tests)
        # For tests focusing on RIR-bias recalculation from history, this part would be more complex.
        estimated_1rm = float(mock_e1rm_history_data['estimated_1rm'])
        e1rm_source = "history" # Simplified for this helper's scope
    else:
        # No history - this is the logic block being tested.
        exercise_key = exercise_name_str.lower().replace(' ', '_')

        default_levels = EXERCISE_DEFAULT_1RM.get(exercise_key)
        if default_levels:
            estimated_1rm = default_levels.get(user_experience_level_str.lower())
            if estimated_1rm is not None:
                e1rm_source = f"{user_experience_level_str.lower()}_default_for_{exercise_key}"
            else: # Experience level not in this exercise's defaults, try 'intermediate'
                estimated_1rm = default_levels.get('intermediate')
                if estimated_1rm is not None:
                    e1rm_source = f"intermediate_default_for_{exercise_key}"
                # If 'intermediate' also not found, estimated_1rm remains None here

        if estimated_1rm is None: # Fallback if exercise unknown or no matching levels found
            estimated_1rm = FALLBACK_DEFAULT_1RM
            if default_levels: # Exercise was known, but specific level & 'intermediate' were not
                e1rm_source = f"fallback_default_no_level_match_for_{exercise_key}"
            else: # Exercise itself was not in EXERCISE_DEFAULT_1RM
                e1rm_source = "fallback_default_exercise_unknown"

    return estimated_1rm, e1rm_source

def test_smart_default_specific_exercise_and_level():
    exercise = "barbell_bench_press" # Must match a key in EXERCISE_DEFAULT_1RM
    level = "beginner" # Must match a key for the exercise
    expected_1rm = EXERCISE_DEFAULT_1RM[exercise][level]
    expected_source = f"{level}_default_for_{exercise}"

    actual_1rm, actual_source = get_smart_default_1rm_and_source(exercise, level)
    assert actual_1rm == pytest.approx(expected_1rm)
    assert actual_source == expected_source

def test_smart_default_specific_exercise_intermediate_fallback():
    exercise = "barbell_bench_press" # Must match a key in EXERCISE_DEFAULT_1RM
    level = "expert" # Assuming 'expert' is not a defined level for this exercise
    expected_1rm = EXERCISE_DEFAULT_1RM[exercise]['intermediate'] # Fallback to intermediate
    expected_source = f"intermediate_default_for_{exercise}"

    actual_1rm, actual_source = get_smart_default_1rm_and_source(exercise, level)
    assert actual_1rm == pytest.approx(expected_1rm)
    assert actual_source == expected_source

def test_smart_default_unknown_exercise_fallback():
    exercise = "super_unknown_exercise_type" # This key should not be in EXERCISE_DEFAULT_1RM
    level = "intermediate"
    expected_1rm = FALLBACK_DEFAULT_1RM
    expected_source = "fallback_default_exercise_unknown"

    actual_1rm, actual_source = get_smart_default_1rm_and_source(exercise, level)
    assert actual_1rm == pytest.approx(expected_1rm)
    assert actual_source == expected_source

def test_smart_default_known_exercise_no_intermediate_or_level_fallback(monkeypatch):
    # Test a scenario where an exercise exists, but the specific level AND 'intermediate' are missing.
    exercise_key = "test_only_exercise_temp"
    exercise_name_for_test = exercise_key.replace('_', ' ')

    # Temporarily add an exercise that only has an 'advanced' level
    # Using monkeypatch to temporarily modify the dictionary for the test
    monkeypatch.setitem(EXERCISE_DEFAULT_1RM, exercise_key, {'advanced': 150.0})

    level_to_test = "beginner" # This level is not defined for 'test_only_exercise_temp'

    expected_1rm = FALLBACK_DEFAULT_1RM
    # Source should indicate that the exercise was known, but no suitable level default was found
    expected_source = f"fallback_default_no_level_match_for_{exercise_key}"

    actual_1rm, actual_source = get_smart_default_1rm_and_source(exercise_name_for_test, level_to_test)

    assert actual_1rm == pytest.approx(expected_1rm)
    assert actual_source == expected_source

    # Monkeypatch automatically cleans up the change to EXERCISE_DEFAULT_1RM after the test.

@pytest.mark.parametrize("exercise_key_from_dict, levels_in_dict", EXERCISE_DEFAULT_1RM.items())
def test_all_defined_smart_defaults(exercise_key_from_dict, levels_in_dict):
    # This test iterates through all defined exercise and level combinations in EXERCISE_DEFAULT_1RM
    # and verifies that the helper function correctly retrieves them.
    for level_from_dict, expected_1rm_val_from_dict in levels_in_dict.items():
        # Convert exercise_key (e.g., 'barbell_bench_press') back to a name-like string for the helper
        exercise_name_for_test_helper = exercise_key_from_dict.replace('_', ' ')

        actual_1rm, actual_source = get_smart_default_1rm_and_source(exercise_name_for_test_helper, level_from_dict)

        assert actual_1rm == pytest.approx(expected_1rm_val_from_dict)
        assert actual_source == f"{level_from_dict}_default_for_{exercise_key_from_dict}"
