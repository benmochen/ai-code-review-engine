"""
Week 3 tests — Redis queue + worker job.

Uses fakeredis (in-memory Redis) so no real Redis server is needed, and
rq's SimpleWorker to drain the queue synchronously inside the test. The
GitHub diff fetch is monkeypatched so no network calls happen.
"""
import pytest
import fakeredis
from rq import Queue, SimpleWorker

from app.core.database import SessionLocal
from app.models.models import User, Repository, Review, ReviewStatus
import app.core.queue as queue_module
import app.workers.jobs as jobs_module


@pytest.fixture
def fake_redis():
    """A fresh in-memory Redis for each test."""
    return fakeredis.FakeStrictRedis()


# ──────────────────────────────────────────────
# Queue wiring
# ──────────────────────────────────────────────
def test_get_queue_uses_patched_redis(fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    q = queue_module.get_queue()
    assert q.name == "reviews"
    assert q.connection is fake_redis


def test_enqueue_adds_job(fake_redis, monkeypatch):
    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)
    q = queue_module.get_queue()

    def dummy(x):
        return x * 2

    job = q.enqueue(dummy, 21)
    assert job.id is not None
    assert q.count == 1


# ──────────────────────────────────────────────
# Job processing (the consumer side)
# ──────────────────────────────────────────────
def _seed_review(diff_owner_token="gho_faketoken"):
    """Create a user → repo → review directly in the DB, return review id."""
    db = SessionLocal()
    try:
        user = User(github_id=777, username="ben", access_token=diff_owner_token)
        db.add(user)
        db.commit()
        db.refresh(user)

        repo = Repository(github_id=888, full_name="ben/demo", owner_id=user.id)
        db.add(repo)
        db.commit()
        db.refresh(repo)

        review = Review(
            repository_id=repo.id,
            pr_number=3,
            pr_title="Refactor auth",
            status=ReviewStatus.PENDING,
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return review.id
    finally:
        db.close()


def test_process_review_success(client, monkeypatch):
    """Job fetches diff (mocked), stores it, marks COMPLETED."""
    review_id = _seed_review()

    async def fake_get_pr_diff(self, repo_full_name, pr_number):
        return "diff --git a/x.py b/x.py\n+print('hi')\n"

    monkeypatch.setattr(
        "app.workers.jobs.GitHubClient.get_pr_diff", fake_get_pr_diff
    )

    result = jobs_module.process_review(review_id)

    assert result["status"] == "completed"
    assert result["diff_bytes"] > 0

    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        assert review.status == ReviewStatus.COMPLETED
        assert review.completed_at is not None
        assert "diff --git" in review.diff_text
    finally:
        db.close()


def test_process_review_missing(client):
    """Job handles a nonexistent review id gracefully."""
    result = jobs_module.process_review("does-not-exist")
    assert result["status"] == "error"


def test_process_review_diff_failure(client, monkeypatch):
    """If the diff fetch throws, the review is marked FAILED, not left hanging."""
    review_id = _seed_review()

    async def boom(self, repo_full_name, pr_number):
        raise RuntimeError("GitHub 404")

    monkeypatch.setattr("app.workers.jobs.GitHubClient.get_pr_diff", boom)

    result = jobs_module.process_review(review_id)
    assert result["status"] == "failed"

    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        assert review.status == ReviewStatus.FAILED
    finally:
        db.close()


# ──────────────────────────────────────────────
# End-to-end: webhook enqueues, worker drains, job completes
# ──────────────────────────────────────────────
def test_webhook_enqueues_and_worker_processes(client, fake_redis, monkeypatch):
    from app.core.config import get_settings
    settings = get_settings()
    settings.github_webhook_secret = ""  # disable sig check

    monkeypatch.setattr(queue_module, "get_redis", lambda: fake_redis)

    async def fake_get_pr_diff(self, repo_full_name, pr_number):
        return "diff --git a/y.py b/y.py\n+x = 1\n"
    monkeypatch.setattr(
        "app.workers.jobs.GitHubClient.get_pr_diff", fake_get_pr_diff
    )

    user = client.post("/api/users/", json={"github_id": 1, "username": "ben"}).json()
    client.post("/api/repos/", json={
        "github_id": 42, "full_name": "ben/demo", "owner_id": user["id"],
    })

    payload = {
        "action": "opened",
        "pull_request": {"number": 5, "title": "Add feature", "html_url": "http://x/5"},
        "repository": {"id": 42, "full_name": "ben/demo"},
    }
    r = client.post(
        "/api/webhooks/github",
        headers={"X-GitHub-Event": "pull_request"},
        json=payload,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["message"] == "Review created"
    assert body["job_id"] is not None

    q = Queue(queue_module.QUEUE_NAME, connection=fake_redis)
    assert q.count == 1
    worker = SimpleWorker([q], connection=fake_redis)
    worker.work(burst=True)

    review_id = body["review_id"]
    detail = client.get(f"/api/reviews/{review_id}").json()
    assert detail["status"] == "completed"