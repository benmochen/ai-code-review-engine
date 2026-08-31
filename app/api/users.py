"""
User endpoints.

Accounts are created by the GitHub OAuth callback, not here, so there is no
create endpoint. There is no list endpoint either — enumerating every account
on the service is not something any caller needs.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import User
from app.schemas.schemas import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, user: User = Depends(get_current_user)):
    """Get a user. Callers may only read their own account."""
    if user_id != user.id:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete your own account, its repositories, and its reviews."""
    if user_id != user.id:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    request.session.clear()
