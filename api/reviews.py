from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db
from models import Review, Repository

router = APIRouter()

class ReviewCreate(BaseModel):
    repo: str
    pr_number: int
    repository_id: int

@router.post("/reviews")
def create_review(new_review: ReviewCreate, db: Session = Depends(get_db)):
    repo = db.get(Repository, new_review.repository_id)
    if repo is None:
        raise HTTPException(status_code=400, detail="Repository does not exist")
    review = Review(repo=new_review.repo, pr_number=new_review.pr_number, repository_id=new_review.repository_id)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review

@router.get("/reviews")
def get_review(db: Session = Depends(get_db)):
    return db.execute(select(Review)).scalars().all()

@router.get("/reviews/{review_id}")
def get_one_review(review_id: int, db: Session = Depends(get_db)):
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review