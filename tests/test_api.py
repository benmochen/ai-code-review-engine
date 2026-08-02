"""
Week 1 tests — run with: pytest tests/ -v

These tests use SQLite in-memory so you don't need PostgreSQL running.
The `client` fixture comes from conftest.py.
"""


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
def test_create_user(client):
    r = client.post("/api/users/", json={
        "github_id": 12345,
        "username": "testuser",
        "email": "test@example.com",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "testuser"
    assert data["github_id"] == 12345
    assert "id" in data


def test_create_duplicate_user(client):
    client.post("/api/users/", json={"github_id": 1, "username": "dup"})
    r = client.post("/api/users/", json={"github_id": 1, "username": "dup2"})
    assert r.status_code == 409


def test_list_users(client):
    client.post("/api/users/", json={"github_id": 1, "username": "a"})
    client.post("/api/users/", json={"github_id": 2, "username": "b"})
    r = client.get("/api/users/")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_user_not_found(client):
    r = client.get("/api/users/nonexistent")
    assert r.status_code == 404


# ──────────────────────────────────────────────
# Repositories
# ──────────────────────────────────────────────
def test_create_repo(client):
    user = client.post("/api/users/", json={"github_id": 1, "username": "ben"}).json()
    r = client.post("/api/repos/", json={
        "github_id": 100,
        "full_name": "ben/my-project",
        "owner_id": user["id"],
    })
    assert r.status_code == 201
    assert r.json()["full_name"] == "ben/my-project"


def test_create_repo_invalid_owner(client):
    r = client.post("/api/repos/", json={
        "github_id": 100,
        "full_name": "nobody/repo",
        "owner_id": "fake-id",
    })
    assert r.status_code == 404


# ──────────────────────────────────────────────
# Reviews & Comments
# ──────────────────────────────────────────────
def test_full_review_flow(client):
    """End-to-end: create user → repo → review → comment → read back."""
    # Setup
    user = client.post("/api/users/", json={"github_id": 1, "username": "ben"}).json()
    repo = client.post("/api/repos/", json={
        "github_id": 100,
        "full_name": "ben/project",
        "owner_id": user["id"],
    }).json()

    # Create review
    review = client.post("/api/reviews/", json={
        "repository_id": repo["id"],
        "pr_number": 42,
        "pr_title": "Add user authentication",
    }).json()
    assert review["status"] == "pending"
    assert review["pr_number"] == 42

    # Add a comment
    comment = client.post(f"/api/reviews/{review['id']}/comments", json={
        "review_id": review["id"],
        "file_path": "src/auth.py",
        "line_number": 15,
        "severity": "warning",
        "body": "Consider using bcrypt instead of md5 for password hashing",
    }).json()
    assert comment["severity"] == "warning"
    assert comment["posted_to_github"] is False

    # Read review with comments
    detail = client.get(f"/api/reviews/{review['id']}").json()
    assert len(detail["comments"]) == 1
    assert detail["comments"][0]["file_path"] == "src/auth.py"