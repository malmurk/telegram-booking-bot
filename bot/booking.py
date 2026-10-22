"""Pure booking logic: slots, conflicts, status transitions, reminders, CSV.

Nothing in this module touches Telegram, the network or the database, so it is
covered by fast unit tests. All datetimes are naive and in the business's local
time zone (a salon works in exactly one time zone).
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

PENDING = "pending"
CONFIRMED = "confirmed"
CANCELLED = "cancelled"
ACTIVE_STATUSES = (PENDING, CONFIRMED)

Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class Booking:
    id: int
    user_id: int
    client_name: str
    phone: str
    service_id: str
    start_at: datetime
    end_at: datetime
    status: str
    created_at: datetime
    remind_at: datetime | None
    reminded: bool


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Half-open intervals: a booking ending at 11:00 does not clash with one starting at 11:00."""
    return a_start < b_end and b_start < a_end


def is_slot_free(start: datetime, duration: timedelta, busy: Iterable[Interval]) -> bool:
    end = start + duration
    return not any(overlaps(start, end, b_start, b_end) for b_start, b_end in busy)


def free_slots(
    day: date,
    duration: timedelta,
    hours: Mapping[int, tuple[time, time]],
    busy: Iterable[Interval],
    now: datetime,
    step: timedelta = timedelta(minutes=30),
    min_lead: timedelta = timedelta(0),
) -> list[datetime]:
    """Start times on `day` where a service of `duration` fits without conflicts."""
    if day.weekday() not in hours:
        return []
    busy = list(busy)
    open_t, close_t = hours[day.weekday()]
    cursor = datetime.combine(day, open_t)
    close = datetime.combine(day, close_t)
    earliest = now + min_lead
    slots: list[datetime] = []
    while cursor + duration <= close:
        if cursor >= earliest and is_slot_free(cursor, duration, busy):
            slots.append(cursor)
        cursor += step
    return slots


def candidate_days(today: date, horizon_days: int, hours: Mapping[int, tuple[time, time]]) -> list[date]:
    """Open days from today (inclusive) within the booking horizon."""
    days = (today + timedelta(days=i) for i in range(horizon_days))
    return [d for d in days if d.weekday() in hours]


_TRANSITIONS = {
    ("admin_confirm", PENDING): CONFIRMED,
    ("admin_cancel", PENDING): CANCELLED,
    ("admin_cancel", CONFIRMED): CANCELLED,
    ("client_cancel", PENDING): CANCELLED,
    ("client_cancel", CONFIRMED): CANCELLED,
}


def next_status(current: str, action: str) -> str | None:
    """New status for `action`, or None when the transition is not allowed."""
    return _TRANSITIONS.get((action, current))


def reminder_time(
    start: datetime,
    created: datetime,
    lead: timedelta,
    fallback_lead: timedelta = timedelta(hours=1),
) -> datetime | None:
    """When to remind the client.

    Normally `lead` before the visit. If the booking is made too late for that,
    fall back to `fallback_lead` before; if even that has passed, no reminder.
    """
    for candidate in (start - lead, start - fallback_lead):
        if candidate > created:
            return candidate
    return None


def is_reminder_due(booking: Booking, now: datetime) -> bool:
    return (
        booking.status == CONFIRMED
        and not booking.reminded
        and booking.remind_at is not None
        and booking.remind_at <= now < booking.start_at
    )


_PHONE_RE = re.compile(r"^\+?\d{7,15}$")


def normalize_phone(raw: str) -> str | None:
    """Strip spaces, dashes, dots and brackets; accept 7-15 digits with optional leading +."""
    cleaned = re.sub(r"[\s\-().]", "", raw.strip())
    return cleaned if _PHONE_RE.match(cleaned) else None


def normalize_name(raw: str) -> str | None:
    name = " ".join(raw.split())
    if not 2 <= len(name) <= 64 or name.startswith("/"):
        return None
    return name


def bookings_to_csv(bookings: Sequence[Booking], service_names: Mapping[str, str]) -> bytes:
    """CSV export; UTF-8 with BOM so Excel opens Cyrillic/Romanian text correctly."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "date", "start", "end", "service", "client", "phone", "status", "created_at"])
    for b in bookings:
        writer.writerow(
            [
                b.id,
                b.start_at.strftime("%Y-%m-%d"),
                b.start_at.strftime("%H:%M"),
                b.end_at.strftime("%H:%M"),
                service_names.get(b.service_id, b.service_id),
                b.client_name,
                b.phone,
                b.status,
                b.created_at.strftime("%Y-%m-%d %H:%M"),
            ]
        )
    return buf.getvalue().encode("utf-8-sig")
