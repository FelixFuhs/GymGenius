import pytest
from unittest.mock import MagicMock
from engine.predictions import (
    estimate_1rm_with_rir_bias,
    round_to_available_plates,
    calculate_confidence_score,
    DEFAULT_BARBELL_WEIGHT_KG,
    DEFAULT_AVAILABLE_PLATES_KG
)

# Test cases for estimate_1rm_with_rir_bias

def test_estimate_1rm_rir_bias_specific_case():
    # Test case based on formula: weight / (1 - 0.0333 * (reps + adjusted_rir))
    # User feedback mentioned an expected output of ~103kg for this input,
    # which differs from the calculation based on the implemented formula.
    # This test will assert against the implemented formula's output.
    weight = 100.0
    reps = 5
    rir = 2
    user_rir_bias = 1.0

    # Calculation based on the implemented function:
    # adjusted_rir = max(0, 2 - 1.0) = 1.0
    # total_reps_for_estimation = 5 + 1.0 = 6.0
    # denominator = 1 - (0.0333 * 6.0) = 1 - 0.1998 = 0.8002
    # estimated_1rm = 100.0 / 0.8002 = 124.96875...
    # Rounded to 2 decimal places by the function: 124.97
    expected_output = 124.97

    actual_output = estimate_1rm_with_rir_bias(weight, reps, rir, user_rir_bias)
    assert actual_output == pytest.approx(expected_output, abs=0.01)

def test_estimate_1rm_rir_bias_zero_bias():
    weight = 100.0
    reps = 5
    rir = 2
    user_rir_bias = 0.0 # Zero bias

    expected_output = 130.40 # Calculation: 100.0 / (1 - 0.0333 * 7.0)
    actual_output = estimate_1rm_with_rir_bias(weight, reps, rir, user_rir_bias)
    assert actual_output == pytest.approx(expected_output, abs=0.01)

def test_estimate_1rm_rir_bias_negative_effective_rir():
    weight = 100.0
    reps = 5
    rir = 1
    user_rir_bias = 2.0

    expected_output = 119.98 # Calculation: 100.0 / (1 - 0.0333 * 5.0)
    actual_output = estimate_1rm_with_rir_bias(weight, reps, rir, user_rir_bias)
    assert actual_output == pytest.approx(expected_output, abs=0.01)

def test_estimate_1rm_rir_bias_high_reps_to_failure_cap():
    weight = 100.0
    reps = 28
    rir = 2
    user_rir_bias = 0.0

    expected_output = 2915.45 # Calculation: 100.0 / (1 - 0.0333 * 29.0) due to capping
    actual_output = estimate_1rm_with_rir_bias(weight, reps, rir, user_rir_bias)
    assert actual_output == pytest.approx(expected_output, abs=0.01)

def test_estimate_1rm_rir_bias_invalid_reps():
    weight = 100.0
    reps = -1
    rir = 2
    user_rir_bias = 0.0
    expected_output = 100.0
    actual_output = estimate_1rm_with_rir_bias(weight, reps, rir, user_rir_bias)
    assert actual_output == pytest.approx(expected_output, abs=0.01)

def test_estimate_1rm_rir_bias_invalid_rir():
    weight = 100.0
    reps = 5
    rir = -1
    user_rir_bias = 0.0

    expected_output = 119.98 # rir treated as 0, so adjusted_rir = 0. total_reps = 5.
    actual_output = estimate_1rm_with_rir_bias(weight, reps, rir, user_rir_bias)
    assert actual_output == pytest.approx(expected_output, abs=0.01)

def test_estimate_1rm_rir_bias_total_reps_estimation_zero_or_less():
    weight = 100.0
    reps = 0
    rir = 0
    user_rir_bias = 0.0
    expected_output = 100.0
    actual_output = estimate_1rm_with_rir_bias(weight, reps, rir, user_rir_bias)
    assert actual_output == pytest.approx(expected_output, abs=0.01)

    reps = 0
    rir = 1
    user_rir_bias = 2.0 # adjusted_rir becomes 0, total_reps_for_estimation = 0
    expected_output = 100.0
    actual_output = estimate_1rm_with_rir_bias(weight, reps, rir, user_rir_bias)
    assert actual_output == pytest.approx(expected_output, abs=0.01)

