"""Ollama-assisted second opinion for the mail outcome audit.

This module is deliberately isolated from the interview auto-booking feature,
which is working correctly and must not be affected:

* it never imports the booking module and never calls a booking function
* it has its own prompt, its own schema, its own queue and its own cache
* it writes only to its own tables, and only ever to advise a human
* it defers entirely to live interview processing for Ollama capacity

Its output cannot create, move or cancel a booking, cannot change candidate
status, and cannot modify Gmail. The strongest thing it can do is attach a
second opinion to an audit finding that an administrator then reads.

The feature is gated by AI_MAIL_AUDIT_ENABLED, which is separate from
AI_INTERVIEW_AUTO_BOOKING_ENABLED and never read here as a substitute.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from core.db.connection import get_connection, use_postgres
from core import recruitment_mail_audit as engine

logger = logging.getLogger("teleautomation.recruitment_audit_ai")

FEATURE_FLAG = "AI_MAIL_AUDIT_ENABLED"

QUEUE_PENDING = "PENDING"
QUEUE_RUNNING = "RUNNING"
QUEUE_DONE = "COMPLETED"
QUEUE_FAILED = "FAILED"
QUEUE_DEFERRED = "DEFERRED"


def enabled() -> bool:
    """The audit's own switch. Never falls back to the booking flag."""
    return os.getenv(FEATURE_FLAG, "false").strip().lower() == "true"


def _id() -> str:
    return str(uuid.uuid4())


def ensure_schema() -> None:
    if not use_postgres():
        return
    migration = (Path(__file__).with_name("migrations")
                 / "022_recruitment_mail_audit_ai.sql")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(migration.read_text(encoding="utf-8"))


def _rows(cur) -> list[dict[str, Any]]:
    names = [d.name for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


# ── Capacity deference ───────────────────────────────────────────────────────
#
# Live interview processing always wins. The audit does not queue behind it,
# compete with it, or retry into it: when live work exists the audit simply
# does not start, and its jobs stay PENDING until the pipeline is idle.

def live_pipeline_busy() -> dict[str, Any]:
    """Report whether the live mail and booking pipeline has work in flight."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT count(*) FROM mailbox_sync_jobs
               WHERE status IN ('QUEUED','RUNNING')"""
        )
        sync_jobs = int(cur.fetchone()[0] or 0)
        cur.execute(
            """SELECT count(*) FROM mailbox_messages
               WHERE processing_status IN ('AI_RETRY_PENDING','AI_PENDING')"""
        )
        ai_backlog = int(cur.fetchone()[0] or 0)
        cur.execute(
            """SELECT count(*) FROM gmail_message_ingestion_queue
               WHERE status IN ('QUEUED','RUNNING')"""
        )
        ingestion = int(cur.fetchone()[0] or 0)
    busy = bool(sync_jobs or ai_backlog or ingestion)
    return {
        "busy": busy, "sync_jobs": sync_jobs,
        "ai_backlog": ai_backlog, "ingestion": ingestion,
    }


def may_run() -> dict[str, Any]:
    """Whether an audit inference may start right now.

    Every condition is a reason to yield to the booking pipeline rather than a
    reason to wait in its queue.
    """
    if not enabled():
        return {"allowed": False, "reason": f"{FEATURE_FLAG} is not enabled."}
    live = live_pipeline_busy()
    if live["busy"]:
        return {
            "allowed": False,
            "reason": (
                f"Live interview processing is active "
                f"(sync jobs {live['sync_jobs']}, AI backlog {live['ai_backlog']}, "
                f"ingestion {live['ingestion']}); the audit yields."
            ),
            "live": live,
        }
    try:
        from core.ai_gateway import health
        status = health(timeout=5)
    except Exception as exc:
        return {"allowed": False, "reason": f"Ollama health unavailable: {exc}"}
    if not status.get("endpoint_reachable") or not status.get("model_available"):
        return {"allowed": False,
                "reason": "Ollama is unavailable; audit jobs stay pending."}
    return {"allowed": True, "reason": "", "live": live}


def max_concurrency() -> int:
    """Audit inference is single-file by default and hard-capped low."""
    try:
        value = int(os.getenv("AI_MAIL_AUDIT_CONCURRENCY", "1"))
    except ValueError:
        value = 1
    return max(1, min(2, value))


# ── Prompt and schema, owned by the audit alone ──────────────────────────────

AUDIT_PROMPT_NAME = "recruitment_mail_audit_second_opinion_v1"

AUDIT_SYSTEM_PROMPT = """You are the TeleAutomation mail audit reviewer.

You are given one email that a deterministic rule engine has already
classified. Your only job is to give a second opinion on whether that
classification is supported by the text.

You are a read-only reviewer. You cannot book, reschedule or cancel an
interview, you cannot change a candidate's status, and nothing you return is
executed. An administrator reads your answer and decides.

Judge only what the email itself states:
- a job portal or agency relaying news is not the hiring company confirming it
- a bulk campaign or job advertisement is not a decision about this candidate
- a request for profile details is not an interview round
- boilerplate such as "assume you were not shortlisted if you do not hear from
  us" is a general policy, not this candidate's rejection
- an offer letter is only verified when real offer terms are present
- interview scheduling is not selection
If the text does not clearly support any outcome, say so.
"""

