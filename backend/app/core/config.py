from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_JWT_SECRET = "dev-only-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""

    google_client_id: str = ""

    jwt_secret: str = _PLACEHOLDER_JWT_SECRET
    jwt_algorithm: str = "HS256"
    session_ttl_seconds: int = 7 * 24 * 3600

    e2e_bootstrap_secret: str = ""

    enable_summary_nightly_scheduler: bool = True
    summary_schedule_timezone: str = "UTC"

    summary_job_secret: str = ""

    summary_schedule_hour: int = Field(default=3, ge=0, le=23)
    per_user_filter_batch: int = 500
    per_user_filter_top_per_batch: int = 25
    per_user_digest_limit: int = 50
    keyword_extractor_max_query_chars: int = 450

    news_api_key: str = ""
    news_api_language: str = "en"
    news_request_page_size: int = Field(default=100, ge=1, le=100)
    news_max_articles: int = 100

    llm_base_url: str = ""
    llm_timeout_seconds: int = Field(default=60, ge=1)

    llm_api_key: str = ""
    llm_model: str = ""

    @property
    def llm_is_openrouter(self) -> bool:
        """True when the configured endpoint is OpenRouter (which requires an API key)."""
        return "openrouter.ai" in self.llm_base_url.lower()

    cors_origins: str = "http://localhost:5173"

    session_cookie_name: str = "session"
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_path: str = "/"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def cookie_none_requires_secure(self) -> Self:
        if self.cookie_samesite == "none" and not self.cookie_secure:
            msg = "cookie_samesite 'none' requires cookie_secure True (browser requirement)"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def jwt_secret_required_in_production(self) -> Self:
        if self.cookie_secure and self.jwt_secret == _PLACEHOLDER_JWT_SECRET:
            msg = (
                "jwt_secret is the publicly-known placeholder; set JWT_SECRET to a long random "
                "value in production (cookie_secure=True)"
            )
            raise ValueError(msg)
        return self


settings = Settings()
