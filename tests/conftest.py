"""
Shared test configuration.

Both test files use the SAME in-memory SQLite database and the SAME
dependency override, applied here once. This avoids the two files fighting
over app.dependency_overrides (last-import-wins), which caused
"no such table" errors when running the full suite together.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app

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
    """Fresh schema per test, shared across the module via fixture."""
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)