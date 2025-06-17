from flask import Blueprint, request, jsonify
from ..app import (
    get_db_connection,
    release_db_connection,
    jwt_required,
    logger,
)
# Corrected imports for progression and learning_models
from engine.progression import (
    detect_plateau,
    generate_deload_protocol,
    PlateauStatus,
)
from engine.learning_models import (
    update_user_rir_bias,
    calculate_current_fatigue,
    DEFAULT_RECOVERY_TAU_MAP,
    SessionRecord,
)

from engine.predictions import extended_epley_1rm, round_to_available_plates, calculate_confidence_score
import psycopg2
import psycopg2.extras
from datetime import datetime

# --- Constants for Smart 1RM Defaults ---
EXERCISE_DEFAULT_1RM = {
    'barbell_bench_press': {'beginner': 40.0, 'intermediate': 70.0, 'advanced': 100.0},
    'bicep_curl': {'beginner': 10.0, 'intermediate': 20.0, 'advanced': 30.0},
    'leg_press': {'beginner': 100.0, 'intermediate': 200.0, 'advanced': 300.0},
    'deadlift': {'beginner': 60.0, 'intermediate': 100.0, 'advanced': 140.0},
    'overhead_press': {'beginner': 30.0, 'intermediate': 50.0, 'advanced': 70.0},
    # Add more exercises as needed. Key by exercise name (lowercase, spaces replaced with underscore)
}

FALLBACK_DEFAULT_1RM = 30.0 # Generic fallback if no specific default is found

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/v1/predict/1rm/epley', methods=['POST'])
def predict_1rm_epley():
    data = request.get_json()
    if not data or 'weight' not in data or 'reps' not in data:
        return jsonify({"error": "Missing 'weight' or 'reps' in request body"}), 400

    try:
        weight = float(data['weight'])
        reps = int(data['reps'])
    except ValueError:
        return jsonify({"error": "Invalid 'weight' or 'reps' format. Must be numeric."}), 400

    if weight <= 0:
        return jsonify({"error": "'weight' must be positive."}), 400
    if reps < 1:
        return jsonify({"error": "'reps' must be 1 or greater for Epley prediction."}), 400

    estimated_1rm = extended_epley_1rm(weight, reps)

    return jsonify({
        "weight_input": weight,
        "reps_input": reps,
        "estimated_1rm_epley": estimated_1rm,
        "units": "same_as_input_weight"
    })

