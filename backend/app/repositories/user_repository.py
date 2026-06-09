from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User


def _placeholder_email(subject: str) -> str:
    return f"{subject}@oauth-subject.local"


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self._session.scalar(select(User).where(User.id == user_id))

    def list_all_ids(self) -> list[int]:
        return [int(x) for x in self._session.scalars(select(User.id)).all()]

    def get_or_create(
        self,
        *,
        subject: str,
        name: str,
        picture: str | None,
        email: str | None,
    ) -> User:
        resolved_email = (email.strip() if email and email.strip() else None) or _placeholder_email(
            subject
        )

        user = self._session.scalar(select(User).where(User.subject == subject))
        if user is None:
            user = User(
                subject=subject,
                name=name,
                picture=picture,
                email=resolved_email,
            )
            self._session.add(user)
            try:
                self._session.commit()
                self._session.refresh(user)
                return user
            except IntegrityError:
                self._session.rollback()
                user = self._session.scalar(select(User).where(User.subject == subject))
                if user is None:
                    msg = "Could not create or load user after concurrent signup"
                    raise RuntimeError(msg) from None
                user.name = name
                user.picture = picture
                if email is not None and email.strip():
                    user.email = email.strip()
                self._session.commit()
                self._session.refresh(user)
                return user

        user.name = name
        user.picture = picture
        if email is not None and email.strip():
            user.email = email.strip()
        self._session.commit()
        self._session.refresh(user)
        return user

    def update_profile(
        self,
        user: User,
        *,
        name: str | None,
        picture: str | None,
    ) -> User:
        changed = False
        if name is not None:
            user.name = name
            changed = True
        if picture is not None:
            user.picture = picture
            changed = True
        if changed:
            self._session.add(user)
            self._session.flush()
            self._session.refresh(user)
        return user
