"""Precision-first selection and offer email detection."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from datetime import date, datetime
from typing import Any

from core import recruitment_mail_store as store
from core.ai_gateway import AIGatewayError, chat_structured, configured_models

VISIBLE_STATUSES = [
    "SELECTED", "FINAL_SELECTION_CONFIRMED", "OFFER_INDICATION",
    "OFFER_IN_PROGRESS", "OFFER_APPROVED", "OFFER_LETTER_RECEIVED",
    "APPOINTMENT_LETTER_RECEIVED", "OFFER_ACCEPTED", "JOINING_CONFIRMED",
    "JOINED", "POST_SELECTION_ONBOARDING", "MANUAL_REVIEW_REQUIRED",
]
INTERNAL_STATUSES = ["IGNORED_NOT_OFFER_RELATED", "IGNORED_LOW_CONFIDENCE"]
STATUSES = VISIBLE_STATUSES + INTERNAL_STATUSES
TRACKED_STATUSES = set(VISIBLE_STATUSES)
OFFER_CASE_STATUSES = {
    "OFFER_INDICATION", "OFFER_IN_PROGRESS", "OFFER_APPROVED",
    "OFFER_LETTER_RECEIVED", "APPOINTMENT_LETTER_RECEIVED", "OFFER_ACCEPTED",
    "JOINING_CONFIRMED", "JOINED", "POST_SELECTION_ONBOARDING",
}

STATUS_PRIORITY = [
    "JOINED", "JOINING_CONFIRMED", "POST_SELECTION_ONBOARDING",
    "OFFER_ACCEPTED", "APPOINTMENT_LETTER_RECEIVED", "OFFER_LETTER_RECEIVED",
    "OFFER_APPROVED", "OFFER_IN_PROGRESS", "FINAL_SELECTION_CONFIRMED",
    "SELECTED", "OFFER_INDICATION", "SHORTLISTED",
]

STATUS_SIGNALS = [
    ("JOINED", ("welcome aboard", "welcome to the organization", "reported for joining", "joined the company", "employment commenced")),
    ("JOINING_CONFIRMED", ("your date of joining will be", "your joining date is", "date of joining", "expected joining date", "please join on", "report for joining on", "reporting date", "joining is confirmed", "joining confirmed")),
    ("POST_SELECTION_ONBOARDING", ("employee onboarding", "post-selection onboarding", "complete onboarding formalities", "complete pre-joining formalities", "pre-joining formalities", "onboarding has started", "complete onboarding before joining")),
    ("OFFER_ACCEPTED", ("offer acceptance", "accepted your offer", "accept the offer", "offer has been accepted")),
    ("APPOINTMENT_LETTER_RECEIVED", ("appointment letter attached", "letter of appointment", "appointment letter")),
    ("OFFER_LETTER_RECEIVED", ("offer letter attached", "find your offer letter", "offer letter has been released", "employment offer attached", "offer of employment")),
    ("OFFER_APPROVED", ("offer has been approved", "offer is approved", "offer approved")),
    ("OFFER_IN_PROGRESS", ("offer is currently being processed", "processing your offer", "offer is being prepared", "offer under preparation")),
    ("FINAL_SELECTION_CONFIRMED", ("final selection confirmed", "selection has been confirmed", "finally selected")),
    ("SELECTED", ("you have been selected", "you are selected", "selected for the position", "selected for the role", "congratulations on your selection")),
    ("OFFER_INDICATION", ("we are pleased to offer you", "we are delighted to offer you", "we would like to offer you", "planning to release your offer", "intent to offer", "employment offer", "compensation offered", "annual ctc offered")),
    ("SHORTLISTED", ("you have been shortlisted", "being shortlisted", "shortlisted for the role", "shortlisted for the position")),
]

NOISE_RULES = [
    ("JOB_RECOMMENDATION", ("job recommendation", "recommended jobs", "jobs matching your profile", "new jobs for you", "jobs for you", "similar jobs", "suggested opportunities")),
    ("JOB_ALERT", ("job alert", "hiring alert", "featured jobs", "new openings", "daily job", "weekly job")),
    ("JOB_PORTAL_MARKETING", ("apply now", "increase profile visibility", "upgrade account", "premium subscription", "career newsletter", "unsubscribe")),
    ("PROFILE_NOTIFICATION", ("resume viewed", "profile viewed", "searched your profile")),
    ("APPLICATION_UPDATE", ("application received", "thank you for applying", "application submitted", "application under review")),
    ("ASSESSMENT", ("assessment invitation", "coding test invitation", "complete the assessment")),
    ("INTERVIEW", ("interview invitation", "interview scheduled", "interview has been scheduled", "interview rescheduled", "interview reminder", "interview cancelled", "technical round", "hr round")),
    ("REJECTION", ("not selected", "regret to inform", "not moving forward", "rejection")),
]

SPECIAL_CONTEXT = {
    "BACKGROUND_VERIFICATION": ("background verification", "pre-employment verification", "document verification"),
    "SALARY": ("salary discussion", "compensation discussion", "ctc discussion"),
    "JOINING_REQUEST": ("confirm your date of joining", "please confirm your joining date"),
}

SCHEMA = {
    "type": "object",
    "required": [
        "schema_version", "is_recruitment_related", "is_selection_or_offer_related",
        "should_create_review_record", "status", "confidence", "ignore_reason",
        "candidate", "company", "job", "recruiter", "interview", "offer",
        "attachments", "evidence", "risk_flags", "requires_manual_review",
        "summary", "recommended_action",
    ],
    "properties": {
        "schema_version": {"const": "selection_offer_event_v1"},
        "is_recruitment_related": {"type": "boolean"},
        "is_selection_or_offer_related": {"type": "boolean"},
        "should_create_review_record": {"type": "boolean"},
        "status": {"type": "string", "enum": STATUSES},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "ignore_reason": {"type": ["string", "null"]},
        "candidate": {"type": "object", "properties": {"name": {"type": ["string", "null"]}, "email": {"type": ["string", "null"]}}, "required": ["name", "email"]},
        "company": {"type": "object", "properties": {"name": {"type": ["string", "null"]}, "domain": {"type": ["string", "null"]}}, "required": ["name", "domain"]},
        "job": {"type": "object", "properties": {"title": {"type": ["string", "null"]}, "employment_type": {"type": ["string", "null"]}, "location": {"type": ["string", "null"]}}, "required": ["title", "employment_type", "location"]},
        "recruiter": {"type": "object", "properties": {"name": {"type": ["string", "null"]}, "email": {"type": ["string", "null"]}}, "required": ["name", "email"]},
        "interview": {"type": "object", "properties": {key: {"type": ["string", "null"]} for key in ["date", "time", "timezone", "mode", "round", "location", "meeting_link"]}, "required": ["date", "time", "timezone", "mode", "round", "location", "meeting_link"]},
        "offer": {"type": "object", "properties": {
            "offer_detected": {"type": "boolean"}, "offer_letter_detected": {"type": "boolean"},
            "appointment_letter_detected": {"type": "boolean"}, "offer_date": {"type": ["string", "null"]},
            "offered_ctc": {"type": ["number", "null"]}, "currency": {"type": ["string", "null"]},
            "joining_date": {"type": ["string", "null"]}, "offer_expiry_date": {"type": ["string", "null"]},
        }, "required": ["offer_detected", "offer_letter_detected", "appointment_letter_detected", "offer_date", "offered_ctc", "currency", "joining_date", "offer_expiry_date"]},
        "attachments": {"type": "array", "items": {"type": "object", "properties": {"type": {"type": "string"}, "filename": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["type", "filename", "confidence"]}},
        "evidence": {"type": "array", "items": {"type": "object", "properties": {
            "source": {"type": "string", "enum": ["EMAIL_SUBJECT", "EMAIL_BODY", "ATTACHMENT", "THREAD_CONTEXT"]},
            "meaning": {"type": "string"}, "text": {"type": "string", "minLength": 3, "maxLength": 500},
        }, "required": ["source", "meaning", "text"]}},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "requires_manual_review": {"type": "boolean"}, "summary": {"type": "string"},
        "recommended_action": {"type": "string"},
    },
    "additionalProperties": False,
}


def clean_email(text: str) -> str:
    value = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    value = re.split(r"(?im)^\s*(?:on .+ wrote:|from:|unsubscribe|confidentiality notice)", value, maxsplit=1)[0]
    return re.sub(r"\s+", " ", value).strip()[:30000]


def _source_texts(subject: str, body: str, attachments: list[dict[str, Any]] | None, thread_context: list[dict[str, Any]] | None) -> dict[str, list[str]]:
    return {
        "EMAIL_SUBJECT": [clean_email(subject)],
        "EMAIL_BODY": [clean_email(body)],
        "ATTACHMENT": [clean_email(str(item.get("text") or "")) for item in (attachments or [])],
        "THREAD_CONTEXT": [clean_email(" ".join(str(item.get(key) or "") for key in ("subject", "body"))) for item in (thread_context or [])[-5:]],
    }


def _matching_statuses(text: str) -> list[tuple[str, str]]:
    lowered = text.lower()
    matches = []
    for status, phrases in STATUS_SIGNALS:
        for phrase in phrases:
            if phrase in lowered:
                matches.append((status, phrase))
                break
    return matches


def _evidence_excerpt(text: str, phrase: str) -> str:
    clean = clean_email(text)
    start = clean.casefold().find(phrase.casefold())
    if start < 0:
        return phrase
    left = max(clean.rfind(".", 0, start), clean.rfind("!", 0, start), clean.rfind("?", 0, start)) + 1
    endings = [pos for mark in ".!?" if (pos := clean.find(mark, start)) >= 0]
    right = min(endings) + 1 if endings else min(len(clean), start + 240)
    return clean[left:right].strip()[:500]


def _extract_joining_date(text: str) -> str | None:
    month = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    patterns = [rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month})\s*,?\s*(\d{{4}})\b", rf"\b({month})\s+(\d{{1,2}})(?:st|nd|rd|th)?\s*,?\s*(\d{{4}})\b"]
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        parts = match.groups()
        candidate = " ".join(parts if index == 0 else (parts[1], parts[0], parts[2]))
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(candidate, fmt).date().isoformat()
            except ValueError:
                pass
    return None


def _extract_context(subject: str, body: str, sender_email: str) -> tuple[str | None, str | None, str | None]:
    job = None
    for pattern in (r"\brole of\s+([A-Za-z][A-Za-z0-9 /&+.#-]{1,80}?)(?=[.,;\n]|\byour date\b)", r"[-–—]\s*([A-Za-z][A-Za-z0-9 /&+.#-]{1,80}?)\s+Role\b"):
        match = re.search(pattern, subject + "\n" + body, re.I)
        if match:
            job = match.group(1).strip(" -–—")
            break
    company = None
    company_match = re.search(r"\b([A-Z][A-Z0-9 &.,'-]{2,100}?(?:PVT\.?\s*LTD\.?|PRIVATE LIMITED|SERVICES INDIA PVT\.?\s*LTD\.?|LIMITED))\b", body)
    if company_match:
        company = re.sub(r"\s+", " ", company_match.group(1)).strip()
    domain = sender_email.rsplit("@", 1)[-1].lower() if "@" in sender_email else None
    return company, job, domain


def prefilter_decision(subject: str, body: str, sender_name: str = "", sender_email: str = "", attachments: list[dict[str, Any]] | None = None, thread_context: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sources = _source_texts(subject, body, attachments, thread_context)
    evidence = []
    detected = []
    for source, values in sources.items():
        for value in values:
            for status, phrase in _matching_statuses(value):
                detected.append(status)
                evidence.append({"source": source, "meaning": status, "text": _evidence_excerpt(value, phrase)})
    for attachment in attachments or []:
        filename = str(attachment.get("filename") or "").lower()
        attachment_text = clean_email(str(attachment.get("text") or ""))
        lowered_text = attachment_text.lower()
        if "appointment" in filename and any(token in lowered_text for token in ("employment", "appointed", "appointment")):
            detected.append("APPOINTMENT_LETTER_RECEIVED")
            evidence.append({"source": "ATTACHMENT", "meaning": "APPOINTMENT_LETTER_RECEIVED", "text": next(token for token in ("employment", "appointed", "appointment") if token in lowered_text)})
        elif "offer" in filename and any(token in lowered_text for token in ("employment offer", "offered employment", "offer of employment")):
            detected.append("OFFER_LETTER_RECEIVED")
            evidence.append({"source": "ATTACHMENT", "meaning": "OFFER_LETTER_RECEIVED", "text": next(token for token in ("employment offer", "offered employment", "offer of employment") if token in lowered_text)})
    direct_text = " ".join(sources["EMAIL_SUBJECT"] + sources["EMAIL_BODY"])
    if "JOINING_CONFIRMED" in detected and not _extract_joining_date(direct_text) and "please confirm your date of joining" in direct_text.lower():
        detected=[value for value in detected if value!="JOINING_CONFIRMED"]
        evidence=[item for item in evidence if item.get("meaning")!="JOINING_CONFIRMED"]
    combined_context = " ".join(sources["EMAIL_BODY"] + sources["ATTACHMENT"] + sources["THREAD_CONTEXT"]).lower()
    has_confirmed_context = any(token in combined_context for token in ("selected", "selection confirmed", "offer letter", "employment offer", "offer approved", "onboarding"))
    for source, values in sources.items():
        for value in values:
            lowered = value.lower()
            if has_confirmed_context and any(phrase in lowered for phrase in SPECIAL_CONTEXT["BACKGROUND_VERIFICATION"]):
                detected.append("POST_SELECTION_ONBOARDING")
                phrase = next(p for p in SPECIAL_CONTEXT["BACKGROUND_VERIFICATION"] if p in lowered)
                evidence.append({"source": source, "meaning": "POST_SELECTION_ONBOARDING", "text": phrase})
            if has_confirmed_context and any(phrase in lowered for phrase in SPECIAL_CONTEXT["SALARY"]):
                detected.append("OFFER_INDICATION")
                phrase = next(p for p in SPECIAL_CONTEXT["SALARY"] if p in lowered)
                evidence.append({"source": source, "meaning": "OFFER_INDICATION", "text": phrase})
            if has_confirmed_context and any(phrase in lowered for phrase in SPECIAL_CONTEXT["JOINING_REQUEST"]):
                detected.append("JOINING_CONFIRMED")
                phrase = next(p for p in SPECIAL_CONTEXT["JOINING_REQUEST"] if p in lowered)
                evidence.append({"source": source, "meaning": "JOINING_CONFIRMED", "text": phrase})
    if detected:
        status = next((candidate for candidate in STATUS_PRIORITY if candidate in detected), detected[0])
        # A shortlist by itself remains ordinary recruitment noise. Stronger
        # evidence later in the complete message always wins.
        if status == "SHORTLISTED":
            return {"qualified": False, "score": 0.0, "status": "IGNORED_NOT_OFFER_RELATED", "evidence": [], "ignore_reason": "SHORTLIST_ONLY"}
        combined = " ".join(sources["EMAIL_SUBJECT"] + sources["EMAIL_BODY"])
        company, job, domain = _extract_context(subject, body, sender_email)
        conflict = "SHORTLISTED" in detected and status != "SHORTLISTED"
        if subject and any(token in subject.casefold() for token in ("congratulations", "next steps")):
            evidence.append({"source":"EMAIL_SUBJECT","meaning":status,"text":clean_email(subject)[:500]})
        return {
            "qualified": True, "score": max(0.94 if status == "JOINING_CONFIRMED" else 0.92, min(0.99, 0.9 + 0.02 * len(evidence))),
            "status": status, "evidence": evidence[:8], "ignore_reason": None,
            "joining_date": _extract_joining_date(combined) if status in {"JOINING_CONFIRMED", "POST_SELECTION_ONBOARDING", "JOINED"} else None,
            "company_name": company, "company_domain": domain, "job_title": job,
            "risk_flags": ["WORDING_STATUS_CONFLICT"] if conflict else [],
            "requires_manual_review": conflict,
        }
    haystack = " ".join([subject, sender_name, sender_email, body]).lower()
    for reason, phrases in NOISE_RULES:
        if any(phrase in haystack for phrase in phrases):
            return {"qualified": False, "score": 0.0, "status": "IGNORED_NOT_OFFER_RELATED", "evidence": [], "ignore_reason": reason}
    return {"qualified": False, "score": 0.0, "status": "IGNORED_NOT_OFFER_RELATED", "evidence": [], "ignore_reason": "NO_SELECTION_OR_OFFER_SIGNAL"}


def relevance_score(subject: str, body: str, filenames: list[str] | None = None, thread_context: list[dict[str, Any]] | None = None) -> float:
    # Filenames alone are intentionally excluded from qualification.
    return float(prefilter_decision(subject, body, thread_context=thread_context)["score"])


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def _evidence_supported(item: dict[str, Any], sources: dict[str, list[str]]) -> bool:
    needle = clean_email(str(item.get("text") or "")).casefold()
    return bool(needle) and any(needle in value.casefold() for value in sources.get(str(item.get("source") or ""), []))


def validate_result(value: dict[str, Any], message: dict[str, Any] | None = None, attachments: list[dict[str, Any]] | None = None) -> None:
    from jsonschema import Draft202012Validator
    errors = list(Draft202012Validator(SCHEMA).iter_errors(value))
    if errors:
        raise ValueError("invalid selection/offer JSON: " + errors[0].message)
    confidence = float(value["confidence"])
    positive = bool(value["is_selection_or_offer_related"] and value["should_create_review_record"] and value["status"] in TRACKED_STATUSES)
    if not positive:
        value["status"] = "IGNORED_NOT_OFFER_RELATED"
        value["should_create_review_record"] = False
        value["requires_manual_review"] = False
        value["ignore_reason"] = value.get("ignore_reason") or "AI_NOT_OFFER_RELATED"
        return
    sources = _source_texts((message or {}).get("subject", ""), (message or {}).get("body", ""), attachments, (message or {}).get("thread_context"))
    if not value["evidence"] or not all(_evidence_supported(item, sources) for item in value["evidence"]):
        raise ValueError("selection/offer evidence is missing or unsupported")
    if confidence < 0.8:
        value.update(status="IGNORED_LOW_CONFIDENCE", should_create_review_record=False, requires_manual_review=False, ignore_reason="LOW_CONFIDENCE")
    elif confidence < 0.9:
        value.update(status="MANUAL_REVIEW_REQUIRED", requires_manual_review=True, ignore_reason=None)
    else:
        value["requires_manual_review"] = True
        value["ignore_reason"] = None
    for field in ("offer_date", "joining_date", "offer_expiry_date"):
        raw = (value.get("offer") or {}).get(field)
        if raw:
            try:
                date.fromisoformat(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid ISO date: offer.{field}") from exc


def parse_model_json(raw: str) -> dict[str, Any]:
    value = (raw or "").strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        value = re.sub(r"^```(?:json)?|```$", "", value, flags=re.I | re.M).strip()
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("AI output did not contain a JSON object")
        return json.loads(re.sub(r",\s*([}\]])", r"\1", value[start:end + 1]))


def analyze(message: dict[str, Any], attachment_texts: list[dict[str, str]] | None = None) -> tuple[dict[str, Any], str, int]:
    prompt = """You are TeleAutomation recruitment_email_status_extraction_v2. Analyze the complete message before choosing a status; never stop at the first keyword. Choose the furthest confirmed recruitment stage. Priority: JOINED, JOINING_CONFIRMED, OFFER_ACCEPTED, APPOINTMENT_LETTER_RECEIVED, OFFER_LETTER_RECEIVED, OFFER_APPROVED, OFFER_IN_PROGRESS, FINAL_SELECTION_CONFIRMED, SELECTED, OFFER_INDICATION. An explicit joining date overrides SHORTLISTED, INTERVIEW, HR_DISCUSSION, and SELECTED unless clearly tentative or conditional. Shortlist-only and job recommendations are not offer-review events. When wording says shortlisted but stronger joining/offer/onboarding evidence exists, keep the stronger status, add WORDING_STATUS_CONFLICT, and require manual review. Evidence must be verbatim from the full EMAIL_SUBJECT, EMAIL_BODY, ATTACHMENT, or THREAD_CONTEXT. Return only JSON matching selection_offer_event_v1."""
    payload = {"subject": message.get("subject"), "sender": message.get("sender_email"), "recipient": message.get("recipient_email"), "email_date": str(message.get("sent_at")), "body": clean_email(message.get("body") or ""), "thread_context": (message.get("thread_context") or [])[-5:], "attachments": attachment_texts or []}
    last_error = None
    models = list(dict.fromkeys(model for model in [configured_models()["text"], configured_models()["fallback"]] if model))
    attempts = 1 + max(0, min(1, int(os.getenv("AI_RECRUITMENT_MAX_RETRIES", "1"))))
    for model in models:
        for _ in range(attempts):
            try:
                response = chat_structured(messages=[{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}], schema=SCHEMA, model=model)
                parsed = parse_model_json(response.content)
                decision = prefilter_decision(message.get("subject", ""), message.get("body", ""), message.get("sender_name", ""), message.get("sender_email", ""), attachment_texts, message.get("thread_context"))
                parsed_rank = STATUS_PRIORITY.index(parsed["status"]) if parsed.get("status") in STATUS_PRIORITY else len(STATUS_PRIORITY)
                if decision.get("qualified") and STATUS_PRIORITY.index(decision["status"]) < parsed_rank:
                    parsed["status"] = decision["status"]
                    parsed["confidence"] = max(float(parsed.get("confidence") or 0), float(decision["score"]))
                    parsed["evidence"] = decision["evidence"]
                if decision.get("qualified"):
                    parsed["is_recruitment_related"] = True
                    parsed["is_selection_or_offer_related"] = True
                    parsed["should_create_review_record"] = True
                    parsed["company"] = {"name": decision.get("company_name") or (parsed.get("company") or {}).get("name"), "domain": decision.get("company_domain") or (parsed.get("company") or {}).get("domain")}
                    parsed["job"] = {**(parsed.get("job") or {}), "title": decision.get("job_title") or (parsed.get("job") or {}).get("title")}
                    parsed["offer"] = {**(parsed.get("offer") or {}), "joining_date": decision.get("joining_date") or (parsed.get("offer") or {}).get("joining_date")}
                    parsed["risk_flags"] = list(dict.fromkeys((parsed.get("risk_flags") or []) + (decision.get("risk_flags") or [])))
                    parsed["requires_manual_review"] = bool(parsed.get("requires_manual_review") or decision.get("requires_manual_review"))
                validate_result(parsed, message, attachment_texts)
                parsed["primary_status"] = parsed["status"]
                return parsed, response.model, response.duration_ms
            except (AIGatewayError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
    raise AIGatewayError(str(last_error or "AI analysis failed"))


def _fallback_result(decoded: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    status = decision.get("status") or "MANUAL_REVIEW_REQUIRED"
    conflict = bool(decision.get("requires_manual_review"))
    return {
        "schema_version": "selection_offer_event_v1", "is_recruitment_related": True,
        "is_selection_or_offer_related": True, "should_create_review_record": True,
        "status": status, "primary_status": status,
        "confidence": float(decision.get("score") or 0.8), "ignore_reason": None,
        "candidate": {"name": None, "email": decoded.get("recipient_email")},
        "company": {"name": decision.get("company_name"), "domain": decision.get("company_domain")}, "job": {"title": decision.get("job_title"), "employment_type": None, "location": None},
        "recruiter": {"name": decoded.get("sender_name"), "email": decoded.get("sender_email")},
        "interview": {key: None for key in ["date", "time", "timezone", "mode", "round", "location", "meeting_link"]},
        "offer": {"offer_detected": True, "offer_letter_detected": status == "OFFER_LETTER_RECEIVED", "appointment_letter_detected": status == "APPOINTMENT_LETTER_RECEIVED", "offer_date": None, "offered_ctc": None, "currency": None, "joining_date": decision.get("joining_date"), "offer_expiry_date": None},
        "attachments": [], "evidence": decision["evidence"], "risk_flags": list(dict.fromkeys(["AI_PROCESSING_FAILED"] + decision.get("risk_flags", []))),
        "requires_manual_review": True if conflict or status in TRACKED_STATUSES else False, "summary": (f"A joining date was communicated for the {decision.get('job_title') or 'candidate'} role." if status == "JOINING_CONFIRMED" else "Strong selection or offer evidence requires administrator review."),
        "recommended_action": ("Verify the joining confirmation." if status == "JOINING_CONFIRMED" else "Review the source evidence and confirm the exact status."),
    }


def process_message(mailbox: dict[str, Any], decoded: dict[str, Any], attachment_texts: list[dict[str, str]] | None = None, *, reprocess: bool = False) -> dict[str, Any] | None:
    from services.mail_attachment_processor import extract_attachment
    decoded["body"] = clean_email(decoded.get("body") or "")
    decoded["message_hash"] = content_hash("|".join([decoded.get("sender_email") or "", decoded.get("subject") or "", str(decoded.get("sent_at"))]))
    decoded["body_hash"] = content_hash(decoded["body"])
    processed = [extract_attachment(item) if item.get("data") is not None else item for item in (attachment_texts or [])]
    safe = [{key: item.get(key) for key in ("filename", "mime_type", "text", "attachment_type", "extraction_status", "checksum")} for item in processed]
    decision = prefilter_decision(decoded.get("subject", ""), decoded["body"], decoded.get("sender_name", ""), decoded.get("sender_email", ""), safe, decoded.get("thread_context"))
    row, created = store.insert_message(mailbox, decoded, float(decision["score"]))
    if not created and not reprocess:
        return None
    previous_status=row.get("processing_status")
    if not reprocess and store.is_duplicate_content(mailbox["candidate_id"], row["id"], decoded["message_hash"], decoded["body_hash"]):
        store.mark_message_status(row["id"], "DUPLICATE_CONTENT", reason="DUPLICATE_MESSAGE")
        return None
    for attachment in processed:
        if attachment.get("checksum"):
            store.save_attachment(row["id"], attachment)
    if not decision["qualified"]:
        store.mark_message_status(row["id"], "IGNORED_NOT_OFFER_RELATED", reason=decision["ignore_reason"])
        if reprocess: store.mark_reprocessed(row["id"],previous_status,"IGNORED_NOT_OFFER_RELATED","HISTORICAL_RULE_RESCAN")
        return None
    if not reprocess and store.is_duplicate_offer_attachment(mailbox["candidate_id"], row["id"]):
        store.mark_message_status(row["id"], "DUPLICATE_OFFER_ATTACHMENT", reason="DUPLICATE_OFFER_ATTACHMENT")
        return None
    try:
        result, model, duration = analyze(decoded, safe)
    except Exception:
        result, model, duration = _fallback_result(decoded, decision), "unavailable", 0
    if not result.get("is_selection_or_offer_related") or not result.get("should_create_review_record") or result.get("primary_status") not in TRACKED_STATUSES:
        status = "IGNORED_LOW_CONFIDENCE" if result.get("primary_status") == "IGNORED_LOW_CONFIDENCE" else "IGNORED_NOT_OFFER_RELATED"
        store.mark_message_status(row["id"], status, reason=result.get("ignore_reason") or "AI_NOT_OFFER_RELATED")
        return None
    if float(result.get("confidence") or 0) < 0.8 or not result.get("evidence"):
        store.mark_message_status(row["id"], "IGNORED_LOW_CONFIDENCE", reason="LOW_CONFIDENCE_OR_NO_EVIDENCE")
        return None
    if not reprocess and store.is_duplicate_thread_status(mailbox["candidate_id"], row["id"], result["primary_status"]):
        store.mark_message_status(row["id"], "DUPLICATE_OFFER_EVENT", reason="DUPLICATE_THREAD_STATUS")
        return None
    event = (store.create_or_reprocess_event(mailbox["candidate_id"],row["id"],result,model=model,duration_ms=duration,reason="HISTORICAL_RULE_RESCAN") if reprocess else store.create_event(mailbox["candidate_id"], row["id"], result, model=model, duration_ms=duration))
    if reprocess: store.mark_reprocessed(row["id"],previous_status,"EVENT_CREATED","HISTORICAL_RULE_RESCAN")
    from services.recruitment_notifications import notify_detection
    notify_detection(event)
    return event
