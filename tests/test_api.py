"""
API tests — run with: pytest tests/ -v

Users are created by the OAuth callback, not by an endpoint, so these start
from the `auth_client` fixture (a signed-in user) rather than POSTing a user.
"""
import pytest

from tests.conftest import make_repo, make_user


@pytest.fixture
def enabled_repo(auth_client, monkeypatch):
    """Enable a repository through the API with GitHub's calls mocked."""
    monkeypatch.setattr(
        "app.api.repos.settings.public_base_url", "https://example.test"
    )

    async def fake_create_webhook(self, repo_full_name, callback_url, secret):
        return {"id": 555}

    monkeypatch.setattr(
        "app.api.repos.GitHubClient.create_webhook", fake_create_webhook
    )
    r = auth_client.post(
        "/api/repos/", json={"github_id": 100, "full_name": "ben/my-project"}
    )
    assert r.status_code == 201, r.text
    return r.json()


# ──────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ──────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────
def test_get_own_user(auth_client):
    r = auth_client.get(f"/api/users/{auth_client.user.id}")
    assert r.status_code == 200
    assert r.json()["username"] == "ben"


def test_cannot_read_another_user(auth_client):
    other = make_user("mallory", 999)
    r = auth_client.get(f"/api/users/{other}")
    assert r.status_code == 404


def test_cannot_delete_another_user(auth_client):
    other = make_user("mallory", 999)
    r = auth_client.delete(f"/api/users/{other}")
    assert r.status_code == 404


# ──────────────────────────────────────────────
# Repositories
# ──────────────────────────────────────────────
def test_enable_repo(enabled_repo, auth_client):
    assert enabled_repo["full_name"] == "ben/my-project"
    assert enabled_repo["webhook_active"] is True
    assert enabled_repo["owner_id"] == auth_client.user.id


def test_enable_repo_never_returns_the_secret(enabled_repo):
    assert "webhook_secret" not in enabled_repo


def test_enable_repo_requires_public_base_url(auth_client, monkeypatch):
    monkeypatch.setattr("app.api.repos.settings.public_base_url", "")
    r = auth_client.post(
        "/api/repos/", json={"github_id": 1, "full_name": "ben/x"}
    )
    assert r.status_code == 500


def test_list_repos_only_returns_own(auth_client, enabled_repo):
    other = make_user("mallory", 999)
    make_repo(other, "mallory/secret-startup", 777)

    names = [r["full_name"] for r in auth_client.get("/api/repos/").json()]
    assert names == ["ben/my-project"]


def test_cannot_read_another_users_repo(auth_client):
    other = make_user("mallory", 999)
    repo_id = make_repo(other, "mallory/secret-startup", 777)
    assert auth_client.get(f"/api/repos/{repo_id}").status_code == 404


def test_cannot_delete_another_users_repo(auth_client):
    other = make_user("mallory", 999)
    repo_id = make_repo(other, "mallory/secret-startup", 777)
    assert auth_client.delete(f"/api/repos/{repo_id}").status_code == 404


def test_disable_repo(auth_client, enabled_repo, monkeypatch):
    async def fake_delete(self, repo_full_name, hook_id):
        return None

    monkeypatch.setattr("app.api.repos.GitHubClient.delete_webhook", fake_delete)
    assert auth_client.delete(f"/api/repos/{enabled_repo['id']}").status_code == 204
    assert auth_client.get("/api/repos/").json() == []


# ──────────────────────────────────────────────
# Reviews & Comments
# ──────────────────────────────────────────────
def test_full_review_flow(auth_client, enabled_repo):
    """End-to-end: repo -> review -> comment -> read back."""
    review = auth_client.post(
        "/api/reviews/",
        json={
            "repository_id": enabled_repo["id"],
            "pr_number": 42,
            "pr_title": "Add user authentication",
        },
    ).json()
    assert review["status"] == "pending"
    assert review["pr_number"] == 42

    comment = auth_client.post(
        f"/api/reviews/{review['id']}/comments",
        json={
            "review_id": review["id"],
            "file_path": "src/auth.py",
            "line_number": 15,
            "severity": "warning",
            "body": "Consider using bcrypt instead of md5 for password hashing",
        },
    ).json()
    assert comment["severity"] == "warning"
    assert comment["posted_to_github"] is False

    detail = auth_client.get(f"/api/reviews/{review['id']}").json()
    assert len(detail["comments"]) == 1
    assert detail["comments"][0]["file_path"] == "src/auth.py"


def test_cannot_create_review_on_another_users_repo(auth_client):
    other = make_user("mallory", 999)
    repo_id = make_repo(other, "mallory/secret-startup", 777)
    r = auth_client.post(
        "/api/reviews/",
        json={"repository_id": repo_id, "pr_number": 1, "pr_title": "x"},
    )
    assert r.status_code == 404
