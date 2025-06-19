"""
Core logic for learning models related to user performance and fatigue.
"""
from datetime import datetime, timedelta
from math import exp
from typing import List, Dict, Any
from pprint import pprint

# Define reasonable bounds for RIR bias
MIN_RIR_BIAS = -3.0 # As per new spec in a comment, though original was -2.0
MAX_RIR_BIAS = 3.0  # As per new spec in a comment, though original was 5.0
RIR_BIAS_EMA_ALPHA = 0.2 # Smoothing factor for EMA, can be moved to constants.py

def update_user_rir_bias(
    old_bias: float,
    predicted_reps: int,
    actual_reps: int,
    base_lr: float, # Corresponds to users.rir_bias_lr
    current_error_ema: float # Corresponds to users.rir_bias_error_ema
) -> tuple[float, float]:
    """
    Updates the user's RIR (Reps In Reserve) bias based on performance.

    The learning rate (LR) for the bias update adapts per user based on the
    Exponential Moving Average (EMA) of the error in predicted vs. actual reps.
    The formula for the dynamic learning rate is: base_lr / (1 + |EMA(error)|).
    This adaptive LR helps maintain stability if rep errors are noisy, while allowing
    responsiveness when performance is consistent.

    Args:
        old_bias: The user's current RIR bias.
        predicted_reps: The number of reps predicted for the set at the given RIR.
        actual_reps: The number of reps actually performed.
        base_lr: The user's base learning rate for RIR bias adjustments (users.rir_bias_lr).
        current_error_ema: The user's current EMA of the prediction error (users.rir_bias_error_ema).

    Returns:
        A tuple containing:
            - new_bias (float): The updated RIR bias, clipped within bounds.
            - new_error_ema (float): The updated EMA of the prediction error.
    """
    error = float(actual_reps - predicted_reps)

    # Use RIR_BIAS_EMA_ALPHA (defined at module level or imported from constants)
    alpha = RIR_BIAS_EMA_ALPHA
    new_error_ema = alpha * error + (1 - alpha) * current_error_ema

    # Adaptive LR: bigger updates when variance low, ensure it doesn't go too low
    # Using new_error_ema for dynamic_lr calculation as per subtask description
    dynamic_lr = max(0.02, base_lr / (1 + abs(new_error_ema)))

    # Calculate bias update
    # The original logic was: new_bias = current_bias - (error_signal * learning_rate)
    # If error = actual - predicted:
    #   - actual < predicted (underperformed) => error is negative.
    #     We want to INCREASE bias (make it more positive, or less negative).
    #     So, new_bias = old_bias - (negative_error * dynamic_lr) = old_bias + adjustment.
    #   - actual > predicted (overperformed) => error is positive.
    #     We want to DECREASE bias (make it less positive, or more negative).
    #     So, new_bias = old_bias - (positive_error * dynamic_lr) = old_bias - adjustment.
    # This matches the original logic's direction.
    bias_adjustment = error * dynamic_lr # This is 'dynamic_lr * error' from the issue's formula

    # Update bias: if actual > predicted (error > 0), bias should increase (user is stronger/underestimated RIR)
    # if actual < predicted (error < 0), bias should decrease (user is weaker/overestimated RIR)
    new_bias = old_bias + bias_adjustment # Corrected line as per subtask

    # Clip the new bias using module-level constants
    new_bias = max(MIN_RIR_BIAS, min(new_bias, MAX_RIR_BIAS))

    return new_bias, new_error_ema


# Define a type alias for session records for clarity
SessionRecord = Dict[str, Any] # Expects keys like 'session_date': datetime, 'stimulus': float

DEFAULT_RECOVERY_TAU_MAP: Dict[str, float] = {
    'chest': 48.0,
    'back': 48.0,
    'shoulders': 36.0,
    'biceps': 36.0,
    'triceps': 36.0,
    'quads': 72.0,
    'hamstrings': 48.0,
    'glutes': 48.0,
    'calves': 24.0,
    'forearms': 24.0,
    'core': 24.0,
    'default': 48.0 # A general default if a specific muscle group isn't listed
}

