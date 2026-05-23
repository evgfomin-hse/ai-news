"""Unit tests for `app.core.config.Settings` validators."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _kwargs(**overrides):
    """Minimal valid kwargs; tests override the bits they care about."""
    base = {
        "database_url": "sqlite:///:memory:",
        "google_client_id": "",
        "jwt_secret": "a-very-long-random-value-not-the-placeholder",
        "cookie_secure": False,
        "cookie_samesite": "lax",
    }
    base.update(overrides)
    return base


def test_dev_default_jwt_secret_is_accepted_when_cookie_secure_is_false():
    s = Settings(**_kwargs(jwt_secret="dev-only-change-me", cookie_secure=False))
    assert s.jwt_secret == "dev-only-change-me"


def test_placeholder_jwt_secret_is_rejected_when_cookie_secure_is_true():
    with pytest.raises(ValidationError) as exc:
        Settings(
            **_kwargs(
                jwt_secret="dev-only-change-me",
                cookie_secure=True,
                cookie_samesite="lax",
            )
        )
    assert "publicly-known placeholder" in str(exc.value)


def test_custom_jwt_secret_is_accepted_when_cookie_secure_is_true():
    s = Settings(
        **_kwargs(
            jwt_secret="a-very-long-random-value-not-the-placeholder",
            cookie_secure=True,
            cookie_samesite="lax",
        )
    )
    assert s.cookie_secure is True


def test_samesite_none_still_requires_cookie_secure():
    with pytest.raises(ValidationError) as exc:
        Settings(**_kwargs(cookie_samesite="none", cookie_secure=False))
    assert "cookie_samesite 'none' requires cookie_secure True" in str(exc.value)
