from flask import Blueprint, request, jsonify, current_app, g, abort
from ..app import get_db_connection, release_db_connection, jwt_required, logger, limiter # Import limiter
import psycopg2
import psycopg2.extras
import uuid
import bcrypt
import jwt
from datetime import datetime, timezone

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/v1/auth/register', methods=['POST'])
@limiter.limit("5 per hour")
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
            release_db_connection(conn)

@auth_bp.route('/v1/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
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
                jti = str(uuid.uuid4())
                token_payload = {
                    'user_id': str(user_record['id']),
                    'exp': datetime.now(timezone.utc) + current_app.config['JWT_ACCESS_TOKEN_EXPIRES'],
                    # 'iat': datetime.now(timezone.utc) # Optional: Issued at
                    'jti': jti  # Add JTI (JWT ID) claim to access token
                }
                access_token = jwt.encode(token_payload, current_app.config['JWT_SECRET_KEY'], algorithm="HS256")

                # Generate Refresh Token
                refresh_token_jti = str(uuid.uuid4()) # Also add JTI to refresh token for completeness if needed later
                refresh_token_payload = {
                    'user_id': str(user_record['id']),
                    'exp': datetime.now(timezone.utc) + current_app.config['JWT_REFRESH_TOKEN_EXPIRES'],
                    'jti': refresh_token_jti # JTI for refresh token
                }
                refresh_token = jwt.encode(refresh_token_payload, current_app.config['JWT_SECRET_KEY'], algorithm="HS256")

                # Store refresh token in the database
                cur.execute(
                    "INSERT INTO user_refresh_tokens (user_id, token) VALUES (%s, %s)",
                    (user_record['id'], refresh_token)
                )
                conn.commit()

                logger.info(f"User logged in successfully: {email}")
                return jsonify(access_token=access_token, refresh_token=refresh_token), 200
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
            release_db_connection(conn)


@auth_bp.route('/v1/auth/logout', methods=['POST'])
@jwt_required
@limiter.limit("20/hour")
def logout_user():
    user_id = g.current_user_id
    # Assuming jti is available in g.decoded_token_data after jwt_required modification
    # This will be g.decoded_token_data['jti']
    access_token_jti = g.decoded_token_data.get('jti')
    if not access_token_jti:
        # This case should ideally not be reached if tokens always have JTI
        # and jwt_required ensures decoded_token_data is populated.
        logger.error(f"JTI not found in token for user_id: {user_id} during logout.")
        return jsonify(error="Token is missing JTI, cannot process logout."), 500

    data = request.get_json()
    if not data or not data.get('refresh_token'):
        logger.warning(f"Logout attempt without refresh token for user_id: {user_id}")
        abort(400, description="Refresh token is required.")

    refresh_token = data['refresh_token']

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Add access token's JTI to the blocklist
            cur.execute(
                "INSERT INTO jwt_blocklist (jti) VALUES (%s) ON CONFLICT (jti) DO NOTHING;",
                (access_token_jti,)
            )
            logger.info(f"Access token JTI {access_token_jti} for user {user_id} added to blocklist.")

            # Delete the provided refresh token from user_refresh_tokens
            cur.execute(
                "DELETE FROM user_refresh_tokens WHERE user_id = %s AND token = %s;",
                (user_id, refresh_token)
            )
            deleted_count = cur.rowcount
            if deleted_count > 0:
                logger.info(f"Refresh token for user {user_id} deleted from database.")
            else:
                logger.warning(f"Refresh token for user {user_id} not found in database during logout.")

            conn.commit()

        return jsonify(msg="Successfully logged out"), 200

    except psycopg2.Error as e:
        logger.error(f"Database error during logout for user {user_id}: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed during logout"), 500
    except Exception as e:
        logger.error(f"Unexpected error during logout for user {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred during logout"), 500
    finally:
        if conn:
            release_db_connection(conn)


@auth_bp.route('/v1/auth/refresh', methods=['POST'])
@limiter.limit("20 per hour")
def refresh_token():
    data = request.get_json()
    if not data or not data.get('refresh_token'):
        return jsonify(error="Refresh token is required"), 400

    refresh_token_from_request = data['refresh_token']
    conn = None
    try:
        # Decode the refresh token to check expiry and get user_id
        payload = jwt.decode(
            refresh_token_from_request,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=["HS256"]
        )
        user_id = payload['user_id']

        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Check if the refresh token exists in the database for the user
            cur.execute(
                "SELECT token FROM user_refresh_tokens WHERE user_id = %s AND token = %s",
                (user_id, refresh_token_from_request)
            )
            stored_token = cur.fetchone()

            if not stored_token:
                logger.warning(f"Refresh token not found in DB or mismatch for user_id: {user_id}")
                # It's good practice to invalidate all refresh tokens for this user if a potentially compromised token is used.
                # cur.execute("DELETE FROM user_refresh_tokens WHERE user_id = %s", (user_id,))
                # conn.commit()
                return jsonify(error="Invalid or expired refresh token"), 401

            # Token is valid and found in DB, issue a new access token
            # Token is valid and found in DB, issue a new access token
            new_access_token_jti = str(uuid.uuid4())
            access_token_payload = {
                'user_id': user_id,
                'exp': datetime.now(timezone.utc) + current_app.config['JWT_ACCESS_TOKEN_EXPIRES'],
                'jti': new_access_token_jti # Add JTI to new access tokens
            }
            new_access_token = jwt.encode(
                access_token_payload,
                current_app.config['JWT_SECRET_KEY'],
                algorithm="HS256"
            )
            logger.info(f"Access token refreshed for user_id: {user_id}")
            return jsonify(access_token=new_access_token), 200

    except jwt.ExpiredSignatureError:
        logger.warning("Expired refresh token presented.")
        # Optionally, remove the expired token from DB
        # payload = jwt.decode(refresh_token_from_request, algorithms=["HS256"], options={"verify_signature": False, "verify_exp": False}) # decode without verification to get user_id if needed for cleanup
        # if conn and payload and 'user_id' in payload:
        #     with conn.cursor() as cur: # Re-use or get new cursor
        #         cur.execute("DELETE FROM user_refresh_tokens WHERE token = %s", (refresh_token_from_request,))
        #         conn.commit()
        return jsonify(error="Refresh token has expired"), 401
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid refresh token: {e}")
        return jsonify(error="Invalid refresh token"), 401
    except psycopg2.Error as e:
        logger.error(f"Database error during token refresh: {e}")
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed during token refresh"), 500
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred during token refresh"), 500
    finally:
        if conn:
            release_db_connection(conn)

# --- User Profile Management APIs (P1-BE-009) ---
@auth_bp.route('/v1/users/<uuid:user_id>/profile', methods=['GET'])
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
                       created_at, updated_at, rir_bias, rir_bias_lr, rir_bias_error_ema
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
            release_db_connection(conn)

@auth_bp.route('/v1/users/<uuid:user_id>/profile', methods=['PUT'])
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
            release_db_connection(conn)


