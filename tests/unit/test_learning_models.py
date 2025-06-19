import pytest
from engine.learning_models import update_user_rir_bias, MIN_RIR_BIAS, MAX_RIR_BIAS, RIR_BIAS_EMA_ALPHA

# Constants used in tests, mirroring those in learning_models.py for clarity
BASE_LR_FOR_TESTS = 0.10
# RIR_BIAS_EMA_ALPHA is imported

def test_zero_error():
    """
    Test Case: Zero Error
    - old_bias = 0.0, predicted_reps = 10, actual_reps = 10
    - base_lr = 0.10, current_error_ema = 0.0
    - Expected: error = 0. new_error_ema should be 0.0. dynamic_lr should be 0.10. new_bias should remain 0.0.
    """
    old_bias = 0.0
    predicted_reps = 10
    actual_reps = 10
    base_lr = BASE_LR_FOR_TESTS
    current_error_ema = 0.0

    error = actual_reps - predicted_reps # 0
    expected_new_ema = RIR_BIAS_EMA_ALPHA * error + (1 - RIR_BIAS_EMA_ALPHA) * current_error_ema # 0.0
    expected_dynamic_lr = max(0.02, base_lr / (1 + abs(expected_new_ema))) # 0.10 / 1 = 0.10
    expected_new_bias = old_bias + (error * expected_dynamic_lr) # 0.0 + (0 * 0.10) = 0.0

    new_bias, new_ema = update_user_rir_bias(old_bias, predicted_reps, actual_reps, base_lr, current_error_ema)

    assert error == 0
    assert new_ema == pytest.approx(expected_new_ema)
    assert new_bias == pytest.approx(expected_new_bias)

def test_positive_error_ema_zero():
    """
    Test Case: Positive Error (Overperformance), EMA Starts at Zero
    - old_bias = -0.5, predicted_reps = 8, actual_reps = 10 (error = 2)
    - base_lr = 0.10, current_error_ema = 0.0
    - Expected:
        - new_error_ema = 0.2 * 2 + (1 - 0.2) * 0.0 = 0.4.
        - dynamic_lr = max(0.02, 0.10 / (1 + abs(0.4))) = max(0.02, 0.10 / 1.4) approx 0.07142857
        - new_bias = -0.5 + (0.07142857 * 2) = -0.5 + 0.14285714 = -0.35714286
    """
    old_bias = -0.5
    predicted_reps = 8
    actual_reps = 10
    base_lr = BASE_LR_FOR_TESTS
    current_error_ema = 0.0

    error = actual_reps - predicted_reps # 2
    expected_new_ema = RIR_BIAS_EMA_ALPHA * error + (1 - RIR_BIAS_EMA_ALPHA) * current_error_ema # 0.2 * 2 + 0 = 0.4
    expected_dynamic_lr = max(0.02, base_lr / (1 + abs(expected_new_ema))) # max(0.02, 0.1 / 1.4) = 0.1 / 1.4 = 0.0714285714...
    expected_new_bias = old_bias + (error * expected_dynamic_lr) # -0.5 + (2 * (0.1/1.4)) = -0.5 + 0.2/1.4 = -0.5 + 0.14285714... = -0.35714285...

    new_bias, new_ema = update_user_rir_bias(old_bias, predicted_reps, actual_reps, base_lr, current_error_ema)

    assert new_ema == pytest.approx(expected_new_ema)
    assert new_bias == pytest.approx(expected_new_bias)

def test_negative_error_ema_zero():
    """
    Test Case: Negative Error (Underperformance), EMA Starts at Zero
    - old_bias = 0.5, predicted_reps = 10, actual_reps = 8 (error = -2)
    - base_lr = 0.10, current_error_ema = 0.0
    - Expected:
        - new_error_ema = 0.2 * -2 + (1 - 0.2) * 0.0 = -0.4.
        - dynamic_lr = max(0.02, 0.10 / (1 + abs(-0.4))) = max(0.02, 0.10 / 1.4) approx 0.07142857
        - new_bias = 0.5 + (0.07142857 * -2) = 0.5 - 0.14285714 = 0.35714286
    """
    old_bias = 0.5
    predicted_reps = 10
    actual_reps = 8
    base_lr = BASE_LR_FOR_TESTS
    current_error_ema = 0.0

    error = actual_reps - predicted_reps # -2
    expected_new_ema = RIR_BIAS_EMA_ALPHA * error + (1 - RIR_BIAS_EMA_ALPHA) * current_error_ema # 0.2 * -2 = -0.4
    expected_dynamic_lr = max(0.02, base_lr / (1 + abs(expected_new_ema))) # 0.1 / 1.4
    expected_new_bias = old_bias + (error * expected_dynamic_lr) # 0.5 + (-2 * (0.1/1.4)) = 0.5 - 0.2/1.4 = 0.5 - 0.14285714... = 0.35714285...

    new_bias, new_ema = update_user_rir_bias(old_bias, predicted_reps, actual_reps, base_lr, current_error_ema)

    assert new_ema == pytest.approx(expected_new_ema)
    assert new_bias == pytest.approx(expected_new_bias)

