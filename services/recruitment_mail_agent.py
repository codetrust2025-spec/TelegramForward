"""Precision-first selection and offer email detection."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from datetime import date
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

STATUS_SIGNALS = [
    ("APPOINTMENT_LETTER_RECEIVED", ("appointment letter attached", "letter of appointment", "appointment letter")),
    ("OFFER_LETTER_RECEIVED", ("offer letter attached", "find your offer letter", "offer letter has been released", "employment offer attached", "offer of employment")),
    ("OFFER_ACCEPTED", ("offer acceptance", "accepted your offer", "accept the offer", "offer has been accepted")),
    ("JOINED", ("welcome aboard", "welcome to the organization", "reported for joining", "joined the company", "employment commenced")),
    ("JOINING_CONFIRMED", ("your joining date is", "date of joining is", "joining date confirmed", "report for joining")),
    ("POST_SELECTION_ONBOARDING", ("employee onboarding", "post-selection onboarding", "complete onboarding formalities", "pre-joining formalities", "onboarding has started")),
    ("OFFER_APPROVED", ("offer has been approved", "offer is approved", "offer approved")),
    ("OFFER_IN_PROGRESS", ("offer is currently being processed", "processing your offer", "offer is being prepared", "offer under preparation")),
    ("FINAL_SELECTION_CONFIRMED", ("final selection confirmed", "selection has been confirmed", "finally selected")),
    ("SELECTED", ("you have been selected", "you are selected", "selected for the position", "selected for the role", "congratulations on your selection")),
    ("OFFER_INDICATION", ("we are pleased to offer you", "we are delighted to offer you", "we would like to offer you", "planning to release your offer", "intent to offer", "employment offer", "compensation offered", "annual ctc offered")),
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


def _match_status(text: str) -> tuple[str | None, str | None]:
    lowered = text.lower()
    for status, phrases in STATUS_SIGNALS:
        for phrase in phrases:
            if phrase in lowered:
                return status, phrase
    return None, None


def prefilter_decision(subject: str, body: str, sender_name: str = "", sender_email: str = "", attachments: list[dict[str, Any]] | None = None, thread_context: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sources = _source_texts(subject, body, attachments, thread_context)
    evidence = []
    detected = []
    for source, values in sources.items():
        for value in values:
            status, phrase = _match_status(value)
            if status and phrase:
                detected.append(status)
                evidence.append({"source": source, "meaning": status, "text": phrase})
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
        priority = [status for status, _ in STATUS_SIGNALS]
        status = next((candidate for candidate in priority if candidate in detected), detected[0])
        return {"qualified": True, "score": min(0.99, 0.9 + 0.02 * len(evidence)), "status": status, "evidence": evidence[:8], "ignore_reason": None}
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
    prompt = """You are TeleAutomation AI Selection and Offer Detection. First decide whether the email contains credible evidence that the candidate was selected, received or accepted an offer, received a joining confirmation, joined, or entered post-selection onboarding. Recruitment-related alone is not enough. Ignore job recommendations, alerts, listings, applications, assessments, interviews, rejections, newsletters, and marketing. Background verification, joining requests, and salary discussion qualify only with confirmed selection/offer/onboarding context. Evidence must be a short verbatim excerpt from EMAIL_SUBJECT, EMAIL_BODY, ATTACHMENT, or THREAD_CONTEXT and include its supported meaning. Never create MANUAL_REVIEW_REQUIRED below 0.80 confidence. Return only JSON matching selection_offer_event_v1. Prompt: selection_offer_detection v3."""
    payload = {"subject": message.get("subject"), "sender": message.get("sender_email"), "recipient": message.get("recipient_email"), "email_date": str(message.get("sent_at")), "body": clean_email(message.get("body") or ""), "thread_context": (message.get("thread_context") or [])[-5:], "attachments": attachment_texts or []}
    last_error = None
    models = list(dict.fromkeys(model for model in [configured_models()["text"], configured_models()["fallback"]] if model))
    attempts = 1 + max(0, min(1, int(os.getenv("AI_RECRUITMENT_MAX_RETRIES", "1"))))
    for model in models:
        for _ in range(attempts):
            try:
                response = chat_structured(messages=[{"role": "system", "content": prompt}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}], schema=SCHEMA, model=model)
                parsed = parse_model_json(response.content)
                validate_result(parsed, message, attachment_texts)
                parsed["primary_status"] = parsed["status"]
                return parsed, response.model, response.duration_ms
            except (AIGatewayError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
    raise AIGatewayError(str(last_error or "AI analysis failed"))


def _fallback_result(decoded: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "selection_offer_event_v1", "is_recruitment_related": True,
        "is_selection_or_offer_related": True, "should_create_review_record": True,
        "status": "MANUAL_REVIEW_REQUIRED", "primary_status": "MANUAL_REVIEW_REQUIRED",
        "confidence": 0.8, "ignore_reason": None,
        "candidate": {"name": None, "email": decoded.get("recipient_email")},
        "company": {"name": None, "domain": None}, "job": {"title": None, "employment_type": None, "location": None},
        "recruiter": {"name": decoded.get("sender_name"), "email": decoded.get("sender_email")},
        "interview": {key: None for key in ["date", "time", "timezone", "mode", "round", "location", "meeting_link"]},
        "offer": {"offer_detected": True, "offer_letter_detected": False, "appointment_letter_detected": False, "offer_date": None, "offered_ctc": None, "currency": None, "joining_date": None, "offer_expiry_date": None},
        "attachments": [], "evidence": decision["evidence"], "risk_flags": ["AI_PROCESSING_FAILED"],
        "requires_manual_review": True, "summary": "Strong selection or offer evidence requires administrator review.",
        "recommended_action": "Review the source evidence and confirm the exact status.",
    }


def process_message(mailbox: dict[str, Any], decoded: dict[str, Any], attachment_texts: list[dict[str, str]] | None = None) -> dict[str, Any] | None:
    from services.mail_attachment_processor import extract_attachment
    decoded["body"] = clean_email(decoded.get("body") or "")
    decoded["message_hash"] = content_hash("|".join([decoded.get("sender_email") or "", decoded.get("subject") or "", str(decoded.get("sent_at"))]))
    decoded["body_hash"] = content_hash(decoded["body"])
    processed = [extract_attachment(item) if item.get("data") is not None else item for item in (attachment_texts or [])]
    safe = [{key: item.get(key) for key in ("filename", "mime_type", "text", "attachment_type", "extraction_status", "checksum")} for item in processed]
    decision = prefilter_decision(decoded.get("subject", ""), decoded["body"], decoded.get("sender_name", ""), decoded.get("sender_email", ""), safe, decoded.get("thread_context"))
    row, created = store.insert_message(mailbox, decoded, float(decision["score"]))
    if not created:
        return None
    if store.is_duplicate_content(mailbox["candidate_id"], row["id"], decoded["message_hash"], decoded["body_hash"]):
        store.mark_message_status(row["id"], "DUPLICATE_CONTENT", reason="DUPLICATE_MESSAGE")
        return None
    for attachment in processed:
        if attachment.get("checksum"):
            store.save_attachment(row["id"], attachment)
    if not decision["qualified"]:
        store.mark_message_status(row["id"], "IGNORED_NOT_OFFER_RELATED", reason=decision["ignore_reason"])
        return None
    if store.is_duplicate_offer_attachment(mailbox["candidate_id"], row["id"]):
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
    if store.is_duplicate_thread_status(mailbox["candidate_id"], row["id"], result["primary_status"]):
        store.mark_message_status(row["id"], "DUPLICATE_OFFER_EVENT", reason="DUPLICATE_THREAD_STATUS")
        return None
    event = store.create_event(mailbox["candidate_id"], row["id"], result, model=model, duration_ms=duration)
    from services.recruitment_notifications import notify_detection
    notify_detection(event)
    return event