def calculate_current_fatigue(
    muscle_group: str,
    session_history: List[SessionRecord],
    default_recovery_tau_map: Dict[str, float] = DEFAULT_RECOVERY_TAU_MAP,
    user_recovery_multiplier: float = 1.0
) -> float:
    """
    Calculates the current accumulated fatigue for a specific muscle group
    based on an exponential decay model.

    Args:
        muscle_group: The muscle group for which to calculate fatigue (e.g., 'chest').
        session_history: A list of session records. Each record is a dictionary
                         expected to have 'session_date' (datetime) and
                         'stimulus' (float) keys.
        default_recovery_tau_map: A dictionary mapping muscle groups to their
                                  baseline recovery tau values in hours.
        user_recovery_multiplier: A multiplier to adjust the tau value for
                                  individual recovery rates (e.g., if >1.0, recovery is slower).

    Returns:
        The calculated current fatigue value (a unitless accumulation).
    """
    now = datetime.now()
    current_fatigue: float = 0.0

    base_tau_hours = default_recovery_tau_map.get(muscle_group.lower(), default_recovery_tau_map['default'])
    adjusted_tau_hours = base_tau_hours * user_recovery_multiplier

    if adjusted_tau_hours <= 0: # Avoid division by zero or negative tau
        adjusted_tau_hours = default_recovery_tau_map['default'] # Fallback to a sensible default

    for session in session_history:
        session_date = session.get('session_date')
        stimulus = session.get('stimulus')

        if not isinstance(session_date, datetime) or not isinstance(stimulus, (float, int)):
            # Optionally log a warning or skip this record
            # print(f"Warning: Invalid session record skipped: {session}")
            continue

        time_elapsed_delta: timedelta = now - session_date
        time_elapsed_hours: float = time_elapsed_delta.total_seconds() / 3600.0

        # Only consider sessions that are not in the future and within a reasonable timeframe (e.g., last 14 days)
        # For this model, negative time_elapsed_hours (future sessions) would lead to exp(positive), increasing fatigue.
        # Very old sessions have negligible impact due to decay.
        if time_elapsed_hours < 0:
            continue

        decay_factor = exp(-time_elapsed_hours / adjusted_tau_hours)
        current_fatigue += float(stimulus) * decay_factor

    return current_fatigue

if __name__ == '__main__':
    # Example usage for update_user_rir_bias (OLD EXAMPLE - NEEDS UPDATE FOR NEW SIGNATURE)
    # current_bias = 2.0
    # base_lr_example = 0.1
    # current_ema_example = 0.0
    # pred_reps_s1 = 8
    # act_reps_s1 = 6
    # new_bias_s1, new_ema_s1 = update_user_rir_bias(current_bias, pred_reps_s1, act_reps_s1, base_lr_example, current_ema_example)
    # print(f"Scenario 1 (Underperformance): old_bias={current_bias}, base_lr={base_lr_example}, current_ema={current_ema_example}, predicted={pred_reps_s1}, actual={act_reps_s1} => new_bias={new_bias_s1:.3f}, new_ema={new_ema_s1:.3f}")
    # Error = 6 - 8 = -2.
    # new_error_ema = 0.2 * -2 + (1 - 0.2) * 0.0 = -0.4 + 0 = -0.4
    # dynamic_lr = max(0.02, 0.1 / (1 + abs(-0.4))) = max(0.02, 0.1 / 1.4) = max(0.02, 0.0714) = 0.0714
    # bias_update = -2 * 0.0714 = -0.1428
    # new_bias = 2.0 - (-0.1428) = 2.1428. Clipped if needed.

    # pred_reps_s2 = 6
    # act_reps_s2 = 8
    # new_bias_s2, new_ema_s2 = update_user_rir_bias(current_bias, pred_reps_s2, act_reps_s2, base_lr_example, new_ema_s1) # Using previous EMA
    # print(f"Scenario 2 (Overperformance): old_bias={current_bias}, base_lr={base_lr_example}, current_ema={new_ema_s1:.3f}, predicted={pred_reps_s2}, actual={act_reps_s2} => new_bias={new_bias_s2:.3f}, new_ema={new_ema_s2:.3f}")
    # Error = 8 - 6 = 2.
    # new_error_ema_s2 = 0.2 * 2 + (1-0.2) * (-0.4) = 0.4 - 0.32 = 0.08
    # dynamic_lr_s2 = max(0.02, 0.1 / (1 + abs(0.08))) = max(0.02, 0.1 / 1.08) = max(0.02, 0.0926) = 0.0926
    # bias_update_s2 = 2 * 0.0926 = 0.1852
    # new_bias_s2 = 2.0 - (0.1852) = 1.8148. Clipped if needed.


    # Example usage for calculate_current_fatigue
    print("\n--- Fatigue Calculation Example ---")
    history = [
        {'session_date': datetime.now() - timedelta(hours=24), 'stimulus': 100.0}, # 1 day ago
        {'session_date': datetime.now() - timedelta(hours=72), 'stimulus': 120.0}, # 3 days ago
        {'session_date': datetime.now() - timedelta(hours=120), 'stimulus': 80.0}  # 5 days ago
    ]
    # With invalid data
    history_with_invalid = [
        {'session_date': datetime.now() - timedelta(hours=24), 'stimulus': 100.0},
        {'session_date': "not a date", 'stimulus': 120.0}, # Invalid record
        {'session_date': datetime.now() - timedelta(hours=72), 'stimulus': "not a stimulus"}, # Invalid record
        {'session_date': datetime.now() + timedelta(hours=24), 'stimulus': 100.0}, # Future session
    ]

    chest_fatigue = calculate_current_fatigue('chest', history)
    print(f"Current CHEST fatigue (standard recovery): {chest_fatigue:.2f}")

    quads_fatigue = calculate_current_fatigue('quads', history)
    print(f"Current QUADS fatigue (standard recovery): {quads_fatigue:.2f}")

    chest_fatigue_faster_recovery = calculate_current_fatigue('chest', history, user_recovery_multiplier=0.8) # 20% faster recovery
    print(f"Current CHEST fatigue (faster recovery): {chest_fatigue_faster_recovery:.2f}")

    chest_fatigue_slower_recovery = calculate_current_fatigue('chest', history, user_recovery_multiplier=1.2) # 20% slower recovery
    print(f"Current CHEST fatigue (slower recovery): {chest_fatigue_slower_recovery:.2f}")

    unknown_muscle_fatigue = calculate_current_fatigue('unknown_muscle', history)
    print(f"Current UNKNOWN_MUSCLE fatigue (default tau): {unknown_muscle_fatigue:.2f}")

    fatigue_with_invalid = calculate_current_fatigue('chest', history_with_invalid)
    print(f"Fatigue with some invalid records (should skip them): {fatigue_with_invalid:.2f}")


