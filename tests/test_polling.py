"""The real polling loop (start_polling) with Telegram mocked: startup hooks run,
the reminder job fires on its own, and shutdown is clean."""

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bot.config import Config
from bot.db import Database
from bot.main import build_app, make_bot
from bot.testing import FAKE_TOKEN, MockSession


async def scenario(tmp_path) -> None:
    now = datetime(2026, 10, 26, 10, 0)
    config = Config(bot_token=FAKE_TOKEN, admin_ids=frozenset({1}), db_path=tmp_path / "p.db",
                    timezone=ZoneInfo("Europe/Chisinau"), clock=lambda: now)
    db = Database(config.db_path)
    start = now + timedelta(hours=24)
    b = db.create_booking(user_id=42, client_name="Ana", phone="+37360000000", service_id="beard",
                          start_at=start, end_at=start + timedelta(minutes=30),
                          created_at=now - timedelta(days=2), remind_at=now - timedelta(minutes=1))
    db.apply_action(b.id, "admin_confirm")

    session = MockSession()
    bot = make_bot(FAKE_TOKEN, session=session)
    dp = build_app(config, db, reminder_interval=0.05)
    polling = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    for _ in range(100):  # wait up to ~5s for the reminder job to fire by itself
        await asyncio.sleep(0.05)
        if any(r.__api_method__ == "sendMessage" for r in session.requests):
            break
    await dp.stop_polling()
    await asyncio.wait_for(polling, timeout=5)

    apis = [r.__api_method__ for r in session.requests]
    assert "setMyCommands" in apis
    assert "getUpdates" in apis
    reminders = [r for r in session.requests if r.__api_method__ == "sendMessage"]
    assert len(reminders) == 1 and reminders[0].chat_id == 42  # sent once, not every tick


def test_polling_lifecycle(tmp_path):
    asyncio.run(scenario(tmp_path))
