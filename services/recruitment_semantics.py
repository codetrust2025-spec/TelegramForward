"""Deterministic safety checks for recruitment lifecycle classifications.

The model supplies semantic intent, but high-impact lifecycle events are only
accepted after these context checks reject questionnaires, advertisements,
historical employment documents, questions, and other non-outcomes.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any


EMAIL_INTENTS = {
    "JOB_ADVERTISEMENT", "JOB_REQUIREMENT", "RECRUITER_QUESTIONNAIRE",
    "CANDIDATE_DETAILS_REQUEST", "JOB_APPLICATION_UPDATE",
    "INTERVIEW_INVITATION", "SELECTION_CONFIRMATION", "OFFER_LETTER",
    "OFFER_ACCEPTANCE", "JOINING_CONFIRMATION",
    "ACTUAL_JOINING_CONFIRMATION", "REJECTION", "DOCUMENT_SUBMISSION",
    "EMPLOYMENT_DOCUMENT", "GENERAL", "UNKNOWN",
}

DOCUMENT_TYPES = {
    "NONE", "PAYSLIP", "OFFER_LETTER", "APPOINTMENT_LETTER",
    "JOINING_LETTER", "EXPERIENCE_LETTER", "RELIEVING_LETTER",
    "EMPLOYMENT_VERIFICATION", "BACKGROUND_VERIFICATION_DOCUMENT",
    "RESUME", "BANK_STATEMENT", "ID_DOCUMENT", "EDUCATION_DOCUMENT",
    "CANDIDATE_FORM", "OTHER",
}

LIFECYCLE_EVENTS = {
    "NONE", "SELECTED", "FINAL_SELECTION_CONFIRMED", "OFFER_INDICATION",
    "OFFER_IN_PROGRESS", "OFFER_APPROVED", "OFFER_LETTER_RECEIVED",
    "APPOINTMENT_LETTER_RECEIVED", "OFFER_ACCEPTED", "JOINING_CONFIRMED",
    "JOINED", "POST_SELECTION_ONBOARDING",
}

_QUESTIONNAIRE_FIELDS = (
    "full name", "contact no", "contact number", "email id", "date of birth",
    "dob", "total experience", "relevant exp", "current company",
    "notice period", "current ctc", "expected ctc", "offer in hand",
    "offered ctc", "date of joining", "company name", "10th", "12th",
    "graduation", "grades",
)
_QUESTION_PHRASES = (
    "date of joining?", "joining date?", "please provide your joining date",
    "please share your date of joining", "please confirm your date of joining",
    "when can you join", "offer in hand?", "do you have an offer",
    "do you currently have an offer", "current company?",
)
_JOB_AD_PATTERNS = (
    r"^\s*(?:\N{ENVELOPE}|job)\s*\|", r"\bjob description\b", r"\bapply now\b",
    r"\bopen(?:ing|ings)\b", r"\bwe are hiring\b", r"\bjob requirement\b",
)
_PAYSLIP_PATTERNS = (
    r"\bpayslip\b", r"\bsalary slip\b", r"pay slip for the month",
)
_SENSITIVE_PATTERNS = (
    (r"(?i)\b(?:bank\s*(?:a/?c|account)(?:\s*(?:no|number))?|account\s*(?:no|number))\s*[:#-]?\s*\d(?:[ -]?\d){5,}", "Bank account: [REDACTED]"),
    (r"(?i)\bPAN\s*(?:no|number)?\s*[:#-]?\s*[A-Z]{5}[0-9]{4}[A-Z]\b", "PAN: [REDACTED]"),
    (r"(?i)\b(?:Aadhaar|Aadhar)\s*(?:no|number)?\s*[:#-]?\s*(?:\d[ -]?){12}\b", "Aadhaar: [REDACTED]"),
    (r"(?i)\bUAN\s*(?:no|number)?\s*[:#-]?\s*\d{8,}\b", "UAN: [REDACTED]"),
    (r"(?i)\b(?:PF|EPF)\s*(?:no|number)?\s*[:#-]?\s*[A-Z0-9/-]{6,}\b", "PF: [REDACTED]"),
)


def redact_sensitive_text(value: str, *, limit: int = 500) -> str:
    """Return a short evidence excerpt with financial/government IDs removed."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text[:limit]


