from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
    )

    # Same OAuth 2.0 Client ID as VITE_APP_CLIENT_ID on the frontend (Google Sign-In).
    google_client_id: str = ""

    # Used to sign API session JWTs after Google login; use a long random string in production.
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"

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


settings = Settings()
