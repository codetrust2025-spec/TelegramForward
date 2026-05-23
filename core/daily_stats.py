"""Aggregate daily / since-reset stats from inbox messages and forward send history."""

from __future__ import annotations

from datetime import datetime, timezone

from core.dm_store import load_inbox
from core.send_stats import count_since_cutoff
from core.stats_reset import get_effective_cutoff, get_reset_at_iso, get_reset_timestamp


def _parse_iso_ts(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        s = str(iso).strip().replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except (TypeError, ValueError):
        return None


def _empty_slot_stats() -> dict:
    return {
        "contacts": 0,
        "incoming": 0,
        "outgoing": 0,
        "forwarded": 0,
    }


def stats_for_inbox_slot(slot: str, cutoff: float) -> dict:
    """DM inbox counts since cutoff (raw messages kept on disk)."""
    contacts: set[int] = set()
    incoming = 0
    outgoing = 0

    data = load_inbox(slot)
    for conv in (data.get("conversations") or {}).values():
        uid = conv.get("user_id")
        for msg in conv.get("messages") or []:
            ts = _parse_iso_ts(msg.get("timestamp"))
            if ts is None or ts < cutoff:
                continue
            direction = msg.get("direction")
            if direction == "in":
                incoming += 1
                if uid is not None:
                    contacts.add(int(uid))
            elif direction == "out":
                st = msg.get("status") or ""
                if st == "sending":
                    continue
                outgoing += 1
                if uid is not None:
                    contacts.add(int(uid))

    forwarded = count_since_cutoff(slot, cutoff)
    return {
        "contacts": len(contacts),
        "incoming": incoming,
        "outgoing": outgoing,
        "forwarded": forwarded,
    }


def _sum_slots(per_slot: dict) -> dict:
    total = _empty_slot_stats()
    for row in per_slot.values():
        for key in total:
            total[key] += int(row.get(key) or 0)
    return total


def compute_daily_stats(slots: list[str]) -> dict:
    reset_ts = get_reset_timestamp()
    per_slot = {
        slot: stats_for_inbox_slot(slot, get_effective_cutoff(slot))
        for slot in slots
    }
    global_stats = _sum_slots(per_slot)
    crm_stats = {}
    try:
        from services.crm_service import compute_crm_stats

        crm_stats = compute_crm_stats()
    except Exception:
        pass

    return {
        "window": "since_reset" if reset_ts else "rolling_24h",
        "reset_timestamp": reset_ts,
        "reset_at": get_reset_at_iso(),
        "cutoff_timestamp": get_effective_cutoff(),
        "global": global_stats,
        "per_account": per_slot,
        "crm": crm_stats,
    }