def classify_document(filename: str, text: str = "", declared_type: str = "") -> str:
    blob = f"{filename} {text[:12000]}".casefold()
    declared = str(declared_type or "").upper()
    if declared == "BACKGROUND_VERIFICATION_FORM":
        declared = "BACKGROUND_VERIFICATION_DOCUMENT"
    if declared == "OTHER_RECRUITMENT_DOCUMENT":
        declared = "OTHER"
    rules = (
        ("PAYSLIP", _PAYSLIP_PATTERNS),
        ("EXPERIENCE_LETTER", (r"experience\s+letter", r"certificate of experience")),
        ("RELIEVING_LETTER", (r"relieving\s+letter", r"relieved from")),
        ("BANK_STATEMENT", (r"bank\s+statement",)),
        ("RESUME", (r"\bresume\b", r"curriculum vitae", r"\bcv\b")),
        ("ID_DOCUMENT", (r"\baadhaar\b", r"\baadhar\b", r"\bpassport\b", r"\bpan card\b")),
        ("EDUCATION_DOCUMENT", (r"degree certificate", r"marksheet", r"transcript")),
        ("BACKGROUND_VERIFICATION_DOCUMENT", (r"background verification", r"\bbgv\b")),
        ("APPOINTMENT_LETTER", (r"appointment\s+letter", r"letter of appointment")),
        ("OFFER_LETTER", (r"offer\s+letter", r"offer of employment")),
        ("JOINING_LETTER", (r"joining\s+letter", r"joining confirmation")),
        ("EMPLOYMENT_VERIFICATION", (r"employment verification", r"employment certificate")),
        ("CANDIDATE_FORM", (r"candidate information form", r"candidate details form")),
    )
    for label, patterns in rules:
        if any(re.search(pattern, blob) for pattern in patterns):
            return label
    return declared if declared in DOCUMENT_TYPES else "OTHER"


def _questionnaire(text: str) -> bool:
    lowered = text.casefold()
    field_count = sum(1 for field in _QUESTIONNAIRE_FIELDS if field in lowered)
    colon_count = len(re.findall(r"(?im)^\s*[a-z][a-z /().-]{2,35}\s*[:?]", text))
    return field_count >= 4 or (field_count >= 3 and colon_count >= 3)


def _is_question(text: str) -> bool:
    lowered = text.casefold()
    return any(phrase in lowered for phrase in _QUESTION_PHRASES)


def _is_job_ad(subject: str, body: str, sender_email: str) -> bool:
    combined = f"{subject}\n{body[:8000]}".casefold()
    portal = any(token in sender_email.casefold() for token in ("naukri", "foundit", "monster", "indeed", "shine", "timesjobs"))
    ad_language = any(re.search(pattern, combined, re.I) for pattern in _JOB_AD_PATTERNS)
    many_requirements = sum(token in combined for token in ("experience", "skills", "location", "notice period", "ctc", "job description")) >= 3
    return ad_language or (portal and many_requirements)


def _event_date(sent_at: Any) -> date:
    if isinstance(sent_at, datetime):
        return sent_at.date()
    if isinstance(sent_at, date):
        return sent_at
    try:
        return datetime.fromisoformat(str(sent_at or "").replace("Z", "+00:00")).date()
    except ValueError:
        return date.today()