@analytics_bp.route('/v1/user/<uuid:user_id>/update-rir-bias', methods=['POST'])
def rir_bias_update_route(user_id):
    user_id_str = str(user_id)
    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    actual_reps = data.get('actual_reps')
    predicted_reps = data.get('predicted_reps')
    learning_rate = data.get('learning_rate', 0.1)

    if actual_reps is None or predicted_reps is None:
        return jsonify(error="Missing 'actual_reps' or 'predicted_reps' in request body"), 400

    try:
        actual_reps = int(actual_reps)
        predicted_reps = int(predicted_reps)
        learning_rate = float(learning_rate)
    except ValueError:
        return jsonify(error="Invalid data type for reps or learning_rate"), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT rir_bias FROM users WHERE id = %s;", (user_id_str,))
            user_data_db = cur.fetchone() # Renamed to avoid conflict with outer scope user_data
            if not user_data_db:
                return jsonify(error="User not found"), 404

            current_rir_bias = float(user_data_db['rir_bias'])

            new_rir_bias = update_user_rir_bias(
                current_rir_bias,
                predicted_reps,
                actual_reps,
                learning_rate
            )

            cur.execute(
                "UPDATE users SET rir_bias = %s, updated_at = NOW() WHERE id = %s;",
                (new_rir_bias, user_id_str)
            )
            conn.commit()

            return jsonify(user_id=user_id_str, new_rir_bias=new_rir_bias), 200

    except psycopg2.Error as e:
        logger.error(f"Database error in update_rir_bias: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        logger.error(f"Unexpected error in update_rir_bias: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            release_db_connection(conn)

@analytics_bp.route('/v1/user/<uuid:user_id>/fatigue-status', methods=['GET'])
def fatigue_status_route(user_id):
    user_id_str = str(user_id)
    muscle_group = request.args.get('muscle_group')

    if not muscle_group:
        return jsonify(error="Missing 'muscle_group' query parameter"), 400

    muscle_group = muscle_group.lower()

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT recovery_multipliers FROM users WHERE id = %s;", (user_id_str,))
            user_data_db = cur.fetchone() # Renamed
            if not user_data_db:
                return jsonify(error="User not found"), 404

            user_recovery_multiplier = 1.0
            # Ensure recovery_multipliers is treated as a dict even if None/null from DB
            recovery_multipliers_data = user_data_db.get('recovery_multipliers') or {}
            if isinstance(recovery_multipliers_data, dict):
                user_recovery_multiplier = float(recovery_multipliers_data.get(muscle_group, 1.0))

            session_history_query = """
                SELECT
                    ws.completed_at AS session_date,
                    (ws.actual_weight * ws.actual_reps) AS stimulus
                FROM workout_sets ws
                JOIN workouts w ON ws.workout_id = w.id
                JOIN exercises e ON ws.exercise_id = e.id
                WHERE w.user_id = %s
                  AND e.main_target_muscle_group = %s
                  AND ws.completed_at IS NOT NULL
                  AND ws.actual_weight IS NOT NULL
                  AND ws.actual_reps IS NOT NULL
                ORDER BY ws.completed_at DESC
                LIMIT 50;
            """
            try:
                cur.execute(session_history_query, (user_id_str, muscle_group))
                raw_session_history = cur.fetchall()
            except psycopg2.Error as db_err:
                logger.error(f"Database error fetching session history: {db_err}")
                return jsonify(error=f"Error fetching session history for {muscle_group}. Check server logs and schema."), 500

            session_history_formatted: list[SessionRecord] = []
            for record in raw_session_history:
                if isinstance(record['session_date'], datetime) and \
                   (isinstance(record['stimulus'], float) or isinstance(record['stimulus'], int)):
                    session_history_formatted.append({
                        'session_date': record['session_date'],
                        'stimulus': float(record['stimulus'])
                    })

            current_fatigue = calculate_current_fatigue(
                muscle_group,
                session_history_formatted,
                DEFAULT_RECOVERY_TAU_MAP,
                user_recovery_multiplier
            )

            return jsonify(
                user_id=user_id_str,
                muscle_group=muscle_group,
                current_fatigue=current_fatigue,
                user_recovery_multiplier_applied=user_recovery_multiplier,
                session_records_found=len(session_history_formatted)
            ), 200

    except psycopg2.Error as e:
        logger.error(f"Database error in fatigue_status: {e}")
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        logger.error(f"Unexpected error in fatigue_status: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            release_db_connection(conn)

@analytics_bp.route('/v1/user/<uuid:user_id>/exercise/<uuid:exercise_id>/recommend-set-parameters', methods=['GET'])
def recommend_set_parameters_route(user_id, exercise_id):
    user_id_str = str(user_id)
    exercise_id_str = str(exercise_id)

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT goal_slider, rir_bias, recovery_multipliers, experience_level, equipment_settings FROM users WHERE id = %s;", (user_id_str,))
            user_data_db = cur.fetchone() # Renamed
            if not user_data_db:
                return jsonify(error="User not found"), 404

            goal_slider = float(user_data_db['goal_slider'])
            user_rir_bias = float(user_data_db.get('rir_bias', 0.0)) # Added .get with default
            user_experience_level = user_data_db.get('experience_level', 'intermediate').lower() # Default to intermediate
            recovery_multipliers_data = user_data_db.get('recovery_multipliers') or {} # Renamed

            equipment_settings = user_data_db.get('equipment_settings')
            if not isinstance(equipment_settings, dict):
                equipment_settings = {}

            user_available_plates_from_db = equipment_settings.get('available_plates_kg')
            if isinstance(user_available_plates_from_db, list) and \
               all(isinstance(p, (int, float)) and p > 0 for p in user_available_plates_from_db) and \
               user_available_plates_from_db:
                user_available_plates = user_available_plates_from_db
            else:
                user_available_plates = None

            user_barbell_weight_from_db = equipment_settings.get('barbell_weight_kg')
            if isinstance(user_barbell_weight_from_db, (int, float)) and user_barbell_weight_from_db > 0:
                user_barbell_weight = user_barbell_weight_from_db
            else:
                user_barbell_weight = None

            cur.execute("SELECT name, main_target_muscle_group FROM exercises WHERE id = %s;", (exercise_id_str,))
            exercise_data_db = cur.fetchone() # Renamed
            if not exercise_data_db:
                return jsonify(error="Exercise not found"), 404
            exercise_name = exercise_data_db['name']
            main_target_muscle_group = exercise_data_db['main_target_muscle_group']
            if not main_target_muscle_group:
                 return jsonify(error=f"Exercise '{exercise_name}' is missing 'main_target_muscle_group'."), 500

            cur.execute("""
                SELECT estimated_1rm FROM estimated_1rm_history
                WHERE user_id = %s AND exercise_id = %s
                ORDER BY calculated_at DESC
                LIMIT 1;
            """, (user_id_str, exercise_id_str))
            e1rm_data = cur.fetchone()
            estimated_1rm = None
            e1rm_source = None
            if e1rm_data:
                estimated_1rm = float(e1rm_data['estimated_1rm'])
                e1rm_source = "history"
            else:
                # No history, try to use smart defaults
                exercise_key = exercise_name.lower().replace(' ', '_') # Normalize exercise name for lookup
                if exercise_key in EXERCISE_DEFAULT_1RM:
                    if user_experience_level in EXERCISE_DEFAULT_1RM[exercise_key]:
                        estimated_1rm = EXERCISE_DEFAULT_1RM[exercise_key][user_experience_level]
                        e1rm_source = f"{user_experience_level}_default_for_{exercise_key}"
                    else:
                        # Exercise is known, but experience level isn't a category in its defaults
                        # Fallback to 'intermediate' for that exercise if available, else generic fallback
                        if 'intermediate' in EXERCISE_DEFAULT_1RM[exercise_key]:
                            estimated_1rm = EXERCISE_DEFAULT_1RM[exercise_key]['intermediate']
                            e1rm_source = f"intermediate_default_for_{exercise_key}"
                        else: # Should not happen if defaults are structured well
                            estimated_1rm = FALLBACK_DEFAULT_1RM
                            e1rm_source = "fallback_default_no_level_match"

                if estimated_1rm is None: # If still None, use the generic fallback
                    estimated_1rm = FALLBACK_DEFAULT_1RM
                    e1rm_source = "fallback_default_exercise_unknown"

            user_recovery_multiplier = 1.0
            if isinstance(recovery_multipliers_data, dict): # Check if dict
                user_recovery_multiplier = float(recovery_multipliers_data.get(main_target_muscle_group, 1.0))

            session_history_query = """
                SELECT ws.completed_at AS session_date, (ws.actual_weight * ws.actual_reps) AS stimulus
                FROM workout_sets ws
                JOIN workouts w ON ws.workout_id = w.id
                JOIN exercises e ON ws.exercise_id = e.id
                WHERE w.user_id = %s AND e.main_target_muscle_group = %s
                  AND ws.completed_at IS NOT NULL AND ws.actual_weight IS NOT NULL AND ws.actual_reps IS NOT NULL
                ORDER BY ws.completed_at DESC LIMIT 50;
            """
            cur.execute(session_history_query, (user_id_str, main_target_muscle_group))
            raw_session_history = cur.fetchall()
            session_history_formatted: list[SessionRecord] = []
            for record in raw_session_history:
                 if isinstance(record['session_date'], datetime) and \
                   (isinstance(record['stimulus'], (float, int))): # Check type stimulus
                    session_history_formatted.append({
                        'session_date': record['session_date'],
                        'stimulus': float(record['stimulus'])
                    })

            current_fatigue = calculate_current_fatigue(
                main_target_muscle_group,
                session_history_formatted,
                DEFAULT_RECOVERY_TAU_MAP,
                user_recovery_multiplier
            )

            load_percentage_of_1rm = 0.60 + 0.35 * goal_slider

            # Calculate the system's ideal target RIR (actual physiological RIR)
            target_rir_ideal_actual_float = 2.5 - 1.5 * goal_slider

            # Adjust the RIR value to be displayed to the user, accounting for their bias
            # If bias is positive, user underestimates RIR (e.g., says RIR 1 when it's RIR 2).
            # So, to get them to an actual RIR of 2, we tell them to aim for RIR 1 (2 - 1 = 1).
            target_rir_for_user_perception_float = target_rir_ideal_actual_float - user_rir_bias

            # Clamp the displayed RIR to a practical range (e.g., 0 to 5)
            target_rir_for_user_perception_float = max(0.0, min(target_rir_for_user_perception_float, 5.0))
            target_rir_to_display = int(round(target_rir_for_user_perception_float))

            # For explanation and API response, also have the system's actual target RIR rounded
            system_actual_target_rir = int(round(target_rir_ideal_actual_float))

            rep_high_float = 6.0 + 6.0 * (1.0 - goal_slider)
            rep_high = int(round(rep_high_float))
            rep_low = int(round(max(1.0, rep_high_float - 4.0)))

            base_recommended_weight = estimated_1rm * load_percentage_of_1rm

            fatigue_reduction_per_10_points = 0.01
            fatigue_points_for_reduction = 10.0
            # Ensure current_fatigue is float for division
            fatigue_adjustment_factor = (float(current_fatigue) / fatigue_points_for_reduction) * fatigue_reduction_per_10_points
            fatigue_adjustment_factor = min(fatigue_adjustment_factor, 0.10)

            weight_reduction_due_to_fatigue = base_recommended_weight * fatigue_adjustment_factor
            adjusted_weight = base_recommended_weight - weight_reduction_due_to_fatigue

            final_rounded_weight = round_to_available_plates(
                adjusted_weight,
                user_available_plates,
                user_barbell_weight
            )

            goal_slider_desc = "hypertrophy" if goal_slider < 0.34 else "strength" if goal_slider > 0.66 else "blend"
            explanation = (
                f"Est. 1RM ({e1rm_source}): {estimated_1rm:.1f}kg. "
                f"Goal ('{goal_slider_desc}', slider: {goal_slider:.2f}): target {load_percentage_of_1rm*100:.0f}% of 1RM. "
                f"Base weight: {base_recommended_weight:.1f}kg. "
                f"Fatigue on '{main_target_muscle_group}' ({current_fatigue:.1f} pts): applied -{weight_reduction_due_to_fatigue:.1f}kg reduction. "
            )

            # Add RIR bias information to explanation
            if abs(user_rir_bias) > 0.05: # Only add if bias is significant
                 explanation += (
                    f"Your RIR reporting bias is {user_rir_bias:+.1f}. "
                    f"To achieve an actual RIR of ~{system_actual_target_rir}, system recommends you aim for RIR ~{target_rir_to_display}. "
                )
            else:
                explanation += f"Target RIR ~{system_actual_target_rir}. "


            explanation += (
                f"Final Recommendation: {final_rounded_weight:.1f}kg for {rep_low}-{rep_high} reps @ RIR ~{target_rir_to_display} (your perception)."
            )

            confidence_score = calculate_confidence_score(user_id_str, exercise_id_str, cur)

            if confidence_score is not None:
                explanation += f" Recommendation confidence: {confidence_score*100:.0f}%. "

            return jsonify({
                "user_id": user_id_str,
                "exercise_id": exercise_id_str,
                "exercise_name": exercise_name,
                "estimated_1rm_kg": round(estimated_1rm, 2),
                "e1rm_source": e1rm_source,
                "goal_slider": round(goal_slider, 2),
                "main_target_muscle_group": main_target_muscle_group,
                "current_fatigue": round(current_fatigue, 2),
                "recommended_weight_kg": final_rounded_weight,
                "target_reps_low": rep_low,
                "target_reps_high": rep_high,
                "target_rir": target_rir_to_display, # This is the RIR the user should aim for based on their perception
                "system_target_actual_rir": system_actual_target_rir, # For clarity
                "user_rir_bias_applied": round(user_rir_bias, 2), # For clarity, rounded
                "confidence_score": confidence_score, # New field (can be None)
                "explanation": explanation
            }), 200

    except psycopg2.Error as e:
        logger.error(f"Database error in recommend_set_parameters: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        logger.error(f"Unexpected error in recommend_set_parameters: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            release_db_connection(conn)

# --- Workout Plan Builder Endpoints ---
@analytics_bp.route('/v1/system/trigger-training-pipeline', methods=['POST'])
def trigger_training_pipeline_route():
    # Conceptual Authentication: In a real system, this endpoint would be secured.
    # For example, using an API key in the header, IP whitelisting, or a Bearer token.
    # Example:
    # api_key = request.headers.get('X-API-KEY')
    # if not api_key or api_key != os.getenv('INTERNAL_API_KEY'):
    #     logger.warning("Unauthorized attempt to trigger training pipeline.")
    #     return jsonify(error="Unauthorized"), 401

    data = request.get_json(silent=True) or {} # Allow empty body
    task_name = data.get('task_name', 'nightly_user_model_update')
    force_run = data.get('force_run', False)

    logger.info(f"Received request to trigger training pipeline. Task: {task_name}, Force run: {force_run}")

    try:
        from . import tasks  # Imported here to avoid circular dependency on startup
        job = tasks.queue.enqueue(tasks.nightly_user_model_update,
                                  task_name=task_name,
                                  force_run=force_run)
        logger.info(f"Enqueued training pipeline job {job.id}")
        return jsonify({
            "message": "Training pipeline enqueued",
            "job_id": job.id,
            "task_name": task_name,
            "force_run": force_run,
        }), 200

    except Exception as e:
        logger.error(f"Failed to enqueue training pipeline: {e}", exc_info=True)
        return jsonify(error="Failed to enqueue training pipeline"), 500
@analytics_bp.route('/v1/users/<uuid:user_id>/exercises/<uuid:exercise_id>/plateau-analysis', methods=['GET'])
@jwt_required
def get_plateau_analysis(user_id, exercise_id):
    from flask import g
    # from engine.learning_models import calculate_current_fatigue, DEFAULT_RECOVERY_TAU_MAP, SessionRecord -> Already imported

    # Authorization
    if str(user_id) != g.current_user_id:
        logger.warning(f"Forbidden attempt to access plateau analysis for user {user_id} by user {g.current_user_id}")
        return jsonify(error="Forbidden. You can only access your own data."), 403

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Fetch Exercise Details
            cur.execute(
                "SELECT name, main_target_muscle_group FROM exercises WHERE id = %s;",
                (str(exercise_id),)
            )
            exercise_data = cur.fetchone()
            if not exercise_data:
                return jsonify(error=f"Exercise with ID {exercise_id} not found."), 404
            if not exercise_data['main_target_muscle_group']:
                return jsonify(error=f"Exercise '{exercise_data['name']}' (ID: {exercise_id}) is missing 'main_target_muscle_group' which is required for analysis."), 404

            exercise_name = exercise_data['name']
            main_target_muscle_group = exercise_data['main_target_muscle_group']

            # 2. Fetch Historical Performance Data (e1RM)
            cur.execute(
                """
                SELECT estimated_1rm, calculated_at FROM estimated_1rm_history
                WHERE user_id = %s AND exercise_id = %s
                ORDER BY calculated_at ASC;
                """,
                (str(user_id), str(exercise_id))
            )
            e1rm_history_records = cur.fetchall()

            historical_e1rms = [float(record['estimated_1rm']) for record in e1rm_history_records]
            MIN_DATA_POINTS_FOR_PLATEAU = 7 # Configurable minimum for meaningful analysis

            if len(historical_e1rms) < MIN_DATA_POINTS_FOR_PLATEAU:
                return jsonify({
                    "user_id": str(user_id),
                    "exercise_id": str(exercise_id),
                    "exercise_name": exercise_name,
                    "main_target_muscle_group": main_target_muscle_group,
                    "historical_data_points_count": len(historical_e1rms),
                    "plateau_analysis": None,
                    "current_fatigue_score": None, # Could still calculate fatigue if desired
                    "deload_suggested": False,
                    "deload_protocol": None,
                    "summary_message": f"Insufficient data for plateau analysis. Need at least {MIN_DATA_POINTS_FOR_PLATEAU} e1RM records."
                }), 200 # Or 202 Accepted if we want to signify it's not a full analysis

            # 3. Fetch User Fatigue Score (adapting from fatigue_status_route)
            cur.execute("SELECT recovery_multipliers FROM users WHERE id = %s;", (str(user_id),))
            user_data_db = cur.fetchone() # User should exist if JWT valid and user_id matches
            if not user_data_db: # Should ideally not happen due to JWT check
                logger.error(f"User data not found for user {user_id} despite passing JWT check.")
                return jsonify(error="User data inconsistency."), 500

            user_recovery_multiplier = 1.0
            recovery_multipliers_data = user_data_db.get('recovery_multipliers') or {}
            if isinstance(recovery_multipliers_data, dict):
                user_recovery_multiplier = float(recovery_multipliers_data.get(main_target_muscle_group, 1.0))

            session_history_query = """
                SELECT ws.completed_at AS session_date, (ws.actual_weight * ws.actual_reps) AS stimulus
                FROM workout_sets ws
                JOIN workouts w ON ws.workout_id = w.id
                JOIN exercises e ON ws.exercise_id = e.id
                WHERE w.user_id = %s AND e.main_target_muscle_group = %s
                  AND ws.completed_at IS NOT NULL AND ws.actual_weight IS NOT NULL AND ws.actual_reps IS NOT NULL
                ORDER BY ws.completed_at DESC LIMIT 50;
            """
            cur.execute(session_history_query, (str(user_id), main_target_muscle_group))
            raw_session_history = cur.fetchall()
            session_history_formatted: list[SessionRecord] = []
            for record in raw_session_history:
                 if isinstance(record['session_date'], datetime) and \
                   (isinstance(record['stimulus'], (float, int))):
                    session_history_formatted.append({
                        'session_date': record['session_date'],
                        'stimulus': float(record['stimulus'])
                    })

            current_fatigue_score = calculate_current_fatigue(
                main_target_muscle_group,
                session_history_formatted,
                DEFAULT_RECOVERY_TAU_MAP, # Make sure this is available in scope
                user_recovery_multiplier
            )
            current_fatigue_score = round(current_fatigue_score, 2)


            # 4. Plateau Detection Logic
            # Using MIN_DATA_POINTS_FOR_PLATEAU as min_duration, or a slightly smaller number if appropriate
            plateau_min_duration = max(3, MIN_DATA_POINTS_FOR_PLATEAU - 2) # e.g. 5 if MIN_DATA_POINTS_FOR_PLATEAU is 7
            plateau_result = detect_plateau(
                values=historical_e1rms,
                min_duration=plateau_min_duration
            )

            # 5. Deload Protocol Generation
            deload_suggested = False
            deload_protocol = None
            summary_message = f"Analysis complete for {exercise_name}."

            if plateau_result['plateauing']:
                deload_suggested = True
                plateau_severity = 0.0
                if plateau_result['status'] == PlateauStatus.REGRESSION:
                    plateau_severity = 0.8
                    summary_message = f"Regression detected for {exercise_name}. A deload is recommended."
                elif plateau_result['status'] == PlateauStatus.STAGNATION:
                    plateau_severity = 0.5
                    summary_message = f"Stagnation detected for {exercise_name}. Consider a deload."
                elif plateau_result['status'] in [PlateauStatus.REGRESSION_WARNING, PlateauStatus.STAGNATION_WARNING]:
                    plateau_severity = 0.3 # Mild warning, might not always trigger deload by default
                    summary_message = f"Warning of potential {plateau_result['status'].name.lower().replace('_warning','')} for {exercise_name}."
                    # Optional: Only suggest deload for stronger signals
                    if plateau_severity < 0.4: # Example threshold
                        deload_suggested = False


                if deload_suggested:
                    deload_duration_weeks = 1 # Default duration
                    if plateau_severity >= 0.7: # Stronger regression
                        deload_duration_weeks = 2

                    deload_protocol = generate_deload_protocol(
                        plateau_severity=plateau_severity,
                        deload_duration_weeks=deload_duration_weeks,
                        recent_fatigue_score=current_fatigue_score
                    )
            else:
                summary_message = f"No significant plateau detected for {exercise_name} based on the last {len(historical_e1rms)} records."


            # 6. Response Formatting
            return jsonify({
                "user_id": str(user_id),
                "exercise_id": str(exercise_id),
                "exercise_name": exercise_name,
                "main_target_muscle_group": main_target_muscle_group,
                "historical_data_points_count": len(historical_e1rms),
                "plateau_analysis": plateau_result,
                "current_fatigue_score": current_fatigue_score,
                "deload_suggested": deload_suggested,
                "deload_protocol": deload_protocol,
                "summary_message": summary_message
            }), 200

    except psycopg2.Error as e:
        logger.error(f"Database error during plateau analysis for user {user_id}, exercise {exercise_id}: {e}", exc_info=True)
        return jsonify(error="Database operation failed during analysis."), 500
    except Exception as e:
        logger.error(f"Unexpected error during plateau analysis for user {user_id}, exercise {exercise_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred during analysis."), 500
    finally:
        if conn:
            release_db_connection(conn)


@analytics_bp.route('/v1/users/<uuid:user_id>/analytics/1rm-evolution', methods=['GET'])
@jwt_required
def get_1rm_evolution(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        logger.warning(
            f"Forbidden attempt to access 1RM evolution for user {user_id} by user {g.current_user_id}"
        )
        return jsonify(error="Forbidden. You can only access your own data."), 403

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT exercise_id, estimated_1rm, calculated_at
                FROM estimated_1rm_history
                WHERE user_id = %s
                ORDER BY calculated_at ASC;
                """,
                (str(user_id),),
            )
            records = cur.fetchall()

        evolution: dict[str, list[dict[str, float | str]]] = {}
        for rec in records:
            ex_id = str(rec["exercise_id"])
            evolution.setdefault(ex_id, []).append(
                {
                    "date": rec["calculated_at"].isoformat(),
                    "estimated_1rm": float(rec["estimated_1rm"]),
                }
            )

        return jsonify(evolution), 200
    except psycopg2.Error as e:
        logger.error(
            f"Database error during 1RM evolution fetch for user {user_id}: {e}",
            exc_info=True,
        )
        return jsonify(error="Database error during analytics fetch."), 500
    finally:
        if conn:
            release_db_connection(conn)


@analytics_bp.route('/v1/users/<uuid:user_id>/analytics/volume-heatmap', methods=['GET'])
@jwt_required
def get_volume_heatmap(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        logger.warning(
            f"Forbidden attempt to access volume heatmap for user {user_id} by user {g.current_user_id}"
        )
        return jsonify(error="Forbidden. You can only access your own data."), 403

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT date_trunc('week', ws.completed_at) AS week,
                       e.main_target_muscle_group AS muscle_group,
                       SUM(ws.actual_weight * ws.actual_reps) AS volume
                FROM workout_sets ws
                JOIN workouts w ON ws.workout_id = w.id
                JOIN exercises e ON ws.exercise_id = e.id
                WHERE w.user_id = %s AND ws.completed_at IS NOT NULL
                GROUP BY week, muscle_group
                ORDER BY week ASC;
                """,
                (str(user_id),),
            )
            rows = cur.fetchall()

        heatmap = [
            {
                "week": row["week"].date().isoformat(),
                "muscle_group": row["muscle_group"],
                "volume": float(row["volume"] or 0),
            }
            for row in rows
        ]

        return jsonify(heatmap), 200
    except psycopg2.Error as e:
        logger.error(
            f"Database error during volume heatmap fetch for user {user_id}: {e}",
            exc_info=True,
        )
        return jsonify(error="Database error during analytics fetch."), 500
    finally:
        if conn:
            release_db_connection(conn)


@analytics_bp.route('/v1/users/<uuid:user_id>/analytics/key-metrics', methods=['GET'])
@jwt_required
def get_key_metrics(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        logger.warning(
            f"Forbidden attempt to access key metrics for user {user_id} by user {g.current_user_id}"
        )
        return jsonify(error="Forbidden. You can only access your own data."), 403

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS count FROM workouts WHERE user_id = %s;", (str(user_id),))
            total_workouts = int(cur.fetchone()["count"])

            cur.execute(
                """
                SELECT COALESCE(SUM(ws.actual_weight * ws.actual_reps), 0) AS volume
                FROM workout_sets ws
                JOIN workouts w ON ws.workout_id = w.id
                WHERE w.user_id = %s
                  AND ws.actual_weight IS NOT NULL
                  AND ws.actual_reps IS NOT NULL;
                """,
                (str(user_id),),
            )
            total_volume = float(cur.fetchone()["volume"] or 0)

            cur.execute(
                "SELECT AVG(session_rpe) AS avg FROM workouts WHERE user_id = %s AND session_rpe IS NOT NULL;",
                (str(user_id),),
            )
            avg_rpe_row = cur.fetchone()
            avg_rpe = float(avg_rpe_row["avg"] or 0)

            # Calculate Most Frequent Exercise
            cur.execute(
                """
                SELECT e.name AS exercise_name, COUNT(ws.exercise_id) AS frequency
                FROM workout_sets ws
                JOIN workouts w ON ws.workout_id = w.id
                JOIN exercises e ON ws.exercise_id = e.id
                WHERE w.user_id = %s
                GROUP BY e.name
                ORDER BY frequency DESC
                LIMIT 1;
                """,
                (str(user_id),),
            )
            most_frequent_exercise_row = cur.fetchone()
            most_frequent_exercise = None
            if most_frequent_exercise_row:
                most_frequent_exercise = {
                    "name": most_frequent_exercise_row["exercise_name"],
                    "frequency": int(most_frequent_exercise_row["frequency"]),
                }

        return (
            jsonify(
                {
                    "total_workouts": total_workouts,
                    "total_volume": total_volume,
                    "avg_session_rpe": round(avg_rpe, 2) if avg_rpe else 0, # Ensure rounding for avg
                    "most_frequent_exercise": most_frequent_exercise,
                }
            ),
            200,
        )
    except psycopg2.Error as e:
        logger.error(
            f"Database error during key metrics fetch for user {user_id}: {e}",
            exc_info=True,
        )
        return jsonify(error="Database error during analytics fetch."), 500
    finally:
        if conn:
            release_db_connection(conn)

