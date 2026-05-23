"""
Independent DM inbox — private chats only.
Hooks Telethon NewMessage on any connected client; no imports from account_worker.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from telethon import TelegramClient, events
from telethon.tl.types import User

from core import broadcast, telegram_client
from core.account_info_store import load_account_info
from core.config import ACCOUNTS
from core.dm_filter import validate_incoming_dm, validate_outgoing_dm
from core.dm_store import (
    append_message,
    build_slot_payload as _dm_build_slot_payload,
    load_inbox,
    mark_all_outgoing_read,
    mark_conversation_read,
    mark_outbound_delivered,
    mark_outgoing_read_up_to,
)

logger = logging.getLogger(__name__)

_handlers_attached: set[str] = set()
_handler_refs: dict[str, dict[str, Any]] = {}
_handler_clients: dict[str, TelegramClient] = {}
_listener_clients: dict[str, TelegramClient] = {}
_listener_refresh_tasks: dict[str, asyncio.Task] = {}
_bootstrap_done = False


def _is_logged_in(slot: str) -> bool:
    info = load_account_info(slot)
    return bool(info and info.get("phone"))


async def _broadcast_status(
    slot: str,
    user_id: int,
    message: dict,
    *,
    conversation: dict | None = None,
) -> None:
    """Real-time outbound status change (sent → delivered → read)."""
    await _broadcast_inbox(
        slot,
        "message_status",
        conversation=conversation or {"user_id": user_id},
        message={
            "user_id": user_id,
            "chat_id": message.get("chat_id", user_id),
            "account_id": slot,
            "message_id": message.get("id"),
            "status": message.get("status"),
            "read_at": message.get("read_at"),
            "direction": message.get("direction"),
            "text": message.get("text"),
            "timestamp": message.get("timestamp"),
        },
    )


async def _broadcast_inbox(
    slot: str,
    event: str,
    *,
    conversation: dict | None = None,
    message: dict | None = None,
) -> None:
    payload: dict = {
        "type": "inbox",
        "event": event,
        "slot": slot,
        "inbox": build_slot_payload(slot),
    }
    if conversation is not None:
        payload["conversation"] = conversation
    if message is not None:
        payload["message"] = message
    await broadcast.broadcast(payload)


async def _broadcast_daily_stats() -> None:
    """Push recalculated daily counters after inbox activity."""
    from core.daily_stats import compute_daily_stats

    await broadcast.broadcast({
        "type": "daily_stats",
        "daily_stats": compute_daily_stats(list(ACCOUNTS)),
    })


def build_slot_payload(slot: str) -> dict:
    from services.crm_service import enrich_conversation

    raw = _dm_build_slot_payload(slot)
    raw["conversations"] = [
        enrich_conversation(slot, c) for c in raw.get("conversations") or []
    ]
    return raw


def _conversation_summary(conv: dict) -> dict:
    return {
        "user_id": conv["user_id"],
        "username": conv.get("username"),
        "name": conv.get("name"),
        "last_message": conv.get("last_message"),
        "last_message_at": conv.get("last_message_at"),
        "unread_count": conv.get("unread_count"),
    }


async def _handle_dm_event(
    slot: str,
    event: events.NewMessage.Event,
    *,
    direction: str,
    increment_unread: bool,
) -> None:
    if direction == "in":
        ok, meta = await validate_incoming_dm(event)
    else:
        ok, meta = await validate_outgoing_dm(event)
    if not ok or not meta:
        return

    text = event.message.message or ""
    if not text and not event.message.media:
        return

    status = "received" if direction == "in" else "sent"
    conv, record, created = append_message(
        slot,
        user_id=meta["user_id"],
        username=meta["username"],
        name=meta["name"],
        text=text,
        direction=direction,
        telegram_id=event.message.id,
        status=status,
        increment_unread=increment_unread,
        account_id=slot,
    )
    if not created:
        return

    from services.crm_service import enrich_conversation, touch_from_message

    touch_from_message(
        slot,
        meta["user_id"],
        direction=direction,
        name=meta.get("name") or "",
        username=meta.get("username") or "",
    )
    from services.block_service import ensure_blocked_lead_status

    ensure_blocked_lead_status(
        slot,
        meta["user_id"],
        name=meta.get("name") or "",
        username=meta.get("username") or "",
    )
    summary = enrich_conversation(slot, _conversation_summary(conv))
    uid = meta["user_id"]

    if direction == "in":
        read_updates = mark_all_outgoing_read(slot, uid)
        try:
            from events.event_bus import event_bus
            from events.event_types import EventType

            await event_bus.publish(
                EventType.MESSAGE_RECEIVED,
                slot,
                {
                    "user_id": uid,
                    "username": meta.get("username", ""),
                    "name": meta.get("name", ""),
                    "message_id": record.get("id"),
                },
                push_state=False,
            )
        except Exception:
            pass
        await _broadcast_inbox(
            slot,
            "new_message",
            conversation=summary,
            message=record,
        )
        for m in read_updates:
            await _broadcast_status(slot, uid, m, conversation=summary)
        await _broadcast_daily_stats()
        return

    await _broadcast_inbox(
        slot,
        "outgoing_message",
        conversation=summary,
        message=record,
    )
    delivered = mark_outbound_delivered(slot, uid, record["id"])
    if delivered:
        await _broadcast_status(slot, uid, delivered, conversation=summary)
    await _broadcast_daily_stats()


async def _on_incoming_message(slot: str, event: events.NewMessage.Event) -> None:
    try:
        await _handle_dm_event(slot, event, direction="in", increment_unread=True)
    except Exception as e:
        logger.warning("DM inbox incoming %s: %s", slot, e)


async def _on_outgoing_message(slot: str, event: events.NewMessage.Event) -> None:
    try:
        await _handle_dm_event(slot, event, direction="out", increment_unread=False)
    except Exception as e:
        logger.warning("DM inbox outgoing %s: %s", slot, e)


async def _resolve_private_user_id(event: events.MessageRead.Event) -> int | None:
    if not getattr(event, "is_private", False):
        return None
    try:
        chat = await event.get_chat()
    except Exception:
        return None
    from core.dm_filter import is_private_dm_chat

    if not is_private_dm_chat(chat):
        return None
    return int(chat.id)


async def _on_message_read_outbox(slot: str, event: events.MessageRead.Event) -> None:
    """Recipient read our outbound messages (Telegram double-check)."""
    try:
        user_id = await _resolve_private_user_id(event)
        if user_id is None:
            return

        max_id = int(getattr(event, "max_id", 0) or 0)
        if not max_id and getattr(event, "message_ids", None):
            max_id = max(int(x) for x in event.message_ids)

        if max_id <= 0:
            return

        updated = mark_outgoing_read_up_to(slot, user_id, max_id)
        if not updated:
            return

        data = load_inbox(slot)
        conv = data.get("conversations", {}).get(str(user_id), {})
        summary = _conversation_summary(conv) if conv else {"user_id": user_id}
        await _broadcast_inbox(
            slot,
            "message_read",
            conversation=summary,
            message={"user_id": user_id, "max_id": max_id, "updated": len(updated)},
        )
        for m in updated:
            await _broadcast_status(slot, user_id, m, conversation=summary)
    except Exception as e:
        logger.warning("DM inbox read receipt %s: %s", slot, e)


async def _fetch_read_outbox_max_id(client: TelegramClient, user_id: int) -> int:
    """Telegram's read_outbox_max_id for a private chat."""
    try:
        entity = await client.get_entity(int(user_id))
        target = int(entity.id)
        async for dialog in client.iter_dialogs(limit=80):
            ent = dialog.entity
            if getattr(ent, "id", None) == target:
                return int(dialog.dialog.read_outbox_max_id or 0)
    except Exception as e:
        logger.debug("read_outbox_max_id %s: %s", user_id, e)
    return 0


