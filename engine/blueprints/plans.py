from flask import Blueprint, request, jsonify
from app import get_db_connection, release_db_connection, jwt_required, logger
import psycopg2
import psycopg2.extras
import uuid

plans_bp = Blueprint('plans', __name__)

def _calculate_and_store_plan_metrics(cur, plan_id, days_payload):
    """
    Helper function to calculate total volume and muscle group frequency
    and store/update it in the plan_metrics table.
    Assumes cursor (cur) is passed from an active transaction.
    """
    total_volume = 0
    freq_tracker = {}

    for day_struct in days_payload: # Renamed 'day' to 'day_struct' to avoid conflict if used in outer scope
        day_number = day_struct.get('day_number') # Used for frequency tracking
        # Assuming plan_days are already created or handled by the caller for POST/PUT
        # This helper focuses on iterating exercises within the provided structure
        for ex in day_struct.get('exercises', []):
            exercise_id = ex.get('exercise_id')
            sets = int(ex.get('sets', 0))
            if not exercise_id:
                continue

            # Fetch main_target_muscle_group for the exercise
            cur.execute(
                "SELECT main_target_muscle_group FROM exercises WHERE id = %s;",
                (exercise_id,)
            )
            ex_details = cur.fetchone()
            mg = ex_details.get('main_target_muscle_group') if ex_details else None

            total_volume += sets
            if mg and day_number is not None: # Ensure day_number is part of context for frequency
                freq_tracker.setdefault(mg, set()).add(day_number)

    freq_counts = {k: len(v) for k, v in freq_tracker.items()}

    # Upsert into plan_metrics
    cur.execute(
        """
        INSERT INTO plan_metrics (plan_id, total_volume, muscle_group_frequency, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (plan_id) DO UPDATE SET
            total_volume = EXCLUDED.total_volume,
            muscle_group_frequency = EXCLUDED.muscle_group_frequency,
            updated_at = NOW();
        """,
        (plan_id, total_volume, psycopg2.extras.Json(freq_counts))
    )
    return total_volume, freq_counts

