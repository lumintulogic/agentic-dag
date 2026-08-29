from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "dag" / "telegram_notification_chat_ids.json"


def registry_path() -> Path:
    return Path(os.getenv("TELEGRAM_NOTIFICATION_REGISTRY", str(DEFAULT_REGISTRY_PATH)))


def _load_registry() -> dict:
    path = registry_path()
    if not path.exists():
        return {"chat_ids": [], "pending_reviews": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"chat_ids": [], "pending_reviews": {}}
    data.setdefault("chat_ids", [])
    data.setdefault("pending_reviews", {})
    return data


def _save_registry(data: dict) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def notification_chat_ids() -> list[int]:
    return [int(chat_id) for chat_id in _load_registry()["chat_ids"]]


def register_chat_id(chat_id: int) -> bool:
    data = _load_registry()
    if chat_id in data["chat_ids"]:
        return False
    data["chat_ids"].append(chat_id)
    _save_registry(data)
    return True


def register_pending_review(chat_id: int, message_id: int, node_id: str) -> None:
    data = _load_registry()
    data["pending_reviews"][f"{chat_id}:{message_id}"] = {
        "node_id": node_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_registry(data)


def consume_pending_review(chat_id: int, message_id: int) -> dict | None:
    data = _load_registry()
    review = data["pending_reviews"].pop(f"{chat_id}:{message_id}", None)
    if review is not None:
        _save_registry(data)
    return review
