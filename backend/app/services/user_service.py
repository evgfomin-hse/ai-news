from sqlalchemy.orm import Session

from app.models import User
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._users = UserRepository(session)

    def get_by_id(self, user_id: int) -> User | None:
        return self._users.get_by_id(user_id)

    def get_or_create(
        self,
        *,
        subject: str,
        name: str,
        picture: str | None,
        email: str | None,
    ) -> User:
        return self._users.get_or_create(
            subject=subject,
            name=name,
            picture=picture,
            email=email,
        )

    def patch_profile(
        self,
        user: User,
        *,
        name: str | None,
        picture: str | None,
    ) -> User:
        if name is not None or picture is not None:
            self._users.update_profile(user, name=name, picture=picture)
            self._session.commit()
        return user
