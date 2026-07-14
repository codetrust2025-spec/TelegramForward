"""PostgreSQL persistence for candidate mailbox recruitment tracking."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from datetime import date, datetime, timezone
from typing import Any

from core.db.connection import get_connection, use_postgres
from core.recruitment_offer_visibility import (
    qualified_event_sql,
    should_show_in_selection_offer_review,
)


def _id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_schema() -> None:
    if not use_postgres():
        return
    with get_connection() as conn, conn.cursor() as cur:
        migrations = Path(__file__).with_name("migrations")
        for migration in sorted(migrations.glob("*_recruitment_mail_*.sql")):
            cur.execute(migration.read_text(encoding="utf-8"))


def _rows(cur) -> list[dict[str, Any]]:
    names = [d.name for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def mailbox_for_candidate(candidate_id: str) -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM candidate_mailboxes WHERE candidate_id=%s ORDER BY created_at DESC LIMIT 1", (candidate_id,))
        rows = _rows(cur)
    return rows[0] if rows else None


def mailbox_by_id(mailbox_id: str) -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM candidate_mailboxes WHERE id=%s", (mailbox_id,))
        rows = _rows(cur)
    return rows[0] if rows else None


def upsert_mailbox(candidate_id: str, email: str, **fields: Any) -> dict[str, Any]:
    mailbox_id = fields.pop("id", None) or _id()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO candidate_mailboxes(id,candidate_id,provider,email_address,connection_type,monitoring_enabled,connection_status,credential_ciphertext,created_at,updated_at)
            VALUES(%s,%s,'gmail',%s,'oauth2',%s,%s,%s,now(),now())
            ON CONFLICT(candidate_id,provider) DO UPDATE SET email_address=EXCLUDED.email_address,
              monitoring_enabled=EXCLUDED.monitoring_enabled, connection_status=EXCLUDED.connection_status,
              credential_ciphertext=COALESCE(EXCLUDED.credential_ciphertext,candidate_mailboxes.credential_ciphertext), updated_at=now()
            RETURNING *
        """, (mailbox_id,candidate_id,email,bool(fields.get("monitoring_enabled",False)),fields.get("connection_status","PENDING"),fields.get("credential_ciphertext")))
        row=_rows(cur)[0]
        cur.execute("SELECT candidate_id FROM candidate_mailboxes WHERE lower(email_address)=lower(%s) AND candidate_id<>%s LIMIT 1",(email,candidate_id));duplicate=cur.fetchone()
        if duplicate:
            cur.execute("""INSERT INTO recruitment_review_flags(id,candidate_id,flag_type,severity,details,created_at)
              VALUES(%s,%s,'POSSIBLE_DUPLICATE_CANDIDATE','HIGH',%s::jsonb,now()) ON CONFLICT(candidate_id,event_id,flag_type) DO NOTHING""",(_id(),candidate_id,json.dumps({'matching_candidate_id':duplicate[0],'reason':'same_mailbox_email'})))
        return row


def update_mailbox(mailbox_id: str, values: dict[str, Any]) -> dict[str, Any]:
    allowed={"monitoring_enabled","connection_status","credential_ciphertext","sync_cursor","provider_history_id","last_sync_attempt_at","last_successful_sync_at","next_sync_at","failed_sync_count","last_error_code","last_error_message"}
    clean={k:v for k,v in values.items() if k in allowed}
    if not clean:
        return mailbox_by_id(mailbox_id) or {}
    assignments=", ".join(f"{k}=%s" for k in clean)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE candidate_mailboxes SET {assignments},updated_at=now() WHERE id=%s RETURNING *", (*clean.values(),mailbox_id))
        rows=_rows(cur)
    return rows[0] if rows else {}


def enqueue_sync(mailbox_id: str, *, requested_by: str, scheduled_for: datetime | None=None) -> dict[str, Any]:
    job_id=_id()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM mailbox_sync_jobs WHERE mailbox_id=%s AND status IN('QUEUED','RUNNING') ORDER BY created_at DESC LIMIT 1 FOR UPDATE",(mailbox_id,))
        existing=_rows(cur) if cur.description else []
        if existing:return existing[0]
        cur.execute("""INSERT INTO mailbox_sync_jobs(id,mailbox_id,status,scheduled_for,requested_by,created_at)
          VALUES(%s,%s,'QUEUED',%s,%s,now()) RETURNING *""",(job_id,mailbox_id,scheduled_for or now(),requested_by))
        return _rows(cur)[0]


