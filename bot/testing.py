"""Offline harness: run the real dispatcher and handlers without Telegram.

`MockSession` replaces aiogram's HTTP session. Every Bot API call the handlers
make (sendMessage, editMessageText, sendDocument, ...) is recorded instead of
being sent, and a plausible response is returned. `FakeTelegram` builds the
JSON updates Telegram would push (commands, button presses, shared contacts)
and feeds them through `Dispatcher.feed_raw_update`, the same entry point
polling and webhooks use.
"""

from __future__ import annotations

import asyncio
import itertools
import time
from collections.abc import AsyncGenerator
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import TelegramMethod
from aiogram.types import Message, User

FAKE_TOKEN = "123456:TEST-TOKEN-offline-harness-only"
BOT_ID = 123456


class MockSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod[Any]] = []
        self.last_text: dict[int, str] = {}  # chat_id -> text of the last message the bot sent there
        self._ids = itertools.count(1000)

    async def close(self) -> None:
        pass

    async def stream_content(self, url: str, headers: dict[str, Any] | None = None, timeout: int = 30,
                             chunk_size: int = 65536, raise_for_status: bool = True) -> AsyncGenerator[bytes, None]:
        yield b""

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:
        self.requests.append(method)
        api = method.__api_method__
        if api == "getUpdates":
            await asyncio.sleep(0.05)  # long-polling stand-in: no new updates, but yield to the loop
            return []
        if api == "getMe":
            return User(id=BOT_ID, is_bot=True, first_name="Demo", username="demo_booking_bot")
        if api in ("sendMessage", "sendDocument"):
            self.last_text[method.chat_id] = getattr(method, "text", None) or ""  # type: ignore[attr-defined]
            return Message.model_validate(
                {
                    "message_id": next(self._ids),
                    "date": int(time.time()),
                    "chat": {"id": method.chat_id, "type": "private"},  # type: ignore[attr-defined]
                    "from": {"id": BOT_ID, "is_bot": True, "first_name": "Demo"},
                    "text": getattr(method, "text", None) or "",
                },
                context={"bot": bot},
            )
        return True  # editMessageText, answerCallbackQuery, setMyCommands, ...

    # helpers for assertions ----------------------------------------------
    def pop(self) -> list[TelegramMethod[Any]]:
        out, self.requests = self.requests, []
        return out

    @staticmethod
    def texts(requests: list[TelegramMethod[Any]], api: str | None = None) -> list[str]:
        return [
            getattr(r, "text", None) or getattr(r, "caption", None) or ""
            for r in requests
            if api is None or r.__api_method__ == api
        ]


class FakeTelegram:
    """Builds and feeds updates as if real users were tapping in the Telegram app."""

    def __init__(self, dp: Dispatcher, bot: Bot) -> None:
        self.dp, self.bot = dp, bot
        self._update_ids = itertools.count(1)
        self._msg_ids = itertools.count(1)

    @staticmethod
    def _user(user_id: int, name: str, lang: str) -> dict[str, Any]:
        return {"id": user_id, "is_bot": False, "first_name": name, "language_code": lang}

    def _message(self, user_id: int, name: str, lang: str, **content: Any) -> dict[str, Any]:
        return {
            "message_id": next(self._msg_ids),
            "date": int(time.time()),
            "chat": {"id": user_id, "type": "private"},
            "from": self._user(user_id, name, lang),
            **content,
        }

    async def send_text(self, user_id: int, text: str, name: str = "Client", lang: str = "en") -> None:
        content: dict[str, Any] = {"text": text}
        if text.startswith("/"):
            content["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
        await self.dp.feed_raw_update(
            self.bot, {"update_id": next(self._update_ids), "message": self._message(user_id, name, lang, **content)}
        )

    async def send_contact(self, user_id: int, phone: str, name: str = "Client", lang: str = "en") -> None:
        contact = {"phone_number": phone, "first_name": name, "user_id": user_id}
        await self.dp.feed_raw_update(
            self.bot,
            {"update_id": next(self._update_ids), "message": self._message(user_id, name, lang, contact=contact)},
        )

    async def press(self, user_id: int, data: str, name: str = "Client", lang: str = "en") -> None:
        bot_message = {
            "message_id": next(self._msg_ids),
            "date": int(time.time()),
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": BOT_ID, "is_bot": True, "first_name": "Demo"},
            "text": getattr(self.bot.session, "last_text", {}).get(user_id, "(previous bot message)"),
        }
        await self.dp.feed_raw_update(
            self.bot,
            {
                "update_id": next(self._update_ids),
                "callback_query": {
                    "id": str(next(self._update_ids)),
                    "from": self._user(user_id, name, lang),
                    "chat_instance": "test",
                    "data": data,
                    "message": bot_message,
                },
            },
        )
