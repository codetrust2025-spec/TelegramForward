"""Recruitment pre-filter, cleaning, schema validation and AI processing."""
from __future__ import annotations
import hashlib, html, json, os, re
from datetime import date
from typing import Any
from core.ai_gateway import AIGatewayError, chat_structured, configured_models
from core import recruitment_mail_store as store

STATUSES=["INTERVIEW_INVITATION","INTERVIEW_SCHEDULED","INTERVIEW_RESCHEDULED","INTERVIEW_CANCELLED","ASSESSMENT_RECEIVED","ASSESSMENT_COMPLETED","SHORTLISTED","TECHNICAL_ROUND","MANAGERIAL_ROUND","HR_ROUND","HR_DISCUSSION","SELECTED","OFFER_INDICATION","OFFER_LETTER_RECEIVED","OFFER_ACCEPTED","OFFER_DECLINED","JOINING_CONFIRMED","JOINING_DATE_CHANGED","BACKGROUND_VERIFICATION","DOCUMENT_VERIFICATION","REJECTED","APPLICATION_ON_HOLD","APPLICATION_WITHDRAWN","NO_RELEVANT_STATUS","UNCLEAR","MANUAL_REVIEW_REQUIRED"]
TRACKED_STATUSES={"SELECTED","OFFER_INDICATION","OFFER_LETTER_RECEIVED","OFFER_ACCEPTED","JOINING_CONFIRMED","JOINING_DATE_CHANGED","BACKGROUND_VERIFICATION","DOCUMENT_VERIFICATION"}
OUTCOME_PHRASES=(
    "you have been selected", "you are selected", "selected for the position",
    "selected for the role", "pleased to inform you that you have been selected",
    "congratulations on your selection", "offer of employment", "employment offer",
    "job offer", "offer letter", "appointment letter", "letter of intent",
    "intent to offer", "pleased to offer", "we are delighted to offer",
    "we would like to offer", "offer acceptance", "accept the offer",
    "joining date", "date of joining", "joining confirmation", "onboarding confirmation",
    "pre-employment verification", "background verification", "document verification",
)
OUTCOME_REGEXES=(
    re.compile(r"\b(?:selected|chosen)\s+(?:you\s+)?(?:for|as)\s+(?:the\s+)?(?:position|role|post)\b", re.I),
    re.compile(r"\b(?:offer|appointment|joining)\s+(?:confirmation|details|document|letter)\b", re.I),
    re.compile(r"\b(?:annual|total)\s+(?:compensation|ctc)\b", re.I),
)
NOISE_PHRASES=(
    "job recommendation", "job recommendations", "jobs recommended", "recommended jobs",
    "jobs for you", "job alert", "new job alert", "matching jobs", "similar jobs",
    "open positions", "career opportunities", "vacancies", "vacancy", "hiring now",
    "apply now", "view job", "weekly newsletter", "unsubscribe",
)

SCHEMA={"type":"object","required":["schema_version","is_recruitment_related","primary_status","confidence","candidate","company","job","recruiter","interview","offer","attachments","evidence","risk_flags","requires_manual_review","summary","recommended_action"],"properties":{
 "schema_version":{"const":"recruitment_event_v1"},"is_recruitment_related":{"type":"boolean"},"primary_status":{"type":"string","enum":STATUSES},"confidence":{"type":"number","minimum":0,"maximum":1},
 "candidate":{"type":"object","properties":{"name":{"type":["string","null"]},"email":{"type":["string","null"]}},"required":["name","email"]},
 "company":{"type":"object","properties":{"name":{"type":["string","null"]},"domain":{"type":["string","null"]}},"required":["name","domain"]},
 "job":{"type":"object","properties":{"title":{"type":["string","null"]},"employment_type":{"type":["string","null"]},"location":{"type":["string","null"]}},"required":["title","employment_type","location"]},
 "recruiter":{"type":"object","properties":{"name":{"type":["string","null"]},"email":{"type":["string","null"]}},"required":["name","email"]},
 "interview":{"type":"object","properties":{k:{"type":["string","null"]} for k in ["date","time","timezone","mode","round","location","meeting_link"]},"required":["date","time","timezone","mode","round","location","meeting_link"]},
 "offer":{"type":"object","properties":{"offer_detected":{"type":"boolean"},"offer_letter_detected":{"type":"boolean"},"offer_date":{"type":["string","null"]},"offered_ctc":{"type":["number","null"]},"currency":{"type":["string","null"]},"joining_date":{"type":["string","null"]},"offer_expiry_date":{"type":["string","null"]}},"required":["offer_detected","offer_letter_detected","offer_date","offered_ctc","currency","joining_date","offer_expiry_date"]},
 "attachments":{"type":"array","items":{"type":"object","properties":{"type":{"type":"string"},"filename":{"type":"string"},"confidence":{"type":"number"}},"required":["type","filename","confidence"]}},"evidence":{"type":"array","items":{"type":"object","properties":{"source":{"type":"string"},"text":{"type":"string"}},"required":["source","text"]}},"risk_flags":{"type":"array","items":{"type":"string"}},"requires_manual_review":{"type":"boolean"},"summary":{"type":"string"},"recommended_action":{"type":"string"}},"additionalProperties":False}

