"""No valid AI recruitment result may be silently deleted.

The audit of 2026-08-13 found seven statuses still collapsing to NONE when the
lifecycle validator rejected them — including SELECTED, FINAL_SELECTION_CONFIRMED
and CANDIDATE_REJECTED. A rejection vanishing is the worst of these: the
candidate outcome is the entire point of the record.
"""

from core.recruitment_offer_visibility import ALLOWED_STATUSES, should_show_in_selection_offer_review
from services import recruitment_mail_agent as agent


def test_every_tracked_status_has_a_review_landing_place():
    """The invariant: nothing the model may return can collapse to NONE."""
    orphans = [
        s for s in agent.VISIBLE_STATUSES
        if agent._needs_review_status(s) is None
        and "NEEDS_REVIEW" not in s and s != "INTERVIEW_PROPOSED"
    ]
    assert orphans == [], f"these would still be silently deleted: {orphans}"


def test_the_previously_uncovered_statuses_now_downgrade():
    for status in ("SELECTED", "FINAL_SELECTION_CONFIRMED", "BACKGROUND_VERIFICATION",
                   "DOCUMENT_VERIFICATION", "CANDIDATE_REJECTED"):
        assert agent._needs_review_status(status) == "SELECTION_NEEDS_REVIEW", status


def test_interview_family_all_lands_on_proposed():
    for status in ("INTERVIEW_CONFIRMED", "INTERVIEW_CANCELLED", "INTERVIEW_RESCHEDULED",
                   "INTERVIEW_SHORTLISTED", "INTERVIEW_UPDATE"):
        assert agent._needs_review_status(status) == "INTERVIEW_PROPOSED", status


def test_offer_and_joining_families_unchanged():
    assert agent._needs_review_status("OFFER_IN_PROGRESS") == "OFFER_NEEDS_REVIEW"
    assert agent._needs_review_status("JOINING_CONFIRMED") == "JOINING_NEEDS_REVIEW"


def test_an_unknown_status_is_not_invented_into_a_review_state():
    assert agent._needs_review_status("NOT_A_REAL_STATUS") is None
    assert agent._needs_review_status("") is None


class TestReviewStatesStayInert:
    def test_no_review_state_reaches_offer_case_workflows(self):
        for s in ("OFFER_NEEDS_REVIEW", "JOINING_NEEDS_REVIEW", "SELECTION_NEEDS_REVIEW"):
            assert s not in agent.OFFER_CASE_STATUSES, s

    def test_selection_review_is_visible_and_allowed(self):
        assert "SELECTION_NEEDS_REVIEW" in ALLOWED_STATUSES
        assert "SELECTION_NEEDS_REVIEW" in agent.VISIBLE_STATUSES
        event = {"primary_status": "SELECTION_NEEDS_REVIEW", "review_status": "PENDING",
                 "confidence": 0.95, "validation_status": "NEEDS_REVIEW",
                 "structured_result": {"is_selection_or_offer_related": True, "interview": {},
                     "evidence": [{"source": "EMAIL_BODY", "meaning": "SELECTED",
                                   "text": "you have been selected"}]}}
        assert should_show_in_selection_offer_review(event) is True

    def test_labels_never_read_as_a_completed_outcome(self):
        import inspect
        src = inspect.getsource(agent.validate_result)
        for label in ("Offer — needs review", "Joining — needs review",
                      "Interview — needs review", "Selection — needs review"):
            assert label in src, label
