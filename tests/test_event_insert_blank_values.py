"""A blank value from the model must not abort event creation.

The model expresses "no value" two ways: `null`, and an empty string. An empty
string reaching a column Postgres types as date, time or numeric raises
InvalidDatetimeFormat and aborts the whole INSERT, so no event is created at
all.

Verbatim from Production while draining the queue -- a LinkedIn invitation,
Gmail id 19ffb690ae7e58f6:

    [1/12] EXCEPTION InvalidDatetimeFormat: invalid input syntax for type date: ""
    LINE 5: ...ample.com','2023-10-15','14:00','Video C | You have 1 new invitation

Because a raw psycopg2 error is not an AIGatewayError, it bypasses the semantic
retry path entirely: no error code is recorded, and the same mail fails the same
way on every attempt.
"""

import pytest

from core.recruitment_mail_store import typed_or_null


@pytest.mark.parametrize("value", ["", "   ", "\t", "\n", None])
def test_blank_and_missing_values_become_null(value):
    assert typed_or_null(value) is None


@pytest.mark.parametrize("value", [
    "2026-08-17",                    # interview_date
    "12:00:00",                      # interview_time
    "2026-07-30T12:00:00+05:30",
    0, 1, 1200000, 3.5, "1200000",   # offered_ctc
])
def test_real_values_are_passed_through_untouched(value):
    assert typed_or_null(value) == value


def test_zero_is_not_treated_as_blank():
    """0 is a real number; only blank strings and None mean 'no value'."""
    assert typed_or_null(0) == 0
    assert typed_or_null(0) is not None


def test_a_malformed_non_empty_value_is_still_passed_to_the_database():
    """Dropping it silently would lose a real answer.

    The database rejecting "not-a-date" is the correct outcome; only the
    ambiguity between null and "" is resolved here.
    """
    assert typed_or_null("not-a-date") == "not-a-date"


def test_every_typed_column_bound_from_model_output_is_guarded():
    """The columns Postgres types as date/time/numeric, from information_schema.

    interview_date, interview_time, offered_ctc, joining_date, offer_date and
    offer_expiry_date all come straight from the model. Missing one of them
    leaves the same crash reachable by a different field.
    """
    import inspect
    from core import recruitment_mail_store as store

    src = inspect.getsource(store.create_event)
    for field in ("interview.get('date')", "interview.get('time')",
                  "offer.get('offered_ctc')", "offer.get('joining_date')",
                  "offer.get('offer_date')", "offer.get('offer_expiry_date')"):
        assert f"typed_or_null({field})" in src, f"{field} is not guarded"


def test_the_reprocess_path_is_guarded_too():
    """A reprocess writes the same typed columns and crashed identically."""
    import inspect
    from core import recruitment_mail_store as store

    src = inspect.getsource(store.create_or_reprocess_event)
    assert "typed_or_null(offer.get('joining_date'))" in src
