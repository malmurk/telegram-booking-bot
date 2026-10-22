"""Outgoing messages that are not direct replies: admin alerts, client updates, reminders."""

from __future__ import annotations

import logging
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from . import catalog
from .booking import Booking
from .config import Config
from .db import Database
from .i18n import DEFAULT_LANG, fmt_day, fmt_time, t
from .keyboards import admin_decision

log = logging.getLogger(__name__)


def lang_of(db: Database, user_id: int) -> str:
    return db.get_lang(user_id) or DEFAULT_LANG


def booking_fields(lang: str, b: Booking) -> dict[str, object]:
    return {
        "id": b.id,
        "service": catalog.SERVICES_BY_ID[b.service_id].name(lang),
        "day": fmt_day(lang, b.start_at),
        "time": fmt_time(b.start_at),
        "end": fmt_time(b.end_at),
        "name": escape(b.client_name),
        "phone": escape(b.phone),
        "status": t(lang, f"status_{b.status}"),
        "address": catalog.ADDRESS,
    }


async def safe_send(bot: Bot, chat_id: int, text: str, **kwargs: object) -> bool:
    """Send, but never let one unreachable chat (blocked bot, never started) break the flow."""
    try:
        await bot.send_message(chat_id, text, **kwargs)  # type: ignore[arg-type]
        return True
    except TelegramAPIError as exc:
        log.warning("could not message %s: %s", chat_id, exc)
        return False


async def notify_admins_new(bot: Bot, db: Database, config: Config, b: Booking) -> None:
    for admin_id in config.admin_ids:
        lang = lang_of(db, admin_id)
        await safe_send(bot, admin_id, t(lang, "admin_new", **booking_fields(lang, b)),
                        reply_markup=admin_decision(lang, b.id))


async def notify_admins_client_cancelled(bot: Bot, db: Database, config: Config, b: Booking) -> None:
    for admin_id in config.admin_ids:
        lang = lang_of(db, admin_id)
        await safe_send(bot, admin_id, t(lang, "admin_client_cancelled", **booking_fields(lang, b)))


async def notify_client_decision(bot: Bot, db: Database, b: Booking) -> None:
    lang = lang_of(db, b.user_id)
    key = "client_confirmed" if b.status == "confirmed" else "client_admin_cancelled"
    await safe_send(bot, b.user_id, t(lang, key, phone=catalog.PHONE,
                                      **{k: v for k, v in booking_fields(lang, b).items() if k != "phone"}))


async def send_due_reminders(bot: Bot, db: Database, config: Config) -> int:
    """One pass of the reminder job. Returns how many reminders were sent."""
    sent = 0
    for b in db.due_reminders(config.now()):
        lang = lang_of(db, b.user_id)
        if await safe_send(bot, b.user_id, t(lang, "reminder", **booking_fields(lang, b))):
            sent += 1
        # mark even on failure: a client who blocked the bot must not be retried every minute
        db.mark_reminded(b.id)
    return sent
