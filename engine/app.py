from flask import Flask, request, jsonify
from predictions import extended_epley_1rm # Existing import
from engine.learning_models import ( # New imports
    update_user_rir_bias,
    calculate_current_fatigue,
    DEFAULT_RECOVERY_TAU_MAP,
    SessionRecord # Type alias for SessionRecord
)
import psycopg2
import psycopg2.extras # For RealDictCursor
import os
from datetime import datetime
import logging
import math # For rounding and calculations

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__) # Use app.logger or a specific logger

# --- Database Connection Helper ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "gymgenius_dev"),
            user=os.getenv("POSTGRES_USER", "gymgenius"),
            password=os.getenv("POSTGRES_PASSWORD", "secret"),
            host=os.getenv("POSTGRES_HOST", "db"),
            port=os.getenv("POSTGRES_PORT", "5432")
        )
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection error: {e}")
        raise


@app.errorhandler(Exception)
def handle_exception(e):
    """Generic exception handler."""
    # Log the exception with stack trace for debugging
    logger.error(f"Unhandled exception: {e}", exc_info=True)
    if isinstance(e, psycopg2.OperationalError):
        return jsonify(error="Database connection error"), 503
    # Add more specific error handlers if needed for different exception types
    return jsonify(error="An internal server error occurred"), 500


# --- Existing Endpoints ---
@app.route('/v1/predict/1rm/epley', methods=['POST'])
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

@app.route('/v1/user/<uuid:user_id>/update-rir-bias', methods=['POST'])
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
        if conn: conn.rollback()
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        logger.error(f"Unexpected error in update_rir_bias: {e}", exc_info=True)
        if conn: conn.rollback()
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            conn.close()

@app.route('/v1/user/<uuid:user_id>/fatigue-status', methods=['GET'])
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
            conn.close()

@app.route('/v1/user/<uuid:user_id>/exercise/<uuid:exercise_id>/recommend-set-parameters', methods=['GET'])
def recommend_set_parameters_route(user_id, exercise_id):
    user_id_str = str(user_id)
    exercise_id_str = str(exercise_id)

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT goal_slider, rir_bias, recovery_multipliers FROM users WHERE id = %s;", (user_id_str,))
            user_data_db = cur.fetchone() # Renamed
            if not user_data_db:
                return jsonify(error="User not found"), 404

            goal_slider = float(user_data_db['goal_slider'])
            recovery_multipliers_data = user_data_db.get('recovery_multipliers') or {} # Renamed

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
            estimated_1rm = 50.0
            e1rm_source = "default"
            if e1rm_data:
                estimated_1rm = float(e1rm_data['estimated_1rm'])
                e1rm_source = "history"

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
            target_rir_ideal_float = 2.5 - 1.5 * goal_slider
            target_rir_ideal = int(round(target_rir_ideal_float))

            rep_high_float = 6.0 + 6.0 * (1.0 - goal_slider)
            rep_high = int(round(rep_high_float))
            rep_low = int(round(max(1.0, rep_high_float - 4.0)))

            base_recommended_weight = estimated_1rm * load_percentage_of_1rm

            fatigue_reduction_per_10_points = 0.01
            fatigue_points_for_reduction = 10.0
            # Ensure current_fatigue is float for division
            fatigue_adjustment_factor = (float(current_fatigue) / fatigue_points_for_reduction) * fatigue_reduction_per_10_points
            fatigue_adjustment_factor = min(fatigue_adjustment_factor, 0.5)

            weight_reduction_due_to_fatigue = base_recommended_weight * fatigue_adjustment_factor
            adjusted_weight = base_recommended_weight - weight_reduction_due_to_fatigue
            final_rounded_weight = round(adjusted_weight * 2) / 2.0 # Ensure float division for 0.5 steps

            goal_slider_desc = "hypertrophy" if goal_slider < 0.34 else "strength" if goal_slider > 0.66 else "blend"
            explanation = (
                f"Est. 1RM ({e1rm_source}): {estimated_1rm:.1f}kg. "
                f"Goal ('{goal_slider_desc}', slider: {goal_slider:.2f}): target {load_percentage_of_1rm*100:.0f}% of 1RM. "
                f"Base weight: {base_recommended_weight:.1f}kg. "
                f"Fatigue on '{main_target_muscle_group}' ({current_fatigue:.1f} pts): applied -{weight_reduction_due_to_fatigue:.1f}kg reduction. "
                f"Final Recommendation: {final_rounded_weight:.1f}kg for {rep_low}-{rep_high} reps @ RIR ~{target_rir_ideal}."
            )

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
                "target_rir": target_rir_ideal,
                "explanation": explanation
            }), 200

    except psycopg2.Error as e:
        logger.error(f"Database error in recommend_set_parameters: {e}")
        if conn: conn.rollback()
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        logger.error(f"Unexpected error in recommend_set_parameters: {e}", exc_info=True)
        if conn: conn.rollback()
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            conn.close()

# --- New Webhook Endpoint for Training Pipeline ---
@app.route('/v1/system/trigger-training-pipeline', methods=['POST'])
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

    conn = None
    users_processed_count = 0
    processed_user_ids = []

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, email FROM users;") # Fetch id and email for logging
            all_users = cur.fetchall()

        users_processed_count = len(all_users)

        # Conceptual Asynchronous Behavior:
        # In a production scenario, the following loop would be offloaded to a
        # background task queue (e.g., Celery, RQ, or cloud functions)
        # to avoid blocking the HTTP request for a long time.
        logger.info("--- Starting Simulated Nightly Training Tasks ---")
        for user in all_users:
            user_id = str(user['id'])
            user_email = user['email'] # For more informative logging
            # Simulate per-user training tasks
            logger.info(f"Simulating training tasks for user_id: {user_id} (Email: {user_email})...")
            # Example: Fetch some data for the user to simulate work
            # with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as user_task_cur:
            #    user_task_cur.execute("SELECT goal_slider FROM users WHERE id = %s;", (user_id,))
            #    user_specific_data = user_task_cur.fetchone()
            #    logger.info(f"  User {user_id} goal_slider: {user_specific_data.get('goal_slider') if user_specific_data else 'N/A'}")
            processed_user_ids.append(user_id)
        logger.info("--- Finished Simulated Nightly Training Tasks ---")

        return jsonify({
            "message": "Training pipeline triggered successfully (simulated).",
            "users_processed_count": users_processed_count,
            # "processed_user_ids": processed_user_ids, # Optional: for more detailed response
            "task_details": {
                "task_name": task_name,
                "force_run": force_run,
                "simulated_action": "Logged per-user training triggers."
            }
        }), 200

    except psycopg2.Error as e:
        logger.error(f"Database error during training pipeline trigger: {e}")
        return jsonify(error="Database operation failed during pipeline trigger"), 500
    except Exception as e:
        logger.error(f"Unexpected error during training pipeline trigger: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred during pipeline trigger"), 500
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    _conn_check = None
    try:
        _conn_check = get_db_connection()
        with _conn_check.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as _cur:
            _cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='exercises' AND column_name='main_target_muscle_group';
            """)
            if not _cur.fetchone():
                logger.warning("WARNING: The 'exercises' table does not seem to have the "
                               "'main_target_muscle_group' column assumed by some endpoints. "
                               "These endpoints may not function correctly for session history.")
    except Exception as _e:
        # Log a more general warning if DB connection itself fails here for the check
        logger.warning(f"Could not perform initial schema check for 'main_target_muscle_group' column (DB might not be ready or accessible for this check): {_e}")
    finally:
        if _conn_check:
            _conn_check.close()

    app.run(host='0.0.0.0', port=5000, debug=True)

```
