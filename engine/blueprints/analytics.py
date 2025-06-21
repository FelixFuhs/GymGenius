from flask import Blueprint, request, jsonify, g # Added g
from engine.constants import SEX_MULTIPLIERS, PLATEAU_EVENT_NOTIFICATION_COOLDOWN_WEEKS # Import SEX_MULTIPLIERS
from app import get_db_connection, release_db_connection, jwt_required, logger
from datetime import timezone, timedelta # Added timedelta
# Corrected imports for progression and learning_models
from engine.progression import (
    detect_plateau,
    generate_deload_protocol,
    PlateauStatus,
    adjust_next_set,
)
from engine.mesocycles import get_or_create_current_mesocycle, PHASE_INTENSIFICATION, PHASE_DELOAD
from engine.learning_models import (
    update_user_rir_bias, # Make sure datetime is imported if not already
    calculate_current_fatigue,
    DEFAULT_RECOVERY_TAU_MAP,
    SessionRecord,
)

from engine.predictions import extended_epley_1rm, round_to_available_plates, calculate_confidence_score, estimate_1rm_with_rir_bias
import psycopg2
import psycopg2.extras
from datetime import datetime, date, timezone # Added date import, ensured timezone

# --- Constants for Smart 1RM Defaults ---
EXERCISE_DEFAULT_1RM = {
    'barbell_bench_press': {'beginner': 40.0, 'intermediate': 70.0, 'advanced': 100.0},
    'bicep_curl': {'beginner': 10.0, 'intermediate': 20.0, 'advanced': 30.0},
    'leg_press': {'beginner': 100.0, 'intermediate': 200.0, 'advanced': 300.0},
    'deadlift': {'beginner': 60.0, 'intermediate': 100.0, 'advanced': 140.0},
    'overhead_press': {'beginner': 30.0, 'intermediate': 50.0, 'advanced': 70.0},
    # Add more exercises as needed. Key by exercise name (lowercase, spaces replaced with underscore)
    "other": {"beginner": 20.0, "intermediate": 40.0, "advanced": 60.0}, # Added 'other' category
}

FALLBACK_DEFAULT_1RM = 30.0 # Generic fallback if no specific default is found

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/v1/predict/1rm/epley', methods=['POST'])
@limiter.limit("60 per hour")
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
@limiter.limit("60 per hour") # Assuming this is also an analytics-related endpoint for adjustment
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


@analytics_bp.route('/v1/users/<uuid:user_id>/plateau-notifications', methods=['GET'])
@jwt_required
@limiter.limit("60 per minute") # Standard rate limit
def get_plateau_notifications(user_id):
    user_id_str = str(user_id)

    # Authorization check
    if user_id_str != g.current_user_id:
        logger.warning(
            f"Forbidden attempt by user {g.current_user_id} to access plateau notifications for user {user_id_str}"
        )
        return jsonify(error="Forbidden. You can only access your own data."), 403

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            query = """
                SELECT
                    pe.id AS event_id,
                    e.name AS exercise_name,
                    pe.detected_at,
                    pe.details,
                    pe.protocol_applied,
                    pe.plateau_duration_days
                FROM plateau_events pe
                JOIN exercises e ON pe.exercise_id = e.id
                WHERE pe.user_id = %s
                  AND pe.acknowledged_at IS NULL
                ORDER BY pe.detected_at DESC;
            """
            cur.execute(query, (user_id_str,))
            notifications = cur.fetchall()

            # Convert datetime objects to ISO format strings for JSON compatibility
            for notification in notifications:
                if isinstance(notification.get('detected_at'), datetime): # Check if detected_at is a datetime object
                    notification['detected_at'] = notification['detected_at'].isoformat()

            return jsonify(notifications), 200

    except psycopg2.Error as e:
        logger.error(f"Database error fetching plateau notifications for user {user_id_str}: {e}", exc_info=True)
        return jsonify(error="Database operation failed while fetching notifications."), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching plateau notifications for user {user_id_str}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred while fetching notifications."), 500
    finally:
        if conn:
            release_db_connection(conn)


