# Extended Epley Formula for 1RM prediction
# Formula: 1RM = w * (1 + (r / 30))
# Some sources use variations, e.g. Brzycki: w / ( 1.0278 – 0.0278 * r )
# We'll stick to the common Epley: w * (1 + r / 30)
# For r=1, 1RM = w. For r=0, it's undefined or implies w is already 1RM.
# We should handle cases where reps are very low (e.g., 1) or too high for reliable prediction.

import math # For sqrt

DEFAULT_ASSUMED_RIR = 2

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
    # Increased limit to allow for more plates, e.g. many small 1.25kg plates
    MAX_PLATES_PER_SIDE_PHYSICAL_LIMIT = 15

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

# Increased limit to allow for more increments for machines/dumbbells to reach higher totals.
DEFAULT_DUMBBELL_MACHINE_PLATES_LIMIT = 20

def generate_possible_single_weights(
    available_plates_kg: list[float],
    max_weight_target: float,
    max_plates_limit: int = DEFAULT_DUMBBELL_MACHINE_PLATES_LIMIT
) -> set[float]:
    """
    Generates all possible unique sums of plate combinations for a single item
    (e.g., one dumbbell, or machine stack increments).
    Assumes available_plates_kg are the actual increments or small plates.
    """
    unique_plates = sorted(list(set(p for p in available_plates_kg if p > 0)))
    if not unique_plates:
        return {0.0}

    current_sums = {0.0} # Start with 0 (e.g. empty handle or base machine weight if applicable, handled outside)

    for _i in range(max_plates_limit): # Limit the number of plates to prevent excessive combinations
        newly_formed_this_iteration = set()
        for s in current_sums:
            for p_type in unique_plates:
                # Max target for sums is a bit higher than target_weight to find closest match
                new_sum = round(s + p_type, 3)
                if new_sum <= max_weight_target * 1.5: # Allow sums to go a bit over target for finding closest
                    newly_formed_this_iteration.add(new_sum)

        if not newly_formed_this_iteration: # No new sums could be formed
            break

        previous_size = len(current_sums)
        current_sums.update(newly_formed_this_iteration)
        if len(current_sums) == previous_size: # No new sums added in this iteration
            break

        # Safety break for too many combinations, though less likely with fewer plates
        if len(current_sums) > 1000: # Reduced from barbell's 1500, as items are simpler
            break

    return current_sums

