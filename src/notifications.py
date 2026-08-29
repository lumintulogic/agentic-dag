from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "dag" / "telegram_notification_chat_ids.json"


def registry_path() -> Path:
    return Path(os.getenv("TELEGRAM_NOTIFICATION_REGISTRY", str(DEFAULT_REGISTRY_PATH)))


def notification_chat_ids() -> list[int]:
    path = registry_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [int(chat_id) for chat_id in data.get("chat_ids", [])]


def register_chat_id(chat_id: int) -> bool:
    chat_ids = notification_chat_ids()
    if chat_id in chat_ids:
        return False
    chat_ids.append(chat_id)
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps({"chat_ids": chat_ids}, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)
    return True
