from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras  # For RealDictCursor
import os
from urllib.parse import urlparse # Add this import
from datetime import timedelta
import logging
import jwt # For JWT generation and decoding
from functools import wraps # For creating decorators
import atexit

app = Flask(__name__)

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

app.register_blueprint(auth_bp)
app.register_blueprint(workouts_bp)
app.register_blueprint(plans_bp)
app.register_blueprint(analytics_bp)
