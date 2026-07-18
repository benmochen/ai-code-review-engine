from fastapi import FastAPI
from database import Base, engine
from models import Review, Repository
from api import reviews, repositories

app = FastAPI()
Base.metadata.create_all(engine)

app.include_router(reviews.router)
app.include_router(repositories.router)