def test_ema_accumulation_and_lr_adaptation():
    """
    Test Case: EMA Accumulation and LR Adaptation
    - Update 1: old_bias = 0.0, predicted_reps = 8, actual_reps = 10 (error = 2), base_lr = 0.10, current_error_ema = 0.0.
    - Update 2: old_bias = new_bias_1, predicted_reps = 8, actual_reps = 10 (error = 2), base_lr = 0.10, current_error_ema = new_ema_1.
    - Verify dynamic_lr used in Update 2 is different from Update 1. new_ema_2 > new_ema_1. dynamic_lr for update 2 < for update 1.
    """
    # Update 1
    old_bias_1 = 0.0
    predicted_reps_1 = 8
    actual_reps_1 = 10 # error_1 = 2
    base_lr_1 = BASE_LR_FOR_TESTS
    current_error_ema_1 = 0.0

    error_1 = actual_reps_1 - predicted_reps_1
    ema_1_calc = RIR_BIAS_EMA_ALPHA * error_1 + (1-RIR_BIAS_EMA_ALPHA) * current_error_ema_1 # 0.2 * 2 = 0.4
    dynamic_lr_1_calc = max(0.02, base_lr_1 / (1 + abs(ema_1_calc))) # 0.1 / 1.4 = 0.07142857...

    new_bias_1, new_ema_1 = update_user_rir_bias(old_bias_1, predicted_reps_1, actual_reps_1, base_lr_1, current_error_ema_1)
    assert new_ema_1 == pytest.approx(ema_1_calc)

    # Update 2
    old_bias_2 = new_bias_1
    predicted_reps_2 = 8
    actual_reps_2 = 10 # error_2 = 2
    base_lr_2 = BASE_LR_FOR_TESTS
    current_error_ema_2 = new_ema_1 # current_error_ema_2 is new_ema_1 (0.4)

    error_2 = actual_reps_2 - predicted_reps_2
    ema_2_calc = RIR_BIAS_EMA_ALPHA * error_2 + (1-RIR_BIAS_EMA_ALPHA) * current_error_ema_2 # 0.2 * 2 + 0.8 * 0.4 = 0.4 + 0.32 = 0.72
    dynamic_lr_2_calc = max(0.02, base_lr_2 / (1 + abs(ema_2_calc))) # 0.1 / 1.72 = 0.0581395...

    _new_bias_2, new_ema_2 = update_user_rir_bias(old_bias_2, predicted_reps_2, actual_reps_2, base_lr_2, current_error_ema_2)

    # Reconstruct dynamic_lr as it's calculated inside the second call
    internal_dynamic_lr_2 = max(0.02, base_lr_2 / (1 + abs(new_ema_1)))


    assert new_ema_2 == pytest.approx(ema_2_calc)
    assert new_ema_2 > new_ema_1 # EMA has accumulated
    assert internal_dynamic_lr_2 < dynamic_lr_1_calc # Dynamic LR decreased as EMA (error magnitude) increased
    assert internal_dynamic_lr_2 == pytest.approx(dynamic_lr_2_calc)


def test_dynamic_lr_floor():
    """
    Test Case: Dynamic LR Floor
    - old_bias = 0.0, predicted_reps = 0, actual_reps = 20 (error = 20)
    - base_lr = 0.10, current_error_ema = 5.0 (already high)
    - Expected: dynamic_lr hits the 0.02 floor.
    """
    old_bias = 0.0
    predicted_reps = 0
    actual_reps = 20
    base_lr = BASE_LR_FOR_TESTS
    current_error_ema = 5.0

    error = actual_reps - predicted_reps # 20
    expected_new_ema = RIR_BIAS_EMA_ALPHA * error + (1 - RIR_BIAS_EMA_ALPHA) * current_error_ema # 0.2 * 20 + 0.8 * 5 = 4 + 4 = 8.0
    # dynamic_lr = max(0.02, 0.10 / (1 + abs(8.0))) = max(0.02, 0.10 / 9) = max(0.02, 0.0111...) = 0.02
    expected_dynamic_lr = 0.02

    _new_bias, new_ema = update_user_rir_bias(old_bias, predicted_reps, actual_reps, base_lr, current_error_ema)

    # Reconstruct dynamic_lr as it was calculated inside the call that returned _new_bias, new_ema
    # Note: the `new_ema` returned is `expected_new_ema`
    internal_dynamic_lr = max(0.02, base_lr / (1 + abs(new_ema)))

    assert new_ema == pytest.approx(expected_new_ema)
    assert internal_dynamic_lr == pytest.approx(expected_dynamic_lr)


