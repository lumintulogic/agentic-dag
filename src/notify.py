from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram import Bot

from .notifications import notification_chat_ids, register_pending_review

load_dotenv()


def report(event: str, node_id: str, **details: object) -> None:
    """Emit an immediately flushed, non-secret delivery diagnostic."""
    timestamp = datetime.now(timezone.utc).isoformat()
    suffix = " ".join(f"{key}={value}" for key, value in details.items())
    print(f"{timestamp} telegram_review_notification event={event} node_id={node_id}{(' ' + suffix) if suffix else ''}", flush=True)


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
    report("send_started", node_id, recipients=len(chat_ids))
    failures = 0
    async with Bot(token=token) as bot:
        for chat_id in chat_ids:
            try:
                sent_message = await bot.send_message(chat_id=chat_id, text=notification)
                report("telegram_accepted", node_id, message_id=sent_message.message_id)
            except Exception as error:
                failures += 1
                report("send_failed", node_id, error_type=type(error).__name__)
                continue
            try:
                register_pending_review(chat_id, sent_message.message_id, node_id)
                report("reply_mapping_registered", node_id, message_id=sent_message.message_id)
            except Exception as error:
                failures += 1
                report("reply_mapping_failed", node_id, message_id=sent_message.message_id, error_type=type(error).__name__)
    if failures:
        raise RuntimeError(f"Telegram review notification failed for {failures} recipient operation(s); see timestamped diagnostics above")
    report("send_completed", node_id, recipients=len(chat_ids))


if __name__ == "__main__":
    asyncio.run(main())
