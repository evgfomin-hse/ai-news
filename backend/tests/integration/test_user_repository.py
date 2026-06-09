from sqlalchemy.orm import Session

from app.models import User
from app.repositories.user_repository import UserRepository


def test_get_by_id_returns_none_when_absent(db: Session):
    assert UserRepository(db).get_by_id(999) is None


def test_get_by_id_returns_existing_user(db: Session, user: User):
    assert UserRepository(db).get_by_id(user.id).id == user.id


def test_list_all_ids_returns_every_user(db: Session, user: User):
    db.add(User(subject="g2", email="b@example.com"))
    db.commit()
    assert set(UserRepository(db).list_all_ids()) == {user.id, user.id + 1}


def test_get_or_create_inserts_when_missing(db: Session):
    repo = UserRepository(db)
    row = repo.get_or_create(
        subject="new-sub",
        name="N",
        picture="https://example.com/p.png",
        email="n@example.com",
    )
    assert row.id is not None
    assert row.email == "n@example.com"
    assert row.picture == "https://example.com/p.png"


def test_get_or_create_uses_placeholder_email_when_missing(db: Session):
    row = UserRepository(db).get_or_create(
        subject="no-email-sub", name="X", picture=None, email=None
    )
    assert row.email == "no-email-sub@oauth-subject.local"


def test_get_or_create_updates_existing_user_profile(db: Session, user: User):
    updated = UserRepository(db).get_or_create(
        subject=user.subject,
        name="Renamed",
        picture="https://example.com/new.png",
        email="renamed@example.com",
    )
    assert updated.id == user.id
    assert updated.name == "Renamed"
    assert updated.picture == "https://example.com/new.png"
    assert updated.email == "renamed@example.com"


def test_get_or_create_keeps_existing_email_when_new_is_blank(db: Session, user: User):
    original = user.email
    updated = UserRepository(db).get_or_create(
        subject=user.subject, name="N", picture=None, email="   "
    )
    assert updated.email == original


def test_update_profile_no_op_when_all_fields_none(db: Session, user: User):
    snapshot = (user.name, user.picture)
    UserRepository(db).update_profile(user, name=None, picture=None)
    assert (user.name, user.picture) == snapshot


def test_update_profile_changes_only_provided_fields(db: Session, user: User):
    repo = UserRepository(db)
    repo.update_profile(user, name="New Name", picture=None)
    db.commit()
    db.expire_all()
    refreshed = repo.get_by_id(user.id)
    assert refreshed.name == "New Name"
    assert refreshed.picture is None
