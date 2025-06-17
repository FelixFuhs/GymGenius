from flask import Flask, request, jsonify
import psycopg2
import psycopg2.extras # For RealDictCursor
import os
from urllib.parse import urlparse # Add this import
from datetime import timedelta
import logging
import jwt # For JWT generation and decoding
from functools import wraps # For creating decorators

app = Flask(__name__)

# --- JWT Configuration ---
# In a real app, use a strong, randomly generated key stored securely (e.g., env variable)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
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
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),  # In CI, this will be 'postgres' or 'localhost' for service container
            port=os.getenv("POSTGRES_PORT")
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


from .blueprints.auth import auth_bp  # noqa: E402
from .blueprints.workouts import workouts_bp  # noqa: E402
from .blueprints.plans import plans_bp  # noqa: E402
from .blueprints.analytics import analytics_bp  # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(workouts_bp)
app.register_blueprint(plans_bp)
app.register_blueprint(analytics_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
