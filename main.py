from fastapi import FastAPI
from fastapi import HTTPException

from pydantic import BaseModel

from database import Base, engine
from models import Review

app = FastAPI()
reviews = []

class ReviewCreate(BaseModel):
    repo: str
    pr_number: int

@app.get("/hello")
def say_hello():
    return {"message": "hello"}

@app.post("/reviews")
def create_review(new_review: ReviewCreate):
    reviews.append(new_review)
    return {"messages": "review saved", "length of list": len(reviews)}

@app.get("/reviews")
def get_review():
    return reviews

@app.get("/reviews/{review_id}")
def get_one_review(review_id: int):
    if review_id > len(reviews) - 1 or review_id < 0:
        raise HTTPException(status_code=404, detail="Review not found")
    return reviews[review_id]

Base.metadata.create_all(engine)
