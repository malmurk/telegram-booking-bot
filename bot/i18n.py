"""Bot texts in Russian, Romanian and English. Add a language by adding a dict."""

from __future__ import annotations

from datetime import datetime

LANGS = {"ru": "Русский", "ro": "Română", "en": "English"}
DEFAULT_LANG = "en"

WEEKDAYS = {
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    "ru": ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"),
    "ro": ("Lun", "Mar", "Mie", "Joi", "Vin", "Sâm", "Dum"),
}

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "welcome": "Hi, {name}! This is <b>{business}</b>.\nBook a visit in a few taps:",
        "btn_book": "📅 Book a visit",
        "btn_my": "🗂 My bookings",
        "btn_lang": "🌐 Language",
        "btn_about": "ℹ️ Contacts",
        "btn_back": "« Back",
        "btn_menu": "« Menu",
        "about": "<b>{business}</b>\n📍 {address}\n📞 {phone}\n\n{hours}",
        "hours_line": "{day}: {open}–{close}",
        "closed": "closed",
        "choose_service": "Choose a service:",
        "service_btn": "{name} · {duration} min · {price} {currency}",
        "choose_day": "<b>{service}</b>\nChoose a day:",
        "no_days": "Sorry, there are no free slots in the next days. Please call us: {phone}",
        "choose_slot": "<b>{service}</b>, {day}\nChoose a time:",
        "no_slots": "No free time left on this day. Please pick another one.",
        "ask_name": "<b>{service}</b>, {day} {time}\n\nWhat is your name?",
        "bad_name": "Please send your name as text (2–64 characters).",
        "ask_phone": "Your phone number? Tap the button below or type it.",
        "btn_share_phone": "📱 Share my phone",
        "bad_phone": "That doesn't look like a phone number. Example: +37369123456",
        "summary": (
            "Please check your booking:\n\n"
            "Service: <b>{service}</b>\nDate: <b>{day}</b>\nTime: <b>{time}</b>\n"
            "Price: {price} {currency}\nName: {name}\nPhone: {phone}"
        ),
        "btn_confirm": "✅ Confirm",
        "btn_cancel": "✖️ Cancel",
        "booking_sent": "Thank you! Request #{id} is sent. We'll confirm it shortly.",
        "slot_taken": "Sorry, someone has just taken this time. Please choose another one.",
        "flow_cancelled": "Booking cancelled.",
        "session_expired": "This step has expired, let's start again.",
        "my_empty": "You have no upcoming bookings.",
        "my_header": "Your upcoming bookings:",
        "my_item": "#{id} · {day} {time} · {service} · {status}",
        "btn_cancel_booking": "✖️ Cancel #{id}",
        "client_cancel_done": "Booking #{id} is cancelled.",
        "cannot_change": "This booking can no longer be changed.",
        "lang_choose": "Choose a language:",
        "lang_set": "Language set: English.",
        "status_pending": "awaiting confirmation",
        "status_confirmed": "confirmed",
        "status_cancelled": "cancelled",
        "client_confirmed": "✅ Your booking #{id} is confirmed: {service}, {day} at {time}. See you!",
        "client_admin_cancelled": "❌ Unfortunately booking #{id} ({day} {time}) was cancelled. Call us: {phone}",
        "reminder": "⏰ Reminder: {service} on {day} at {time}.\n📍 {address}",
        "admin_new": "🆕 New booking #{id}\n{service}\n{day} {time}\n{name}, {phone}",
        "admin_btn_confirm": "✅ Confirm",
        "admin_btn_cancel": "❌ Cancel",
        "admin_marked": "\n\n→ {status}",
        "admin_client_cancelled": "↩️ Client cancelled booking #{id}: {day} {time}, {name}, {phone}",
        "today_header": "<b>Schedule for {day}</b>",
        "today_item": "{time}–{end} · {service} · {name}, {phone} · {status}",
        "today_empty": "No bookings for {day}.",
        "bad_date": "Use the format /today 2026-10-23",
        "export_empty": "No bookings to export yet.",
        "export_caption": "All bookings ({count})",
        "admin_help": (
            "Admin commands:\n/today [YYYY-MM-DD] – day schedule\n/export – all bookings as CSV\n"
            "New bookings arrive here with Confirm/Cancel buttons."
        ),
        "myid": "Your Telegram ID: <code>{id}</code>",
    },
    "ru": {
        "welcome": "Здравствуйте, {name}! Это <b>{business}</b>.\nЗапишитесь в пару нажатий:",
        "btn_book": "📅 Записаться",
        "btn_my": "🗂 Мои записи",
        "btn_lang": "🌐 Язык",
        "btn_about": "ℹ️ Контакты",
        "btn_back": "« Назад",
        "btn_menu": "« Меню",
        "about": "<b>{business}</b>\n📍 {address}\n📞 {phone}\n\n{hours}",
        "hours_line": "{day}: {open}–{close}",
        "closed": "выходной",
        "choose_service": "Выберите услугу:",
        "service_btn": "{name} · {duration} мин · {price} {currency}",
        "choose_day": "<b>{service}</b>\nВыберите день:",
        "no_days": "К сожалению, в ближайшие дни нет свободного времени. Позвоните нам: {phone}",
        "choose_slot": "<b>{service}</b>, {day}\nВыберите время:",
        "no_slots": "На этот день свободного времени не осталось. Выберите другой день.",
        "ask_name": "<b>{service}</b>, {day} {time}\n\nКак вас зовут?",
        "bad_name": "Пожалуйста, отправьте имя текстом (2–64 символа).",
        "ask_phone": "Ваш номер телефона? Нажмите кнопку ниже или введите вручную.",
        "btn_share_phone": "📱 Отправить мой номер",
        "bad_phone": "Это не похоже на номер телефона. Пример: +37369123456",
        "summary": (
            "Проверьте запись:\n\n"
            "Услуга: <b>{service}</b>\nДата: <b>{day}</b>\nВремя: <b>{time}</b>\n"
            "Цена: {price} {currency}\nИмя: {name}\nТелефон: {phone}"
        ),
        "btn_confirm": "✅ Подтвердить",
        "btn_cancel": "✖️ Отмена",
        "booking_sent": "Спасибо! Заявка №{id} отправлена. Мы скоро её подтвердим.",
        "slot_taken": "Извините, это время только что заняли. Выберите другое.",
        "flow_cancelled": "Запись отменена.",
        "session_expired": "Этот шаг устарел, начнём заново.",
        "my_empty": "У вас нет предстоящих записей.",
        "my_header": "Ваши предстоящие записи:",
        "my_item": "№{id} · {day} {time} · {service} · {status}",
        "btn_cancel_booking": "✖️ Отменить №{id}",
        "client_cancel_done": "Запись №{id} отменена.",
        "cannot_change": "Эту запись уже нельзя изменить.",
        "lang_choose": "Выберите язык:",
        "lang_set": "Язык: русский.",
        "status_pending": "ожидает подтверждения",
        "status_confirmed": "подтверждена",
        "status_cancelled": "отменена",
        "client_confirmed": "✅ Запись №{id} подтверждена: {service}, {day} в {time}. Ждём вас!",
        "client_admin_cancelled": "❌ К сожалению, запись №{id} ({day} {time}) отменена. Позвоните нам: {phone}",
        "reminder": "⏰ Напоминание: {service}, {day} в {time}.\n📍 {address}",
        "admin_new": "🆕 Новая запись №{id}\n{service}\n{day} {time}\n{name}, {phone}",
        "admin_btn_confirm": "✅ Подтвердить",
        "admin_btn_cancel": "❌ Отменить",
        "admin_marked": "\n\n→ {status}",
        "admin_client_cancelled": "↩️ Клиент отменил запись №{id}: {day} {time}, {name}, {phone}",
        "today_header": "<b>Расписание на {day}</b>",
        "today_item": "{time}–{end} · {service} · {name}, {phone} · {status}",
        "today_empty": "На {day} записей нет.",
        "bad_date": "Формат: /today 2026-10-23",
        "export_empty": "Пока нечего выгружать.",
        "export_caption": "Все записи ({count})",
        "admin_help": (
            "Команды администратора:\n/today [ГГГГ-ММ-ДД] – расписание на день\n/export – все записи в CSV\n"
            "Новые записи приходят сюда с кнопками Подтвердить/Отменить."
        ),
        "myid": "Ваш Telegram ID: <code>{id}</code>",
    },
    "ro": {
        "welcome": "Bună, {name}! Aici este <b>{business}</b>.\nProgramează-te în câteva atingeri:",
        "btn_book": "📅 Programare",
        "btn_my": "🗂 Programările mele",
        "btn_lang": "🌐 Limba",
        "btn_about": "ℹ️ Contacte",
        "btn_back": "« Înapoi",
        "btn_menu": "« Meniu",
        "about": "<b>{business}</b>\n📍 {address}\n📞 {phone}\n\n{hours}",
        "hours_line": "{day}: {open}–{close}",
        "closed": "închis",
        "choose_service": "Alege serviciul:",
        "service_btn": "{name} · {duration} min · {price} {currency}",
        "choose_day": "<b>{service}</b>\nAlege ziua:",
        "no_days": "Ne pare rău, nu sunt ore libere în zilele următoare. Sună-ne: {phone}",
        "choose_slot": "<b>{service}</b>, {day}\nAlege ora:",
        "no_slots": "Nu mai sunt ore libere în această zi. Alege altă zi.",
        "ask_name": "<b>{service}</b>, {day} {time}\n\nCum te numești?",
        "bad_name": "Te rugăm să trimiți numele ca text (2–64 de caractere).",
        "ask_phone": "Numărul tău de telefon? Apasă butonul de mai jos sau scrie-l.",
        "btn_share_phone": "📱 Trimite numărul meu",
        "bad_phone": "Nu pare a fi un număr de telefon. Exemplu: +37369123456",
        "summary": (
            "Verifică programarea:\n\n"
            "Serviciu: <b>{service}</b>\nData: <b>{day}</b>\nOra: <b>{time}</b>\n"
            "Preț: {price} {currency}\nNume: {name}\nTelefon: {phone}"
        ),
        "btn_confirm": "✅ Confirmă",
        "btn_cancel": "✖️ Anulează",
        "booking_sent": "Mulțumim! Cererea #{id} a fost trimisă. O confirmăm în curând.",
        "slot_taken": "Ne pare rău, cineva tocmai a ocupat această oră. Alege alta.",
        "flow_cancelled": "Programarea a fost anulată.",
        "session_expired": "Acest pas a expirat, să începem din nou.",
        "my_empty": "Nu ai programări viitoare.",
        "my_header": "Programările tale viitoare:",
        "my_item": "#{id} · {day} {time} · {service} · {status}",
        "btn_cancel_booking": "✖️ Anulează #{id}",
        "client_cancel_done": "Programarea #{id} a fost anulată.",
        "cannot_change": "Această programare nu mai poate fi modificată.",
        "lang_choose": "Alege limba:",
        "lang_set": "Limba: română.",
        "status_pending": "în așteptarea confirmării",
        "status_confirmed": "confirmată",
        "status_cancelled": "anulată",
        "client_confirmed": "✅ Programarea #{id} este confirmată: {service}, {day} la {time}. Te așteptăm!",
        "client_admin_cancelled": "❌ Din păcate, programarea #{id} ({day} {time}) a fost anulată. Sună-ne: {phone}",
        "reminder": "⏰ Amintire: {service}, {day} la {time}.\n📍 {address}",
        "admin_new": "🆕 Programare nouă #{id}\n{service}\n{day} {time}\n{name}, {phone}",
        "admin_btn_confirm": "✅ Confirmă",
        "admin_btn_cancel": "❌ Anulează",
        "admin_marked": "\n\n→ {status}",
        "admin_client_cancelled": "↩️ Clientul a anulat programarea #{id}: {day} {time}, {name}, {phone}",
        "today_header": "<b>Programul pentru {day}</b>",
        "today_item": "{time}–{end} · {service} · {name}, {phone} · {status}",
        "today_empty": "Nu sunt programări pentru {day}.",
        "bad_date": "Format: /today 2026-10-23",
        "export_empty": "Încă nu sunt programări de exportat.",
        "export_caption": "Toate programările ({count})",
        "admin_help": (
            "Comenzi de administrator:\n/today [AAAA-LL-ZZ] – programul zilei\n/export – toate programările în CSV\n"
            "Programările noi vin aici cu butoanele Confirmă/Anulează."
        ),
        "myid": "ID-ul tău Telegram: <code>{id}</code>",
    },
}


def t(lang: str, key: str, **kwargs: object) -> str:
    table = TEXTS.get(lang, TEXTS[DEFAULT_LANG])
    return table[key].format(**kwargs) if kwargs else table[key]


def pick_lang(telegram_code: str | None) -> str:
    """Initial language from the user's Telegram app language."""
    code = (telegram_code or "").split("-")[0].lower()
    return code if code in LANGS else DEFAULT_LANG


def fmt_day(lang: str, dt: datetime | object) -> str:
    """'Thu 23.10' style label in the user's language."""
    return f"{WEEKDAYS.get(lang, WEEKDAYS[DEFAULT_LANG])[dt.weekday()]} {dt.strftime('%d.%m')}"  # type: ignore[attr-defined]


def fmt_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")
