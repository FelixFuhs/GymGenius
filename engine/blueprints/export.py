from flask import Blueprint, Response, jsonify, g, current_app
from ..app import get_db_connection, release_db_connection, jwt_required, logger, limiter # Assuming limiter is available from app
import io
import csv
import zipfile
import psycopg2
from datetime import datetime, timezone # Ensure timezone is imported for datetime operations

export_bp = Blueprint('export', __name__, url_prefix='/v1')

def _write_to_csv_buffer(data, fieldnames):
    """Helper function to write list of dicts to a CSV in-memory buffer."""
    string_io = io.StringIO()
    # Using csv.writer for simplicity, assuming data is list of lists (with header as first list)
    # If data is list of dicts, DictWriter is better. Let's assume RealDictCursor gives list of dicts.
    if not data: # No data, just write headers
        writer = csv.writer(string_io)
        writer.writerow(fieldnames)
        return string_io

    writer = csv.DictWriter(string_io, fieldnames=fieldnames)
    writer.writeheader()
    for row in data:
        # Convert datetime objects to ISO format string
        processed_row = {}
        for key, value in row.items():
            if isinstance(value, datetime):
                processed_row[key] = value.isoformat()
            elif value is None:
                processed_row[key] = "" # Replace None with empty string for CSV
            else:
                processed_row[key] = value
        writer.writerow(processed_row)
    return string_io

@export_bp.route('/users/<uuid:uid>/export', methods=['GET'])
@jwt_required
@limiter.limit("5 per day") # Apply rate limit
def export_user_data(uid):
    if str(uid) != g.current_user_id:
        logger.warning(f"Forbidden attempt to export data for user {uid} by user {g.current_user_id}")
        return jsonify(error="Forbidden. You can only export your own data."), 403

    user_id = str(uid)
    conn = None

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Fetch Workouts
            cur.execute("SELECT * FROM workouts WHERE user_id = %s ORDER BY started_at DESC;", (user_id,))
            workouts_data = cur.fetchall()
            workout_fieldnames = [desc[0] for desc in cur.description] if workouts_data else [
                "id", "user_id", "plan_day_id", "started_at", "completed_at",
                "fatigue_level", "sleep_hours", "stress_level", "notes",
                "created_at", "updated_at" # Add all expected fields
            ]


            # Fetch Workout Sets
            # Consider joining with exercises table to get exercise_name if desired directly in sets.csv
            # For now, just raw set data. Users can join with exercises.csv using exercise_id if needed.
            cur.execute(
                """
                SELECT ws.*
                FROM workout_sets ws
                JOIN workouts w ON ws.workout_id = w.id
                WHERE w.user_id = %s
                ORDER BY ws.completed_at ASC;
                """, (user_id,)
            )
            sets_data = cur.fetchall()
            set_fieldnames = [desc[0] for desc in cur.description] if sets_data else [
                "id", "workout_id", "exercise_id", "set_number", "actual_weight",
                "actual_reps", "actual_rir", "form_rating", "mti", "rest_before_seconds",
                "completed_at", "notes", "created_at", "updated_at" # Add all expected fields
            ]


            # Fetch Exercise Plans
            cur.execute("SELECT * FROM exercise_plans WHERE user_id = %s ORDER BY created_at DESC;", (user_id,))
            plans_data = cur.fetchall()
            plan_fieldnames = [desc[0] for desc in cur.description] if plans_data else [
                "id", "user_id", "name", "description", "goal", "duration_weeks",
                "days_per_week", "created_at", "updated_at" # Add all expected fields
            ]

            # (Optional) Fetch plan_days and plan_day_exercises if they are to be separate CSVs
            # For MVP, focusing on the main tables.

        # Create CSVs in memory
        workouts_csv_buffer = _write_to_csv_buffer(workouts_data, workout_fieldnames)
        sets_csv_buffer = _write_to_csv_buffer(sets_data, set_fieldnames)
        plans_csv_buffer = _write_to_csv_buffer(plans_data, plan_fieldnames)

        # Create ZIP archive in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_f:
            zip_f.writestr('workouts.csv', workouts_csv_buffer.getvalue().encode('utf-8'))
            zip_f.writestr('sets.csv', sets_csv_buffer.getvalue().encode('utf-8'))
            zip_f.writestr('plans.csv', plans_csv_buffer.getvalue().encode('utf-8'))

        zip_buffer.seek(0) # Rewind buffer to the beginning

        logger.info(f"User data export generated for user {user_id}.")

        return Response(
            zip_buffer.getvalue(),
            mimetype='application/zip',
            headers={'Content-Disposition': f'attachment;filename=gymgenius_export_{user_id}.zip'}
        )

    except psycopg2.Error as e:
        logger.error(f"Database error during data export for user {user_id}: {e}", exc_info=True)
        return jsonify(error="Database operation failed during export."), 500
    except Exception as e:
        logger.error(f"Unexpected error during data export for user {user_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred during export."), 500
    finally:
        if conn:
            release_db_connection(conn)
