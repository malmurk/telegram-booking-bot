"""End-to-end conversation through the real aiogram Dispatcher, with Telegram mocked out."""

import asyncio
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from bot.booking import CANCELLED, CONFIRMED
from bot.config import Config
from bot.db import Database
from bot.keyboards import BookingCb, DayCb, LangCb, MenuCb, ServiceCb, SlotCb
from bot.main import build_dispatcher, make_bot
from bot.notify import send_due_reminders
from bot.testing import FAKE_TOKEN, FakeTelegram, MockSession

ADMIN = 999
ION = 111  # Romanian-speaking client
OLGA = 222  # Russian-speaking client


class Clock:
    def __init__(self, now: datetime) -> None:
        self.value = now

    def __call__(self) -> datetime:
        return self.value


def buttons(request) -> list[str]:
    markup = getattr(request, "reply_markup", None)
    if markup is None or not hasattr(markup, "inline_keyboard"):
        return []
    return [b.callback_data for row in markup.inline_keyboard for b in row]


async def scenario(tmp: Path) -> None:
    clock = Clock(datetime(2026, 10, 26, 9, 0))  # Monday 09:00
    config = Config(bot_token=FAKE_TOKEN, admin_ids=frozenset({ADMIN}), db_path=tmp / "b.db",
                    timezone=ZoneInfo("Europe/Chisinau"), clock=clock)
    db = Database(config.db_path)
    session = MockSession()
    bot = make_bot(FAKE_TOKEN, session=session)
    dp = build_dispatcher(config, db)
    tg = FakeTelegram(dp, bot)

    async def ion(action, *args):
        await action(ION, *args, name="Ion", lang="ro")

    async def olga(action, *args):
        await action(OLGA, *args, name="Olga", lang="ru")

    # /start picks the language from the Telegram app (ro)
    await ion(tg.send_text, "/start")
    (welcome,) = session.pop()
    assert "Demo Barbershop" in welcome.text and MenuCb(action="book").pack() in buttons(welcome)
    assert db.get_lang(ION) == "ro"

    # service -> day -> slot
    await ion(tg.press, MenuCb(action="book").pack())
    reqs = session.pop()
    assert any("Alege serviciul" in r.text for r in reqs if r.__api_method__ == "editMessageText")
    await ion(tg.press, ServiceCb(id="haircut").pack())
    edit = next(r for r in session.pop() if r.__api_method__ == "editMessageText")
    assert DayCb(day="2026-10-27").pack() in buttons(edit)
    assert DayCb(day="2026-11-01").pack() not in buttons(edit)  # Sunday: closed
    await ion(tg.press, DayCb(day="2026-10-27").pack())
    edit = next(r for r in session.pop() if r.__api_method__ == "editMessageText")
    assert SlotCb(hm="1000").pack() in buttons(edit)

    # Olga races for the same slot while Ion is typing his details
    await olga(tg.send_text, "/book")
    await olga(tg.press, ServiceCb(id="haircut").pack())
    await olga(tg.press, DayCb(day="2026-10-27").pack())
    await olga(tg.press, SlotCb(hm="1000").pack())
    await olga(tg.send_text, "Olga")
    await olga(tg.send_text, "+373 79 000 111")
    session.pop()

    await ion(tg.press, SlotCb(hm="1000").pack())
    await ion(tg.send_text, "Ion Popescu")
    ask_phone = session.pop()[-1]
    assert ask_phone.reply_markup.keyboard[0][0].request_contact is True
    await ion(tg.send_text, "not a phone")
    assert "Exemplu" in session.pop()[-1].text
    await ion(tg.send_contact, "+37369123456")
    summary = session.pop()[-1]
    assert "Ion Popescu" in summary.text and "+37369123456" in summary.text and "250 MDL" in summary.text

    # Ion confirms first -> admin is notified with Confirm/Cancel buttons
    await ion(tg.press, MenuCb(action="confirm").pack())
    reqs = session.pop()
    admin_msg = next(r for r in reqs if r.__api_method__ == "sendMessage" and r.chat_id == ADMIN)
    assert "Ion Popescu" in admin_msg.text
    assert BookingCb(action="admin_confirm", id=1).pack() in buttons(admin_msg)

    # Olga confirms the same slot -> conflict, she is shown the remaining times
    await olga(tg.press, MenuCb(action="confirm").pack())
    edit = next(r for r in session.pop() if r.__api_method__ == "editMessageText")
    assert "только что заняли" in edit.text
    assert SlotCb(hm="1000").pack() not in buttons(edit)
    assert SlotCb(hm="1030").pack() not in buttons(edit)  # 10:30-11:15 overlaps 10:00-10:45
    assert SlotCb(hm="1100").pack() in buttons(edit)
    assert len(db.all_bookings()) == 1

    # admin confirms -> client gets a Romanian confirmation
    await tg.press(ADMIN, BookingCb(action="admin_confirm", id=1).pack(), name="Boss")
    reqs = session.pop()
    to_ion = next(r for r in reqs if r.__api_method__ == "sendMessage" and r.chat_id == ION)
    assert "confirmată" in to_ion.text
    assert db.get(1).status == CONFIRMED
    # a second press (another admin, double tap) is refused, client is not spammed
    await tg.press(ADMIN, BookingCb(action="admin_confirm", id=1).pack(), name="Boss")
    assert not [r for r in session.pop() if r.__api_method__ == "sendMessage"]

    # admin tools
    await tg.send_text(ADMIN, "/today 2026-10-27", name="Boss")
    (today,) = session.pop()
    assert "10:00–10:45" in today.text and "Ion Popescu" in today.text
    await tg.send_text(ADMIN, "/export", name="Boss")
    (export,) = session.pop()
    assert export.__api_method__ == "sendDocument"
    assert "Ion Popescu" in export.document.data.decode("utf-8-sig")

    # non-admins can't use admin commands or buttons
    await olga(tg.send_text, "/export")
    assert not [r for r in session.pop() if r.__api_method__ == "sendDocument"]
    await olga(tg.press, BookingCb(action="admin_cancel", id=1).pack())
    session.pop()
    assert db.get(1).status == CONFIRMED

    # reminder job: nothing before time, exactly one at time, none afterwards
    assert await send_due_reminders(bot, db, config) == 0
    clock.value = datetime(2026, 10, 26, 10, 0)  # 24h before the visit
    assert await send_due_reminders(bot, db, config) == 1
    (reminder,) = session.pop()
    assert reminder.chat_id == ION and "Amintire" in reminder.text
    assert await send_due_reminders(bot, db, config) == 0

    # language switch + /mybookings + client cancel (admin notified)
    await ion(tg.press, LangCb(code="en").pack())
    assert "Language set" in session.pop()[0].text
    await ion(tg.send_text, "/mybookings")
    (mine,) = session.pop()
    assert "#1" in mine.text and "confirmed" in mine.text
    await ion(tg.press, BookingCb(action="client_cancel", id=1).pack())
    reqs = session.pop()
    assert db.get(1).status == CANCELLED
    assert any(r.__api_method__ == "sendMessage" and r.chat_id == ADMIN and "cancelled" in r.text for r in reqs)

    # Olga can't cancel someone else's booking
    await olga(tg.press, BookingCb(action="client_cancel", id=1).pack())
    session.pop()

    db.close()
    await bot.session.close()


def test_full_booking_conversation(tmp_path):
    asyncio.run(scenario(tmp_path))
