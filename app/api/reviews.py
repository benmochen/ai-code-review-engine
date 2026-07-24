from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.models.models import Review, Repository, ReviewComment
from app.schemas.schemas import (
    ReviewCreate, ReviewResponse, ReviewDetail,
    ReviewCommentCreate, ReviewCommentResponse,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("/", response_model=ReviewResponse, status_code=201)
def create_review(payload: ReviewCreate, db: Session = Depends(get_db)):
    """Create a new review for a PR. In Week 3 this is triggered by webhooks."""
    repo = db.query(Repository).filter(Repository.id == payload.repository_id).first()
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
    db: Session = Depends(get_db),
):
    """List reviews, optionally filtered by repository."""
    query = db.query(Review)
    if repo_id:
        query = query.filter(Review.repository_id == repo_id)
    return query.order_by(Review.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{review_id}", response_model=ReviewDetail)
def get_review(review_id: str, db: Session = Depends(get_db)):
    """Get a single review with all its comments."""
    review = (
        db.query(Review)
        .options(joinedload(Review.comments))
        .filter(Review.id == review_id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


# ──────────────────────────────────────────────
# Review Comments (nested under reviews)
# ──────────────────────────────────────────────
@router.post("/{review_id}/comments", response_model=ReviewCommentResponse, status_code=201)
def add_comment(review_id: str, payload: ReviewCommentCreate, db: Session = Depends(get_db)):
    """Add a comment to a review. In Week 4 Claude generates these."""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if payload.review_id != review_id:
        raise HTTPException(status_code=400, detail="review_id in body must match URL")

    comment = ReviewComment(**payload.model_dump())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/{review_id}/comments", response_model=list[ReviewCommentResponse])
def list_comments(review_id: str, db: Session = Depends(get_db)):
    """List all comments for a review."""
    return (
        db.query(ReviewComment)
        .filter(ReviewComment.review_id == review_id)
        .order_by(ReviewComment.created_at)
        .all()
    )