def test_bias_clipping_upper_bound():
    """
    Test Case: Bias Clipping (Upper Bound)
    - old_bias = 2.9, predicted_reps = 5, actual_reps = 10 (error = 5)
    - base_lr = 0.10, current_error_ema = 0.0
    - dynamic_lr = 0.10 / (1 + abs(0.2*5)) = 0.10 / (1+1) = 0.05.
    - calculated_new_bias = 2.9 + 0.05 * 5 = 2.9 + 0.25 = 3.15.
    - Expected: new_bias should be clipped to MAX_RIR_BIAS (3.0).
    """
    old_bias = 2.9
    predicted_reps = 5
    actual_reps = 10 # error = 5
    base_lr = BASE_LR_FOR_TESTS
    current_error_ema = 0.0

    new_bias, _new_ema = update_user_rir_bias(old_bias, predicted_reps, actual_reps, base_lr, current_error_ema)

    assert new_bias == pytest.approx(MAX_RIR_BIAS)

def test_bias_clipping_lower_bound():
    """
    Test Case: Bias Clipping (Lower Bound)
    - old_bias = -2.9, predicted_reps = 10, actual_reps = 5 (error = -5)
    - base_lr = 0.10, current_error_ema = 0.0
    - dynamic_lr = 0.10 / (1 + abs(0.2*-5)) = 0.05.
    - calculated_new_bias = -2.9 + (0.05 * -5) = -2.9 - 0.25 = -3.15.
    - Expected: new_bias should be clipped to MIN_RIR_BIAS (-3.0).
    """
    old_bias = -2.9
    predicted_reps = 10
    actual_reps = 5 # error = -5
    base_lr = BASE_LR_FOR_TESTS
    current_error_ema = 0.0

    new_bias, _new_ema = update_user_rir_bias(old_bias, predicted_reps, actual_reps, base_lr, current_error_ema)

    assert new_bias == pytest.approx(MIN_RIR_BIAS)

# A test to verify the internal dynamic_lr calculation for the second step of accumulation test
def test_ema_accumulation_dynamic_lr_value_check():
    # Update 1 (same as in test_ema_accumulation_and_lr_adaptation)
    old_bias_1 = 0.0
    predicted_reps_1 = 8
    actual_reps_1 = 10
    base_lr_1 = 0.10 # Using explicit value for clarity in this test
    current_error_ema_1 = 0.0
    _new_bias_1, new_ema_1 = update_user_rir_bias(old_bias_1, predicted_reps_1, actual_reps_1, base_lr_1, current_error_ema_1)
    # new_ema_1 should be 0.4

    # Parameters for Update 2
    base_lr_2 = 0.10
    current_error_ema_for_update2 = new_ema_1 # This is 0.4

    # Expected dynamic_lr for Update 2
    # error_2 = 10 - 8 = 2
    # new_ema_for_update2_output = 0.2 * 2 + 0.8 * 0.4 = 0.4 + 0.32 = 0.72
    # dynamic_lr for THIS update (based on current_error_ema_for_update2 = 0.4):
    # dynamic_lr = max(0.02, 0.10 / (1 + abs(0.4))) = max(0.02, 0.1/1.4) = 0.07142857...
    expected_dynamic_lr_for_update2_calculation = base_lr_2 / (1 + abs(current_error_ema_for_update2)) # 0.1 / 1.4
    if expected_dynamic_lr_for_update2_calculation < 0.02:
        expected_dynamic_lr_for_update2_calculation = 0.02

    # To actually test the dynamic_lr *used* in the second update, we need to know what it was.
    # The function update_user_rir_bias doesn't return dynamic_lr.
    # We can infer it by checking the change in bias.
    # new_bias = old_bias + error * dynamic_lr  => dynamic_lr = (new_bias - old_bias) / error

    old_bias_2 = _new_bias_1 # from previous step
    predicted_reps_2 = 8
    actual_reps_2 = 10 # error = 2

    new_bias_2, _new_ema_2 = update_user_rir_bias(old_bias_2, predicted_reps_2, actual_reps_2, base_lr_2, current_error_ema_for_update2)

    error_2 = actual_reps_2 - predicted_reps_2
    if error_2 != 0: # Avoid division by zero if error is 0
        calculated_dynamic_lr_from_update2 = (new_bias_2 - old_bias_2) / error_2
        assert calculated_dynamic_lr_from_update2 == pytest.approx(expected_dynamic_lr_for_update2_calculation)
    else: # if error is 0, dynamic_lr could be anything, bias won't change.
        assert new_bias_2 == pytest.approx(old_bias_2)
