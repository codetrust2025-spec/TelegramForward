"""T-30min web push reminders for confirmed interview slots."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timedelta

from core.config import DATA_DIR
from core.ist_time import IST, ist_now

logger = logging.getLogger(__name__)

_SENT_PATH = os.path.join(DATA_DIR, "interview_reminders_sent.json")
_lock = threading.Lock()
REMINDER_MINUTES = 30
CHECK_INTERVAL_SEC = 300


def _load_sent() -> set[str]:
    if not os.path.isfile(_SENT_PATH):
        return set()
    try:
        with open(_SENT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(str(x) for x in data)
    except Exception:
        pass
    return set()


def _save_sent(keys: set[str]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    trimmed = sorted(keys)[-500:]
    tmp = _SENT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, indent=2)
    os.replace(tmp, _SENT_PATH)


def _slot_start_dt(row: dict) -> datetime | None:
    day = (row.get("date") or "").strip()[:10]
    start = (row.get("time") or "").strip()[:5]
    if len(day) != 10 or len(start) < 4:
        return None
    try:
        y, m, d = int(day[:4]), int(day[5:7]), int(day[8:10])
        sh, sm = map(int, start.split(":")[:2])
    except ValueError:
        return None
    return datetime(y, m, d, sh, sm, tzinfo=IST)


def _reminder_key(row: dict) -> str:
    cid = str(row.get("id") or "")
    day = (row.get("date") or "")[:10]
    start = (row.get("time") or "").strip()[:5]
    return f"{cid}:{day}:{start}"


def run_reminder_tick(*, minutes: int = REMINDER_MINUTES) -> int:
    from features import candidate_store as cs
    from features import web_push
    from services.slot_booking_notify import format_slot_reminder

    if not web_push.vapid_keys():
        return 0
    now = ist_now()
    window_start = now + timedelta(minutes=minutes - 5)
    window_end = now + timedelta(minutes=minutes + 5)
    snap = cs.interview_upcoming(days=2, phase="scheduled")
    rows = snap.get("interviews") or []
    sent = _load_sent()
    fired = 0
    users = web_push.all_usernames_with_subscriptions()
    if not users:
        return 0
    for row in rows:
        start_dt = _slot_start_dt(row)
        if start_dt is None:
            continue
        if not (window_start <= start_dt <= window_end):
            continue
        key = _reminder_key(row)
        if key in sent:
            continue
        title, body = format_slot_reminder(row, minutes=minutes)
        tag = f"interview-reminder:{key}"
        for user in users:
            web_push.send_to_user(user, title=title, body=body, tag=tag)
        sent.add(key)
        fired += 1
    if fired:
        with _lock:
            _save_sent(sent)
    return fired


async def interview_reminder_loop() -> None:
    await asyncio.sleep(45.0)
    while True:
        try:
            n = await asyncio.to_thread(run_reminder_tick)
            if n:
                logger.info("Interview reminders sent: %d", n)
        except Exception as exc:
            logger.debug("interview reminder tick: %s", exc)
        await asyncio.sleep(CHECK_INTERVAL_SEC)


def start_interview_reminder_loop() -> None:
    if os.environ.get("INTERVIEW_REMINDERS_ENABLED", "1").strip().lower() in ("0", "false", "no"):
        return
    asyncio.create_task(interview_reminder_loop())
