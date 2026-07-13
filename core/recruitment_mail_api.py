"""Authenticated API for candidate mailbox tracking and AI review."""
from __future__ import annotations
import base64, hashlib, hmac, json, os, time
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from core import recruitment_mail_store as store
from core.dashboard_access import operator_profile, require_fleet_admin, assert_candidate_row_access
from features import candidate_store
from services.gmail_mailbox_provider import authorization_url, exchange_code, encrypt_credentials, GmailMailboxProvider

def enabled():return os.getenv('AI_INTERVIEW_OFFER_TRACKING_ENABLED','false').lower()=='true'
def offer_enabled():return os.getenv('AI_OFFER_VERIFICATION_ENABLED','false').lower()=='true'
def _guard():
    if not enabled():raise HTTPException(404,'AI interview and offer tracking is disabled')
def _state(data:dict)->str:
    raw=base64.urlsafe_b64encode(json.dumps({**data,'exp':int(time.time())+600}).encode()).decode().rstrip('=');key=(os.getenv('DASHBOARD_AUTH_SECRET') or os.getenv('DASHBOARD_PASSWORD') or '').encode()
    if not key:raise HTTPException(503,'OAuth state signing is not configured')
    return raw+'.'+hmac.new(key,raw.encode(),hashlib.sha256).hexdigest()
def _read_state(value:str)->dict:
    raw,sig=value.rsplit('.',1);key=(os.getenv('DASHBOARD_AUTH_SECRET') or os.getenv('DASHBOARD_PASSWORD') or '').encode()
    if not hmac.compare_digest(sig,hmac.new(key,raw.encode(),hashlib.sha256).hexdigest()):raise HTTPException(400,'Invalid OAuth state')
    data=json.loads(base64.urlsafe_b64decode(raw+'==='));
    if data['exp']<time.time():raise HTTPException(400,'OAuth request expired')
    return data