@analytics_bp.route('/v1/plateau-events/<uuid:event_id>/acknowledge', methods=['POST'])
@jwt_required
@limiter.limit("60 per minute")
def acknowledge_plateau_event(event_id):
    event_id_str = str(event_id)
    current_user_id = g.current_user_id

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur: # No RealDictCursor needed for UPDATE and rowcount
            update_query = """
                UPDATE plateau_events
                SET acknowledged_at = %s
                WHERE id = %s AND user_id = %s;
            """
            cur.execute(
                update_query,
                (datetime.now(timezone.utc), event_id_str, current_user_id)
            )

            if cur.rowcount == 0:
                # This means either the event_id doesn't exist or it doesn't belong to the user
                conn.rollback() # Rollback any potential transaction start
                logger.warning(f"Failed attempt to acknowledge plateau event {event_id_str} by user {current_user_id}. Event not found or not owned by user.")
                return jsonify(error="Plateau event not found or you do not have permission to acknowledge it."), 404

            conn.commit()
            logger.info(f"Plateau event {event_id_str} acknowledged by user {current_user_id}.")
            return jsonify({"message": "Notification acknowledged"}), 200

    except psycopg2.Error as e:
        logger.error(f"Database error acknowledging plateau event {event_id_str} for user {current_user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed."), 500
    except Exception as e:
        logger.error(f"Unexpected error acknowledging plateau event {event_id_str} for user {current_user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred."), 500
    finally:
        if conn:
            release_db_connection(conn)

@analytics_bp.route('/v1/user/<uuid:user_id>/fatigue-status', methods=['GET'])
@limiter.limit("60 per hour")
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

