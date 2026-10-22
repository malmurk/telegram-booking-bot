# Telegram Booking Bot

An appointment booking bot for barbershops, beauty salons, clinics and other small businesses
that work by appointment. Clients book a visit in Telegram in under a minute. The owner gets
each request on their phone and confirms it with one tap.

The demo is set up for a fictional **Demo Barbershop** in Chișinău. Every business detail
(services, prices, hours, address) lives in one file, so adapting it to a real business takes
minutes, not days.

## What it does

**For your clients**
- A `/start` menu with buttons. Clients never have to type commands.
- Booking flow: **service → day → free time → name → phone → confirm**.
  - Only times that are actually free are shown. A 45-minute haircut is never offered at 10:30 if someone is booked at 11:00.
  - The phone number can be shared with one tap ("Share my phone") or typed.
- **My bookings**: see upcoming visits and cancel one with a tap.
- An **automatic reminder** 24 hours before the visit, or 1 hour before for last-minute bookings.
- **Three languages: Russian, Romanian, English.** The bot picks the language of the client's Telegram app, and the client can switch at any time.

**For the owner / staff**
- Every new booking arrives as a Telegram message with **Confirm** and **Cancel** buttons. The client is notified automatically either way.
- You are told when a client cancels.
- `/today`: today's schedule. `/today 2026-10-27`: any other day.
- `/export`: all bookings as a CSV file that opens in Excel or Google Sheets, with correct Cyrillic and Romanian characters.
- Several staff members can be admins.

**Under the hood**
- Two clients can never take the same slot. The check and the insert run in one database transaction, so if two people confirm at the same moment, the second one is politely offered the remaining times.
- Reminders are stored in the database, so a restart never loses one.
- SQLite storage. There is no database server to run or pay for.

## Screenshots

> Placeholders. These get filled in once the test bot is live (see the next section).

| Main menu | Choosing a time | Admin notification |
|---|---|---|
| `docs/screenshots/menu.png` | `docs/screenshots/slots.png` | `docs/screenshots/admin.png` |

Until then, `python -m bot.demo` prints a full conversation transcript without needing a token (see *Try it without a token*).

## Create your test bot (BotFather, 2 minutes)

1. In Telegram, open **@BotFather** (the one with the blue verified checkmark) and press **Start**.
2. Send `/newbot`.
3. Send the display name, e.g. `Demo Barbershop Booking`.
4. Send a username. It must end in `bot`, e.g. `demo_barbershop_booking_bot`. If it's taken, try another.
5. BotFather replies with a token like `123456789:AA...`. **Keep it secret**: anyone with it controls the bot.
6. Optional polish in BotFather:
   - `/setdescription` sets the text shown before the user presses Start.
   - `/setuserpic` sets the bot avatar.
   - The command menu is set automatically by the bot on startup.
7. Put the token into `.env` as `BOT_TOKEN` (see Quickstart).
8. Start the bot, open it in Telegram and send `/myid`. Put that number into `ADMIN_IDS` in `.env` and restart. From now on, bookings come to you.

If a token ever leaks, send `/revoke` to BotFather to get a new one.

## Quickstart

Requires Python 3.12+.

**Windows (PowerShell)**
```powershell
git clone <repo-url> telegram-booking-bot
cd telegram-booking-bot
py -3.12 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env          # paste BOT_TOKEN and ADMIN_IDS
.\.venv\Scripts\python -m bot
```

**Linux / macOS**
```bash
git clone <repo-url> telegram-booking-bot && cd telegram-booking-bot
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env
.venv/bin/python -m bot
```

You should see `authorized as @your_bot_username`. Open the bot in Telegram and press **Start**.

| Setting (`.env`) | Meaning | Default |
|---|---|---|
| `BOT_TOKEN` | Token from BotFather | required |
| `ADMIN_IDS` | Comma-separated Telegram IDs of staff (`/myid` shows yours) | none |
| `TIMEZONE` | Business time zone | `Europe/Chisinau` |
| `REMINDER_HOURS` | How long before the visit to send the reminder | `24` |
| `DB_PATH` | SQLite file | `data/bookings.db` |

Every admin must press **Start** in the bot once. Telegram doesn't let bots message people who never started them.

## Try it without a token

```bash
python -m bot.demo
```

This runs a complete booking (client books, admin confirms, reminder fires) through the real bot
code with Telegram replaced by a mock, and prints what each person would see. No token and no
internet are needed. The same mock (`bot/testing.py`) powers the automated tests.

## Adapting it to your business

| You want to change… | Where |
|---|---|
| Business name, address, phone, currency | `bot/catalog.py` (top) |
| Services, durations, prices | `bot/catalog.py` → `SERVICES` |
| Opening hours, days off | `bot/catalog.py` → `WORKING_HOURS` |
| Slot step (30 min), how far ahead clients can book (7 days), minimum notice (60 min) | `bot/catalog.py` |
| Any text the bot says, in any language | `bot/i18n.py` |
| Add a language (e.g. Ukrainian) | add a block to `TEXTS` and `WEEKDAYS` in `bot/i18n.py` |
| Reminder timing | `REMINDER_HOURS` in `.env` |

Typical paid extensions:
- Several masters, each with their own schedule; the client chooses a master.
- Google Calendar or Google Sheets sync.
- Deposits or prepayment via Telegram Payments.
- Holidays and one-off closed days.
- Reviews ("How was your visit?") a few hours after the appointment.
- A web admin panel.

## Deploy

The bot uses long polling, so it needs no domain, HTTPS or open ports. Any small VPS (1 vCPU / 512 MB, a few euros a month) is enough.

**Docker (recommended)**
```bash
cp .env.example .env    # fill in BOT_TOKEN and ADMIN_IDS
docker compose up -d --build
docker compose logs -f bot
```
Bookings are kept in the `bot-data` volume and survive updates. To update: `git pull && docker compose up -d --build`.

**Without Docker:** run `python -m bot` under systemd (`Restart=always`) with the working directory set to the repo.

**Backups:** the whole state is one file, `data/bookings.db`. Copy it to back up, e.g. with a daily cron job.

## For developers

```bash
pip install -r requirements-dev.txt
python -m pytest     # booking logic, slot conflicts, reminders, full conversations; no network
python -m ruff check bot tests
```

```
bot/
  catalog.py     business config: services, hours, rules
  booking.py     pure logic: free slots, conflicts, status changes, reminders, CSV
  db.py          SQLite storage, atomic booking insert
  i18n.py        RU / RO / EN texts
  keyboards.py   inline keyboards and callback data
  handlers/      client flow (user.py) and admin commands/buttons (admin.py)
  notify.py      admin alerts, client updates, reminder job
  main.py        startup, polling, background reminder loop
  testing.py     mock Telegram session used by tests and the demo
tests/           unit tests and end-to-end conversation tests
```

**Why aiogram 3.** [aiogram](https://pypi.org/project/aiogram/) 3.31.0 (pinned) is a widely used asyncio Telegram framework, especially among Russian-speaking developers, so another developer can pick the code up easily. It is fully typed, keeps up with the Bot API, and includes what a booking flow needs: FSM for multi-step forms, typed callback data and keyboard builders. Reminders use a small database-backed loop instead of a scheduler library. That is one dependency fewer, and reminders survive restarts by design.

**Known limits of this demo.** One shared calendar (no per-master schedules). A client who is halfway through booking when the bot restarts starts the booking again; confirmed bookings are never lost.

## License

MIT. See [LICENSE](LICENSE).
