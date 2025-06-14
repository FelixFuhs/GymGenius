import logging
from rq import Worker
from .tasks import queue, redis_conn

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    worker = Worker([queue], connection=redis_conn)
    worker.work()
