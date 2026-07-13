"""Read-only Daily AI Briefing built from approved TeleAutomation services."""

from __future__ import annotations

import json
import os
import threading
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from core.config import DATA_DIR

TIMEZONE = os.getenv("DAILY_BRIEFING_TIMEZONE", "Asia/Kolkata")
GENERATION_TIME = os.getenv("DAILY_BRIEFING_TIME", "08:00")
STALE_DAYS = max(1, int(os.getenv("DAILY_BRIEFING_STALE_DAYS", "2")))
ENABLED = os.getenv("DAILY_BRIEFING_ENABLED", "1").strip().lower() not in {"0", "false", "off"}
_FILE = Path(DATA_DIR) / "daily_briefings.json"
_LOCK = threading.Lock()


def _now() -> datetime:
    try:
        return datetime.now(ZoneInfo(TIMEZONE))
    except Exception:
        return datetime.now(ZoneInfo("Asia/Kolkata"))


def _scope(reference: str | None) -> str:
    return (reference or "all").strip().lower() or "all"


def _load_cache() -> dict[str, Any]:
    with _LOCK:
        try:
            return json.loads(_FILE.read_text(encoding="utf-8")) if _FILE.exists() else {"briefings": {}}
        except (OSError, json.JSONDecodeError):
            return {"briefings": {}}


def _save_cache(data: dict[str, Any]) -> None:
    with _LOCK:
        _FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(_FILE)


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _record(row: dict, *, kind: str, detail: str) -> dict:
    return {
        "type": kind,
        "id": row.get("id") or row.get("user_id") or "",
        "name": row.get("name") or row.get("candidate_name") or row.get("username") or "Unknown",
        "detail": detail,
    }


def _fallback_summary(metrics: dict[str, int], recommendations: list[str]) -> dict[str, str]:
    def noun(count: int, singular: str, plural: str | None = None) -> str:
        return singular if count == 1 else (plural or singular + "s")
    overview = (
        f"Today: {metrics['interviews_today']} {noun(metrics['interviews_today'], 'interview')}, "
        f"{metrics['pending_attendance']} pending attendance {noun(metrics['pending_attendance'], 'update')}, "
        f"{metrics['payments_due']} {noun(metrics['payments_due'], 'payment')} due, "
        f"{metrics['followups_due']} follow-{noun(metrics['followups_due'], 'up')} pending, and "
        f"{metrics['missing_resumes']} {noun(metrics['missing_resumes'], 'candidate')} missing a resume."
    )
    attention = (
        f"{metrics['important_cancellations']} important {noun(metrics['important_cancellations'], 'cancellation')} and "
        f"{metrics['stale_leads']} stale {noun(metrics['stale_leads'], 'lead')} require review."
    )
    if not any(metrics.values()):
        overview = "All clear for today."
        attention = "No interviews, overdue payments, pending follow-ups or urgent operational items were found."
    return {
        "overview": overview,
        "attention": attention,
        "recommended": " ".join(recommendations) if recommendations else "Review upcoming activities or continue monitoring new leads.",
    }


