"""
Worker entry point.

Run this in a SEPARATE terminal from the web server:

    python -m app.workers.worker

It connects to Redis, listens on the "reviews" queue, and runs
process_review() for each job the webhook enqueues.

In production you'd run several of these processes for parallelism.
"""
from rq import Worker
from app.core.queue import get_redis, QUEUE_NAME


def main():
    conn = get_redis()
    worker = Worker([QUEUE_NAME], connection=conn)
    print(f"[worker] listening on queue '{QUEUE_NAME}'...")
    worker.work()


if __name__ == "__main__":
    main()