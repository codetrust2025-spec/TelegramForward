"""Persist private DM conversations per account slot — never group/channel data."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from threading import Lock

from core.config import STATE_DIR

_MAX_MESSAGES_PER_CHAT = 300
_file_locks: dict[str, Lock] = {}

# Outbound: sending (UI-only) → sent → delivered → read | failed
# Inbound: received → read (when agent marks conversation read)
_OUTBOUND_RANK = {
    "failed": 0,
    "sending": 1,
    "sent": 2,
    "delivered": 3,
    "read": 4,
}


def _path(slot: str) -> str:
    return os.path.join(STATE_DIR, slot, "dm_inbox.json")


def _lock(slot: str) -> Lock:
    if slot not in _file_locks:
        _file_locks[slot] = Lock()
    return _file_locks[slot]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty() -> dict:
    return {"conversations": {}, "updated_at": _now_iso()}


def _can_advance_outbound(current: str, target: str) -> bool:
    if target == "failed":
        return current in ("sending", "sent")
    return _OUTBOUND_RANK.get(target, 0) > _OUTBOUND_RANK.get(current, 0)


def _normalize_outbound_record(m: dict) -> dict:
    """Upgrade legacy stored 'sent' to 'delivered' for display consistency."""
    if m.get("direction") != "out":
        return m
    out = dict(m)
    st = out.get("status") or "sent"
    if st == "sent":
        out["status"] = "delivered"
    return out


def load_inbox(slot: str) -> dict:
    path = _path(slot)
    with _lock(slot):
        if not os.path.exists(path):
            return _empty()
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return _empty()
            data.setdefault("conversations", {})
            return data
        except (json.JSONDecodeError, OSError):
            return _empty()


def save_inbox(slot: str, data: dict) -> None:
    path = _path(slot)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["updated_at"] = _now_iso()
    with _lock(slot):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def _trim_messages(messages: list) -> list:
    if len(messages) <= _MAX_MESSAGES_PER_CHAT:
        return messages
    return messages[-_MAX_MESSAGES_PER_CHAT:]


def _find_message(conv: dict, message_id: int) -> dict | None:
    mid = int(message_id)
    for m in conv.get("messages") or []:
        if int(m.get("id") or 0) == mid:
            return m
    return None


def append_message(
    slot: str,
    *,
    user_id: int,
    username: str,
    name: str,
    text: str,
    direction: str,
    telegram_id: int | None = None,
    status: str = "received",
    increment_unread: bool = False,
    account_id: str | None = None,
    timestamp: str | None = None,
) -> tuple[dict, dict, bool]:
    """Returns (conversation_summary, message_record, created). created=False if duplicate telegram_id."""
    data = load_inbox(slot)
    key = str(user_id)
    conv = data["conversations"].get(key) or {
        "user_id": user_id,
        "username": username,
        "name": name,
        "unread_count": 0,
        "last_message": "",
        "last_message_at": None,
        "messages": [],
    }
    conv["username"] = username or conv.get("username") or ""
    conv["name"] = name or conv.get("name") or str(user_id)

    msg_id = telegram_id or int(datetime.now(timezone.utc).timestamp() * 1000)
    record = {
        "id": msg_id,
        "chat_id": int(user_id),
        "account_id": account_id or slot,
        "direction": direction,
        "text": text or "",
        "timestamp": timestamp or _now_iso(),
        "status": status,
        "read_at": None,
    }

    msgs = conv.get("messages") or []
    if telegram_id and any(m.get("id") == telegram_id for m in msgs):
        existing = next(m for m in msgs if m.get("id") == telegram_id)
        return conv, _normalize_outbound_record(existing), False

    msgs.append(record)
    conv["messages"] = _trim_messages(msgs)
    conv["last_message"] = (text or "")[:500]
    prev_at = conv.get("last_message_at") or ""
    if not prev_at or (record["timestamp"] or "") >= prev_at:
        conv["last_message_at"] = record["timestamp"]

    if direction == "in" and increment_unread:
        conv["unread_count"] = int(conv.get("unread_count") or 0) + 1
    elif direction == "out":
        # Our reply — never show as unread in the sidebar
        conv["unread_count"] = 0

    data["conversations"][key] = conv
    save_inbox(slot, data)
    return conv, record, True


def update_outbound_status(
    slot: str,
    user_id: int,
    message_id: int,
    status: str,
    *,
    read_at: str | None = None,
) -> dict | None:
    """Advance a single outbound message status. Returns updated record or None."""
    data = load_inbox(slot)
    key = str(user_id)
    conv = data.get("conversations", {}).get(key)
    if not conv:
        return None
    msg = _find_message(conv, message_id)
    if not msg or msg.get("direction") != "out":
        return None
    current = msg.get("status") or "sent"
    if not _can_advance_outbound(current, status):
        return _normalize_outbound_record(msg)
    msg["status"] = status
    if status == "read":
        msg["read_at"] = read_at or _now_iso()
    data["conversations"][key] = conv
    save_inbox(slot, data)
    return _normalize_outbound_record(msg)


def mark_outbound_delivered(slot: str, user_id: int, message_id: int) -> dict | None:
    return update_outbound_status(slot, user_id, message_id, "delivered")


def mark_conversation_read(slot: str, user_id: int) -> dict | None:
    data = load_inbox(slot)
    key = str(user_id)
    conv = data["conversations"].get(key)
    if not conv:
        return None
    conv["unread_count"] = 0
    save_inbox(slot, data)
    return conv


def list_conversations(slot: str) -> list[dict]:
    data = load_inbox(slot)
    items = []
    dirty = False
    for conv in data.get("conversations", {}).values():
        unread = int(conv.get("unread_count") or 0)
        msgs = conv.get("messages") or []
        if unread > 0 and msgs and msgs[-1].get("direction") == "out":
            conv["unread_count"] = 0
            unread = 0
            dirty = True
        items.append({
            "user_id": conv.get("user_id"),
            "username": conv.get("username") or "",
            "name": conv.get("name") or "",
            "last_message": conv.get("last_message") or "",
            "last_message_at": conv.get("last_message_at"),
            "unread_count": unread,
        })
    if dirty:
        save_inbox(slot, data)
    items.sort(key=lambda c: c.get("last_message_at") or "", reverse=True)
    return items


def _mark_outbound_read(msg: dict) -> bool:
    if msg.get("direction") != "out" or msg.get("status") == "read":
        return False
    msg["status"] = "read"
    msg["read_at"] = _now_iso()
    return True


def mark_outgoing_read_up_to(slot: str, user_id: int, max_telegram_id: int) -> list[dict]:
    """Mark outgoing messages with id <= max_telegram_id as read. Returns updated records."""
    if max_telegram_id <= 0:
        return []
    data = load_inbox(slot)
    key = str(user_id)
    conv = data.get("conversations", {}).get(key)
    if not conv:
        return []
    updated: list[dict] = []
    for m in conv.get("messages") or []:
        if m.get("direction") != "out":
            continue
        mid = int(m.get("id") or 0)
        if mid > 0 and mid <= max_telegram_id and _mark_outbound_read(m):
            updated.append(_normalize_outbound_record(m))
    if updated:
        save_inbox(slot, data)
    return updated


def mark_all_outgoing_read(slot: str, user_id: int) -> list[dict]:
    """Mark every outbound message in a thread as read (e.g. contact replied)."""
    data = load_inbox(slot)
    key = str(user_id)
    conv = data.get("conversations", {}).get(key)
    if not conv:
        return []
    updated: list[dict] = []
    for m in conv.get("messages") or []:
        if m.get("direction") == "out" and _mark_outbound_read(m):
            updated.append(_normalize_outbound_record(m))
    if updated:
        save_inbox(slot, data)
    return updated


def infer_outgoing_read_from_thread(conv: dict) -> list[dict]:
    """
    If the contact replied after our messages, treat our earlier outbound as read.
    Covers history loaded before read receipts were tracked.
    """
    msgs = conv.get("messages") or []
    if not msgs or msgs[-1].get("direction") != "in":
        return []
    updated: list[dict] = []
    for m in msgs:
        if m.get("direction") == "out" and _mark_outbound_read(m):
            updated.append(_normalize_outbound_record(m))
    return updated


def migrate_legacy_sent_to_delivered(slot: str, user_id: int) -> list[dict]:
    """Persist upgrade for old outbound rows still stored as 'sent'."""
    data = load_inbox(slot)
    key = str(user_id)
    conv = data.get("conversations", {}).get(key)
    if not conv:
        return []
    updated: list[dict] = []
    for m in conv.get("messages") or []:
        if m.get("direction") == "out" and m.get("status") == "sent":
            m["status"] = "delivered"
            updated.append(_normalize_outbound_record(m))
    if updated:
        save_inbox(slot, data)
    return updated


def get_messages(
    slot: str,
    user_id: int,
    *,
    persist_read_hints: bool = True,
) -> list[dict]:
    data = load_inbox(slot)
    key = str(user_id)
    conv = data.get("conversations", {}).get(key)
    if not conv:
        return []
    changed = False
    migrated = migrate_legacy_sent_to_delivered(slot, user_id)
    if migrated:
        changed = True
        data = load_inbox(slot)
        conv = data.get("conversations", {}).get(key) or conv
    inferred = infer_outgoing_read_from_thread(conv)
    if persist_read_hints and inferred:
        save_inbox(slot, data)
        data = load_inbox(slot)
        conv = data.get("conversations", {}).get(key, conv)
    msgs = [_normalize_outbound_record(m) for m in (conv.get("messages") or [])]
    msgs.sort(key=lambda m: (m.get("timestamp") or "", int(m.get("id") or 0)))
    return msgs


def build_slot_payload(slot: str) -> dict:
    return {
        "slot": slot,
        "conversations": list_conversations(slot),
        "updated_at": load_inbox(slot).get("updated_at"),
    }
