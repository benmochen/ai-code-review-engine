import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.github_client import GitHubClient
from app.models.models import Repository, User
from app.schemas.schemas import (
    AvailableRepository,
    RepositoryCreate,
    RepositoryResponse,
)

router = APIRouter(prefix="/repos", tags=["repositories"])
settings = get_settings()


def _owned_repo(repo_id: str, user: User, db: Session) -> Repository:
    """Fetch a repo the caller owns, or 404.

    Someone else's repo returns 404 rather than 403 so the response doesn't
    confirm that the id exists.
    """
    repo = (
        db.query(Repository)
        .filter(Repository.id == repo_id, Repository.owner_id == user.id)
        .first()
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


@router.get("/available", response_model=list[AvailableRepository])
async def list_available_repositories(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the caller's GitHub repos so they can pick which to enable."""
    if not user.access_token:
        raise HTTPException(status_code=400, detail="No GitHub token; sign in again")

    gh = GitHubClient(access_token=user.access_token)
    try:
        remote = await gh.list_repositories()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {e}")

    enabled_ids = {
        r.github_id
        for r in db.query(Repository).filter(Repository.owner_id == user.id).all()
    }
    return [
        AvailableRepository(
            github_id=r["id"],
            full_name=r["full_name"],
            private=r.get("private", False),
            enabled=r["id"] in enabled_ids,
        )
        for r in remote
    ]


@router.post("/", response_model=RepositoryResponse, status_code=201)
async def enable_repository(
    payload: RepositoryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enable reviews for a repo: register the row and create the webhook."""
    if not settings.public_base_url:
        raise HTTPException(
            status_code=500,
            detail="PUBLIC_BASE_URL is not configured; GitHub cannot reach the webhook",
        )
    if not user.access_token:
        raise HTTPException(status_code=400, detail="No GitHub token; sign in again")

    existing = (
        db.query(Repository).filter(Repository.github_id == payload.github_id).first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Repository already registered")

    # A secret per repository, so one leak can't forge events for every repo.
    secret = secrets.token_hex(32)
    callback = f"{settings.public_base_url.rstrip('/')}/api/webhooks/github"

    gh = GitHubClient(access_token=user.access_token)
    try:
        hook = await gh.create_webhook(payload.full_name, callback, secret)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not create webhook: {e}")

    repo = Repository(
        github_id=payload.github_id,
        full_name=payload.full_name,
        owner_id=user.id,
        webhook_secret=secret,
        webhook_id=hook.get("id"),
        webhook_active=True,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


@router.delete("/{repo_id}", status_code=204)
async def disable_repository(
    repo_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disable reviews: remove the webhook from GitHub and drop the row."""
    repo = _owned_repo(repo_id, user, db)

    if repo.webhook_id and user.access_token:
        gh = GitHubClient(access_token=user.access_token)
        try:
            await gh.delete_webhook(repo.full_name, repo.webhook_id)
        except Exception:
            # GitHub may have lost the hook already, or the token may have been
            # revoked. Neither should block the user from disconnecting locally.
            pass

    db.delete(repo)
    db.commit()


@router.get("/", response_model=list[RepositoryResponse])
def list_repositories(
    skip: int = 0,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List repositories belonging to the caller."""
    return (
        db.query(Repository)
        .filter(Repository.owner_id == user.id)
        .order_by(Repository.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{repo_id}", response_model=RepositoryResponse)
def get_repository(
    repo_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get one of the caller's repositories."""
    return _owned_repo(repo_id, user, db)
