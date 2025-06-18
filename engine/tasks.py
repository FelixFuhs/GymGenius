import os
import logging
import psycopg2
import psycopg2.extras
from redis import Redis
from rq import Queue, Retry, get_current_job

from .app import get_db_connection

logger = logging.getLogger(__name__)

# Redis connection for RQ
redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_conn = Redis.from_url(redis_url)

# Default queue used by the API and worker
queue = Queue("training", connection=redis_conn)

DEFAULT_RETRY = Retry(max=3, interval=[10, 30, 60])


def enqueue_nightly_user_model_update(task_name="nightly_user_model_update", force_run=False):
    """Enqueue nightly update with retry strategy."""
    return queue.enqueue(
        nightly_user_model_update,
        task_name=task_name,
        force_run=force_run,
        retry=DEFAULT_RETRY,
    )

def nightly_user_model_update(task_name="nightly_user_model_update", force_run=False):
    """Process nightly per-user training tasks."""
    job = get_current_job()
    if job and job.meta.get("retry_count", 0) > 0:
        logger.info(
            "Retry attempt %s for job %s", job.meta["retry_count"], job.id
        )

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, email FROM users;")
            users = cur.fetchall()
        logger.info("--- Starting Nightly Training Tasks ---")
        for user in users:
            user_id = str(user["id"])
            user_email = user["email"]
            logger.info(
                "Simulating training tasks for user_id: %s (Email: %s)...",
                user_id,
                user_email,
            )
        logger.info("--- Finished Nightly Training Tasks ---")
    except psycopg2.Error as e:
        logger.error("Database error during nightly update: %s", e)
        raise
    finally:
        if conn:
            conn.close()