@plans_bp.route('/v1/users/<uuid:user_id>/plans', methods=['POST'])
@jwt_required
def create_workout_plan(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        logger.warning(f"Forbidden attempt to create plan for user {user_id} by user {g.current_user_id}")
        return jsonify(error="Forbidden. You can only create plans for your own profile."), 403

    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    plan_name = data.get('name')
    if not plan_name:
        return jsonify(error="Missing required field: name"), 400

    # Optional fields
    days_per_week = data.get('days_per_week')
    plan_length_weeks = data.get('plan_length_weeks')
    goal_focus = data.get('goal_focus') # E.g., "strength", "hypertrophy", "endurance"

    # Validate optional fields if present
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
        conn = get_db_connection()
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

            # --- Calculate volume and frequency if plan details provided ---
            total_volume = 0
            freq_tracker = {}
            days_payload = data.get('days', []) or []

            for day in days_payload:
                day_number = day.get('day_number')
                day_name = day.get('name')
                day_id = str(uuid.uuid4())
                if day_number is not None:
                    cur.execute(
                        "INSERT INTO plan_days (id, plan_id, day_number, name) VALUES (%s, %s, %s, %s);",
                        (day_id, plan_id, day_number, day_name),
                    )

                for ex in day.get('exercises', []) or []:
                    exercise_id = ex.get('exercise_id')
                    sets = int(ex.get('sets', 0))
                    if not exercise_id:
                        continue
                    cur.execute(
                        "SELECT main_target_muscle_group FROM exercises WHERE id = %s;",
                        (exercise_id,),
                    )
                    ex_details = cur.fetchone()
                    mg = ex_details.get('main_target_muscle_group') if ex_details else None
                    cur.execute(
                        "INSERT INTO plan_exercises (id, plan_day_id, exercise_id, order_index, sets) VALUES (%s, %s, %s, %s, %s);",
                        (str(uuid.uuid4()), day_id, exercise_id, ex.get('order_index', 0), sets),
                    )
                    total_volume += sets
                    if mg and day_number is not None:
                        freq_tracker.setdefault(mg, set()).add(day_number)

            # Use the helper function to calculate and store metrics
            total_volume, freq_counts = _calculate_and_store_plan_metrics(cur, plan_id, days_payload)

            conn.commit() # Commit all changes including metrics
            new_plan['total_volume'] = total_volume # Add to response
            new_plan['muscle_group_frequency'] = freq_counts # Add to response
            logger.info(
                f"Workout plan '{plan_name}' (ID: {plan_id}) created successfully for user: {user_id}"
            )
            return jsonify(new_plan), 201

    except psycopg2.Error as e:
        logger.error(f"Database error creating workout plan for user {user_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed creating workout plan"), 500
    except Exception as e:
        logger.error(f"Unexpected error creating workout plan for user {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred creating workout plan"), 500
    finally:
        if conn:
            release_db_connection(conn)

@plans_bp.route('/v1/users/<uuid:user_id>/plans', methods=['GET'])
@jwt_required
def get_workout_plans_for_user(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        logger.warning(f"Forbidden attempt to get plans for user {user_id} by user {g.current_user_id}")
        return jsonify(error="Forbidden. You can only view your own plans."), 403

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM workout_plans WHERE user_id = %s ORDER BY created_at DESC;",
                (str(user_id),)
            )
            plans_list = cur.fetchall()

            return jsonify(plans_list), 200

    except psycopg2.Error as e:
        logger.error(f"Database error fetching workout plans for user {user_id}: {e}")
        return jsonify(error="Database operation failed fetching workout plans"), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching workout plans for user {user_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred fetching workout plans"), 500
    finally:
        if conn:
            release_db_connection(conn)

@plans_bp.route('/v1/plans/<uuid:plan_id>', methods=['GET'])
@jwt_required
def get_workout_plan_details(plan_id):
    from flask import g
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Fetch the plan
            cur.execute("SELECT * FROM workout_plans WHERE id = %s;", (str(plan_id),))
            plan = cur.fetchone()

            if not plan:
                return jsonify(error="Workout plan not found"), 404

            # Verify ownership
            if plan['user_id'] != uuid.UUID(g.current_user_id):
                logger.warning(f"Forbidden attempt to access plan {plan_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own this plan."), 403

            # Fetch associated plan days
            cur.execute(
                "SELECT * FROM plan_days WHERE plan_id = %s ORDER BY day_number ASC;",
                (str(plan_id),)
            )
            plan_days = cur.fetchall()

            # For each plan day, fetch its exercises
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
        logger.error(f"Database error fetching details for plan {plan_id}: {e}")
        return jsonify(error="Database operation failed fetching plan details"), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching details for plan {plan_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred fetching plan details"), 500
    finally:
        if conn:
            release_db_connection(conn)

@plans_bp.route('/v1/plans/<uuid:plan_id>', methods=['PUT'])
@jwt_required
def update_workout_plan(plan_id):
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Fetch the plan to verify ownership
            cur.execute("SELECT user_id FROM workout_plans WHERE id = %s;", (str(plan_id),))
            plan_owner = cur.fetchone()

            if not plan_owner:
                return jsonify(error="Workout plan not found"), 404

            if plan_owner['user_id'] != uuid.UUID(g.current_user_id):
                logger.warning(f"Forbidden attempt to update plan {plan_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own this plan."), 403

            # Fields that can be updated
            allowed_fields = {
                'name': str,
                'days_per_week': int,
                'plan_length_weeks': int,
                'goal_focus': str,
                'is_active': bool # Example: allowing to activate/deactivate a plan
            }

            update_fields_parts = []
            update_values = []

            for field, field_type in allowed_fields.items():
                if field in data:
                    value = data[field]
                    # Basic type validation
                    if value is not None: # Allow fields to be set to null if appropriate for DB schema
                        if field_type is int and isinstance(value, float) and value.is_integer():
                            value = int(value) # Allow float if it's a whole number for int fields
                        elif not isinstance(value, field_type):
                            return jsonify(error=f"Invalid type for field '{field}'. Expected {field_type.__name__}."), 400

                    # Specific validation for certain fields
                    if field == 'days_per_week' and value is not None and not (1 <= value <= 7):
                        return jsonify(error="'days_per_week' must be between 1 and 7"), 400
                    if field == 'plan_length_weeks' and value is not None and value < 0: # 0 could mean ongoing
                        return jsonify(error="'plan_length_weeks' must be non-negative"), 400

                    update_fields_parts.append(f"{field} = %s")
                    update_values.append(value)

            if not update_fields_parts:
                return jsonify(error="No valid fields provided for update"), 400

            # Update top-level plan fields if any were provided
            if update_fields_parts:
                update_fields_parts.append("updated_at = NOW()") # Ensure updated_at is set for workout_plans
                query = f"UPDATE workout_plans SET {', '.join(update_fields_parts)} WHERE id = %s RETURNING *;"
                update_values_list = update_values + [str(plan_id)] # Ensure plan_id is last for query
                cur.execute(query, tuple(update_values_list))
                updated_plan = cur.fetchone() # This will be the base for our response
            else:
                # If no top-level fields changed, fetch the current plan to return later
                cur.execute("SELECT * FROM workout_plans WHERE id = %s;", (str(plan_id),))
                updated_plan = cur.fetchone()


            # Handle updates to plan structure (days and exercises)
            if 'days' in data:
                days_payload = data.get('days', [])

                # 1. Delete existing plan days and their exercises (CASCADE should handle exercises)
                cur.execute("DELETE FROM plan_days WHERE plan_id = %s;", (str(plan_id),))

                # 2. Create new plan days and exercises from payload
                for day_struct in days_payload:
                    day_number = day_struct.get('day_number')
                    day_name = day_struct.get('name')
                    new_day_id = str(uuid.uuid4()) # New ID for the plan day

                    if day_number is not None: # Ensure day_number is provided
                        cur.execute(
                            """
                            INSERT INTO plan_days (id, plan_id, day_number, name, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, NOW(), NOW());
                            """,
                            (new_day_id, str(plan_id), day_number, day_name)
                        )

                        for ex_struct in day_struct.get('exercises', []):
                            exercise_id = ex_struct.get('exercise_id')
                            if not exercise_id: # Skip if no exercise_id
                                continue

                            # Minimal required fields for plan_exercises
                            sets = int(ex_struct.get('sets', 0))
                            order_index = int(ex_struct.get('order_index', 0))

                            # Include all optional fields from plan_exercises
                            rep_range_low = ex_struct.get('rep_range_low')
                            rep_range_high = ex_struct.get('rep_range_high')
                            target_rir = ex_struct.get('target_rir')
                            rest_seconds = ex_struct.get('rest_seconds')
                            notes = ex_struct.get('notes')

                            cur.execute(
                                """
                                INSERT INTO plan_exercises (
                                    id, plan_day_id, exercise_id, order_index, sets,
                                    rep_range_low, rep_range_high, target_rir, rest_seconds, notes,
                                    created_at, updated_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW());
                                """,
                                (str(uuid.uuid4()), new_day_id, exercise_id, order_index, sets,
                                 rep_range_low, rep_range_high, target_rir, rest_seconds, notes)
                            )

                # 3. Recalculate and store/update metrics
                total_volume, freq_counts = _calculate_and_store_plan_metrics(cur, str(plan_id), days_payload)
                if updated_plan: # Add metrics to the response object if it exists
                    updated_plan['total_volume'] = total_volume
                    updated_plan['muscle_group_frequency'] = freq_counts

            conn.commit() # Commit all changes (plan fields, structure, metrics)

            if not updated_plan: # Should only happen if plan_id was invalid from start and no updates made
                return jsonify(error="Workout plan not found or no updates made"), 404

            # If only structure was updated, metrics might be the only new thing in `updated_plan`
            # We might want to fetch the full plan details again if we want to return the complete updated plan structure
            # For now, returning the workout_plans record and any calculated metrics.
            # Fetching full plan details to ensure the response is complete after structural changes
            if 'days' in data: # If structure changed, refetch full plan for accurate response
                cur.execute("SELECT * FROM workout_plans WHERE id = %s;", (str(plan_id),))
                updated_plan_base = cur.fetchone()

                cur.execute("SELECT * FROM plan_days WHERE plan_id = %s ORDER BY day_number ASC;", (str(plan_id),))
                plan_days_list = cur.fetchall()
                for day_item in plan_days_list:
                    cur.execute(
                        "SELECT pe.*, e.name as exercise_name FROM plan_exercises pe JOIN exercises e ON pe.exercise_id = e.id WHERE pe.plan_day_id = %s ORDER BY pe.order_index ASC;",
                        (str(day_item['id']),)
                    )
                    day_item['exercises'] = cur.fetchall()
                updated_plan_base['days'] = plan_days_list

                # Re-fetch metrics to ensure they are part of the response if only structure changed initially
                cur.execute("SELECT total_volume, muscle_group_frequency FROM plan_metrics WHERE plan_id = %s;", (str(plan_id),))
                metrics_data = cur.fetchone()
                if metrics_data:
                    updated_plan_base['total_volume'] = metrics_data['total_volume']
                    updated_plan_base['muscle_group_frequency'] = metrics_data['muscle_group_frequency']

                updated_plan = updated_plan_base


            logger.info(f"Workout plan {plan_id} updated successfully by user {g.current_user_id}")
            return jsonify(updated_plan), 200

    except psycopg2.Error as e:
        logger.error(f"Database error updating plan {plan_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed updating plan"), 500
    except Exception as e:
        logger.error(f"Unexpected error updating plan {plan_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred updating plan"), 500
    finally:
        if conn:
            release_db_connection(conn)

@plans_bp.route('/v1/plans/<uuid:plan_id>', methods=['DELETE'])
@jwt_required
def delete_workout_plan(plan_id):
    from flask import g
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Fetch the plan to verify ownership before deleting
            cur.execute("SELECT user_id FROM workout_plans WHERE id = %s;", (str(plan_id),))
            plan_owner = cur.fetchone()

            if not plan_owner:
                return jsonify(error="Workout plan not found"), 404

            if plan_owner['user_id'] != uuid.UUID(g.current_user_id):
                logger.warning(f"Forbidden attempt to delete plan {plan_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own this plan."), 403

            # Delete the plan. Associated plan_days and plan_exercises should be deleted by CASCADE.
            cur.execute("DELETE FROM workout_plans WHERE id = %s;", (str(plan_id),))
            conn.commit()

            # Check if deletion was successful
            if cur.rowcount == 0:
                # This case should ideally be caught by the initial check, but as a safeguard:
                logger.error(f"Failed to delete plan {plan_id}, though ownership was verified. Plan might have been deleted by another process.")
                return jsonify(error="Failed to delete plan, it might have already been deleted."), 404

            logger.info(f"Workout plan {plan_id} deleted successfully by user {g.current_user_id}")
            return '', 204 # No content

    except psycopg2.Error as e:
        logger.error(f"Database error deleting plan {plan_id}: {e}")
        if conn:
            conn.rollback()
        # Consider if this should be 500 or if specific psycopg2 errors might indicate a 404 (e.g., foreign key constraint)
        return jsonify(error="Database operation failed deleting plan"), 500
    except Exception as e:
        logger.error(f"Unexpected error deleting plan {plan_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred deleting plan"), 500
    finally:
        if conn:
            release_db_connection(conn)

# --- Plan Day Endpoints ---

@plans_bp.route('/v1/plans/<uuid:plan_id>/days', methods=['POST'])
@jwt_required
def create_plan_day(plan_id):
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    day_number = data.get('day_number')
    if day_number is None: # Check for None specifically, as 0 could be a valid day_number in some systems
        return jsonify(error="Missing required field: day_number"), 400

    try:
        day_number = int(day_number)
        if day_number < 0: # Or 1 if day numbers are 1-indexed
             raise ValueError("day_number must be a non-negative integer.")
    except ValueError as e:
        return jsonify(error=f"Invalid 'day_number': {e}"), 400

    day_name = data.get('name') # Optional

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Verify ownership of the parent plan
            cur.execute("SELECT user_id FROM workout_plans WHERE id = %s;", (str(plan_id),))
            plan_owner = cur.fetchone()

            if not plan_owner:
                return jsonify(error="Parent workout plan not found"), 404

            if plan_owner['user_id'] != uuid.UUID(g.current_user_id):
                logger.warning(f"Forbidden attempt to add day to plan {plan_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own this plan."), 403

            # Check if a day with the same day_number already exists for this plan
            cur.execute("SELECT id FROM plan_days WHERE plan_id = %s AND day_number = %s;", (str(plan_id), day_number))
            if cur.fetchone():
                return jsonify(error=f"A day with day_number {day_number} already exists for this plan."), 409 # Conflict

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
            logger.info(f"Plan day {plan_day_id} (Day {day_number}) created for plan {plan_id} by user {g.current_user_id}")
            return jsonify(new_plan_day), 201

    except psycopg2.Error as e:
        logger.error(f"Database error creating plan day for plan {plan_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed creating plan day"), 500
    except Exception as e:
        logger.error(f"Unexpected error creating plan day for plan {plan_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred creating plan day"), 500
    finally:
        if conn:
            release_db_connection(conn)

@plans_bp.route('/v1/plans/<uuid:plan_id>/days', methods=['GET'])
@jwt_required
def get_plan_days(plan_id):
    from flask import g
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Verify ownership of the parent plan
            cur.execute("SELECT user_id FROM workout_plans WHERE id = %s;", (str(plan_id),))
            plan_owner = cur.fetchone()

            if not plan_owner:
                return jsonify(error="Parent workout plan not found"), 404

            if plan_owner['user_id'] != uuid.UUID(g.current_user_id):
                logger.warning(f"Forbidden attempt to get days for plan {plan_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own this plan."), 403

            # Fetch all plan days for this plan
            cur.execute(
                "SELECT * FROM plan_days WHERE plan_id = %s ORDER BY day_number ASC;",
                (str(plan_id),)
            )
            plan_days_list = cur.fetchall()

            return jsonify(plan_days_list), 200

    except psycopg2.Error as e:
        logger.error(f"Database error fetching plan days for plan {plan_id}: {e}")
        return jsonify(error="Database operation failed fetching plan days"), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching plan days for plan {plan_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred fetching plan days"), 500
    finally:
        if conn:
            release_db_connection(conn)

@plans_bp.route('/v1/plandays/<uuid:day_id>', methods=['PUT'])
@jwt_required
def update_plan_day(day_id):
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Fetch plan day and its parent plan's user_id for ownership verification
            cur.execute(
                """
                SELECT pd.id AS plan_day_id, pd.plan_id, wp.user_id AS plan_owner_id
                FROM plan_days pd
                JOIN workout_plans wp ON pd.plan_id = wp.id
                WHERE pd.id = %s;
                """, (str(day_id),)
            )
            day_info = cur.fetchone()

            if not day_info:
                return jsonify(error="Plan day not found"), 404

            if day_info['plan_owner_id'] != uuid.UUID(g.current_user_id):
                logger.warning(f"Forbidden attempt to update plan day {day_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own the parent plan of this day."), 403

            update_fields_parts = []
            update_values = []

            if 'day_number' in data:
                try:
                    day_number = int(data['day_number'])
                    if day_number < 0: # Or 1 if 1-indexed
                        raise ValueError("day_number must be a non-negative integer.")

                    # Check for day_number conflict within the same plan
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
                if name is not None and not isinstance(name, str): # Allow name to be nullified
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

            logger.info(f"Plan day {day_id} updated successfully by user {g.current_user_id}")
            return jsonify(updated_plan_day), 200

    except psycopg2.Error as e:
        logger.error(f"Database error updating plan day {day_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed updating plan day"), 500
    except Exception as e:
        logger.error(f"Unexpected error updating plan day {day_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred updating plan day"), 500
    finally:
        if conn:
            release_db_connection(conn)

@plans_bp.route('/v1/plandays/<uuid:day_id>', methods=['DELETE'])
@jwt_required
def delete_plan_day(day_id):
    from flask import g
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Fetch plan day and its parent plan's user_id for ownership verification
            cur.execute(
                """
                SELECT wp.user_id AS plan_owner_id
                FROM plan_days pd
                JOIN workout_plans wp ON pd.plan_id = wp.id
                WHERE pd.id = %s;
                """, (str(day_id),)
            )
            day_info = cur.fetchone()

            if not day_info:
                return jsonify(error="Plan day not found"), 404

            if day_info['plan_owner_id'] != uuid.UUID(g.current_user_id):
                logger.warning(f"Forbidden attempt to delete plan day {day_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own the parent plan of this day."), 403

            # Delete the plan day. Associated plan_exercises should be deleted by CASCADE.
            cur.execute("DELETE FROM plan_days WHERE id = %s;", (str(day_id),))
            conn.commit()

            if cur.rowcount == 0:
                # Should be caught by the initial check, but as a safeguard
                logger.error(f"Failed to delete plan day {day_id}, though ownership was verified. Day might have been deleted by another process.")
                return jsonify(error="Failed to delete plan day, it might have already been deleted."), 404

            logger.info(f"Plan day {day_id} deleted successfully by user {g.current_user_id}")
            return '', 204

    except psycopg2.Error as e:
        logger.error(f"Database error deleting plan day {day_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed deleting plan day"), 500
    except Exception as e:
        logger.error(f"Unexpected error deleting plan day {day_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred deleting plan day"), 500
    finally:
        if conn:
            release_db_connection(conn)

# --- Plan Exercise Endpoints ---

@plans_bp.route('/v1/plandays/<uuid:day_id>/exercises', methods=['POST'])
@jwt_required
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
        exercise_id = str(uuid.UUID(data['exercise_id'])) # Validate UUID
        order_index = int(data['order_index'])
        sets = int(data['sets'])
        if order_index < 0:
            raise ValueError("'order_index' must be non-negative.")
        if sets < 1:
            raise ValueError("'sets' must be at least 1.")
    except (ValueError, TypeError) as e:
        return jsonify(error=f"Invalid data type or value for required fields: {e}"), 400

    # Optional fields with type validation
    optional_fields_spec = {
        'rep_range_low': int, 'rep_range_high': int, 'target_rir': int,
        'rest_seconds': int, 'notes': str
    }
    plan_exercise_data = {}
    for field, field_type in optional_fields_spec.items():
        if field in data:
            value = data[field]
            if value is not None:
                try:
                    typed_value = field_type(value)
                    # Additional validation for specific fields
                    if field_type is int and typed_value < 0 and field not in ['target_rir']: # RIR can be negative with some scales/interpretations
                         raise ValueError(f"'{field}' must be non-negative.")
                    plan_exercise_data[field] = typed_value
                except ValueError as e:
                    return jsonify(error=f"Invalid value for field '{field}': {e}"), 400
            else:
                plan_exercise_data[field] = None


    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Verify ownership of the parent plan day (and thus the plan)
            cur.execute(
                """
                SELECT wp.user_id AS plan_owner_id
                FROM plan_days pd
                JOIN workout_plans wp ON pd.plan_id = wp.id
                WHERE pd.id = %s;
                """, (str(day_id),)
            )
            owner_info = cur.fetchone()

            if not owner_info:
                return jsonify(error="Parent plan day not found"), 404

            if owner_info['plan_owner_id'] != uuid.UUID(g.current_user_id):
                logger.warning(f"Forbidden attempt to add exercise to day {day_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own the parent plan of this day."), 403

            # Check if exercise_id exists in exercises table
            cur.execute("SELECT id FROM exercises WHERE id = %s;", (exercise_id,))
            if not cur.fetchone():
                return jsonify(error=f"Exercise with id {exercise_id} not found."), 404 # Or 400 Bad Request

            # Check for order_index conflict within the same plan_day
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
            logger.info(f"Plan exercise {plan_exercise_id} created for day {day_id} by user {g.current_user_id}")
            return jsonify(new_plan_exercise), 201

    except psycopg2.Error as e:
        logger.error(f"Database error creating plan exercise for day {day_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed creating plan exercise"), 500
    except Exception as e:
        logger.error(f"Unexpected error creating plan exercise for day {day_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred creating plan exercise"), 500
    finally:
        if conn:
            release_db_connection(conn)

@plans_bp.route('/v1/plandays/<uuid:day_id>/exercises', methods=['GET'])
@jwt_required
def get_plan_exercises_for_day(day_id):
    from flask import g
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Verify ownership of the parent plan day
            cur.execute(
                """
                SELECT wp.user_id AS plan_owner_id
                FROM plan_days pd
                JOIN workout_plans wp ON pd.plan_id = wp.id
                WHERE pd.id = %s;
                """, (str(day_id),)
            )
            owner_info = cur.fetchone()

            if not owner_info:
                return jsonify(error="Parent plan day not found"), 404

            if owner_info['plan_owner_id'] != uuid.UUID(g.current_user_id):
                logger.warning(f"Forbidden attempt to get exercises for day {day_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own the parent plan of this day."), 403

            # Fetch all plan exercises for this day, joining with exercises table for names
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
        logger.error(f"Database error fetching plan exercises for day {day_id}: {e}")
        return jsonify(error="Database operation failed fetching plan exercises"), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching plan exercises for day {day_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred fetching plan exercises"), 500
    finally:
        if conn:
            release_db_connection(conn)

@plans_bp.route('/v1/planexercises/<uuid:plan_exercise_id>', methods=['PUT'])
@jwt_required
def update_plan_exercise(plan_exercise_id):
    from flask import g
    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Verify ownership by fetching the plan exercise and joining up to the workout_plan's user_id
            cur.execute(
                """
                SELECT pe.id AS plan_exercise_id, pe.plan_day_id, pd.plan_id, wp.user_id AS plan_owner_id
                FROM plan_exercises pe
                JOIN plan_days pd ON pe.plan_day_id = pd.id
                JOIN workout_plans wp ON pd.plan_id = wp.id
                WHERE pe.id = %s;
                """, (str(plan_exercise_id),)
            )
            exercise_info = cur.fetchone()

            if not exercise_info:
                return jsonify(error="Plan exercise not found"), 404

            if exercise_info['plan_owner_id'] != uuid.UUID(g.current_user_id):
                logger.warning(f"Forbidden attempt to update plan exercise {plan_exercise_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own the parent plan of this exercise."), 403

            # Fields that can be updated
            allowed_fields = {
                'exercise_id': uuid.UUID, 'order_index': int, 'sets': int,
                'rep_range_low': int, 'rep_range_high': int, 'target_rir': int,
                'rest_seconds': int, 'notes': str
            }

            update_fields_parts = []
            update_values = []

            for field, field_type in allowed_fields.items():
                if field in data:
                    value = data[field]
                    if value is None: # Allow nullification for optional fields
                        if field not in ['exercise_id', 'order_index', 'sets']: # These are usually required
                            update_fields_parts.append(f"{field} = NULL")
                            # No value to add to update_values for NULL assignment like this
                            continue # Skip to next field
                        else:
                             return jsonify(error=f"Field '{field}' cannot be null."), 400

                    try:
                        if field_type is uuid.UUID:
                            typed_value = str(uuid.UUID(value)) # Validate and convert to string for query
                            # Check if new exercise_id exists
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
                            typed_value = value # Should not happen with current spec

                        # Check for order_index conflict if it's being changed
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

            logger.info(f"Plan exercise {plan_exercise_id} updated successfully by user {g.current_user_id}")
            # Join with exercises table to get exercise_name for the response
            cur.execute("SELECT name FROM exercises WHERE id = %s;", (updated_plan_exercise['exercise_id'],))
            exercise_details = cur.fetchone()
            if exercise_details:
                 updated_plan_exercise['exercise_name'] = exercise_details['name']

            return jsonify(updated_plan_exercise), 200

    except psycopg2.Error as e:
        logger.error(f"Database error updating plan exercise {plan_exercise_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed updating plan exercise"), 500
    except Exception as e:
        logger.error(f"Unexpected error updating plan exercise {plan_exercise_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred updating plan exercise"), 500
    finally:
        if conn:
            release_db_connection(conn)

@plans_bp.route('/v1/planexercises/<uuid:plan_exercise_id>', methods=['DELETE'])
@jwt_required
def delete_plan_exercise(plan_exercise_id):
    from flask import g
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Verify ownership by fetching the plan exercise and joining up to the workout_plan's user_id
            cur.execute(
                """
                SELECT wp.user_id AS plan_owner_id
                FROM plan_exercises pe
                JOIN plan_days pd ON pe.plan_day_id = pd.id
                JOIN workout_plans wp ON pd.plan_id = wp.id
                WHERE pe.id = %s;
                """, (str(plan_exercise_id),)
            )
            exercise_info = cur.fetchone()

            if not exercise_info:
                return jsonify(error="Plan exercise not found"), 404

            if exercise_info['plan_owner_id'] != uuid.UUID(g.current_user_id):
                logger.warning(f"Forbidden attempt to delete plan exercise {plan_exercise_id} by user {g.current_user_id}")
                return jsonify(error="Forbidden. You do not own the parent plan of this exercise."), 403

            # Delete the plan exercise
            # Delete the plan exercise
            cur.execute("DELETE FROM plan_exercises WHERE id = %s;", (str(plan_exercise_id),))
            conn.commit()

            if cur.rowcount == 0:
                # Should be caught by the initial check, but as a safeguard
                logger.error(f"Failed to delete plan exercise {plan_exercise_id}, though ownership was verified. Exercise might have been deleted by another process.")
                return jsonify(error="Failed to delete plan exercise, it might have already been deleted."), 404

            logger.info(f"Plan exercise {plan_exercise_id} deleted successfully by user {g.current_user_id}")
            return '', 204

    except psycopg2.Error as e:
        logger.error(f"Database error deleting plan exercise {plan_exercise_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed deleting plan exercise"), 500
    except Exception as e:
        logger.error(f"Unexpected error deleting plan exercise {plan_exercise_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred deleting plan exercise"), 500
    finally:
        if conn:
            release_db_connection(conn)


