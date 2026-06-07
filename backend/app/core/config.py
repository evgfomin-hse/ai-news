from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholder JWT secret used as a development default. Refused at startup
# when cookie_secure=True (i.e. production-shaped config) — see validator below.
_PLACEHOLDER_JWT_SECRET = "dev-only-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""

    # Same OAuth 2.0 Client ID as VITE_APP_CLIENT_ID on the frontend (Google Sign-In).
    google_client_id: str = ""

    # Used to sign API session JWTs after Google login; use a long random string in production.
    jwt_secret: str = _PLACEHOLDER_JWT_SECRET
    jwt_algorithm: str = "HS256"
    session_ttl_seconds: int = 7 * 24 * 3600

    # When set, POST /auth/e2e/bootstrap-session (header X-E2E-Bootstrap-Secret) creates a
    # real DB user + HttpOnly session JWT (same path as Google login). Leave empty in production.
    e2e_bootstrap_secret: str = ""

    # Nightly job: insert one `summaries` row per user at 00:00 in
    # `summary_schedule_timezone` (IANA, e.g. UTC).
    enable_summary_nightly_scheduler: bool = True
    summary_schedule_timezone: str = "UTC"

    # When set, POST /tasks/summary/run-bulk (header X-Summary-Job-Secret) runs
    # the same job as midnight. Empty = route disabled.
    summary_job_secret: str = ""

    # GDELT-based daily news pipeline (replaces NewsAPI top-headlines for the bulk job).
    summary_schedule_hour: int = Field(default=3, ge=0, le=23)
    gdelt_max_articles: int = 2000
    gdelt_request_max_records: int = 250
    per_user_filter_batch: int = 500
    per_user_filter_top_per_batch: int = 25
    per_user_digest_limit: int = 50
    keyword_extractor_max_query_chars: int = 450

    # OpenRouter chat-completions endpoint. Empty key disables LLM-based summary
    # generation (the job falls back to inserting placeholder rows).
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"

    # Comma-separated browser origins allowed to call the API (e.g. http://localhost:5173).
    cors_origins: str = "http://localhost:5173"

    # HttpOnly session cookie (JWT). Use Secure=true on HTTPS in production.
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
        # Only fail on production-shaped configs (cookie_secure=True).
        # Dev keeps working with the default.
        if self.cookie_secure and self.jwt_secret == _PLACEHOLDER_JWT_SECRET:
            msg = (
                "jwt_secret is the publicly-known placeholder; set JWT_SECRET to a long random "
                "value in production (cookie_secure=True)"
            )
            raise ValueError(msg)
        return self


settings = Settings()
