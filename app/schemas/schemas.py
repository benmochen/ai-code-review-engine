from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.models.models import ReviewStatus, Severity


# ──────────────────────────────────────────────
# User schemas
# ──────────────────────────────────────────────
class UserCreate(BaseModel):
    github_id: int
    username: str
    email: str | None = None
    avatar_url: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    github_id: int
    username: str
    email: str | None
    avatar_url: str | None
    created_at: datetime


# ──────────────────────────────────────────────
# Repository schemas
# ──────────────────────────────────────────────
class RepositoryCreate(BaseModel):
    """Enable a repository. The owner comes from the session, never the body."""
    github_id: int
    full_name: str


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    github_id: int
    full_name: str
    owner_id: str
    webhook_active: bool
    created_at: datetime
    # webhook_secret is deliberately absent — it never leaves the server.


class AvailableRepository(BaseModel):
    """A GitHub repo the user could enable, plus whether it already is."""
    github_id: int
    full_name: str
    private: bool
    enabled: bool


# ──────────────────────────────────────────────
# Review schemas
# ──────────────────────────────────────────────
class ReviewCreate(BaseModel):
    repository_id: str
    pr_number: int
    pr_title: str
    pr_url: str | None = None


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    pr_number: int
    pr_title: str
    pr_url: str | None
    status: ReviewStatus
    created_at: datetime
    completed_at: datetime | None


class ReviewDetail(ReviewResponse):
    """Review with nested comments."""
    comments: list["ReviewCommentResponse"] = []


# ──────────────────────────────────────────────
# ReviewComment schemas
# ──────────────────────────────────────────────
class ReviewCommentCreate(BaseModel):
    review_id: str
    file_path: str
    line_number: int | None = None
    severity: Severity = Severity.INFO
    body: str


class ReviewCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    review_id: str
    file_path: str
    line_number: int | None
    severity: Severity
    body: str
    posted_to_github: bool
    created_at: datetime


# ──────────────────────────────────────────────
# Generic
# ──────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
