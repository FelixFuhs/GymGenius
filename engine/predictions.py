# Extended Epley Formula for 1RM prediction
# Formula: 1RM = w * (1 + (r / 30))
# Some sources use variations, e.g. Brzycki: w / ( 1.0278 – 0.0278 * r )
# We'll stick to the common Epley: w * (1 + r / 30)
# For r=1, 1RM = w. For r=0, it's undefined or implies w is already 1RM.
# We should handle cases where reps are very low (e.g., 1) or too high for reliable prediction.

import math # For sqrt

# Helper for manual stddev and mean if numpy not used
def _calculate_stats(values: list[float]) -> tuple[float | None, float | None]:
    n = len(values)
    if n == 0:
        return None, None

    mean_val = sum(values) / n

    if n < 2: # Stddev is not well-defined for less than 2 samples, or is 0.
        return mean_val, 0.0

    sum_sq_diff = sum((x - mean_val) ** 2 for x in values)
    std_dev = math.sqrt(sum_sq_diff / (n - 1)) # Sample standard deviation
    return mean_val, std_dev

def calculate_confidence_score(
    user_id: str,
    exercise_id: str,
    db_cursor: 'psycopg2.extensions.cursor', # Type hint for psycopg2 cursor
    min_samples: int = 3,
    max_samples: int = 10
) -> float | None:
    """
    Calculates a confidence score for the current 1RM estimate based on historical consistency.
    Fetches recent estimated_1rm values for the user/exercise.
    Confidence = 1.0 - (std_dev / mean) of these recent 1RMs.
    Returns None if not enough data or calculation is problematic.
    """
    try:
        db_cursor.execute(
            """
            SELECT estimated_1rm FROM estimated_1rm_history
            WHERE user_id = %s AND exercise_id = %s
            ORDER BY calculated_at DESC
            LIMIT %s;
            """,
            (user_id, exercise_id, max_samples)
        )
        history_records = db_cursor.fetchall()
    except Exception as e:
        # print(f"Error fetching 1RM history for confidence score: {e}") # If logger available
        return None # Cannot calculate if DB fetch fails

    if not history_records or len(history_records) < min_samples:
        return None # Not enough data points for a meaningful confidence score

    e1rm_values = [float(record['estimated_1rm']) for record in history_records]

    mean_e1rm, std_dev_e1rm = _calculate_stats(e1rm_values)

    if mean_e1rm is None: # Should not happen if len(history_records) >= min_samples > 0
        return None

    if mean_e1rm == 0: # Avoid division by zero if mean is 0
        return 0.0 # Low confidence if mean is zero (and std_dev likely also zero)

    if std_dev_e1rm is None: # Should not happen with min_samples logic
        return None

    if std_dev_e1rm == 0: # Perfect consistency
        return 1.0

    # Coefficient of variation
    cv = std_dev_e1rm / mean_e1rm

    # Confidence score: 1 - CV.
    # CV can be > 1 if std_dev > mean. Clamp confidence to be >= 0.
    confidence = max(0.0, 1.0 - cv)

    return round(confidence, 2)

DEFAULT_BARBELL_WEIGHT_KG = 20.0
DEFAULT_AVAILABLE_PLATES_KG = [25, 20, 15, 10, 5, 2.5, 1.25, 0.5, 0.25] # Common plates

def generate_possible_side_weights(available_plates_kg: list[float], max_total_weight_one_side: float) -> set[float]:
    """
    Generates all possible unique sums of plate combinations for one side of a barbell,
    up to a reasonable maximum and number of plates.
    """
    unique_plates = sorted(list(set(p for p in available_plates_kg if p > 0)))

    current_sums = {0.0}
    MAX_PLATES_PER_SIDE_PHYSICAL_LIMIT = 8

    for _i in range(MAX_PLATES_PER_SIDE_PHYSICAL_LIMIT):
        newly_formed_this_iteration = set()
        for s in current_sums:
            for p_type in unique_plates:
                new_sum = round(s + p_type, 3)
                if new_sum <= max_total_weight_one_side:
                    newly_formed_this_iteration.add(new_sum)

        if not newly_formed_this_iteration:
            break

        previous_size = len(current_sums)
        current_sums.update(newly_formed_this_iteration)

        if len(current_sums) == previous_size:
            break

        if len(current_sums) > 1500:
            # print(f"Warning: Plate combination generation exceeded 1500 sums at iteration {_i+1}.")
            break

    return current_sums

