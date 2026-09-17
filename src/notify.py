from __future__ import annotations

import argparse
import asyncio
import json
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


async def send_notification(node_id: str, message: str) -> None:
    """Send the review notification to all registered chats."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in .env")
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


def wait_for_review(node_id: str, timeout: float = 300, port: int | None = None) -> dict | None:
    """Call the web server's wait endpoint and return the review result."""
    import urllib.request
    import urllib.error

    if port is None:
        port = int(os.getenv("WEB_PORT", "8080"))
    url = f"http://localhost:{port}/api/telegram/reviews/{node_id}/wait?timeout={timeout}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 408:
            return None
        raise


async def main() -> None:
    parser = argparse.ArgumentParser(description="Send a Telegram review notification")
    parser.add_argument("node_id", help="DAG node ID to request review for")
    parser.add_argument("message", nargs="+", help="Review message text")
    parser.add_argument("--wait", action="store_true", help="Block until the human replies (requires the web server to be running)")
    parser.add_argument("--timeout", type=float, default=300, help="Seconds to wait for a reply (default: 300)")
    args = parser.parse_args()

    message = " ".join(args.message).strip()
    await send_notification(args.node_id, message)

    if args.wait:
        report("waiting_for_reply", args.node_id, timeout=args.timeout)
        result = wait_for_review(args.node_id, timeout=args.timeout)
        if result is None:
            report("wait_timeout", args.node_id)
            sys.exit(1)
        report("review_received", args.node_id, status=result.get("status"))
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