def install_recruitment_mail_routes(app):
    @app.get('/api/ai-recruitment/config')
    async def feature_config(request:Request):
        require_fleet_admin(request)
        return {'status':'ok','enabled':enabled(),'mailbox_sync_enabled':os.getenv('AI_MAILBOX_SYNC_ENABLED','false').lower()=='true','offer_verification_enabled':offer_enabled()}
    @app.get('/api/candidates/{candidate_id}/mailbox')
    async def mailbox(candidate_id:str,request:Request):
        _guard(); row=candidate_store.get_candidate(candidate_id)
        if not row:raise HTTPException(404,'Candidate not found')
        assert_candidate_row_access(request,row); mb=store.mailbox_for_candidate(candidate_id)
        if mb:mb={k:v for k,v in mb.items() if k!='credential_ciphertext'}
        stats=store.mailbox_stats(mb['id']) if mb else {}
        return {'status':'ok','mailbox':mb,'stats':stats,'events':store.list_events(candidate_id=candidate_id,limit=20)}
    @app.post('/api/candidates/{candidate_id}/mailbox/connect')
    async def connect(candidate_id:str,request:Request,body:dict):
        _guard();profile=require_fleet_admin(request);row=candidate_store.get_candidate(candidate_id)
        if not row:raise HTTPException(404,'Candidate not found')
        email=str(body.get('email_address') or '').strip().lower()
        if '@' not in email:raise HTTPException(400,'Valid Gmail address required')
        mb=store.upsert_mailbox(candidate_id,email,connection_status='AUTHORIZING');store.audit(actor=profile.get('username') or 'admin',role='admin',action='MAILBOX_CONNECT_STARTED',candidate_id=candidate_id,source_id=mb['id'],new={'email_address':email},source_ip=request.client.host if request.client else None)
        redirect=str(body.get('redirect_uri') or os.getenv('GOOGLE_OAUTH_REDIRECT_URI') or '').strip()
        if not redirect:raise HTTPException(503,'GOOGLE_OAUTH_REDIRECT_URI is not configured')
        return {'status':'ok','authorization_url':authorization_url(_state({'candidate_id':candidate_id,'email':email,'actor':profile.get('username'),'redirect_uri':redirect}),redirect)}
    @app.get('/api/candidate-mailboxes/oauth/google/callback')
    async def callback(code:str,state:str):
        _guard();data=_read_state(state);tokens=exchange_code(code,data['redirect_uri'])
        if not tokens.get('refresh_token'):raise HTTPException(400,'Google did not provide offline mailbox authorization; reconnect and grant access')
        cipher=encrypt_credentials({'refresh_token':tokens.get('refresh_token'),'access_token':tokens.get('access_token')})
        gmail_profile=GmailMailboxProvider(cipher).verify_connection();authorized=str(gmail_profile.get('emailAddress') or '').strip().lower()
        if authorized!=str(data['email']).strip().lower():raise HTTPException(400,'The authorized Gmail account does not match the selected mailbox address')
        mb=store.upsert_mailbox(data['candidate_id'],data['email'],connection_status='CONNECTED',credential_ciphertext=cipher);store.audit(actor=data.get('actor') or 'admin',role='admin',action='MAILBOX_CONNECTED',candidate_id=data['candidate_id'],source_id=mb['id'],new={'email_address':data['email']})
        return RedirectResponse('/?view=ai-recruitment&mailbox=connected')
    @app.post('/api/candidates/{candidate_id}/mailbox/verify')
    async def verify(candidate_id:str,request:Request):
        _guard();require_fleet_admin(request);mb=store.mailbox_for_candidate(candidate_id)
        if not mb or not mb.get('credential_ciphertext'):raise HTTPException(400,'Mailbox is not connected')
        gmail_profile=await __import__('asyncio').to_thread(GmailMailboxProvider(mb['credential_ciphertext']).verify_connection);store.update_mailbox(mb['id'],{'connection_status':'CONNECTED','last_error_message':None});profile=operator_profile(request);store.audit(actor=profile.get('username') or 'admin',role='admin',action='MAILBOX_VERIFIED',candidate_id=candidate_id,source_id=mb['id']);return {'status':'ok','email_address':gmail_profile.get('emailAddress')}
    @app.post('/api/candidates/{candidate_id}/mailbox/sync')
    async def sync(candidate_id:str,request:Request):
        _guard();profile=require_fleet_admin(request);mb=store.mailbox_for_candidate(candidate_id)
        if not mb:raise HTTPException(404,'Mailbox not configured')
        job=store.enqueue_sync(mb['id'],requested_by=profile.get('username') or 'admin');store.audit(actor=profile.get('username') or 'admin',role='admin',action='MANUAL_SYNC_REQUESTED',candidate_id=candidate_id,source_id=job['id'],source_ip=request.client.host if request.client else None);return {'status':'ok','job':job}
    @app.patch('/api/candidates/{candidate_id}/mailbox/settings')
    async def settings(candidate_id:str,request:Request,body:dict):
        _guard();profile=require_fleet_admin(request);mb=store.mailbox_for_candidate(candidate_id)
        if not mb:raise HTTPException(404,'Mailbox not configured')
        value=bool(body.get('monitoring_enabled'));updated=store.update_mailbox(mb['id'],{'monitoring_enabled':value});updated.pop('credential_ciphertext',None);store.audit(actor=profile.get('username') or 'admin',role='admin',action='MONITORING_ENABLED' if value else 'MONITORING_DISABLED',candidate_id=candidate_id,source_id=mb['id'],previous={'monitoring_enabled':mb.get('monitoring_enabled')},new={'monitoring_enabled':value});return {'status':'ok','mailbox':updated}
    @app.delete('/api/candidates/{candidate_id}/mailbox')
    async def disconnect(candidate_id:str,request:Request):
        _guard();profile=require_fleet_admin(request);mb=store.mailbox_for_candidate(candidate_id)
        if not mb:return {'status':'ok'}
        store.update_mailbox(mb['id'],{'credential_ciphertext':None,'monitoring_enabled':False,'connection_status':'DISCONNECTED','sync_cursor':None,'provider_history_id':None});store.audit(actor=profile.get('username') or 'admin',role='admin',action='MAILBOX_DISCONNECTED',candidate_id=candidate_id,source_id=mb['id']);return {'status':'ok'}
    @app.post('/api/candidate-mailboxes/bulk-import')
    async def bulk_import(request:Request,body:dict):
        _guard();require_fleet_admin(request);created=[]
        for row in (body.get('mailboxes') or [])[:500]:
            cid=str(row.get('candidate_id') or '');email=str(row.get('email_address') or '').strip().lower()
            if candidate_store.get_candidate(cid) and '@' in email:created.append(store.upsert_mailbox(cid,email,monitoring_enabled=False,connection_status='PENDING'))
        profile=operator_profile(request);store.audit(actor=profile.get('username') or 'admin',role='admin',action='BULK_MAILBOX_IMPORT_COMPLETED',new={'count':len(created)});return {'status':'ok','count':len(created)}
    @app.get('/api/candidates/{candidate_id}/recruitment-timeline')
    async def timeline(candidate_id:str,request:Request):
        _guard();row=candidate_store.get_candidate(candidate_id)
        if not row:raise HTTPException(404,'Candidate not found')
        assert_candidate_row_access(request,row);return {'status':'ok','events':store.list_events(candidate_id=candidate_id,limit=100)}
    @app.get('/api/candidates/{candidate_id}/recruitment-events')
    async def recruitment_events(candidate_id:str,request:Request,limit:int=50,offset:int=0):
        _guard();row=candidate_store.get_candidate(candidate_id)
        if not row:raise HTTPException(404,'Candidate not found')
        assert_candidate_row_access(request,row);return {'status':'ok','events':store.list_events(candidate_id=candidate_id,limit=min(max(limit,1),100),offset=max(offset,0))}
    @app.get('/api/ai-recruitment/review')
    async def review_list(request:Request,status:str|None=None,limit:int=50,offset:int=0):
        _guard();require_fleet_admin(request);return {'status':'ok','events':store.list_events(review_status=status,limit=min(limit,100),offset=max(offset,0))}
    @app.get('/api/ai-recruitment/events/{event_id}')
    async def event_get(event_id:str,request:Request):
        _guard();require_fleet_admin(request);row=store.event_detail(event_id,include_evidence=True)
        if not row:raise HTTPException(404,'Event not found')
        return {'status':'ok','event':row}
    @app.patch('/api/ai-recruitment/events/{event_id}')
    async def event_edit(event_id:str,request:Request,body:dict):
        _guard();profile=require_fleet_admin(request)
        try:row=store.edit_event(event_id,body.get('changes') or {},reviewer=profile.get('username') or 'admin',notes=str(body.get('notes') or ''))
        except ValueError as exc:raise HTTPException(400,str(exc))
        if not row:raise HTTPException(404,'Event not found')
        return {'status':'ok','event':row}
    @app.post('/api/ai-recruitment/events/{event_id}/{action}')
    async def review_action(event_id:str,action:str,request:Request,body:dict):
        _guard();profile=require_fleet_admin(request)
        if action not in ('approve','reject','false-positive','duplicate'):raise HTTPException(404,'Unknown review action')
        row=store.review_event(event_id,action,profile.get('username') or 'admin',str(body.get('notes') or ''))
        if not row:raise HTTPException(404,'Event not found')
        return {'status':'ok','event':row}
    @app.get('/api/ai-recruitment/dashboard')
    async def dashboard(request:Request):
        _guard();require_fleet_admin(request)
        from core.db.connection import get_connection
        with get_connection() as conn,conn.cursor() as cur:
            cur.execute("""SELECT (SELECT count(*) FROM candidate_mailboxes WHERE connection_status='CONNECTED') connected_mailboxes,(SELECT count(*) FROM candidate_mailboxes WHERE monitoring_enabled) monitored_mailboxes,(SELECT count(*) FROM mailbox_sync_jobs WHERE status='COMPLETED' AND completed_at::date=current_date) successful_syncs_today,(SELECT count(*) FROM mailbox_sync_jobs WHERE status='FAILED' AND created_at::date=current_date) failed_syncs_today,(SELECT COALESCE(sum(messages_fetched),0) FROM mailbox_sync_jobs WHERE created_at::date=current_date) emails_scanned_today,(SELECT count(*) FROM ai_recruitment_events WHERE created_at::date=current_date) recruitment_emails_detected,(SELECT count(*) FROM ai_recruitment_events WHERE review_status='PENDING') pending_reviews,(SELECT count(*) FROM ai_recruitment_events WHERE primary_status LIKE 'INTERVIEW%%') interviews_detected,(SELECT count(*) FROM ai_recruitment_events WHERE primary_status='SELECTED') selections_detected,(SELECT count(*) FROM offer_verification_cases) offers_detected,(SELECT count(*) FROM ai_recruitment_events WHERE primary_status='OFFER_LETTER_RECEIVED') offer_letters_detected,(SELECT count(*) FROM ai_recruitment_events WHERE primary_status='JOINING_CONFIRMED') joining_confirmations,(SELECT count(*) FROM offer_verification_cases WHERE verification_status='VERIFIED') verified_offers,(SELECT count(*) FROM ai_recruitment_events WHERE review_status='FALSE_POSITIVE') false_positives,(SELECT count(*) FROM ai_recruitment_events WHERE primary_status='MANUAL_REVIEW_REQUIRED') ai_failures""");cols=[d.name for d in cur.description];metrics=dict(zip(cols,cur.fetchone()))
            cur.execute("SELECT created_at::date day,count(*) count FROM ai_recruitment_events WHERE created_at>=current_date-30 GROUP BY 1 ORDER BY 1");events_by_day=[{'day':str(r[0]),'count':r[1]} for r in cur.fetchall()]
            cur.execute("SELECT primary_status,count(*) count FROM ai_recruitment_events GROUP BY 1 ORDER BY 2 DESC");status_distribution=[{'status':r[0],'count':r[1]} for r in cur.fetchall()]
        return {'status':'ok','metrics':metrics,'charts':{'events_by_day':events_by_day,'status_distribution':status_distribution},'flags':store.list_flags(status='PENDING')}
    @app.get('/api/offer-verification')
    async def offer_list(request:Request,status:str|None=None,limit:int=50,offset:int=0):
        _guard();require_fleet_admin(request)
        if not offer_enabled():return {'status':'ok','cases':[],'enabled':False}
        return {'status':'ok','cases':store.list_offer_cases(status=status,limit=min(limit,100),offset=max(offset,0))}
    @app.get('/api/offer-verification/{case_id}')
    async def offer_get(case_id:str,request:Request):
        _guard();require_fleet_admin(request)
        if not offer_enabled():raise HTTPException(404,'AI offer verification is disabled')
        rows=[r for r in store.list_offer_cases(limit=1000) if r['id']==case_id]
        if not rows:raise HTTPException(404,'Offer case not found')
        return {'status':'ok','case':rows[0]}
    @app.post('/api/offer-verification/{case_id}/{action}')
    async def offer_review(case_id:str,action:str,request:Request,body:dict):
        _guard();profile=require_fleet_admin(request)
        if not offer_enabled():raise HTTPException(404,'AI offer verification is disabled')
        if action not in ('verify','reject','duplicate','dispute'):raise HTTPException(404,'Unknown offer action')
        row=store.review_offer(case_id,action,profile.get('username') or 'admin',str(body.get('notes') or ''))
        if not row:raise HTTPException(404,'Offer case not found')
        return {'status':'ok','case':row}
    @app.get('/api/ai-recruitment/metrics')
    async def recruitment_metrics(request:Request):
        _guard();require_fleet_admin(request)
        from core.db.connection import get_connection
        with get_connection() as conn,conn.cursor() as cur:
            cur.execute("""SELECT
              (SELECT count(*) FROM mailbox_sync_jobs) mailbox_sync_total,
              (SELECT count(*) FROM mailbox_sync_jobs WHERE status='COMPLETED') mailbox_sync_success_total,
              (SELECT count(*) FROM mailbox_sync_jobs WHERE status IN('FAILED','DEAD_LETTER')) mailbox_sync_failure_total,
              (SELECT COALESCE(sum(messages_fetched),0) FROM mailbox_sync_jobs) mailbox_messages_fetched_total,
              (SELECT count(*) FROM ai_recruitment_events) ai_recruitment_request_total,
              (SELECT count(*) FROM ai_recruitment_events WHERE primary_status<>'MANUAL_REVIEW_REQUIRED') ai_recruitment_success_total,
              (SELECT count(*) FROM ai_recruitment_events WHERE primary_status='MANUAL_REVIEW_REQUIRED') ai_recruitment_failure_total,
              (SELECT COALESCE(avg(processing_duration_ms),0) FROM ai_recruitment_events) ai_processing_duration_ms_avg,
              (SELECT count(*) FROM mailbox_sync_jobs WHERE status='QUEUED') queue_depth,
              (SELECT count(*) FROM ai_recruitment_events WHERE primary_status LIKE 'INTERVIEW%%') interview_detected_total,
              (SELECT count(*) FROM ai_recruitment_events WHERE primary_status='OFFER_INDICATION') offer_indication_total,
              (SELECT count(*) FROM ai_recruitment_events WHERE primary_status='OFFER_LETTER_RECEIVED') offer_letter_detected_total,
              (SELECT count(*) FROM offer_verification_cases WHERE verification_status='VERIFIED') verified_offer_total,
              (SELECT count(*) FROM ai_recruitment_events WHERE review_status='FALSE_POSITIVE') false_positive_total""");names=[d.name for d in cur.description];values=dict(zip(names,cur.fetchone()))
        return {'status':'ok','metrics':values}
