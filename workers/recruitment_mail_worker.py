"""Durable mailbox scheduler and worker."""
from __future__ import annotations
import asyncio, logging, os
from datetime import timedelta
from core import recruitment_mail_store as store
from services.gmail_mailbox_provider import GmailMailboxProvider, decode_gmail_message
from services.recruitment_mail_agent import process_message

logger=logging.getLogger('teleautomation.recruitment_mail_worker')

class RecruitmentMailWorker:
    def __init__(self):self._task=None;self._stopping=False;self._jobs=set()
    def start(self):
        if self._task is None or self._task.done():self._stopping=False;self._task=asyncio.create_task(self._run(),name='recruitment-mail-worker')
    async def stop(self):
        self._stopping=True
        if self._task:self._task.cancel();await asyncio.gather(self._task,return_exceptions=True);self._task=None
        for job in self._jobs:job.cancel()
        if self._jobs:await asyncio.gather(*self._jobs,return_exceptions=True)
        self._jobs.clear()
    async def _run(self):
        while not self._stopping:
            try:
                if os.getenv('AI_INTERVIEW_OFFER_TRACKING_ENABLED','false').lower()=='true' and os.getenv('AI_MAILBOX_SYNC_ENABLED','false').lower()=='true':
                    await asyncio.to_thread(self.schedule_due)
                    self._jobs={task for task in self._jobs if not task.done()}
                    maximum=max(1,min(20,int(os.getenv('AI_MAIL_SYNC_MAX_CONCURRENCY','5'))))
                    while len(self._jobs)<maximum:
                        job=await asyncio.to_thread(store.claim_job)
                        if not job:break
                        self._jobs.add(asyncio.create_task(asyncio.to_thread(self.process_job,job),name=f"mailbox-sync-{job['id']}"))
                    if self._jobs:
                        await asyncio.wait(self._jobs,timeout=1,return_when=asyncio.FIRST_COMPLETED);continue
            except asyncio.CancelledError:raise
            except Exception:logger.exception('Mailbox worker loop failed')
            await asyncio.sleep(5)
    def schedule_due(self):
        from core.db.connection import get_connection
        with get_connection() as conn,conn.cursor() as cur:
            cur.execute("""INSERT INTO mailbox_sync_jobs(id,mailbox_id,status,scheduled_for,requested_by,created_at)
              SELECT gen_random_uuid()::text,m.id,'QUEUED',now(),'scheduler',now() FROM candidate_mailboxes m
              WHERE m.monitoring_enabled=true AND m.connection_status='CONNECTED' AND COALESCE(m.next_sync_at,now())<=now()
              AND NOT EXISTS(SELECT 1 FROM mailbox_sync_jobs j WHERE j.mailbox_id=m.id AND j.status IN('QUEUED','RUNNING'))""")
            mins=max(1,int(os.getenv('AI_MAIL_SYNC_INTERVAL_MINUTES','15')))
            cur.execute("UPDATE candidate_mailboxes SET next_sync_at=now()+(%s||' minutes')::interval WHERE monitoring_enabled=true AND COALESCE(next_sync_at,now())<=now()",(mins,))
    def process_job(self,job):
        mailbox=store.mailbox_by_id(job['mailbox_id']);counts={'fetched':0,'processed':0,'events':0}
        if not mailbox:store.finish_job(job['id'],status='FAILED',error='Mailbox not found');return
        try:
            store.update_mailbox(mailbox['id'],{'last_sync_attempt_at':store.now()})
            provider=GmailMailboxProvider(mailbox['credential_ciphertext']); batch=max(1,min(100,int(os.getenv('AI_MAIL_SYNC_BATCH_SIZE','50'))))
            refs,cursor=provider.fetch_new_messages(mailbox.get('provider_history_id') or mailbox.get('sync_cursor'),batch_size=batch);counts['fetched']=len(refs)
            for ref in refs:
                raw=provider.fetch_message(ref['id']);decoded=decode_gmail_message(raw,mailbox['email_address'])
                if decoded.get('provider_thread_id'):
                    try:
                        thread=provider.fetch_thread(decoded['provider_thread_id'])[-5:]
                        decoded['thread_context']=[{k:v for k,v in decode_gmail_message(item,mailbox['email_address']).items() if k in ('subject','sender_name','sender_email','sent_at')} for item in thread]
                    except Exception:
                        logger.info('Thread context unavailable mailbox=%s message=%s',mailbox['id'],ref['id'])
                attachments=provider.fetch_attachments(raw)
                event=process_message(mailbox,decoded,attachments);counts['processed']+=1;counts['events']+=1 if event else 0
            store.update_mailbox(mailbox['id'],{'provider_history_id':cursor,'sync_cursor':cursor,'connection_status':'CONNECTED','last_successful_sync_at':store.now(),'failed_sync_count':0,'last_error_code':None,'last_error_message':None})
            store.finish_job(job['id'],status='COMPLETED',counts=counts)
        except Exception as exc:
            failures=int(mailbox.get('failed_sync_count') or 0)+1;delay=min(240,2**min(failures,8))
            store.update_mailbox(mailbox['id'],{'connection_status':'ERROR','failed_sync_count':failures,'last_error_code':type(exc).__name__,'last_error_message':str(exc)[:400],'next_sync_at':store.now()+timedelta(minutes=delay)})
            store.finish_job(job['id'],status='FAILED',counts=counts,error=str(exc)[:400]);final=store.retry_job(job['id'],delay_minutes=delay,error=str(exc)[:400],max_attempts=max(1,int(os.getenv('AI_MAIL_SYNC_MAX_RETRIES','5'))));logger.warning('Mailbox sync failed mailbox=%s code=%s',mailbox['id'],type(exc).__name__)
            if failures>=3 or final=='DEAD_LETTER':
                from services.recruitment_notifications import notify_system
                notify_system('Mailbox synchronization failed',f"Mailbox {mailbox['id']} requires administrator attention.",f"mailbox-failure:{mailbox['id']}")

recruitment_mail_worker=RecruitmentMailWorker()
