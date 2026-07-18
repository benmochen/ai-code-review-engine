from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel

from database import get_db
from models import Repository

router = APIRouter()

class RepositoryCreate(BaseModel):
    name: str

@router.post("/repositories")
def create_repository(new_repository: RepositoryCreate, db: Session = Depends(get_db)):
    repository = Repository(name=new_repository.name)
    db.add(repository)
    db.commit()
    db.refresh(repository)
    return repository

@router.get("/repositories")
def get_repository(db: Session = Depends(get_db)):
    return db.execute(select(Repository)).scalars().all()

@router.get("/repositories/{repository_id}")
def get_one_repository(repository_id: int, db: Session = Depends(get_db)):
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repository