async def sync_read_receipts(slot: str, user_id: int) -> list[dict]:
    """Apply Telegram read state to stored messages before returning to UI."""
    from core.dm_store import load_inbox, save_inbox, infer_outgoing_read_from_thread

    async def operation(client: TelegramClient):
        max_id = await _fetch_read_outbox_max_id(client, user_id)
        updated = mark_outgoing_read_up_to(slot, user_id, max_id)
        data = load_inbox(slot)
        conv = data.get("conversations", {}).get(str(user_id))
        if conv:
            inferred = infer_outgoing_read_from_thread(conv)
            if inferred:
                save_inbox(slot, data)
                updated = updated or inferred
        return updated

    try:
        if telegram_client.is_login_exclusive(slot):
            return []
        return await telegram_client.run_dm_operation(slot, operation)
    except Exception as e:
        logger.debug("sync_read_receipts %s %s: %s", slot, user_id, e)
        return []


async def attach_handlers(slot: str, client: TelegramClient) -> None:
    """Register private-DM listeners (incoming + outgoing) on an existing client."""
    if slot not in ACCOUNTS:
        return
    prev = _handler_clients.get(slot)
    if slot in _handlers_attached and prev is client:
        return
    if slot in _handlers_attached:
        detach_handlers(slot, prev)

    def _make_incoming(s: str):
        async def handler(event: events.NewMessage.Event) -> None:
            await _on_incoming_message(s, event)
        return handler

    def _make_outgoing(s: str):
        async def handler(event: events.NewMessage.Event) -> None:
            await _on_outgoing_message(s, event)
        return handler

    def _make_read_outbox(s: str):
        async def handler(event: events.MessageRead.Event) -> None:
            await _on_message_read_outbox(s, event)
        return handler

    from telethon.tl.types import UpdatePhoneCall

    from services.phone_call_service import make_phone_call_handler

    handler_in = _make_incoming(slot)
    handler_out = _make_outgoing(slot)
    handler_read = _make_read_outbox(slot)
    handler_phone = make_phone_call_handler(slot, client)
    client.add_event_handler(handler_in, events.NewMessage(incoming=True))
    client.add_event_handler(handler_out, events.NewMessage(outgoing=True))
    client.add_event_handler(handler_read, events.MessageRead(inbox=False))
    client.add_event_handler(handler_phone, events.Raw(types=[UpdatePhoneCall]))
    _handlers_attached.add(slot)
    _handler_clients[slot] = client
    _handler_refs[slot] = {
        "incoming": handler_in,
        "outgoing": handler_out,
        "read_outbox": handler_read,
        "phone_call": handler_phone,
    }
    logger.info("DM inbox listeners attached for %s", slot)