def round_to_available_plates(
    target_weight_kg: float,
    available_plates_kg: list[float] | None = None,
    barbell_weight_kg: float | None = None
) -> float:
    """
    Rounds the target_weight_kg to the closest weight achievable with the
    user's available plates and barbell.
    """
    if available_plates_kg is None or not isinstance(available_plates_kg, list) or not available_plates_kg:
        processed_available_plates = DEFAULT_AVAILABLE_PLATES_KG
    else:
        processed_available_plates = [p for p in available_plates_kg if isinstance(p, (int, float)) and p > 0]
        if not processed_available_plates:
            processed_available_plates = DEFAULT_AVAILABLE_PLATES_KG

    if barbell_weight_kg is None or not isinstance(barbell_weight_kg, (int,float)) or barbell_weight_kg < 0:
        current_barbell_weight_kg = DEFAULT_BARBELL_WEIGHT_KG
    else:
        current_barbell_weight_kg = barbell_weight_kg
    current_barbell_weight_kg = round(current_barbell_weight_kg, 3)


    if target_weight_kg <= current_barbell_weight_kg:
        return current_barbell_weight_kg

    max_one_side_for_calc = (target_weight_kg * 1.2 + 20 - current_barbell_weight_kg) / 2.0
    max_one_side_for_calc = max(0, max_one_side_for_calc)

    possible_one_side_weights = generate_possible_side_weights(processed_available_plates, max_one_side_for_calc)

    achievable_total_weights = sorted(list(set(round(current_barbell_weight_kg + 2 * s_w, 3) for s_w in possible_one_side_weights)))

    if not achievable_total_weights:
        if 0.0 in possible_one_side_weights and current_barbell_weight_kg not in achievable_total_weights:
                achievable_total_weights.append(current_barbell_weight_kg)
                achievable_total_weights.sort()
        elif not achievable_total_weights:
            return round(target_weight_kg * 2) / 2.0

    if not achievable_total_weights:
        return round(target_weight_kg * 2) / 2.0


    closest_weight = achievable_total_weights[0]
    min_diff = abs(target_weight_kg - closest_weight)

    for achievable_w in achievable_total_weights:
        diff = abs(target_weight_kg - achievable_w)
        if diff < min_diff:
            min_diff = diff
            closest_weight = achievable_w
        elif diff == min_diff:
            closest_weight = max(closest_weight, achievable_w)

    return closest_weight

def extended_epley_1rm(weight: float, reps: int) -> float:
    """
    Calculates estimated 1 Rep Max (1RM) using the Extended Epley formula.
    Assumes weight is positive and reps are 1 or more.
    Returns 0 if reps are less than 1, as the formula is not intended for it.
    """
    if reps < 1:
        return 0.0 # Or raise ValueError, depending on desired handling
    if reps == 1:
        return weight

    # Standard Epley formula
    estimated_1rm = weight * (1 + (reps / 30.0))
    return round(estimated_1rm, 2)