AUDIT_SCHEMA = {
    "type": "object",
    "required": ["agrees", "suggested_outcome", "confidence", "reasoning",
                 "is_bulk_campaign", "sender_is_hiring_company"],
    "properties": {
        "agrees": {"type": "boolean"},
        "suggested_outcome": {"type": "string", "enum": sorted(engine.OUTCOMES)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 100},
        "reasoning": {"type": "string", "maxLength": 800},
        "is_bulk_campaign": {"type": "boolean"},
        "sender_is_hiring_company": {"type": "boolean"},
        "quoted_evidence": {"type": "string", "maxLength": 400},
    },
    "additionalProperties": False,
}


def cache_key(finding: dict[str, Any]) -> str:
    """Audit's own cache namespace; shares nothing with booking or detection."""
    payload = "|".join([
        AUDIT_PROMPT_NAME,
        str(finding.get("provider_message_id") or ""),
        str(finding.get("outcome") or ""),
        str(finding.get("content_signature") or ""),
    ])
    return hashlib.sha256(payload.encode("utf-8", "replace")).hexdigest()


def _prompt_payload(finding: dict[str, Any], body: str) -> list[dict[str, Any]]:
    return [
        {"role": "system", "content": AUDIT_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps({
            "rule_engine_outcome": finding.get("outcome"),
            "rule_engine_rationale": finding.get("rationale"),
            "subject": finding.get("subject"),
            "sender_email": finding.get("sender_email"),
            "sender_domain": finding.get("sender_domain"),
            "stated_company": finding.get("company_name"),
            "company_domain": finding.get("company_domain"),
            "role": finding.get("job_title"),
            "received_at": str(finding.get("received_at") or ""),
            "body": (body or "")[:6000],
        }, default=str)},
    ]


# ── Queue ────────────────────────────────────────────────────────────────────

def enqueue(finding_ids: list[str], *, requested_by: str = "system") -> int:
    """Queue findings for a second opinion. Idempotent per finding."""
    if not finding_ids:
        return 0
    ensure_schema()
    queued = 0
    with get_connection() as conn, conn.cursor() as cur:
        for finding_id in finding_ids:
            cur.execute(
                """INSERT INTO mail_audit_ai_queue
                     (id,finding_id,status,requested_by)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (finding_id) DO NOTHING""",
                (_id(), finding_id, QUEUE_PENDING, requested_by),
            )
            queued += cur.rowcount or 0
    return queued


def claim(limit: int = 1) -> list[dict[str, Any]]:
    """Take pending audit jobs. Touches no queue but the audit's own."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE mail_audit_ai_queue SET status=%s,started_at=now(),
                   attempts=attempts+1,updated_at=now()
               WHERE id IN (
                 SELECT id FROM mail_audit_ai_queue
                 WHERE status=%s AND (retry_after IS NULL OR retry_after<=now())
                 ORDER BY created_at LIMIT %s FOR UPDATE SKIP LOCKED)
               RETURNING *""",
            (QUEUE_RUNNING, QUEUE_PENDING, max(1, min(5, int(limit)))),
        )
        return _rows(cur)


def _finish(job_id: str, status: str, *, error: str | None = None,
            delay_minutes: int = 15) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        if status == QUEUE_FAILED:
            cur.execute(
                """UPDATE mail_audit_ai_queue
                   SET status=CASE WHEN attempts>=3 THEN 'FAILED' ELSE 'PENDING' END,
                       last_error=%s,retry_after=now()+(%s||' minutes')::interval,
                       updated_at=now()
                   WHERE id=%s""",
                (str(error or "")[:400], delay_minutes, job_id),
            )
        else:
            cur.execute(
                """UPDATE mail_audit_ai_queue SET status=%s,completed_at=now(),
                       last_error=NULL,updated_at=now() WHERE id=%s""",
                (status, job_id),
            )


