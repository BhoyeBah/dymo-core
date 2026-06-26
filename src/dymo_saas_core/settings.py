"""Runtime settings for Dymo SaaS Core."""

from pydantic import BaseModel, Field


class CoreSettings(BaseModel):
    app_env: str = Field(default="development")
    database_url: str | None = None
    redis_url: str | None = None
    cookie_secure: bool = False

