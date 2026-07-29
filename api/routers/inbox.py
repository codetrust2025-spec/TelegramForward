"""Auto-extracted inbox routes (pure move from server.py)."""
import asyncio
import json
import os
import shutil
from datetime import datetime
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from core import broadcast
from core.config import ACCOUNTS, ACCOUNT_SLOTS, BASE_DIR, DATA_DIR, GROUPS_FILE, MESSAGE_FILE
from core.groups_store import (
    _normalize_group_name,
    build_group_lists,
    collect_all_dead_for_upload,
    ensure_groups_loaded,
    ensure_invalid_registry_backfill,
    is_valid_group_username,
    load_account_dead,
    load_master_groups,
    normalize_upload_username,
    save_master_groups,
)
from core.config import MESSAGE_REWRITE_ENABLED
from core.message_rewrite import preview_cycle_message
from core.message_store import (
    load_message,
    load_message_for_account,
    save_message,
    save_message_for_account,
)
from core import telegram_client
from telethon import TelegramClient
from core.account_info_store import (
    clear_account_info,
    duplicate_phone_login_message,
    find_logged_in_slot_by_phone,
    load_account_info,
    save_account_info,
)
from core.login_pending import clear_pending, load_pending, save_pending
from core.worker_persistence import log_reload_event
from services.account_manager import manager
from events.event_bus import event_bus
from events.event_types import EventType
from core.admin_dashboard import install_admin_dashboard
from core.dashboard_auth_api import install_dashboard_auth
from core.voice_call_api import install_voice_call_routes
from core.web_push_api import install_web_push_routes
from core.whatsapp_api import install_whatsapp_routes
from core.public_slot_api import install_public_slot_routes
from core.demo_tools_api import install_demo_tools_routes
from core.recruitment_mail_api import install_recruitment_mail_routes
from fastapi import APIRouter
from server import (
    _push_state,
)

router = APIRouter()

@router.get("/message")
async def get_message(slot: str | None = None):
    if slot and slot in ACCOUNTS:
        return {
            "message": load_message_for_account(slot),
            "slot": slot,
            "rewrite_enabled": MESSAGE_REWRITE_ENABLED,
        }
    return {"message": load_message(), "rewrite_enabled": MESSAGE_REWRITE_ENABLED}
@router.get("/message/preview")
async def message_preview(slot: str, cycle: int = 1):
    if slot not in ACCOUNTS:
        return {"success": False, "error": "Invalid slot"}
    return {"success": True, **preview_cycle_message(slot, max(1, cycle))}
@router.post("/message")
async def update_message(payload: dict):
    text = payload.get("message", "").strip()
    slot = payload.get("slot")
    if not text:
        return {"success": False, "error": "Message cannot be empty"}
    if slot and slot in ACCOUNTS:
        save_message_for_account(slot, text)
    else:
        save_message(text)
    await _push_state()
    return {"success": True, "slot": slot}
@router.post("/inbox/listeners/refresh")
async def inbox_ensure_listeners():
    """Re-attach Telethon DM listeners (after reload or if live messages stop)."""
    from services.dm_inbox_service import bootstrap_listeners

    await bootstrap_listeners(force=True)
    return {"status": "ok", "message": "DM listeners re-attached"}
@router.post("/inbox/{slot}/sync/{user_id}")
async def inbox_force_sync(slot: str, user_id: int):
    """Pull latest messages from Telegram for one chat (bypasses UI)."""
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.dm_store import get_messages
    from services.dm_inbox_service import sync_conversation_from_telegram

    added = await sync_conversation_from_telegram(slot, user_id, limit=200)
    return {
        "status": "ok",
        "added": len(added),
        "messages": get_messages(slot, user_id),
    }