def _finding_for_job(finding_id: str) -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT f.id,f.provider_message_id,f.outcome,f.rationale,f.subject,
                      f.sender_email,f.sender_domain,f.company_name,f.company_domain,
                      f.job_title,f.received_at,f.content_signature,
                      m.body_text
               FROM mail_outcome_audit_findings f
               LEFT JOIN mailbox_messages m ON m.id=f.mailbox_message_id
               WHERE f.id=%s""",
            (finding_id,),
        )
        rows = _rows(cur)
    return rows[0] if rows else None


def cached_result(key: str) -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM mail_audit_ai_results WHERE cache_key=%s", (key,),
        )
        rows = _rows(cur)
    return rows[0] if rows else None


def review_one(job: dict[str, Any]) -> dict[str, Any]:
    """Run one second opinion. Never raises into the caller's loop."""
    finding = _finding_for_job(str(job["finding_id"]))
    if not finding:
        _finish(str(job["id"]), QUEUE_DONE)
        return {"status": "SKIPPED", "reason": "finding no longer exists"}

    key = cache_key(finding)
    cached = cached_result(key)
    if cached:
        _finish(str(job["id"]), QUEUE_DONE)
        return {"status": "CACHED", "result": cached}

    from core.ai_gateway import chat_structured, AIGatewayError
    try:
        answer = chat_structured(
            messages=_prompt_payload(finding, finding.get("body_text") or ""),
            schema=AUDIT_SCHEMA,
            timeout=float(os.getenv("AI_MAIL_AUDIT_TIMEOUT_SECONDS", "90")),
            workload="mail_audit_review",
        )
        payload = answer.data if hasattr(answer, "data") else answer
        if not isinstance(payload, dict):
            raise AIGatewayError("Audit model returned a non-object response")
    except Exception as exc:
        # A failed or malformed audit review is contained here. It never
        # reaches the booking pipeline and never becomes an outcome.
        logger.warning("Audit second opinion failed finding_id=%s: %s",
                       job.get("finding_id"), exc)
        _finish(str(job["id"]), QUEUE_FAILED, error=str(exc))
        return {"status": "FAILED", "error": str(exc)[:400]}

    record = _store_result(key, finding, payload, model=str(getattr(answer, "model", "") or ""))
    _finish(str(job["id"]), QUEUE_DONE)
    return {"status": "COMPLETED", "result": record}


def _store_result(key: str, finding: dict[str, Any], payload: dict[str, Any],
                  *, model: str) -> dict[str, Any]:
    """Persist the second opinion. Advisory only: no finding is overwritten."""
    record_id = _id()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO mail_audit_ai_results
                 (id,cache_key,finding_id,prompt_name,model,agrees,suggested_outcome,
                  confidence,reasoning,is_bulk_campaign,sender_is_hiring_company,
                  quoted_evidence,raw_response)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
               ON CONFLICT (cache_key) DO UPDATE SET
                 agrees=EXCLUDED.agrees,suggested_outcome=EXCLUDED.suggested_outcome,
                 confidence=EXCLUDED.confidence,reasoning=EXCLUDED.reasoning,
                 is_bulk_campaign=EXCLUDED.is_bulk_campaign,
                 sender_is_hiring_company=EXCLUDED.sender_is_hiring_company,
                 quoted_evidence=EXCLUDED.quoted_evidence,
                 raw_response=EXCLUDED.raw_response,updated_at=now()
               RETURNING *""",
            (record_id, key, finding["id"], AUDIT_PROMPT_NAME, model,
             bool(payload.get("agrees")), str(payload.get("suggested_outcome") or ""),
             float(payload.get("confidence") or 0), str(payload.get("reasoning") or "")[:800],
             bool(payload.get("is_bulk_campaign")),
             bool(payload.get("sender_is_hiring_company")),
             str(payload.get("quoted_evidence") or "")[:400],
             json.dumps(payload, default=str)),
        )
        rows = _rows(cur)
    return rows[0] if rows else {}


def process_pending(limit: int | None = None) -> dict[str, Any]:
    """One audit pass. Yields to live processing and returns without work."""
    gate = may_run()
    if not gate["allowed"]:
        return {"ran": 0, "deferred": True, "reason": gate["reason"]}

    ensure_schema()
    budget = limit if limit is not None else max_concurrency()
    done = failed = 0
    for _ in range(max(1, budget)):
        # Re-check before every inference: live work that arrives mid-pass
        # takes the node back immediately.
        if not may_run()["allowed"]:
            return {"ran": done, "failed": failed, "deferred": True,
                    "reason": "Live processing resumed; audit yielded."}
        jobs = claim(limit=1)
        if not jobs:
            break
        outcome = review_one(jobs[0])
        if outcome["status"] == "FAILED":
            failed += 1
        else:
            done += 1
    return {"ran": done, "failed": failed, "deferred": False, "reason": ""}


def queue_status() -> dict[str, Any]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT status,count(*) AS total FROM mail_audit_ai_queue GROUP BY 1",
        )
        counts = {row["status"]: int(row["total"]) for row in _rows(cur)}
        cur.execute("SELECT count(*) FROM mail_audit_ai_results")
        results = int(cur.fetchone()[0] or 0)
    return {"enabled": enabled(), "queue": counts, "results": results,
            "concurrency": max_concurrency(), "gate": may_run()}


def results_for_findings(finding_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not finding_ids:
        return {}
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM mail_audit_ai_results WHERE finding_id = ANY(%s)",
            (finding_ids,),
        )
        return {str(row["finding_id"]): row for row in _rows(cur)}


def disagreements(limit: int = 100) -> list[dict[str, Any]]:
    """Findings where the model and the rule engine differ — the useful output."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT r.*,f.subject,f.sender_email,f.outcome AS rule_outcome,
                      f.canonical_candidate_id,c.candidate_name
               FROM mail_audit_ai_results r
               JOIN mail_outcome_audit_findings f ON f.id=r.finding_id
               LEFT JOIN mail_outcome_audit_candidates c
                 ON c.canonical_candidate_id=f.canonical_candidate_id
               WHERE r.agrees=false
               ORDER BY r.confidence DESC LIMIT %s""",
            (max(1, min(500, int(limit))),),
        )
        return _rows(cur)