def detach_handlers(slot: str, client: TelegramClient | None = None) -> None:
    refs = _handler_refs.pop(slot, None)
    if refs and client is not None:
        for handler in refs.values():
            try:
                client.remove_event_handler(handler)
            except Exception:
                pass
    _handlers_attached.discard(slot)


async def inbox_on_client_connected(slot: str, client: TelegramClient) -> None:
    if not _is_logged_in(slot):
        return
    # Prefer dedicated string-session listener (avoids duplicate events + SQLite lock).
    existing = _listener_clients.get(slot)
    if existing is not None:
        try:
            if existing.is_connected():
                return
        except Exception:
            pass
    await attach_handlers(slot, client)


async def inbox_on_client_disconnected(slot: str) -> None:
    client = telegram_client.get_client_ref(slot)
    detach_handlers(slot, client)


def _telegram_msg_timestamp(msg) -> str:
    dt = getattr(msg, "date", None)
    if dt is None:
        from core.dm_store import _now_iso

        return _now_iso()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _telegram_msg_text(msg) -> str:
    text = (msg.message or "").strip()
    if text:
        return text
    if msg.media:
        return "[media]"
    return ""


def _peer_meta_from_entity(entity: User) -> dict:
    from core.dm_filter import _peer_meta

    return _peer_meta(entity)


