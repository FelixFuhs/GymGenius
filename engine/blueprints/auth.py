from flask import Blueprint, request, jsonify
import uuid
import bcrypt
import jwt
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

import engine.app as app_module

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/v1/auth/register', methods=['POST'])
def register_user():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify(error="Email and password are required"), 400

    email = data['email'].lower()
    password = data['password']
    if len(password) < 8:
        return jsonify(error="Password must be at least 8 characters long"), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    conn = None
    try:
        conn = app_module.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
            if cur.fetchone():
                return jsonify(error="Email address already registered"), 409

            user_id = str(uuid.uuid4())
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
            app_module.logger.info(f"User registered successfully: {email} (ID: {user_id})")
            return jsonify(message="User registered successfully.", user=new_user), 201
    except psycopg2.Error as e:
        app_module.logger.error(f"Database error during registration: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed during registration"), 500
    except Exception as e:
        app_module.logger.error(f"Unexpected error during registration: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred during registration"), 500
    finally:
        if conn:
            conn.close()


@auth_bp.route('/v1/auth/login', methods=['POST'])
def login_user():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify(error="Email and password are required"), 400

    email = data['email'].lower()
    password = data['password']

    conn = None
    try:
        conn = app_module.get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, password_hash FROM users WHERE email = %s;", (email,))
            user_record = cur.fetchone()
            if not user_record:
                app_module.logger.warning(f"Login attempt failed for non-existent email: {email}")
                return jsonify(error="Invalid credentials"), 401

            if bcrypt.checkpw(password.encode('utf-8'), user_record['password_hash'].encode('utf-8')):
                token_payload = {
                    'user_id': str(user_record['id']),
                    'exp': datetime.now(timezone.utc) + app_module.app.config['JWT_ACCESS_TOKEN_EXPIRES']
                }
                access_token = jwt.encode(token_payload, app_module.app.config['JWT_SECRET_KEY'], algorithm="HS256")
                app_module.logger.info(f"User logged in successfully: {email}")
                return jsonify(access_token=access_token), 200
            else:
                app_module.logger.warning(f"Login attempt failed for email (invalid password): {email}")
                return jsonify(error="Invalid credentials"), 401
    except psycopg2.Error as e:
        app_module.logger.error(f"Database error during login: {e}")
        return jsonify(error="Database operation failed during login"), 500
    except Exception as e:
        app_module.logger.error(f"Unexpected error during login: {e}", exc_info=True)
        return jsonify(error="An unexpected error occurred during login"), 500
    finally:
        if conn:
            conn.close()
