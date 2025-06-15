from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import uuid
import math
import psycopg2
import psycopg2.extras
import engine.app as app

workouts_bp = Blueprint('workouts', __name__)


@workouts_bp.route('/v1/users/<uuid:user_id>/workouts', methods=['POST'])
@app.jwt_required
def create_workout(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        return jsonify(error="Forbidden. You can only create workouts for your own profile."), 403
    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400
    plan_day_id = data.get('plan_day_id')
    started_at = data.get('started_at')
    fatigue_level_reported = data.get('fatigue_level_reported')
    sleep_hours = data.get('sleep_hours')
    stress_level_reported = data.get('stress_level_reported')
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
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO workouts (id, user_id, plan_day_id, started_at,
                                      fatigue_level_reported, sleep_hours, stress_level_reported, notes,
                                      created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING *;
                """,
                (workout_id, str(user_id), plan_day_id, started_at_dt,
                 fatigue_level_reported, sleep_hours, stress_level_reported, notes)
            )
            new_workout = cur.fetchone()
            conn.commit()
            app.logger.info(f"Workout created successfully (ID: {workout_id}) for user: {user_id}")
            return jsonify(new_workout), 201
    except psycopg2.Error as e:
        app.logger.error(f"Database error creating workout for user {user_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed creating workout"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error creating workout for user {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred creating workout"), 500
    finally:
        if conn:
            conn.close()


@workouts_bp.route('/v1/users/<uuid:user_id>/workouts', methods=['GET'])
@app.jwt_required
def get_workouts_for_user(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        return jsonify(error="Forbidden. You can only view your own workouts."), 403
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
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
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id = %s;", (str(user_id),))
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
        app.logger.error(f"Database error fetching workouts for user {user_id}: {e}")
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error fetching workouts for user {user_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            conn.close()


@workouts_bp.route('/v1/workouts/<uuid:workout_id>', methods=['GET'])
@app.jwt_required
def get_single_workout(workout_id):
    from flask import g
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT user_id FROM workouts WHERE id = %s;", (str(workout_id),))
            workout_owner = cur.fetchone()
            if not workout_owner:
                return jsonify(error="Workout not found"), 404
            if workout_owner['user_id'] != uuid.UUID(g.current_user_id):
                app.logger.warning(f"Forbidden attempt to access workout {workout_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You can only view your own workouts."), 403
            cur.execute("SELECT * FROM workouts WHERE id = %s;", (str(workout_id),))
            workout_details = cur.fetchone()
            cur.execute(
                """
                SELECT ws.*, e.name as exercise_name
                FROM workout_sets ws
                JOIN exercises e ON ws.exercise_id = e.id
                WHERE ws.workout_id = %s
                ORDER BY ws.set_number ASC;
                """,
                (str(workout_id),)
            )
            sets_list = cur.fetchall()
            workout_details['sets'] = sets_list
            return jsonify(workout_details), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error fetching workout {workout_id}: {e}")
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error fetching workout {workout_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            conn.close()


@workouts_bp.route('/v1/workouts/<uuid:workout_id>/sets', methods=['POST'])
@app.jwt_required
def log_set_to_workout(workout_id):
    from flask import g
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT user_id FROM workouts WHERE id = %s;", (str(workout_id),))
            workout_owner = cur.fetchone()
            if not workout_owner:
                return jsonify(error="Workout not found"), 404
            if workout_owner['user_id'] != uuid.UUID(g.current_user_id):
                app.logger.warning(f"Forbidden attempt to log set to workout {workout_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You can only add sets to your own workouts."), 403
            data = request.get_json()
            if not data:
                return jsonify(error="Request body must be JSON"), 400
            required_fields = ['exercise_id', 'set_number', 'actual_weight', 'actual_reps', 'actual_rir']
            for field in required_fields:
                if field not in data:
                    return jsonify(error=f"Missing required field: {field}"), 400
            try:
                exercise_id = str(uuid.UUID(data['exercise_id']))
                set_number = int(data['set_number'])
                actual_weight = float(data['actual_weight'])
                actual_reps = int(data['actual_reps'])
                actual_rir = int(data['actual_rir'])
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
            cur.execute(
                """
                INSERT INTO workout_sets (
                    id, workout_id, exercise_id, set_number,
                    actual_weight, actual_reps, actual_rir,
                    rest_before_seconds, completed_at, notes, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING *;
                """,
                (set_id, str(workout_id), exercise_id, set_number,
                 actual_weight, actual_reps, actual_rir,
                 rest_before_seconds, completed_at_dt, set_notes)
            )
            new_set = cur.fetchone()
            conn.commit()
            app.logger.info(f"Set {set_id} logged to workout {workout_id} successfully.")
            return jsonify(new_set), 201
    except psycopg2.Error as e:
        app.logger.error(f"Database error logging set to workout {workout_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed logging set"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error logging set to workout {workout_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred logging set"), 500
    finally:
        if conn:
            conn.close()