# --- Test cases for round_to_available_plates ---

def test_round_to_plates_specific_case_from_user_feedback():
    target_weight = 77.0
    available_plates = [1.25, 2.5]
    barbell_weight = 20.0
    expected_rounded_weight = 77.5

    actual_rounded_weight = round_to_available_plates(target_weight, available_plates, barbell_weight)
    assert actual_rounded_weight == pytest.approx(expected_rounded_weight)

def test_round_to_plates_default_settings():
    target_weight = 77.8
    expected_rounded_weight = 78.0

    actual_rounded_weight = round_to_available_plates(target_weight, None, None)
    assert actual_rounded_weight == pytest.approx(expected_rounded_weight)

def test_round_to_plates_target_below_barbell():
    target_weight = 15.0
    barbell_weight = 20.0
    expected_rounded_weight = 20.0

    actual_rounded_weight = round_to_available_plates(target_weight, [1.25, 2.5], barbell_weight)
    assert actual_rounded_weight == pytest.approx(expected_rounded_weight)

def test_round_to_plates_target_equals_barbell():
    target_weight = 20.0
    barbell_weight = 20.0
    expected_rounded_weight = 20.0

    actual_rounded_weight = round_to_available_plates(target_weight, [1.25, 2.5], barbell_weight)
    assert actual_rounded_weight == pytest.approx(expected_rounded_weight)

def test_round_to_plates_empty_plate_list():
    target_weight = 77.8
    expected_rounded_weight = 78.0

    actual_rounded_weight_empty = round_to_available_plates(target_weight, [], 20.0)
    assert actual_rounded_weight_empty == pytest.approx(expected_rounded_weight)

    actual_rounded_weight_invalid = round_to_available_plates(target_weight, [-5, 0], 20.0)
    assert actual_rounded_weight_invalid == pytest.approx(expected_rounded_weight)

def test_round_to_plates_no_possible_increment():
    target_weight = 21.0
    available_plates = [5, 10]
    barbell_weight = 20.0
    expected_rounded_weight = 20.0

    actual_rounded_weight = round_to_available_plates(target_weight, available_plates, barbell_weight)
    assert actual_rounded_weight == pytest.approx(expected_rounded_weight)

    target_weight_2 = 26.0
    expected_rounded_weight_2 = 30.0
    actual_rounded_weight_2 = round_to_available_plates(target_weight_2, available_plates, barbell_weight)
    assert actual_rounded_weight_2 == pytest.approx(expected_rounded_weight_2)

def test_round_to_plates_equidistant_preference():
    target_weight = 27.5
    available_plates = [2.5, 5]
    barbell_weight = 20.0
    expected_rounded_weight = 30.0
    actual_rounded_weight = round_to_available_plates(target_weight, available_plates, barbell_weight)
    assert actual_rounded_weight == pytest.approx(expected_rounded_weight)

def test_round_to_plates_with_many_small_plates():
    target_weight = 61.3
    available_plates = DEFAULT_AVAILABLE_PLATES_KG
    barbell_weight = DEFAULT_BARBELL_WEIGHT_KG
    expected_rounded_weight = 61.5
    actual_rounded_weight = round_to_available_plates(target_weight, available_plates, barbell_weight)
    assert actual_rounded_weight == pytest.approx(expected_rounded_weight)

def test_round_to_plates_invalid_barbell_weight():
    target_weight = 77.8
    expected_rounded_weight = 78.0

    actual_rounded_weight_neg_barbell = round_to_available_plates(target_weight, None, -10.0)
    assert actual_rounded_weight_neg_barbell == pytest.approx(expected_rounded_weight)

    assert round_to_available_plates(target_weight, None, 0.0) == pytest.approx(78.0)
    assert round_to_available_plates(target_weight, None, None) == pytest.approx(78.0)

