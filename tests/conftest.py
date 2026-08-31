"""
Shared test configuration.

Every test file uses the SAME in-memory SQLite database and the SAME
dependency overrides, applied here once. This avoids the files fighting over
app.dependency_overrides (last-import-wins), which caused "no such table"
errors when running the full suite together.

Two client fixtures:
  client       - nobody is signed in; use it to assert endpoints return 401
  auth_client  - a signed-in user; use it for normal behavior
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.models import Repository, User

# StaticPool + shared connection keeps one in-memory DB alive for the session
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Worker jobs (Week 3) call SessionLocal() directly instead of going through
# the get_db dependency, because in production they run in a separate process.
# In tests we rebind those module-level references to the test session so the
# job sees the same in-memory database the API writes to.
import app.core.database as _db_module
import app.workers.jobs as _jobs_module

_db_module.SessionLocal = TestSession
_jobs_module.SessionLocal = TestSession


@pytest.fixture
def client():
    """Unauthenticated client with a fresh schema per test."""
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides.pop(get_current_user, None)
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def auth_client(client):
    """Client acting as a signed-in user, exposed as client.user."""
    # The session stays open for the test so the User stays attached and the
    # override can keep handing back a live instance.
    db = TestSession()
    user = User(github_id=4242, username="ben", access_token="gho_test")
    db.add(user)
    db.commit()
    db.refresh(user)

    app.dependency_overrides[get_current_user] = lambda: user
    client.user = user
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        db.close()


def make_user(username: str, github_id: int) -> str:
    """Create another user directly in the DB. Returns their id."""
    db = TestSession()
    try:
        u = User(github_id=github_id, username=username, access_token="gho_other")
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def make_repo(owner_id: str, full_name: str, github_id: int, secret: str | None = None) -> str:
    """Create a repository owned by someone, bypassing the API. Returns its id."""
    db = TestSession()
    try:
        r = Repository(
            owner_id=owner_id,
            full_name=full_name,
            github_id=github_id,
            webhook_secret=secret,
            webhook_active=secret is not None,
        )
        db.add(r)
        db.commit()
        db.refresh(r)
        return r.id
    finally:
        db.close()
