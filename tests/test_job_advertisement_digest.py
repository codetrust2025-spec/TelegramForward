"""A catalogue of vacancies is not news about the candidate.

Production message 19fa7beaaae8d122 — LinkedIn <jobs-noreply@linkedin.com> to
Ram Charan, subject "Senior Angular Developer at Saven Technologies", body
"Jobs that match your profile Based on your title and location." listing six
vacancies — produced:

    primary_status  INTERVIEW_SHORTLISTED   confidence 0.95
    company         "Birlasoft and FactSet"
    job_title       "Senior Frontend Developer Angular React, Software Engineer III"
    summary         "Candidate Reddy Charan M.S has been shortlisted for the
                     position of ... The candidate should prepare for an
                     interview scheduled in Greater Hyderabad Area, Hyderabad."
    notification    "Profile Active"

None of that was contamination from another message: "Birlasoft" and "FactSet"
are in *this* mail's own body, as two of the six adverts. The model quoted them
verbatim, so the evidence check passed — what it invented was the *meaning*:

    evidence text    "Sr Application Developer Birlasoft Greater Hyderabad Area
                      View job: https://www.linkedin.com/comm/jobs/view/44332..."
    claimed meaning  "Candidate has been shortlisted for the position of Senior
                      Frontend Developer Angular React in Birlasoft ..."

The backend's own reading of the same source said `is_job_outcome=False`,
`lifecycle_event="NONE"`, "No validated candidate employment outcome was found",
and was overruled. `routing_decision` had sent it to the model as
AMBIGUOUS_RECRUITMENT because `is_promotional_or_job_ad` was False and the
phrase table knew "jobs matching your profile" but not LinkedIn's actual
"Jobs that match your profile".
"""

import pytest

from services.recruitment_mail_agent import (
    clean_email, job_advertisement_digest, routing_decision, validate_result,
)

SENDER = "jobs-noreply@linkedin.com"
SUBJECT = "Senior Angular Developer at Saven Technologies"

# Verbatim from the Production body, trimmed to the listing lines.
BODY = (
    "Jobs that match your profile Based on your title and location. "
    "Senior Angular Developer Saven Technologies Hyderabad "
    "View job: https://www.linkedin.com/comm/jobs/view/4442814245/?trackingId=hcgALEDAK22Z "
    "--------------------------------------------------------- "
    "Sr Application Developer Birlasoft Greater Hyderabad Area "
    "View job: https://www.linkedin.com/comm/jobs/view/4433245817/?trackingId=yTzEMKSHniHJfkQult4TKQ "
    "--------------------------------------------------------- "
    "Software Engineer III FactSet Hyderabad "
    "View job: https://www.linkedin.com/comm/jobs/view/4438707634/?trackingId=cPtex5kIJeRZU1ZXySDQ "
)


def test_the_production_digest_is_recognised():
    assert job_advertisement_digest(SUBJECT, BODY, SENDER, []) is True


def test_it_never_reaches_the_model():
    route = routing_decision(SUBJECT, clean_email(BODY), "LinkedIn", SENDER, [], None)
    assert route["send_to_ai"] is False
    assert route["reason"] == "JOB_RECOMMENDATION"
    assert route["score"] == 0.0


def test_two_distinct_postings_are_enough_whoever_sent_them():
    """The structural test, so a reworded digest from a new board still fails."""
    body = ("Openings you may like "
            "Data Engineer Acme https://www.linkedin.com/comm/jobs/view/1111111111/ "
            "Backend Engineer Globex https://www.linkedin.com/comm/jobs/view/2222222222/")
    assert job_advertisement_digest("Openings", body, "someone@unknown.example", []) is True


def test_naukri_listing_urls_count_too():
    body = ("Recommended jobs "
            "https://www.naukri.com/job-listings-python-developer-acme-123456789 "
            "https://www.naukri.com/job-listings-react-developer-globex-987654321")
    assert job_advertisement_digest("Jobs for you", body, "alerts@naukri.com", []) is True


def test_one_posting_alone_is_not_a_catalogue():
    """A single link is not a digest; a board sender must also talk like one."""
    one_link = "Senior Angular Developer Saven https://www.linkedin.com/comm/jobs/view/4442814245/"
    assert job_advertisement_digest("A role", one_link, SENDER, []) is False
    assert job_advertisement_digest("A role", "We have an opening.", SENDER, []) is False
    # the same single posting, now presented as a listing by the board itself
    assert job_advertisement_digest(
        "A role", "Jobs that match your profile " + one_link, SENDER, []) is True


