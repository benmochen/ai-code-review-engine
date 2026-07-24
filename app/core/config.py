from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "CodeReviewBot"
    debug: bool = True
    database_url: str = "postgresql://postgres:postgres@localhost:5432/code_review_bot"

    # These will be used in later weeks
    github_client_id: str = ""
    github_client_secret: str = ""
    github_webhook_secret: str = ""
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str = ""

    model_config = {"env_file": ".env"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
