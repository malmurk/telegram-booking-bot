from datetime import date, datetime, timedelta

import pytest

from bot.booking import CANCELLED, CONFIRMED, PENDING
from bot.db import Database, SlotTaken

DAY = date(2026, 10, 27)
NOW = datetime(2026, 10, 26, 9, 0)


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


def book(db: Database, h: int, m: int = 0, minutes: int = 45, user_id: int = 1):
    start = datetime(DAY.year, DAY.month, DAY.day, h, m)
    return db.create_booking(
        user_id=user_id, client_name="Ion", phone="+37369123456", service_id="haircut",
        start_at=start, end_at=start + timedelta(minutes=minutes), created_at=NOW,
        remind_at=start - timedelta(hours=24),
    )


def test_create_and_read_back(db):
    b = book(db, 10)
    assert b.id == 1 and b.status == PENDING
    assert db.get(b.id) == b
    assert db.busy_intervals(DAY) == [(b.start_at, b.end_at)]


def test_overlapping_booking_is_rejected(db):
    book(db, 10)
    with pytest.raises(SlotTaken):
        book(db, 10, 30, user_id=2)  # 10:30 overlaps 10:00-10:45
    assert len(db.all_bookings()) == 1  # the failed insert left nothing behind


def test_back_to_back_is_allowed(db):
    book(db, 10)
    book(db, 10, 45, user_id=2)
    assert len(db.day_schedule(DAY)) == 2


def test_cancelled_booking_frees_the_slot(db):
    b = book(db, 10)
    assert db.apply_action(b.id, "client_cancel").status == CANCELLED
    assert db.busy_intervals(DAY) == []
    book(db, 10, user_id=2)  # no SlotTaken


def test_invalid_transition_returns_none(db):
    b = book(db, 10)
    assert db.apply_action(b.id, "admin_confirm").status == CONFIRMED
    assert db.apply_action(b.id, "admin_confirm") is None
    assert db.apply_action(999, "admin_confirm") is None


def test_user_upcoming_excludes_past_and_cancelled(db):
    a = book(db, 10, user_id=7)
    b = book(db, 12, user_id=7)
    book(db, 14, user_id=8)
    db.apply_action(b.id, "client_cancel")
    assert [x.id for x in db.user_upcoming(7, NOW)] == [a.id]
    assert db.user_upcoming(7, datetime(2026, 10, 27, 11)) == []


def test_due_reminders_only_confirmed_once(db):
    b = book(db, 10)  # remind_at = 2026-10-26 10:00
    at = datetime(2026, 10, 26, 10, 0)
    assert db.due_reminders(at) == []  # still pending
    db.apply_action(b.id, "admin_confirm")
    assert db.due_reminders(at - timedelta(minutes=1)) == []
    assert [x.id for x in db.due_reminders(at)] == [b.id]
    db.mark_reminded(b.id)
    assert db.due_reminders(at) == []


def test_language_upsert(db):
    assert db.get_lang(5) is None
    db.set_lang(5, "ro")
    db.set_lang(5, "ru")
    assert db.get_lang(5) == "ru"
