"""Client-side flow: menu -> service -> day -> time -> name -> phone -> confirm."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from html import escape
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardRemove, User

from .. import catalog
from .. import keyboards as kb
from ..booking import candidate_days, free_slots, normalize_name, normalize_phone, reminder_time
from ..config import Config
from ..db import Database, SlotTaken
from ..i18n import LANGS, WEEKDAYS, fmt_day, fmt_time, pick_lang, t
from ..notify import booking_fields, notify_admins_client_cancelled, notify_admins_new

_ROUTES: list[tuple[str, tuple[Any, ...], Callable[..., Any]]] = []


def on(observer: str, *filters: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Collect handlers so each Dispatcher gets a fresh Router (aiogram routers attach only once)."""
    def register(handler: Callable[..., Any]) -> Callable[..., Any]:
        _ROUTES.append((observer, filters, handler))
        return handler
    return register


def build_user_router() -> Router:
    router = Router(name="user")
    for observer, filters, handler in _ROUTES:
        getattr(router, observer).register(handler, *filters)
    return router


class BookingForm(StatesGroup):
    name = State()
    phone = State()
    confirm = State()


def user_lang(db: Database, user: User) -> str:
    lang = db.get_lang(user.id)
    if lang is None:
        lang = pick_lang(user.language_code)
        db.set_lang(user.id, lang)
    return lang


