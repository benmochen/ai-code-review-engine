from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import get_settings
from app.core.database import engine, Base
from app.api import users, repos, reviews
from app.api import webhooks, auth
from starlette.middleware.sessions import SessionMiddleware

settings = get_settings()


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
def health_check():
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "version": "0.1.0",
    }
