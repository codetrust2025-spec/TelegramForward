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

You receive the whole thread, oldest first, and the text extracted from any
attachments. Read all of it before answering, and keep companies separate: a
result from one company says nothing about another.

Every answer must be checkable:
- cited_message_id must be one of the message_id values given to you
- quoted_evidence must be text copied verbatim from a body or an attachment
- cited_attachment must be a filename given to you, or null
Do not invent a message, a quotation, an attachment or a company. If nothing
in the input supports a conclusion, set agrees to reflect that and say why.
"""

AUDIT_SCHEMA = {
    "type": "object",
    "required": ["agrees", "suggested_outcome", "confidence", "reasoning",
                 "is_bulk_campaign", "sender_is_hiring_company",
                 "cited_message_id", "quoted_evidence", "company", "cited_attachment"],
    "properties": {
        "agrees": {"type": "boolean"},
        "suggested_outcome": {"type": "string", "enum": sorted(engine.OUTCOMES)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 100},
        "reasoning": {"type": "string", "maxLength": 800},
        "is_bulk_campaign": {"type": "boolean"},
        "sender_is_hiring_company": {"type": "boolean"},
        # Citations exist so the answer can be checked against the source.
        # A message id or quote that is not in the input is a fabrication and
        # is caught by verify_review before the result is trusted.
        "cited_message_id": {"type": "string", "maxLength": 64},
        "quoted_evidence": {"type": "string", "maxLength": 400},
        "cited_attachment": {"type": ["string", "null"], "maxLength": 200},
        "company": {"type": ["string", "null"], "maxLength": 200},
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
            "message_under_review": finding.get("provider_message_id"),
            "rule_engine_outcome": finding.get("outcome"),
            "rule_engine_rationale": finding.get("rationale"),
            "live_pipeline_outcome": finding.get("pipeline_outcome"),
            "subject": finding.get("subject"),
            "sender_email": finding.get("sender_email"),
            "sender_domain": finding.get("sender_domain"),
            "stated_company": finding.get("company_name"),
            "company_domain": finding.get("company_domain"),
            "role": finding.get("job_title"),
            "application_key": finding.get("application_key"),
            "received_at": str(finding.get("received_at") or ""),
            # The full conversation and the real extracted attachment text.
            "thread": finding.get("thread") or [],
            "attachments": finding.get("attachments") or [],
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
    """Load one finding with everything the reviewer must actually read.

    The complete thread and the extracted attachment text travel with the
    prompt, because a second opinion formed from the subject line alone is
    worth no more than the rule it is checking.
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT f.id,f.provider_message_id,f.provider_thread_id,f.outcome,
                      f.rationale,f.subject,f.sender_email,f.sender_domain,
                      f.company_name,f.company_domain,f.job_title,f.received_at,
                      f.content_signature,f.application_key,f.source_type,
                      f.evidence_strength,f.authenticity,f.pipeline_outcome,
                      f.mailbox_id,f.mailbox_message_id,f.canonical_candidate_id,
                      m.body_text
               FROM mail_outcome_audit_findings f
               LEFT JOIN mailbox_messages m ON m.id=f.mailbox_message_id
               WHERE f.id=%s""",
            (finding_id,),
        )
        rows = _rows(cur)
    if not rows:
        return None
    finding = rows[0]

    with get_connection() as conn, conn.cursor() as cur:
        # The whole conversation, oldest first, so chronology is visible.
        cur.execute(
            """SELECT provider_message_id,subject,sender_email,sent_at,body_text,
                      message_direction
               FROM mailbox_messages
               WHERE mailbox_id=%s AND provider_thread_id=%s
               ORDER BY COALESCE(sent_at,created_at)""",
            (finding.get("mailbox_id"), finding.get("provider_thread_id") or ""),
        )
        thread = _rows(cur)
        cur.execute(
            """SELECT a.filename,a.mime_type,a.attachment_type,a.extraction_status,
                      c.extracted_text
               FROM mailbox_attachments a
               LEFT JOIN mailbox_attachment_cache c ON c.checksum=a.checksum
               WHERE a.mailbox_message_id=%s""",
            (finding.get("mailbox_message_id"),),
        )
        attachments = _rows(cur)

    finding["thread"] = [
        {
            "message_id": row.get("provider_message_id"),
            "subject": row.get("subject"),
            "from": row.get("sender_email"),
            "sent_at": str(row.get("sent_at") or ""),
            "direction": row.get("message_direction"),
            "body": (row.get("body_text") or "")[:2500],
        }
        for row in thread
    ] or [{
        "message_id": finding.get("provider_message_id"),
        "subject": finding.get("subject"), "from": finding.get("sender_email"),
        "sent_at": str(finding.get("received_at") or ""), "direction": None,
        "body": (finding.get("body_text") or "")[:2500],
    }]
    finding["attachments"] = [
        {
            "filename": row.get("filename"), "mime_type": row.get("mime_type"),
            "attachment_type": row.get("attachment_type"),
            "extraction_status": row.get("extraction_status"),
            "extracted_text": (row.get("extracted_text") or "")[:3000],
        }
        for row in attachments
    ]
    return finding


# ── First-rollout eligibility ────────────────────────────────────────────────
#
# The audit does not review everything. It reviews the cases where a second
# opinion changes what an administrator would do: the ones the rules already
# doubt, the ones where the rules and the live pipeline disagree, and the ones
# whose consequences are largest.

ELIGIBILITY_SQL = """
    (
      f.outcome = 'MANUAL_REVIEW_REQUIRED'
      OR f.manual_review_required = true
      OR f.pipeline_agreement IN ('AUDIT_STRONGER','PIPELINE_STRONGER')
      OR f.outcome IN ('VERIFIED_OFFER_LETTER','OFFER_INDICATION')
      OR f.authenticity = 'SUSPICIOUS'
      OR c.status_mismatch = true
    )