def clean_email(text:str)->str:
    value=html.unescape(re.sub(r'<[^>]+>',' ',text or ''))
    value=re.split(r'(?im)^\s*(?:on .+ wrote:|from:|unsubscribe|confidentiality notice)',value,maxsplit=1)[0]
    return re.sub(r'\s+',' ',value).strip()[:30000]

def relevance_score(subject:str,body:str,filenames:list[str]|None=None,thread_context:list[dict[str,Any]]|None=None)->float:
    """Return a strict job-outcome score, not a general recruitment score."""
    subject_blob=(subject or '').lower();body_blob=(body or '').lower();file_blob=' '.join(filenames or []).lower();thread_blob=' '.join(str(item.get('subject') or '') for item in (thread_context or [])).lower();blob=' '.join([subject_blob,body_blob,file_blob,thread_blob])
    explicit=[phrase for phrase in OUTCOME_PHRASES if phrase in blob]
    regex_hit=any(pattern.search(blob) for pattern in OUTCOME_REGEXES)
    attachment_hit=bool(re.search(r'\b(?:offer|appointment|joining|selection|loi)[\w ._-]*\.(?:pdf|docx?)\b',file_blob,re.I))
    noise=any(phrase in subject_blob for phrase in NOISE_PHRASES)
    # Marketing/listing subjects are ignored even when the body contains generic
    # words such as "offer". A real attached offer/appointment letter overrides it.
    if noise and not attachment_hit:return 0.0
    if not explicit and not regex_hit and not attachment_hit:return 0.0
    score=.62 + min(.24,.08*len(explicit)) + (.1 if regex_hit else 0) + (.18 if attachment_hit else 0)
    return min(1.0,score)

def content_hash(value:str)->str:return hashlib.sha256(value.encode('utf-8','replace')).hexdigest()

def analyze(message:dict[str,Any],attachment_texts:list[dict[str,str]]|None=None)->tuple[dict[str,Any],str,int]:
    cleaned=clean_email(message.get('body') or '')
    prompt="""You are a strict job-outcome extraction system. Track only confirmed selection, offer indication, offer/appointment letter, offer acceptance, joining confirmation or date change, background verification, and document verification. Ignore job recommendations, vacancy listings, job alerts, applications, assessments, interview invitations, interview schedules, rejections, newsletters, and marketing. Extract only facts supported by the supplied content. Distinguish offer indication from a confirmed attached offer letter. Salary discussion alone is not an offer. If the email is not one of the tracked outcomes, return NO_RELEVANT_STATUS and is_recruitment_related=false. Return JSON matching the schema; use null for unknown values. Every tracked outcome requires administrator review. Prompt: recruitment_email_status_extraction v2.\n"""
    payload={"subject":message.get('subject'),"sender":message.get('sender_email'),"recipient":message.get('recipient_email'),"cc":message.get('cc_metadata') or [],"email_date":str(message.get('sent_at')),"body":cleaned,"thread_context":(message.get('thread_context') or [])[-5:],"attachments":attachment_texts or []}
    last_error=None
    models=list(dict.fromkeys(model for model in [configured_models()['text'],configured_models()['fallback']] if model))
    attempts=1+max(0,min(1,int(os.getenv('AI_RECRUITMENT_MAX_RETRIES','1'))))
    for model in models:
        if not model:continue
        for _ in range(attempts):
            try:
                res=chat_structured(messages=[{"role":"system","content":prompt},{"role":"user","content":json.dumps(payload,ensure_ascii=False)}],schema=SCHEMA,model=model)
                parsed=parse_model_json(res.content);validate_result(parsed);return parsed,res.model,res.duration_ms
            except (AIGatewayError,ValueError,json.JSONDecodeError) as exc:last_error=exc
    raise AIGatewayError(str(last_error or 'AI analysis failed'))

