from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError, ChatWriteForbiddenError, UserBannedInChannelError,
    UsernameNotOccupiedError, UsernameInvalidError, ChannelPrivateError,
    ChatRestrictedError,
)
from telethon.tl.functions.channels import JoinChannelRequest
import asyncio
import json
import os
from typing import List, Dict

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Constants ─────────────────────────────────────────────────────────────────

API_ID   = REMOVED_TELEGRAM_API_ID
API_HASH = 'REMOVED_TELEGRAM_API_HASH'
MESSAGE_FILE = 'custom_message.txt'
GROUPS_FILE  = 'groups_list.json'

ACCOUNTS = {
    "account1": "session_account1",
    "account2": "session_account2",
}

DEFAULT_MESSAGE = """🚀 IT Career Support | Java | React | Python | Power BI | Salesforce & more

Struggling to crack interviews or switch tech domains? We've got you covered.

Services:
• End-to-end Interview Support (till you get the job)
• ATS-friendly Resume Building
• Real-time Work & Project Support
• MNC-level Interview Prep

DM or WhatsApp: 9000000001
(Serious candidates only)"""

# ── File helpers ──────────────────────────────────────────────────────────────

def load_groups() -> list:
    if os.path.exists(GROUPS_FILE):
        try:
            with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    return data
        except Exception:
            pass
    return []

def save_groups(groups: list):
    with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(groups, f, indent=2)

