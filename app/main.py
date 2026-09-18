from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import get_settings
from app.core.database import engine, Base, get_db
from app.core.queue import get_redis
from app.api import users, repos, reviews
from app.api import webhooks, auth
from starlette.middleware.sessions import SessionMiddleware

settings = get_settings()
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all tables on startup (replaced by Alembic migrations later)."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    description="AI-powered code review bot — reviews your PRs using Claude",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

# Register route modules
app.include_router(users.router, prefix="/api")
app.include_router(repos.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(auth.router, prefix="/api")


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    redis_ok = False
    try:
        r = get_redis()
        redis_ok = bool(r.ping())
    except Exception:
        redis_ok = False

    return {
        "status": "ok",
        "app_name": settings.app_name,
        "version": "0.1.0",
        "database": "ok" if db_ok else "unreachable",
        "redis": "ok" if redis_ok else "unreachable",
    }


# Mount static assets if built
if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/")
def serve_root():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {
        "app_name": settings.app_name,
        "status": "ok",
        "message": "API is running. Build frontend to view dashboard.",
        "docs_url": "/docs",
    }


@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")

    candidate = FRONTEND_DIST / full_path
    if candidate.is_file():
        return FileResponse(candidate)

    index_file = FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Page not found")
