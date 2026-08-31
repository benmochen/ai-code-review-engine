"""
Shared FastAPI dependencies.

get_current_user is the gate every data endpoint sits behind. Routers that
return user-owned rows must depend on it AND filter by the returned user's
id — the dependency proves who is asking, not what they may see.
"""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the signed-in user from the session cookie, or 401."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # Session references a deleted user; clear it so the client re-logs in.
        request.session.clear()
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