def enqueue_historical_rescan(mailbox_id: str, *, requested_by: str, range_start: date, range_end: date) -> dict[str, Any]:
    job_id = _id()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM mailbox_sync_jobs WHERE mailbox_id=%s AND status IN('QUEUED','RUNNING') ORDER BY created_at DESC LIMIT 1 FOR UPDATE", (mailbox_id,))
        existing = _rows(cur) if cur.description else []
        if existing:
            return existing[0]
        cur.execute("""INSERT INTO mailbox_sync_jobs(id,mailbox_id,status,scheduled_for,requested_by,job_type,range_start,range_end,created_at)
          VALUES(%s,%s,'QUEUED',now(),%s,'HISTORICAL_RESCAN',%s,%s,now()) RETURNING *""",
          (job_id, mailbox_id, requested_by, range_start, range_end))
        return _rows(cur)[0]


def claim_job() -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT j.id FROM mailbox_sync_jobs j WHERE j.status='QUEUED' AND j.scheduled_for<=now()
          AND NOT EXISTS(SELECT 1 FROM mailbox_sync_jobs active WHERE active.mailbox_id=j.mailbox_id AND active.status='RUNNING')
          ORDER BY j.scheduled_for FOR UPDATE OF j SKIP LOCKED LIMIT 1""")
        row=cur.fetchone()
        if not row:return None
        cur.execute("UPDATE mailbox_sync_jobs SET status='RUNNING',started_at=now(),attempts=attempts+1 WHERE id=%s RETURNING *",(row[0],))
        return _rows(cur)[0]


def finish_job(job_id: str, *, status: str, counts: dict[str,int]|None=None, error: str|None=None) -> None:
    c=counts or {}
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE mailbox_sync_jobs SET status=%s,completed_at=now(),messages_fetched=%s,messages_processed=%s,
          events_detected=%s,error_message=%s WHERE id=%s""",(status,c.get('fetched',0),c.get('processed',0),c.get('events',0),error,job_id))


def retry_job(job_id:str,*,delay_minutes:int,error:str,max_attempts:int=5)->str:
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("SELECT attempts FROM mailbox_sync_jobs WHERE id=%s FOR UPDATE",(job_id,));row=cur.fetchone();attempts=int(row[0] if row else max_attempts)
        status='DEAD_LETTER' if attempts>=max_attempts else 'QUEUED'
        cur.execute("UPDATE mailbox_sync_jobs SET status=%s,scheduled_for=now()+(%s||' minutes')::interval,completed_at=CASE WHEN %s='DEAD_LETTER' THEN now() ELSE NULL END,error_message=%s WHERE id=%s",(status,delay_minutes,status,error,job_id))
    return status


def insert_message(mailbox: dict[str,Any], message: dict[str,Any], score: float) -> tuple[dict[str,Any],bool]:
    mid=_id()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO mailbox_messages(id,mailbox_id,candidate_id,provider_message_id,provider_thread_id,sender_name,sender_email,
          recipient_email,subject,sent_at,message_hash,body_hash,recruitment_relevance_score,processing_status,body_text,html_body_text,created_at,updated_at)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'FILTERED',%s,%s,now(),now())
          ON CONFLICT(mailbox_id,provider_message_id) DO UPDATE SET
            body_text=COALESCE(mailbox_messages.body_text,EXCLUDED.body_text),
            html_body_text=COALESCE(mailbox_messages.html_body_text,EXCLUDED.html_body_text),
            recruitment_relevance_score=GREATEST(COALESCE(mailbox_messages.recruitment_relevance_score,0),EXCLUDED.recruitment_relevance_score),updated_at=now()
          RETURNING *, (xmax = 0) AS was_created""",
          (mid,mailbox['id'],mailbox['candidate_id'],message['provider_message_id'],message.get('provider_thread_id'),message.get('sender_name'),message.get('sender_email'),message.get('recipient_email'),message.get('subject'),message.get('sent_at'),message['message_hash'],message['body_hash'],score,message.get('body'),message.get('html_body')))
        rows=_rows(cur) if cur.description else []
    if not rows:return {},False
    row=rows[0];created=bool(row.pop('was_created',False));return row,created


def mark_reprocessed(message_id: str, previous_status: str | None, new_status: str, reason: str) -> None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE mailbox_messages SET previous_processing_status=%s,processing_status=%s,
          reprocessed_at=now(),reprocessing_reason=%s,reprocessing_prompt_version='recruitment_email_status_extraction_v2',updated_at=now()
          WHERE id=%s""", (previous_status,new_status,reason,message_id))


