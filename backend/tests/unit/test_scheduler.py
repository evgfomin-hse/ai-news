"""Unit tests for the nightly scheduler wiring — does NOT actually start APScheduler."""

from __future__ import annotations

from app.core.config import settings


def test_setup_scheduler_uses_summary_schedule_hour_from_settings(monkeypatch):
    from app import scheduler as sched_module

    monkeypatch.setattr(settings, "enable_summary_nightly_scheduler", True)
    monkeypatch.setattr(settings, "summary_schedule_hour", 3)
    monkeypatch.setattr(settings, "summary_schedule_timezone", "UTC")
    # Ensure no leftover from another test.
    sched_module._scheduler = None

    captured: dict = {}

    class _FakeScheduler:
        def __init__(self):
            self.jobs = []

        def add_job(self, func, trigger, *, id, replace_existing):
            captured["trigger"] = trigger
            captured["id"] = id
            captured["func"] = func

        def start(self):
            captured["started"] = True

        def shutdown(self, wait):
            captured["shutdown_wait"] = wait

    monkeypatch.setattr(sched_module, "AsyncIOScheduler", _FakeScheduler)
    sched_module.setup_scheduler()

    trigger = captured["trigger"]
    # CronTrigger stores fields; the simplest check is repr() containing "hour='3'".
    assert "hour='3'" in repr(trigger)
    assert captured["started"] is True
    assert captured["id"] == sched_module.SUMMARY_JOB_ID

    sched_module.shutdown_scheduler()


def test_setup_scheduler_noop_when_disabled(monkeypatch):
    from app import scheduler as sched_module

    monkeypatch.setattr(settings, "enable_summary_nightly_scheduler", False)
    sched_module._scheduler = None

    def _explode(*_a, **_kw):
        raise AssertionError("should not construct scheduler when disabled")

    monkeypatch.setattr(sched_module, "AsyncIOScheduler", _explode)

    sched_module.setup_scheduler()  # must not raise
    assert sched_module._scheduler is None
