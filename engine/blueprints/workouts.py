from flask import Blueprint, request, jsonify
from ..app import get_db_connection, release_db_connection, jwt_required, logger
import psycopg2
import psycopg2.extras
import uuid
import math
from datetime import datetime, timezone, date
from engine.predictions import calculate_mti, estimate_1rm_with_rir_bias
from engine.learning_models import update_user_rir_bias

workouts_bp = Blueprint('workouts', __name__)

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

            # 1. Fetch User's Current RIR Bias
            cur.execute("SELECT rir_bias FROM users WHERE id = %s FOR UPDATE;", (str(user_id),)) # Lock user row
            user_data = cur.fetchone()
            if not user_data:
                logger.error(f"User not found for ID: {user_id} during set logging.")
                conn.rollback() # Release lock
                return jsonify(error="User not found."), 404
            current_rir_bias = float(user_data['rir_bias'])

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

            # 4. Update RIR Bias
            new_rir_bias = update_user_rir_bias(current_rir_bias, predicted_reps_for_bias_update, reps)
            cur.execute(
                "UPDATE users SET rir_bias = %s, updated_at = NOW() WHERE id = %s;",
                (new_rir_bias, str(user_id))
            )
            logger.info(f"RIR bias for user {user_id} updated from {current_rir_bias:.2f} to {new_rir_bias:.2f} (predicted_reps: {predicted_reps_for_bias_update}, actual_reps: {reps}).")

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
            logger.info(f"Set {set_id} (workout: {workout_id_for_set}) logged for user {user_id}, ex {exercise_id}. MTI: {mti_score}, New 1RM: {new_estimated_1rm}, New RIR Bias: {new_rir_bias:.2f}")
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