def stored_message(mailbox_id: str, provider_message_id: str) -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM mailbox_messages WHERE mailbox_id=%s AND provider_message_id=%s", (mailbox_id,provider_message_id))
        rows=_rows(cur)
    return rows[0] if rows else None


def is_duplicate_content(candidate_id:str,message_id:str,message_hash:str,body_hash:str)->bool:
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("""SELECT 1 FROM mailbox_messages m JOIN ai_recruitment_events e ON e.mailbox_message_id=m.id
          WHERE m.candidate_id=%s AND m.id<>%s AND (m.message_hash=%s OR (m.body_hash=%s AND %s<>%s)) LIMIT 1""",(candidate_id,message_id,message_hash,body_hash,body_hash,content_hash_empty()))
        return cur.fetchone() is not None


def content_hash_empty()->str:
    import hashlib
    return hashlib.sha256(b'').hexdigest()


def mark_message_status(message_id:str,status:str,*,reason:str|None=None,cleanup_version:str|None=None)->None:
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("""UPDATE mailbox_messages SET processing_status=%s,ignore_reason=%s,
          ignored_at=CASE WHEN %s LIKE 'IGNORED%%' THEN now() ELSE ignored_at END,
          cleanup_version=COALESCE(%s,cleanup_version),updated_at=now() WHERE id=%s""",
          (status,reason,status,cleanup_version,message_id))


def is_duplicate_offer_attachment(candidate_id:str,message_id:str)->bool:
    """True when a checksum already belongs to a visible event for this candidate."""
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("""SELECT 1 FROM mailbox_attachments current_attachment
          JOIN mailbox_attachments previous_attachment ON previous_attachment.checksum=current_attachment.checksum
            AND previous_attachment.mailbox_message_id<>current_attachment.mailbox_message_id
          JOIN ai_recruitment_events e ON e.mailbox_message_id=previous_attachment.mailbox_message_id
          WHERE current_attachment.mailbox_message_id=%s AND e.candidate_id=%s
            AND e.review_status NOT IN('FALSE_POSITIVE','DUPLICATE') LIMIT 1""",(message_id,candidate_id))
        return cur.fetchone() is not None


def is_duplicate_thread_status(candidate_id:str,message_id:str,status:str)->bool:
    """Suppress repeated reminders with the same status in the same Gmail thread."""
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("""SELECT 1 FROM mailbox_messages current_message
          JOIN mailbox_messages previous_message ON previous_message.provider_thread_id=current_message.provider_thread_id
            AND previous_message.id<>current_message.id
          JOIN ai_recruitment_events e ON e.mailbox_message_id=previous_message.id
          WHERE current_message.id=%s AND current_message.provider_thread_id IS NOT NULL
            AND e.candidate_id=%s AND e.primary_status=%s
            AND e.review_status NOT IN('FALSE_POSITIVE','DUPLICATE') LIMIT 1""",(message_id,candidate_id,status))
        return cur.fetchone() is not None


def attachment_cache(checksum: str) -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM mailbox_attachment_cache WHERE checksum=%s", (checksum,))
        rows = _rows(cur)
    return rows[0] if rows else None