def round_to_available_plates(
    target_weight_kg: float,
    available_plates_kg: list[float] | None = None,
    barbell_weight_kg: float | None = None,
    equipment_type: str | None = 'barbell' # New parameter
) -> float:
    """
    Rounds the target_weight_kg to the closest weight achievable based on equipment type.
    For 'dumbbell_pair', target_weight_kg is for a single dumbbell.
    For 'machine', target_weight_kg is for the machine stack.
    """
    equipment_type_processed = (equipment_type or 'barbell').lower()

    # Validate and process available_plates_kg first
    if available_plates_kg is None or not isinstance(available_plates_kg, list) or not available_plates_kg:
        # For barbell, use default. For others, this might mean fallback to rounding.
        if equipment_type_processed == 'barbell':
            processed_available_plates = DEFAULT_AVAILABLE_PLATES_KG
        else:
            processed_available_plates = [] # Empty list signifies fallback for dumbbell/machine
    else:
        processed_available_plates = [p for p in available_plates_kg if isinstance(p, (int, float)) and p > 0]
        if not processed_available_plates and equipment_type_processed == 'barbell':
            processed_available_plates = DEFAULT_AVAILABLE_PLATES_KG
        # If still no processed_available_plates for dumbbell/machine, they'll use fallback.

    # --- Dumbbell Pair Logic ---
    if equipment_type_processed == 'dumbbell_pair':
        if not processed_available_plates:
            return round(target_weight_kg) # Fallback to integer steps for single dumbbell

        # Dumbbell target_weight_kg is for one dumbbell.
        # We assume the provided plates are for loading one dumbbell.
        # Dumbbell handles themselves might have a base weight, but we assume target_weight_kg is total for one.
        # Or, if plates are [0.5, 1, 1.25, 2.5], these are added to a base handle (e.g. 2kg)
        # For simplicity here, generated sums are total dumbbell weights.
        # If a base handle weight is needed, it should be the first element of `available_plates_kg`
        # or `generate_possible_single_weights` should take a `base_weight` param.
        # Current `generate_possible_single_weights` starts sums from 0.0.

        # Use a slightly higher target for generation to ensure we find closest around target_weight_kg
        possible_dumbbell_weights = generate_possible_single_weights(processed_available_plates, target_weight_kg)

        if not possible_dumbbell_weights: # Should at least have {0.0}
             return round(target_weight_kg)

        closest_weight = -1.0
        min_diff = float('inf')

        # Find closest in possible_dumbbell_weights (which are total weights for one dumbbell)
        for achievable_w in sorted(list(possible_dumbbell_weights)):
            diff = abs(target_weight_kg - achievable_w)
            if diff < min_diff:
                min_diff = diff
                closest_weight = achievable_w
            elif diff == min_diff: # Prefer heavier if equidistant
                closest_weight = max(closest_weight, achievable_w)

        return closest_weight if closest_weight != -1.0 else round(target_weight_kg)

    # --- Machine Logic ---
    elif equipment_type_processed == 'machine':
        if not processed_available_plates: # No specific machine increments provided
            return round(target_weight_kg) # Fallback to integer steps

        # target_weight_kg is the total for the machine stack.
        # available_plates_kg are the machine's increments (e.g., [2.5, 5, 10]).
        # Similar to dumbbell, generate sums from these increments.
        possible_machine_weights = generate_possible_single_weights(processed_available_plates, target_weight_kg)

        if not possible_machine_weights:
            return round(target_weight_kg)

        closest_weight = -1.0
        min_diff = float('inf')

        for achievable_w in sorted(list(possible_machine_weights)):
            diff = abs(target_weight_kg - achievable_w)
            if diff < min_diff:
                min_diff = diff
                closest_weight = achievable_w
            elif diff == min_diff:
                closest_weight = max(closest_weight, achievable_w)

        return closest_weight if closest_weight != -1.0 else round(target_weight_kg)

    # --- Barbell Logic (Default) ---
    else: # 'barbell' or any other type
        if barbell_weight_kg is None or not isinstance(barbell_weight_kg, (int,float)) or barbell_weight_kg < 0:
            current_barbell_weight_kg = DEFAULT_BARBELL_WEIGHT_KG
        else:
            current_barbell_weight_kg = barbell_weight_kg
        current_barbell_weight_kg = round(current_barbell_weight_kg, 3)

        if target_weight_kg <= current_barbell_weight_kg:
            return current_barbell_weight_kg

        # Max weight for one side calculation for barbell
        max_one_side_for_calc = (target_weight_kg * 1.2 + 20 - current_barbell_weight_kg) / 2.0
        max_one_side_for_calc = max(0, max_one_side_for_calc)

        possible_one_side_weights = generate_possible_side_weights(processed_available_plates, max_one_side_for_calc)

        # Calculate achievable total weights for barbell
        achievable_total_weights = sorted(list(set(round(current_barbell_weight_kg + 2 * s_w, 3) for s_w in possible_one_side_weights)))

        if not achievable_total_weights:
            # This case implies possible_one_side_weights was empty or only {0.0} and target > barbell
            # If possible_one_side_weights is just {0.0}, then achievable_total_weights = [barbell_weight]
            # This path should ideally not be hit if target_weight_kg > current_barbell_weight_kg
            # and generate_possible_side_weights works.
             if 0.0 in possible_one_side_weights and current_barbell_weight_kg not in achievable_total_weights: # Should not happen
                achievable_total_weights.append(current_barbell_weight_kg)
                achievable_total_weights.sort()
             else: # Fallback if generation somehow fails to produce meaningful weights
                return round(target_weight_kg * 2) / 2.0 # Generic rounding like before

        if not achievable_total_weights: # Should be populated now or returned above
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
    if rir is None:
        adjusted_rir = DEFAULT_ASSUMED_RIR # Bias is ignored as per requirement
    elif rir < 0: # RIR should be non-negative if provided
        adjusted_rir = 0 # Or perhaps user_rir_bias should still apply? Req says bias-free for None.
                         # For negative RIR, it's like 0 RIR. So max(0, 0 - user_rir_bias)
                         # If bias is positive, this makes adjusted_rir 0. If bias is negative (helping), then positive.
                         # Let's assume non-negative RIR inputs if not None.
                         # For now, if rir is explicitly < 0, it implies failure.
        adjusted_rir = max(0, 0 - user_rir_bias) # Treat as 0 RIR and apply bias.
    else:
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

    # If total_reps_for_estimation is at or above the formula's practical limit (30),
    # cap it at 29 to prevent division by zero/small number or negative results.
    if total_reps_for_estimation >= 30:
        total_reps_for_estimation = 29

    denominator = 1 - (0.0333 * total_reps_for_estimation)

    # After capping, denominator should generally be positive.
    # total_reps_for_estimation = 29 -> denominator = 1 - 0.0333*29 = 0.0343
    # total_reps_for_estimation = 0 -> denominator = 1
    # This check is a safeguard for any other unexpected scenario leading to non-positive denominator.
    if denominator <= 0:
        return weight # Fallback if calculation is not possible

    estimated_1rm = weight / denominator
    return round(estimated_1rm, 2)

