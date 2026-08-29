from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv
from telegram import Bot

from .notifications import notification_chat_ids, register_pending_review

load_dotenv()


async def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")
    if len(sys.argv) < 3:
        raise RuntimeError("Usage: python -m src.notify <node_id> <message>")
    node_id = sys.argv[1]
    message = " ".join(sys.argv[2:]).strip()
    chat_ids = notification_chat_ids()
    if not chat_ids:
        raise RuntimeError("No notification chat is registered; send /register to the bot first")
    notification = f"Review needed for {node_id}\n\n{message}\n\nReply directly to this message with approved, rejected, or your review notes."
    async with Bot(token=token) as bot:
        for chat_id in chat_ids:
            sent_message = await bot.send_message(chat_id=chat_id, text=notification)
            register_pending_review(chat_id, sent_message.message_id, node_id)


if __name__ == "__main__":
    asyncio.run(main())
