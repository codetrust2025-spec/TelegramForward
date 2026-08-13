"""No model string may abort event creation.

`create_event` binds six columns Postgres types as date, time or numeric
straight from the model's answer. Anything it cannot parse aborts the whole
INSERT, so no event is created — and because a raw psycopg2 error is not an
AIGatewayError, it never reaches the semantic retry path: no code is recorded,
and the mail fails identically on every attempt, forever.

Two shapes did exactly that in Production while draining the queue:

    InvalidDatetimeFormat: invalid input syntax for type date: ""
      -- a LinkedIn invitation, Gmail 19ffb690ae7e58f6

    InvalidTimeZoneDisplacementValue: time zone displacement out of range:
    "15:30 - 16:00 IST"
      -- two ripplehire cancellations, "Interview canceled: Fri, August 07"
         and "... Wed, August 05"

Nothing is lost by normalising these columns: the model's exact answer is kept
verbatim in `structured_result`, and these columns are only the projection the
roster and audit read from.
"""

import pytest

from core.recruitment_mail_store import (
    storable_date, storable_number, storable_time, typed_or_null,
)


# ── times ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("15:30 - 16:00 IST", "15:30:00"),        # the Production crash
    ("12:00:00 until 13:00:00 IST", "12:00:00"),
    ("15:30", "15:30:00"),
    ("15:30:45", "15:30:45"),
    ("03:00 PM", "15:00:00"),
    ("3:00 PM", "15:00:00"),
    ("12:00 AM", "00:00:00"),
    ("12:00 PM", "12:00:00"),
    ("Interview at 09:45 sharp", "09:45:00"),
])
def test_a_stated_time_survives_however_it_is_written(raw, expected):
    """A range gives its start: that is when the interview begins."""
    assert storable_time(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", None, "no time given", "TBD", "25:00", "99:99"])
def test_an_unreadable_time_becomes_null_rather_than_aborting(raw):
    assert storable_time(raw) is None


# ── dates ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("2026-08-17", "2026-08-17"),
    ("2026-07-30T12:00:00+05:30", "2026-07-30"),
    ("2026-07-30T12:00:00Z", "2026-07-30"),
])
def test_a_stated_date_survives(raw, expected):
    assert storable_date(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", None, "next Tuesday", "2026-13-45", "TBD"])
def test_an_unreadable_date_becomes_null_rather_than_aborting(raw):
    assert storable_date(raw) is None


# ── numbers ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [(0, 0), (12.5, 12.5), ("1200000", 1200000.0), ("12,00,000", 1200000.0)])
def test_a_stated_amount_survives(raw, expected):
    assert storable_number(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", None, "not disclosed", "competitive"])
def test_an_unreadable_amount_becomes_null(raw):
    assert storable_number(raw) is None


def test_zero_is_a_real_number_not_a_blank():
    assert storable_number(0) == 0
    assert storable_number(0) is not None


# ── the blank guard kept for untyped callers ────────────────────────────────

@pytest.mark.parametrize("raw", ["", "  ", None])
def test_typed_or_null_still_collapses_blanks(raw):
    assert typed_or_null(raw) is None


# ── every typed column is routed through a coercer ──────────────────────────

def test_every_typed_column_in_create_event_is_coerced():
    """Missing one leaves the same crash reachable through a different field."""
    import inspect
    from core import recruitment_mail_store as store

    src = inspect.getsource(store.create_event)
    for binding in (
        "storable_date(interview.get('date'))",
        "storable_time(interview.get('time'))",
        "storable_number(offer.get('offered_ctc'))",
        "storable_date(offer.get('joining_date'))",
        "storable_date(offer.get('offer_date'))",
        "storable_date(offer.get('offer_expiry_date'))",
    ):
        assert binding in src, binding


def test_the_reprocess_path_is_coerced_too():
    import inspect
    from core import recruitment_mail_store as store

    assert "storable_date(offer.get('joining_date'))" in inspect.getsource(store.create_or_reprocess_event)


def test_no_raw_model_value_reaches_a_typed_column():
    """A bare offer.get(...) on a date column is the whole defect."""
    import inspect
    from core import recruitment_mail_store as store

    for fn in (store.create_event, store.create_or_reprocess_event):
        src = inspect.getsource(fn)
        for raw in ("offer.get('joining_date')", "offer.get('offer_date')",
                    "offer.get('offer_expiry_date')", "interview.get('date')",
                    "interview.get('time')"):
            for line in src.splitlines():
                if raw in line and "storable_" not in line and "def " not in line:
                    pytest.fail(f"unguarded {raw} in {fn.__name__}: {line.strip()[:90]}")