@router.get("/inbox")
async def inbox_all(
    slot: str | None = Query(None),
    combined: bool = Query(False),
    sync: bool = Query(False),
):
    from services import dm_inbox_service

    if sync:
        for s in ACCOUNTS:
            try:
                await dm_inbox_service.sync_stored_conversations(s)
            except Exception:
                pass

    if slot:
        if slot not in ACCOUNTS:
            return {"status": "error", "message": "Invalid slot"}
        return {"status": "ok", **dm_inbox_service.build_slot_payload(slot)}
    if combined:
        return {
            "status": "ok",
            "combined": True,
            "conversations": dm_inbox_service.get_combined_conversations(),
        }
    return {"status": "ok", **dm_inbox_service.build_all_inboxes()}
@router.get("/inbox/{slot}/messages/{user_id}")
async def inbox_messages(
    slot: str,
    user_id: int,
    sync: bool = Query(True),
):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    import asyncio

    from core.dm_store import get_messages
    from services import dm_inbox_service

    from core.dm_store import load_inbox

    messages = get_messages(slot, user_id)
    if sync:
        try:
            await dm_inbox_service.sync_read_receipts(slot, user_id)
        except Exception:
            pass
        try:
            await asyncio.wait_for(
                dm_inbox_service.sync_conversation_from_telegram(
                    slot, user_id, limit=dm_inbox_service.INBOX_INITIAL_SYNC_LIMIT
                ),
                timeout=30.0,
            )
            messages = get_messages(slot, user_id)
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass
        # Only auto-mark-read on the explicit sync path. The fast (sync=0) path
        # is a passive preview; the front-end calls POST /inbox/{slot}/read/{user_id}
        # once the user has actually viewed the chat.
        key = str(user_id)
        had_unread = int(
            load_inbox(slot).get("conversations", {}).get(key, {}).get("unread_count") or 0
        ) > 0
        if had_unread:
            await dm_inbox_service.mark_read(slot, user_id)
    return {"status": "ok", "slot": slot, "user_id": user_id, "messages": messages}
