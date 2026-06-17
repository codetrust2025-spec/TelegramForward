"""Unified lead graph — links Telegram DMs, Karthik AI, CRM, and Candidates.

One logical lead is keyed by ``slot:user_id``. This module keeps AI
qualification and stage in sync with CRM, and creates candidate drafts
when a lead converts.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from core.ai_smart_reply_store import (
    STAGE_CTA,
    STAGE_QUALIFY,
    STAGE_VALUE,
    get_lead_state,
)
from core.crm_store import CRM_INACTIVE_STATUSES, get_lead, upsert_lead

STAGE_TO_CRM_STATUS = {
    STAGE_QUALIFY: "interested",
    STAGE_VALUE: "interested",
    STAGE_CTA: "follow_up",
}

CRM_STATUS_RANK = {
    "new": 0,
    "interested": 1,
    "follow_up": 2,
    "converted": 3,
    "not_interested": 90,
    "spam": 91,
}

QUAL_LABELS = {
    "tech_stack": "Tech",
    "experience": "Experience",
    "service_need": "Service",
    "urgency": "Urgency",
    "round_type": "Round",
    "interview_timing": "Interview",
    "domain": "Domain",
    "location": "Location",
    "phone": "Phone",
    "deferral": "Follow-up",
}

KARTHIK_NOTE_PREFIX = "[Karthik]"


def lead_key(slot: str, user_id: int) -> str:
    return f"{slot}:{int(user_id)}"


def _qual_hash(qual: dict) -> str:
    items = sorted(
        (k, str(v))
        for k, v in (qual or {}).items()
        if v not in (None, "", "unknown")
    )
    if not items:
        return ""
    return hashlib.md5(repr(items).encode()).hexdigest()[:12]


def format_qualification_summary(qual: dict | None) -> str:
    parts: list[str] = []
    for key, label in QUAL_LABELS.items():
        val = (qual or {}).get(key)
        if val not in (None, "", "unknown"):
            parts.append(f"{label}: {val}")
    return " | ".join(parts)


def _notes_with_karthik_line(existing_notes: str, line: str) -> str:
    kept = [
        row
        for row in (existing_notes or "").split("\n")
        if not row.strip().startswith(KARTHIK_NOTE_PREFIX)
    ]
    kept.append(f"{KARTHIK_NOTE_PREFIX} {line}")
    return "\n".join(row for row in kept if row is not None).strip()


def sync_ai_to_crm(
    slot: str,
    user_id: int,
    *,
    stage: str | None = None,
    qualification: dict | None = None,
) -> dict | None:
    """Push Karthik stage/facts into CRM (upgrade-only for status)."""
    lead = get_lead(slot, user_id)
    if not lead:
        lead = upsert_lead(slot, int(user_id))

    status = lead.get("status") or "new"
    if status in CRM_INACTIVE_STATUSES:
        return lead

    patch: dict = {}
    graph = dict(lead.get("graph") or {})

    if stage and stage in STAGE_TO_CRM_STATUS:
        target = STAGE_TO_CRM_STATUS[stage]
        current_rank = CRM_STATUS_RANK.get(status, 0)
        target_rank = CRM_STATUS_RANK.get(target, 0)
        if target_rank > current_rank:
            patch["status"] = target

    qual = dict(qualification or {})
    if qual:
        new_hash = _qual_hash(qual)
        if new_hash and new_hash != graph.get("qual_hash"):
            summary = format_qualification_summary(qual)
            if summary:
                patch["notes"] = _notes_with_karthik_line(lead.get("notes") or "", summary)
                graph["qual_hash"] = new_hash
                graph["last_qualification"] = qual
        phone = str(qual.get("phone") or "").strip()
        if phone:
            try:
                from core.contact_link_store import link_phone

                link_phone(slot, int(user_id), phone, linked_by="auto")
            except Exception:
                pass

    if stage:
        graph["ai_stage"] = stage

    if graph != dict(lead.get("graph") or {}):
        patch["graph"] = graph

    if not patch:
        return lead

    return upsert_lead(slot, int(user_id), **patch)


def _mine_phone_from_history(slot: str, user_id: int) -> str:
    from core.dm_store import load_inbox

    conv = (load_inbox(slot).get("conversations") or {}).get(str(int(user_id))) or {}
    blob = " ".join(
        (m.get("text") or m.get("content") or "")
        for m in (conv.get("messages") or [])
        if m.get("direction") == "in"
    )
    match = re.search(r"(?:\+91|91)?[\s-]?([6-9]\d{9})", blob)
    return match.group(1) if match else ""


def _lead_display_name(slot: str, user_id: int, lead: dict) -> str:
    name = (lead.get("name") or "").strip()
    if name:
        return name
    from core.dm_store import list_conversations

    for conv in list_conversations(slot):
        if int(conv.get("user_id") or 0) == int(user_id):
            return (
                (conv.get("name") or conv.get("username") or str(user_id)).strip()
            )
    return str(user_id)


def build_candidate_draft(slot: str, user_id: int) -> dict:
    """Build a candidate row from unified lead data."""
    lead = get_lead(slot, user_id) or {}
    ai = get_lead_state(slot, user_id)
    qual = dict(ai.get("qualification") or {})

    name = _lead_display_name(slot, user_id, lead)
    phone = str(qual.get("phone") or "").strip() or _mine_phone_from_history(slot, user_id)
    tech = str(qual.get("tech_stack") or qual.get("domain") or "").strip()
    service = str(qual.get("service_need") or "").strip()

    notes_parts = [f"Telegram lead {slot}:{user_id}"]
    if service:
        notes_parts.append(f"Service: {service}")
    summary = format_qualification_summary(qual)
    if summary:
        notes_parts.append(summary)
    operator_notes = (lead.get("notes") or "").strip()
    if operator_notes:
        notes_parts.append(operator_notes)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "name": name,
        "technology": tech,
        "phone": phone,
        "reference": str(lead.get("handler_reference") or "").strip(),
        "notes": "\n".join(notes_parts),
        "stage": "in_progress",
        "task": "not_started",
        "date": today,
        "telegram_slot": slot,
        "telegram_user_id": int(user_id),
    }


def create_candidate_from_lead(
    slot: str,
    user_id: int,
    *,
    handler_reference: str | None = None,
) -> dict:
    """Create or return the candidate linked to this Telegram lead."""
    from features import candidate_store

    lead = get_lead(slot, user_id) or {}
    cid = lead.get("candidate_id") or (lead.get("graph") or {}).get("candidate_id")
    if cid:
        existing = candidate_store.get_candidate(str(cid))
        if existing:
            return {"ok": True, "created": False, "candidate": existing}

    existing = candidate_store.find_by_telegram(slot, user_id)
    if existing:
        graph = dict(lead.get("graph") or {})
        graph["candidate_id"] = existing["id"]
        upsert_lead(slot, int(user_id), candidate_id=existing["id"], graph=graph)
        return {"ok": True, "created": False, "candidate": existing}

    draft = build_candidate_draft(slot, user_id)
    if not (draft.get("name") or "").strip():
        return {"ok": False, "reason": "no_name"}
    ref = (handler_reference or "").strip()
    if ref:
        draft["reference"] = ref

    row = candidate_store.create_candidate(draft)
    graph = dict(lead.get("graph") or {})
    graph["candidate_id"] = row["id"]
    upsert_lead(slot, int(user_id), candidate_id=row["id"], graph=graph)
    return {"ok": True, "created": True, "candidate": row}


def on_crm_status_changed(
    slot: str,
    user_id: int,
    old_status: str | None,
    new_status: str | None,
) -> dict | None:
    """React to CRM status transitions."""
    if new_status == "converted" and old_status != "converted":
        return create_candidate_from_lead(slot, user_id)
    return None


def get_unified_graph(slot: str, user_id: int) -> dict:
    """Merged view for API + dashboard."""
    from features import candidate_store

    lead = get_lead(slot, user_id) or {}
    ai = get_lead_state(slot, user_id)
    qual = dict(ai.get("qualification") or graph_qualification(lead))

    candidate = None
    cid = lead.get("candidate_id") or (lead.get("graph") or {}).get("candidate_id")
    if cid:
        candidate = candidate_store.get_candidate(str(cid))
    if not candidate:
        candidate = candidate_store.find_by_telegram(slot, user_id)

    return {
        "key": lead_key(slot, user_id),
        "slot": slot,
        "user_id": int(user_id),
        "ai_stage": ai.get("stage") or (lead.get("graph") or {}).get("ai_stage"),
        "qualification": qual,
        "qualification_summary": format_qualification_summary(qual),
        "escalated": bool(ai.get("escalated")),
        "crm_status": lead.get("status") or "new",
        "candidate_id": (candidate or {}).get("id") or cid,
        "candidate": candidate,
    }


def graph_qualification(lead: dict) -> dict:
    graph = lead.get("graph") or {}
    stored = graph.get("last_qualification")
    return dict(stored) if isinstance(stored, dict) else {}
