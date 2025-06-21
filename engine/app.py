from flask import Flask, request, jsonify, render_template
import psycopg2
import psycopg2.extras
from psycopg2 import pool
import os
from urllib.parse import urlparse
from datetime import timedelta, datetime, timezone
import logging
import jwt
from functools import wraps
import atexit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

# --- Rate Limiter Configuration ---
RATELIMIT_STORAGE_URL = os.getenv("RATELIMIT_STORAGE_URL", "redis://localhost:6379/1")
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=RATELIMIT_STORAGE_URL,
    strategy="fixed-window",
)
limiter.init_app(app)


# --- Database Connection Pool Configuration ---
MIN_DB_CONNECTIONS = 1
MAX_DB_CONNECTIONS = 10
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
            pass

    return {
        'dbname': os.getenv("POSTGRES_DB"),
        'user': os.getenv("POSTGRES_USER"),
        'password': os.getenv("POSTGRES_PASSWORD"),
        'host': os.getenv("POSTGRES_HOST"),
        'port': os.getenv("POSTGRES_PORT", "5432")
    }

def init_db_pool():
    """Initializes the database connection pool."""
    global db_pool
    if db_pool is None:
        try:
            params = get_db_connection_params()
            if not all(params.values()):
                 app.logger.error("Database connection parameters are incomplete. Pool not initialized.")
                 return

            app.logger.info(f"Initializing database connection pool for host '{params.get('host')}' db '{params.get('dbname')}'")
            db_pool = pool.SimpleConnectionPool(
                MIN_DB_CONNECTIONS,
                MAX_DB_CONNECTIONS,
                **params
            )
            app.logger.info("Database connection pool initialized successfully.")
        except psycopg2.OperationalError as e:
            app.logger.error(f"Failed to initialize database pool: {e}")
            raise
        except Exception as e:
            app.logger.error(f"An unexpected error occurred during pool initialization: {e}")
            raise

init_db_pool()

@atexit.register
def close_db_pool():
    global db_pool
    if db_pool:
        app.logger.info("Closing database connection pool.")
        db_pool.closeall()
        db_pool = None

# --- JWT Configuration ---
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=7)

logging.basicConfig(level=logging.INFO)
logger = app.logger


# --- Database Connection Helper ---
def get_db_connection():
    """Gets a connection from the database pool."""
    global db_pool
    if db_pool is None:
        logger.error("Database pool is not initialized. Attempting to re-initialize.")
        init_db_pool()
        if db_pool is None:
             logger.critical("Failed to re-initialize database pool. Cannot get connection.")
             raise Exception("Database pool not available.")
    try:
        return db_pool.getconn()
    except psycopg2.pool.PoolError as e:
        logger.error(f"Failed to get connection from pool: {e}")
        raise

def release_db_connection(conn):
    """Releases a connection back to the database pool."""
    global db_pool
    if db_pool and conn:
        try:
            db_pool.putconn(conn)
        except psycopg2.pool.PoolError as e:
            logger.error(f"Error releasing connection back to pool: {e}")
        except Exception as e:
            logger.error(f"Unexpected error releasing connection: {e}")


# --- JWT Blocklist Check ---
def check_if_revoked(jwt_payload):
    jti = jwt_payload.get('jti')
    if not jti:
        logger.warning("JWT payload missing 'jti' claim for blocklist check.")
        return True

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT EXISTS (SELECT 1 FROM jwt_blocklist WHERE jti = %s);", (jti,))
            result = cur.fetchone()
            if result and result['exists']:
                logger.info(f"Token with JTI {jti} found in blocklist (revoked).")
                return True
            return False
    except psycopg2.Error as e:
        logger.error(f"Database error during JTI blocklist check for {jti}: {e}")
        return True
    except Exception as e:
        logger.error(f"Unexpected error during JTI blocklist check for {jti}: {e}", exc_info=True)
        return True
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
            elif len(parts) == 1:
                token = parts[0]


        if not token:
            logger.warning("JWT token is missing")
            return jsonify(message="Authentication token is missing!"), 401

        try:
            from flask import g

            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            g.decoded_token_data = data

            if check_if_revoked(data):
                logger.warning(f"Revoked token presented for user_id: {data.get('user_id')}, jti: {data.get('jti')}")
                return jsonify(message="Token has been revoked"), 401
            
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
    app.logger.error(f"Unhandled exception: {e}", exc_info=True)
    if isinstance(e, psycopg2.pool.PoolError):
        return jsonify(error="Database pool error"), 503
    if isinstance(e, psycopg2.OperationalError):
        return jsonify(error="Database connection error"), 503
    return jsonify(error="An internal server error occurred"), 500


# --- Public Route for Shared Workouts ---
@app.route('/share/<slug>', methods=['GET'])
def show_shared_workout(slug):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT workout_id, expires_at FROM shared_workouts WHERE slug = %s;",
                (slug,)
            )
            shared_link_data = cur.fetchone()

            if not shared_link_data:
                logger.info(f"Share link with slug '{slug}' not found.")
                return render_template('share_error.html', message="This share link is invalid."), 404

            if shared_link_data['expires_at'] < datetime.now(timezone.utc):
                logger.info(f"Share link with slug '{slug}' has expired (expired at {shared_link_data['expires_at']}).")
                return render_template('share_error.html', message="This share link has expired."), 404

            workout_id = shared_link_data['workout_id']

            cur.execute(
                "SELECT id, user_id, notes, started_at, completed_at FROM workouts WHERE id = %s;",
                (workout_id,)
            )
            workout_details = cur.fetchone()

            if not workout_details:
                logger.error(f"Workout {workout_id} for share link {slug} not found in workouts table.")
                return render_template('share_error.html', message="The workout data could not be retrieved."), 404

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


# --- Register Blueprints (MOVED TO THE BOTTOM TO FIX CIRCULAR IMPORT) ---
from blueprints.auth import auth_bp
from blueprints.workouts import workouts_bp
from blueprints.plans import plans_bp
from blueprints.analytics import analytics_bp
from blueprints.share import share_bp
from blueprints.export import export_bp

app.register_blueprint(auth_bp)
app.register_blueprint(workouts_bp)
app.register_blueprint(plans_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(share_bp)
app.register_blueprint(export_bp)