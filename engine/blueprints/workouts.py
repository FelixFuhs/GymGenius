from flask import Blueprint, request, jsonify, g, abort
from ..app import get_db_connection, release_db_connection, jwt_required, logger # Assuming limiter is also in app if needed by new endpoint
import psycopg2
import psycopg2.extras
import uuid
import math
from datetime import datetime, timezone, date, timedelta # Added timedelta
from engine.predictions import calculate_mti, estimate_1rm_with_rir_bias, round_to_available_plates
# Removed: calculate_confidence_score, generate_possible_side_weights, generate_possible_single_weights, extended_epley_1rm as they are not directly used by this new endpoint, but round_to_available_plates is.
# estimate_1rm_with_rir_bias is used by get_previous_performance, so keep.
from engine.learning_models import update_user_rir_bias, calculate_training_params, calculate_current_fatigue
from engine.readiness import calculate_readiness_multiplier

workouts_bp = Blueprint('workouts', __name__)


# Constants for Fatigue Adjustment
MAX_REASONABLE_FATIGUE_SCORE = 500.0  # Example value, needs tuning
MAX_FATIGUE_REDUCTION_PERCENT = 0.20  # Max 20% reduction due to fatigue


# --- API Endpoint for Set Parameter Recommendation ---
# Path changed to /v1/ per common prefix, not /api/v1
@workouts_bp.route('/v1/users/<uuid:user_id>/exercises/<uuid:exercise_id>/recommend-set-parameters', methods=['GET'])
@jwt_required
# Add limiter if desired: @limiter.limit("...")
def recommend_set_parameters_for_exercise(user_id, exercise_id):
    # Authorization
    if str(user_id) != g.current_user_id:
        logger.warning(f"Forbidden attempt to get recommendations for user {user_id} by user {g.current_user_id}")
        return jsonify(error="Forbidden. You can only get recommendations for your own profile."), 403

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Fetch User Data
            cur.execute(
                """
                SELECT goal_slider, rir_bias, available_plates,
                       COALESCE((available_plates->>'barbell_weight_kg')::numeric, 20.0) as barbell_weight_kg
                FROM users WHERE id = %s;
                """, (str(user_id),)
            )
            user_data = cur.fetchone()
            if not user_data:
                return jsonify(error="User not found."), 404

            goal_strength_fraction = float(user_data['goal_slider'])
            user_rir_bias = float(user_data['rir_bias'])
            user_available_plates_data = user_data.get('available_plates')
            user_available_plates_kg = user_available_plates_data.get('plates_kg') if isinstance(user_available_plates_data, dict) else []
            user_barbell_weight_kg = float(user_data.get('barbell_weight_kg', 20.0))

            # 2. Fetch Exercise Data
            cur.execute(
                "SELECT id, name, equipment_type, main_target_muscle_group FROM exercises WHERE id = %s;",
                (str(exercise_id),)
            )
            exercise_data = cur.fetchone()
            if not exercise_data:
                return jsonify(error="Exercise not found."), 404
            exercise_equipment_type = exercise_data['equipment_type']
            main_target_muscle_group = exercise_data['main_target_muscle_group']

            # 3. Fetch Current Estimated 1RM
            cur.execute(
                "SELECT estimated_1rm FROM estimated_1rm_history WHERE user_id = %s AND exercise_id = %s ORDER BY calculated_at DESC LIMIT 1;",
                (str(user_id), str(exercise_id))
            )
            e1rm_record = cur.fetchone()
            current_e1rm = float(e1rm_record['estimated_1rm']) if e1rm_record and e1rm_record['estimated_1rm'] is not None else 0.0

            if current_e1rm <= 0.0:
                logger.info(f"No valid 1RM history for user {user_id}, exercise {exercise_id}. Cannot generate 1RM-based recommendation.")
                return jsonify({
                    "message": "No performance history found for this exercise. Please log a set to establish a baseline.",
                    "recommended_weight_kg": None, "target_reps_low": 8, "target_reps_high": 12, "target_rir": 3,
                    "explanation": "Cannot calculate recommendation without prior performance data."
                }), 200

            # 4. Calculate Base Training Parameters
            base_params = calculate_training_params(goal_strength_fraction)
            target_reps = round((base_params['rep_range_low'] + base_params['rep_range_high']) / 2)

            # 5. Calculate Effective Target RIR for weight calculation
            effective_rir_for_calc = base_params['target_rir_float'] - user_rir_bias
            effective_rir_for_calc = max(0, min(effective_rir_for_calc, 5))

            # 6. Calculate Recommended Weight (before fatigue/readiness)
            total_reps_for_e1rm_formula = target_reps + effective_rir_for_calc
            if total_reps_for_e1rm_formula >= 30: total_reps_for_e1rm_formula = 29

            denominator_for_weight_calc = 1 - (0.0333 * total_reps_for_e1rm_formula)
            if denominator_for_weight_calc <= 0:
                recommended_weight_pre_adjustments = current_e1rm * 0.5
                logger.warning(f"Denominator issue for weight calc User {user_id}, Ex {exercise_id}. Defaulting to 50% 1RM.")
            else:
                recommended_weight_pre_adjustments = current_e1rm * denominator_for_weight_calc

            explanation_parts = [f"Base on e1RM {current_e1rm:.1f}kg for {target_reps}reps@{base_params['target_rir']:.0f}RIR (adj. for bias {user_rir_bias:.1f} to eff_RIR {effective_rir_for_calc:.1f})."]

            # 7. Apply Fatigue Adjustment (Simplified)
            fatigue_multiplier = 1.0
            # Placeholder for actual fatigue calculation logic
            # current_fatigue_value = calculate_current_fatigue(main_target_muscle_group, session_history_for_fatigue, ...)
            # For MVP, assume fatigue_multiplier = 1.0 or a very simple model if possible.
            current_fatigue_value = 0.0
            if main_target_muscle_group: # Only calculate fatigue if a main muscle group is defined
                # Fetch session history for fatigue calculation
                cur.execute(
                    """
                    SELECT
                        w.completed_at as session_date,
                        SUM(ws.mti) as stimulus
                    FROM workout_sets ws
                    JOIN workouts w ON ws.workout_id = w.id
                    JOIN exercises e ON ws.exercise_id = e.id
                    WHERE w.user_id = %s
                      AND e.main_target_muscle_group = %s
                      AND w.completed_at IS NOT NULL
                      AND w.completed_at >= (NOW() AT TIME ZONE 'UTC') - INTERVAL '21 days'
                    GROUP BY w.id, w.completed_at
                    ORDER BY w.completed_at ASC;
                    """,
                    (str(user_id), main_target_muscle_group)
                )
                session_history_for_fatigue_raw = cur.fetchall()

                session_history_for_fatigue = [
                    {'session_date': row['session_date'], 'stimulus': float(row['stimulus'])}
                    for row in session_history_for_fatigue_raw if row['stimulus'] is not None
                ]

                if session_history_for_fatigue:
                    current_fatigue_value = calculate_current_fatigue(
                        main_target_muscle_group,
                        session_history_for_fatigue
                        # Potentially pass user_recovery_multiplier if stored on user
                    )
                    logger.info(f"User {user_id}, Ex {exercise_id}, Muscle Group {main_target_muscle_group}: Calculated fatigue score {current_fatigue_value:.2f}")
                else:
                    logger.info(f"User {user_id}, Ex {exercise_id}, Muscle Group {main_target_muscle_group}: No recent session history found for fatigue calculation.")

            # Apply fatigue effect
            fatigue_effect = min(current_fatigue_value / MAX_REASONABLE_FATIGUE_SCORE, 1.0)
            fatigue_multiplier = 1.0 - (fatigue_effect * MAX_FATIGUE_REDUCTION_PERCENT)

            recommended_weight_after_fatigue = recommended_weight_pre_adjustments * fatigue_multiplier
            if abs(fatigue_multiplier - 1.0) > 0.005: # Only add to explanation if fatigue adjustment is significant
               explanation_parts.append(f"Fatigue adj: {fatigue_multiplier:.3f} (score: {current_fatigue_value:.1f}).")


            # 8. Apply Readiness Adjustment
            cur.execute(
                "SELECT sleep_hours, stress_level, hrv_ms FROM workouts WHERE user_id = %s AND completed_at IS NOT NULL ORDER BY completed_at DESC LIMIT 1;",
                (str(user_id),)
            )
            latest_workout_readiness_data = cur.fetchone()

            readiness_mult = 1.0
            readiness_total_score = None # Default to None

            if latest_workout_readiness_data and \
               latest_workout_readiness_data['sleep_hours'] is not None and \
               latest_workout_readiness_data['stress_level'] is not None:

                readiness_mult, readiness_total_score = calculate_readiness_multiplier(
                    sleep_h=float(latest_workout_readiness_data['sleep_hours']),
                    stress_lvl=int(latest_workout_readiness_data['stress_level']),
                    hrv_ms=float(latest_workout_readiness_data['hrv_ms']) if latest_workout_readiness_data['hrv_ms'] is not None else None,
                    user_id=uuid.UUID(user_id),
                    db_conn=conn
                )
                explanation_parts.append(f"Readiness (score: {round(readiness_total_score * 100)}%) adj: x{readiness_mult:.3f}.")
            else:
                # Default readiness_mult is 1.0, readiness_total_score is None
                # Calculate what score would yield a 1.0 multiplier for consistent reporting if desired, or keep as None
                # (1.0 - MULTIPLIER_BASE) / MULTIPLIER_RANGE = (1.0 - 0.93) / 0.14 = 0.07 / 0.14 = 0.5
                # So, a score of 0.5 implies a multiplier of 1.0.
                # If no data, perhaps it's better to report score as None.
                explanation_parts.append("No recent readiness data for adjustment (multiplier x1.0).")

            recommended_weight_after_readiness = recommended_weight_after_fatigue * readiness_mult

            # 9. Round Weight
            final_weight = round_to_available_plates(
                target_weight_kg=recommended_weight_after_readiness,
                available_plates_kg=user_available_plates_kg,
                barbell_weight_kg=user_barbell_weight_kg,
                equipment_type=exercise_equipment_type
            )
            explanation_parts.append(f"Suggested: {final_weight:.2f}kg.")

            # from ..predictions import calculate_confidence_score # Delayed import
            # confidence = calculate_confidence_score(str(user_id), str(exercise_id), cur)


            logger.info(
                f"Recommendation for user {user_id}, ex {exercise_id} ('{exercise_data['name']}'): "
                f"Weight={final_weight:.2f}kg (Pre-adj: {recommended_weight_pre_adjustments:.2f}, "
                f"Post-Fatigue: {recommended_weight_after_fatigue:.2f}, Post-Readiness: {recommended_weight_after_readiness:.2f}), "
                f"Reps Low={base_params['rep_range_low']}, Reps High={base_params['rep_range_high']}, "
                f"Target RIR (goal): {base_params['target_rir']}"
            )

            return jsonify({
                "recommended_weight_kg": final_weight,
                "target_reps_low": base_params['rep_range_low'],
                "target_reps_high": base_params['rep_range_high'],
                "target_rir": base_params['target_rir'],
                "explanation": " ".join(explanation_parts),
                "readiness_score_percent": round(readiness_total_score * 100) if readiness_total_score is not None else None,
                # "confidence_score": confidence
            }), 200

    except psycopg2.Error as e:
        logger.error(f"DB error recommending set for user {user_id}, ex {exercise_id}: {e}", exc_info=True)
        return jsonify(error="Database error during recommendation."), 500
    except Exception as e:
        logger.error(f"Unexpected error recommending set for user {user_id}, ex {exercise_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred."), 500
    finally:
        if conn:
            release_db_connection(conn)