"""


def eligible_findings(limit: int = 5) -> list[dict[str, Any]]:
    """Selection-audit findings worth a second opinion, highest value first.

    Deliberately excludes suppressed findings and anything already reviewed:
    this is a targeted first pass, not a backfill of every stored email.
    """
    from core import recruitment_mail_audit as audit_engine
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT f.id,f.canonical_candidate_id,f.subject,f.outcome,
                       f.authenticity,f.pipeline_agreement,f.manual_review_required,
                       c.candidate_name,c.status_mismatch
                FROM mail_outcome_audit_findings f
                LEFT JOIN mail_outcome_audit_candidates c
                  ON c.canonical_candidate_id = f.canonical_candidate_id
                WHERE COALESCE(f.suppressed,false) = false
                  AND f.outcome = ANY(%s)
                  AND {ELIGIBILITY_SQL}
                  AND NOT EXISTS (
                    SELECT 1 FROM mail_audit_ai_queue q WHERE q.finding_id = f.id)
                  AND NOT EXISTS (
                    SELECT 1 FROM mail_audit_ai_results r WHERE r.finding_id = f.id)
                ORDER BY
                  CASE f.outcome
                    WHEN 'VERIFIED_OFFER_LETTER' THEN 0
                    WHEN 'OFFER_INDICATION' THEN 1
                    WHEN 'MANUAL_REVIEW_REQUIRED' THEN 2
                    ELSE 3 END,
                  (f.authenticity = 'SUSPICIOUS') DESC,
                  f.received_at DESC NULLS LAST
                LIMIT %s""",
            (sorted(audit_engine.SELECTION_OUTCOMES), max(1, min(50, int(limit)))),
        )
        return _rows(cur)


def cached_result(key: str) -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM mail_audit_ai_results WHERE cache_key=%s", (key,),
        )
        rows = _rows(cur)
    return rows[0] if rows else None


def _normalise(value: str) -> str:
    return " ".join(str(value or "").split()).lower()