def save_attachment(message_id: str, attachment: dict[str, Any]) -> dict[str, Any]:
    aid = _id()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO mailbox_attachment_cache(checksum,mime_type,size,extracted_text,extraction_method,attachment_type,created_at,updated_at)
          VALUES(%s,%s,%s,%s,%s,%s,now(),now()) ON CONFLICT(checksum) DO UPDATE SET extracted_text=COALESCE(mailbox_attachment_cache.extracted_text,EXCLUDED.extracted_text),updated_at=now()""",
          (attachment['checksum'],attachment.get('mime_type'),attachment.get('size'),attachment.get('text'),attachment.get('extraction_method'),attachment.get('attachment_type')))
        cur.execute("""INSERT INTO mailbox_attachments(id,mailbox_message_id,filename,mime_type,size,checksum,attachment_type,extraction_status,extracted_text_reference,created_at)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,now()) ON CONFLICT(mailbox_message_id,checksum) DO UPDATE SET filename=EXCLUDED.filename RETURNING *""",
          (aid,message_id,attachment.get('filename'),attachment.get('mime_type'),attachment.get('size'),attachment['checksum'],attachment.get('attachment_type'),attachment.get('extraction_status'),attachment['checksum']))
        return _rows(cur)[0]


def attachments_for_message(message_id: str, *, include_text: bool=False) -> list[dict[str,Any]]:
    fields="a.*,c.extraction_method"+(",c.extracted_text" if include_text else "")
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute(f"SELECT {fields} FROM mailbox_attachments a LEFT JOIN mailbox_attachment_cache c ON c.checksum=a.checksum WHERE a.mailbox_message_id=%s ORDER BY a.created_at",(message_id,));return _rows(cur)


def create_event(candidate_id: str, message_id: str, result: dict[str,Any], *, model: str, duration_ms: int) -> dict[str,Any]:
    event_id=_id(); interview=result.get('interview') or {}; offer=result.get('offer') or {}; company=result.get('company') or {}; job=result.get('job') or {}; recruiter=result.get('recruiter') or {}
    candidate_event={"primary_status":result.get("primary_status"),"confidence":result.get("confidence"),"structured_result":result,"review_status":"PENDING","visible_in_offer_review":True}
    visible=should_show_in_selection_offer_review(candidate_event)
    original_status=result.get('primary_status')
    status=original_status if visible else ('IGNORED_LOW_CONFIDENCE' if float(result.get('confidence') or 0)<.8 else 'IGNORED_NOT_OFFER_RELATED')
    review_status='PENDING' if visible else 'IGNORED'
    ignore_reason=None if visible else (result.get('ignore_reason') or 'LOW_CONFIDENCE_OR_NO_STRONG_OFFER_EVIDENCE')
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO ai_recruitment_events(id,candidate_id,mailbox_message_id,primary_status,confidence,company_name,company_domain,job_title,
          recruiter_name,recruiter_email,interview_date,interview_time,interview_mode,offered_ctc,currency,joining_date,offer_date,offer_expiry_date,
          structured_result,summary,requires_manual_review,review_status,visible_in_offer_review,original_primary_status,ignore_reason,ignored_at,
          ai_model,prompt_name,prompt_version,schema_version,processing_duration_ms,created_at,updated_at)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,
            CASE WHEN %s THEN NULL ELSE now() END,%s,'recruitment_email_status_extraction_v2','v2','selection_offer_event_v1',%s,now(),now()) RETURNING *""",
          (event_id,candidate_id,message_id,status,result['confidence'],company.get('name'),company.get('domain'),job.get('title'),recruiter.get('name'),recruiter.get('email'),interview.get('date'),interview.get('time'),interview.get('mode'),offer.get('offered_ctc'),offer.get('currency'),offer.get('joining_date'),offer.get('offer_date'),offer.get('offer_expiry_date'),json.dumps(result),result.get('summary'),bool(result.get('requires_manual_review')) if visible else False,review_status,visible,original_status if not visible else None,ignore_reason,visible,model,duration_ms))
        event=_rows(cur)[0]
        cur.execute("""INSERT INTO recruitment_audit_log(id,actor,role,action,candidate_id,source_id,new_value,created_at)
          VALUES(%s,'system','system','AI_RECRUITMENT_EVENT_CREATED',%s,%s,%s::jsonb,now())""",(_id(),candidate_id,event_id,json.dumps({'primary_status':result['primary_status'],'confidence':result['confidence'],'model':model})))
        if visible and result['confidence'] >= .8 and result['primary_status'] != 'MANUAL_REVIEW_REQUIRED':
            cur.execute("""INSERT INTO candidate_status_history(id,candidate_id,new_detected_status,source_type,source_id,confidence,created_at)
              VALUES(%s,%s,%s,'AI_RECRUITMENT_EVENT',%s,%s,now())""",(_id(),candidate_id,result['primary_status'],event_id,result['confidence']))
        from services.recruitment_mail_agent import OFFER_CASE_STATUSES
        if visible and result['primary_status'] in OFFER_CASE_STATUSES:
            cur.execute("""SELECT m.provider_thread_id,a.checksum FROM mailbox_messages m
              LEFT JOIN mailbox_attachments a ON a.mailbox_message_id=m.id WHERE m.id=%s
              ORDER BY CASE WHEN lower(COALESCE(a.filename,'')) ~ '(offer|appointment|joining)' THEN 0 ELSE 1 END LIMIT 1""",(message_id,))
            source=cur.fetchone() or (None,None)
            identity=source[1] or source[0] or '|'.join(str(value or '').strip().lower() for value in (company.get('name'),job.get('title')))
            raw_key='|'.join(str(value or '').strip().lower() for value in (candidate_id,identity))
            # An unknown offer must not collapse every offer for the candidate
            # into one case. PostgreSQL permits multiple NULL values in this
            # unique index, so only deduplicate when a stable identity exists.
            offer_case_key=__import__('hashlib').sha256(raw_key.encode()).hexdigest() if identity else None
            cur.execute("""INSERT INTO offer_verification_cases(id,candidate_id,ai_recruitment_event_id,offer_case_key,company_name,job_title,offered_ctc,currency,offer_date,joining_date,offer_expiry_date,verification_status,confidence,created_at,updated_at)
              VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'PENDING_REVIEW',%s,now(),now())
              ON CONFLICT(offer_case_key) DO UPDATE SET ai_recruitment_event_id=EXCLUDED.ai_recruitment_event_id,
                company_name=COALESCE(EXCLUDED.company_name,offer_verification_cases.company_name),
                job_title=COALESCE(EXCLUDED.job_title,offer_verification_cases.job_title),
                offered_ctc=COALESCE(EXCLUDED.offered_ctc,offer_verification_cases.offered_ctc),
                currency=COALESCE(EXCLUDED.currency,offer_verification_cases.currency),
                offer_date=COALESCE(EXCLUDED.offer_date,offer_verification_cases.offer_date),
                joining_date=COALESCE(EXCLUDED.joining_date,offer_verification_cases.joining_date),
                offer_expiry_date=COALESCE(EXCLUDED.offer_expiry_date,offer_verification_cases.offer_expiry_date),
                confidence=GREATEST(offer_verification_cases.confidence,EXCLUDED.confidence),updated_at=now()""",
              (_id(),candidate_id,event_id,offer_case_key,company.get('name'),job.get('title'),offer.get('offered_ctc'),offer.get('currency'),offer.get('offer_date'),offer.get('joining_date'),offer.get('offer_expiry_date'),result['confidence']))
            cur.execute("""INSERT INTO recruitment_audit_log(id,actor,role,action,candidate_id,source_id,new_value,created_at)
              VALUES(%s,'system','system','OFFER_CASE_CREATED',%s,%s,%s::jsonb,now())""",(_id(),candidate_id,event_id,json.dumps({'status':result['primary_status'],'confidence':result['confidence']})))
        cur.execute("SELECT confirmed_status FROM candidate_status_history WHERE candidate_id=%s AND confirmed_status IS NOT NULL ORDER BY reviewed_at DESC LIMIT 1",(candidate_id,));confirmed=cur.fetchone()
        conflict_pairs={('INTERVIEW_CANCELLED','INTERVIEW_RESCHEDULED'),('REJECTED','SELECTED'),('APPLICATION_WITHDRAWN','OFFER_LETTER_RECEIVED')}
        if confirmed and (confirmed[0],result['primary_status']) in conflict_pairs:
            cur.execute("""INSERT INTO recruitment_review_flags(id,candidate_id,event_id,flag_type,severity,details,created_at)
              VALUES(%s,%s,%s,'POTENTIAL_STATUS_CONFLICT','HIGH',%s::jsonb,now()) ON CONFLICT(candidate_id,event_id,flag_type) DO NOTHING""",(_id(),candidate_id,event_id,json.dumps({'confirmed_status':confirmed[0],'detected_status':result['primary_status']})))
        if offer.get('offered_ctc'):
            cur.execute("SELECT offered_ctc FROM offer_verification_cases WHERE candidate_id=%s AND ai_recruitment_event_id<>%s AND offered_ctc IS NOT NULL ORDER BY created_at DESC LIMIT 1",(candidate_id,event_id));previous_offer=cur.fetchone()
            if previous_offer and float(previous_offer[0])!=float(offer['offered_ctc']):
                cur.execute("""INSERT INTO recruitment_review_flags(id,candidate_id,event_id,flag_type,severity,details,created_at)
                  VALUES(%s,%s,%s,'POTENTIAL_OFFER_CONFLICT','HIGH',%s::jsonb,now()) ON CONFLICT(candidate_id,event_id,flag_type) DO NOTHING""",(_id(),candidate_id,event_id,json.dumps({'previous_ctc':float(previous_offer[0]),'detected_ctc':offer['offered_ctc']})))
        cur.execute("""UPDATE mailbox_messages SET processing_status=%s,ignore_reason=%s,
          ignored_at=CASE WHEN %s THEN ignored_at ELSE now() END,updated_at=now() WHERE id=%s""",
          ('EVENT_CREATED' if visible else status,ignore_reason,visible,message_id))
    return event


