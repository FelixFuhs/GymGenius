from flask import Flask, request, jsonify, render_template
import psycopg2
import psycopg2.extras  # For RealDictCursor
import os
from urllib.parse import urlparse # Add this import
from datetime import timedelta, datetime, timezone # Added datetime, timezone
import logging
import jwt # For JWT generation and decoding
from functools import wraps # For creating decorators
import atexit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

# --- Rate Limiter Configuration ---
# Use a dedicated Redis instance or a different DB number if sharing with RQ
RATELIMIT_STORAGE_URL = os.getenv("RATELIMIT_STORAGE_URL", "redis://localhost:6379/1")
limiter = Limiter(
    key_func=get_remote_address, # <--- ADD key_func= HERE
    default_limits=["200 per day", "50 per hour"],
    storage_uri=RATELIMIT_STORAGE_URL,
    strategy="fixed-window",
)
limiter.init_app(app)


# --- Database Connection Pool Configuration ---
MIN_DB_CONNECTIONS = 1
MAX_DB_CONNECTIONS = 10 # Adjust as needed based on expected load
db_pool = None

def get_db_connection_params():
    """Determines database connection parameters."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            url = urlparse(database_url)
            return {
                'dbname': url.path[1:],
                'user': url.username,
                'password': url.password,
                'host': url.hostname,
                'port': url.port
            }
        except Exception as e:
            app.logger.error(f"Failed to parse DATABASE_URL: {e}. Falling back to POSTGRES_* vars.")
            # Fall through to original method if DATABASE_URL connection fails
            pass

    return {
        'dbname': os.getenv("POSTGRES_DB"),
        'user': os.getenv("POSTGRES_USER"),
        'password': os.getenv("POSTGRES_PASSWORD"),
        'host': os.getenv("POSTGRES_HOST"),
        'port': os.getenv("POSTGRES_PORT", "5432") # Provide default port
    }

def init_db_pool():
    """Initializes the database connection pool."""
    global db_pool
    if db_pool is None:
        try:
            params = get_db_connection_params()
            if not all(params.values()): # Check if any crucial param is None or empty
                 app.logger.error("Database connection parameters are incomplete. Pool not initialized.")
                 # Depending on strictness, could raise an error or prevent app startup
                 return

            app.logger.info(f"Initializing database connection pool for host '{params.get('host')}' db '{params.get('dbname')}'")
            db_pool = psycopg2.pool.SimpleConnectionPool(
                MIN_DB_CONNECTIONS,
                MAX_DB_CONNECTIONS,
                **params
            )
            app.logger.info("Database connection pool initialized successfully.")
        except psycopg2.OperationalError as e:
            app.logger.error(f"Failed to initialize database pool: {e}")
            # This is a critical error, might want to exit or prevent app from serving requests
            raise
        except Exception as e:
            app.logger.error(f"An unexpected error occurred during pool initialization: {e}")
            raise

init_db_pool() # Initialize the pool when the app module is loaded

# Register a function to close the pool when the application exits
@atexit.register
def close_db_pool():
    global db_pool
    if db_pool:
        app.logger.info("Closing database connection pool.")
        db_pool.closeall()
        db_pool = None

# --- JWT Configuration ---
# In a real app, use a strong, randomly generated key stored securely (e.g., env variable)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1) # Access token valid for 1 hour
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=7) # Refresh token valid for 7 days

# Configure logging
logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__) # Use app.logger or a specific logger
# Use app.logger directly as it's configured by Flask
logger = app.logger


# --- Database Connection Helper ---
def get_db_connection():
    """Gets a connection from the database pool."""
    global db_pool
    if db_pool is None:
        logger.error("Database pool is not initialized. Attempting to re-initialize.")
        init_db_pool() # Attempt to re-initialize, though this might indicate a larger issue
        if db_pool is None: # If still None, raise an error
             logger.critical("Failed to re-initialize database pool. Cannot get connection.")
             raise Exception("Database pool not available.") # Or a more specific custom exception
    try:
        return db_pool.getconn()
    except psycopg2.pool.PoolError as e:
        logger.error(f"Failed to get connection from pool: {e}")
        # Potentially try to re-initialize the pool or handle specific pool errors
        raise

def release_db_connection(conn):
    """Releases a connection back to the database pool."""
    global db_pool
    if db_pool and conn:
        try:
            db_pool.putconn(conn)
        except psycopg2.pool.PoolError as e:
            logger.error(f"Error releasing connection back to pool: {e}")
            # Depending on the error, might want to close the connection explicitly
            # conn.close() if it's a "bad" connection not belonging to pool etc.
        except Exception as e: # Catch any other exception during putconn
            logger.error(f"Unexpected error releasing connection: {e}")


# --- JWT Blocklist Check ---
def check_if_revoked(jwt_payload):
    """
    Checks if the given JWT ID (jti) is in the blocklist.
    """
    jti = jwt_payload.get('jti')
    if not jti:
        # This should not happen if all tokens are issued with a jti
        logger.warning("JWT payload missing 'jti' claim for blocklist check.")
        # Depending on policy, could return True (treat as revoked) or False (ignore if no JTI)
        # For strict security, if a token *should* have a JTI but doesn't, it might be suspect.
        return True # Treat as revoked if jti is missing, or handle as an error

    conn = None
    try:
        conn = get_db_connection()
        # Using RealDictCursor is not strictly necessary here as we only need 'exists'
        # but keeping it consistent with other DB calls.
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT EXISTS (SELECT 1 FROM jwt_blocklist WHERE jti = %s);", (jti,))
            result = cur.fetchone()
            if result and result['exists']:
                logger.info(f"Token with JTI {jti} found in blocklist (revoked).")
                return True # Token is blocklisted
            return False # Token is not blocklisted
    except psycopg2.Error as e:
        logger.error(f"Database error during JTI blocklist check for {jti}: {e}")
        # In case of DB error, policy might be to deny access (fail-safe)
        return True # Conservatively treat as revoked or deny access
    except Exception as e:
        logger.error(f"Unexpected error during JTI blocklist check for {jti}: {e}", exc_info=True)
        return True # Conservatively treat as revoked
    finally:
        if conn:
            release_db_connection(conn)


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

            from flask import g  # Ensure g is imported

            # Store the entire decoded payload in g for potential use in routes (e.g., accessing jti)
            g.decoded_token_data = data

            # Check if the token has been revoked
            if check_if_revoked(data):
                logger.warning(f"Revoked token presented for user_id: {data.get('user_id')}, jti: {data.get('jti')}")
                return jsonify(message="Token has been revoked"), 401

            # Make user_id available to the decorated route via Flask's g object.
            # This is done *after* the revoke check.
            if 'user_id' not in data:
                logger.error("user_id not in JWT data after decoding and revoke check.")
                return jsonify(message="Invalid token: missing user_id"), 401

            g.current_user_id = data['user_id']

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
    # logger.error(f"Unhandled exception: {e}", exc_info=True) # Original
    app.logger.error(f"Unhandled exception: {e}", exc_info=True) # Use app.logger
    # Check if it's a pool error or general operational error
    if isinstance(e, psycopg2.pool.PoolError):
        return jsonify(error="Database pool error"), 503
    if isinstance(e, psycopg2.OperationalError): # This might catch issues from getconn if pool is down
        return jsonify(error="Database connection error"), 503
    # Add more specific error handlers if needed for different exception types
    return jsonify(error="An internal server error occurred"), 500


# --- Existing Endpoints ---


# Import blueprints after pool initialization and app context is more stable
from .blueprints.auth import auth_bp  # noqa: E402
from .blueprints.workouts import workouts_bp  # noqa: E402
from .blueprints.plans import plans_bp  # noqa: E402
from .blueprints.analytics import analytics_bp  # noqa: E402
from .blueprints.share import share_bp # noqa: E402
from .blueprints.export import export_bp # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(workouts_bp)
app.register_blueprint(plans_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(share_bp)
app.register_blueprint(export_bp)


# --- Public Route for Shared Workouts ---
@app.route('/share/<slug>', methods=['GET'])
def show_shared_workout(slug):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Query shared_workouts for the slug
            cur.execute(
                "SELECT workout_id, expires_at FROM shared_workouts WHERE slug = %s;",
                (slug,)
            )
            shared_link_data = cur.fetchone()

            if not shared_link_data:
                logger.info(f"Share link with slug '{slug}' not found.")
                return render_template('share_error.html', message="This share link is invalid."), 404

            # 2. Check expiry
            if shared_link_data['expires_at'] < datetime.now(timezone.utc):
                logger.info(f"Share link with slug '{slug}' has expired (expired at {shared_link_data['expires_at']}).")
                return render_template('share_error.html', message="This share link has expired."), 404 # Or 410 Gone

            workout_id = shared_link_data['workout_id']

            # 3. Fetch main workout details
            cur.execute(
                "SELECT id, user_id, notes, started_at, completed_at FROM workouts WHERE id = %s;",
                (workout_id,)
            )
            workout_details = cur.fetchone()

            if not workout_details:
                logger.error(f"Workout {workout_id} for share link {slug} not found in workouts table.")
                return render_template('share_error.html', message="The workout data could not be retrieved."), 404

            # For MVP, we don't fetch user's name. Can be added later if user profiles have display names.
            # workout_details['user_display_name'] = "A GymGenius User"


            # 4. Fetch associated sets, joining with exercises for exercise_name
            cur.execute(
                """
                SELECT ws.set_number, ws.actual_weight, ws.actual_reps, ws.actual_rir,
                       ws.notes, ws.mti, e.name as exercise_name
                FROM workout_sets ws
                JOIN exercises e ON ws.exercise_id = e.id
                WHERE ws.workout_id = %s
                ORDER BY ws.set_number ASC;
                """,
                (workout_id,)
            )
            sets_list = cur.fetchall()

            workout_data_for_template = {
                'started_at': workout_details['started_at'],
                'notes': workout_details['notes'],
                # 'user_display_name': workout_details['user_display_name'], # If added
                'sets': sets_list
            }

            return render_template('share_workout.html', workout=workout_data_for_template)

    except psycopg2.Error as e:
        logger.error(f"Database error retrieving shared workout for slug {slug}: {e}", exc_info=True)
        return render_template('share_error.html', message="Could not retrieve workout due to a database error."), 500
    except Exception as e:
        logger.error(f"Unexpected error retrieving shared workout for slug {slug}: {e}", exc_info=True)
        return render_template('share_error.html', message="An unexpected error occurred."), 500
    finally:
        if conn:
            release_db_connection(conn)
