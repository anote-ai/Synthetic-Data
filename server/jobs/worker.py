"""
RQ worker entry point.
Run with: rq worker --url redis://localhost:6379 synthetic-data
Or: python -m server.jobs.worker
"""
import os
from redis import Redis
from rq import Worker, Queue

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
conn = Redis.from_url(redis_url)


def get_queue():
    return Queue("synthetic-data", connection=conn)


if __name__ == "__main__":
    w = Worker([Queue("synthetic-data", connection=conn)], connection=conn)
    w.work()
