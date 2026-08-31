from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import Review, Repository, ReviewComment, User
from app.schemas.schemas import (
    ReviewCreate, ReviewResponse, ReviewDetail,
    ReviewCommentCreate, ReviewCommentResponse,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _owned_review(review_id: str, user: User, db: Session) -> Review:
    """Fetch a review whose repository belongs to the caller, or 404.

    Reviews have no owner of their own — ownership is inherited through the
    repository, so every lookup joins back to it.
    """
    review = (
        db.query(Review)
        .join(Repository, Review.repository_id == Repository.id)
        .filter(Review.id == review_id, Repository.owner_id == user.id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.post("/", response_model=ReviewResponse, status_code=201)
def create_review(
    payload: ReviewCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a review manually. Normally the webhook does this."""
    repo = (
        db.query(Repository)
        .filter(
            Repository.id == payload.repository_id,
            Repository.owner_id == user.id,
        )
        .first()
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    review = Review(**payload.model_dump())
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.get("/", response_model=list[ReviewResponse])
def list_reviews(
    repo_id: str | None = None,
    skip: int = 0,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the caller's reviews, optionally filtered by repository."""
    query = (
        db.query(Review)
        .join(Repository, Review.repository_id == Repository.id)
        .filter(Repository.owner_id == user.id)
    )
    if repo_id:
        query = query.filter(Review.repository_id == repo_id)
    return query.order_by(Review.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{review_id}", response_model=ReviewDetail)
def get_review(
    review_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get one of the caller's reviews with all its comments."""
    _owned_review(review_id, user, db)
    return (
        db.query(Review)
        .options(joinedload(Review.comments))
        .filter(Review.id == review_id)
        .first()
    )


# ──────────────────────────────────────────────
# Review Comments (nested under reviews)
# ──────────────────────────────────────────────
@router.post("/{review_id}/comments", response_model=ReviewCommentResponse, status_code=201)
def add_comment(
    review_id: str,
    payload: ReviewCommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a comment to a review. Normally the worker does this."""
    _owned_review(review_id, user, db)

    if payload.review_id != review_id:
        raise HTTPException(status_code=400, detail="review_id in body must match URL")

    comment = ReviewComment(**payload.model_dump())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/{review_id}/comments", response_model=list[ReviewCommentResponse])
def list_comments(
    review_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List comments on one of the caller's reviews."""
    _owned_review(review_id, user, db)
    return (
        db.query(ReviewComment)
        .filter(ReviewComment.review_id == review_id)
        .order_by(ReviewComment.created_at)
        .all()
    )
