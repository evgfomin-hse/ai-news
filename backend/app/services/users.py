from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User


def _placeholder_email(google_id: str) -> str:
    # Table requires NOT NULL UNIQUE email; Google may omit email if scopes are minimal.
    return f"{google_id}@google-subject.local"


def get_or_create_user(
    db: Session,
    *,
    google_id: str,
    name: str,
    picture: str | None,
    email: str | None,
) -> User:
    resolved_email = (email.strip() if email and email.strip() else None) or _placeholder_email(
        google_id
    )

    user = db.scalar(select(User).where(User.google_id == google_id))
    if user is None:
        user = User(
            google_id=google_id,
            name=name,
            picture=picture,
            email=resolved_email,
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
            return user
        except IntegrityError:
            db.rollback()
            user = db.scalar(select(User).where(User.google_id == google_id))
            if user is None:
                msg = "Could not create or load user after concurrent signup"
                raise RuntimeError(msg) from None
            user.name = name
            user.picture = picture
            if email is not None and email.strip():
                user.email = email.strip()
            db.commit()
            db.refresh(user)
            return user

    user.name = name
    user.picture = picture
    if email is not None and email.strip():
        user.email = email.strip()
    db.commit()
    db.refresh(user)
    return user
