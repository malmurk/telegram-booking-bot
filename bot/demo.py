"""Offline demo: `python -m bot.demo`

Runs a full booking conversation through the real bot code with Telegram mocked
out (see bot/testing.py) and prints what each person would see. Needs no token
and no network; uses a throwaway in-memory database.
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Config
from .db import Database
from .keyboards import BookingCb, DayCb, MenuCb, ServiceCb, SlotCb
from .main import build_dispatcher, make_bot
from .notify import send_due_reminders
from .testing import FAKE_TOKEN, FakeTelegram, MockSession

CLIENT, ADMIN = 111, 999
NAMES = {CLIENT: "client", ADMIN: "admin"}


def _plain(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


def _print(session: MockSession) -> None:
    for r in session.pop():
        api = r.__api_method__
        if api not in ("sendMessage", "editMessageText", "sendDocument"):
            continue
        who = NAMES.get(r.chat_id, str(r.chat_id)) if r.chat_id else "client"
        text = _plain(getattr(r, "text", None) or getattr(r, "caption", None) or "")
        print(f"  bot -> {who} [{api}]")
        for line in text.splitlines():
            print(f"      | {line}")
        markup = getattr(r, "reply_markup", None)
        rows = getattr(markup, "inline_keyboard", None) or getattr(markup, "keyboard", None) or []
        labels = [b.text for row in rows for b in row]
        if labels:
            print(f"      buttons: {' | '.join(labels)}")


async def demo() -> None:
    clock_now = [datetime(2026, 10, 26, 9, 0)]  # a Monday morning
    config = Config(bot_token=FAKE_TOKEN, admin_ids=frozenset({ADMIN}), db_path=Path(":memory:"),
                    timezone=ZoneInfo("Europe/Chisinau"), clock=lambda: clock_now[0])
    db = Database(":memory:")
    session = MockSession()
    bot = make_bot(FAKE_TOKEN, session=session)
    tg = FakeTelegram(build_dispatcher(config, db), bot)

    steps = [
        ("client sends /start", tg.send_text(CLIENT, "/start", name="Ion")),
        ("client taps 'Book a visit'", tg.press(CLIENT, MenuCb(action="book").pack(), name="Ion")),
        ("client taps 'Haircut'", tg.press(CLIENT, ServiceCb(id="haircut").pack(), name="Ion")),
        ("client taps 'Tue 27.10'", tg.press(CLIENT, DayCb(day="2026-10-27").pack(), name="Ion")),
        ("client taps '10:00'", tg.press(CLIENT, SlotCb(hm="1000").pack(), name="Ion")),
        ("client types name", tg.send_text(CLIENT, "Ion Popescu", name="Ion")),
        ("client shares phone", tg.send_contact(CLIENT, "+37369123456", name="Ion")),
        ("client taps 'Confirm'", tg.press(CLIENT, MenuCb(action="confirm").pack(), name="Ion")),
        ("admin taps 'Confirm'", tg.press(ADMIN, BookingCb(action="admin_confirm", id=1).pack(), name="Boss")),
        ("admin sends /today 2026-10-27", tg.send_text(ADMIN, "/today 2026-10-27", name="Boss")),
    ]
    for title, step in steps:
        print(f"\n>> {title}")
        await step
        _print(session)

    print("\n>> clock moves to Mon 26.10 10:00 (24h before the visit); reminder job runs")
    clock_now[0] = datetime(2026, 10, 26, 10, 0)
    await send_due_reminders(bot, db, config)
    _print(session)

    db.close()
    await bot.session.close()
    print("\nDemo finished: real handlers, mocked Telegram, no network.")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    asyncio.run(demo())