def create_or_reprocess_event(candidate_id: str, message_id: str, result: dict[str,Any], *, model: str, duration_ms: int, reason: str) -> dict[str,Any]:
    """Update the existing event in place, preserving its prior classification in audit."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM ai_recruitment_events WHERE mailbox_message_id=%s", (message_id,))
        existing_rows=_rows(cur)
    if not existing_rows:
        event=create_event(candidate_id,message_id,result,model=model,duration_ms=duration_ms)
        audit(actor='system',role='system',action='HISTORICAL_EMAIL_REPROCESSED',candidate_id=candidate_id,source_id=event['id'],previous=None,new={'new_classification':result['primary_status'],'prompt_version':'v2','reason':reason})
        return event
    previous=existing_rows[0];company=result.get('company') or {};job=result.get('job') or {};offer=result.get('offer') or {};recruiter=result.get('recruiter') or {}
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("""UPDATE ai_recruitment_events SET original_primary_status=COALESCE(original_primary_status,primary_status),
          primary_status=%s,confidence=%s,company_name=%s,company_domain=%s,job_title=%s,recruiter_name=%s,recruiter_email=%s,
          joining_date=%s,structured_result=%s::jsonb,summary=%s,requires_manual_review=%s,review_status='PENDING',
          visible_in_offer_review=true,ignore_reason=NULL,ignored_at=NULL,cleanup_version=NULL,ai_model=%s,
          prompt_name='recruitment_email_status_extraction_v2',prompt_version='v2',processing_duration_ms=%s,updated_at=now()
          WHERE id=%s RETURNING *""",
          (result['primary_status'],result['confidence'],company.get('name'),company.get('domain'),job.get('title'),recruiter.get('name'),recruiter.get('email'),offer.get('joining_date'),json.dumps(result),result.get('summary'),bool(result.get('requires_manual_review')),model,duration_ms,previous['id']))
        event=_rows(cur)[0]
        if result['primary_status'] in __import__('services.recruitment_mail_agent',fromlist=['OFFER_CASE_STATUSES']).OFFER_CASE_STATUSES:
            cur.execute("""INSERT INTO offer_verification_cases(id,candidate_id,ai_recruitment_event_id,company_name,job_title,joining_date,verification_status,confidence,created_at,updated_at)
              VALUES(%s,%s,%s,%s,%s,%s,'PENDING_REVIEW',%s,now(),now())
              ON CONFLICT(ai_recruitment_event_id) DO UPDATE SET company_name=EXCLUDED.company_name,job_title=EXCLUDED.job_title,
                joining_date=EXCLUDED.joining_date,verification_status='PENDING_REVIEW',confidence=EXCLUDED.confidence,updated_at=now()""",
              (_id(),candidate_id,event['id'],company.get('name'),job.get('title'),offer.get('joining_date'),result['confidence']))
        cur.execute("""INSERT INTO recruitment_audit_log(id,actor,role,action,candidate_id,source_id,previous_value,new_value,created_at)
          VALUES(%s,'system','system','HISTORICAL_EMAIL_RECLASSIFIED',%s,%s,%s::jsonb,%s::jsonb,now())""",
          (_id(),candidate_id,event['id'],json.dumps({'classification':previous.get('primary_status'),'prompt_version':previous.get('prompt_version')},default=str),json.dumps({'classification':result['primary_status'],'prompt_version':'v2','reason':reason},default=str)))
    return event


def audit(*,actor:str,role:str,action:str,candidate_id:str|None=None,source_id:str|None=None,previous:Any=None,new:Any=None,source_ip:str|None=None)->None:
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("INSERT INTO recruitment_audit_log(id,actor,role,action,candidate_id,source_id,previous_value,new_value,source_ip,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,now())",(_id(),actor,role,action,candidate_id,source_id,json.dumps(previous) if previous is not None else None,json.dumps(new) if new is not None else None,source_ip))


def list_flags(*,status:str|None=None,limit:int=100)->list[dict[str,Any]]:
    where=' WHERE review_status=%s' if status else ''
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute(f"SELECT * FROM recruitment_review_flags{where} ORDER BY created_at DESC LIMIT %s",(([status] if status else [])+[limit]));return _rows(cur)


def candidate_filter_ids(value:str)->set[str]:
    key=(value or '').strip().upper()
    with get_connection() as conn,conn.cursor() as cur:
        if key=='MAILBOX_CONNECTED':cur.execute("SELECT candidate_id FROM candidate_mailboxes WHERE connection_status='CONNECTED'")
        elif key=='MAILBOX_MONITORING_ENABLED':cur.execute("SELECT candidate_id FROM candidate_mailboxes WHERE monitoring_enabled=true")
        elif key=='MAILBOX_SYNC_FAILED':cur.execute("SELECT candidate_id FROM candidate_mailboxes WHERE connection_status='ERROR'")
        elif key=='PENDING_AI_REVIEW':
            predicate,params=qualified_event_sql('e');cur.execute(f"SELECT DISTINCT candidate_id FROM ai_recruitment_events e WHERE e.review_status='PENDING' AND {predicate}",params)
        elif key=='POTENTIAL_STATUS_CONFLICT':cur.execute("SELECT DISTINCT candidate_id FROM recruitment_review_flags WHERE flag_type LIKE 'POTENTIAL%%' AND review_status='PENDING'")
        elif key=='OFFER_VERIFIED':cur.execute("SELECT DISTINCT candidate_id FROM offer_verification_cases WHERE verification_status='VERIFIED'")
        else:cur.execute("SELECT DISTINCT candidate_id FROM ai_recruitment_events WHERE primary_status=%s",(key,))
        return {str(row[0]) for row in cur.fetchall()}


def list_events(*, candidate_id: str|None=None, review_status: str|None=None, limit:int=50, offset:int=0, active_only:bool=True) -> list[dict[str,Any]]:
    where=[]; params=[]
    if active_only:
        predicate,predicate_params=qualified_event_sql('e');where.append(predicate);params.extend(predicate_params)
    if candidate_id:where.append('e.candidate_id=%s');params.append(candidate_id)
    if review_status:where.append('e.review_status=%s');params.append(review_status)
    sql='''SELECT e.*,m.subject,m.sender_name,m.sender_email,m.sent_at AS email_sent_at
      FROM ai_recruitment_events e LEFT JOIN mailbox_messages m ON m.id=e.mailbox_message_id'''+((' WHERE '+' AND '.join(where)) if where else '')+' ORDER BY e.created_at DESC LIMIT %s OFFSET %s';params.extend([limit,offset])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql,params);rows=_rows(cur)
    return [row for row in rows if not active_only or should_show_in_selection_offer_review(row)]


def event_detail(event_id:str,*,include_evidence:bool=False)->dict[str,Any]|None:
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("""SELECT e.*,m.subject,m.sender_name,m.sender_email,m.sent_at AS email_sent_at,m.provider_message_id,m.provider_thread_id
          FROM ai_recruitment_events e LEFT JOIN mailbox_messages m ON m.id=e.mailbox_message_id WHERE e.id=%s""",(event_id,));rows=_rows(cur)
    if not rows:return None
    row=rows[0];row['attachments']=attachments_for_message(row['mailbox_message_id'],include_text=include_evidence) if row.get('mailbox_message_id') else []
    return row


def edit_event(event_id:str,changes:dict[str,Any],*,reviewer:str,notes:str='')->dict[str,Any]:
    allowed={'primary_status','confidence','company_name','company_domain','job_title','recruiter_name','recruiter_email','interview_date','interview_time','interview_mode','offered_ctc','currency','joining_date','offer_date','offer_expiry_date','summary','requires_manual_review'}
    clean={k:v for k,v in changes.items() if k in allowed}
    if 'primary_status' in clean:
        from services.recruitment_mail_agent import STATUSES
        if clean['primary_status'] not in STATUSES:raise ValueError('Invalid recruitment status')
    if 'confidence' in clean and not 0<=float(clean['confidence'])<=1:raise ValueError('Confidence must be between 0 and 1')
    if not clean:return event_detail(event_id) or {}
    before=event_detail(event_id) or {};assignments=', '.join(f'{k}=%s' for k in clean)
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute(f"UPDATE ai_recruitment_events SET {assignments},review_notes=%s,updated_at=now() WHERE id=%s RETURNING *",(*clean.values(),notes,event_id));rows=_rows(cur)
        if rows:cur.execute("INSERT INTO recruitment_audit_log(id,actor,role,action,candidate_id,source_id,previous_value,new_value,created_at) VALUES(%s,%s,'admin','EVENT_EDITED',%s,%s,%s::jsonb,%s::jsonb,now())",(_id(),reviewer,rows[0]['candidate_id'],event_id,json.dumps({k:before.get(k) for k in clean},default=str),json.dumps(clean,default=str)))
    return rows[0] if rows else {}


def mailbox_stats(mailbox_id:str)->dict[str,int]:
    with get_connection() as conn,conn.cursor() as cur:
        predicate,params=qualified_event_sql('e')
        cur.execute(f"""SELECT count(*) FILTER(WHERE {predicate}) important_emails,
          count(*) FILTER(WHERE e.primary_status IN('SELECTED','FINAL_SELECTION_CONFIRMED') AND {predicate}) selection_events,
          count(*) FILTER(WHERE e.primary_status IN('OFFER_INDICATION','OFFER_IN_PROGRESS','OFFER_APPROVED','OFFER_LETTER_RECEIVED','APPOINTMENT_LETTER_RECEIVED','OFFER_ACCEPTED') AND {predicate}) offer_events,
          count(*) FILTER(WHERE e.primary_status='OFFER_LETTER_RECEIVED' AND {predicate}) offer_letters,
          count(*) FILTER(WHERE e.review_status='PENDING' AND {predicate}) pending_reviews
          FROM mailbox_messages m LEFT JOIN ai_recruitment_events e ON e.mailbox_message_id=m.id WHERE m.mailbox_id=%s""",params*5+[mailbox_id]);names=[d.name for d in cur.description];return dict(zip(names,cur.fetchone()))


def review_event(event_id:str, action:str, reviewer:str, notes:str='', changes:dict[str,Any]|None=None)->dict[str,Any]:
    status={'approve':'APPROVED','reject':'REJECTED','false-positive':'FALSE_POSITIVE','duplicate':'DUPLICATE'}.get(action,action.upper())
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE ai_recruitment_events SET review_status=%s,reviewed_by=%s,reviewed_at=now(),review_notes=%s,updated_at=now() WHERE id=%s RETURNING *",(status,reviewer,notes,event_id)); rows=_rows(cur)
        if rows:
            cur.execute("INSERT INTO recruitment_audit_log(id,actor,role,action,candidate_id,source_id,new_value,created_at) VALUES(%s,%s,'admin',%s,%s,%s,%s::jsonb,now())",(_id(),reviewer,'EVENT_'+status,rows[0]['candidate_id'],event_id,json.dumps({'notes':notes,'changes':changes or {}})))
            if status=='APPROVED':
                cur.execute("""UPDATE candidate_status_history SET confirmed_status=%s,reviewed_by=%s,reviewed_at=now(),review_notes=%s
                  WHERE id=(SELECT id FROM candidate_status_history WHERE source_id=%s ORDER BY created_at DESC LIMIT 1)""",(rows[0]['primary_status'],reviewer,notes,event_id))
    return rows[0] if rows else {}


def list_offer_cases(*, status:str|None=None, limit:int=50, offset:int=0)->list[dict[str,Any]]:
    predicate,predicate_params=qualified_event_sql('e')
    where=('c.verification_status=%s AND ' if status else "c.verification_status<>'IGNORED' AND ")+predicate
    params=([status] if status else [])+predicate_params+[limit,offset]
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute(f"SELECT c.* FROM offer_verification_cases c JOIN ai_recruitment_events e ON e.id=c.ai_recruitment_event_id WHERE {where} ORDER BY c.created_at DESC LIMIT %s OFFSET %s",params);return _rows(cur)


def review_offer(case_id:str, action:str, reviewer:str, notes:str='')->dict[str,Any]:
    status={'verify':'VERIFIED','reject':'REJECTED','duplicate':'DUPLICATE','dispute':'CANDIDATE_DISPUTED'}.get(action)
    if not status:raise ValueError('Invalid offer review action')
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute("UPDATE offer_verification_cases SET verification_status=%s,reviewed_by=%s,reviewed_at=now(),notes=%s,updated_at=now() WHERE id=%s RETURNING *",(status,reviewer,notes,case_id));rows=_rows(cur)
        if rows:cur.execute("INSERT INTO recruitment_audit_log(id,actor,role,action,candidate_id,source_id,new_value,created_at) VALUES(%s,%s,'admin',%s,%s,%s,%s::jsonb,now())",(_id(),reviewer,'OFFER_'+status,rows[0]['candidate_id'],case_id,json.dumps({'notes':notes})))
    return rows[0] if rows else {}