def estimate_1rm_with_rir_bias(weight: float, reps: int, rir: int, user_rir_bias: float) -> float:
    """
    Calculates estimated 1 Rep Max (1RM) using the Epley formula, adjusted for RIR bias.
    Formula: 1RM = weight / (1 - 0.0333 * total_reps_adjusted_for_rir)
    (Note: The issue uses 1 - 0.0333 * X, which is equivalent to 1 / (1/ (1+reps/30)) which is weight * (1+reps/30)
    The common Epley is weight * (1 + reps/30). The provided formula in the issue is:
    estimated_1rm = weight / (1 - 0.0333 * (reps + adjusted_rir))
    This is equivalent to weight * (1 / ( (30 - (reps + adjusted_rir)) / 30) )
    = weight * (30 / (30 - (reps + adjusted_rir)))
    Let's stick to the formula precisely as given in the issue for this function.
    """
    if reps < 0: # Reps should be non-negative
        # Or handle as an error, but for now, returning 0 or input weight might be safest
        return weight # Or 0.0, needs clarification for invalid reps with RIR
    if rir < 0: # RIR should be non-negative
        rir = 0

    adjusted_rir = max(0, rir - user_rir_bias)

    # Total effective reps considering RIR and bias
    # This is reps performed + reps left in tank (adjusted by bias)
    total_reps_for_estimation = reps + adjusted_rir

    if total_reps_for_estimation <= 0: # Avoid division by zero or negative in formula if total_reps makes 0.0333 * total_reps >= 1
        # This implies the set was taken to failure or beyond with adjusted RIR,
        # or bias is very high.
        # If total_reps_for_estimation is 0, and reps is e.g. 5, it means rir - user_rir_bias was -5.
        # A single rep max is usually when reps = 1, rir = 0.
        # If total_reps_for_estimation makes the denominator <=0, it implies extremely high predicted 1RM or invalid state.
        # The Epley (1+r/30) implicitly means r should be what you *could do*.
        # The formula weight / (1 - 0.0333 * X) means X is "reps to failure".
        # So, 'reps + adjusted_rir' *is* the estimated reps to failure.
        return weight # Fallback if calculation is not possible or implies superhuman strength

    # Denominator: (1 - 0.0333 * total_reps_for_estimation)
    denominator = 1 - (0.0333 * total_reps_for_estimation)

    if denominator <= 0:
        # This implies that total_reps_for_estimation >= 30, which is the limit for this Epley variant.
        # (since 1 - 0.0333 * 30 = 1 - 0.999 = ~0).
        # If estimated reps to failure are >=30, 1RM estimation is unreliable with this formula.
        # Consider returning a very high value or current weight, or using an alternative.
        # For now, cap at a high multiplier or return based on an alternative for high reps
        # For simplicity, if total_reps_for_estimation is very high, it means 1RM is not much higher than weight.
        # However, the formula given will break.
        # If reps + adjusted_rir = 30, 1RM is infinite. If > 30, 1RM is negative.
        # This indicates the formula is only valid for (reps + adjusted_rir) < 30.
        # Let's cap total_reps_for_estimation at 29 for practical purposes with this formula.
        if total_reps_for_estimation >= 30:
            # This condition implies the set was very far from a 1RM effort if weight was light.
            # Or, the formula breaks down.
            # Fallback: use standard Epley on 'reps' only if 'adjusted_rir' causes issues.
            # For now, we'll cap to avoid negative/zero denominator.
            total_reps_for_estimation = 29
            denominator = 1 - (0.0333 * total_reps_for_estimation)


    estimated_1rm = weight / denominator
    return round(estimated_1rm, 2)

# Example Test (not part of the app, just for quick verification)
if __name__ == '__main__':
    print(f"100kg for 10 reps: {extended_epley_1rm(100, 10):.2f}kg 1RM") # Expected: 133.33
    print(f"100kg for 1 rep: {extended_epley_1rm(100, 1):.2f}kg 1RM")   # Expected: 100.00
    print(f"50kg for 5 reps: {extended_epley_1rm(50, 5):.2f}kg 1RM")    # Expected: 58.33
    print(f"200kg for 0 reps: {extended_epley_1rm(200, 0):.2f}kg 1RM")  # Expected: 0.0
