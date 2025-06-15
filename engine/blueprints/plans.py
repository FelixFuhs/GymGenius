from flask import Blueprint, request, jsonify
import uuid
import psycopg2
import psycopg2.extras
import engine.app as app

plans_bp = Blueprint('plans', __name__)


@plans_bp.route('/v1/users/<uuid:user_id>/plans', methods=['POST'])
@app.jwt_required
def create_workout_plan(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        app.logger.warning(f"Forbidden attempt to create plan for user {user_id} by user {g.current_user_id}")
        return jsonify(error="Forbidden. You can only create plans for your own profile."), 403
    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400
    plan_name = data.get('name')
    if not plan_name:
        return jsonify(error="Missing required field: name"), 400
    days_per_week = data.get('days_per_week')
    plan_length_weeks = data.get('plan_length_weeks')
    goal_focus = data.get('goal_focus')
    if days_per_week is not None:
        try:
            days_per_week = int(days_per_week)
            if not (1 <= days_per_week <= 7):
                raise ValueError("Days per week must be between 1 and 7.")
        except ValueError as e:
            return jsonify(error=f"Invalid 'days_per_week': {e}"), 400
    if plan_length_weeks is not None:
        try:
            plan_length_weeks = int(plan_length_weeks)
            if plan_length_weeks < 1:
                raise ValueError("Plan length must be at least 1 week.")
        except ValueError as e:
            return jsonify(error=f"Invalid 'plan_length_weeks': {e}"), 400
    plan_id = str(uuid.uuid4())
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO workout_plans (id, user_id, name, days_per_week, plan_length_weeks, goal_focus, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING *;
                """,
                (plan_id, str(user_id), plan_name, days_per_week, plan_length_weeks, goal_focus)
            )
            new_plan = cur.fetchone()
            conn.commit()
            app.logger.info(f"Workout plan '{plan_name}' (ID: {plan_id}) created successfully for user: {user_id}")
            return jsonify(new_plan), 201
    except psycopg2.Error as e:
        app.logger.error(f"Database error creating workout plan for user {user_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed creating workout plan"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error creating workout plan for user {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred creating workout plan"), 500
    finally:
        if conn:
            conn.close()


@plans_bp.route('/v1/users/<uuid:user_id>/plans', methods=['GET'])
@app.jwt_required
def get_workout_plans_for_user(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        app.logger.warning(f"Forbidden attempt to get plans for user {user_id} by user {g.current_user_id}")
        return jsonify(error="Forbidden. You can only view your own plans."), 403
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM workout_plans WHERE user_id = %s ORDER BY created_at DESC;",
                (str(user_id),)
            )
            plans_list = cur.fetchall()
            return jsonify(plans_list), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error fetching workout plans for user {user_id}: {e}")
        return jsonify(error="Database operation failed fetching workout plans"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error fetching workout plans for user {user_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred fetching workout plans"), 500
    finally:
        if conn:
            conn.close()


@plans_bp.route('/v1/plans/<uuid:plan_id>', methods=['GET'])
@app.jwt_required
def get_workout_plan_details(plan_id):
    from flask import g
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM workout_plans WHERE id = %s;", (str(plan_id),))
            plan = cur.fetchone()
            if not plan:
                return jsonify(error="Workout plan not found"), 404
            if plan['user_id'] != uuid.UUID(g.current_user_id):
                app.logger.warning(f"Forbidden attempt to access plan {plan_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own this plan."), 403
            cur.execute(
                "SELECT * FROM plan_days WHERE plan_id = %s ORDER BY day_number ASC;",
                (str(plan_id),)
            )
            plan_days = cur.fetchall()
            for day in plan_days:
                cur.execute(
                    """
                    SELECT pe.*, e.name as exercise_name
                    FROM plan_exercises pe
                    JOIN exercises e ON pe.exercise_id = e.id
                    WHERE pe.plan_day_id = %s
                    ORDER BY pe.order_index ASC;
                    """,
                    (str(day['id']),)
                )
                day['exercises'] = cur.fetchall()
            plan['days'] = plan_days
            return jsonify(plan), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error fetching details for plan {plan_id}: {e}")
        return jsonify(error="Database operation failed fetching plan details"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error fetching details for plan {plan_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred fetching plan details"), 500
    finally:
        if conn:
            conn.close()


@plans_bp.route('/v1/plans/<uuid:plan_id>', methods=['PUT'])
@app.jwt_required
def update_workout_plan(plan_id):
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT user_id FROM workout_plans WHERE id = %s;", (str(plan_id),))
            plan_owner = cur.fetchone()
            if not plan_owner:
                return jsonify(error="Workout plan not found"), 404
            if plan_owner['user_id'] != uuid.UUID(g.current_user_id):
                app.logger.warning(f"Forbidden attempt to update plan {plan_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own this plan."), 403
            allowed_fields = {
                'name': str,
                'days_per_week': int,
                'plan_length_weeks': int,
                'goal_focus': str,
                'is_active': bool
            }
            update_fields_parts = []
            update_values = []
            for field, field_type in allowed_fields.items():
                if field in data:
                    value = data[field]
                    if value is not None:
                        if field_type is int and isinstance(value, float) and value.is_integer():
                            value = int(value)
                        elif not isinstance(value, field_type):
                            return jsonify(error=f"Invalid type for field '{field}'. Expected {field_type.__name__}."), 400
                    if field == 'days_per_week' and value is not None and not (1 <= value <= 7):
                        return jsonify(error="'days_per_week' must be between 1 and 7"), 400
                    if field == 'plan_length_weeks' and value is not None and value < 0:
                        return jsonify(error="'plan_length_weeks' must be non-negative"), 400
                    update_fields_parts.append(f"{field} = %s")
                    update_values.append(value)
            if not update_fields_parts:
                return jsonify(error="No valid fields provided for update"), 400
            update_fields_parts.append("updated_at = NOW()")
            query = f"UPDATE workout_plans SET {', '.join(update_fields_parts)} WHERE id = %s RETURNING *;"
            update_values.append(str(plan_id))
            cur.execute(query, tuple(update_values))
            updated_plan = cur.fetchone()
            conn.commit()
            app.logger.info(f"Workout plan {plan_id} updated successfully by user {g.current_user_id}")
            return jsonify(updated_plan), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error updating plan {plan_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed updating plan"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error updating plan {plan_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred updating plan"), 500
    finally:
        if conn:
            conn.close()


@plans_bp.route('/v1/plans/<uuid:plan_id>', methods=['DELETE'])
@app.jwt_required
def delete_workout_plan(plan_id):
    from flask import g
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT user_id FROM workout_plans WHERE id = %s;", (str(plan_id),))
            plan_owner = cur.fetchone()
            if not plan_owner:
                return jsonify(error="Workout plan not found"), 404
            if plan_owner['user_id'] != uuid.UUID(g.current_user_id):
                app.logger.warning(f"Forbidden attempt to delete plan {plan_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own this plan."), 403
            cur.execute("DELETE FROM workout_plans WHERE id = %s;", (str(plan_id),))
            conn.commit()
            if cur.rowcount == 0:
                app.logger.error(f"Failed to delete plan {plan_id}, though ownership was verified. Plan might have been deleted by another process.")
                return jsonify(error="Failed to delete plan, it might have already been deleted."), 404
            app.logger.info(f"Workout plan {plan_id} deleted successfully by user {g.current_user_id}")
            return '', 204
    except psycopg2.Error as e:
        app.logger.error(f"Database error deleting plan {plan_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed deleting plan"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error deleting plan {plan_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred deleting plan"), 500
    finally:
        if conn:
            conn.close()


@plans_bp.route('/v1/plans/<uuid:plan_id>/days', methods=['POST'])
@app.jwt_required
def create_plan_day(plan_id):
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400
    day_number = data.get('day_number')
    if day_number is None:
        return jsonify(error="Missing required field: day_number"), 400
    try:
        day_number = int(day_number)
        if day_number < 0:
            raise ValueError("day_number must be a non-negative integer.")
    except ValueError as e:
        return jsonify(error=f"Invalid 'day_number': {e}"), 400
    day_name = data.get('name')
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT user_id FROM workout_plans WHERE id = %s;", (str(plan_id),))
            plan_owner = cur.fetchone()
            if not plan_owner:
                return jsonify(error="Parent workout plan not found"), 404
            if plan_owner['user_id'] != uuid.UUID(g.current_user_id):
                app.logger.warning(f"Forbidden attempt to add day to plan {plan_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own this plan."), 403
            cur.execute("SELECT id FROM plan_days WHERE plan_id = %s AND day_number = %s;", (str(plan_id), day_number))
            if cur.fetchone():
                return jsonify(error=f"A day with day_number {day_number} already exists for this plan."), 409
            plan_day_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO plan_days (id, plan_id, day_number, name, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                RETURNING *;
                """,
                (plan_day_id, str(plan_id), day_number, day_name)
            )
            new_plan_day = cur.fetchone()
            conn.commit()
            app.logger.info(f"Plan day {plan_day_id} (Day {day_number}) created for plan {plan_id} by user {g.current_user_id}")
            return jsonify(new_plan_day), 201
    except psycopg2.Error as e:
        app.logger.error(f"Database error creating plan day for plan {plan_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed creating plan day"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error creating plan day for plan {plan_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred creating plan day"), 500
    finally:
        if conn:
            conn.close()


@plans_bp.route('/v1/plans/<uuid:plan_id>/days', methods=['GET'])
@app.jwt_required
def get_plan_days(plan_id):
    from flask import g
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT user_id FROM workout_plans WHERE id = %s;", (str(plan_id),))
            plan_owner = cur.fetchone()
            if not plan_owner:
                return jsonify(error="Parent workout plan not found"), 404
            if plan_owner['user_id'] != uuid.UUID(g.current_user_id):
                app.logger.warning(f"Forbidden attempt to get days for plan {plan_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own this plan."), 403
            cur.execute(
                "SELECT * FROM plan_days WHERE plan_id = %s ORDER BY day_number ASC;",
                (str(plan_id),)
            )
            plan_days_list = cur.fetchall()
            return jsonify(plan_days_list), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error fetching plan days for plan {plan_id}: {e}")
        return jsonify(error="Database operation failed fetching plan days"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error fetching plan days for plan {plan_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred fetching plan days"), 500
    finally:
        if conn:
            conn.close()


@plans_bp.route('/v1/plandays/<uuid:day_id>', methods=['PUT'])
@app.jwt_required
def update_plan_day(day_id):
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT pd.id AS plan_day_id, pd.plan_id, wp.user_id AS plan_owner_id
                FROM plan_days pd
                JOIN workout_plans wp ON pd.plan_id = wp.id
                WHERE pd.id = %s;
                """,
                (str(day_id),)
            )
            day_info = cur.fetchone()
            if not day_info:
                return jsonify(error="Plan day not found"), 404
            if day_info['plan_owner_id'] != uuid.UUID(g.current_user_id):
                app.logger.warning(f"Forbidden attempt to update plan day {day_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own the parent plan of this day."), 403
            allowed_fields = {'name': str, 'day_number': int}
            update_fields_parts = []
            update_values = []
            if 'day_number' in data:
                try:
                    day_number = int(data['day_number'])
                    if day_number < 0:
                        raise ValueError("day_number must be a non-negative integer.")
                    cur.execute(
                        "SELECT id FROM plan_days WHERE plan_id = %s AND day_number = %s AND id != %s;",
                        (day_info['plan_id'], day_number, str(day_id))
                    )
                    if cur.fetchone():
                        return jsonify(error=f"A day with day_number {day_number} already exists for this plan."), 409
                    update_fields_parts.append("day_number = %s")
                    update_values.append(day_number)
                except ValueError as e:
                    return jsonify(error=f"Invalid 'day_number': {e}"), 400
            if 'name' in data:
                name = data['name']
                if name is not None and not isinstance(name, str):
                    return jsonify(error="Invalid type for field 'name'. Expected string or null."), 400
                update_fields_parts.append("name = %s")
                update_values.append(name)
            if not update_fields_parts:
                return jsonify(error="No valid fields provided for update"), 400
            update_fields_parts.append("updated_at = NOW()")
            query = f"UPDATE plan_days SET {', '.join(update_fields_parts)} WHERE id = %s RETURNING *;"
            update_values.append(str(day_id))
            cur.execute(query, tuple(update_values))
            updated_plan_day = cur.fetchone()
            conn.commit()
            app.logger.info(f"Plan day {day_id} updated successfully by user {g.current_user_id}")
            return jsonify(updated_plan_day), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error updating plan day {day_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed updating plan day"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error updating plan day {day_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred updating plan day"), 500
    finally:
        if conn:
            conn.close()


@plans_bp.route('/v1/plandays/<uuid:day_id>', methods=['DELETE'])
@app.jwt_required
def delete_plan_day(day_id):
    from flask import g
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT wp.user_id AS plan_owner_id
                FROM plan_days pd
                JOIN workout_plans wp ON pd.plan_id = wp.id
                WHERE pd.id = %s;
                """,
                (str(day_id),)
            )
            day_info = cur.fetchone()
            if not day_info:
                return jsonify(error="Plan day not found"), 404
            if day_info['plan_owner_id'] != uuid.UUID(g.current_user_id):
                app.logger.warning(f"Forbidden attempt to delete plan day {day_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own the parent plan of this day."), 403
            cur.execute("DELETE FROM plan_days WHERE id = %s;", (str(day_id),))
            conn.commit()
            if cur.rowcount == 0:
                app.logger.error(f"Failed to delete plan day {day_id}, though ownership was verified. Day might have been deleted by another process.")
                return jsonify(error="Failed to delete plan day, it might have already been deleted."), 404
            app.logger.info(f"Plan day {day_id} deleted successfully by user {g.current_user_id}")
            return '', 204
    except psycopg2.Error as e:
        app.logger.error(f"Database error deleting plan day {day_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed deleting plan day"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error deleting plan day {day_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred deleting plan day"), 500
    finally:
        if conn:
            conn.close()


@plans_bp.route('/v1/plandays/<uuid:day_id>/exercises', methods=['POST'])
@app.jwt_required
def create_plan_exercise(day_id):
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400
    required_fields = ['exercise_id', 'order_index', 'sets']
    for field in required_fields:
        if field not in data:
            return jsonify(error=f"Missing required field: {field}"), 400
    try:
        exercise_id = str(uuid.UUID(data['exercise_id']))
        order_index = int(data['order_index'])
        sets = int(data['sets'])
        if order_index < 0:
            raise ValueError("'order_index' must be non-negative.")
        if sets < 1:
            raise ValueError("'sets' must be at least 1.")
    except (ValueError, TypeError) as e:
        return jsonify(error=f"Invalid data type or value for required fields: {e}"), 400
    optional_fields_spec = {
        'rep_range_low': int,
        'rep_range_high': int,
        'target_rir': int,
        'rest_seconds': int,
        'notes': str
    }
    plan_exercise_data = {}
    for field, field_type in optional_fields_spec.items():
        if field in data:
            value = data[field]
            if value is not None:
                try:
                    typed_value = field_type(value)
                    if field_type is int and typed_value < 0 and field not in ['target_rir']:
                        raise ValueError(f"'{field}' must be non-negative.")
                    plan_exercise_data[field] = typed_value
                except ValueError as e:
                    return jsonify(error=f"Invalid value for field '{field}': {e}"), 400
            else:
                plan_exercise_data[field] = None
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT wp.user_id AS plan_owner_id
                FROM plan_days pd
                JOIN workout_plans wp ON pd.plan_id = wp.id
                WHERE pd.id = %s;
                """,
                (str(day_id),)
            )
            owner_info = cur.fetchone()
            if not owner_info:
                return jsonify(error="Parent plan day not found"), 404
            if owner_info['plan_owner_id'] != uuid.UUID(g.current_user_id):
                app.logger.warning(f"Forbidden attempt to add exercise to day {day_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own the parent plan of this day."), 403
            cur.execute("SELECT id FROM exercises WHERE id = %s;", (exercise_id,))
            if not cur.fetchone():
                return jsonify(error=f"Exercise with id {exercise_id} not found."), 404
            cur.execute(
                "SELECT id FROM plan_exercises WHERE plan_day_id = %s AND order_index = %s;",
                (str(day_id), order_index)
            )
            if cur.fetchone():
                return jsonify(error=f"An exercise with order_index {order_index} already exists for this day."), 409
            plan_exercise_id = str(uuid.uuid4())
            insert_query_cols = [
                'id', 'plan_day_id', 'exercise_id', 'order_index', 'sets',
                'rep_range_low', 'rep_range_high', 'target_rir', 'rest_seconds', 'notes',
                'created_at', 'updated_at'
            ]
            insert_query_values = [
                plan_exercise_id, str(day_id), exercise_id, order_index, sets,
                plan_exercise_data.get('rep_range_low'), plan_exercise_data.get('rep_range_high'),
                plan_exercise_data.get('target_rir'), plan_exercise_data.get('rest_seconds'),
                plan_exercise_data.get('notes'),
                psycopg2.extensions.AsIs('NOW()'), psycopg2.extensions.AsIs('NOW()')
            ]
            placeholders = ', '.join(['%s'] * len(insert_query_cols))
            cols_sql = ', '.join(insert_query_cols)
            cur.execute(
                f"INSERT INTO plan_exercises ({cols_sql}) VALUES ({placeholders}) RETURNING *;",
                tuple(insert_query_values)
            )
            new_plan_exercise = cur.fetchone()
            conn.commit()
            app.logger.info(f"Plan exercise {plan_exercise_id} created for day {day_id} by user {g.current_user_id}")
            return jsonify(new_plan_exercise), 201
    except psycopg2.Error as e:
        app.logger.error(f"Database error creating plan exercise for day {day_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed creating plan exercise"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error creating plan exercise for day {day_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred creating plan exercise"), 500
    finally:
        if conn:
            conn.close()


@plans_bp.route('/v1/plandays/<uuid:day_id>/exercises', methods=['GET'])
@app.jwt_required
def get_plan_exercises_for_day(day_id):
    from flask import g
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT wp.user_id AS plan_owner_id
                FROM plan_days pd
                JOIN workout_plans wp ON pd.plan_id = wp.id
                WHERE pd.id = %s;
                """,
                (str(day_id),)
            )
            owner_info = cur.fetchone()
            if not owner_info:
                return jsonify(error="Parent plan day not found"), 404
            if owner_info['plan_owner_id'] != uuid.UUID(g.current_user_id):
                app.logger.warning(f"Forbidden attempt to get exercises for day {day_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own the parent plan of this day."), 403
            cur.execute(
                """
                SELECT pe.*, e.name as exercise_name
                FROM plan_exercises pe
                JOIN exercises e ON pe.exercise_id = e.id
                WHERE pe.plan_day_id = %s
                ORDER BY pe.order_index ASC;
                """,
                (str(day_id),)
            )
            plan_exercises_list = cur.fetchall()
            return jsonify(plan_exercises_list), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error fetching plan exercises for day {day_id}: {e}")
        return jsonify(error="Database operation failed fetching plan exercises"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error fetching plan exercises for day {day_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred fetching plan exercises"), 500
    finally:
        if conn:
            conn.close()


@plans_bp.route('/v1/planexercises/<uuid:plan_exercise_id>', methods=['PUT'])
@app.jwt_required
def update_plan_exercise(plan_exercise_id):
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT pe.id AS plan_exercise_id, pe.plan_day_id, pd.plan_id, wp.user_id AS plan_owner_id
                FROM plan_exercises pe
                JOIN plan_days pd ON pe.plan_day_id = pd.id
                JOIN workout_plans wp ON pd.plan_id = wp.id
                WHERE pe.id = %s;
                """,
                (str(plan_exercise_id),)
            )
            exercise_info = cur.fetchone()
            if not exercise_info:
                return jsonify(error="Plan exercise not found"), 404
            if exercise_info['plan_owner_id'] != uuid.UUID(g.current_user_id):
                app.logger.warning(f"Forbidden attempt to update plan exercise {plan_exercise_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own the parent plan of this exercise."), 403
            allowed_fields = {
                'exercise_id': uuid.UUID,
                'order_index': int,
                'sets': int,
                'rep_range_low': int,
                'rep_range_high': int,
                'target_rir': int,
                'rest_seconds': int,
                'notes': str
            }
            update_fields_parts = []
            update_values = []
            for field, field_type in allowed_fields.items():
                if field in data:
                    value = data[field]
                    if value is None:
                        if field not in ['exercise_id', 'order_index', 'sets']:
                            update_fields_parts.append(f"{field} = NULL")
                            continue
                        else:
                            return jsonify(error=f"Field '{field}' cannot be null."), 400
                    try:
                        if field_type is uuid.UUID:
                            typed_value = str(uuid.UUID(value))
                            cur.execute("SELECT id FROM exercises WHERE id = %s;", (typed_value,))
                            if not cur.fetchone():
                                return jsonify(error=f"New exercise_id {typed_value} not found."), 400
                        elif field_type is int:
                            typed_value = int(value)
                            if typed_value < 0 and field not in ['target_rir']:
                                raise ValueError(f"'{field}' must be non-negative.")
                            if field == 'sets' and typed_value < 1:
                                raise ValueError("'sets' must be at least 1.")
                        elif field_type is str:
                            typed_value = str(value)
                        else:
                            typed_value = value
                        if field == 'order_index':
                            cur.execute(
                                "SELECT id FROM plan_exercises WHERE plan_day_id = %s AND order_index = %s AND id != %s;",
                                (exercise_info['plan_day_id'], typed_value, str(plan_exercise_id))
                            )
                            if cur.fetchone():
                                return jsonify(error=f"An exercise with order_index {typed_value} already exists for this day."), 409
                        update_fields_parts.append(f"{field} = %s")
                        update_values.append(typed_value)
                    except ValueError as e:
                        return jsonify(error=f"Invalid value or type for field '{field}': {e}"), 400
            if not update_fields_parts:
                return jsonify(error="No valid fields provided for update"), 400
            update_fields_parts.append("updated_at = NOW()")
            query = f"UPDATE plan_exercises SET {', '.join(update_fields_parts)} WHERE id = %s RETURNING *;"
            update_values.append(str(plan_exercise_id))
            cur.execute(query, tuple(update_values))
            updated_plan_exercise = cur.fetchone()
            conn.commit()
            app.logger.info(f"Plan exercise {plan_exercise_id} updated successfully by user {g.current_user_id}")
            cur.execute("SELECT name FROM exercises WHERE id = %s;", (updated_plan_exercise['exercise_id'],))
            exercise_details = cur.fetchone()
            if exercise_details:
                updated_plan_exercise['exercise_name'] = exercise_details['name']
            return jsonify(updated_plan_exercise), 200
    except psycopg2.Error as e:
        app.logger.error(f"Database error updating plan exercise {plan_exercise_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed updating plan exercise"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error updating plan exercise {plan_exercise_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred updating plan exercise"), 500
    finally:
        if conn:
            conn.close()


@plans_bp.route('/v1/planexercises/<uuid:plan_exercise_id>', methods=['DELETE'])
@app.jwt_required
def delete_plan_exercise(plan_exercise_id):
    from flask import g
    conn = None
    try:
        conn = app.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT wp.user_id AS plan_owner_id
                FROM plan_exercises pe
                JOIN plan_days pd ON pe.plan_day_id = pd.id
                JOIN workout_plans wp ON pd.plan_id = wp.id
                WHERE pe.id = %s;
                """,
                (str(plan_exercise_id),)
            )
            exercise_info = cur.fetchone()
            if not exercise_info:
                return jsonify(error="Plan exercise not found"), 404
            if exercise_info['plan_owner_id'] != uuid.UUID(g.current_user_id):
                app.logger.warning(f"Forbidden attempt to delete plan exercise {plan_exercise_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own the parent plan of this exercise."), 403
            cur.execute("DELETE FROM plan_exercises WHERE id = %s;", (str(plan_exercise_id),))
            conn.commit()
            if cur.rowcount == 0:
                app.logger.error(f"Failed to delete plan exercise {plan_exercise_id}, though ownership was verified. Exercise might have been deleted by another process.")
                return jsonify(error="Failed to delete plan exercise, it might have already been deleted."), 404
            app.logger.info(f"Plan exercise {plan_exercise_id} deleted successfully by user {g.current_user_id}")
            return '', 204
    except psycopg2.Error as e:
        app.logger.error(f"Database error deleting plan exercise {plan_exercise_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed deleting plan exercise"), 500
    except Exception as e:
        app.logger.error(f"Unexpected error deleting plan exercise {plan_exercise_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred deleting plan exercise"), 500
    finally:
        if conn:
            conn.close()