# User sets goal: 0 = pure hypertrophy, 1 = pure strength
def calculate_training_params(goal_strength_fraction: float) -> dict:
    """
    Calculates training parameters based on a user's goal ranging from pure hypertrophy to pure strength.

    Args:
        goal_strength_fraction: A float between 0.0 (pure hypertrophy) and 1.0 (pure strength).

    Returns:
        A dictionary containing calculated training parameters:
        - 'load_percentage_of_1rm': Target load as a fraction of 1 Rep Max.
        - 'target_rir': Target Reps In Reserve (rounded for practical use).
        - 'target_rir_float': Target Reps In Reserve (as a float for precision).
        - 'rest_seconds': Recommended rest time in seconds.
        - 'rep_range_low': Lower end of the recommended rep range.
        - 'rep_range_high': Upper end of the recommended rep range.
    """
    if not 0.0 <= goal_strength_fraction <= 1.0:
        raise ValueError("goal_strength_fraction must be between 0.0 and 1.0")

    load_percentage = 0.60 + 0.35 * goal_strength_fraction
    target_rir_float = 2.5 - 1.5 * goal_strength_fraction  # Keep as float for now
    rest_minutes = 1.5 + 2.0 * goal_strength_fraction

    # Rep ranges
    rep_high_float = 6.0 + 6.0 * (1.0 - goal_strength_fraction) # Use floats for precision
    rep_high = int(round(rep_high_float))
    # Ensure rep_low is at least 1 and also considers the float value before rounding rep_high
    rep_low_candidate = rep_high_float - 4.0
    rep_low = int(round(max(1.0, rep_low_candidate)))

    # Ensure rep_low is not greater than rep_high after rounding adjustments
    if rep_low > rep_high:
        rep_low = rep_high

    return {
        'load_percentage_of_1rm': round(load_percentage, 4), # Store with precision
        'target_rir': int(round(target_rir_float)), # Round RIR for practical use
        'target_rir_float': round(target_rir_float, 2), # Also return float for potential finer use
        'rest_seconds': int(round(rest_minutes * 60)),  # in seconds
        'rep_range_low': rep_low,
        'rep_range_high': rep_high
    }