# ── genuine recruitment mail must be untouched ──────────────────────────────

@pytest.mark.parametrize("subject,body,sender", [
    ("L1-CGEMJP00347400-React UI Developer-Reddy Charan M S",
     "Your interview is scheduled for 31 July 2026 at 02:00 PM IST via Teams.",
     "recruiter@capgemini.com"),
    ("Interview confirmation - Role: Software Developer",
     "We are pleased to confirm your interview on 3 August 2026 at 2:00 PM IST.",
     "talent@company.example"),
    ("You have been shortlisted",
     "You have been shortlisted for the position of Senior Engineer. We will call you.",
     "hr@company.example"),
    ("Offer Letter",
     "We are pleased to offer you the position of Senior Engineer.",
     "hr@company.example"),
])
def test_a_real_recruitment_mail_is_not_a_digest(subject, body, sender):
    assert job_advertisement_digest(subject, body, sender, []) is False


def test_a_recruiter_mail_that_links_one_posting_is_not_a_digest():
    """A recruiter citing the role they are hiring for must still be analysed."""
    body = ("Hi Charan, we would like to discuss this role with you: "
            "https://www.linkedin.com/comm/jobs/view/4442814245/ "
            "Are you available tomorrow at 3 PM?")
    assert job_advertisement_digest("Opportunity", body, "recruiter@acme.example", []) is False


# ── the second layer: even if it reaches the model ──────────────────────────

def _shortlist_result():
    """The model's actual Production answer, including its verbatim evidence."""
    from tests.test_recruitment_mail_agent import valid_result

    row = valid_result()
    row.update(
        status="INTERVIEW_SHORTLISTED", confidence=0.95,
        summary="Candidate Reddy Charan M.S has been shortlisted for the position of "
                "Senior Frontend Developer Angular React at Birlasoft and Software "
                "Engineer III at FactSet.",
        evidence=[{
            "source": "EMAIL_BODY",
            "meaning": "Candidate has been shortlisted for the position of Senior Frontend "
                       "Developer Angular React in Birlasoft and Software Engineer III at FactSet.",
            "text": "Sr Application Developer Birlasoft Greater Hyderabad Area",
        }],
    )
    row["company"] = {"name": "Birlasoft and FactSet", "domain": None}
    return row


def test_a_digest_cannot_become_a_tracked_record_even_at_95_percent():
    row = _shortlist_result()
    message = {"subject": SUBJECT, "body": BODY, "sender_email": SENDER}

    validate_result(row, message)

    assert row["is_selection_or_offer_related"] is False
    assert row["should_create_review_record"] is False
    assert row["requires_manual_review"] is False
    assert row["ignore_reason"] == "JOB_RECOMMENDATION"


def test_the_models_answer_is_kept_so_the_decision_stays_auditable():
    """Gating is not deletion: what the model said must survive for the audit.

    Recorded the way every other downgrade in this pipeline records it, so the
    audit can always answer "what did the AI actually say, and who overruled it".
    """
    row = _shortlist_result()
    validate_result(row, {"subject": SUBJECT, "body": BODY, "sender_email": SENDER})

    assert row["downgraded_from"] == "INTERVIEW_SHORTLISTED"
    assert row["downgrade_reason"] == "JOB_ADVERTISEMENT_DIGEST"
    assert row["confidence"] == 0.95
    assert row["evidence"], "the evidence the model quoted must still be recorded"
    assert "Birlasoft" in row["summary"]


def test_the_same_result_on_a_real_mail_is_still_tracked():
    """The gate keys off the source, never off the model's answer."""
    row = _shortlist_result()
    row["evidence"] = [{"source": "EMAIL_BODY", "meaning": "SHORTLISTED",
                        "text": "You have been shortlisted for the position"}]
    message = {"subject": "Shortlisted",
               "body": "You have been shortlisted for the position of Senior Engineer.",
               "sender_email": "hr@company.example"}

    validate_result(row, message)

    assert row.get("ignore_reason") != "JOB_RECOMMENDATION"


# ── the contamination question this investigation had to answer ─────────────

def test_the_foreign_company_names_came_from_this_mails_own_body():
    """Proof it was never cross-message contamination.

    Both names the notification showed are in this message's own source, as two
    of its six adverts. Any fix aimed at a stale-result or wrong-join defect
    would have been aimed at the wrong layer.
    """
    assert "Birlasoft" in BODY
    assert "FactSet" in BODY
    assert "shortlisted" not in BODY.lower()
    assert "interview" not in BODY.lower()
