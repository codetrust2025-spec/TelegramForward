"""Read-only natural-language access to TeleAutomation operational records."""

from __future__ import annotations

import json
import os
import re
import urllib.request
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

ALLOWED_INTENTS = {
    "pending_payments", "tomorrow_interviews", "today_interviews", "today_attended_interviews", "candidates_without_resumes",
    "stale_leads", "candidate_summary", "search_candidates", "daily_briefing",
}
_SESSIONS: dict[str, dict[str, Any]] = {}
_SESSION_LOCK = threading.Lock()
_SESSION_TTL_SECONDS = 30 * 60


def _session(session_id: str | None) -> tuple[str, dict[str, Any]]:
    now = time.time()
    with _SESSION_LOCK:
        for key in list(_SESSIONS):
            if now - float(_SESSIONS[key].get("touched") or 0) > _SESSION_TTL_SECONDS:
                _SESSIONS.pop(key, None)
        sid = (session_id or "").strip() or uuid.uuid4().hex
        state = _SESSIONS.setdefault(sid, {"turns": [], "last_plan": {}, "touched": now})
        state["touched"] = now
        return sid, state


def end_session(session_id: str) -> bool:
    with _SESSION_LOCK:
        return _SESSIONS.pop((session_id or "").strip(), None) is not None


