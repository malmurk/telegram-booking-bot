"""Business configuration: the one file you edit to adapt the bot to a new client.

Everything a salon owner usually asks to change lives here: the business name,
address, services (names, durations, prices), opening hours and booking rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class Service:
    id: str
    names: dict[str, str]  # language code -> display name
    duration_min: int
    price: int  # in CURRENCY units

    def name(self, lang: str) -> str:
        return self.names.get(lang) or self.names["en"]


BUSINESS_NAME = "Demo Barbershop"
ADDRESS = "Str. Exemplu 1, Chișinău"
PHONE = "+373 00 000 000"
CURRENCY = "MDL"

SERVICES: tuple[Service, ...] = (
    Service("haircut", {"en": "Haircut", "ru": "Стрижка", "ro": "Tuns"}, 45, 250),
    Service("beard", {"en": "Beard trim", "ru": "Оформление бороды", "ro": "Aranjare barbă"}, 30, 150),
    Service(
        "combo",
        {"en": "Haircut + beard", "ru": "Стрижка + борода", "ro": "Tuns + barbă"},
        75,
        350,
    ),
    Service("kids", {"en": "Kids haircut", "ru": "Детская стрижка", "ro": "Tuns copii"}, 30, 180),
)
SERVICES_BY_ID = {s.id: s for s in SERVICES}

# weekday() -> (open, close); a missing weekday means closed. Monday == 0.
WORKING_HOURS: dict[int, tuple[time, time]] = {
    0: (time(10), time(19)),
    1: (time(10), time(19)),
    2: (time(10), time(19)),
    3: (time(10), time(19)),
    4: (time(10), time(19)),
    5: (time(10), time(16)),
}

SLOT_STEP_MIN = 30  # slot grid: 10:00, 10:30, 11:00 ...
BOOKING_HORIZON_DAYS = 7  # how many days ahead clients can book
MIN_LEAD_MIN = 60  # no bookings starting sooner than this from now