@router.post("/inbox/{slot}/messages/{user_id}/older")
async def inbox_messages_older(
    slot: str,
    user_id: int,
    before_id: int = Query(..., description="Oldest telegram message id already stored"),
    limit: int = Query(100, ge=10, le=200),
):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.dm_store import get_messages
    from services import dm_inbox_service

    if before_id <= 0:
        return {"status": "error", "message": "Invalid before_id"}
    try:
        meta = await dm_inbox_service.sync_older_messages_from_telegram(
            slot,
            user_id,
            before_telegram_id=before_id,
            limit=limit,
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {
        "status": "ok",
        "slot": slot,
        "user_id": user_id,
        "messages": get_messages(slot, user_id),
        **meta,
    }
@router.get("/inbox/{slot}/messages/{user_id}/export")
async def inbox_export_chat(
    slot: str,
    user_id: int,
    format: str = Query("txt", alias="format"),
):
    """Download one stored conversation (txt, csv, or json)."""
    from fastapi import HTTPException
    from fastapi.responses import Response

    if slot not in ACCOUNTS:
        raise HTTPException(status_code=404, detail="Invalid slot")
    from features.inbox_export import export_conversation

    try:
        body, mime, filename = export_conversation(slot, int(user_id), format)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return Response(
        content=body,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
@router.get("/inbox/{slot}/media/{user_id}/{message_id}")
async def inbox_media(slot: str, user_id: int, message_id: int):
    from fastapi import HTTPException

    if slot not in ACCOUNTS:
        raise HTTPException(status_code=404, detail="Invalid slot")
    from services import dm_inbox_service

    hit = await dm_inbox_service.ensure_inbox_media_file(slot, int(user_id), int(message_id))
    if not hit:
        raise HTTPException(status_code=404, detail="Media not found")
    path, mime = hit
    from core.dm_media import mime_for_cached_file

    return FileResponse(path, media_type=mime_for_cached_file(path) or mime)
@router.post("/inbox/{slot}/reply")
async def inbox_reply(slot: str, body: dict, request: Request):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    user_id = body.get("user_id")
    text = body.get("text") or body.get("message") or ""
    # Track who composed this outbound message: "manual" (operator typed
    # from scratch) or "ai_approved" (operator clicked Suggest, then Send).
    # Other values are ignored and fall back to "manual" so callers can't
    # spoof exotic provenance.
    sent_by_raw = (body.get("sent_by") or "manual").strip().lower()
    sent_by = sent_by_raw if sent_by_raw in {"manual", "ai_approved"} else "manual"
    from core import dashboard_auth_vps as dashboard_auth

    operator_name = (
        dashboard_auth.username_from_request_cookies(dict(request.cookies))
        or (body.get("operator_name") or "").strip()
        or "Operator"
    )
    if user_id is None:
        return {"status": "error", "message": "user_id required"}
    channel = (body.get("channel") or "").strip().lower()
    if channel == "whatsapp":
        try:
            from services.whatsapp_dispatch import dispatch_lead_reply
            from services.crm_service import enrich_conversation, get_lead

            result = await dispatch_lead_reply(
                slot,
                int(user_id),
                str(text),
                sent_by=sent_by,
                channel="whatsapp",
            )
            conv = result.get("conversation") or {}
            uid = int(user_id)
            summary = enrich_conversation(
                slot,
                {
                    "user_id": uid,
                    "username": conv.get("username") or "",
                    "name": conv.get("name") or "",
                    "last_message": conv.get("last_message") or "",
                    "last_message_at": conv.get("last_message_at"),
                    "unread_count": conv.get("unread_count") or 0,
                    "phone_e164": conv.get("phone_e164"),
                    "channels": conv.get("channels"),
                    "whatsapp_linked": conv.get("whatsapp_linked"),
                },
            ) if conv else enrich_conversation(
                slot,
                {"user_id": uid, "username": "", "name": "", "unread_count": 0},
            )
            lead = get_lead(slot, uid)
            return {
                "status": "ok",
                "message": result.get("message"),
                "conversation": summary,
                "lead": lead,
                "channel": "whatsapp",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    reply_to_raw = body.get("reply_to_message_id") or body.get("reply_to")
    reply_to_message_id = None
    if reply_to_raw is not None:
        try:
            rid = int(reply_to_raw)
            if rid > 0:
                reply_to_message_id = rid
        except (TypeError, ValueError):
            pass
    try:
        from messaging.message_router import message_router

        result = await message_router.enqueue_dm_send(
            slot,
            int(user_id),
            str(text),
            wait=True,
            sent_by=sent_by,
            operator_name=operator_name,
            reply_to_message_id=reply_to_message_id,
        )
        from services.crm_service import enrich_conversation, get_lead

        conv = result.get("conversation") or {}
        uid = int(user_id)
        summary = enrich_conversation(
            slot,
            {
                "user_id": uid,
                "username": conv.get("username") or "",
                "name": conv.get("name") or "",
                "last_message": conv.get("last_message") or "",
                "last_message_at": conv.get("last_message_at"),
                "unread_count": conv.get("unread_count") or 0,
            },
        )
        lead = get_lead(slot, uid)
        return {
            "status": "ok",
            "message": result.get("message"),
            "conversation": summary,
            "lead": lead,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
@router.post("/inbox/{slot}/reply-media")
async def inbox_reply_media(
    slot: str,
    request: Request,
    user_id: int = Form(...),
    file: UploadFile = File(...),
    caption: str = Form(""),
    reply_to_message_id: str = Form(""),
):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.config import STATE_DIR
    from core.dm_media import OUTBOUND_UPLOAD_MAX_BYTES
    from core import dashboard_auth_vps as dashboard_auth

    operator_name = (
        dashboard_auth.username_from_request_cookies(dict(request.cookies))
        or "Operator"
    )
    reply_to_id = None
    if reply_to_message_id:
        try:
            rid = int(str(reply_to_message_id).strip())
            if rid > 0:
                reply_to_id = rid
        except (TypeError, ValueError):
            pass

    upload_dir = os.path.join(STATE_DIR, slot, "outbound_uploads")
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename or "upload").replace("..", "_")
    temp_path = os.path.join(upload_dir, f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{safe_name}")

    total = 0
    try:
        with open(temp_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > OUTBOUND_UPLOAD_MAX_BYTES:
                    raise ValueError("Attachment too large (max 25 MB)")
                out.write(chunk)
    except Exception as e:
        try:
            if os.path.isfile(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        return {"status": "error", "message": str(e)}

    try:
        from messaging.message_router import message_router
        from services.crm_service import enrich_conversation, get_lead

        result = await message_router.enqueue_dm_send_media(
            slot,
            int(user_id),
            temp_path,
            caption=str(caption or ""),
            filename=safe_name,
            content_type=file.content_type or "",
            wait=True,
            sent_by="manual",
            operator_name=operator_name,
            reply_to_message_id=reply_to_id,
        )
        conv = result.get("conversation") or {}
        uid = int(user_id)
        summary = enrich_conversation(
            slot,
            {
                "user_id": uid,
                "username": conv.get("username") or "",
                "name": conv.get("name") or "",
                "last_message": conv.get("last_message") or "",
                "last_message_at": conv.get("last_message_at"),
                "unread_count": conv.get("unread_count") or 0,
            },
        )
        lead = get_lead(slot, uid)
        return {
            "status": "ok",
            "message": result.get("message"),
            "conversation": summary,
            "lead": lead,
        }
    except Exception as e:
        try:
            if os.path.isfile(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        return {"status": "error", "message": str(e)}
@router.post("/inbox/{slot}/ai-reply")
@router.post("/inbox/{slot}/ai-suggestion")
async def inbox_ai_suggestion(slot: str, body: dict):
    """Generate an AI draft reply for the latest inbound message — but DO
    NOT send it. The frontend fills the reply composer with the draft so
    the operator can review, edit, and click Send themselves.

    Both `/ai-reply` and `/ai-suggestion` route here; `/ai-reply` is kept
    as an alias so older clients keep working — they too will now only
    get a suggestion back, never an automatic send.

    Response shape:
        {
          "status": "ok",
          "text":   "<draft>",
          "stage":  "...",
          "confidence": 0.82,
          "ai": True
        }
    """
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    user_id = body.get("user_id")
    if user_id is None:
        return {"status": "error", "message": "user_id required"}
    from core import ai_smart_reply
    from core.dm_store import load_inbox

    conv = (load_inbox(slot).get("conversations") or {}).get(str(int(user_id))) or {}
    msgs = list(conv.get("messages") or [])
    last_in = next((m for m in reversed(msgs) if m.get("direction") == "in"), None)
    if not last_in:
        return {"status": "error", "message": "No inbound message in this chat"}
    if not ai_smart_reply.is_enabled():
        return {"status": "error", "message": "AI smart-reply is disabled or API key missing"}

    res = await ai_smart_reply.generate_suggestion(
        slot,
        int(user_id),
        user_message_id=last_in.get("id"),
        user_text=last_in.get("text") or "",
    )
    if not res.get("ok"):
        return {"status": "error", "message": res.get("error") or res.get("reason") or "ai_failed", **res}
    return {"status": "ok", **res}
@router.post("/inbox/{slot}/send-location")
async def inbox_send_location(slot: str, body: dict):
    """Send a geo location pin to a DM recipient from the given account slot.

    Body: { user_id: int, latitude: float, longitude: float, accuracy?: float }
    """
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    user_id = body.get("user_id")
    latitude = body.get("latitude")
    longitude = body.get("longitude")
    accuracy = body.get("accuracy")
    if user_id is None:
        return {"status": "error", "message": "user_id required"}
    if latitude is None or longitude is None:
        return {"status": "error", "message": "latitude and longitude required"}
    try:
        from messaging.message_router import message_router

        result = await message_router.enqueue_dm_send_location(
            slot,
            int(user_id),
            float(latitude),
            float(longitude),
            accuracy=float(accuracy) if accuracy is not None else None,
            wait=True,
        )
        from services.crm_service import enrich_conversation, get_lead

        conv = result.get("conversation") or {}
        uid = int(user_id)
        summary = enrich_conversation(
            slot,
            {
                "user_id": uid,
                "username": conv.get("username") or "",
                "name": conv.get("name") or "",
                "last_message": conv.get("last_message") or "",
                "last_message_at": conv.get("last_message_at"),
                "unread_count": conv.get("unread_count") or 0,
            },
        )
        lead = get_lead(slot, uid)
        return {
            "status": "ok",
            "message": result.get("message"),
            "conversation": summary,
            "lead": lead,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
@router.patch("/inbox/{slot}/messages/{user_id}/{message_id}")
async def inbox_edit_message(slot: str, user_id: int, message_id: int, body: dict):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    text = body.get("text") or body.get("message") or ""
    if not str(text).strip():
        return {"status": "error", "message": "text required"}
    try:
        from services import dm_inbox_service

        result = await dm_inbox_service.run_dm_edit(
            slot, int(user_id), int(message_id), str(text),
        )
        return {
            "status": "ok",
            "message": result.get("message"),
            "conversation": result.get("conversation"),
            "unchanged": bool(result.get("unchanged")),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
@router.delete("/inbox/{slot}/messages/{user_id}/{message_id}")
async def inbox_delete_message(slot: str, user_id: int, message_id: int):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    try:
        from services import dm_inbox_service

        result = await dm_inbox_service.run_dm_delete_message(
            slot, int(user_id), int(message_id),
        )
        return {
            "status": "ok",
            "message_id": result.get("message_id"),
            "conversation": result.get("conversation"),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
@router.post("/inbox/{slot}/read/{user_id}")
async def inbox_mark_read(slot: str, user_id: int):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services import crm_service, dm_inbox_service

    uid = int(user_id)
    await dm_inbox_service.mark_read(slot, uid)
    lead = crm_service.get_lead(slot, uid)
    return {
        "status": "ok",
        "slot": slot,
        "user_id": uid,
        "lead": lead,
        "crm": crm_service.build_crm_payload() if lead else None,
    }
@router.get("/inbox/delete-config")
async def inbox_delete_config():
    """Whether chat delete requires INBOX_DELETE_PASSWORD on the server."""
    pwd = (os.environ.get("INBOX_DELETE_PASSWORD") or "").strip()
    return {"status": "ok", "requires_password": bool(pwd)}
@router.delete("/inbox/{slot}/conversation/{user_id}")
async def inbox_delete_conversation(
    slot: str,
    user_id: int,
    body: dict | None = Body(default=None),
):
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    expected = (os.environ.get("INBOX_DELETE_PASSWORD") or "").strip()
    if expected:
        got = ""
        if isinstance(body, dict):
            got = str(body.get("password") or "").strip()
        if got != expected:
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="Incorrect delete password")
    from services import dm_inbox_service

    result = await dm_inbox_service.delete_conversation(slot, int(user_id))
    if result.get("status") != "ok":
        return result
    from services import call_service

    try:
        await broadcast.broadcast({
            "type": "crm",
            "event": "lead_deleted",
            "slot": slot,
            "user_id": int(user_id),
            "crm": call_service.build_crm_payload(),
        })
    except Exception:
        pass
    return result
@router.post("/inbox/{slot}/karthik/block-spam/{user_id}")
async def inbox_karthik_block_spam(slot: str, user_id: int):
    """Block the open chat as spam (Karthik guard / operator)."""
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from services import crm_service
    from services.spam_guard_service import block_chat_as_spam

    result = await block_chat_as_spam(slot, int(user_id))
    return {"status": "ok", "crm": crm_service.build_crm_payload(), **result}
@router.get("/inbox/{slot}/karthik/spam-check/{user_id}")
async def inbox_karthik_spam_check(slot: str, user_id: int):
    """Classify whether a stored thread looks like inbound spam."""
    if slot not in ACCOUNTS:
        return {"status": "error", "message": "Invalid slot"}
    from core.dm_store import load_inbox
    from services.spam_guard_service import classify_conversation_spam

    conv = (load_inbox(slot).get("conversations") or {}).get(str(int(user_id))) or {}
    verdict = classify_conversation_spam(slot, conv)
    return {"status": "ok", "slot": slot, "user_id": int(user_id), **verdict}