async def _sync_conversation_with_client(
    client: TelegramClient,
    slot: str,
    user_id: int,
    *,
    limit: int = 60,
) -> list[dict]:
    from services.block_service import assert_not_blocked

    try:
        assert_not_blocked(slot, int(user_id))
    except Exception:
        return []

    last_inbound: dict | None = None
    entity = await client.get_entity(int(user_id))
    if not isinstance(entity, User) or getattr(entity, "bot", False):
        return []
    meta = _peer_meta_from_entity(entity)
    collected: list = []
    async for msg in client.iter_messages(entity, limit=limit):
        collected.append(msg)
    collected.reverse()
    created_records: list[dict] = []
    for msg in collected:
        text = _telegram_msg_text(msg)
        if not text:
            continue
        direction = "out" if bool(getattr(msg, "out", False)) else "in"
        status = "delivered" if direction == "out" else "received"
        _conv, record, created = append_message(
            slot,
            user_id=meta["user_id"],
            username=meta["username"],
            name=meta["name"],
            text=text,
            direction=direction,
            telegram_id=int(msg.id),
            status=status,
            increment_unread=direction == "in",
            account_id=slot,
            timestamp=_telegram_msg_timestamp(msg),
        )
        if created:
            created_records.append(record)
            if direction == "in":
                last_inbound = record
    if last_inbound:
        from services.crm_service import touch_from_message

        data = load_inbox(slot)
        conv = data.get("conversations", {}).get(str(user_id)) or {}
        touch_from_message(
            slot,
            int(user_id),
            direction="in",
            name=conv.get("name") or "",
            username=conv.get("username") or "",
        )
        mark_all_outgoing_read(slot, int(user_id))
    return created_records


async def _finalize_sync_broadcast(slot: str, user_id: int, new_records: list[dict]) -> None:
    if not new_records:
        return
    from services.crm_service import enrich_conversation

    data = load_inbox(slot)
    conv = data.get("conversations", {}).get(str(user_id)) or {}
    summary = enrich_conversation(slot, _conversation_summary(conv))
    for record in new_records:
        event = "new_message" if record.get("direction") == "in" else "outgoing_message"
        await _broadcast_inbox(slot, event, conversation=summary, message=record)
    await _broadcast_daily_stats()


async def _ensure_string_session_exported(slot: str) -> bool:
    from core.dm_string_session import load_string_session, run_with_string_session, save_string_session

    if load_string_session(slot):
        return True
    try:

        async def grab(client: TelegramClient) -> None:
            save_string_session(slot, client)

        await run_with_string_session(slot, grab)
        if load_string_session(slot):
            return True
    except Exception as e:
        logger.debug("export string session %s: %s", slot, e)
    try:

        async def grab(client: TelegramClient) -> None:
            save_string_session(slot, client)

        await telegram_client.run_dm_operation(
            slot, grab, attempts=2, attach_inbox_handlers=False
        )
    except Exception:
        pass
    return bool(load_string_session(slot))


async def _run_sync_with_client(
    slot: str,
    operation: Callable[[TelegramClient], Awaitable[list[dict]]],
) -> list[dict]:
    from core.dm_string_session import run_with_string_session

    await _ensure_string_session_exported(slot)
    try:
        return await run_with_string_session(slot, operation)
    except Exception as e:
        logger.debug("string session sync %s: %s", slot, e)
    ref = telegram_client.get_client_ref(slot)
    if ref is not None:
        try:
            if ref.is_connected():
                return await operation(ref)
        except Exception:
            pass
    async def wrapped(client: TelegramClient) -> list[dict]:
        return await operation(client)

    return await telegram_client.run_dm_operation(
        slot, wrapped, attempts=4, attach_inbox_handlers=False
    )


