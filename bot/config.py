from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: frozenset[int]
    db_path: Path
    timezone: ZoneInfo
    reminder_hours: int = 24
    clock: Callable[[], datetime] | None = field(default=None, compare=False)  # tests/demo: fixed time

    def now(self) -> datetime:
        """Current local business time, naive (all stored datetimes are local)."""
        if self.clock is not None:
            return self.clock()
        return datetime.now(self.timezone).replace(tzinfo=None, microsecond=0)


def parse_admin_ids(raw: str) -> frozenset[int]:
    return frozenset(int(part) for part in raw.replace(";", ",").split(",") if part.strip())


def load_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")
    return Config(
        bot_token=token,
        admin_ids=parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        db_path=Path(os.getenv("DB_PATH", "data/bookings.db")),
        timezone=ZoneInfo(os.getenv("TIMEZONE", "Europe/Chisinau")),
        reminder_hours=int(os.getenv("REMINDER_HOURS", "24")),
    )
