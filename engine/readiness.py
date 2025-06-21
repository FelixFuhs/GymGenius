import uuid
from datetime import datetime, timezone, timedelta # Ensure all are imported
import psycopg2
import psycopg2.extras # For RealDictCursor if needed, though AVG might not require it.
from app import get_db_connection, release_db_connection, logger

# Constants for readiness calculation (can be tuned)
SLEEP_TARGET_HOURS = 8.0
STRESS_MAX_LEVEL = 10.0
# Weights for score components
SLEEP_WEIGHT = 0.4
STRESS_WEIGHT = 0.3
HRV_WEIGHT = 0.3

# Multiplier mapping parameters
MULTIPLIER_BASE = 0.93
MULTIPLIER_RANGE = 0.14 # total_score of 1.0 results in 0.93 + 0.14 = 1.07

# The functions will be added here in subsequent steps.

def get_personal_hrv_baseline(user_id: uuid.UUID, db_conn) -> float | None:
    """
    Calculates the average hrv_ms from the workouts table for the given user_id
    over the last 30 days (where hrv_ms is not NULL).

    Args:
        user_id: The UUID of the user.
        db_conn: Active database connection.

    Returns:
        The average HRV in ms as a float, or None if no data is available.
    """
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            sql_query = """
                SELECT AVG(hrv_ms) as avg_hrv
                FROM workouts
                WHERE user_id = %s
                  AND hrv_ms IS NOT NULL
                  AND completed_at >= NOW() - INTERVAL '30 days';
            """
            cur.execute(sql_query, (str(user_id),)) # Ensure user_id is string for query
            result = cur.fetchone()

            if result and result['avg_hrv'] is not None:
                return float(result['avg_hrv'])
            else:
                logger.info(f"No recent HRV data found for user {user_id} to calculate baseline.")
                return None
    except psycopg2.Error as e:
        logger.error(f"Database error calculating HRV baseline for user {user_id}: {e}", exc_info=True)
        # Depending on desired behavior, could re-raise or return None
        return None
    except Exception as e:
        logger.error(f"Unexpected error calculating HRV baseline for user {user_id}: {e}", exc_info=True)
        return None

def calculate_readiness_multiplier(
    sleep_h: float | None,
    stress_lvl: int | None, # Assuming stress_lvl is 1-10
    hrv_ms: float | None,
    user_id: uuid.UUID,
    db_conn
) -> tuple[float, float]:
    """
    Calculates a readiness multiplier and the underlying total score
    based on sleep, stress, and HRV relative to baseline.

    Args:
        sleep_h: Hours of sleep last night.
        stress_lvl: Subjective stress level (1-10, where 1 is low stress).
        hrv_ms: Current HRV reading in milliseconds.
        user_id: The UUID of the user.
        db_conn: Active database connection (for fetching HRV baseline).

    Returns:
        A tuple containing:
            - readiness_multiplier (float): Typically ranging from ~0.93 to ~1.07.
            - total_score (float): The combined score (0-1) from which the multiplier is derived.
    """
    sleep_score_contribution = 0.0
    stress_score_contribution = 0.0
    hrv_score_contribution = 0.0

    # Sleep contribution
    if sleep_h is not None:
        # Normalize sleep score: 1.0 if sleep_h >= target, scales down otherwise.
        # Cap at 1.0 (e.g. 10 hours sleep is not necessarily better than 8 for this score component)
        normalized_sleep = min(1.0, sleep_h / SLEEP_TARGET_HOURS)
        sleep_score_contribution = normalized_sleep * SLEEP_WEIGHT
    else: # If sleep_h is None, it contributes 0 to the score, effectively lowering readiness.
        logger.info(f"Readiness: Sleep data not provided for user {user_id}. Sleep contribution will be 0.")


    # Stress contribution
    if stress_lvl is not None:
        # Normalize stress score: 1.0 for stress_lvl 1, 0.0 for stress_lvl 10.
        normalized_stress = (STRESS_MAX_LEVEL - float(stress_lvl)) / (STRESS_MAX_LEVEL - 1.0) # (10-lvl)/(10-1) = (10-lvl)/9
        stress_score_contribution = normalized_stress * STRESS_WEIGHT
    else: # If stress_lvl is None, it contributes 0.
        logger.info(f"Readiness: Stress data not provided for user {user_id}. Stress contribution will be 0.")


    # HRV contribution
    if hrv_ms is not None:
        personal_avg_hrv = get_personal_hrv_baseline(user_id, db_conn)
        if personal_avg_hrv is not None and personal_avg_hrv > 0:
            # Normalize HRV score: 1.0 if current HRV >= baseline, scales down otherwise.
            # Cap at 1.0 (e.g. significantly higher HRV than baseline is still just "good")
            normalized_hrv = min(1.0, hrv_ms / personal_avg_hrv)
            hrv_score_contribution = normalized_hrv * HRV_WEIGHT
        else:
            # No baseline or baseline is zero, HRV reading cannot be meaningfully compared.
            # Contribution remains 0.
            logger.info(f"Readiness: HRV baseline not available or zero for user {user_id}. HRV contribution will be 0.")
    else: # If hrv_ms is None, it contributes 0.
        logger.info(f"Readiness: HRV data not provided for user {user_id}. HRV contribution will be 0.")

    # Total Score (ranges from 0 to 1, as weights sum to 1)
    total_score = sleep_score_contribution + stress_score_contribution + hrv_score_contribution
    # Ensure total_score is within 0-1 range, though it should be by construction if inputs are valid.
    total_score = max(0.0, min(total_score, 1.0))

    # Map Score to Multiplier
    readiness_multiplier = MULTIPLIER_BASE + (MULTIPLIER_RANGE * total_score)

    logger.info(
        f"Readiness for user {user_id}: Sleep={sleep_h}h, Stress={stress_lvl}, HRV={hrv_ms}ms. "
        f"Contributions: Sleep={sleep_score_contribution:.3f}, Stress={stress_score_contribution:.3f}, HRV={hrv_score_contribution:.3f}. "
        f"Total Score={total_score:.3f}. Multiplier={readiness_multiplier:.4f}."
    )

    return round(readiness_multiplier, 4), round(total_score, 4)