def validate_result(v:dict[str,Any])->None:
    from jsonschema import Draft202012Validator
    errors=list(Draft202012Validator(SCHEMA).iter_errors(v))
    if errors:raise ValueError('invalid recruitment JSON: '+errors[0].message)
    if v.get('schema_version')!='recruitment_event_v1' or v.get('primary_status') not in STATUSES:raise ValueError('invalid schema or status')
    confidence=v.get('confidence');
    if not isinstance(confidence,(int,float)) or not 0<=confidence<=1:raise ValueError('invalid confidence')
    for section,fields in {'interview':['date'],'offer':['offer_date','joining_date','offer_expiry_date']}.items():
        for field in fields:
            value=(v.get(section) or {}).get(field)
            if value:
                try:date.fromisoformat(value)
                except (TypeError,ValueError):raise ValueError(f'invalid ISO date: {section}.{field}')
    interview_time=(v.get('interview') or {}).get('time')
    if interview_time and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?',interview_time):
        raise ValueError('invalid ISO time: interview.time')
    if confidence<.9:v['requires_manual_review']=True

def parse_model_json(raw:str)->dict[str,Any]:
    value=(raw or '').strip()
    try:return json.loads(value)
    except json.JSONDecodeError:pass
    # One bounded, non-evaluating repair pass: remove fences, keep the first
    # object, and remove trailing commas. Never use eval or execute model text.
    value=re.sub(r'^```(?:json)?|```$','',value,flags=re.I|re.M).strip()
    start=value.find('{');end=value.rfind('}')
    if start<0 or end<=start:raise ValueError('AI output did not contain a JSON object')
    value=re.sub(r',\s*([}\]])',r'\1',value[start:end+1])
    return json.loads(value)

def process_message(mailbox:dict[str,Any],decoded:dict[str,Any],attachment_texts:list[dict[str,str]]|None=None)->dict[str,Any]|None:
    from services.mail_attachment_processor import extract_attachment
    decoded['body']=clean_email(decoded.get('body') or '');decoded['message_hash']=content_hash('|'.join([decoded.get('sender_email') or '',decoded.get('subject') or '',str(decoded.get('sent_at'))]));decoded['body_hash']=content_hash(decoded['body'])
    score=relevance_score(decoded.get('subject',''),decoded['body'],[x.get('filename','') for x in (attachment_texts or [])],decoded.get('thread_context'))
    row,created=store.insert_message(mailbox,decoded,score)
    if created and store.is_duplicate_content(mailbox['candidate_id'],row['id'],decoded['message_hash'],decoded['body_hash']):
        store.mark_message_status(row['id'],'DUPLICATE_CONTENT');return None
    if not created or score<float(os.getenv('AI_RECRUITMENT_FILTER_THRESHOLD','0.55')):return None
    processed_attachments=[extract_attachment(a) if a.get('data') is not None else a for a in (attachment_texts or [])]
    if created:
        for attachment in processed_attachments:
            if attachment.get('checksum'):store.save_attachment(row['id'],attachment)
    safe_attachments=[{k:a.get(k) for k in ('filename','mime_type','text','attachment_type','extraction_status')} for a in processed_attachments]
    try:
        result,model,duration=analyze(decoded,safe_attachments)
        if not result.get('is_recruitment_related') or result.get('primary_status') not in TRACKED_STATUSES:
            store.mark_message_status(row['id'],'IGNORED_NOT_JOB_OUTCOME');return None
        result['requires_manual_review']=True
        event=store.create_event(mailbox['candidate_id'],row['id'],result,model=model,duration_ms=duration)
        from services.recruitment_notifications import notify_detection
        notify_detection(event);return event
    except Exception:
        fallback={"schema_version":"recruitment_event_v1","is_recruitment_related":True,"primary_status":"MANUAL_REVIEW_REQUIRED","confidence":0,"candidate":{"name":None,"email":decoded.get('recipient_email')},"company":{"name":None,"domain":None},"job":{"title":None,"employment_type":None,"location":None},"recruiter":{"name":decoded.get('sender_name'),"email":decoded.get('sender_email')},"interview":{k:None for k in ["date","time","timezone","mode","round","location","meeting_link"]},"offer":{"offer_detected":False,"offer_letter_detected":False,"offer_date":None,"offered_ctc":None,"currency":None,"joining_date":None,"offer_expiry_date":None},"attachments":[],"evidence":[],"risk_flags":["AI_PROCESSING_FAILED"],"requires_manual_review":True,"summary":"Potential selection or offer email requires manual review.","recommended_action":"Review the source email for a confirmed job outcome."}
        return store.create_event(mailbox['candidate_id'],row['id'],fallback,model='unavailable',duration_ms=0)