async def sync_conversation_from_telegram(
    slot: str,
    user_id: int,
    *,
    limit: int = 60,
) -> list[dict]:
    """
    Pull recent private messages from Telegram into the local inbox store.
    Backfill when live listeners were offline (session release, reload, etc.).
    """
    if not _is_logged_in(slot):
        return []
    if telegram_client.is_login_exclusive(slot):
        return []

    async def operation(client: TelegramClient) -> list[dict]:
        return await _sync_conversation_with_client(
            client, slot, int(user_id), limit=limit
        )

    try:
        new_records = await _run_sync_with_client(slot, operation)
    except Exception as e:
        logger.warning("sync_conversation %s %s: %s", slot, user_id, e)
        new_records = []

    await _finalize_sync_broadcast(slot, int(user_id), new_records)
    return new_records


async def sync_stored_conversations(
    slot: str,
    *,
    per_chat_limit: int = 8,
    max_chats: int = 12,
) -> int:
    """Light refresh of stored threads (used by inbox list polling)."""
    if not _is_logged_in(slot) or telegram_client.is_login_exclusive(slot):
        return 0
    data = load_inbox(slot)
    convs = list((data.get("conversations") or {}).values())
    convs.sort(key=lambda c: c.get("last_message_at") or "", reverse=True)
    targets = convs[:max_chats]
    if not targets:
        return 0

    async def operation(client: TelegramClient):
        total: list[dict] = []
        for conv in targets:
            uid = conv.get("user_id")
            if uid is None:
                continue
            try:
                added = await _sync_conversation_with_client(
                    client,
                    slot,
                    int(uid),
                    limit=per_chat_limit,
                )
                if added:
                    total.extend(added)
                    await _finalize_sync_broadcast(slot, int(uid), added)
            except Exception as e:
                logger.debug("sync_stored %s %s: %s", slot, uid, e)
        return total

    try:
        created = await _run_sync_with_client(slot, operation)
        return len(created)
    except Exception as e:
        logger.debug("sync_stored_conversations %s: %s", slot, e)
        return 0


async def ensure_inbox_listener(slot: str) -> None:
    """Dedicated DM listener on StringSession (independent of worker SQLite)."""
    if not _is_logged_in(slot) or telegram_client.is_login_exclusive(slot):
        return
    from core.dm_string_session import connect_inbox_listener, load_string_session

    if not load_string_session(slot):
        if not await _ensure_string_session_exported(slot):
            return

    prev = _listener_clients.get(slot)
    if prev is not None:
        try:
            if prev.is_connected() and slot in _handlers_attached:
                return
        except Exception:
            pass
        detach_handlers(slot, prev)
        try:
            await prev.disconnect()
        except Exception:
            pass

    client = await connect_inbox_listener(slot)
    if client is None:
        return
    _listener_clients[slot] = client
    await attach_handlers(slot, client)
    logger.info("DM inbox listener (string session) active for %s", slot)


async def suspend_all_for_login() -> None:
    """Stop all inbox listeners while OTP login runs (any slot)."""
    for slot in list(ACCOUNTS.keys()):
        await suspend_for_login(slot)


async def suspend_for_login(slot: str) -> None:
    """Stop inbox listener and cancel refresh so OTP login can open the SQLite session."""
    prev = _listener_refresh_tasks.pop(slot, None)
    if prev is not None and not prev.done():
        prev.cancel()
    client = _listener_clients.pop(slot, None)
    if client is not None:
        detach_handlers(slot, client)
        try:
            await client.disconnect()
        except Exception:
            pass
    _listener_clients.pop(slot, None)


def schedule_inbox_listener_refresh(slot: str) -> None:
    prev = _listener_refresh_tasks.get(slot)
    if prev is not None and not prev.done():
        prev.cancel()

    async def _run() -> None:
        await asyncio.sleep(1.0)
        try:
            await ensure_inbox_listener(slot)
        except Exception as e:
            logger.debug("inbox listener refresh %s: %s", slot, e)

    _listener_refresh_tasks[slot] = asyncio.create_task(_run())


