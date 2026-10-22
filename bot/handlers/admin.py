"""Admin side: confirm/cancel requests, today's schedule, CSV export.

Admins are the Telegram user IDs listed in ADMIN_IDS. Each admin must press
/start in the bot once, otherwise Telegram does not let the bot message them.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import date

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from .. import catalog
from ..booking import bookings_to_csv
from ..config import Config
from ..db import Database
from ..i18n import fmt_day, t
from ..keyboards import BookingCb
from ..notify import booking_fields, lang_of, notify_client_decision


def build_admin_router(admin_ids: Collection[int]) -> Router:
    router = Router(name="admin")
    is_admin = F.from_user.id.in_(set(admin_ids))
    router.message.filter(is_admin)
    router.callback_query.filter(is_admin)

    @router.message(Command("admin"))
    async def cmd_admin(message: Message, db: Database) -> None:
        assert message.from_user
        await message.answer(t(lang_of(db, message.from_user.id), "admin_help"))

    @router.message(Command("today"))
    async def cmd_today(message: Message, command: CommandObject, db: Database, config: Config) -> None:
        assert message.from_user
        lang = lang_of(db, message.from_user.id)
        try:
            day = date.fromisoformat(command.args.strip()) if command.args else config.now().date()
        except ValueError:
            await message.answer(t(lang, "bad_date"))
            return
        bookings = db.day_schedule(day)
        label = fmt_day(lang, day)
        if not bookings:
            await message.answer(t(lang, "today_empty", day=label))
            return
        lines = [t(lang, "today_header", day=label)]
        lines += [t(lang, "today_item", **booking_fields(lang, b)) for b in bookings]
        await message.answer("\n".join(lines))

    @router.message(Command("export"))
    async def cmd_export(message: Message, db: Database, config: Config) -> None:
        assert message.from_user
        lang = lang_of(db, message.from_user.id)
        bookings = db.all_bookings()
        if not bookings:
            await message.answer(t(lang, "export_empty"))
            return
        names = {s.id: s.name(lang) for s in catalog.SERVICES}
        data = bookings_to_csv(bookings, names)
        filename = f"bookings_{config.now():%Y%m%d_%H%M}.csv"
        await message.answer_document(BufferedInputFile(data, filename=filename),
                                      caption=t(lang, "export_caption", count=len(bookings)))

    @router.callback_query(BookingCb.filter(F.action.in_({"admin_confirm", "admin_cancel"})))
    async def cb_decision(cb: CallbackQuery, callback_data: BookingCb, db: Database, bot: Bot) -> None:
        lang = lang_of(db, cb.from_user.id)
        booking = db.apply_action(callback_data.id, callback_data.action)
        if booking is None:
            await cb.answer(t(lang, "cannot_change"), show_alert=True)
            return
        if isinstance(cb.message, Message):
            original = cb.message.html_text or ""
            await cb.message.edit_text(original + t(lang, "admin_marked", status=t(lang, f"status_{booking.status}")),
                                       reply_markup=None)
        await cb.answer()
        await notify_client_decision(bot, db, booking)

    return router
