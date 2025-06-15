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
from urllib.parse import urlparse # Add this import
from datetime import datetime, timedelta, timezone
import logging
import math # For rounding and calculations
import uuid # For generating UUIDs for new records
import bcrypt # For password hashing
import jwt # For JWT generation and decoding
from functools import wraps # For creating decorators

app = Flask(__name__)

# --- JWT Configuration ---
# In a real app, use a strong, randomly generated key stored securely (e.g., env variable)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-super-secret-jwt-key-please-change')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1) # Access token valid for 1 hour
# Consider adding JWT_REFRESH_TOKEN_EXPIRES if implementing refresh tokens

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__) # Use app.logger or a specific logger

# --- Database Connection Helper ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            url = urlparse(database_url)
            conn = psycopg2.connect(
                dbname=url.path[1:], # Remove leading '/'
                user=url.username,
                password=url.password,
                host=url.hostname,
                port=url.port
            )
            # logger.info("Connected to database using DATABASE_URL.") # Optional: for debugging
            return conn
        except Exception as e:
            # Log that DATABASE_URL parsing failed and falling back or re-raising
            logger.error(f"Failed to connect using DATABASE_URL: {e}. Falling back to POSTGRES_* vars.")
            # Fall through to original method if DATABASE_URL connection fails
            pass

    # Original fallback to individual POSTGRES_* variables
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "gymgenius_dev"),
            user=os.getenv("POSTGRES_USER", "gymgenius"),
            password=os.getenv("POSTGRES_PASSWORD", "secret"),
            host=os.getenv("POSTGRES_HOST", "db"), # In CI, this will be 'postgres' or 'localhost' for service container
            port=os.getenv("POSTGRES_PORT", "5432")
        )
        # logger.info("Connected to database using POSTGRES_* environment variables.") # Optional
        return conn
    except psycopg2.OperationalError as e:
        # Use app.logger if logger instance is not directly available or properly configured at this point
        # For consistency with the rest of the file, using 'logger' which should be app.logger or a configured one.
        logger.error(f"Database connection error (POSTGRES_* vars): {e}")
        raise

# --- JWT Required Decorator ---
def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
            elif len(parts) == 1: # Handle cases where 'Bearer' prefix might be missing by mistake
                token = parts[0]


        if not token:
            logger.warning("JWT token is missing")
            return jsonify(message="Authentication token is missing!"), 401

        try:
            # Decode the token using the application's secret key
            # Add 'algorithms' parameter to specify the algorithm used for encoding
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])

            # Make user_id available to the decorated route, e.g., via request context or direct pass
            # For simplicity, we can fetch basic user info here if needed often, or just pass user_id
            # For now, just passing user_id. Routes can fetch more details if needed.
            # request.current_user_id = data['user_id'] # Example of adding to request context (Flask's g object is better)

            # Pass the decoded payload (which should contain user_id) to the decorated function
            # This way, the route can access it directly as an argument if designed so, or use g.user_id
            # For this implementation, we'll assume routes can get it from g or it's passed if the decorator is modified
            from flask import g
            g.current_user_id = data['user_id'] # Store user_id in Flask's g object for easy access in routes

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return jsonify(message="Your token has expired. Please log in again."), 401
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid JWT token: {e}")
            return jsonify(message="Invalid token. Please log in again."), 401
        except Exception as e:
            logger.error(f"Error during token decoding: {e}", exc_info=True)
            return jsonify(message="Error processing token."), 500

        return f(*args, **kwargs)
    return decorated_function


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

# --- Authentication Endpoints (P1-BE-008) ---
@app.route('/v1/auth/register', methods=['POST'])
def register_user():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify(error="Email and password are required"), 400

    email = data['email'].lower() # Store email in lowercase for consistency
    password = data['password']

    if len(password) < 8: # Basic password strength
        return jsonify(error="Password must be at least 8 characters long"), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Check if user already exists
            cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
            if cur.fetchone():
                return jsonify(error="Email address already registered"), 409 # Conflict

            # Create new user
            user_id = str(uuid.uuid4())
            # Default values for other fields can be set here or by DB schema defaults
            cur.execute(
                """
                INSERT INTO users (id, email, password_hash, created_at, updated_at,
                                   goal_slider, experience_level, unit_system, rir_bias)
                VALUES (%s, %s, %s, NOW(), NOW(), 0.5, 'beginner', 'metric', 0.0)
                RETURNING id, email, created_at;
                """,
                (user_id, email, hashed_password.decode('utf-8'))
            )
            new_user = cur.fetchone()
            conn.commit()
            logger.info(f"User registered successfully: {email} (ID: {user_id})")
            return jsonify(message="User registered successfully.", user=new_user), 201

    except psycopg2.Error as e:
        logger.error(f"Database error during registration: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed during registration"), 500
    except Exception as e:
        logger.error(f"Unexpected error during registration: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred during registration"), 500
    finally:
        if conn:
            conn.close()

