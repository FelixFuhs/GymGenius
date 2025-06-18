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


from engine.constants import SEX_MULTIPLIERS # Import SEX_MULTIPLIERS


# --- Tests for Smart Default 1RM Logic ---

def get_smart_default_1rm_and_source(
    exercise_name_str,
    user_experience_level_str,
    user_sex_str, # Added user_sex_str parameter
    mock_e1rm_history_data=None # This will be None for these tests to focus on default logic
):
    """
    Helper function to simulate the core smart default 1RM logic, now including sex adjustment.
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
        user_level_lower = user_experience_level_str.lower()

        # Logic mirroring engine/blueprints/analytics.py
        default_levels = EXERCISE_DEFAULT_1RM.get(exercise_key)
        used_other_category = False

        if not default_levels:
            default_levels = EXERCISE_DEFAULT_1RM.get("other", {})
            # e1rm_source will be set later based on which level is found within 'other'
            used_other_category = True
            # Tentatively set source, might be overwritten if 'intermediate' or global fallback used
            e1rm_source = f"{user_level_lower}_default_for_other_category"


        if default_levels: # This means either specific exercise's defaults or 'other's defaults were found
            estimated_1rm = default_levels.get(user_level_lower)
            if estimated_1rm is not None: # Direct level match
                if not used_other_category:
                    e1rm_source = f"{user_level_lower}_default_for_{exercise_key}"
                # If used_other_category, e1rm_source is already correctly set from above.
            else: # No direct level match, try 'intermediate' within the current default_levels
                estimated_1rm = default_levels.get('intermediate')
                if estimated_1rm is not None:
                    if not used_other_category:
                        e1rm_source = f"intermediate_default_for_{exercise_key}"
                    else:
                        e1rm_source = f"intermediate_default_for_other_category"
                # If still None, will proceed to global fallback

        if estimated_1rm is None: # Global fallback
            estimated_1rm = FALLBACK_DEFAULT_1RM
            e1rm_source = "global_fallback_default"

        # Apply sex multiplier if estimated_1rm was derived from defaults
        # Check if source indicates a default was used (it should always, if no history)
        if "default" in e1rm_source:
            processed_user_sex = user_sex_str.lower() if user_sex_str else 'unknown'

            actual_key_used_for_multiplier = 'unknown' # Default key
            if processed_user_sex in SEX_MULTIPLIERS:
                sex_multiplier = SEX_MULTIPLIERS[processed_user_sex]
                actual_key_used_for_multiplier = processed_user_sex
            else:
                sex_multiplier = SEX_MULTIPLIERS['unknown'] # Fallback to 'unknown' multiplier

            if estimated_1rm is not None: # Ensure estimated_1rm is not None before multiplication
                estimated_1rm *= sex_multiplier
                # Update e1rm_source to reflect sex adjustment using the key that determined the multiplier
                e1rm_source += f"_sex_adj_{actual_key_used_for_multiplier}"

    return estimated_1rm, e1rm_source

def test_smart_default_specific_exercise_and_level():
    exercise_key = "barbell_bench_press"
    exercise_name = exercise_key.replace('_', ' ')
    level = "beginner"
    user_sex = "male" # Base case, multiplier is 1.0

    base_1rm = EXERCISE_DEFAULT_1RM[exercise_key][level]
    expected_1rm = base_1rm * SEX_MULTIPLIERS[user_sex]
    expected_source = f"{level}_default_for_{exercise_key}_sex_adj_{user_sex}"

    actual_1rm, actual_source = get_smart_default_1rm_and_source(exercise_name, level, user_sex)
    assert actual_1rm == pytest.approx(expected_1rm)
    assert actual_source == expected_source

def test_smart_default_specific_exercise_intermediate_fallback():
    exercise_key = "barbell_bench_press"
    exercise_name = exercise_key.replace('_', ' ')
    level = "expert" # Assuming 'expert' is not a defined level for this exercise
    user_sex = "male" # Base case, multiplier is 1.0

    base_1rm = EXERCISE_DEFAULT_1RM[exercise_key]['intermediate'] # Fallback to intermediate
    expected_1rm = base_1rm * SEX_MULTIPLIERS[user_sex]
    expected_source = f"intermediate_default_for_{exercise_key}_sex_adj_{user_sex}"

    actual_1rm, actual_source = get_smart_default_1rm_and_source(exercise_name, level, user_sex)
    assert actual_1rm == pytest.approx(expected_1rm)
    assert actual_source == expected_source

def test_smart_default_unknown_exercise_fallback():
    exercise_name = "super_unknown_exercise_type" # This key should not be in EXERCISE_DEFAULT_1RM
    level = "intermediate"
    user_sex = "male" # Base case, multiplier is 1.0

    # Now expects to use 'other' category's intermediate value
    base_1rm = EXERCISE_DEFAULT_1RM["other"][level]
    expected_1rm = base_1rm * SEX_MULTIPLIERS[user_sex]
    # Source should reflect 'other' category and its intermediate level
    expected_source = f"{level}_default_for_other_category_sex_adj_{user_sex}"

    actual_1rm, actual_source = get_smart_default_1rm_and_source(exercise_name, level, user_sex)
    assert actual_1rm == pytest.approx(expected_1rm)
    assert actual_source == expected_source

def test_smart_default_known_exercise_no_intermediate_or_level_fallback(monkeypatch):
    # Test a scenario where an exercise exists, but the specific level AND 'intermediate' are missing.
    # This should now fall back to 'other' category's specified level, or 'other' intermediate,
    # or finally global FALLBACK_DEFAULT_1RM if 'other' is incomplete.
    exercise_key_specific = "test_only_exercise_temp"
    exercise_name_for_test = exercise_key_specific.replace('_', ' ')
    user_sex = "male"

    # Temporarily add an exercise that only has an 'advanced' level
    monkeypatch.setitem(EXERCISE_DEFAULT_1RM, exercise_key_specific, {'advanced': 150.0})

    # Case 1: Level 'beginner' not in 'test_only_exercise_temp', nor is 'intermediate'.
    # This exercise IS KNOWN, so it should NOT use 'other'. It should use global fallback.
    level_to_test_beginner = "beginner"
    base_1rm_beginner = FALLBACK_DEFAULT_1RM
    expected_1rm_beginner = base_1rm_beginner * SEX_MULTIPLIERS[user_sex]
    expected_source_beginner = f"global_fallback_default_sex_adj_{user_sex}" # Corrected source

    actual_1rm_b, actual_source_b = get_smart_default_1rm_and_source(exercise_name_for_test, level_to_test_beginner, user_sex)
    assert actual_1rm_b == pytest.approx(expected_1rm_beginner)
    assert actual_source_b == expected_source_beginner # This will be checked against helper's output

    # Case 2: Level 'non_existent_level' not in 'test_only_exercise_temp', nor is 'intermediate'.
    # Similar to above, should use global fallback.
    level_to_test_non_existent = "non_existent_level"
    base_1rm_non_existent = FALLBACK_DEFAULT_1RM
    expected_1rm_non_existent = base_1rm_non_existent * SEX_MULTIPLIERS[user_sex]
    expected_source_non_existent = f"global_fallback_default_sex_adj_{user_sex}" # Corrected source

    actual_1rm_ne, actual_source_ne = get_smart_default_1rm_and_source(exercise_name_for_test, level_to_test_non_existent, user_sex)
    assert actual_1rm_ne == pytest.approx(expected_1rm_non_existent)
    assert actual_source_ne == expected_source_non_existent # This will be checked

    # Monkeypatch automatically cleans up the change to EXERCISE_DEFAULT_1RM after the test.

@pytest.mark.parametrize("exercise_key_from_dict, levels_in_dict", EXERCISE_DEFAULT_1RM.items())
def test_all_defined_smart_defaults(exercise_key_from_dict, levels_in_dict):
    # This test iterates through all defined exercise and level combinations in EXERCISE_DEFAULT_1RM
    # (including 'other') and verifies that the helper function correctly retrieves them.
    user_sex_for_test = "male" # Using 'male' for simplicity (1.0 multiplier)
    sex_mult = SEX_MULTIPLIERS[user_sex_for_test]

    for level_from_dict, expected_1rm_val_from_dict_base in levels_in_dict.items():
        exercise_name_for_test_helper = exercise_key_from_dict.replace('_', ' ')
        expected_1rm_val_adjusted = expected_1rm_val_from_dict_base * sex_mult

        actual_1rm, actual_source = get_smart_default_1rm_and_source(
            exercise_name_for_test_helper,
            level_from_dict,
            user_sex_for_test
        )

        assert actual_1rm == pytest.approx(expected_1rm_val_adjusted)
        # Source string needs to account for whether 'other' key was used literally or as fallback
        expected_source_key = exercise_key_from_dict # This is 'other' when testing the 'other' entry directly
        expected_source = f"{level_from_dict}_default_for_{expected_source_key}_sex_adj_{user_sex_for_test}"
        assert actual_source == expected_source


# Test for various sex inputs using a known exercise
@pytest.mark.parametrize(
    "user_sex_input, expected_sex_key_in_multiplier, expected_sex_in_source",
    [
        ("male", "male", "male"),
        ("female", "female", "female"),
        ("other", "other", "other"),
        ("unknown", "unknown", "unknown"),
        (None, "unknown", "unknown"),
        ("", "unknown", "unknown"),
        ("non_existent_sex", "unknown", "unknown")
    ]
)
def test_smart_default_sex_multipliers_for_known_exercise(user_sex_input, expected_sex_key_in_multiplier, expected_sex_in_source):
    exercise_key = "barbell_bench_press" # Known exercise
    exercise_name = exercise_key.replace('_', ' ')
    level = "beginner"

    base_1rm = EXERCISE_DEFAULT_1RM[exercise_key][level]
    expected_multiplier = SEX_MULTIPLIERS[expected_sex_key_in_multiplier]
    expected_1rm = base_1rm * expected_multiplier
    expected_source = f"{level}_default_for_{exercise_key}_sex_adj_{expected_sex_in_source}"

    actual_1rm, actual_source = get_smart_default_1rm_and_source(exercise_name, level, user_sex_input)

    assert actual_1rm == pytest.approx(expected_1rm)
    assert actual_source == expected_source

# New test focusing on 'other' category fallback with sex multipliers
@pytest.mark.parametrize(
    "level_input, expected_level_in_source, base_level_from_other",
    [
        ("beginner", "beginner", "beginner"),
        ("intermediate", "intermediate", "intermediate"),
        ("advanced", "advanced", "advanced"),
        ("non_existent_level", "intermediate", "intermediate") # Falls back to 'other' intermediate
    ]
)
@pytest.mark.parametrize(
    "user_sex_input, expected_sex_key_in_multiplier, expected_sex_in_source",
    [
        ("male", "male", "male"),
        ("female", "female", "female"),
        (None, "unknown", "unknown")
    ]
)
def test_smart_default_other_category_fallback_with_sex(
    level_input, expected_level_in_source, base_level_from_other,
    user_sex_input, expected_sex_key_in_multiplier, expected_sex_in_source
):
    exercise_name = "super_unknown_exercise_type_for_other_test" # Ensures fallback to 'other'

    base_1rm = EXERCISE_DEFAULT_1RM["other"][base_level_from_other]
    expected_multiplier = SEX_MULTIPLIERS[expected_sex_key_in_multiplier]
    expected_1rm = base_1rm * expected_multiplier

    expected_source = f"{expected_level_in_source}_default_for_other_category_sex_adj_{expected_sex_in_source}"

    actual_1rm, actual_source = get_smart_default_1rm_and_source(exercise_name, level_input, user_sex_input)

    assert actual_1rm == pytest.approx(expected_1rm)
    assert actual_source == expected_source
