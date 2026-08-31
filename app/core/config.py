from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "CodeReviewBot"
    debug: bool = True
    sql_echo: bool = False
    database_url: str = "postgresql://localhost/reviewbot"

    # These will be used in later weeks
    github_client_id: str = ""
    github_client_secret: str = ""
    github_webhook_secret: str = Field(min_length=1)
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5"
    session_secret: str = Field(min_length=1)
    # Public origin GitHub delivers webhooks to (an ngrok URL in dev). Without
    # it a repo cannot be enabled, since GitHub needs a reachable callback.
    public_base_url: str = ""
    # Where to send the browser after a successful OAuth login.
    frontend_url: str = "/"

    model_config = {"env_file": ".env"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