def load_custom_message() -> str:
    if os.path.exists(MESSAGE_FILE):
        try:
            with open(MESSAGE_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            pass
    return DEFAULT_MESSAGE

def save_custom_message(text: str):
    with open(MESSAGE_FILE, 'w', encoding='utf-8') as f:
        f.write(text)

# ── Runtime state ─────────────────────────────────────────────────────────────

TARGET_GROUPS: list = load_groups()

# Permanently dead groups — never retried
invalid_groups: set = {'AiredTech', 'etl_test'}
blocked_groups: set = {'SAP_USA_job', 'hireweb3', 'rahulshettyacademy',
                       'sapremotejobs', 'web_dev_support', 'awsazurelearners'}

# Per-account runtime state
account_state: Dict[str, dict] = {
    "account1": {
        "running": False, "cycle": 0, "success": 0, "failed": 0,
        "current_group": "", "success_list": [], "failed_list": [],
        "logs": [], "active_groups": 0, "status": "idle",
        "my_groups": [], "next_cycle_in": 0,
    },
    "account2": {
        "running": False, "cycle": 0, "success": 0, "failed": 0,
        "current_group": "", "success_list": [], "failed_list": [],
        "logs": [], "active_groups": 0, "status": "idle",
        "my_groups": [], "next_cycle_in": 0,
    },
}

# Shared UI state (combined view)
forwarding_state = {
    "running": False,
    "total": len(TARGET_GROUPS),
    "success": 0, "failed": 0,
    "current_group": "",
    "success_list": [], "failed_list": [],
    "logs": [],
    "message_id": None,
    "cycle": 0,
    "active_groups": 0,
    "active_account": None,
    "account_info": {},
    "custom_message": load_custom_message(),
    "account_states": account_state,
}

telegram_clients = {"account1": None, "account2": None}
login_state = {"phone": None, "phone_code_hash": None, "slot": None}
active_connections: List[WebSocket] = []

# ── Broadcast helpers ─────────────────────────────────────────────────────────

async def broadcast(data: dict):
    dead = []
    for ws in active_connections:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in active_connections:
            active_connections.remove(ws)

async def log_global(msg: str, level: str = "info"):
    entry = {"msg": msg, "level": level}
    forwarding_state["logs"].append(entry)
    if len(forwarding_state["logs"]) > 1000:
        forwarding_state["logs"] = forwarding_state["logs"][-1000:]
    await broadcast({"type": "state", **forwarding_state})

async def log_account(slot: str, msg: str, level: str = "info"):
    """Log to both account-specific and global log."""
    prefixed = f"[{slot}] {msg}"
    entry = {"msg": prefixed, "level": level}
    account_state[slot]["logs"].append(entry)
    if len(account_state[slot]["logs"]) > 500:
        account_state[slot]["logs"] = account_state[slot]["logs"][-500:]
    forwarding_state["logs"].append(entry)
    if len(forwarding_state["logs"]) > 1000:
        forwarding_state["logs"] = forwarding_state["logs"][-1000:]
    await broadcast({"type": "state", **forwarding_state})

# ── Telegram client helpers ───────────────────────────────────────────────────

async def get_or_create_client(slot: str) -> TelegramClient:
    client = telegram_clients.get(slot)
    if client is None or not client.is_connected():
        client = TelegramClient(ACCOUNTS[slot], API_ID, API_HASH)
        await client.connect()
        telegram_clients[slot] = client
    return client

async def refresh_account_info():
    info = {}
    for slot in ACCOUNTS:
        try:
            client = await get_or_create_client(slot)
            if await client.is_user_authorized():
                me = await client.get_me()
                info[slot] = {"name": me.first_name, "phone": me.phone}
            else:
                info[slot] = None
        except Exception:
            info[slot] = None
    forwarding_state["account_info"] = info
    if forwarding_state["active_account"] is None:
        for slot in ["account1", "account2"]:
            if info.get(slot):
                forwarding_state["active_account"] = slot
                break
    await broadcast({"type": "state", **forwarding_state})

# ── Group splitting ───────────────────────────────────────────────────────────

def get_active_slots() -> list:
    """Return list of logged-in account slots."""
    return [s for s in ["account1", "account2"]
            if forwarding_state["account_info"].get(s)]

# ── Smart send ────────────────────────────────────────────────────────────────

async def send_to_group(client, slot: str, group: str, text: str) -> str:
    try:
        await client.send_message(group, text)
        return 'ok'

    except FloodWaitError as e:
        if e.seconds > 60:
            await log_account(slot, f"⚠ FloodWait {group}: {e.seconds}s — skip cycle", "warning")
            return 'flood'
        await log_account(slot, f"⚠ FloodWait {group}: waiting {e.seconds}s...", "warning")
        await asyncio.sleep(e.seconds + 5)
        try:
            await client.send_message(group, text)
            return 'ok'
        except Exception:
            return 'flood'

    except (UsernameNotOccupiedError, UsernameInvalidError):
        return 'invalid'

    except (ChannelPrivateError, UserBannedInChannelError):
        return 'blocked'

    except ChatRestrictedError:
        return 'blocked'

    except ChatWriteForbiddenError:
        await log_account(slot, f"🔗 {group}: not joined — attempting join...", "info")
        try:
            await client(JoinChannelRequest(group))
            await asyncio.sleep(3)
            try:
                await client.send_message(group, text)
                return 'ok'
            except ChatWriteForbiddenError:
                # Joined but still can't write = broadcast channel — log once here
                await log_account(slot, f"🚫 {group}: broadcast channel — removed", "warning")
                return 'blocked'
        except FloodWaitError as e:
            if e.seconds > 60:
                await log_account(slot, f"⚠ FloodWait joining {group}: {e.seconds}s — skip", "warning")
                return 'flood'
            await log_account(slot, f"⚠ FloodWait joining {group}: waiting {e.seconds}s...", "warning")
            await asyncio.sleep(e.seconds + 5)
            try:
                await client(JoinChannelRequest(group))
                await asyncio.sleep(3)
                await client.send_message(group, text)
                return 'ok'
            except Exception:
                return 'flood'
        except (ChannelPrivateError, UserBannedInChannelError):
            return 'blocked'
        except Exception as join_err:
            err = str(join_err).lower()
            if 'private' in err or 'banned' in err:
                return 'blocked'
            if 'requested to join' in err or 'request' in err:
                # Private group requiring admin approval — treat as blocked
                await log_account(slot, f"🚫 {group}: requires admin approval — removed", "warning")
                return 'blocked'
            if "can't write" in err or 'forbidden' in err or 'write' in err:
                # Broadcast channel — nobody can post
                await log_account(slot, f"🚫 {group}: broadcast channel — removed", "warning")
                return 'blocked'
            await log_account(slot, f"✗ {group}: join failed — {join_err}", "error")
            return 'cant_write'

    except Exception as e:
        err = str(e).lower()
        if 'private' in err or 'banned' in err:
            return 'blocked'
        if 'username' in err or 'no user' in err:
            return 'invalid'
        if 'topic_closed' in err or 'restricted' in err or 'discussion' in err:
            return 'blocked'
        await log_account(slot, f"✗ {group}: {e}", "error")
        return 'error'

# ── Per-account forwarding worker ─────────────────────────────────────────────

async def run_account(slot: str, groups: list, msg_text: str, one_shot: bool) -> str:
    """
    Runs one cycle for the given account.
    Returns: 'done' | 'flood_banned' | 'not_logged_in' | 'error'
    """
    global TARGET_GROUPS, invalid_groups, blocked_groups

    st = account_state[slot]
    st.update({
        "running": True, "cycle": 0,
        "current_group": "", "logs": [],
        "active_groups": 0, "status": "starting",
        "my_groups": groups,
        # Keep last cycle's success/failed/lists visible — don't reset here
    })
    await broadcast({"type": "state", **forwarding_state})

    try:
        client = await get_or_create_client(slot)
        if not await client.is_user_authorized():
            await log_account(slot, f"Not logged in — skipping", "error")
            return 'not_logged_in'

        await log_account(slot, f"Connected ✓", "success")

        # Flood-ban check
        try:
            await client.get_messages('telegram', limit=1)
            await log_account(slot, "Account healthy ✓", "success")
        except FloodWaitError as e:
            h, m = e.seconds // 3600, (e.seconds % 3600) // 60
            await log_account(slot, f"⛔ Flood-banned {h}h {m}m — stopping this account", "error")
            st["status"] = "flood_banned"
            return 'flood_banned'

        me = await client.get_me()
        my_id = me.id

        while st["running"]:
            st["cycle"] += 1
            await log_account(slot, f"--- Cycle {st['cycle']} ({len(groups)} groups) ---")

            # Scan: find groups where our message is not last
            needs_send = []
            await log_account(slot, f"Scanning {len(groups)} groups...")
            for group in groups:
                if not st["running"]:
                    break
                try:
                    messages = await client.get_messages(group, limit=1)
                    if messages:
                        sender_id = getattr(messages[0], 'sender_id', None) \
                                    or getattr(messages[0], 'from_id', None)
                        if sender_id != my_id:
                            needs_send.append(group)
                        else:
                            await log_account(slot, f"↷ {group}: our msg is last", "info")
                except Exception:
                    needs_send.append(group)

            st["active_groups"] = len(needs_send)
            await broadcast({"type": "state", **forwarding_state})

            if not needs_send:
                await log_account(slot, "✓ Our message is last in all assigned groups.")
            else:
                await log_account(slot, f"{len(needs_send)} groups need re-send...", "success")
                # Reset stats only when we're about to send — keeps last results visible during wait
                st["success"] = 0
                st["failed"] = 0
                st["success_list"] = []
                st["failed_list"] = []
                cycle_invalid, cycle_blocked = [], []

                for group in needs_send:
                    if not st["running"]:
                        break
                    st["current_group"] = group
                    await broadcast({"type": "state", **forwarding_state})

                    result = await send_to_group(client, slot, group, msg_text)

                    if result == 'ok':
                        st["success"] += 1
                        st["success_list"].append(group)
                        await log_account(slot, f"✓ {group}", "success")

                    elif result == 'invalid':
                        invalid_groups.add(group)
                        cycle_invalid.append(group)
                        groups = [g for g in groups if g != group]
                        TARGET_GROUPS = [g for g in TARGET_GROUPS if g != group]
                        st["failed"] += 1
                        st["failed_list"].append({"group": group, "reason": "Invalid — removed"})
                        await log_account(slot, f"🗑 {group}: invalid — removed", "warning")

                    elif result == 'blocked':
                        blocked_groups.add(group)
                        cycle_blocked.append(group)
                        groups = [g for g in groups if g != group]
                        TARGET_GROUPS = [g for g in TARGET_GROUPS if g != group]
                        st["failed"] += 1
                        st["failed_list"].append({"group": group, "reason": "Blocked — removed"})

                    else:
                        st["failed"] += 1
                        st["failed_list"].append({"group": group, "reason": result})

                    await asyncio.sleep(10)

                # Post-cycle: clean and save
                seen = set()
                merged = []
                for g in TARGET_GROUPS:
                    if g not in invalid_groups and g not in blocked_groups and g not in seen:
                        seen.add(g)
                        merged.append(g)
                TARGET_GROUPS = merged
                forwarding_state["total"] = len(TARGET_GROUPS)
                save_groups(TARGET_GROUPS)

                total = st["success"] + st["failed"]
                rate  = round(st["success"] / total * 100, 1) if total > 0 else 0
                await log_account(
                    slot,
                    f"Cycle {st['cycle']} done — ✓ {st['success']} ✗ {st['failed']} ({rate}%)",
                    "success"
                )

            if one_shot:
                break
            if st["running"]:
                total = st["success"] + st["failed"]
                rate  = round(st["success"] / total * 100, 1) if total > 0 else 0
                await log_account(
                    slot,
                    f"⏳ Waiting 15 min — last cycle: ✓ {st['success']} ✗ {st['failed']} ({rate}%)",
                    "info"
                )
                # Live countdown — broadcasts every 5 seconds
                wait_seconds = 900
                st["next_cycle_in"] = wait_seconds
                await broadcast({"type": "state", **forwarding_state})
                while st["running"] and wait_seconds > 0:
                    await asyncio.sleep(1)
                    wait_seconds -= 1
                    st["next_cycle_in"] = wait_seconds
                    if wait_seconds % 5 == 0:
                        await broadcast({"type": "state", **forwarding_state})
                st["next_cycle_in"] = 0
                await broadcast({"type": "state", **forwarding_state})

        return 'done'

    except Exception as e:
        await log_account(slot, f"Fatal error: {e}", "error")
        return 'error'
    finally:
        st["running"] = False
        st["current_group"] = ""
        st["status"] = "idle"
        # Update global running flag
        forwarding_state["running"] = any(
            account_state[s]["running"] for s in ACCOUNTS
        )
        await broadcast({"type": "state", **forwarding_state})

# ── Rotation forwarding launcher ─────────────────────────────────────────────

async def run_forwarding(one_shot: bool = False):
    """
    Rotation mode: accounts take turns each cycle.
    Cycle 1 → Account 1 sends to ALL groups
    Cycle 2 → Account 2 sends to ALL groups
    Cycle 3 → Account 1 sends to ALL groups
    ...
    If active account is flood-banned → automatically switches to the other.
    If only one account is logged in → it handles every cycle.
    """
    global forwarding_state

    active_slots = get_active_slots()
    if not active_slots:
        await log_global("No logged-in accounts. Please log in first.", "error")
        return

    forwarding_state.update({
        "running": True, "success": 0, "failed": 0,
        "success_list": [], "failed_list": [], "logs": [],
        "current_group": "", "message_id": None, "cycle": 0, "active_groups": 0,
    })
    await broadcast({"type": "state", **forwarding_state})

    msg_text = load_custom_message()
    forwarding_state["custom_message"] = msg_text

    rotation_index = 0  # which slot in active_slots to use next

    await log_global(
        f"Rotation mode started — {len(active_slots)} account(s): "
        f"{', '.join(active_slots)}",
        "success"
    )

    while forwarding_state["running"]:
        # Pick the current account in rotation
        slot = active_slots[rotation_index % len(active_slots)]
        forwarding_state["cycle"] += 1

        await log_global(
            f"=== Cycle {forwarding_state['cycle']} — using {slot} ===",
            "success"
        )

        # Run one cycle with this account
        completed = await run_account(slot, list(TARGET_GROUPS), msg_text, one_shot=True)

        if completed == 'flood_banned':
            # This account is banned — try the other one next cycle immediately
            await log_global(
                f"⚠ {slot} is flood-banned — switching to other account next cycle",
                "warning"
            )
            # Don't advance rotation — try next slot right away
            active_slots_now = get_active_slots()
            if len(active_slots_now) > 1:
                # Move to the other account
                rotation_index = (rotation_index + 1) % len(active_slots)
                await log_global("Switching account — retrying in 1 minute...", "info")
                await asyncio.sleep(60)
            else:
                await log_global("No other account available. Waiting 15 minutes...", "warning")
                await asyncio.sleep(900)
        else:
            # Advance to next account in rotation
            rotation_index = (rotation_index + 1) % len(active_slots)

        if one_shot:
            break

        if forwarding_state["running"]:
            await log_global("Waiting 15 minutes before next cycle...")
            await asyncio.sleep(900)

    forwarding_state["running"] = False
    await broadcast({"type": "state", **forwarding_state})

# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    await websocket.send_json({"type": "state", **forwarding_state})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)

# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    asyncio.create_task(refresh_account_info())

# ── Forwarding control ────────────────────────────────────────────────────────

@app.post("/start")
async def start_forwarding():
    if forwarding_state["running"]:
        return {"status": "already_running"}
    asyncio.create_task(run_forwarding(one_shot=False))
    return {"status": "started"}

@app.post("/start-test")
async def start_test():
    if forwarding_state["running"]:
        return {"status": "already_running"}
    asyncio.create_task(run_forwarding(one_shot=True))
    return {"status": "started"}

@app.post("/stop")
async def stop_forwarding():
    forwarding_state["running"] = False
    for slot in ACCOUNTS:
        account_state[slot]["running"] = False
    await broadcast({"type": "state", **forwarding_state})
    return {"status": "stopped"}

@app.get("/state")
async def get_state():
    return forwarding_state

@app.get("/health")
async def health():
    return {"status": "ok"}

# ── Groups management ─────────────────────────────────────────────────────────

@app.get("/groups")
async def get_groups():
    return {"groups": TARGET_GROUPS, "total": len(TARGET_GROUPS)}

@app.get("/groups/removed")
async def get_removed_groups():
    return {
        "invalid": sorted(invalid_groups),
        "blocked": sorted(blocked_groups),
    }

@app.post("/groups/update")
async def update_groups(payload: dict):
    global TARGET_GROUPS
    raw = payload.get("groups", [])
    uploaded, seen_upload = [], set()
    for g in raw:
        g = str(g).strip().lstrip('@')
        if '/' in g or not g:
            continue
        if g in invalid_groups or g in blocked_groups:
            continue
        if g not in seen_upload:
            seen_upload.add(g)
            uploaded.append(g)
    if not uploaded:
        return {"success": False, "error": "No valid groups found"}
    existing_set = set(TARGET_GROUPS)
    merged = list(TARGET_GROUPS)
    added = 0
    for g in uploaded:
        if g not in existing_set:
            merged.append(g)
            existing_set.add(g)
            added += 1
    TARGET_GROUPS = merged
    save_groups(TARGET_GROUPS)
    forwarding_state["total"] = len(TARGET_GROUPS)
    await broadcast({"type": "state", **forwarding_state})
    return {
        "success": True, "total": len(TARGET_GROUPS),
        "added_new": added,
        "already_existed": len(uploaded) - added,
        "skipped_dead": len(raw) - len(uploaded),
        "groups": TARGET_GROUPS,
    }

# ── Message editor ────────────────────────────────────────────────────────────

@app.get("/message")
async def get_message():
    return {"message": load_custom_message()}

@app.post("/message")
async def update_message(payload: dict):
    text = payload.get("message", "").strip()
    if not text:
        return {"success": False, "error": "Message cannot be empty"}
    save_custom_message(text)
    forwarding_state["custom_message"] = text
    await broadcast({"type": "state", **forwarding_state})
    return {"success": True}

# ── Account management ────────────────────────────────────────────────────────

@app.post("/account/switch")
async def switch_account(payload: dict):
    slot = payload.get("slot")
    if slot not in ACCOUNTS:
        return {"success": False, "error": "Invalid slot"}
    forwarding_state["active_account"] = slot
    await broadcast({"type": "state", **forwarding_state})
    return {"success": True, "active_account": slot}

@app.get("/account/status")
async def account_status():
    await refresh_account_info()
    return {
        "active_account": forwarding_state["active_account"],
        "account_info":   forwarding_state["account_info"],
    }

@app.post("/login/send-otp")
async def send_otp(payload: dict):
    phone = payload.get("phone", "").strip()
    slot  = payload.get("slot", "account1")
    if not phone:
        return {"success": False, "error": "Phone number required"}
    if slot not in ACCOUNTS:
        return {"success": False, "error": "Invalid slot"}
    try:
        existing = telegram_clients.get(slot)
        if existing:
            try:
                await existing.disconnect()
            except Exception:
                pass
        client = TelegramClient(ACCOUNTS[slot], API_ID, API_HASH)
        await client.connect()
        telegram_clients[slot] = client
        result = await client.send_code_request(phone)
        login_state["phone"] = phone
        login_state["phone_code_hash"] = result.phone_code_hash
        login_state["slot"] = slot
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/login/verify-otp")
async def verify_otp(payload: dict):
    code            = payload.get("code", "").strip()
    slot            = login_state.get("slot")
    phone           = login_state.get("phone")
    phone_code_hash = login_state.get("phone_code_hash")
    if not all([code, slot, phone, phone_code_hash]):
        return {"success": False, "error": "Missing login state"}
    try:
        client = telegram_clients[slot]
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        me = await client.get_me()
        forwarding_state["account_info"][slot] = {"name": me.first_name, "phone": me.phone}
        forwarding_state["active_account"] = slot
        await broadcast({"type": "state", **forwarding_state})
        return {"success": True, "name": me.first_name, "phone": me.phone, "slot": slot}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/login/logout")
async def logout(payload: dict = {}):
    slot = payload.get("slot") or forwarding_state.get("active_account")
    if slot not in ACCOUNTS:
        return {"success": False, "error": "Invalid slot"}
    try:
        client = telegram_clients.get(slot)
        if client and client.is_connected():
            await client.log_out()
        session_file = f"{ACCOUNTS[slot]}.session"
        if os.path.exists(session_file):
            os.remove(session_file)
        telegram_clients[slot] = None
        forwarding_state["account_info"][slot] = None
        other = "account2" if slot == "account1" else "account1"
        forwarding_state["active_account"] = other if forwarding_state["account_info"].get(other) else None
        await broadcast({"type": "state", **forwarding_state})
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/login/status")
async def login_status():
    slot = forwarding_state.get("active_account")
    if slot:
        info = forwarding_state["account_info"].get(slot)
        if info:
            return {"logged_in": True, "name": info["name"], "phone": info["phone"], "slot": slot}
    return {"logged_in": False}


# ── Serve frontend (production) ───────────────────────────────────────────────

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.exists(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