if __name__ == '__main__':
    # ... (previous examples for update_user_rir_bias and calculate_current_fatigue remain) ...

    print("\n--- Training Parameter Calculation Examples ---")
    goals = [0.0, 0.25, 0.5, 0.75, 1.0]
    for goal in goals:
        params = calculate_training_params(goal)
        print(f"Goal Fraction: {goal:.2f}")
        print(f"  Load % of 1RM: {params['load_percentage_of_1rm']:.4f}")
        print(f"  Target RIR (rounded): {params['target_rir']}")
        print(f"  Target RIR (float): {params['target_rir_float']:.2f}")
        print(f"  Rest (seconds): {params['rest_seconds']}")
        print(f"  Rep Range: {params['rep_range_low']}-{params['rep_range_high']}")
        print("-" * 20)

    # Test edge case for rep_low and rep_high logic
    print("Testing rep range logic specifically:")
    # This goal (e.g., 0.0) should give rep_high_float = 12, rep_high = 12. rep_low_candidate = 8, rep_low = 8
    params_hypertrophy = calculate_training_params(0.0)
    print(f"Goal 0.0 (Hypertrophy): Rep Range {params_hypertrophy['rep_range_low']}-{params_hypertrophy['rep_range_high']}")

    # This goal (e.g., 1.0) should give rep_high_float = 6, rep_high = 6. rep_low_candidate = 2, rep_low = 2
    params_strength = calculate_training_params(1.0)
    print(f"Goal 1.0 (Strength): Rep Range {params_strength['rep_range_low']}-{params_strength['rep_range_high']}")

    # A goal that might make rep_low > rep_high if not careful after rounding
    # e.g. if rep_high_float = 6.4 (rounds to 6) and rep_low_candidate = 2.4 (rounds to 2) - fine
    # e.g. if rep_high_float = 6.6 (rounds to 7) and rep_low_candidate = 2.7 (rounds to 3) - fine
    # e.g. if rep_high_float = 6.1 (rounds to 6) and rep_low_candidate = 2.3 (rounds to 2) - fine
    # The logic `rep_low = int(round(max(1.0, rep_high_float - 4.0)))` and `if rep_low > rep_high: rep_low = rep_high` should handle this.
    # Let's test a value like goal_strength_fraction = 0.9, where rep_high_float = 6 + 6*(0.1) = 6.6 (rounds to 7)
    # rep_low_candidate = 6.6 - 4 = 2.6 (rounds to 3). So 3-7, which is fine.
    params_intermediate = calculate_training_params(0.90) # rep_high_float = 6.6 -> 7, target_rir_float = 2.5 - 1.5*0.9 = 2.5 - 1.35 = 1.15 -> 1
    print(f"Goal 0.90: Rep Range {params_intermediate['rep_range_low']}-{params_intermediate['rep_range_high']}, RIR {params_intermediate['target_rir']}")
    # Test value from problem statement (0.0)
    # load_percentage = 0.60 + 0.35 * 0.0 = 0.60
    # target_rir_float = 2.5 - 1.5 * 0.0 = 2.5  (rounds to 3)
    # rest_minutes = 1.5 + 2.0 * 0.0 = 1.5 (90s)
    # rep_high_float = 6.0 + 6.0 * (1.0 - 0.0) = 12.0 (rounds to 12)
    # rep_low = int(round(max(1.0, 12.0 - 4.0))) = int(round(max(1.0, 8.0))) = 8.  Range: 8-12

    # Test value from problem statement (0.5)
    # load_percentage = 0.60 + 0.35 * 0.5 = 0.60 + 0.175 = 0.775
    # target_rir_float = 2.5 - 1.5 * 0.5 = 2.5 - 0.75 = 1.75 (rounds to 2)
    # rest_minutes = 1.5 + 2.0 * 0.5 = 1.5 + 1.0 = 2.5 (150s)
    # rep_high_float = 6.0 + 6.0 * (1.0 - 0.5) = 6.0 + 3.0 = 9.0 (rounds to 9)
    # rep_low = int(round(max(1.0, 9.0 - 4.0))) = int(round(max(1.0, 5.0))) = 5. Range: 5-9

    # Test value from problem statement (1.0)
    # load_percentage = 0.60 + 0.35 * 1.0 = 0.95
    # target_rir_float = 2.5 - 1.5 * 1.0 = 1.0 (rounds to 1)
    # rest_minutes = 1.5 + 2.0 * 1.0 = 3.5 (210s)
    # rep_high_float = 6.0 + 6.0 * (1.0 - 1.0) = 6.0 (rounds to 6)
    # rep_low = int(round(max(1.0, 6.0 - 4.0))) = int(round(max(1.0, 2.0))) = 2. Range: 2-6

    print("\nTesting with values from problem statement prompt:")
    print("Goal 0.0 (Pure Hypertrophy):")
    pprint(calculate_training_params(0.0))
    print("Goal 0.5 (Balanced):")
    pprint(calculate_training_params(0.5))
    print("Goal 1.0 (Pure Strength):")
    pprint(calculate_training_params(1.0))

    try:
        calculate_training_params(1.1)
    except ValueError as e:
        print(f"\nCaught expected error for out-of-bounds input: {e}")
