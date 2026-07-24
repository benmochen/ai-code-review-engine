from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import Repository, User
from app.schemas.schemas import RepositoryCreate, RepositoryResponse

router = APIRouter(prefix="/repos", tags=["repositories"])


@router.post("/", response_model=RepositoryResponse, status_code=201)
def create_repository(payload: RepositoryCreate, db: Session = Depends(get_db)):
    """Register a repo for code review tracking."""
    # Verify owner exists
    owner = db.query(User).filter(User.id == payload.owner_id).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner user not found")

    # Check duplicate
    existing = db.query(Repository).filter(Repository.github_id == payload.github_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Repository already registered")

    repo = Repository(**payload.model_dump())
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


@router.get("/", response_model=list[RepositoryResponse])
def list_repositories(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """List all registered repositories."""
    return db.query(Repository).offset(skip).limit(limit).all()


@router.get("/{repo_id}", response_model=RepositoryResponse)
def get_repository(repo_id: str, db: Session = Depends(get_db)):
    """Get a single repository by ID."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo
