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

    # Same OAuth 2.0 Client ID as VITE_APP_CLIENT_ID on the frontend (OAuth Sign-In).
    google_client_id: str = ""

    # Used to sign API session JWTs after login; use a long random string in production.
    jwt_secret: str = _PLACEHOLDER_JWT_SECRET
    jwt_algorithm: str = "HS256"
    session_ttl_seconds: int = 7 * 24 * 3600

    # When set, POST /auth/e2e/bootstrap-session (header X-E2E-Bootstrap-Secret) creates a
    # real DB user + HttpOnly session JWT (same path as login). Leave empty in production.
    e2e_bootstrap_secret: str = ""

    # Nightly job: insert one `summaries` row per user at 00:00 in
    # `summary_schedule_timezone` (IANA, e.g. UTC).
    enable_summary_nightly_scheduler: bool = True
    summary_schedule_timezone: str = "UTC"

    # When set, POST /tasks/summary/run-bulk (header X-Summary-Job-Secret) runs
    # the same job as midnight. Empty = route disabled.
    summary_job_secret: str = ""

    # NewsAPI.org /everything daily news pipeline.
    summary_schedule_hour: int = Field(default=3, ge=0, le=23)
    per_user_filter_batch: int = 500
    per_user_filter_top_per_batch: int = 25
    per_user_digest_limit: int = 50
    keyword_extractor_max_query_chars: int = 450

    # NewsAPI key (newsapi.org). Empty disables fetching; the run falls back to stored
    # articles. The free Developer plan caps results at 100 and delays articles ~24h.
    news_api_key: str = ""
    news_api_language: str = "en"
    news_request_page_size: int = Field(default=100, ge=1, le=100)
    news_max_articles: int = 100

    # OpenAI-compatible chat-completions endpoint. Defaults to OpenRouter; point at a
    # local LM Studio server (e.g. http://127.0.0.1:1234/v1/chat/completions) to run
    # models locally with no API key and no rate limits.
    llm_base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    # Request timeout (seconds). Local models on modest hardware can be slow — bump for LM Studio.
    llm_timeout_seconds: int = Field(default=60, ge=1)

    # API key for the LLM endpoint. Required for OpenRouter; ignored by LM Studio.
    # When targeting OpenRouter, an empty key disables LLM-based summary generation
    # (the job falls back to inserting placeholder rows).
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"

    @property
    def llm_is_openrouter(self) -> bool:
        """True when the configured endpoint is OpenRouter (which requires an API key)."""
        return "openrouter.ai" in self.llm_base_url.lower()

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
