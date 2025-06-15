from flask import Flask, request, jsonify
import os
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
import logging
import psycopg2
import psycopg2.extras
import bcrypt
import jwt
from functools import wraps

from predictions import extended_epley_1rm
from engine.learning_models import (
    update_user_rir_bias,
    calculate_current_fatigue,
    DEFAULT_RECOVERY_TAU_MAP,
    SessionRecord,
)
from engine.progression import detect_plateau, generate_deload_protocol, PlateauStatus

app = Flask(__name__)

# JWT config
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-super-secret-jwt-key-please-change')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            url = urlparse(database_url)
            conn = psycopg2.connect(
                dbname=url.path[1:],
                user=url.username,
                password=url.password,
                host=url.hostname,
                port=url.port,
            )
            return conn
        except Exception as e:
            logger.error(f"Failed to connect using DATABASE_URL: {e}. Falling back to POSTGRES_* vars.")
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB", "gymgenius_dev"),
            user=os.getenv("POSTGRES_USER", "gymgenius"),
            password=os.getenv("POSTGRES_PASSWORD", "secret"),
            host=os.getenv("POSTGRES_HOST", "db"),
            port=os.getenv("POSTGRES_PORT", "5432"),
        )
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection error (POSTGRES_* vars): {e}")
        raise


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
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            from flask import g
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
    logger.error(f"Unhandled exception: {e}", exc_info=True)
    if isinstance(e, psycopg2.OperationalError):
        return jsonify(error="Database connection error"), 503
    return jsonify(error="An internal server error occurred"), 500


# Blueprint registrations
from engine.blueprints.auth import auth_bp
from engine.blueprints.workouts import workouts_bp
from engine.blueprints.plans import plans_bp
from engine.blueprints.analytics import analytics_bp

app.register_blueprint(auth_bp)
app.register_blueprint(workouts_bp)
app.register_blueprint(plans_bp)
app.register_blueprint(analytics_bp)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
