"""
Authorization tests.

Two properties, both previously missing:
  1. Data endpoints reject anonymous callers (401).
  2. A signed-in user sees only their own rows, never another user's.
"""
import pytest

from tests.conftest import make_repo, make_user

# Every endpoint that returns or mutates user-owned data.
PROTECTED = [
    ("get", "/api/repos/"),
    ("get", "/api/repos/available"),
    ("post", "/api/repos/"),
    ("get", "/api/repos/some-id"),
    ("delete", "/api/repos/some-id"),
    ("get", "/api/reviews/"),
    ("post", "/api/reviews/"),
    ("get", "/api/reviews/some-id"),
    ("get", "/api/reviews/some-id/comments"),
    ("post", "/api/reviews/some-id/comments"),
    ("get", "/api/users/some-id"),
    ("delete", "/api/users/some-id"),
    ("get", "/api/auth/me"),
]


@pytest.mark.parametrize("method,path", PROTECTED, ids=[f"{m}:{p}" for m, p in PROTECTED])
def test_requires_authentication(client, method, path):
    """No session cookie means 401 — never 200 with someone else's data."""
    r = client.request(method, path, json={})
    assert r.status_code == 401, f"{method.upper()} {path} returned {r.status_code}"


def test_anonymous_cannot_enumerate_users(client):
    """The old GET /api/users/ listed every account; it no longer exists."""
    assert client.get("/api/users/").status_code in (401, 404, 405)


def test_repos_are_isolated_between_users(auth_client):
    """The original leak: one user's list returning another user's repos."""
    mallory = make_user("mallory", 999)
    make_repo(mallory, "mallory/secret-startup", 777)
    make_repo(auth_client.user.id, "ben/my-project", 100)

    names = [r["full_name"] for r in auth_client.get("/api/repos/").json()]
    assert names == ["ben/my-project"]
    assert "mallory/secret-startup" not in names


def test_reviews_are_isolated_between_users(auth_client):
    """Reviews inherit ownership through their repository."""
    mallory = make_user("mallory", 999)
    their_repo = make_repo(mallory, "mallory/secret-startup", 777)
    mine = make_repo(auth_client.user.id, "ben/my-project", 100)

    # Insert a review on each repo directly, bypassing the API.
    from tests.conftest import TestSession
    from app.models.models import Review, ReviewStatus

    db = TestSession()
    try:
        for repo_id, title in ((their_repo, "theirs"), (mine, "mine")):
            db.add(Review(
                repository_id=repo_id, pr_number=1, pr_title=title,
                status=ReviewStatus.PENDING,
            ))
        db.commit()
        theirs = db.query(Review).filter(Review.pr_title == "theirs").first().id
    finally:
        db.close()

    titles = [r["pr_title"] for r in auth_client.get("/api/reviews/").json()]
    assert titles == ["mine"]

    # And fetching the other user's review by id is a 404, not a 403 — the
    # response must not confirm that the id exists.
    assert auth_client.get(f"/api/reviews/{theirs}").status_code == 404
    assert auth_client.get(f"/api/reviews/{theirs}/comments").status_code == 404
