from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv
from telegram import Bot

from .notifications import notification_chat_ids

load_dotenv()


async def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")
    chat_ids = notification_chat_ids()
    if not chat_ids:
        raise RuntimeError("No notification chat is registered; send /register to the bot first")
    message = " ".join(sys.argv[1:]).strip()
    if not message:
        raise RuntimeError("Usage: python -m src.notify <message>")
    async with Bot(token=token) as bot:
        for chat_id in chat_ids:
            await bot.send_message(chat_id=chat_id, text=message)


if __name__ == "__main__":
    asyncio.run(main())