@analytics_bp.route('/v1/user/<uuid:user_id>/exercise/<uuid:exercise_id>/recommend-set-parameters', methods=['GET', 'POST']) # Added POST
@limiter.limit("60 per hour") # Recommendations might be called frequently during a workout
def recommend_set_parameters_route(user_id, exercise_id):
    user_id_str = str(user_id)
    exercise_id_str = str(exercise_id)

    previous_set_metrics = None
    if request.method == 'POST':
        request_data = request.get_json(silent=True) or {}
        previous_set_metrics = request_data.get('previous_set_metrics')
    # For GET requests, previous_set_metrics remains None, or could be read from query params if designed so.

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Fetch 'sex' and 'equipment_type' along with other user data
            cur.execute("SELECT goal_slider, rir_bias, recovery_multipliers, experience_level, equipment_settings, sex, equipment_type FROM users WHERE id = %s;", (user_id_str,))
            user_data_db = cur.fetchone()
            if not user_data_db:
                return jsonify(error="User not found"), 404

            goal_slider = float(user_data_db['goal_slider'])
            user_rir_bias = float(user_data_db.get('rir_bias', 0.0))
            user_experience_level = user_data_db.get('experience_level', 'intermediate').lower()
            recovery_multipliers_data = user_data_db.get('recovery_multipliers') or {}
            user_equipment_type = user_data_db.get('equipment_type', 'barbell').lower() # Get equipment_type

            equipment_settings = user_data_db.get('equipment_settings') # Still needed for plates/barbell weight
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

            # Fetch 1RM history, including source data for potential recalculation
            cur.execute(
                "SELECT estimated_1rm, source_weight, source_reps, source_rir "
                "FROM estimated_1rm_history "
                "WHERE user_id = %s AND exercise_id = %s "
                "ORDER BY calculated_at DESC LIMIT 1;",
                (user_id_str, exercise_id_str)
            )
            e1rm_data = cur.fetchone()

            estimated_1rm = None
            e1rm_source = "default" # Default e1rm_source before specific logic

            if e1rm_data:
                source_weight_val = e1rm_data.get('source_weight')
                source_reps_val = e1rm_data.get('source_reps')
                source_rir_val = e1rm_data.get('source_rir')

                if source_weight_val is not None and source_reps_val is not None and source_rir_val is not None:
                    try:
                        estimated_1rm = estimate_1rm_with_rir_bias(
                            float(source_weight_val),
                            int(source_reps_val),
                            int(source_rir_val),
                            user_rir_bias
                        )
                        e1rm_source = "history_recalculated_w_bias"
                    except ValueError: # Catch potential errors from int/float conversion if data is bad
                        estimated_1rm = float(e1rm_data['estimated_1rm'])
                        e1rm_source = "history_recalc_conversion_failed"
                    except Exception: # Catch any other error from estimate_1rm_with_rir_bias
                        estimated_1rm = float(e1rm_data['estimated_1rm'])
                        e1rm_source = "history_recalc_failed"
                else:
                    estimated_1rm = float(e1rm_data['estimated_1rm'])
                    e1rm_source = "history_no_source_for_bias"

            if estimated_1rm is None: # If no history, or if history processing failed to set estimated_1rm
                # Fallback to smart default logic
                exercise_key = exercise_name.lower().replace(' ', '_')
                used_other_category = False

                default_levels = EXERCISE_DEFAULT_1RM.get(exercise_key)
                if not default_levels: # Exercise name not directly in defaults
                    default_levels = EXERCISE_DEFAULT_1RM.get("other", {}) # Fallback to 'other'
                    e1rm_source = "other_category_default" # Initial source if 'other' is used
                    used_other_category = True

                if default_levels: # Either specific exercise or 'other' category defaults
                    estimated_1rm = default_levels.get(user_experience_level)
                    if estimated_1rm is not None:
                        if not used_other_category: # Specific exercise found
                           e1rm_source = f"{user_experience_level}_default_for_{exercise_key}"
                        else: # 'other' category used for this experience level
                           e1rm_source = f"{user_experience_level}_default_for_other_category"
                    else: # Experience level not in the chosen category, try 'intermediate'
                        estimated_1rm = default_levels.get('intermediate')
                        if estimated_1rm is not None:
                            if not used_other_category:
                                e1rm_source = f"intermediate_default_for_{exercise_key}"
                            else:
                                e1rm_source = "intermediate_default_for_other_category"
                        # If still None, it will hit the global fallback next.
                        # No need to set e1rm_source to "fallback_default_no_intermediate_match" here,
                        # as the next block handles it more globally.

                # Global fallback if no default found yet (neither specific, nor 'other', nor their intermediates)
                if estimated_1rm is None:
                    estimated_1rm = FALLBACK_DEFAULT_1RM
                    e1rm_source = "global_fallback_default" # More descriptive global fallback source

                # Apply sex multiplier if estimated_1rm was derived from defaults
                if "default" in e1rm_source: # Check if source indicates a default was used
                    user_sex = user_data_db.get('sex')
                    if user_sex and user_sex.lower() in SEX_MULTIPLIERS:
                        sex_multiplier = SEX_MULTIPLIERS[user_sex.lower()]
                    else: # Handles None, empty string, or values not in SEX_MULTIPLIERS explicitly
                        sex_multiplier = SEX_MULTIPLIERS['unknown']

                    if estimated_1rm is not None: # Ensure estimated_1rm is not None before multiplication
                        estimated_1rm *= sex_multiplier
                        e1rm_source += f"_sex_adj_{user_sex or 'unknown'}" # Updated source string

            # Plateau Detection & Deload Logic
            plateau_analysis_details = {'plateau_detected': False, 'deload_applied': False}
            MIN_HISTORY_FOR_PLATEAU_CHECK = 5 # Need at least this many records to check for a plateau
            PLATEAU_CHECK_WINDOW = 15 # Look at the last N records for plateau

            cur.execute(
                "SELECT estimated_1rm FROM estimated_1rm_history "
                "WHERE user_id = %s AND exercise_id = %s "
                "ORDER BY calculated_at ASC LIMIT %s;", # Oldest first for detect_plateau
                (user_id_str, exercise_id_str, PLATEAU_CHECK_WINDOW)
            )
            e1rm_history_for_plateau = cur.fetchall()

            if len(e1rm_history_for_plateau) >= MIN_HISTORY_FOR_PLATEAU_CHECK:
                e1rm_values = [float(r['estimated_1rm']) for r in e1rm_history_for_plateau]
                # Using min_duration=3 for plateau detection as per requirement
                plateau_status = detect_plateau(e1rm_values, min_duration=3)

                plateau_analysis_details.update({
                    'plateau_detected': plateau_status['plateauing'],
                    'status': plateau_status['status'].value if plateau_status.get('status') else None,
                    'slope': plateau_status.get('slope'),
                    'duration_evaluated': plateau_status.get('duration') # Duration from detect_plateau
                })

                # Requirement: "If plateau = True for >= 3 sessions"
                # detect_plateau's 'duration' is the number of points confirming the trend.
                # If min_duration=3 is used in detect_plateau, then plateau_status['plateauing'] being True implies this.
                if plateau_status['plateauing']: # Relies on min_duration=3 in detect_plateau call
                    if estimated_1rm is not None: # Ensure there's an e1RM to adjust
                        original_e1rm_before_deload = estimated_1rm
                        estimated_1rm *= 0.90 # Apply 10% deload to e1RM
                        plateau_analysis_details['deload_applied'] = True
                        plateau_analysis_details['original_e1rm'] = original_e1rm_before_deload
                        plateau_analysis_details['deloaded_e1rm'] = estimated_1rm
                        e1rm_source += "_plateau_deload"

                        # --- BEGIN: Insert plateau event if deload was applied ---
                        if plateau_analysis_details.get('deload_applied'):
                            try:
                                # Check for recent, unacknowledged plateau events for this user/exercise
                                cutoff_date = datetime.now(timezone.utc) - timedelta(weeks=PLATEAU_EVENT_NOTIFICATION_COOLDOWN_WEEKS)

                                cur.execute(
                                    """
                                    SELECT id FROM plateau_events
                                    WHERE user_id = %s AND exercise_id = %s
                                      AND acknowledged_at IS NULL
                                      AND detected_at >= %s
                                    ORDER BY detected_at DESC LIMIT 1;
                                    """,
                                    (user_id_str, exercise_id_str, cutoff_date)
                                )
                                existing_event = cur.fetchone()

                                if not existing_event:
                                    plateau_duration_value = plateau_status.get('duration') # This is likely in sessions
                                    details_message = (
                                        f"Plateau detected on {exercise_name}. Applied 10% e1RM reduction. "
                                        f"Plateau confirmed over {plateau_duration_value} prior data points/sessions."
                                    )

                                    cur.execute(
                                        """
                                        INSERT INTO plateau_events (
                                            user_id, exercise_id, detected_at,
                                            plateau_duration_days, protocol_applied, details, acknowledged_at
                                        )
                                        VALUES (%s, %s, %s, %s, %s, %s, NULL);
                                        """,
                                        (
                                            user_id_str,
                                            exercise_id_str,
                                            datetime.now(timezone.utc), # Let DB handle default if possible, else use this
                                            plateau_duration_value, # Storing session count here
                                            "auto_deload_10_percent",
                                            details_message
                                        )
                                    )
                                    logger.info(f"Inserted new plateau event for user {user_id_str}, exercise {exercise_id_str} due to auto-deload.")
                                    # conn.commit() should happen outside this specific block, at the end of the main try block normally
                            except psycopg2.Error as db_err:
                                logger.error(f"Database error during plateau event logging for user {user_id_str}, exercise {exercise_id_str}: {db_err}")
                                # Do not re-raise or rollback here, let the main handler do it.
                            except Exception as e_plat_event:
                                logger.error(f"Unexpected error during plateau event logging for user {user_id_str}, exercise {exercise_id_str}: {e_plat_event}", exc_info=True)
                        # --- END: Insert plateau event ---
                    else: # estimated_1rm is None, cannot apply deload
                        plateau_analysis_details['deload_applied'] = False
                        plateau_analysis_details['reason_no_deload'] = "e1RM was None initially"
            else: # Insufficient history for plateau check
                plateau_analysis_details['reason_no_plateau_check'] = "Insufficient history"

            # Mesocycle Phase Adjustment (applied to e1RM after plateau, before goal % and fatigue)
            today = date.today()
            meso_details_dict = get_or_create_current_mesocycle(cur, user_id_str, today)
            current_phase = meso_details_dict['phase']
            current_meso_week = meso_details_dict['week_number']

            load_modifier = 1.0
            meso_source_append = ""
            if current_phase == PHASE_INTENSIFICATION:
                load_modifier = 1.02
                meso_source_append = "_meso_intensification"
            elif current_phase == PHASE_DELOAD:
                load_modifier = 0.90
                meso_source_append = "_meso_deload"
            # else accumulation, load_modifier = 1.0, no source change needed unless explicitly desired

            if estimated_1rm is not None and load_modifier != 1.0:
                estimated_1rm *= load_modifier
                e1rm_source += meso_source_append

            response_mesocycle_details = {
                "phase": current_phase,
                "week_in_phase": current_meso_week,
                "load_modifier_applied": load_modifier,
                "mesocycle_id": meso_details_dict.get('id') # Pass ID for reference
            }

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

            # Intra-session adaptation logic
            intra_session_adjustment_info = {"type": "none", "original_calculated_weight": round(base_recommended_weight,2)}

            if previous_set_metrics:
                prev_actual_rir = previous_set_metrics.get('prev_actual_rir')
                prev_target_rir = previous_set_metrics.get('prev_target_rir')
                prev_weight_lifted = previous_set_metrics.get('prev_weight_lifted')

                if prev_actual_rir is not None and prev_target_rir is not None and prev_weight_lifted is not None:
                    try:
                        prev_actual_rir = int(prev_actual_rir)
                        prev_target_rir = int(prev_target_rir)
                        prev_weight_lifted = float(prev_weight_lifted)

                        # The weight to adjust is the one from the previous set
                        adjusted_weight_from_prev = adjust_next_set(
                            prev_actual_rir, prev_target_rir, prev_weight_lifted
                        )

                        adjustment_type = "none"
                        if adjusted_weight_from_prev < prev_weight_lifted:
                            adjustment_type = "decreased"
                        elif adjusted_weight_from_prev > prev_weight_lifted:
                            adjustment_type = "increased"

                        intra_session_adjustment_info = {
                            "type": adjustment_type,
                            "from_weight": prev_weight_lifted,
                            "to_weight_before_fatigue": adjusted_weight_from_prev,
                            "adjustment_applied_to_base": True
                        }
                        # This adjusted weight becomes the new "base" before fatigue, effectively overriding e1RM based calculation for this set
                        base_recommended_weight = adjusted_weight_from_prev
                        e1rm_source += "_intra_adjusted" # Append to source

                    except ValueError:
                        logger.warning(f"Invalid previous_set_metrics format for user {user_id_str}, exercise {exercise_id_str}")
                        intra_session_adjustment_info["error"] = "Invalid metric types"


            fatigue_reduction_per_10_points = 0.01
            fatigue_points_for_reduction = 10.0
            # Ensure current_fatigue is float for division
            fatigue_adjustment_factor = (float(current_fatigue) / fatigue_points_for_reduction) * fatigue_reduction_per_10_points
            fatigue_adjustment_factor = min(fatigue_adjustment_factor, 0.10)

            weight_reduction_due_to_fatigue = base_recommended_weight * fatigue_adjustment_factor
            adjusted_weight = base_recommended_weight - weight_reduction_due_to_fatigue
            intra_session_adjustment_info["weight_after_fatigue"] = round(adjusted_weight,2)


            final_rounded_weight = round_to_available_plates(
                target_weight_kg=adjusted_weight,
                available_plates_kg=user_available_plates,
                barbell_weight_kg=user_barbell_weight,
                equipment_type=user_equipment_type # Pass equipment_type
            )

            goal_slider_desc = "hypertrophy" if goal_slider < 0.34 else "strength" if goal_slider > 0.66 else "blend"
            explanation = (
                f"Est. 1RM ({e1rm_source}): {estimated_1rm:.1f}kg. "
                f"Goal ('{goal_slider_desc}', slider: {goal_slider:.2f}): target {load_percentage_of_1rm*100:.0f}% of 1RM. "
                f"Base weight: {base_recommended_weight:.1f}kg (after potential intra-session adj.). "
                f"Fatigue on '{main_target_muscle_group}' ({current_fatigue:.1f} pts): applied -{weight_reduction_due_to_fatigue:.1f}kg reduction. "
            )

            if intra_session_adjustment_info["type"] != "none":
                explanation += (
                    f"Intra-session adjustment: {intra_session_adjustment_info['type']} "
                    f"from {intra_session_adjustment_info.get('from_weight', 'N/A'):.1f}kg "
                    f"to {intra_session_adjustment_info.get('to_weight_before_fatigue', 'N/A'):.1f}kg (before fatigue). "
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
                "system_target_actual_rir": system_actual_target_rir,
                "user_rir_bias_applied": round(user_rir_bias, 2),
                "confidence_score": confidence_score,
                "intra_session_adjustment_details": intra_session_adjustment_info,
                "plateau_analysis_details": plateau_analysis_details,
                "mesocycle_details": response_mesocycle_details, # Added mesocycle details
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
@limiter.limit("5 per day") # Very strict limit for a system-level trigger
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
        job = tasks.enqueue_nightly_user_model_update(
            task_name=task_name,
            force_run=force_run,
        )
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
@limiter.limit("60 per hour")
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


@analytics_bp.route('/v1/users/<uuid:user_id>/exercises/<uuid:exercise_id>/analytics/mti-trends', methods=['GET'])
@jwt_required
@limiter.limit("60 per hour")
def get_mti_trends(user_id, exercise_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        logger.warning(f"Forbidden attempt by user {g.current_user_id} to access MTI trends for user {user_id}.")
        return jsonify(error="Forbidden. You can only access your own MTI data."), 403

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Optional: Check if exercise exists, though the query will just return empty if not.
            # cur.execute("SELECT id FROM exercises WHERE id = %s;", (str(exercise_id),))
            # if not cur.fetchone():
            #     return jsonify(error=f"Exercise with ID {exercise_id} not found."), 404

            # Fetch MTI data for the user and exercise
            cur.execute(
                """
                SELECT ws.completed_at, ws.mti
                FROM workout_sets ws
                JOIN workouts w ON ws.workout_id = w.id
                WHERE w.user_id = %s AND ws.exercise_id = %s AND ws.mti IS NOT NULL
                ORDER BY ws.completed_at ASC;
                """,
                (str(user_id), str(exercise_id))
            )
            records = cur.fetchall()

            if not records:
                # Return an empty list as per frontend expectation for chart data
                return jsonify([]), 200

            mti_trends_data = [
                {
                    "date": rec["completed_at"].isoformat(), # Ensure ISO format for dates
                    "mti_score": int(rec["mti"]) # MTI is already stored as INTEGER
                }
                for rec in records
            ]

            return jsonify(mti_trends_data), 200

    except psycopg2.Error as e:
        logger.error(f"Database error fetching MTI trends for user {user_id}, exercise {exercise_id}: {e}", exc_info=True)
        return jsonify(error="Database error while fetching MTI trends."), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching MTI trends for user {user_id}, exercise {exercise_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred while fetching MTI trends."), 500
    finally:
        if conn:
            release_db_connection(conn)
@analytics_bp.route('/v1/users/<uuid:user_id>/analytics/1rm-evolution', methods=['GET'])
@jwt_required
@limiter.limit("60 per hour")
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
@limiter.limit("60 per hour")
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
@limiter.limit("60 per hour")
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


@analytics_bp.route('/v1/user/<uuid:user_id>/volume-summary', methods=['GET'])
@jwt_required
@limiter.limit("60 per hour")
def get_volume_summary(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        logger.warning(
            f"Forbidden attempt to access volume summary for user {user_id} by user {g.current_user_id}"
        )
        return jsonify(error="Forbidden. You can only access your own data."), 403

    iso_week = request.args.get('week')
    week_start = None
    if iso_week:
        try:
            week_start = datetime.fromisoformat(iso_week).date()
        except ValueError:
            return jsonify(error="Invalid week format. Use ISO date YYYY-MM-DD"), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if week_start:
                cur.execute(
                    "SELECT muscle_group, total_volume FROM volume_summaries WHERE user_id = %s AND week = %s;",
                    (str(user_id), week_start),
                )
                rows = cur.fetchall()
                if not rows:
                    cur.execute(
                        """
                        SELECT e.main_target_muscle_group, SUM(ws.actual_weight * ws.actual_reps) AS volume
                        FROM workout_sets ws
                        JOIN workouts w ON ws.workout_id = w.id
                        JOIN exercises e ON ws.exercise_id = e.id
                        WHERE w.user_id = %s
                          AND ws.completed_at >= %s
                          AND ws.completed_at < %s + INTERVAL '7 days'
                          AND ws.actual_weight IS NOT NULL
                          AND ws.actual_reps IS NOT NULL
                        GROUP BY e.main_target_muscle_group;
                        """,
                        (str(user_id), week_start, week_start),
                    )
                    rows = cur.fetchall()
                summary = [
                    {
                        "muscle_group": r.get("muscle_group") or r.get("main_target_muscle_group"),
                        "volume": float(r["total_volume"] if "total_volume" in r else r["volume"] or 0),
                    }
                    for r in rows
                ]
                return jsonify({"week": iso_week, "data": summary}), 200
            else:
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
                    ORDER BY week DESC
                    LIMIT 50;
                    """,
                    (str(user_id),),
                )
                rows = cur.fetchall()
                summary = [
                    {
                        "week": r["week"].date().isoformat(),
                        "muscle_group": r["muscle_group"],
                        "volume": float(r["volume"] or 0),
                    }
                    for r in rows
                ]
                return jsonify(summary), 200
    except psycopg2.Error as e:
        logger.error(f"Database error during volume summary fetch for user {user_id}: {e}")
        return jsonify(error="Database error during analytics fetch."), 500
    finally:
        if conn:
            release_db_connection(conn)


@analytics_bp.route('/v1/user/<uuid:user_id>/mti-history', methods=['GET'])
@jwt_required
@limiter.limit("60 per hour")
def get_mti_history(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        logger.warning(
            f"Forbidden attempt to access MTI history for user {user_id} by user {g.current_user_id}"
        )
        return jsonify(error="Forbidden. You can only access your own data."), 403

    exercise_id = request.args.get('exercise')
    days_range = request.args.get('range', '30')
    if not exercise_id:
        return jsonify(error="Missing 'exercise' query parameter"), 400
    try:
        days_range = int(days_range)
    except ValueError:
        return jsonify(error="Invalid 'range' query parameter"), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT ws.completed_at, ws.mti
                FROM workout_sets ws
                JOIN workouts w ON ws.workout_id = w.id
                WHERE w.user_id = %s
                  AND ws.exercise_id = %s
                  AND ws.mti IS NOT NULL
                  AND ws.completed_at >= NOW() - INTERVAL '%s days'
                ORDER BY ws.completed_at ASC;
                """,
                (str(user_id), exercise_id, days_range),
            )
            rows = cur.fetchall()
            history = [
                {"date": r["completed_at"].date().isoformat(), "mti": int(r["mti"])}
                for r in rows
            ]
        return jsonify(history), 200
    except psycopg2.Error as e:
        logger.error(f"Database error during MTI history fetch for user {user_id}: {e}")
        return jsonify(error="Database error during analytics fetch."), 500
    finally:
        if conn:
            release_db_connection(conn)

