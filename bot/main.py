from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from .config import Config, load_config
from .db import Database
from .handlers.admin import build_admin_router
from .handlers.user import build_user_router
from .notify import send_due_reminders

log = logging.getLogger("bot")

REMINDER_INTERVAL_SEC = 60


def build_dispatcher(config: Config, db: Database) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp["config"] = config
    dp["db"] = db
    dp.include_router(build_admin_router(config.admin_ids))  # admin first: its filters are narrower
    dp.include_router(build_user_router())
    return dp


async def reminder_loop(bot: Bot, db: Database, config: Config, interval: float = REMINDER_INTERVAL_SEC) -> None:
    """Background job: every minute, send reminders that are due.

    Reminder times are stored in SQLite, so restarts never lose a reminder; a
    reminder whose time passed while the bot was down is sent on the next tick
    (as long as the visit itself hasn't started yet).
    """
    while True:
        try:
            sent = await send_due_reminders(bot, db, config)
            if sent:
                log.info("sent %d reminder(s)", sent)
        except Exception:  # keep the job alive whatever happens
            log.exception("reminder pass failed")
        await asyncio.sleep(interval)


def make_bot(token: str, **kwargs: object) -> Bot:
    return Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML), **kwargs)  # type: ignore[arg-type]


def build_app(config: Config, db: Database, reminder_interval: float = REMINDER_INTERVAL_SEC) -> Dispatcher:
    """Dispatcher plus lifecycle hooks: bot menu commands, reminder job, clean shutdown."""
    dp = build_dispatcher(config, db)
    tasks: list[asyncio.Task[None]] = []

    @dp.startup()
    async def on_startup(bot: Bot) -> None:
        await bot.set_my_commands([
            BotCommand(command="start", description="Menu / Меню / Meniu"),
            BotCommand(command="book", description="Book / Записаться / Programare"),
            BotCommand(command="mybookings", description="My bookings / Мои записи / Programările mele"),
            BotCommand(command="language", description="Language / Язык / Limba"),
        ])
        tasks.append(asyncio.create_task(reminder_loop(bot, db, config, reminder_interval)))

    @dp.shutdown()
    async def on_shutdown() -> None:
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        db.close()

    return dp


async def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()
    if not config.admin_ids:
        log.warning("ADMIN_IDS is empty: nobody will receive new bookings. Send /myid to the bot to get yours.")
    bot = make_bot(config.bot_token)
    try:
        me = await bot.get_me()
    except TelegramUnauthorizedError:
        await bot.session.close()
        raise SystemExit("Telegram rejected BOT_TOKEN. Get a valid token from @BotFather (see README).") from None
    log.info("authorized as @%s, admins=%s", me.username, sorted(config.admin_ids))
    dp = build_app(config, Database(config.db_path))
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
