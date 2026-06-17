"""Notify team when a slot is booked via submit-slot (web push + optional WhatsApp)."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _slot_summary(row: dict) -> str:
    name = (row.get("name") or "Candidate").strip()
    day = (row.get("date") or "")[:10]
    start = (row.get("time") or "").strip()[:5]
    end = (row.get("time_end") or "").strip()[:5]
    tech = (row.get("technology") or "").strip()
    rnd = (row.get("interview_round") or "").strip()
    parts = [name]
    if day and start:
        parts.append(f"{day} {start}" + (f"–{end}" if end else ""))
    if rnd:
        parts.append(rnd)
    if tech and tech not in {"", "Unspecified"}:
        parts.append(tech)
    return " · ".join(parts)


def _wa_group_message(row: dict) -> str:
    """Copy-paste friendly line for the Interview slots WhatsApp group."""
    name = (row.get("name") or "Candidate").strip()
    day = (row.get("date") or "")[:10]
    start = (row.get("time") or "").strip()[:5]
    end = (row.get("time_end") or "").strip()[:5]
    tech = (row.get("technology") or "").strip()
    rnd = (row.get("interview_round") or "").strip()
    lines = [f"📅 Interview slot — {name}"]
    if day and start:
        slot = f"{day} {start}"
        if end:
            slot += f" – {end}"
        lines.append(slot)
    if rnd:
        lines.append(f"Round: {rnd}")
    if tech and tech not in {"", "Unspecified"}:
        lines.append(f"Tech: {tech}")
    lines.append("(booked via teleautomation.online/submit-slot)")
    return "\n".join(lines)


async def notify_slot_booked(row: dict, *, action: str = "assigned") -> None:
    if action in {"skip_exists"}:
        return
    summary = _slot_summary(row)
    title = "Interview slot booked"
    body = summary
    wa_text = _wa_group_message(row)

    def _push() -> None:
        from features import web_push

        users = web_push.all_usernames_with_subscriptions()
        tag = f"slot:{row.get('id') or summary}"
        for user in users:
            web_push.send_to_user(
                user,
                title=title,
                body=body,
                tag=tag,
            )

    await asyncio.to_thread(_push)

    phones_raw = os.environ.get("WHATSAPP_SLOTS_NOTIFY_PHONES", "").strip()
    if not phones_raw:
        return
    from core.config import is_whatsapp_enabled

    if not is_whatsapp_enabled():
        return
    phones = [p.strip() for p in phones_raw.split(",") if p.strip()]
    if not phones:
        return
    try:
        from core.config import WHATSAPP_DEFAULT_SLOT
        from services.whatsapp_bsp import get_bsp_client

        client = get_bsp_client()
        if client is None or not client.configured:
            return
        for phone in phones:
            await client.send_text(phone, wa_text)
    except Exception as exc:
        logger.debug("WhatsApp slot notify failed: %s", exc)


def format_slot_reminder(row: dict, *, minutes: int = 30) -> tuple[str, str]:
    name = (row.get("name") or "Candidate").strip()
    start = (row.get("time") or "").strip()[:5]
    title = f"Interview in {minutes} min — {name}"
    body = f"{(row.get('date') or '')[:10]} {start} · {(row.get('technology') or '').strip() or 'Interview'}"
    return title, body
