from sqlalchemy.orm import Session

from app.models import User
from app.services.user_service import UserService


def test_get_by_id_returns_user(db: Session, user: User):
    assert UserService(db).get_by_id(user.id).id == user.id


def test_patch_profile_updates_and_commits(db: Session, user: User):
    UserService(db).patch_profile(user, name="Updated", picture="https://x/p.png")
    db.expire_all()
    refreshed = UserService(db).get_by_id(user.id)
    assert refreshed.name == "Updated"
    assert refreshed.picture == "https://x/p.png"


def test_patch_profile_noop_when_both_fields_none(db: Session, user: User):
    before = (user.name, user.picture)
    UserService(db).patch_profile(user, name=None, picture=None)
    assert (user.name, user.picture) == before


def test_get_or_create_delegates_to_repository(db: Session):
    created = UserService(db).get_or_create(
        google_id="svc-sub", name="S", picture=None, email="s@example.com"
    )
    assert created.id is not None
    again = UserService(db).get_or_create(google_id="svc-sub", name="S2", picture=None, email=None)
    assert again.id == created.id
    assert again.name == "S2"