def verify_review(finding: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Check the model's citations against the material it was actually given.

    A second opinion is only useful if it can be checked. Every claim the
    model makes must point at a real message, a real quotation and a real
    attachment; anything else is recorded as a fabrication and the review is
    marked untrusted rather than silently believed.
    """
    problems: list[str] = []
    thread = finding.get("thread") or []
    attachments = finding.get("attachments") or []

    known_ids = {str(item.get("message_id") or "") for item in thread}
    known_ids.add(str(finding.get("provider_message_id") or ""))
    known_ids.discard("")
    cited_id = str(payload.get("cited_message_id") or "").strip()
    if not cited_id:
        problems.append("No message id was cited.")
    elif cited_id not in known_ids:
        problems.append(f"Cited message id {cited_id} was not in the input.")

    corpus = _normalise(" ".join(
        [str(item.get("body") or "") for item in thread]
        + [str(item.get("extracted_text") or "") for item in attachments]
        + [str(finding.get("subject") or "")]
    ))
    quote = _normalise(payload.get("quoted_evidence"))
    if not quote:
        problems.append("No evidence was quoted.")
    elif quote not in corpus:
        # Allow a shortened quote, but require a substantial contiguous run.
        head = quote[:60]
        if len(head) < 12 or head not in corpus:
            problems.append("Quoted evidence does not appear in the source text.")

    known_files = {_normalise(item.get("filename")) for item in attachments}
    known_files.discard("")
    cited_file = _normalise(payload.get("cited_attachment"))
    if cited_file and cited_file not in known_files:
        problems.append(f"Cited attachment '{payload.get('cited_attachment')}' does not exist.")
    if cited_file and not attachments:
        problems.append("An attachment was cited but the message has none.")

    return {"trusted": not problems, "problems": problems,
            "checked_message_ids": sorted(known_ids),
            "checked_attachments": sorted(f for f in known_files if f)}


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

    verification = verify_review(finding, payload)
    record = _store_result(key, finding, payload,
                           model=str(getattr(answer, "model", "") or ""),
                           verification=verification)
    _finish(str(job["id"]), QUEUE_DONE)
    return {"status": "COMPLETED", "result": record, "verification": verification}


def _store_result(key: str, finding: dict[str, Any], payload: dict[str, Any],
                  *, model: str, verification: dict[str, Any] | None = None) -> dict[str, Any]:
    """Persist the second opinion. Advisory only: no finding is overwritten."""
    record_id = _id()
    verification = verification or {"trusted": False, "problems": ["not verified"]}
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO mail_audit_ai_results
                 (id,cache_key,finding_id,prompt_name,model,agrees,suggested_outcome,
                  confidence,reasoning,is_bulk_campaign,sender_is_hiring_company,
                  quoted_evidence,cited_message_id,cited_attachment,cited_company,
                  verified,verification_problems,raw_response)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
               ON CONFLICT (cache_key) DO UPDATE SET
                 agrees=EXCLUDED.agrees,suggested_outcome=EXCLUDED.suggested_outcome,
                 confidence=EXCLUDED.confidence,reasoning=EXCLUDED.reasoning,
                 is_bulk_campaign=EXCLUDED.is_bulk_campaign,
                 sender_is_hiring_company=EXCLUDED.sender_is_hiring_company,
                 quoted_evidence=EXCLUDED.quoted_evidence,
                 cited_message_id=EXCLUDED.cited_message_id,
                 cited_attachment=EXCLUDED.cited_attachment,
                 cited_company=EXCLUDED.cited_company,
                 verified=EXCLUDED.verified,
                 verification_problems=EXCLUDED.verification_problems,
                 raw_response=EXCLUDED.raw_response,updated_at=now()
               RETURNING *""",
            (record_id, key, finding["id"], AUDIT_PROMPT_NAME, model,
             bool(payload.get("agrees")), str(payload.get("suggested_outcome") or ""),
             float(payload.get("confidence") or 0), str(payload.get("reasoning") or "")[:800],
             bool(payload.get("is_bulk_campaign")),
             bool(payload.get("sender_is_hiring_company")),
             str(payload.get("quoted_evidence") or "")[:400],
             str(payload.get("cited_message_id") or "")[:64],
             str(payload.get("cited_attachment") or "")[:200] or None,
             str(payload.get("company") or "")[:200] or None,
             bool(verification.get("trusted")),
             "; ".join(verification.get("problems") or [])[:600] or None,
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