def classify_context(
    subject: str,
    body: str,
    *,
    sender_email: str = "",
    sent_at: Any = None,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Classify message/document context without promoting candidate truth."""
    attachment_rows = attachments or []
    documents = [
        classify_document(
            str(item.get("filename") or ""), str(item.get("text") or ""),
            str(item.get("document_type") or item.get("attachment_type") or ""),
        )
        for item in attachment_rows
    ]
    document_type = next((item for item in documents if item != "OTHER"), "NONE" if not documents else "OTHER")
    direct = f"{subject}\n{body}"
    all_text = " ".join([direct] + [str(item.get("text") or "") for item in attachment_rows])
    questionnaire = _questionnaire(direct)
    question = _is_question(direct)
    job_ad = _is_job_ad(subject, body, sender_email)
    payslip = document_type == "PAYSLIP" or any(re.search(pattern, all_text, re.I) for pattern in _PAYSLIP_PATTERNS)
    historical = payslip or document_type in {"EXPERIENCE_LETTER", "RELIEVING_LETTER", "EMPLOYMENT_VERIFICATION"}

    lowered = direct.casefold()
    actual_joined = any(re.search(pattern, lowered) for pattern in (
        r"\bofficially joined\b", r"\bjoined (?:the company|[a-z0-9 &.-]+) today\b",
        r"\bemployment commenced\b", r"\bstarted (?:employment|working) (?:today|on)\b",
        r"\breported for (?:duty|joining)\b",
    ))
    joining_confirmed = any(re.search(pattern, lowered) for pattern in (
        r"\bjoining date (?:is|has been) confirmed\b", r"\byour (?:date of joining|joining date) (?:is|will be)\b",
        r"\bplease join on\b", r"\breport for joining on\b",
    ))
    offer_received = any(phrase in lowered for phrase in (
        "we are pleased to offer you", "we are delighted to offer you",
        "offer letter attached", "offer of employment",
    ))
    offer_accepted = any(phrase in lowered for phrase in (
        "we have received your acceptance", "your offer acceptance is confirmed",
        "accepted the offer", "offer has been accepted",
    ))
    selected = any(phrase in lowered for phrase in (
        "you have been selected", "selected for the role", "selected for the position",
        "selection has been confirmed", "final selection confirmed",
    ))

    if questionnaire:
        intent, summary = "RECRUITER_QUESTIONNAIRE", "Recruiter is requesting candidate information. No employment outcome is confirmed."
    elif job_ad:
        intent, summary = "JOB_ADVERTISEMENT", "This is a job advertisement or recruiter requirement, not a candidate employment outcome."
    elif payslip:
        intent, summary = "EMPLOYMENT_DOCUMENT", "Payslip contains historical employee metadata. No current joining event was found."
    elif question:
        intent, summary = "CANDIDATE_DETAILS_REQUEST", "The message asks for candidate information; it does not assert an employment outcome."
    elif actual_joined:
        intent, summary = "ACTUAL_JOINING_CONFIRMATION", "The message explicitly confirms that employment has started."
    elif joining_confirmed:
        intent, summary = "JOINING_CONFIRMATION", "The message confirms a joining arrangement but does not confirm that employment has started."
    elif offer_accepted:
        intent, summary = "OFFER_ACCEPTANCE", "The message explicitly confirms acceptance of an employment offer."
    elif offer_received or document_type in {"OFFER_LETTER", "APPOINTMENT_LETTER"}:
        intent, summary = "OFFER_LETTER", "The message contains a candidate-specific employment offer."
    elif selected:
        intent, summary = "SELECTION_CONFIRMATION", "The message explicitly confirms candidate selection."
    else:
        intent, summary = "UNKNOWN", "No validated candidate employment outcome was found."

    lifecycle = "NONE"
    if not (questionnaire or job_ad or question or historical):
        if actual_joined:
            lifecycle = "JOINED"
        elif joining_confirmed:
            lifecycle = "JOINING_CONFIRMED"
        elif offer_accepted:
            lifecycle = "OFFER_ACCEPTED"
        elif offer_received:
            lifecycle = "OFFER_LETTER_RECEIVED"
        elif selected:
            lifecycle = "SELECTED"

    return {
        "email_intent": intent,
        "document_type": document_type,
        "is_candidate_specific": not job_ad,
        "is_job_outcome": lifecycle != "NONE",
        "is_current_event": lifecycle != "NONE" and not historical,
        "is_questionnaire": questionnaire,
        "is_question": question,
        "is_promotional_or_job_ad": job_ad,
        "is_historical_information": historical,
        "historical_employment_evidence": historical,
        "lifecycle_event": lifecycle,
        "event_reference_date": _event_date(sent_at).isoformat(),
        "evidence_summary": summary,
    }


def validate_lifecycle_event(proposed: str, context: dict[str, Any]) -> tuple[str, str | None]:
    """Return a safe lifecycle event and a machine-readable rejection reason."""
    status = str(proposed or "NONE").upper()
    if any(context.get(key) for key in (
        "is_questionnaire", "is_question", "is_promotional_or_job_ad",
        "is_historical_information",
    )):
        return "NONE", str(context.get("email_intent") or "NON_OUTCOME_CONTEXT")
    supported = str(context.get("lifecycle_event") or "NONE").upper()
    if status == "JOINED" and supported != "JOINED":
        return "NONE", "JOINED_REQUIRES_EXPLICIT_EMPLOYMENT_START"
    if status == "JOINING_CONFIRMED" and supported != "JOINING_CONFIRMED":
        return "NONE", "JOINING_CONFIRMATION_NOT_ASSERTED"
    comparable = {
        "SELECTED": {"SELECTED", "FINAL_SELECTION_CONFIRMED"},
        "FINAL_SELECTION_CONFIRMED": {"SELECTED", "FINAL_SELECTION_CONFIRMED"},
        "OFFER_INDICATION": {"OFFER_INDICATION", "OFFER_LETTER_RECEIVED"},
        "OFFER_LETTER_RECEIVED": {"OFFER_INDICATION", "OFFER_LETTER_RECEIVED"},
        "APPOINTMENT_LETTER_RECEIVED": {"OFFER_INDICATION", "OFFER_LETTER_RECEIVED"},
        "OFFER_ACCEPTED": {"OFFER_ACCEPTED"},
    }
    if status in comparable and supported not in comparable[status]:
        return "NONE", "PROPOSED_EVENT_NOT_SUPPORTED_BY_ASSERTIVE_CONTEXT"
    return status, None
