import logging
from rq import Worker
from rq.registry import FailedJobRegistry
from .tasks import queue, redis_conn

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    worker = Worker([queue], connection=redis_conn)

    failed_registry = FailedJobRegistry(queue.name, connection=redis_conn)
    for job_id in failed_registry.get_job_ids():
        logging.info("Requeuing failed job %s", job_id)
        queue.requeue(job_id)

    worker.work(with_scheduler=True)
