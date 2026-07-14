"""Single source of truth for the Selection and Offer Review visibility rule."""

from __future__ import annotations

from typing import Any


ALLOWED_STATUSES = (
    "SELECTED", "FINAL_SELECTION_CONFIRMED", "OFFER_INDICATION",
    "OFFER_IN_PROGRESS", "OFFER_APPROVED", "OFFER_LETTER_RECEIVED",
    "APPOINTMENT_LETTER_RECEIVED", "OFFER_ACCEPTED", "JOINING_CONFIRMED",
    "JOINED", "POST_SELECTION_ONBOARDING", "MANUAL_REVIEW_REQUIRED",
)
IGNORED_STATUSES = {
    "IGNORED_NOT_OFFER_RELATED", "IGNORED_LOW_CONFIDENCE", "NO_RELEVANT_STATUS",
}
IGNORED_REVIEW_STATUSES = {"IGNORED", "FALSE_POSITIVE", "DUPLICATE"}
STRONG_SIGNAL_PHRASES = (
    "you have been selected", "selected for the role", "selected for the position",
    "selection confirmed", "final selection", "we are pleased to offer",
    "we are delighted to offer", "offer letter attached", "employment offer",
    "appointment letter", "letter of appointment", "offer approved", "offer released",
    "offer is being processed", "joining date", "date of joining", "welcome aboard",
    "employee onboarding", "pre-joining formalities", "report for joining",
)


def _evidence(event: dict[str, Any]) -> list[Any]:
    structured = event.get("structured_result") or {}
    return structured.get("evidence") or [] if isinstance(structured, dict) else []


def has_strong_selection_or_offer_signal(event: dict[str, Any]) -> bool:
    structured = event.get("structured_result") or {}
    if isinstance(structured, dict) and structured.get("is_selection_or_offer_related") is True:
        meanings = " ".join(str(item.get("meaning") or "") for item in _evidence(event) if isinstance(item, dict)).upper()
        if any(status in meanings for status in ALLOWED_STATUSES if status != "MANUAL_REVIEW_REQUIRED"):
            return True
    text = " ".join(str(event.get(key) or "") for key in ("subject", "summary", "sender_name", "sender_email"))
    text += " " + str(structured)
    lowered = text.casefold()
    return any(phrase in lowered for phrase in STRONG_SIGNAL_PHRASES)


def should_show_in_selection_offer_review(event: dict[str, Any]) -> bool:
    status = str(event.get("primary_status") or event.get("status") or "").upper()
    review_status = str(event.get("review_status") or "").upper()
    if status not in ALLOWED_STATUSES or status in IGNORED_STATUSES:
        return False
    if review_status in IGNORED_REVIEW_STATUSES or event.get("visible_in_offer_review") is False:
        return False
    evidence = _evidence(event)
    if not evidence or float(event.get("confidence") or 0) < 0.8:
        return False
    if status == "MANUAL_REVIEW_REQUIRED" and not has_strong_selection_or_offer_signal(event):
        return False
    return True


def cleanup_reason(event: dict[str, Any]) -> str | None:
    """Return an audit reason for a historical row that must be archived."""
    if should_show_in_selection_offer_review(event):
        return None
    subject = str(event.get("subject") or "").casefold()
    sender = " ".join(str(event.get(key) or "") for key in ("sender_name", "sender_email")).casefold()
    if any(term in subject for term in ("job recommendation", "recommended jobs", "jobs for you", "job alert", "similar jobs", "featured jobs")):
        return "JOB_RECOMMENDATION"
    if any(term in subject for term in ("interview", "assessment", "coding test")):
        return "INTERVIEW_OR_ASSESSMENT"
    if any(term in subject for term in ("application", "resume viewed", "profile viewed", "rejection", "regret to inform")):
        return "NON_OFFER_RECRUITMENT_MAIL"
    if any(portal in subject + " " + sender for portal in ("foundit", "monster", "naukri", "linkedin jobs", "indeed", "shine", "timesjobs")):
        return "JOB_PORTAL_PROMOTION"
    if float(event.get("confidence") or 0) < 0.8:
        return "LOW_CONFIDENCE"
    if not _evidence(event):
        return "NO_EVIDENCE"
    return "NO_QUALIFIED_SELECTION_OR_OFFER_EVIDENCE"


# Requested public spelling; Python callers should use the snake-case function above.
shouldShowInSelectionOfferReview = should_show_in_selection_offer_review


def qualified_event_sql(alias: str = "e") -> tuple[str, list[Any]]:
    """SQL counterpart used by review, timeline, metrics and dashboard queries."""
    predicate = f"""{alias}.primary_status=ANY(%s)
      AND {alias}.primary_status NOT IN('IGNORED_NOT_OFFER_RELATED','IGNORED_LOW_CONFIDENCE','NO_RELEVANT_STATUS')
      AND {alias}.review_status NOT IN('IGNORED','FALSE_POSITIVE','DUPLICATE')
      AND COALESCE({alias}.visible_in_offer_review,true)=true
      AND {alias}.confidence>=0.8
      AND jsonb_array_length(COALESCE({alias}.structured_result->'evidence','[]'::jsonb))>0
      AND ({alias}.primary_status<>'MANUAL_REVIEW_REQUIRED' OR (
        COALESCE(({alias}.structured_result->>'is_selection_or_offer_related')::boolean,false)=true
        AND EXISTS (
          SELECT 1 FROM jsonb_array_elements(COALESCE({alias}.structured_result->'evidence','[]'::jsonb)) item
          WHERE upper(COALESCE(item->>'meaning',''))=ANY(%s)
        )
      ))"""
    important = [status for status in ALLOWED_STATUSES if status != "MANUAL_REVIEW_REQUIRED"]
    return predicate, [list(ALLOWED_STATUSES), important]
