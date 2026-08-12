"""Recruiting calendar invites that never say "interview".

Production message 05654d02-801c-4c76-af5d-8123d2439900 was titled "Discussion
with Gopichand for DevOps Engineer" on a Microsoft Teams invite and was dropped
as NO_RECRUITMENT_ROUTING_SIGNAL before ever reaching Ollama, because no keyword
matched. Routing on "discussion" alone would pull in every internal meeting, so
three structured signals must agree.
"""

from services.recruitment_mail_agent import recruiting_invite_signal, routing_decision

TEAMS_BODY = (
    "When: 12 August 2026 17:30-18:00 (UTC+05:30) Chennai, Kolkata, Mumbai, New Delhi\n"
    "Where: Microsoft Teams Meeting\n\n"
    "________________________________________\n"
    "Join the meeting now\nMeeting ID: 412 858 913 24\n"
    "________________________________________\n"
)


def test_the_gopichand_invite_is_routed():
    assert recruiting_invite_signal(
        "Discussion with Gopichand for DevOps Engineer", TEAMS_BODY,
        "rvadde@innominds.com",
    ) is True


def test_the_gopichand_invite_reaches_the_model_through_routing_decision():
    decision = routing_decision(
        "Discussion with Gopichand for DevOps Engineer", TEAMS_BODY,
        "Ramu Vadde", "rvadde@innominds.com",
    )
    assert decision["send_to_ai"] is True
    assert decision["reason"] != "NO_RECRUITMENT_ROUTING_SIGNAL"


def test_other_invite_wordings_are_routed():
    for subject in (
        "Discussion regarding Senior Backend Developer role",
        "Technical discussion with Priya for QA Engineer",
        "Screening round with Ravi - Full Stack Developer",
    ):
        assert recruiting_invite_signal(subject, TEAMS_BODY, "hr@acme.com") is True, subject


def test_an_explicit_interview_invite_still_routes():
    decision = routing_decision(
        "Interview confirmation - Consultant role", TEAMS_BODY,
        "Recruiter", "interview@jobs.capgemini.com",
    )
    assert decision["send_to_ai"] is True


class TestOrdinaryMeetingsFailClosed:
    def test_an_internal_business_discussion_is_not_routed(self):
        """Has invite structure and "discussion with", but names no role."""
        assert recruiting_invite_signal(
            "Discussion with Ramu about the Q3 budget", TEAMS_BODY,
            "finance@innominds.com",
        ) is False

    def test_a_sprint_meeting_is_not_routed(self):
        assert recruiting_invite_signal(
            "Sprint planning", TEAMS_BODY, "scrum@innominds.com",
        ) is False

    def test_a_role_word_without_invite_structure_is_not_routed(self):
        """Ambiguous: no calendar/meeting evidence at all, so fail closed."""
        assert recruiting_invite_signal(
            "Discussion with Gopichand for DevOps Engineer",
            "Let us catch up sometime next week.", "rvadde@innominds.com",
        ) is False

    def test_an_invite_naming_a_role_but_not_a_person_is_not_routed(self):
        """Ambiguous: a team meeting about a role, not about a candidate."""
        assert recruiting_invite_signal(
            "DevOps Engineer hiring plan sync", TEAMS_BODY, "hr@innominds.com",
        ) is False

    def test_all_three_signals_are_required(self):
        subject = "Discussion with Gopichand for DevOps Engineer"
        assert recruiting_invite_signal(subject, TEAMS_BODY, "x@y.com") is True
        # drop the invite structure
        assert recruiting_invite_signal(subject, "hello", "x@y.com") is False
        # drop the role title
        assert recruiting_invite_signal(
            "Discussion with Gopichand", TEAMS_BODY, "x@y.com") is False
        # drop the person framing
        assert recruiting_invite_signal(
            "DevOps Engineer", TEAMS_BODY, "x@y.com") is False


def test_an_ics_attachment_counts_as_invite_structure():
    assert recruiting_invite_signal(
        "Discussion with Gopichand for DevOps Engineer",
        "Please accept.", "rvadde@innominds.com",
        [{"filename": "invite.ics", "text": ""}],
    ) is True