async def show(cb: CallbackQuery, bot: Bot, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Edit the message the button belongs to (keeps the chat tidy)."""
    if isinstance(cb.message, Message):
        await cb.message.edit_text(text, reply_markup=markup)
    else:  # message too old to edit
        await bot.send_message(cb.from_user.id, text, reply_markup=markup)
    await cb.answer()


def _slots_for(db: Database, config: Config, service_id: str, day: date) -> list[datetime]:
    service = catalog.SERVICES_BY_ID[service_id]
    return free_slots(
        day,
        timedelta(minutes=service.duration_min),
        catalog.WORKING_HOURS,
        db.busy_intervals(day),
        now=config.now(),
        step=timedelta(minutes=catalog.SLOT_STEP_MIN),
        min_lead=timedelta(minutes=catalog.MIN_LEAD_MIN),
    )


def _days_with_slots(db: Database, config: Config, service_id: str) -> list[date]:
    days = candidate_days(config.now().date(), catalog.BOOKING_HORIZON_DAYS, catalog.WORKING_HOURS)
    return [d for d in days if _slots_for(db, config, service_id, d)]


def _hours_text(lang: str) -> str:
    lines = []
    for wd, label in enumerate(WEEKDAYS[lang]):
        if wd in catalog.WORKING_HOURS:
            o, c = catalog.WORKING_HOURS[wd]
            lines.append(t(lang, "hours_line", day=label, open=o.strftime("%H:%M"), close=c.strftime("%H:%M")))
        else:
            lines.append(f"{label}: {t(lang, 'closed')}")
    return "\n".join(lines)


# --- entry points -------------------------------------------------------------

@on("message", CommandStart())
@on("message", Command("menu"))
async def cmd_start(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    assert message.from_user
    lang = user_lang(db, message.from_user)
    await message.answer(
        t(lang, "welcome", name=escape(message.from_user.first_name), business=catalog.BUSINESS_NAME),
        reply_markup=kb.main_menu(lang),
    )


@on("message", Command("myid"))
async def cmd_myid(message: Message, db: Database) -> None:
    assert message.from_user
    await message.answer(t(user_lang(db, message.from_user), "myid", id=message.from_user.id))


@on("message", Command("language"))
async def cmd_language(message: Message, db: Database) -> None:
    assert message.from_user
    await message.answer(t(user_lang(db, message.from_user), "lang_choose"), reply_markup=kb.languages())


@on("message", Command("book"))
async def cmd_book(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    assert message.from_user
    lang = user_lang(db, message.from_user)
    await message.answer(t(lang, "choose_service"), reply_markup=kb.services(lang))


@on("message", Command("mybookings"))
async def cmd_mybookings(message: Message, db: Database, config: Config) -> None:
    assert message.from_user
    lang = user_lang(db, message.from_user)
    text, markup = _my_bookings_view(db, config, message.from_user.id, lang)
    await message.answer(text, reply_markup=markup)


# --- main menu buttons ----------------------------------------------------------

@on("callback_query", kb.MenuCb.filter(F.action == "home"))
async def cb_home(cb: CallbackQuery, state: FSMContext, db: Database, bot: Bot) -> None:
    await state.clear()
    lang = user_lang(db, cb.from_user)
    await show(cb, bot, t(lang, "welcome", name=escape(cb.from_user.first_name), business=catalog.BUSINESS_NAME),
               kb.main_menu(lang))


@on("callback_query", kb.MenuCb.filter(F.action == "about"))
async def cb_about(cb: CallbackQuery, db: Database, bot: Bot) -> None:
    lang = user_lang(db, cb.from_user)
    text = t(lang, "about", business=catalog.BUSINESS_NAME, address=catalog.ADDRESS,
             phone=catalog.PHONE, hours=_hours_text(lang))
    await show(cb, bot, text, kb.back_to_menu(lang))


@on("callback_query", kb.MenuCb.filter(F.action == "lang"))
async def cb_lang_menu(cb: CallbackQuery, db: Database, bot: Bot) -> None:
    await show(cb, bot, t(user_lang(db, cb.from_user), "lang_choose"), kb.languages())


@on("callback_query", kb.LangCb.filter(F.code.in_(set(LANGS))))
async def cb_lang_set(cb: CallbackQuery, callback_data: kb.LangCb, db: Database, bot: Bot) -> None:
    db.set_lang(cb.from_user.id, callback_data.code)
    lang = callback_data.code
    await show(cb, bot, t(lang, "lang_set") + "\n\n" +
               t(lang, "welcome", name=escape(cb.from_user.first_name), business=catalog.BUSINESS_NAME),
               kb.main_menu(lang))


# --- booking flow -------------------------------------------------------------

@on("callback_query", kb.MenuCb.filter(F.action == "book"))
async def cb_book(cb: CallbackQuery, state: FSMContext, db: Database, bot: Bot) -> None:
    await state.clear()
    lang = user_lang(db, cb.from_user)
    await show(cb, bot, t(lang, "choose_service"), kb.services(lang))


async def _show_days(cb: CallbackQuery, bot: Bot, db: Database, config: Config, service_id: str) -> None:
    lang = user_lang(db, cb.from_user)
    days = _days_with_slots(db, config, service_id)
    if not days:
        await show(cb, bot, t(lang, "no_days", phone=catalog.PHONE), kb.back_to_menu(lang))
        return
    service = catalog.SERVICES_BY_ID[service_id].name(lang)
    await show(cb, bot, t(lang, "choose_day", service=service), kb.days(lang, days))


@on("callback_query", kb.ServiceCb.filter(F.id.in_(set(catalog.SERVICES_BY_ID))))
async def cb_service(cb: CallbackQuery, callback_data: kb.ServiceCb, state: FSMContext,
                     db: Database, config: Config, bot: Bot) -> None:
    await state.set_data({"service_id": callback_data.id})
    await _show_days(cb, bot, db, config, callback_data.id)


@on("callback_query", kb.MenuCb.filter(F.action == "days"))
async def cb_back_to_days(cb: CallbackQuery, state: FSMContext, db: Database, config: Config, bot: Bot) -> None:
    data = await state.get_data()
    if "service_id" not in data:
        await _expired(cb, state, db, bot)
        return
    await _show_days(cb, bot, db, config, data["service_id"])


async def _show_slots(cb: CallbackQuery, bot: Bot, db: Database, config: Config,
                      service_id: str, day: date, prefix: str = "") -> None:
    lang = user_lang(db, cb.from_user)
    slots = _slots_for(db, config, service_id, day)
    service = catalog.SERVICES_BY_ID[service_id].name(lang)
    if not slots:
        await show(cb, bot, prefix + t(lang, "no_slots"), kb.slots(lang, []))
        return
    await show(cb, bot, prefix + t(lang, "choose_slot", service=service, day=fmt_day(lang, day)),
               kb.slots(lang, slots))


@on("callback_query", kb.DayCb.filter())
async def cb_day(cb: CallbackQuery, callback_data: kb.DayCb, state: FSMContext,
                 db: Database, config: Config, bot: Bot) -> None:
    data = await state.get_data()
    if "service_id" not in data:
        await _expired(cb, state, db, bot)
        return
    day = date.fromisoformat(callback_data.day)
    await state.update_data(day=day.isoformat())
    await _show_slots(cb, bot, db, config, data["service_id"], day)


@on("callback_query", kb.SlotCb.filter())
async def cb_slot(cb: CallbackQuery, callback_data: kb.SlotCb, state: FSMContext,
                  db: Database, config: Config, bot: Bot) -> None:
    data = await state.get_data()
    if "service_id" not in data or "day" not in data:
        await _expired(cb, state, db, bot)
        return
    lang = user_lang(db, cb.from_user)
    start = datetime.strptime(f"{data['day']} {callback_data.hm}", "%Y-%m-%d %H%M")
    await state.update_data(start=start.isoformat())
    await state.set_state(BookingForm.name)
    service = catalog.SERVICES_BY_ID[data["service_id"]].name(lang)
    await show(cb, bot, t(lang, "ask_name", service=service, day=fmt_day(lang, start), time=fmt_time(start)))


@on("message", StateFilter(BookingForm.name), F.text)
async def got_name(message: Message, state: FSMContext, db: Database) -> None:
    assert message.from_user and message.text
    lang = user_lang(db, message.from_user)
    name = normalize_name(message.text)
    if name is None:
        await message.answer(t(lang, "bad_name"))
        return
    await state.update_data(name=name)
    await state.set_state(BookingForm.phone)
    await message.answer(t(lang, "ask_phone"), reply_markup=kb.share_phone(lang))


@on("message", StateFilter(BookingForm.phone), F.contact | F.text)
async def got_phone(message: Message, state: FSMContext, db: Database) -> None:
    assert message.from_user
    lang = user_lang(db, message.from_user)
    raw = message.contact.phone_number if message.contact else (message.text or "")
    phone = normalize_phone(raw)
    if phone is None:
        await message.answer(t(lang, "bad_phone"))
        return
    await state.update_data(phone=phone)
    await state.set_state(BookingForm.confirm)
    data = await state.get_data()
    service = catalog.SERVICES_BY_ID[data["service_id"]]
    start = datetime.fromisoformat(data["start"])
    await message.answer("👌", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        t(lang, "summary", service=service.name(lang), day=fmt_day(lang, start), time=fmt_time(start),
          price=service.price, currency=catalog.CURRENCY, name=escape(data["name"]), phone=escape(phone)),
        reply_markup=kb.confirm(lang),
    )


@on("callback_query", StateFilter(BookingForm.confirm), kb.MenuCb.filter(F.action == "confirm"))
async def cb_confirm(cb: CallbackQuery, state: FSMContext, db: Database, config: Config, bot: Bot) -> None:
    lang = user_lang(db, cb.from_user)
    data = await state.get_data()
    service = catalog.SERVICES_BY_ID[data["service_id"]]
    start = datetime.fromisoformat(data["start"])
    now = config.now()
    if start < now + timedelta(minutes=catalog.MIN_LEAD_MIN):
        await state.set_state(None)
        await _show_slots(cb, bot, db, config, service.id, start.date(), prefix=t(lang, "slot_taken") + "\n\n")
        return
    try:
        booking = db.create_booking(
            user_id=cb.from_user.id,
            client_name=data["name"],
            phone=data["phone"],
            service_id=service.id,
            start_at=start,
            end_at=start + timedelta(minutes=service.duration_min),
            created_at=now,
            remind_at=reminder_time(start, now, timedelta(hours=config.reminder_hours)),
        )
    except SlotTaken:
        await state.set_state(None)  # keep service/day so the client just picks another time
        await _show_slots(cb, bot, db, config, service.id, start.date(), prefix=t(lang, "slot_taken") + "\n\n")
        return
    await state.clear()
    await show(cb, bot, t(lang, "booking_sent", id=booking.id), kb.back_to_menu(lang))
    await notify_admins_new(bot, db, config, booking)


@on("callback_query", kb.MenuCb.filter(F.action.in_({"abort", "confirm"})))
async def cb_abort(cb: CallbackQuery, state: FSMContext, db: Database, bot: Bot) -> None:
    # "confirm" lands here only if the FSM state is gone (e.g. bot restarted mid-flow)
    await state.clear()
    lang = user_lang(db, cb.from_user)
    await show(cb, bot, t(lang, "flow_cancelled"), kb.main_menu(lang))


async def _expired(cb: CallbackQuery, state: FSMContext, db: Database, bot: Bot) -> None:
    await state.clear()
    lang = user_lang(db, cb.from_user)
    await show(cb, bot, t(lang, "session_expired"), kb.main_menu(lang))


# --- my bookings --------------------------------------------------------------

def _my_bookings_view(db: Database, config: Config, user_id: int, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    bookings = db.user_upcoming(user_id, config.now())
    if not bookings:
        return t(lang, "my_empty"), kb.back_to_menu(lang)
    lines = [t(lang, "my_header")] + [t(lang, "my_item", **booking_fields(lang, b)) for b in bookings]
    return "\n".join(lines), kb.my_bookings(lang, bookings)


@on("callback_query", kb.MenuCb.filter(F.action == "my"))
async def cb_my(cb: CallbackQuery, db: Database, config: Config, bot: Bot) -> None:
    lang = user_lang(db, cb.from_user)
    text, markup = _my_bookings_view(db, config, cb.from_user.id, lang)
    await show(cb, bot, text, markup)


@on("callback_query", kb.BookingCb.filter(F.action == "client_cancel"))
async def cb_client_cancel(cb: CallbackQuery, callback_data: kb.BookingCb,
                           db: Database, config: Config, bot: Bot) -> None:
    lang = user_lang(db, cb.from_user)
    existing = db.get(callback_data.id)
    if existing is None or existing.user_id != cb.from_user.id:
        await cb.answer(t(lang, "cannot_change"), show_alert=True)
        return
    booking = db.apply_action(existing.id, "client_cancel")
    if booking is None:
        await cb.answer(t(lang, "cannot_change"), show_alert=True)
        return
    text, markup = _my_bookings_view(db, config, cb.from_user.id, lang)
    await show(cb, bot, t(lang, "client_cancel_done", id=booking.id) + "\n\n" + text, markup)
    await notify_admins_client_cancelled(bot, db, config, booking)
