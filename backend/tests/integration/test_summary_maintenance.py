from sqlalchemy.orm import Session

from app.models import User
from app.repositories.summary_repository import SummaryRepository
from app.services.summary_service import (
    MockSummaryService,
    SummaryMaintenanceService,
    insert_generated_summary_for_user,
    run_summary_generation_for_all_users,
)


def test_append_placeholder_for_user_inserts_one_row(db: Session, user: User):
    svc = SummaryMaintenanceService(db)
    assert svc.append_placeholder_for_user(user.id) == 1
    assert SummaryRepository(db).count_for_user(user.id) == 1


def test_run_bulk_for_all_users_inserts_one_per_user(db: Session, user: User):
    db.add(User(google_id="g2", email="b@example.com"))
    db.commit()

    stats = SummaryMaintenanceService(db).run_bulk_for_all_users()
    assert stats == {"users": 2, "rows_inserted": 2}


def test_insert_generated_summary_for_user_returns_one(db: Session, user: User):
    assert insert_generated_summary_for_user(db, user.id) == 1
    db.commit()
    assert SummaryRepository(db).count_for_user(user.id) == 1


def test_run_summary_generation_for_all_users_reports_counts(db: Session, user: User):
    stats = run_summary_generation_for_all_users(db)
    db.commit()
    assert stats["users"] == 1
    assert stats["rows_inserted"] == 1


def test_mock_summary_service_returns_sample_page():
    svc = MockSummaryService()
    resp = svc.get_summary_for_user(user_id=1, page=1, page_size=5)
    assert resp.total > 0
    assert len(resp.items) == 5
    assert resp.generated_at is not None


def test_mock_summary_service_clamps_high_page():
    svc = MockSummaryService()
    resp = svc.get_summary_for_user(user_id=1, page=999, page_size=10)
    assert resp.page == resp.total_pages