def test_round_to_plates_user_case_exact_match():
    target_weight = 100.0
    available_plates = [1.25, 2.5, 5, 10, 15, 20, 25]
    barbell_weight = 25.0
    expected_rounded_weight = 100.0
    actual_rounded_weight = round_to_available_plates(target_weight, available_plates, barbell_weight)
    assert actual_rounded_weight == pytest.approx(expected_rounded_weight)

def test_round_to_plates_user_case_near_match():
    target_weight = 101.0
    available_plates = [1.25, 2.5, 5, 10, 15, 20, 25]
    barbell_weight = 25.0
    expected_rounded_weight = 100.0
    actual_rounded_weight = round_to_available_plates(target_weight, available_plates, barbell_weight)
    assert actual_rounded_weight == pytest.approx(expected_rounded_weight)

    target_weight_2 = 102.0
    expected_rounded_weight_2 = 102.5
    actual_rounded_weight_2 = round_to_available_plates(target_weight_2, available_plates, barbell_weight)
    assert actual_rounded_weight_2 == pytest.approx(expected_rounded_weight_2)

# --- Test cases for calculate_confidence_score ---

def test_confidence_score_ideal_case():
    mock_cursor = MagicMock()
    # Data: [98, 98, 100, 102, 102]. Mean=100. Stddev = 2.
    history_records = [
        {'estimated_1rm': 98.0}, {'estimated_1rm': 98.0},
        {'estimated_1rm': 100.0},
        {'estimated_1rm': 102.0},{'estimated_1rm': 102.0}
    ]
    mock_cursor.fetchall.return_value = history_records

    confidence = calculate_confidence_score("user1", "ex1", mock_cursor)
    assert confidence == pytest.approx(0.98) # 1.0 - (2.0 / 100.0)

def test_confidence_score_insufficient_data():
    mock_cursor = MagicMock()
    history_records = [{'estimated_1rm': 100.0}, {'estimated_1rm': 102.0}] # Only 2 records
    mock_cursor.fetchall.return_value = history_records

    confidence = calculate_confidence_score("user1", "ex1", mock_cursor)
    assert confidence is None

def test_confidence_score_no_data():
    mock_cursor = MagicMock()
    history_records = [] # No records
    mock_cursor.fetchall.return_value = history_records

    confidence = calculate_confidence_score("user1", "ex1", mock_cursor)
    assert confidence is None

def test_confidence_score_perfect_consistency():
    mock_cursor = MagicMock()
    history_records = [
        {'estimated_1rm': 100.0}, {'estimated_1rm': 100.0}, {'estimated_1rm': 100.0}
    ]
    mock_cursor.fetchall.return_value = history_records

    confidence = calculate_confidence_score("user1", "ex1", mock_cursor)
    assert confidence == pytest.approx(1.0)

def test_confidence_score_zero_mean():
    mock_cursor = MagicMock()
    history_records = [
        {'estimated_1rm': 0.0}, {'estimated_1rm': 0.0}, {'estimated_1rm': 0.0}
    ]
    mock_cursor.fetchall.return_value = history_records

    confidence = calculate_confidence_score("user1", "ex1", mock_cursor)
    assert confidence == pytest.approx(0.0)

def test_confidence_score_high_variability():
    mock_cursor = MagicMock()
    # Data: [1, 1, 1, 1, 46]. Mean = 10. Stddev approx 20.12. CV approx 2.012.
    # Confidence = 1 - 2.012 -> clamped to 0.0.
    history_records = [
        {'estimated_1rm': 1.0}, {'estimated_1rm': 1.0}, {'estimated_1rm': 1.0},
        {'estimated_1rm': 1.0}, {'estimated_1rm': 46.0},
    ]
    mock_cursor.fetchall.return_value = history_records

    confidence = calculate_confidence_score("user1", "ex1", mock_cursor)
    assert confidence == pytest.approx(0.0)

def test_confidence_score_db_error():
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = Exception("DB error")

    confidence = calculate_confidence_score("user1", "ex1", mock_cursor)
    assert confidence is None
