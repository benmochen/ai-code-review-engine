import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.core.github_client import GitHubClient
from app.models.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.get("/login")
def login(request: Request):
    if not settings.github_client_id:
        raise HTTPException(status_code=500, detail="GITHUB_CLIENT_ID not configured")

    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    redirect_uri = str(request.url_for("oauth_callback"))
    url = GitHubClient.authorize_url(
        client_id=settings.github_client_id,
        redirect_uri=redirect_uri,
        state=state,
    )
    return RedirectResponse(url)

@router.get("/callback", name="oauth_callback")
async def oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
):
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # CSRF check: does the returned state match what we stored?
    expected_state = request.session.get("oauth_state")
    if not expected_state or state != expected_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    request.session.pop("oauth_state", None)

    # Exchange the code for a token
    access_token = await GitHubClient.exchange_code_for_token(
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        code=code,
    )

    # Fetch the user's GitHub profile
    gh = GitHubClient(access_token=access_token)
    profile = await gh.get_authenticated_user()

    # Upsert: update if the user exists, else create
    user = db.query(User).filter(User.github_id == profile["id"]).first()
    if user:
        user.username = profile["login"]
        user.email = profile.get("email")
        user.avatar_url = profile.get("avatar_url")
        user.access_token = access_token
    else:
        user = User(
            github_id=profile["id"],
            username=profile["login"],
            email=profile.get("email"),
            avatar_url=profile.get("avatar_url"),
            access_token=access_token,
        )
        db.add(user)
    db.commit()
    db.refresh(user)

    # Log them in
    request.session["user_id"] = user.id

    return {"message": "Login successful", "user": {"id": user.id, "username": user.username}}

@router.get("/me")
def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not logged in")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return {"id": user.id, "username": user.username, "email": user.email, "avatar_url": user.avatar_url}

@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out"}