@app.route('/v1/auth/login', methods=['POST'])
def login_user():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify(error="Email and password are required"), 400

    email = data['email'].lower()
    password = data['password']

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, password_hash FROM users WHERE email = %s;", (email,))
            user_record = cur.fetchone()

            if not user_record:
                logger.warning(f"Login attempt failed for non-existent email: {email}")
                return jsonify(error="Invalid credentials"), 401

            if bcrypt.checkpw(password.encode('utf-8'), user_record['password_hash'].encode('utf-8')):
                # Password matches, generate JWT
                token_payload = {
                    'user_id': str(user_record['id']),
                    'exp': datetime.now(timezone.utc) + app.config['JWT_ACCESS_TOKEN_EXPIRES']
                    # 'iat': datetime.now(timezone.utc) # Optional: Issued at
                }
                access_token = jwt.encode(token_payload, app.config['JWT_SECRET_KEY'], algorithm="HS256")

                logger.info(f"User logged in successfully: {email}")
                return jsonify(access_token=access_token), 200
            else:
                logger.warning(f"Login attempt failed for email (invalid password): {email}")
                return jsonify(error="Invalid credentials"), 401

    except psycopg2.Error as e:
        logger.error(f"Database error during login: {e}")
        return jsonify(error="Database operation failed during login"), 500
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred during login"), 500
    finally:
        if conn:
            conn.close()

