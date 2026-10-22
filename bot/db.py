"""SQLite storage. Synchronous sqlite3 is plenty for a salon-sized bot and keeps
dependencies minimal; every query is a few milliseconds."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .booking import ACTIVE_STATUSES, CONFIRMED, Booking, Interval, next_status

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    lang    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    client_name TEXT    NOT NULL,
    phone       TEXT    NOT NULL,
    service_id  TEXT    NOT NULL,
    start_at    TEXT    NOT NULL,
    end_at      TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    remind_at   TEXT,
    reminded    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_bookings_start ON bookings (start_at);
CREATE INDEX IF NOT EXISTS ix_bookings_user ON bookings (user_id);
"""

_ACTIVE_SQL = "('" + "','".join(ACTIVE_STATUSES) + "')"


class SlotTaken(Exception):
    """Someone else booked an overlapping slot first."""


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def _row_to_booking(row: sqlite3.Row) -> Booking:
    return Booking(
        id=row["id"],
        user_id=row["user_id"],
        client_name=row["client_name"],
        phone=row["phone"],
        service_id=row["service_id"],
        start_at=datetime.fromisoformat(row["start_at"]),
        end_at=datetime.fromisoformat(row["end_at"]),
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
        remind_at=_dt(row["remind_at"]),
        reminded=bool(row["reminded"]),
    )


class Database:
    def __init__(self, path: str | Path) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None: autocommit, explicit BEGIN IMMEDIATE where atomicity matters
        self.conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # users -----------------------------------------------------------------
    def get_lang(self, user_id: int) -> str | None:
        row = self.conn.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row["lang"] if row else None

    def set_lang(self, user_id: int, lang: str) -> None:
        self.conn.execute(
            "INSERT INTO users (user_id, lang) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET lang = excluded.lang",
            (user_id, lang),
        )

    # bookings --------------------------------------------------------------
    def busy_intervals(self, day: date) -> list[Interval]:
        start = datetime.combine(day, time.min)
        end = start + timedelta(days=1)
        rows = self.conn.execute(
            f"SELECT start_at, end_at FROM bookings WHERE status IN {_ACTIVE_SQL} "
            "AND start_at < ? AND end_at > ?",
            (_iso(end), _iso(start)),
        ).fetchall()
        return [(datetime.fromisoformat(r["start_at"]), datetime.fromisoformat(r["end_at"])) for r in rows]

    def create_booking(
        self,
        *,
        user_id: int,
        client_name: str,
        phone: str,
        service_id: str,
        start_at: datetime,
        end_at: datetime,
        created_at: datetime,
        remind_at: datetime | None,
    ) -> Booking:
        """Insert atomically; raises SlotTaken if an active booking overlaps."""
        cur = self.conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        try:
            clash = cur.execute(
                f"SELECT 1 FROM bookings WHERE status IN {_ACTIVE_SQL} AND start_at < ? AND end_at > ? LIMIT 1",
                (_iso(end_at), _iso(start_at)),
            ).fetchone()
            if clash:
                raise SlotTaken
            cur.execute(
                "INSERT INTO bookings (user_id, client_name, phone, service_id, start_at, end_at, "
                "status, created_at, remind_at) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                (user_id, client_name, phone, service_id, _iso(start_at), _iso(end_at),
                 _iso(created_at), _iso(remind_at)),
            )
            booking_id = cur.lastrowid
            cur.execute("COMMIT")
        except BaseException:
            cur.execute("ROLLBACK")
            raise
        booking = self.get(booking_id)
        assert booking is not None
        return booking

    def get(self, booking_id: int) -> Booking | None:
        row = self.conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        return _row_to_booking(row) if row else None

    def apply_action(self, booking_id: int, action: str) -> Booking | None:
        """Apply a status transition. Returns the updated booking, or None if not allowed."""
        booking = self.get(booking_id)
        if booking is None:
            return None
        new = next_status(booking.status, action)
        if new is None:
            return None
        # compare-and-set so two admins pressing buttons at once can't both win
        cur = self.conn.execute(
            "UPDATE bookings SET status = ? WHERE id = ? AND status = ?",
            (new, booking_id, booking.status),
        )
        return self.get(booking_id) if cur.rowcount == 1 else None

    def user_upcoming(self, user_id: int, now: datetime) -> list[Booking]:
        rows = self.conn.execute(
            f"SELECT * FROM bookings WHERE user_id = ? AND status IN {_ACTIVE_SQL} AND start_at >= ? "
            "ORDER BY start_at",
            (user_id, _iso(now)),
        ).fetchall()
        return [_row_to_booking(r) for r in rows]

    def day_schedule(self, day: date) -> list[Booking]:
        start = datetime.combine(day, time.min)
        rows = self.conn.execute(
            f"SELECT * FROM bookings WHERE status IN {_ACTIVE_SQL} AND start_at >= ? AND start_at < ? "
            "ORDER BY start_at",
            (_iso(start), _iso(start + timedelta(days=1))),
        ).fetchall()
        return [_row_to_booking(r) for r in rows]

    def all_bookings(self) -> list[Booking]:
        rows = self.conn.execute("SELECT * FROM bookings ORDER BY start_at").fetchall()
        return [_row_to_booking(r) for r in rows]

    def due_reminders(self, now: datetime) -> list[Booking]:
        rows = self.conn.execute(
            "SELECT * FROM bookings WHERE status = ? AND reminded = 0 AND remind_at IS NOT NULL "
            "AND remind_at <= ? AND start_at > ? ORDER BY remind_at",
            (CONFIRMED, _iso(now), _iso(now)),
        ).fetchall()
        return [_row_to_booking(r) for r in rows]

    def mark_reminded(self, booking_id: int) -> None:
        self.conn.execute("UPDATE bookings SET reminded = 1 WHERE id = ?", (booking_id,))