# Example Test (not part of the app, just for quick verification)
if __name__ == '__main__':
    print(f"100kg for 10 reps: {extended_epley_1rm(100, 10):.2f}kg 1RM") # Expected: 133.33
    print(f"100kg for 1 rep: {extended_epley_1rm(100, 1):.2f}kg 1RM")   # Expected: 100.00
    print(f"50kg for 5 reps: {extended_epley_1rm(50, 5):.2f}kg 1RM")    # Expected: 58.33
    print(f"200kg for 0 reps: {extended_epley_1rm(200, 0):.2f}kg 1RM")  # Expected: 0.0


def calculate_mti(weight: float, reps: int, rir: int) -> tuple[int, int]:
    """
    Calculates effective reps and the Mechanical-Tension Index (MTI).
    Returns a tuple: (effective_reps, mti_value).
    """
    if weight is None or reps is None or rir is None: # Handle potential None inputs
        return 0, 0

    # Effective reps are reps performed minus reps that were "too far" from failure.
    # Reps further than RIR 4 from failure are not counted as effective.
    # max(0, rir - 4) determines how many reps were "beyond" RIR 4.
    # For example:
    # RIR 0-4: max(0, rir-4) = 0. Effective reps = reps - 0 = reps.
    # RIR 5: max(0, 5-4) = 1. Effective reps = reps - 1.
    # RIR 8: max(0, 8-4) = 4. Effective reps = reps - 4.
    effective_reps = max(0, reps - max(0, rir - 4))

    mti_value = round(weight * effective_reps) # Round MTI to nearest integer

    return effective_reps, int(mti_value) # Ensure mti_value is int


# --- Main Recommendation Function (incorporating readiness) ---
# This is a simplified placeholder. A full implementation would involve more factors.
from readiness import calculate_readiness_multiplier # Import from readiness.py
# Assuming app context for logger and db helpers might be tricky if this file is purely computational.
# For now, let's assume db_conn is passed in, or this function is called from a route that handles DB.
# from ..app import get_db_connection, release_db_connection, logger # Would need careful handling of app context

