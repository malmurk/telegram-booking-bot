from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import catalog
from .booking import Booking
from .i18n import LANGS, fmt_day, fmt_time, t


class MenuCb(CallbackData, prefix="m"):
    action: str  # home | book | days | my | lang | about | confirm | abort


class ServiceCb(CallbackData, prefix="s"):
    id: str


class DayCb(CallbackData, prefix="d"):
    day: str  # YYYY-MM-DD


class SlotCb(CallbackData, prefix="t"):
    hm: str  # HHMM (":" is the callback separator, so no colon)


class LangCb(CallbackData, prefix="l"):
    code: str


class BookingCb(CallbackData, prefix="b"):
    action: str  # client_cancel | admin_confirm | admin_cancel
    id: int


def main_menu(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_book"), callback_data=MenuCb(action="book"))
    kb.button(text=t(lang, "btn_my"), callback_data=MenuCb(action="my"))
    kb.button(text=t(lang, "btn_lang"), callback_data=MenuCb(action="lang"))
    kb.button(text=t(lang, "btn_about"), callback_data=MenuCb(action="about"))
    kb.adjust(1, 1, 2)
    return kb.as_markup()


def back_to_menu(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_menu"), callback_data=MenuCb(action="home"))
    return kb.as_markup()


def services(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in catalog.SERVICES:
        kb.button(
            text=t(lang, "service_btn", name=s.name(lang), duration=s.duration_min,
                   price=s.price, currency=catalog.CURRENCY),
            callback_data=ServiceCb(id=s.id),
        )
    kb.button(text=t(lang, "btn_menu"), callback_data=MenuCb(action="home"))
    kb.adjust(1)
    return kb.as_markup()


def days(lang: str, options: Sequence[date]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for d in options:
        kb.button(text=fmt_day(lang, d), callback_data=DayCb(day=d.isoformat()))
    kb.adjust(3)
    nav = InlineKeyboardBuilder()
    nav.button(text=t(lang, "btn_back"), callback_data=MenuCb(action="book"))
    kb.attach(nav)
    return kb.as_markup()


def slots(lang: str, options: Sequence[datetime]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in options:
        kb.button(text=fmt_time(s), callback_data=SlotCb(hm=s.strftime("%H%M")))
    kb.adjust(4)
    nav = InlineKeyboardBuilder()
    nav.button(text=t(lang, "btn_back"), callback_data=MenuCb(action="days"))
    kb.attach(nav)
    return kb.as_markup()


def share_phone(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "btn_share_phone"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def confirm(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "btn_confirm"), callback_data=MenuCb(action="confirm"))
    kb.button(text=t(lang, "btn_cancel"), callback_data=MenuCb(action="abort"))
    return kb.as_markup()


def languages() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, label in LANGS.items():
        kb.button(text=label, callback_data=LangCb(code=code))
    return kb.as_markup()


def my_bookings(lang: str, bookings: Sequence[Booking]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for b in bookings:
        kb.button(text=t(lang, "btn_cancel_booking", id=b.id),
                  callback_data=BookingCb(action="client_cancel", id=b.id))
    kb.button(text=t(lang, "btn_menu"), callback_data=MenuCb(action="home"))
    kb.adjust(1)
    return kb.as_markup()


def admin_decision(lang: str, booking_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "admin_btn_confirm"), callback_data=BookingCb(action="admin_confirm", id=booking_id))
    kb.button(text=t(lang, "admin_btn_cancel"), callback_data=BookingCb(action="admin_cancel", id=booking_id))
    return kb.as_markup()
