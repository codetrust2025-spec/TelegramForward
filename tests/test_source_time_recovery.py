"""A stated AM/PM time must survive the model reformatting it to 24-hour.

Production message 5494b05a (Altimetrik/Gopichand): the subject reads
"Interview scheduled with Altimetrik on Fri, August 14, 2:00 PM - 3:00 PM IST"
and the model quoted that verbatim in its evidence, yet returned
interview.time as "14:00 - 15:00". The 24-hour rejection then fired and the
interview looped forever. Recovering the stated time from the source is not
inventing one: with no AM/PM anywhere, the rejection still stands.
"""

import inspect
from services import recruitment_mail_agent as agent
from services.recruitment_mail_agent import _normalise_interview_time as norm


def test_the_altimetrik_subject_yields_the_stated_start_time():
    assert norm("Interview scheduled with Altimetrik on Fri, August 14, "
                "2:00 PM - 3:00 PM IST") == "02:00 PM"


def test_an_evidence_quote_yields_the_stated_time():
    assert norm("We would like to invite you to attend an interview on Friday, "
                "14 August, 2026, 2:00 PM to 3:00 PM IST") == "02:00 PM"


def test_the_models_reformatted_value_alone_is_still_rejected():
    """This is what makes recovery necessary rather than optional."""
    assert norm("14:00 - 15:00") == ""
    assert norm("17:00") == ""


def test_a_source_without_am_pm_recovers_nothing():
    """No AM/PM anywhere means no time — never invented from a bare 24h value."""
    for text in ("Interview scheduled for 17:00 hrs",
                 "Meeting at 14:00 - 15:00",
                 "We will confirm the timing shortly"):
        assert norm(text) == "", text


def test_recovery_reads_subject_and_evidence_only():
    src = inspect.getsource(agent.validate_result)
    block = src.split("if not normalised_time:")[1].split("if normalised_time:")[0]
    assert '(message or {}).get("subject")' in block
    assert 'value.get("evidence")' in block
    # the whole body is deliberately not scanned: a signature or an unrelated
    # meeting time must not become the interview time
    assert '.get("body")' not in block


def test_recovery_runs_only_when_the_model_value_is_unusable():
    src = inspect.getsource(agent.validate_result)
    assert src.index("normalised_time = _normalise_interview_time(interview.get") \
        < src.index("if not normalised_time:")