# --- User Profile Management APIs (P1-BE-009) ---
@app.route('/v1/users/<uuid:user_id>/profile', methods=['GET'])
@jwt_required
def get_user_profile(user_id):
    from flask import g # Import g here or ensure it's available
    # Ensure the authenticated user can only access their own profile
    # The user_id in the path should match the one in the token (g.current_user_id)
    if str(user_id) != g.current_user_id:
        logger.warning(f"Forbidden attempt to access profile. Token user: {g.current_user_id}, Path user: {user_id}")
        return jsonify(error="Forbidden. You can only access your own profile."), 403

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, email, name, birth_date, gender, goal_slider,
                       experience_level, unit_system, available_plates,
                       created_at, updated_at
                FROM users WHERE id = %s;
                """, (str(user_id),)
            )
            profile = cur.fetchone()
            if not profile:
                return jsonify(error="User profile not found"), 404

            # Convert available_plates from JSON string in DB to list/dict if needed by frontend
            # Assuming it's stored as JSONB and psycopg2 handles it.
            return jsonify(profile), 200

    except psycopg2.Error as e:
        logger.error(f"Database error fetching profile for user {user_id}: {e}")
        return jsonify(error="Database operation failed"), 500
    except Exception as e:
        logger.error(f"Unexpected error fetching profile for user {user_id}: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred"), 500
    finally:
        if conn:
            conn.close()

@app.route('/v1/users/<uuid:user_id>/profile', methods=['PUT'])
@jwt_required
def update_user_profile(user_id):
    from flask import g
    if str(user_id) != g.current_user_id:
        logger.warning(f"Forbidden attempt to update profile. Token user: {g.current_user_id}, Path user: {user_id}")
        return jsonify(error="Forbidden. You can only update your own profile."), 403

    data = request.get_json()
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    # Fields that can be updated by the user
    allowed_fields = {
        'name': str, 'birth_date': str, 'gender': str,
        'goal_slider': float, 'experience_level': str,
        'unit_system': str, 'available_plates': dict # Or list, depending on expected structure
    }

    update_fields = []
    update_values = []

    for field, field_type in allowed_fields.items():
        if field in data:
            value = data[field]
            # Basic type validation, can be more sophisticated
            if value is not None and not isinstance(value, field_type):
                if field == 'birth_date': # Allow None for birth_date
                    pass
                elif field_type is float and isinstance(value, int):  # Allow int for float fields
                    value = float(value)
                else:
                    return jsonify(error=f"Invalid type for field '{field}'. Expected {field_type.__name__}."), 400

            # Specific validation for certain fields
            if field == 'gender' and value not in [None, 'male', 'female', 'other', 'prefer_not_to_say']:
                return jsonify(error="Invalid value for 'gender'"), 400
            if field == 'experience_level' and value not in [None, 'beginner', 'intermediate', 'advanced']:
                return jsonify(error="Invalid value for 'experience_level'"), 400
            if field == 'unit_system' and value not in [None, 'metric', 'imperial']:
                return jsonify(error="Invalid value for 'unit_system'"), 400
            if field == 'goal_slider' and value is not None and not (0.0 <= value <= 1.0):
                 return jsonify(error="'goal_slider' must be between 0.0 and 1.0"), 400


            update_fields.append(f"{field} = %s")
            # For JSONB fields like available_plates, ensure it's passed as a JSON string or use psycopg2.extras.Json
            if field == 'available_plates' and value is not None:
                 update_values.append(psycopg2.extras.Json(value))
            else:
                update_values.append(value)

    if not update_fields:
        return jsonify(error="No valid fields provided for update"), 400

    update_fields.append("updated_at = NOW()")

    query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s RETURNING *;"
    update_values.append(str(user_id))

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, tuple(update_values))
            updated_profile = cur.fetchone()
            if not updated_profile: # Should not happen if ID is correct and record exists
                return jsonify(error="Failed to update or find profile after update."), 500

            # Remove password_hash before returning
            if 'password_hash' in updated_profile:
                del updated_profile['password_hash']

            conn.commit()
            logger.info(f"User profile updated successfully for user: {user_id}")
            return jsonify(updated_profile), 200

    except psycopg2.Error as e:
        logger.error(f"Database error updating profile for user {user_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed during profile update"), 500
    except Exception as e:
        logger.error(f"Unexpected error updating profile for user {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred during profile update"), 500
    finally:
        if conn:
            conn.close()

# --- Basic CRUD APIs for Exercises (P1-BE-010) ---
@app.route('/v1/exercises', methods=['GET'])
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
            conn.close()

@app.route('/v1/exercises/<uuid:exercise_id>', methods=['GET'])
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
            conn.close()

# --- Basic CRUD APIs for Workout Logging (P1-BE-011) ---
@app.route('/v1/users/<uuid:user_id>/workouts', methods=['POST'])
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
        conn = get_db_connection()
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
            conn.close()

@app.route('/v1/users/<uuid:user_id>/workouts', methods=['GET'])
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
            conn.close()

@app.route('/v1/workouts/<uuid:workout_id>', methods=['GET'])
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
            conn.close()

@app.route('/v1/workouts/<uuid:workout_id>/sets', methods=['POST'])
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
            conn.close()


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

# --- Plateau Detection and Deload Suggestion Logic ---
from typing import List, Dict, Any # Already imported math, uuid
import random
from pprint import pprint

from engine.progression import detect_plateau, generate_deload_protocol, PlateauStatus

def _get_mock_historical_performance_data(
    scenario: str = "stagnation",
    lookback_period: int = 10,
    base_value: float = 100.0
) -> List[float]:
    """Generates mock historical performance data for testing."""
    data = []
    if scenario == "progression":
        data = [base_value + i * 0.5 for i in range(lookback_period)] # Steady small gains
    elif scenario == "stagnation":
        data = [base_value + (i * 0.1 if i < lookback_period / 2 else (lookback_period / 2 * 0.1) + random.uniform(-0.1, 0.1) ) for i in range(lookback_period)]
    elif scenario == "regression":
        data = [base_value - i * 0.5 for i in range(lookback_period)] # Steady decline
    elif scenario == "short_history":
        data = [base_value, base_value + 0.5] # Not enough data for min_duration=3 or 5
    elif scenario == "volatile":
        # Creates a sine wave pattern, could be tricky for simple linear regression
        data = [base_value + 5 * math.sin(math.pi * i / (lookback_period/2)) + random.uniform(-1,1) for i in range(lookback_period)]
    elif scenario == "initial_gains_then_stagnation":
        half_period = lookback_period // 2
        data = [base_value + i * 1.0 for i in range(half_period)]
        stagnation_value = data[-1]
        data.extend([stagnation_value + random.uniform(-0.2, 0.2) for _ in range(lookback_period - half_period)])
    else: # Default to stagnation
        data = [base_value + random.uniform(-0.2, 0.2) for _ in range(lookback_period)]

    return [round(x, 2) for x in data]

def check_for_plateau_and_suggest_deload(
    user_id: str,
    exercise_id: str,
    historical_performance_data: List[float] = None,
    mock_scenario: str = "stagnation", # Used if historical_performance_data is None
    mock_fatigue: float = 40.0,
    plateau_min_duration: int = 5 # Default min_duration for plateau detection
) -> Dict[str, Any]:
    """
    Checks for plateaus using historical data and suggests a deload if needed.
    If historical_performance_data is None, mock data is generated based on mock_scenario.
    """
    if historical_performance_data is None:
        logger.info(f"No historical data provided for user {user_id}, exercise {exercise_id}. Generating mock data for scenario: {mock_scenario}.")
        historical_performance_data = _get_mock_historical_performance_data(
            scenario=mock_scenario,
            lookback_period=max(10, plateau_min_duration + 2) # Ensure enough data for lookback
        )

    plateau_result = detect_plateau(
        values=historical_performance_data,
        min_duration=plateau_min_duration
        # Using default threshold from detect_plateau
    )

    result = {
        "user_id": user_id,
        "exercise_id": exercise_id,
        "sample_historical_data": historical_performance_data[:5], # Show a sample
        "plateau_check_details": plateau_result,
        "deload_suggested": False,
        "deload_protocol": None,
        "user_notification": ""
    }

    if plateau_result['plateauing']:
        status = plateau_result['status']
        plateau_severity = 0.0
        if status == PlateauStatus.REGRESSION:
            plateau_severity = 0.8
        elif status == PlateauStatus.STAGNATION:
            plateau_severity = 0.5
        elif status in [PlateauStatus.REGRESSION_WARNING, PlateauStatus.STAGNATION_WARNING]:
            plateau_severity = 0.3

        # Determine deload duration
        deload_duration_weeks = 2 if plateau_severity >= 0.7 else 1

        # Generate deload protocol
        deload_protocol = generate_deload_protocol(
            plateau_severity=plateau_severity,
            deload_duration_weeks=deload_duration_weeks,
            recent_fatigue_score=mock_fatigue # Using the mock_fatigue passed in
        )

        result["deload_suggested"] = True
        result["deload_protocol"] = deload_protocol
        result["user_notification"] = (
            f"Plateau detected for exercise {exercise_id} (Status: {status.name}, Slope: {plateau_result['slope']:.3f}). "
            f"A {deload_duration_weeks}-week deload is suggested."
        )

        logger.info(f"INFO: Storing deload protocol for user {user_id}, exercise {exercise_id}.")
        logger.info(f"User Notification: {result['user_notification']}")
        logger.info(f"Deload Protocol: {deload_protocol}")


    return result


if __name__ == '__main__':
    _conn_check = None
    try:
        # Keep existing DB check
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

    # --- Test Plateau Detection and Deload Suggestion ---
    print("\n--- Testing Plateau Detection and Deload Integration ---")
    test_user_id = "user_test_123"
    test_exercise_id = "exercise_bench_press"

    scenarios_to_test = [
        {"name": "Clear Progression", "scenario": "progression", "fatigue": 20.0},
        {"name": "Stagnation (Moderate Fatigue)", "scenario": "stagnation", "fatigue": 50.0},
        {"name": "Stagnation (High Fatigue)", "scenario": "stagnation", "fatigue": 75.0},
        {"name": "Regression", "scenario": "regression", "fatigue": 60.0},
        {"name": "Short History", "scenario": "short_history", "fatigue": 30.0},
        {"name": "Volatile Data", "scenario": "volatile", "fatigue": 40.0},
        {"name": "Initial Gains then Stagnation", "scenario": "initial_gains_then_stagnation", "fatigue": 55.0}
    ]

    for test_case in scenarios_to_test:
        print(f"\n--- Scenario: {test_case['name']} (Fatigue: {test_case['fatigue']}) ---")
        result = check_for_plateau_and_suggest_deload(
            user_id=test_user_id,
            exercise_id=test_exercise_id,
            mock_scenario=test_case["scenario"],
            mock_fatigue=test_case["fatigue"],
            plateau_min_duration=5 # Using min_duration of 5 for these tests
        )
        # Using pprint for better readability of the dictionary
        pprint(result, indent=2)
        print("--------------------------------------------------")

    # Example with directly passed historical data
    print("\n--- Scenario: Direct Data - Clear Regression ---")
    direct_data = [110.0, 108.0, 107.5, 106.0, 105.0, 103.0, 102.0]
    result_direct = check_for_plateau_and_suggest_deload(
        user_id=test_user_id,
        exercise_id="exercise_squat",
        historical_performance_data=direct_data,
        mock_fatigue=70.0,
        plateau_min_duration=4 # Test with different min_duration
    )
    pprint(result_direct, indent=2)
    print("--------------------------------------------------")

    # Keep the Flask app run command if this file is also meant to be executable as a server
    # For subtask testing, the print statements above are the primary output.
    # If running in a CI/test environment where the Flask app shouldn't start,
    # you might guard app.run with a specific condition.
    # For now, assuming it's fine as is.
    app.run(host='0.0.0.0', port=5000, debug=True)