async def run_dm_send(
    slot: str,
    user_id: int,
    text: str,
) -> dict:
    """Manual reply only — sends from the same account slot that owns the conversation."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Message text is required")
    if not _is_logged_in(slot):
        raise RuntimeError(f"{slot} is not logged in")

    from services.block_service import assert_not_blocked

    assert_not_blocked(slot, int(user_id))

    async def operation(client: TelegramClient):
        entity = await client.get_entity(int(user_id))
        if not isinstance(entity, User) or getattr(entity, "bot", False):
            raise ValueError("Not a private user chat")
        sent = await client.send_message(entity, text)
        username = (getattr(entity, "username", None) or "").strip()
        first = (getattr(entity, "first_name", None) or "").strip()
        last = (getattr(entity, "last_name", None) or "").strip()
        name = " ".join(p for p in (first, last) if p).strip() or username or str(user_id)
        conv, record, _created = append_message(
            slot,
            user_id=int(user_id),
            username=username,
            name=name,
            text=text,
            direction="out",
            telegram_id=sent.id,
            status="sent",
            increment_unread=False,
            account_id=slot,
        )
        return conv, record

    async def wrapped(client: TelegramClient):
        await attach_handlers(slot, client)
        return await operation(client)

    try:
        conv, record = await telegram_client.run_dm_operation(slot, wrapped)
        await sync_conversation_from_telegram(slot, int(user_id), limit=25)
    except Exception:
        await _broadcast_inbox(
            slot,
            "message_status",
            conversation={"user_id": int(user_id)},
            message={
                "user_id": int(user_id),
                "account_id": slot,
                "status": "failed",
                "direction": "out",
            },
        )
        raise

    from services.crm_service import enrich_conversation, touch_from_message

    mark_conversation_read(slot, int(user_id))
    conv = load_inbox(slot).get("conversations", {}).get(str(user_id), conv)
    touch_from_message(
        slot,
        int(user_id),
        direction="out",
        name=conv.get("name") or "",
        username=conv.get("username") or "",
    )
    summary = enrich_conversation(slot, _conversation_summary(conv))
    uid = int(user_id)
    await _broadcast_inbox(slot, "reply_sent", conversation=summary, message=record)
    delivered = mark_outbound_delivered(slot, uid, record["id"])
    if delivered:
        record = delivered
        await _broadcast_status(slot, uid, delivered, conversation=summary)
    await _broadcast_daily_stats()
    return {"ok": True, "conversation": conv, "message": record}


async def bootstrap_listeners(*, force: bool = False) -> None:
    """Start string-session DM listeners (does not compete with worker SQLite)."""
    global _bootstrap_done
    if _bootstrap_done and not force:
        return

    await asyncio.sleep(2.0)
    attached = 0
    for slot in ACCOUNTS:
        if not _is_logged_in(slot):
            continue
        if telegram_client.is_login_exclusive(slot):
            logger.info("Inbox listener defer %s: login in progress", slot)
            continue
        try:
            await ensure_inbox_listener(slot)
            if slot in _handlers_attached:
                attached += 1
        except Exception as e:
            logger.info("Inbox listener skip %s: %s", slot, e)
        await asyncio.sleep(1.2)

    _bootstrap_done = True
    logger.info("DM inbox bootstrap done — listeners on %s account(s)", attached)


async def ensure_inbox_listeners() -> None:
    """Re-attach listeners after worker resume or reload (safe to call repeatedly)."""
    await bootstrap_listeners(force=True)


def build_all_inboxes() -> dict:
    slots = {}
    for slot in ACCOUNTS:
        if _is_logged_in(slot):
            slots[slot] = build_slot_payload(slot)
    return {"slots": slots}


def get_combined_conversations() -> list[dict]:
    combined = []
    for slot in ACCOUNTS:
        if not _is_logged_in(slot):
            continue
        for c in build_slot_payload(slot)["conversations"]:
            combined.append({**c, "account_id": slot})
    combined.sort(key=lambda x: x.get("last_message_at") or "", reverse=True)
    return combined


async def mark_read(slot: str, user_id: int) -> None:
    mark_conversation_read(slot, user_id)
    await _broadcast_inbox(slot, "read", conversation={"user_id": user_id, "unread_count": 0})