def _ai_summary(metrics: dict[str, int], fallback: dict[str, str]) -> tuple[dict[str, str], str]:
    prompt = (
        "Summarize only this approved JSON as concise TeleAutomation operations text. "
        "Return JSON with overview, attention, recommended. Never invent names, counts, dates, or actions. "
        f"DATA={json.dumps(metrics, separators=(',', ':'))}"
    )
    try:
        payload = json.dumps({
            "model": os.getenv("OLLAMA_REASONING_MODEL", "qwen2.5:7b"),
            "stream": False,
            "format": "json",
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            f"{os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')}/api/chat",
            data=payload, headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=float(os.getenv("DAILY_BRIEFING_AI_TIMEOUT", "12"))) as response:
            body = json.loads(response.read().decode())
        parsed = json.loads(body.get("message", {}).get("content", "{}"))
        if all(isinstance(parsed.get(key), str) and parsed[key].strip() for key in ("overview", "attention", "recommended")):
            return {key: parsed[key].strip() for key in ("overview", "attention", "recommended")}, "ollama"
    except Exception:
        pass
    return fallback, "deterministic"


def calculate(*, reference: str | None = None, use_ai: bool = True) -> dict[str, Any]:
    from core.crm_store import CRM_INACTIVE_STATUSES, list_leads
    from features import candidate_store

    now = _now()
    day = now.date().isoformat()
    candidates = candidate_store.list_candidates(stage="in_progress", reference=reference)
    roster = candidate_store.daily_interview_roster(day, viewer_reference=reference)["interviews"]
    awaiting = candidate_store.interview_upcoming(
        days=1, lookback_days=30, phase="awaiting_status", viewer_reference=reference,
    )["interviews"]
    pending_works = candidate_store.pending_works(reference=reference)
    missing_resume_records = [w for w in pending_works["works"] if w.get("kind") == "missing_resume"]
    payment_rows = [r for r in candidates if int(r.get("balance_due") or 0) > 0]

    leads = []
    for key, raw in list_leads().items():
        lead = dict(raw)
        lead.setdefault("id", key)
        if reference and str(lead.get("reference") or "").strip().lower() != reference.strip().lower():
            # CRM account IDs are Telegram accounts, not handler references; authorization is enforced by the endpoint.
            pass
        if str(lead.get("status") or "").lower() not in CRM_INACTIVE_STATUSES:
            leads.append(lead)
    now_utc = now.astimezone(timezone.utc)
    followups = [lead for lead in leads if (dt := _parse_dt(lead.get("reminder_timestamp"))) and dt <= now_utc]
    stale_cutoff = now_utc - timedelta(days=STALE_DAYS)
    stale = []
    for lead in leads:
        dt = _parse_dt(lead.get("last_reply_at") or lead.get("last_contact_time") or lead.get("created_at"))
        if dt and dt < stale_cutoff:
            stale.append(lead)
    cancellations = [r for r in roster if candidate_store.row_interview_attendance_status(r) == "cancelled"]

    metrics = {
        "interviews_today": len(roster),
        "pending_attendance": len(awaiting),
        "payments_due": len(payment_rows),
        "missing_resumes": len(missing_resume_records),
        "followups_due": len(followups),
        "stale_leads": len(stale),
        "important_cancellations": len(cancellations),
    }
    recommendations = []
    if awaiting:
        recommendations.append(f"Confirm attendance for {len(awaiting)} completed interview slot(s).")
    if payment_rows:
        recommendations.append(f"Review {len(payment_rows)} overdue payment(s).")
    if followups:
        recommendations.append(f"Contact {len(followups)} lead(s) waiting for follow-up.")
    if missing_resume_records:
        recommendations.append(f"Collect {len(missing_resume_records)} missing resume(s).")
    if stale:
        recommendations.append(f"Re-engage {len(stale)} stale lead(s).")
    if cancellations:
        recommendations.append(f"Review {len(cancellations)} cancellation(s) recorded today.")

    fallback = _fallback_summary(metrics, recommendations)
    summary, provider = _ai_summary(metrics, fallback) if use_ai else (fallback, "deterministic")
    records = {
        "interviews_today": [_record(r, kind="interview", detail=f"{r.get('time') or 'Time missing'} · {r.get('technology') or 'Technology missing'} · {candidate_store.row_interview_attendance_status(r) or 'pending'}") for r in roster],
        "pending_attendance": [_record(r, kind="interview", detail=f"{r.get('date')} · {r.get('time') or 'Time missing'}") for r in awaiting],
        "payments_due": [_record(r, kind="candidate", detail=f"₹{int(r.get('balance_due') or 0):,} due") for r in payment_rows],
        "missing_resumes": [_record(w, kind="candidate", detail=w.get("technology") or "Resume unavailable") for w in missing_resume_records],
        "followups_due": [_record(r, kind="lead", detail="Follow-up due") for r in followups],
        "stale_leads": [_record(r, kind="lead", detail=f"No recent activity for more than {STALE_DAYS} days") for r in stale],
        "important_cancellations": [_record(r, kind="interview", detail=f"Cancelled · {r.get('time') or 'Time missing'}") for r in cancellations],
    }
    generated = now.isoformat()
    return {
        "date": day, "timezone": TIMEZONE, "scope": _scope(reference), "metrics": metrics,
        "summary": summary, "recommendations": recommendations, "records": records,
        "generated_at": generated, "updated_at": generated, "ai_provider": provider,
        "read_only": True, "stale_lead_threshold_days": STALE_DAYS,
    }


def get_briefing(*, reference: str | None = None, refresh: bool = False, use_ai: bool = True) -> dict[str, Any]:
    key = f"{_now().date().isoformat()}:{_scope(reference)}"
    data = _load_cache()
    if not refresh and key in data.get("briefings", {}):
        return data["briefings"][key]
    briefing = calculate(reference=reference, use_ai=use_ai)
    data.setdefault("briefings", {})[key] = briefing
    # Bound persistence to the most recent 45 scope-days.
    data["briefings"] = dict(sorted(data["briefings"].items(), reverse=True)[:45])
    _save_cache(data)
    return briefing


async def scheduler_loop() -> None:
    """Backend-owned daily generator; no browser needs to remain open."""
    import asyncio

    while True:
        try:
            now = _now()
            hour, minute = (int(x) for x in GENERATION_TIME.split(":", 1))
            if ENABLED and (now.hour, now.minute) >= (hour, minute):
                get_briefing(refresh=False)
        except Exception:
            pass
        await asyncio.sleep(60)
