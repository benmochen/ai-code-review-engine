from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from pydantic import BaseModel

from database import Base, engine, get_db
from models import Review

app = FastAPI()

class ReviewCreate(BaseModel):
    repo: str
    pr_number: int

Base.metadata.create_all(engine)

# @app.get("/hello")
# def say_hello():
#     return {"message": "hello"}

@app.post("/reviews")
def create_review(new_review: ReviewCreate, db: Session = Depends(get_db)):
    review = Review(repo=new_review.repo, pr_number=new_review.pr_number)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review

@app.get("/reviews")
def get_review(db: Session = Depends(get_db)):
    return db.execute(select(Review)).scalars().all() 
    

@app.get("/reviews/{review_id}")
def get_one_review(review_id: int, db: Session = Depends(get_db)):
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review

