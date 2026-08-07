"""
Load test — measures REAL latency and throughput so you can put honest
numbers on your resume instead of guessing.

Run against a running server:

    # 1. Start the stack (docker compose up, or uvicorn locally)
    # 2. Run locust:
    locust -f loadtest/locustfile.py --host http://localhost:8000

    # Then open http://localhost:8089 and set users + spawn rate,
    # OR run headless for a fixed test:
    locust -f loadtest/locustfile.py --host http://localhost:8000 \
           --users 50 --spawn-rate 10 --run-time 60s --headless

Locust reports p50/p95/p99 latency and requests/sec per endpoint. Those
are the numbers to quote — e.g. "sustained N req/s at p95 < X ms with
50 concurrent users" — because you measured them.

NOTE: This hits the fast read/enqueue paths (health, list reviews, webhook
ingestion). It deliberately does NOT drive real Claude calls — you're
measuring YOUR service's request handling, not Anthropic's API latency.
The webhook enqueues and returns immediately (the whole point of Week 3),
so it's a fair thing to load test.
"""
import json
from locust import HttpUser, task, between


class ReadUser(HttpUser):
    """Simulates dashboard traffic — listing reviews and checking health."""
    wait_time = between(0.1, 0.5)

    @task(3)
    def health(self):
        self.client.get("/health")

    @task(5)
    def list_reviews(self):
        self.client.get("/api/reviews/")

    @task(2)
    def list_repos(self):
        self.client.get("/api/repos/")


class WebhookUser(HttpUser):
    """Simulates GitHub webhook load — the enqueue path."""
    wait_time = between(0.2, 1.0)

    @task
    def send_webhook(self):
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 1,
                "title": "Load test PR",
                "html_url": "https://github.com/x/y/pull/1",
            },
            "repository": {"id": 999999, "full_name": "loadtest/repo"},
        }
        # Unregistered repo → webhook returns fast without enqueuing real work,
        # so this measures ingestion + signature handling under load.
        self.client.post(
            "/api/webhooks/github",
            data=json.dumps(payload),
            headers={
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
            name="/api/webhooks/github",
        )
