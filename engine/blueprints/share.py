from flask import Blueprint, jsonify, request, current_app
from flask import g # For accessing g.current_user_id
from app import get_db_connection, release_db_connection, jwt_required, logger
import uuid
from datetime import datetime, timezone, timedelta
import secrets # For generating unique slugs
import psycopg2 # For database error handling

share_bp = Blueprint('share', __name__, url_prefix='/v1/share')

MAX_SLUG_GENERATION_ATTEMPTS = 5

def generate_unique_slug(cursor):
    """Generates a unique 10-character slug for a shared workout."""
    for _ in range(MAX_SLUG_GENERATION_ATTEMPTS):
        # secrets.token_hex(5) generates 10 hex characters
        slug = secrets.token_hex(5)
        cursor.execute("SELECT 1 FROM shared_workouts WHERE slug = %s;", (slug,))
        if not cursor.fetchone():
            return slug
    raise Exception("Failed to generate a unique slug after multiple attempts.")


@share_bp.route('/workout/<uuid:workout_id>', methods=['POST'])
@jwt_required
def share_workout_link(workout_id): # Renamed to avoid conflict with workout_id param if it were a var
    user_id = g.current_user_id
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Ownership Check: Verify the workout belongs to the authenticated user
            cur.execute("SELECT id FROM workouts WHERE id = %s AND user_id = %s;", (str(workout_id), user_id))
            workout = cur.fetchone()
            if not workout:
                logger.warning(f"User {user_id} attempt to share non-owned or non-existent workout {workout_id}.")
                # Return 404 as per spec, could also be 403 if workout exists but not owned by this user.
                return jsonify(error="Workout not found or access denied."), 404

            # 2. Generate Slug
            try:
                slug = generate_unique_slug(cur)
            except Exception as slug_exc:
                logger.error(f"Failed to generate unique slug for workout {workout_id}: {slug_exc}")
                return jsonify(error="Could not generate a unique share identifier."), 500

            # 3. Set Expiry (e.g., 7 days from now)
            expires_at = datetime.now(timezone.utc) + timedelta(days=current_app.config.get('SHARE_LINK_EXPIRY_DAYS', 7))

            # 4. Database Insert
            shared_workout_id = uuid.uuid4()
            created_at = datetime.now(timezone.utc)

            cur.execute(
                """
                INSERT INTO shared_workouts (id, workout_id, slug, expires_at, created_at)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (str(shared_workout_id), str(workout_id), slug, expires_at, created_at)
            )
            conn.commit()

            # 5. Return URL
            # The public link should not have the /v1/api prefix.
            # It should point to a new root-level /share/{slug} endpoint (to be created later).
            # request.host_url will give e.g. "http://localhost:5000/"
            # We need to ensure the share URL is constructed correctly based on deployment.
            # For now, assuming a simple structure.
            # The actual frontend route for viewing a shared workout might be different.
            # This URL is what a user would share.
            base_url = request.host_url.rstrip('/')
            shareable_url = f"{base_url}/share/{slug}" # Public access route

            logger.info(f"Workout {workout_id} shared by user {user_id} with slug {slug}. URL: {shareable_url}")
            return jsonify({"share_url": shareable_url, "slug": slug, "expires_at": expires_at.isoformat()}), 200

    except psycopg2.Error as e:
        logger.error(f"Database error sharing workout {workout_id} for user {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="Database operation failed."), 500
    except Exception as e:
        logger.error(f"Unexpected error sharing workout {workout_id} for user {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify(error="An unexpected error occurred."), 500
    finally:
        if conn:
            release_db_connection(conn)