def recommend_next_set_parameters(
    user_id: str,
    exercise_id: str,
    db_conn, # Expect an active database connection
    user_current_e1rm: float, # User's current estimated 1RM for this exercise
    user_goal_strength_fraction: float, # User's goal (0.0 hyper, 1.0 strength)
    user_rir_bias: float, # User's current RIR bias
    exercise_equipment_type: str | None = 'barbell', # From exercises table
    user_available_plates_kg: list[float] | None = None, # From users table
    user_barbell_weight_kg: float | None = None # From users table
    ):
    """
    Recommends parameters for the next set, applying readiness multiplier.
    This is a simplified version for integration.
    """
    from app import logger # Local import to avoid circular dependencies at module level if app imports predictions

    # 1. Determine target parameters based on goal (from learning_models.calculate_training_params)
    # This function is in learning_models.py, so it needs to be imported or its logic replicated/called.
    # For now, let's assume we get some base targets from it.
    # from .learning_models import calculate_training_params # This creates a circular import if learning_models imports predictions
    # Simplified:
    # target_load_percentage = 0.75 # Example: 75% of 1RM
    # target_reps_for_calc = 8      # Example: Target 8 reps
    # target_rir_for_calc = 2       # Example: Target RIR 2

    # Using a simplified version of calculate_training_params logic here
    # to avoid direct import issues for now.
    # In a refactor, this might be structured differently.
    if not 0.0 <= user_goal_strength_fraction <= 1.0:
        user_goal_strength_fraction = 0.5 # Default to balanced if invalid

    target_load_percentage = 0.60 + 0.35 * user_goal_strength_fraction
    # target_rir_float = 2.5 - 1.5 * user_goal_strength_fraction
    # For recommending weight, we often work towards a target rep and RIR.
    # Let's assume a common target of 8-12 reps for hypertrophy, 3-6 for strength.
    # And RIR 1-3.
    # The `calculate_training_params` in learning_models gives these.
    # For this example, let's fix target_reps and target_rir for simplicity of demonstration.
    target_reps_for_recommendation = 8
    target_rir_for_recommendation = 2


    # 2. Calculate initial recommended weight based on e1RM, target reps, and target RIR
    # This is effectively reversing the e1RM formula: Weight = e1RM * ( (30 - (Reps + RIR_adj)) / 30 )
    # Or more directly: Weight = e1RM / (1 + ( (Reps + RIR_adj) / 30) )
    # Using the formula from estimate_1rm_with_rir_bias: estimated_1rm = weight / (1 - 0.0333 * total_reps_adjusted_for_rir)
    # So, weight = estimated_1rm * (1 - 0.0333 * total_reps_adjusted_for_rir)

    # Adjust target_rir by user's bias for calculation:
    # If user underestimates RIR (positive bias), they are stronger, so for a *true* RIR 2, they might report RIR 0.
    # Or, if they report RIR 2, their true RIR is 2 + bias.
    # When recommending, we want them to *achieve* a true RIR.
    # So, if we want them to hit true RIR 2, and their bias is +1 (they underestimate by 1),
    # we should tell them to aim for RIR 1 (because 1 - (+1) = 0 in their perception for e1RM calc, but that's for *input*.
    # For *output* recommendation: target effective RIR for calculation = target_reported_RIR - user_rir_bias
    # This is the RIR value the Epley formula expects if it were raw.
    effective_rir_for_calc = max(0, target_rir_for_recommendation - user_rir_bias)

    total_reps_for_e1rm_formula = target_reps_for_recommendation + effective_rir_for_calc
    if total_reps_for_e1rm_formula >= 30: total_reps_for_e1rm_formula = 29 # Cap for formula stability

    denominator_for_weight_calc = 1 - (0.0333 * total_reps_for_e1rm_formula)

    if user_current_e1rm <= 0 or denominator_for_weight_calc <= 0:
        recommended_weight_before_readiness = 40.0 # Default fallback or error
        logger.warning(f"User {user_id}, Ex {exercise_id}: Invalid e1RM ({user_current_e1rm}) or calc error for initial weight. Defaulting.")
    else:
        recommended_weight_before_readiness = user_current_e1rm * denominator_for_weight_calc

    logger.info(f"User {user_id}, Ex {exercise_id}: Initial recommended weight {recommended_weight_before_readiness:.2f}kg (e1RM: {user_current_e1rm}kg, GoalFrac: {user_goal_strength_fraction}, Bias: {user_rir_bias})")


    # 3. Fetch latest workout's readiness data
    readiness_multiplier_val = 1.0
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT sleep_hours, stress_level, hrv_ms
                FROM workouts
                WHERE user_id = %s AND completed_at IS NOT NULL
                ORDER BY completed_at DESC LIMIT 1;
                """,
                (user_id,)
            )
            latest_workout_data = cur.fetchone()

        if latest_workout_data and \
           latest_workout_data['sleep_hours'] is not None and \
           latest_workout_data['stress_level'] is not None:

            # hrv_ms can be None, calculate_readiness_multiplier handles it
            readiness_multiplier_val = calculate_readiness_multiplier(
                sleep_h=float(latest_workout_data['sleep_hours']),
                stress_lvl=int(latest_workout_data['stress_level']), # Assuming stress stored as int/float convertible
                hrv_ms=float(latest_workout_data['hrv_ms']) if latest_workout_data['hrv_ms'] is not None else None,
                user_id=user_id, # Pass as UUID if type hinting expects it, else str
                db_conn=db_conn
            )
            logger.info(f"User {user_id}, Ex {exercise_id}: Readiness multiplier {readiness_multiplier_val:.4f} applied.")
        else:
            logger.info(f"User {user_id}, Ex {exercise_id}: No recent-enough readiness data found or sleep/stress missing, multiplier is 1.0.")
            # readiness_multiplier_val remains 1.0

    except Exception as e:
        logger.error(f"User {user_id}, Ex {exercise_id}: Error fetching readiness data or calculating multiplier: {e}", exc_info=True)
        readiness_multiplier_val = 1.0 # Default to neutral on error

    # 4. Apply readiness multiplier
    final_recommended_weight = recommended_weight_before_readiness * readiness_multiplier_val

    # 5. Round to available plates (using the existing function)
    # Ensure user_available_plates_kg and user_barbell_weight_kg are correctly passed if needed for barbell
    rounded_weight = round_to_available_plates(
        target_weight_kg=final_recommended_weight,
        available_plates_kg=user_available_plates_kg,
        barbell_weight_kg=user_barbell_weight_kg,
        equipment_type=exercise_equipment_type
    )
    logger.info(f"User {user_id}, Ex {exercise_id}: Final recommended weight {rounded_weight:.2f}kg (pre-round: {final_recommended_weight:.2f}kg)")

    return {
        "recommended_weight_kg": rounded_weight,
        "target_reps_low": target_reps_for_recommendation -1, # Example rep range
        "target_reps_high": target_reps_for_recommendation +1,
        "target_rir": target_rir_for_recommendation,
        "explanation": f"Based on e1RM {user_current_e1rm:.1f}kg, goal ({user_goal_strength_fraction}), and readiness ({readiness_multiplier_val:.3f}). Initial: {recommended_weight_before_readiness:.1f}kg."
        # Add confidence score later if needed
    }

# Placeholder for a more sophisticated fatigue model if needed
# def apply_fatigue_adjustment(recommended_weight, fatigue_metrics):
#     # ...
#     return adjusted_weight
