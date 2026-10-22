from datetime import date, datetime, time, timedelta

import pytest

from bot import catalog
from bot.booking import (
    CANCELLED,
    CONFIRMED,
    PENDING,
    Booking,
    bookings_to_csv,
    candidate_days,
    free_slots,
    is_reminder_due,
    is_slot_free,
    next_status,
    normalize_name,
    normalize_phone,
    overlaps,
    reminder_time,
)

HOURS = {0: (time(10), time(13)), 1: (time(10), time(13))}  # Mon, Tue 10:00-13:00
MON = date(2026, 10, 26)
assert MON.weekday() == 0


def dt(h: int, m: int = 0, day: date = MON) -> datetime:
    return datetime.combine(day, time(h, m))


# --- conflicts ---------------------------------------------------------------

def test_overlap_is_half_open():
    assert overlaps(dt(10), dt(11), dt(10, 30), dt(11, 30))
    assert not overlaps(dt(10), dt(11), dt(11), dt(12))  # back-to-back is fine
    assert overlaps(dt(10), dt(12), dt(10, 30), dt(11))  # containment


def test_is_slot_free_checks_full_duration():
    busy = [(dt(11), dt(11, 45))]
    assert is_slot_free(dt(10), timedelta(minutes=60), busy)
    assert not is_slot_free(dt(10, 30), timedelta(minutes=45), busy)  # would end 11:15
    assert is_slot_free(dt(11, 45), timedelta(minutes=30), busy)


# --- slot generation -----------------------------------------------------------

def test_free_slots_empty_day_respects_closing_time():
    slots = free_slots(MON, timedelta(minutes=45), HOURS, [], now=dt(0))
    assert slots[0] == dt(10)
    assert slots[-1] == dt(12)  # 12:00 + 45m <= 13:00; 12:30 would overrun
    assert dt(12, 30) not in slots


def test_free_slots_skip_busy_and_neighbours():
    busy = [(dt(11), dt(11, 45))]
    slots = free_slots(MON, timedelta(minutes=45), HOURS, busy, now=dt(0))
    assert dt(10) in slots
    assert dt(10, 30) not in slots  # 10:30-11:15 clashes
    assert dt(11) not in slots
    assert dt(11, 30) not in slots  # 11:30-12:15 clashes with 11:00-11:45
    assert dt(12) in slots


def test_free_slots_hide_past_and_min_lead():
    slots = free_slots(MON, timedelta(minutes=30), HOURS, [], now=dt(10, 10), min_lead=timedelta(minutes=60))
    assert slots[0] == dt(11, 30)  # first grid slot >= 11:10


def test_closed_day_has_no_slots():
    sunday = MON + timedelta(days=6)
    assert free_slots(sunday, timedelta(minutes=30), HOURS, [], now=dt(0)) == []


def test_candidate_days_only_open_days():
    days = candidate_days(MON, 7, HOURS)
    assert days == [MON, MON + timedelta(days=1)]


def test_catalog_services_fit_into_working_day():
    for service in catalog.SERVICES:
        for wd, (o, c) in catalog.WORKING_HOURS.items():
            span = datetime.combine(MON, c) - datetime.combine(MON, o)
            assert timedelta(minutes=service.duration_min) <= span, (service.id, wd)


# --- status transitions ----------------------------------------------------------

@pytest.mark.parametrize(
    ("current", "action", "expected"),
    [
        (PENDING, "admin_confirm", CONFIRMED),
        (PENDING, "admin_cancel", CANCELLED),
        (CONFIRMED, "admin_cancel", CANCELLED),
        (CONFIRMED, "client_cancel", CANCELLED),
        (CONFIRMED, "admin_confirm", None),  # double confirm
        (CANCELLED, "admin_confirm", None),  # can't revive a cancelled booking
        (CANCELLED, "client_cancel", None),
    ],
)
def test_next_status(current, action, expected):
    assert next_status(current, action) == expected


# --- reminders ---------------------------------------------------------------

def test_reminder_normally_24h_before():
    start = dt(15, day=MON + timedelta(days=3))
    assert reminder_time(start, created=dt(9), lead=timedelta(hours=24)) == start - timedelta(hours=24)


def test_reminder_falls_back_to_1h_for_late_bookings():
    start = dt(15)
    assert reminder_time(start, created=dt(9), lead=timedelta(hours=24)) == dt(14)


def test_no_reminder_when_even_fallback_passed():
    assert reminder_time(dt(15), created=dt(14, 30), lead=timedelta(hours=24)) is None


def _booking(**over) -> Booking:
    base = dict(id=1, user_id=1, client_name="A", phone="+1234567", service_id="haircut",
                start_at=dt(15), end_at=dt(15, 45), status=CONFIRMED, created_at=dt(8),
                remind_at=dt(14), reminded=False)
    base.update(over)
    return Booking(**base)


def test_reminder_due_window():
    b = _booking()
    assert not is_reminder_due(b, dt(13, 59))
    assert is_reminder_due(b, dt(14))
    assert is_reminder_due(b, dt(14, 30))  # late tick (e.g. bot was restarted) still sends
    assert not is_reminder_due(b, dt(15))  # visit already started: too late
    assert not is_reminder_due(_booking(reminded=True), dt(14))
    assert not is_reminder_due(_booking(status=PENDING), dt(14))
    assert not is_reminder_due(_booking(remind_at=None), dt(14))


# --- input validation & export -------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+373 69 123 456", "+37369123456"),
        ("069-123-456", "069123456"),
        ("(022) 12.34.56", "022123456"),
        ("hello", None),
        ("123", None),
        ("+1234567890123456", None),
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_normalize_name():
    assert normalize_name("  Ion   Popescu ") == "Ion Popescu"
    assert normalize_name("A") is None
    assert normalize_name("/start") is None
    assert normalize_name("x" * 65) is None


def test_csv_export_has_bom_and_unicode():
    data = bookings_to_csv([_booking(client_name="Ștefan Ionuț")], {"haircut": "Стрижка"})
    assert data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig")
    header, row = text.strip().splitlines()
    assert header.startswith("id,date,start,end,service")
    assert "Ștefan Ionuț" in row and "Стрижка" in row and "15:00" in row
