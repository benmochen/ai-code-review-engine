"""
Redis connection + job queue setup.

Both the web app (producer) and the worker (consumer) import `get_queue()`
to talk to the same Redis-backed queue.
"""
from redis import Redis
from rq import Queue
from app.core.config import get_settings

settings = get_settings()

QUEUE_NAME = "reviews"

_redis_conn: Redis | None = None


def get_redis() -> Redis:
    """Return a singleton Redis connection built from REDIS_URL."""
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = Redis.from_url(settings.redis_url)
    return _redis_conn


def get_queue(connection: Redis | None = None) -> Queue:
    """Return the rq Queue used for review jobs."""
    conn = connection or get_redis()
    return Queue(QUEUE_NAME, connection=conn)