# --- Basic CRUD APIs for Exercises (P1-BE-010) ---
@workouts_bp.route('/v1/exercises', methods=['GET'])
def list_exercises():
    # Pagination parameters
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
    except ValueError:
        return jsonify(error="Invalid 'page' or 'per_page' parameter. Must be integers."), 400

    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 1
    if per_page > 100:
        per_page = 100  # Max per_page limit
    offset = (page - 1) * per_page

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Get total count for pagination metadata
            cur.execute("SELECT COUNT(*) FROM exercises WHERE is_public = TRUE;")
            total_exercises = cur.fetchone()['count']

            # Fetch paginated exercises
            cur.execute(
                """
                SELECT id, name, category, equipment, difficulty,
                       primary_muscles, secondary_muscles, main_target_muscle_group, is_public
                FROM exercises
                WHERE is_public = TRUE
                ORDER BY name
                LIMIT %s OFFSET %s;
                """,
                (per_page, offset)
            )
            exercises_list = cur.fetchall()

            return jsonify({
                "page": page,
                "per_page": per_page,
                "total_exercises": total_exercises,
                "total_pages": math.ceil(total_exercises / per_page),
                "data": exercises_list
            }), 200

    except psycopg2.Error as e:
        logger.error(f"Database error listing exercises: {e}")
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        logger.error(f"Unexpected error listing exercises: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            release_db_connection(conn)


@workouts_bp.route('/v1/sets/<uuid:set_id>', methods=['DELETE'])
@jwt_required
def delete_workout_set(set_id):
    user_id = g.current_user_id

    sql_query = "DELETE FROM workout_sets WHERE id = %s AND workout_id IN (SELECT id FROM workouts WHERE user_id = %s);"

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(sql_query, (str(set_id), user_id))

            if cur.rowcount == 0:
                # Check if the set exists at all for better error context (optional)
                cur.execute("SELECT id FROM workout_sets WHERE id = %s;", (str(set_id),))
                if not cur.fetchone():
                    logger.warning(f"Delete set {set_id} failed for user {user_id}: Set not found.")
                    abort(404, description="Set not found.")
                else:
                    logger.warning(f"Delete set {set_id} failed for user {user_id}: Set found but ownership check failed.")
                    abort(404, description="Set not found or not authorized to delete.") # Or 403

            conn.commit()
            logger.info(f"Set {set_id} deleted successfully by user {user_id}.")

            # Placeholder for recalculation/cleanup logic:
            # If a set is deleted, it might affect e1RM history or other aggregated data.
            # This might involve:
            # - Removing associated e1RM history entries if they were solely based on this set.
            # - Triggering a recalculation of exercise progression or user stats.
            # - This could be handled by an asynchronous task.
            # Example:
            # logger.info(f"Set {set_id} deleted. Scheduling related data cleanup/recalculation.")
            # queue_set_deletion_cleanup_task(user_id, exercise_id_of_set, deleted_set_data)

            return jsonify({"msg": "Set deleted successfully"}), 200

    except psycopg2.Error as e:
        logger.error(f"Database error deleting set {set_id} for user {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed"), 500
    except Exception as e: # Catch other exceptions like aborts
        logger.error(f"Unexpected error deleting set {set_id} for user {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        if hasattr(e, 'code') and e.code is not None: # Check if it's an HTTPException
            raise e
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            release_db_connection(conn)


@workouts_bp.route('/v1/sets/<uuid:set_id>', methods=['PATCH'])
@jwt_required
def edit_workout_set(set_id):
    user_id = g.current_user_id
    payload = request.json

    if not payload:
        logger.warning(f"Edit set {set_id} failed for user {user_id}: No JSON payload provided.")
        abort(400, description="Invalid request: No JSON payload provided.")

    allowed_fields = {"actual_weight", "actual_reps", "actual_rir", "notes"}
    updates = {}

    for field in allowed_fields:
        if field in payload:
            # Basic type validation, can be expanded
            if field in {"actual_weight", "actual_reps", "actual_rir"}:
                try:
                    if payload[field] is not None: # Allow null to clear, but if not null, validate type
                        if field == "actual_weight":
                            updates[field] = float(payload[field])
                        else: # reps, rir
                            updates[field] = int(payload[field])
                except ValueError:
                    logger.warning(f"Edit set {set_id} failed for user {user_id}: Invalid type for field '{field}'.")
                    abort(400, description=f"Invalid type for field '{field}'.")
            else: # notes (string)
                updates[field] = payload[field]


    if not updates:
        logger.info(f"Edit set {set_id} for user {user_id}: No valid fields to update provided.")
        abort(400, description="No valid fields to update provided.")

    set_clauses = [f"{field} = %s" for field in updates.keys()]
    sql_query = f"UPDATE workout_sets SET {', '.join(set_clauses)}, updated_at = NOW() " \
                f"WHERE id = %s AND workout_id IN (SELECT id FROM workouts WHERE user_id = %s);"

    update_values = list(updates.values())
    update_values.extend([str(set_id), user_id])

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(sql_query, tuple(update_values))
            if cur.rowcount == 0:
                # Check if the set exists at all, to distinguish between not found vs not owned
                # This adds an extra query, but provides better error feedback potential
                cur.execute("SELECT workout_id FROM workout_sets WHERE id = %s", (str(set_id),))
                set_exists = cur.fetchone()
                if not set_exists:
                    logger.warning(f"Edit set {set_id} failed for user {user_id}: Set not found.")
                    abort(404, description="Set not found.")
                else:
                    logger.warning(f"Edit set {set_id} failed for user {user_id}: Set found but ownership check failed (or no changes made).")
                    # This could also mean the data sent was the same as existing,
                    # though `updated_at` should still trigger rowcount=1 if ownership is fine.
                    # For simplicity, treating as "not found or not authorized".
                    abort(404, description="Set not found or not authorized to edit.")


            conn.commit()
            logger.info(f"Set {set_id} updated successfully by user {user_id}. Fields updated: {', '.join(updates.keys())}")

            # Placeholder for recalculation logic:
            # If 'actual_weight', 'actual_reps', or 'actual_rir' are in updates:
            # - Consider recalculating user's RIR bias.
            # - Consider updating e1RM history for this set/exercise.
            # - This might involve queuing a background task (e.g., with RQ).
            # Example:
            # if any(key in updates for key in ['actual_weight', 'actual_reps', 'actual_rir']):
            #   logger.info(f"Set {set_id} data relevant to predictions changed. Scheduling recalculations.")
            #   # queue_recalculation_task(user_id, exercise_id_of_set, set_id)

            return jsonify({"msg": "Set updated successfully"}), 200

    except psycopg2.Error as e:
        logger.error(f"Database error updating set {set_id} for user {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed"), 500
    except Exception as e: # Catch other exceptions like aborts if they are not Response objects
        logger.error(f"Unexpected error updating set {set_id} for user {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        # If e is an HTTPException from abort(), re-raise it or Flask handles it.
        # Otherwise, return a generic 500.
        if hasattr(e, 'code') and e.code is not None: # Check if it's an HTTPException
            raise e
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            release_db_connection(conn)

@workouts_bp.route('/api/v1/workouts/exercise/<uuid:exercise_id>/previous-performance', methods=['GET'])
@jwt_required
def get_previous_performance(exercise_id):
    from flask import g
    user_id = g.current_user_id

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Get user's current RIR bias for e1RM calculations
            cur.execute("SELECT rir_bias FROM users WHERE id = %s;", (user_id,))
            user_record = cur.fetchone()
            if not user_record:
                logger.warning(f"User {user_id} not found when fetching RIR bias for previous performance.")
                return jsonify(error="User not found."), 404 # Should not happen if JWT is valid
            user_rir_bias = float(user_record['rir_bias'])

            # Fetch the last two workout sets for this user and exercise
            # We join with workouts to ensure we only get sets from workouts belonging to the user
            cur.execute(
                """
                SELECT ws.actual_weight, ws.actual_reps, ws.actual_rir, ws.completed_at, ws.mti, ws.notes
                FROM workout_sets ws
                JOIN workouts w ON ws.workout_id = w.id
                WHERE w.user_id = %s AND ws.exercise_id = %s
                ORDER BY ws.completed_at DESC
                LIMIT 2;
                """,
                (user_id, str(exercise_id))
            )
            sets = cur.fetchall()

            if not sets:
                return jsonify(message="No previous performance recorded for this exercise."), 404

            # The primary "previous_set" is the most recent one
            previous_set_data = sets[0]
            # Convert decimal fields to float for JSON serialization if they aren't already
            previous_set_to_return = {
                "weight_kg": float(previous_set_data['actual_weight']) if previous_set_data['actual_weight'] is not None else None,
                "reps": previous_set_data['actual_reps'],
                "rir": previous_set_data['actual_rir'],
                "mti": previous_set_data['mti'],
                "notes": previous_set_data['notes'],
                "completed_at": previous_set_data['completed_at'].isoformat() if previous_set_data['completed_at'] else None
            }

            response_data = {
                "previous_set": previous_set_to_return,
                "progression_metric_string": "No comparison data available.",
                "is_positive_progression": None # Can be True, False, or None if no comparison
            }

            # If there's a second set, we can make a comparison
            if len(sets) > 1:
                older_set_data = sets[1]

                # Calculate e1RM for both sets using the user's current RIR bias
                # estimate_1rm_with_rir_bias(weight: float, reps: int, rir: int, user_rir_bias: float)
                e1rm_current = estimate_1rm_with_rir_bias(
                    float(previous_set_data['actual_weight']),
                    previous_set_data['actual_reps'],
                    previous_set_data['actual_rir'],
                    user_rir_bias
                )
                e1rm_older = estimate_1rm_with_rir_bias(
                    float(older_set_data['actual_weight']),
                    older_set_data['actual_reps'],
                    older_set_data['actual_rir'],
                    user_rir_bias
                )

                if e1rm_older > 0: # Avoid division by zero or meaningless comparison if older 1RM is 0
                    percentage_change = ((e1rm_current - e1rm_older) / e1rm_older) * 100
                    diff_kg = e1rm_current - e1rm_older

                    if abs(diff_kg) < 0.1: # Effectively no change
                        response_data['progression_metric_string'] = f"e1RM stable ({e1rm_current:.1f}kg vs {e1rm_older:.1f}kg)."
                        response_data['is_positive_progression'] = None # Neutral
                    elif diff_kg > 0:
                        response_data['progression_metric_string'] = f"+{diff_kg:.1f}kg ({percentage_change:+.1f}%) on e1RM vs previous."
                        response_data['is_positive_progression'] = True
                    else:
                        response_data['progression_metric_string'] = f"{diff_kg:.1f}kg ({percentage_change:+.1f}%) on e1RM vs previous."
                        response_data['is_positive_progression'] = False
                else:
                    response_data['progression_metric_string'] = f"Current e1RM: {e1rm_current:.1f}kg (no valid prior e1RM for comparison)."
                    response_data['is_positive_progression'] = None # Cannot determine trend
            else:
                 # Only one set exists, calculate its e1RM to display
                 e1rm_current = estimate_1rm_with_rir_bias(
                    float(previous_set_data['actual_weight']),
                    previous_set_data['actual_reps'],
                    previous_set_data['actual_rir'],
                    user_rir_bias
                )
                 response_data['progression_metric_string'] = f"First recorded set. e1RM: {e1rm_current:.1f}kg."
                 response_data['is_positive_progression'] = None


            return jsonify(response_data), 200

    except psycopg2.Error as e:
        logger.error(f"Database error fetching previous performance for user {user_id}, exercise {exercise_id}: {e}", exc_info=True)
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching previous performance for user {user_id}, exercise {exercise_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            release_db_connection(conn)

@workouts_bp.route('/v1/exercises/<uuid:exercise_id>', methods=['GET'])
def get_exercise_details(exercise_id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM exercises WHERE id = %s AND (is_public = TRUE OR TRUE);", # Assuming admin could see non-public, for now allow all by ID
                (str(exercise_id),)
            )
            exercise = cur.fetchone()
            if not exercise:
                return jsonify(error="Exercise not found or not public"), 404

            return jsonify(exercise), 200

    except psycopg2.Error as e:
        logger.error(f"Database error fetching exercise {exercise_id}: {e}")
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching exercise {exercise_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            release_db_connection(conn)

# --- Basic CRUD APIs for Workout Logging (P1-BE-011) ---
@workouts_bp.route('/v1/users/<uuid:user_id>/workouts', methods=['POST'])
@jwt_required
def create_workout(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        return jsonify(error="Forbidden. You can only create workouts for your own profile."), 403

    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    # Optional fields from request, with defaults or None
    plan_day_id = data.get('plan_day_id')
    started_at = data.get('started_at') # Expect ISO format string if provided
    fatigue_level = data.get('fatigue_level')
    sleep_hours = data.get('sleep_hours')
    stress_level = data.get('stress_level')
    notes = data.get('notes')

    if started_at:
        try:
            started_at_dt = datetime.fromisoformat(started_at)
        except ValueError:
            return jsonify(error="Invalid 'started_at' format. Use ISO 8601 format."), 400
    else:
        started_at_dt = datetime.now(timezone.utc)

    workout_id = str(uuid.uuid4())
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO workouts (id, user_id, plan_day_id, started_at,
                                      fatigue_level, sleep_hours, stress_level, notes,
                                      created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING *;
                """,
                (workout_id, str(user_id), plan_day_id, started_at_dt,
                 fatigue_level, sleep_hours, stress_level, notes)
            )
            new_workout = cur.fetchone()
            conn.commit()
            logger.info(f"Workout created successfully (ID: {workout_id}) for user: {user_id}")
            return jsonify(new_workout), 201

    except psycopg2.Error as e:
        logger.error(f"Database error creating workout for user {user_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed creating workout"), 500
    except Exception as e:
        logger.error(f"Unexpected error creating workout for user {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred creating workout"), 500
    finally:
        if conn:
            release_db_connection(conn)

@workouts_bp.route('/v1/users/<uuid:user_id>/workouts', methods=['GET'])
@jwt_required
def get_workouts_for_user(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        return jsonify(error="Forbidden. You can only view your own workouts."), 403

    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10)) # Fewer workouts per page by default
    except ValueError:
        return jsonify(error="Invalid 'page' or 'per_page' parameter. Must be integers."), 400

    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 1
    if per_page > 50:
        per_page = 50
    offset = (page - 1) * per_page

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT COUNT(*) FROM workouts WHERE user_id = %s;", (str(user_id),)
            )
            total_workouts = cur.fetchone()['count']

            cur.execute(
                "SELECT * FROM workouts WHERE user_id = %s ORDER BY started_at DESC LIMIT %s OFFSET %s;",
                (str(user_id), per_page, offset)
            )
            workouts_list = cur.fetchall()

            return jsonify({
                "page": page,
                "per_page": per_page,
                "total_workouts": total_workouts,
                "total_pages": math.ceil(total_workouts / per_page),
                "data": workouts_list
            }), 200

    except psycopg2.Error as e:
        logger.error(f"Database error fetching workouts for user {user_id}: {e}")
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching workouts for user {user_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            release_db_connection(conn)

@workouts_bp.route('/v1/workouts/<uuid:workout_id>', methods=['GET'])
@jwt_required
def get_single_workout(workout_id):
    from flask import g
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # First, verify the workout belongs to the authenticated user
            cur.execute("SELECT user_id FROM workouts WHERE id = %s;", (str(workout_id),))
            workout_owner = cur.fetchone()
            if not workout_owner:
                return jsonify(error="Workout not found"), 404
            if workout_owner['user_id'] != uuid.UUID(g.current_user_id): # Ensure types match for comparison
                 logger.warning(f"Forbidden attempt to access workout {workout_id} by user {g.current_user_id}")
                 return jsonify(error="Forbidden. You can only view your own workouts."), 403

            # Fetch workout details
            cur.execute("SELECT * FROM workouts WHERE id = %s;", (str(workout_id),))
            workout_details = cur.fetchone() # Already checked it exists

            # Fetch associated sets
            cur.execute(
                """
                SELECT ws.*, e.name as exercise_name
                FROM workout_sets ws
                JOIN exercises e ON ws.exercise_id = e.id
                WHERE ws.workout_id = %s
                ORDER BY ws.set_number ASC;
                """, (str(workout_id),)
            )
            sets_list = cur.fetchall()

            workout_details['sets'] = sets_list
            return jsonify(workout_details), 200

    except psycopg2.Error as e:
        logger.error(f"Database error fetching workout {workout_id}: {e}")
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching workout {workout_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            release_db_connection(conn)

@workouts_bp.route('/v1/workouts/<uuid:workout_id>/sets', methods=['POST'])
@jwt_required
def log_set_to_workout(workout_id):
    from flask import g
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Verify workout belongs to the authenticated user
            cur.execute("SELECT user_id FROM workouts WHERE id = %s;", (str(workout_id),))
            workout_owner = cur.fetchone()
            if not workout_owner:
                return jsonify(error="Workout not found"), 404
            if workout_owner['user_id'] != uuid.UUID(g.current_user_id):
                 logger.warning(f"Forbidden attempt to log set to workout {workout_id} by user {g.current_user_id}")
                 return jsonify(error="Forbidden. You can only add sets to your own workouts."), 403

            data = request.get_json()
            if not data:
                return jsonify(error="Request body must be JSON"), 400

            required_fields = ['exercise_id', 'set_number', 'actual_weight', 'actual_reps', 'actual_rir']
            for field in required_fields:
                if field not in data:
                    return jsonify(error=f"Missing required field: {field}"), 400

            # Type validation can be added here for each field
            try:
                exercise_id = str(uuid.UUID(data['exercise_id'])) # Validate UUID format
                set_number = int(data['set_number'])
                actual_weight = float(data['actual_weight'])
                actual_reps = int(data['actual_reps'])
                actual_rir = int(data['actual_rir'])
                # Optional fields
                rest_before_seconds = data.get('rest_before_seconds')
                if rest_before_seconds is not None:
                    rest_before_seconds = int(rest_before_seconds)
                completed_at_str = data.get('completed_at')
                set_notes = data.get('notes')
            except (ValueError, TypeError) as ve:
                return jsonify(error=f"Invalid data type for one or more fields: {ve}"), 400


            completed_at_dt = datetime.now(timezone.utc)
            if completed_at_str:
                try:
                    completed_at_dt = datetime.fromisoformat(completed_at_str)
                except ValueError:
                     return jsonify(error="Invalid 'completed_at' format. Use ISO 8601 format."), 400

            set_id = str(uuid.uuid4())
            _effective_reps, mti_score = calculate_mti(actual_weight, actual_reps, actual_rir)

            cur.execute(
                """
                INSERT INTO workout_sets (
                    id, workout_id, exercise_id, set_number,
                    actual_weight, actual_reps, actual_rir,
                    rest_before_seconds, completed_at, notes, mti, -- Added mti column
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()) -- Added %s for mti
                RETURNING *;
                """,
                (set_id, str(workout_id), exercise_id, set_number,
                 actual_weight, actual_reps, actual_rir,
                 rest_before_seconds, completed_at_dt, set_notes, mti_score) # Added mti_score to params
            )
            new_set = cur.fetchone()
            conn.commit()
            logger.info(f"Set {set_id} logged to workout {workout_id} successfully.")
            return jsonify(new_set), 201

    except psycopg2.Error as e:
        logger.error(f"Database error logging set to workout {workout_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed logging set"), 500
    except Exception as e:
        logger.error(f"Unexpected error logging set to workout {workout_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred logging set"), 500
    finally:
        if conn:
            release_db_connection(conn)

@workouts_bp.route('/v1/workouts/<uuid:workout_id>', methods=['PUT'])
@jwt_required
def update_workout_summary(workout_id):
    user_id_from_token = g.current_user_id

    data = request.get_json()
    if not data:
        logger.warning(f"Update workout {workout_id} failed: No JSON payload provided by user {user_id_from_token}.")
        return jsonify(error="Invalid request: No JSON payload provided."), 400

    # Fields that can be updated in the workout summary
    allowed_fields = {
        "completed_at": datetime, # Expect ISO string, will be parsed
        "fatigue_level": float,
        "sleep_hours": float,
        "hrv_ms": float,
        "stress_level": float, # Or int, depending on how it's stored/used
        "notes": str
    }

    update_payload = {}
    update_errors = []

    for field, field_type in allowed_fields.items():
        if field in data:
            value = data[field]
            if value is None and field not in ["hrv_ms", "notes", "fatigue_level", "sleep_hours", "stress_level"]: # These can be explicitly nulled
                 update_errors.append(f"Field '{field}' cannot be null.")
                 continue

            if value is not None: # Process if not None, or if it's an allowed nullable field like notes/hrv
                try:
                    if field_type is datetime:
                        # Frontend sends ISO string, convert to datetime object
                        update_payload[field] = datetime.fromisoformat(value)
                        # Ensure timezone awareness if needed, fromisoformat might produce naive if tz not in string
                        if update_payload[field].tzinfo is None:
                             update_payload[field] = update_payload[field].replace(tzinfo=timezone.utc)
                    elif field_type is float:
                        update_payload[field] = float(value)
                    elif field_type is int: # e.g. for stress_level if it's int
                        update_payload[field] = int(value)
                    else: # string for notes
                        update_payload[field] = str(value)
                except ValueError:
                    update_errors.append(f"Invalid data type for field '{field}'. Expected format for {field_type.__name__}.")
            else: # Value is None, explicitly set for allowed nullable fields
                 update_payload[field] = None


    if update_errors:
        logger.warning(f"Update workout {workout_id} for user {user_id_from_token} failed due to validation errors: {update_errors}")
        return jsonify(errors=update_errors), 400

    if not update_payload:
        logger.info(f"Update workout {workout_id} for user {user_id_from_token}: No valid fields provided for update.")
        return jsonify(msg="No valid fields provided for update or no changes needed."), 200 # Or 400 if no fields is an error

    # Add updated_at timestamp
    update_payload["updated_at"] = datetime.now(timezone.utc)

    set_clauses = [f"{field} = %s" for field in update_payload.keys()]
    sql_query = f"UPDATE workouts SET {', '.join(set_clauses)} WHERE id = %s AND user_id = %s RETURNING *;"

    query_params = list(update_payload.values())
    query_params.extend([str(workout_id), user_id_from_token])

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # First, verify ownership and existence (already part of WHERE clause but good for early 404)
            cur.execute("SELECT id FROM workouts WHERE id = %s AND user_id = %s;", (str(workout_id), user_id_from_token))
            if not cur.fetchone():
                logger.warning(f"Update workout failed: Workout {workout_id} not found or not owned by user {user_id_from_token}.")
                abort(404, description="Workout not found or you do not have permission to update it.")

            cur.execute(sql_query, tuple(query_params))
            if cur.rowcount == 0:
                # This case should ideally be caught by the check above.
                # If reached, it might mean no actual data change occurred, or a race condition.
                logger.warning(f"Update workout {workout_id} for user {user_id_from_token}: Rowcount 0, workout not updated (no change or error).")
                # Fetch current to return, or indicate no change
                cur.execute("SELECT * FROM workouts WHERE id = %s AND user_id = %s;", (str(workout_id), user_id_from_token))
                updated_workout_data = cur.fetchone()
                if updated_workout_data:
                     return jsonify(updated_workout_data), 200 # Return current data if no change made by update
                else: # Should not happen if first check passed
                     abort(404, description="Workout not found after update attempt.")


            updated_workout_data = cur.fetchone()
            conn.commit()
            logger.info(f"Workout {workout_id} summary updated successfully by user {user_id_from_token}.")
            return jsonify(updated_workout_data), 200

    except psycopg2.Error as e:
        logger.error(f"Database error updating workout {workout_id} for user {user_id_from_token}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        logger.error(f"Unexpected error updating workout {workout_id} for user {user_id_from_token}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        if hasattr(e, 'code') and e.code is not None: # Check if it's an HTTPException (from abort)
            raise e
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            release_db_connection(conn)


# The new endpoint as per the subtask description
@workouts_bp.route('/v1/users/<uuid:user_id>/exercises/<uuid:exercise_id>/log-set', methods=['POST'])
@jwt_required
def log_set_for_user_exercise(user_id, exercise_id):
    from flask import g
    # Authenticate: Ensure the JWT's user_id matches the user_id in the path
    if str(user_id) != g.current_user_id:
        logger.warning(f"Forbidden attempt to log set for user {user_id} by user {g.current_user_id}")
        return jsonify(error="Forbidden. You can only log sets for your own profile."), 403

    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    required_fields = ['weight_kg', 'reps', 'rir']
    for field in required_fields:
        if field not in data or data[field] is None: # Also check for None
            return jsonify(error=f"Missing or null required field: {field}"), 400

    try:
        weight_kg = float(data['weight_kg'])
        reps = int(data['reps'])
        rir = int(data['rir'])
        notes = data.get('notes') # Optional
        completed_at_str = data.get('completed_at') # Optional

        if weight_kg < 0 or reps < 0: # RIR can be 0 normally
            return jsonify(error="Weight and reps cannot be negative."), 400
        if rir < 0 or rir > 10: # Assuming RIR scale 0-10
             return jsonify(error="RIR must be between 0 and 10."), 400

    except (ValueError, TypeError) as ve:
        logger.error(f"Invalid data type for set logging for user {user_id}, exercise {exercise_id}: {ve}")
        return jsonify(error=f"Invalid data type for one or more fields: {ve}"), 400

    completed_at_dt = datetime.now(timezone.utc)
    if completed_at_str:
        try:
            # Attempt to parse, assuming ISO format. Add timezone if naive.
            parsed_dt = datetime.fromisoformat(completed_at_str)
            if parsed_dt.tzinfo is None:
                completed_at_dt = parsed_dt.replace(tzinfo=timezone.utc)
            else:
                completed_at_dt = parsed_dt
        except ValueError:
            logger.warning(f"Invalid 'completed_at' format '{completed_at_str}' for user {user_id}. Using current time.")
            # Fallback to now() is already handled by default initialization

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # --- Start Transaction ---
            # All operations should be atomic for this endpoint

            # 1. Fetch User's Current RIR Bias, LR, and Error EMA
            cur.execute(
                "SELECT rir_bias, rir_bias_lr, rir_bias_error_ema FROM users WHERE id = %s FOR UPDATE;",
                (str(user_id),)
            ) # Lock user row
            user_data = cur.fetchone()
            if not user_data:
                logger.error(f"User not found for ID: {user_id} during set logging.")
                conn.rollback() # Release lock
                return jsonify(error="User not found."), 404

            current_rir_bias = float(user_data['rir_bias'])
            current_rir_bias_lr = float(user_data['rir_bias_lr'])
            current_rir_bias_error_ema = float(user_data['rir_bias_error_ema'])

            # 2. Fetch Latest Estimated 1RM (Pre-Set)
            cur.execute(
                """
                SELECT estimated_1rm FROM estimated_1rm_history
                WHERE user_id = %s AND exercise_id = %s
                ORDER BY calculated_at DESC LIMIT 1;
                """,
                (str(user_id), str(exercise_id))
            )
            latest_1rm_record = cur.fetchone()
            latest_estimated_1rm = float(latest_1rm_record['estimated_1rm']) if latest_1rm_record else 0.0

            # 3. Calculate `predicted_reps` for RIR Bias Update
            predicted_reps_for_bias_update = 0
            if latest_estimated_1rm > 0.001 and weight_kg < latest_estimated_1rm : # Check latest_1rm is not zero and weight is less
                # Formula: R_pred = ( (1 - w/prev_1RM) / 0.0333 ) - max(0, actual_rir - current_rir_bias)
                term_one_numerator = 1.0 - (weight_kg / latest_estimated_1rm)
                # Ensure term_one_numerator is positive, otherwise predicted reps would be negative from this part
                if term_one_numerator > 0:
                    reps_component_from_1rm = term_one_numerator / 0.0333
                    # actual_rir from input is used here as per plan
                    adjusted_rir_for_pred = max(0, rir - current_rir_bias)
                    predicted_reps_for_bias_update = round(reps_component_from_1rm - adjusted_rir_for_pred)
                else: # weight_kg is too close to or above latest_estimated_1rm for this formula part
                    predicted_reps_for_bias_update = 0
                predicted_reps_for_bias_update = max(0, predicted_reps_for_bias_update) # Ensure non-negative
            elif weight_kg >= latest_estimated_1rm and latest_estimated_1rm > 0.001 : # If lifting at or more than prev 1RM
                 predicted_reps_for_bias_update = 0 # Predict 0-1 reps
            # If no latest_estimated_1rm, predicted_reps_for_bias_update remains 0, leading to minimal RIR bias change if actual_reps also 0.

            # 4. Update RIR Bias and Error EMA
            new_rir_bias, new_rir_error_ema = update_user_rir_bias(
                current_rir_bias,
                predicted_reps_for_bias_update,
                reps,
                current_rir_bias_lr,
                current_rir_bias_error_ema
            )
            cur.execute(
                "UPDATE users SET rir_bias = %s, rir_bias_error_ema = %s, updated_at = NOW() WHERE id = %s;",
                (new_rir_bias, new_rir_error_ema, str(user_id))
            )
            logger.info(
                f"RIR bias for user {user_id} updated from {current_rir_bias:.3f} to {new_rir_bias:.3f}. "
                f"Error EMA from {current_rir_bias_error_ema:.3f} to {new_rir_error_ema:.3f}. "
                f"Base LR: {current_rir_bias_lr:.3f}. Pred Reps: {predicted_reps_for_bias_update}, Actual Reps: {reps}."
            )

            # 5. Calculate New Estimated 1RM (Post-Set)
            # Use the *newly updated* rir_bias for this calculation
            new_estimated_1rm = estimate_1rm_with_rir_bias(weight_kg, reps, rir, new_rir_bias)
            e1rm_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO estimated_1rm_history
                (id, user_id, exercise_id, estimated_1rm, calculation_method, calculated_at)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (e1rm_id, str(user_id), str(exercise_id), new_estimated_1rm, "epley_rir_biased", completed_at_dt) # Use completed_at_dt
            )
            logger.info(f"New 1RM estimate {new_estimated_1rm}kg for user {user_id}, exercise {exercise_id} stored.")

            # 6. Calculate MTI
            _effective_reps, mti_score = calculate_mti(weight_kg, reps, rir)

            # 7. Log the Set (into `workout_sets`)
            # 7a. Implicit Workout Creation: Find or create a workout for today (UTC date of completed_at_dt)
            workout_date_utc = completed_at_dt.date() # Get date part in UTC

            cur.execute(
                """
                SELECT id FROM workouts
                WHERE user_id = %s AND DATE(started_at AT TIME ZONE 'UTC') = %s
                ORDER BY started_at DESC LIMIT 1;
                """,
                (str(user_id), workout_date_utc)
            )
            todays_workout = cur.fetchone()
            workout_id_for_set: str

            if todays_workout:
                workout_id_for_set = str(todays_workout['id'])
            else:
                workout_id_for_set = str(uuid.uuid4())
                # Use completed_at_dt for started_at of auto-created workout for consistency
                cur.execute(
                    """
                    INSERT INTO workouts (id, user_id, started_at, notes, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NOW(), NOW());
                    """,
                    (workout_id_for_set, str(user_id), completed_at_dt, "Auto-created workout for ad-hoc set.")
                )

            # 7b. Determine `set_number`
            cur.execute(
                """
                SELECT COALESCE(MAX(set_number), 0) as max_set_num FROM workout_sets
                WHERE workout_id = %s AND exercise_id = %s;
                """,
                (workout_id_for_set, str(exercise_id))
            )
            max_set_record = cur.fetchone()
            current_set_number = int(max_set_record['max_set_num']) + 1

            # 7c. Insert the set
            set_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO workout_sets (
                    id, workout_id, exercise_id, set_number,
                    actual_weight, actual_reps, actual_rir, mti,
                    completed_at, notes, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING *;
                """,
                (set_id, workout_id_for_set, str(exercise_id), current_set_number,
                 weight_kg, reps, rir, mti_score,
                 completed_at_dt, notes)
            )
            new_set_log = cur.fetchone()

            conn.commit()
            logger.info(
                f"Set {set_id} (workout: {workout_id_for_set}) logged for user {user_id}, ex {exercise_id}. "
                f"MTI: {mti_score:.2f}, New 1RM: {new_estimated_1rm:.2f}, "
                f"New RIR Bias: {new_rir_bias:.3f}, New RIR Error EMA: {new_rir_error_ema:.3f}"
            )
            return jsonify(new_set_log), 201

    except psycopg2.Error as e:
        logger.error(f"Database error logging set for user {user_id}, exercise {exercise_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        # Consider more specific error messages based on PostgreSQL error codes if needed
        return jsonify(error=f"Database operation failed. Please check logs."), 500
    except Exception as e:
        logger.error(f"Unexpected error logging set for user {user_id}, exercise {exercise_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error=f"An unexpected error occurred. Please check logs."), 500
    finally:
        if conn:
            release_db_connection(conn)