def _ollama_plan(question: str, context: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    prompt = f"""Convert the operator question into exactly one JSON object.
Allowed intents: {', '.join(sorted(ALLOWED_INTENTS))}.
Schema: {{"intent":"...","name":"","technology":"","days":2,"limit":25}}
Resolve pronouns and follow-ups from this recent context: {json.dumps((context or [])[-4:], ensure_ascii=False)[:1800]}
Never output SQL, code, or commentary. Question: {question[:500]}"""
    try:
        payload = json.dumps({
            "model": os.getenv("OLLAMA_REASONING_MODEL", "qwen2.5:7b"),
            "stream": False, "format": "json",
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')}/api/chat",
            data=payload, headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(request, timeout=float(os.getenv("OLLAMA_TEXT_TIMEOUT", "60"))) as response:
            body = json.loads(response.read().decode("utf-8"))
        raw = body.get("message", {}).get("content", "")
        plan = json.loads(raw)
        if plan.get("intent") in ALLOWED_INTENTS:
            return plan
    except Exception:
        return None
    return None


def _fallback_plan(question: str) -> dict[str, Any]:
    q = question.strip().lower()
    if any(x in q for x in ("daily briefing", "today's briefing", "todays briefing", "today work summary", "today em pending", "focus on today", "today's pending tasks", "todays pending tasks", "summarize today's operations")):
        return {"intent": "daily_briefing"}
    if "payment" in q and any(x in q for x in ("pending", "due", "unpaid")):
        return {"intent": "pending_payments"}
    if "interview" in q and "tomorrow" in q:
        return {"intent": "tomorrow_interviews"}
    if "interview" in q and "today" in q and any(x in q for x in ("attend", "attended", "completed", "done")):
        return {"intent": "today_attended_interviews"}
    if "interview" in q and "today" in q:
        return {"intent": "today_interviews"}
    if "resume" in q and any(x in q for x in ("without", "missing", "no resume")):
        tech = "java" if "java" in q else ""
        return {"intent": "candidates_without_resumes", "technology": tech}
    if "lead" in q and any(x in q for x in ("reply", "respond", "contact")):
        match = re.search(r"(\d+)\s*day", q)
        return {"intent": "stale_leads", "days": int(match.group(1)) if match else 2}
    if "current status" in q:
        name = re.split(r"\s+current\s+status", question, flags=re.I)[0]
        name = re.sub(r"^summari[sz]e\s+", "", name, flags=re.I)
        return {"intent": "candidate_summary", "name": name.strip(" .'\"")}
    match = re.search(r"(?:summari[sz]e|status(?:\s+of)?)\s+(.+?)(?:\?|$)", question, re.I)
    if match:
        raw_name = match.group(1).strip(" .'\"")
        name = re.sub(r"(?:'s)?\s+current\s+status$", "", raw_name, flags=re.I)
        return {"intent": "candidate_summary", "name": name.strip(" .'\"")}
    return {"intent": "search_candidates", "name": question.strip()}


def _money(value: Any) -> str:
    return f"₹{int(value or 0):,}"


def answer_question(question: str, *, reference: str | None = None,
                    session_id: str | None = None) -> dict[str, Any]:
    """Interpret then execute one allowlisted, read-only query."""
    from core.crm_store import list_leads
    from features import candidate_store

    sid, session = _session(session_id)
    qlow = question.lower()
    briefing_phrases = ("daily briefing", "today's briefing", "todays briefing", "today work summary", "today em pending", "focus on today", "today's pending tasks", "todays pending tasks", "summarize today's operations")
    if any(x in qlow for x in briefing_phrases):
        plan = {"intent": "daily_briefing"}
    elif "interview" in qlow and "today" in qlow:
        plan = {"intent": ("today_attended_interviews"
                            if any(x in qlow for x in ("attend", "attended", "completed", "done"))
                            else "today_interviews")}
    else:
        plan = _ollama_plan(question, session.get("turns")) or _fallback_plan(question)
    previous = session.get("last_plan") or {}
    follow_up = len(question.split()) <= 8 or any(x in qlow for x in ("only", "among", "them", "valla", "cheppu", "undha", "kitne", "evaru"))
    if follow_up:
        asks_whose_interview = "interview" in qlow and bool(re.search(r"\b(?:who(?:'s|se)?|whose)\b", qlow))
        if asks_whose_interview and previous.get("intent") in {"today_interviews", "today_attended_interviews"}:
            plan["intent"] = "today_interviews"
        if previous.get("intent") == "candidate_summary" and previous.get("name") and any(x in qlow for x in ("payment", "pending", "status", "resume", "interview")):
            plan["intent"] = "candidate_summary"
        if plan.get("intent") == "search_candidates" and previous.get("intent"):
            plan["intent"] = previous["intent"]
        for key in ("name", "technology", "days"):
            if not plan.get(key) and previous.get(key):
                plan[key] = previous[key]
        if "java" in qlow:
            plan["technology"] = "java"
    intent = plan["intent"]
    limit = max(1, min(int(plan.get("limit") or 25), 50))
    candidates = candidate_store.list_candidates(reference=reference)
    evidence: list[dict[str, Any]] = []

    if intent == "daily_briefing":
        from core.daily_briefing import get_briefing
        briefing = get_briefing(reference=reference)
        summary = briefing["summary"]
        answer = " ".join((summary["overview"], summary["attention"], summary["recommended"]))
        for key, rows in briefing.get("records", {}).items():
            for row in rows[:limit]:
                evidence.append({"type": row.get("type") or key, "id": row.get("id"), "title": row.get("name"), "detail": row.get("detail"), "fields": {"category": key.replace("_", " ")}})
    elif intent == "pending_payments":
        rows = [r for r in candidates if int(r.get("payment") or 0) < int(r.get("expected_payment") or 0)]
        for r in rows[:limit]:
            due = int(r.get("expected_payment") or 0) - int(r.get("payment") or 0)
            evidence.append({"type": "candidate", "id": r.get("id"), "title": r.get("name"),
                             "detail": f"{r.get('technology') or 'Unspecified'} · {_money(due)} pending",
                             "fields": {"received": r.get("payment", 0), "expected": r.get("expected_payment", 0), "reference": r.get("reference", "")}})
        total = sum(int(r.get("expected_payment") or 0) - int(r.get("payment") or 0) for r in rows)
        answer = f"{len(rows)} candidate(s) have pending payments totalling {_money(total)}."
    elif intent == "tomorrow_interviews":
        day = (datetime.now().astimezone().date() + timedelta(days=1)).isoformat()
        rows = candidate_store.daily_interview_roster(day, viewer_reference=reference)["interviews"]
        tech = str(plan.get("technology") or "").strip().lower()
        if tech:
            rows = [r for r in rows if tech in str(r.get("technology") or "").lower()]
        for r in rows[:limit]:
            evidence.append({"type": "candidate", "id": r.get("id"), "title": r.get("name"),
                             "detail": f"{r.get('time') or 'Time missing'} · {r.get('interview_round') or 'Round missing'} · {r.get('technology') or 'Technology missing'}",
                             "fields": {"date": day, "reference": r.get("reference", "")}})
        answer = f"{len(rows)}{' ' + tech if tech else ''} interview(s) are scheduled for tomorrow, {day}."
    elif intent == "today_attended_interviews":
        day = datetime.now().astimezone().date().isoformat()
        scheduled_today = candidate_store.daily_interview_roster(day, viewer_reference=reference)["interviews"]
        rows = [
            r for r in scheduled_today
            if candidate_store.row_interview_attendance_status(r) == "attended"
        ]
        for r in rows[:limit]:
            evidence.append({"type": "candidate", "id": r.get("id"), "title": r.get("name"),
                             "detail": f"Attended · {r.get('time') or 'Time missing'} · {r.get('interview_round') or 'Round missing'}",
                             "fields": {"date": day, "technology": r.get("technology", ""), "attendee": candidate_store.row_interview_attendee(r), "reference": r.get("reference", "")}})
        pending = [r for r in scheduled_today if not candidate_store.row_interview_attendance_status(r)]
        answer = (f"{len(rows)} interview(s) were attended today, {day}."
                  if rows else f"No interviews are marked as attended today, {day}."
                  + (f" However, {len(pending)} interview(s) are scheduled and still pending attendance." if pending else ""))
    elif intent == "today_interviews":
        day = datetime.now().astimezone().date().isoformat()
        rows = candidate_store.daily_interview_roster(day, viewer_reference=reference)["interviews"]
        for r in rows[:limit]:
            status = candidate_store.row_interview_attendance_status(r) or "pending"
            evidence.append({"type": "candidate", "id": r.get("id"), "title": r.get("name"),
                             "detail": f"{r.get('time') or 'Time missing'} · {r.get('interview_round') or 'Round missing'} · {status.replace('_', ' ').title()}",
                             "fields": {"date": day, "technology": r.get("technology", ""), "attendance": status, "attendee": candidate_store.row_interview_attendee(r), "reference": r.get("reference", "")}})
        if rows:
            schedule = "; ".join(
                f"{r.get('name') or 'Unknown candidate'} at {r.get('time') or 'time not recorded'}"
                for r in rows[:limit]
            )
            answer = f"{len(rows)} interview(s) are scheduled today, {day}: {schedule}."
        else:
            answer = f"No interviews are scheduled today, {day}."
    elif intent == "candidates_without_resumes":
        tech = str(plan.get("technology") or "").strip().lower()
        rows = [r for r in candidates if not (r.get("resumes") or []) and (not tech or tech in str(r.get("technology") or "").lower())]
        for r in rows[:limit]:
            evidence.append({"type": "candidate", "id": r.get("id"), "title": r.get("name"),
                             "detail": f"{r.get('technology') or 'Unspecified'} · no resume uploaded",
                             "fields": {"stage": r.get("stage", ""), "reference": r.get("reference", "")}})
        answer = f"{len(rows)} candidate(s){' matching ' + tech if tech else ''} do not have a resume."
    elif intent == "stale_leads":
        days = max(1, min(int(plan.get("days") or 2), 365))
        cutoff = datetime.now().astimezone() - timedelta(days=days)
        rows = []
        for key, lead in list_leads().items():
            stamp = lead.get("last_reply_at") or lead.get("last_contact_time") or lead.get("created_at")
            try:
                dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                continue
            if dt < cutoff and lead.get("status") not in {"converted", "not_interested", "spam"}:
                rows.append((key, lead, dt))
        rows.sort(key=lambda x: x[2])
        for key, lead, dt in rows[:limit]:
            evidence.append({"type": "lead", "id": key, "title": lead.get("name") or lead.get("username") or key,
                             "detail": f"No recorded reply/contact since {dt.date().isoformat()} · {lead.get('status', 'new')}",
                             "fields": {"account": lead.get("account_id", ""), "user_id": lead.get("user_id")}})
        answer = f"{len(rows)} active lead(s) have no recorded reply or contact in the last {days} days."
    elif intent == "candidate_summary":
        term = str(plan.get("name") or question).strip()
        rows = candidate_store.list_candidates(search=term, reference=reference)
        for r in rows[:limit]:
            due = max(0, int(r.get("expected_payment") or 0) - int(r.get("payment") or 0))
            evidence.append({"type": "candidate", "id": r.get("id"), "title": r.get("name"),
                             "detail": f"{r.get('technology') or 'Unspecified'} · {r.get('stage') or 'unknown'} · {_money(due)} pending",
                             "fields": {"technology": r.get("technology", ""), "status": r.get("stage", ""), "pending_amount": due, "interview_date": r.get("date", ""), "resume_count": len(r.get("resumes") or []), "reference": r.get("reference", "")}})
        if not rows:
            answer = f"I could not find a candidate matching “{term}”."
        else:
            r = rows[0]; due = max(0, int(r.get("expected_payment") or 0) - int(r.get("payment") or 0))
            if any(x in qlow for x in ("payment", "pending", "undha")):
                answer = f"{r.get('name')} currently has {_money(due)} pending."
            else:
                answer = f"{r.get('name')} is a {r.get('technology') or 'technology-unspecified'} candidate, currently {str(r.get('stage') or 'unknown').replace('_', ' ')}, with {_money(due)} pending."
    else:
        term = str(plan.get("name") or plan.get("technology") or question).strip()
        rows = candidate_store.list_candidates(search=term, reference=reference)
        for r in rows[:limit]:
            due = max(0, int(r.get("expected_payment") or 0) - int(r.get("payment") or 0))
            evidence.append({"type": "candidate", "id": r.get("id"), "title": r.get("name"),
                             "detail": f"{r.get('technology') or 'Unspecified'} · {r.get('stage') or 'unknown'} · {_money(due)} pending",
                             "fields": {"interview_date": r.get("date", ""), "interview_time": r.get("time", ""), "resume_count": len(r.get("resumes") or []), "reference": r.get("reference", "")}})
        answer = (f"I found {len(rows)} matching candidate record(s) for “{term}”."
                  if rows else f"I could not find a candidate matching “{term}”.")

    session["last_plan"] = dict(plan)
    session["turns"] = (session.get("turns") or [])[-6:] + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer, "plan": plan},
    ]
    session["touched"] = time.time()
    return {"status": "ok", "question": question, "answer": answer, "plan": plan,
            "evidence": evidence, "evidence_count": len(evidence), "read_only": True,
            "session_id": sid}
