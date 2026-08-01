"""A profile records the day it closed.

The profile-closure complimentary is earned when the profile closes, which can
fall in a different month from the day the lead was registered. Without a
closure date the earning was attributed to the registration month, so the
amount surfaced against the wrong month's balance.
"""

from __future__ import annotations

from datetime import datetime

from features import candidate_store as cs


def _completed(record, existing=None):
    return cs._normalise({**record, "stage": "completed"}, existing=existing)


def _today():
    return datetime.now().strftime("%Y-%m-%d")


BASE = {
    "name": "Yamini Akhil",
    "reference": "Pavan Kalyan",
    "service_type": "profile_service",
    "date": "2026-06-23",
    "logged_date": "2026-06-23",
    "payment": 22_000,
}


def test_closing_a_profile_stamps_todays_date():
    row = _completed(BASE, existing={**BASE, "stage": "in_progress"})

    assert row["closure_date"] == _today()
    assert row["closure_recorded_at"]


def test_an_open_profile_has_no_closure_date():
    row = cs._normalise({**BASE, "stage": "in_progress"})

    assert row["closure_date"] == ""
    assert row["closure_recorded_at"] == ""


def test_later_edits_do_not_move_an_existing_closure_date():
    closed = {**BASE, "stage": "completed", "closure_date": "2026-07-05",
              "closure_recorded_at": "2026-07-05T09:00:00+00:00"}

    row = cs._normalise({"payment": 25_000}, existing=closed)

    assert row["closure_date"] == "2026-07-05"
    assert row["closure_recorded_at"] == "2026-07-05T09:00:00+00:00"


def test_reopening_clears_the_closure_date():
    closed = {**BASE, "stage": "completed", "closure_date": "2026-07-05"}

    row = cs._normalise({"stage": "in_progress"}, existing=closed)

    assert row["closure_date"] == ""
    assert row["closure_recorded_at"] == ""


def test_reclosing_records_the_new_date_not_the_original():
    closed = {**BASE, "stage": "completed", "closure_date": "2026-07-05"}
    reopened = cs._normalise({"stage": "in_progress"}, existing=closed)

    reclosed = cs._normalise({"stage": "completed"}, existing=reopened)

    assert reclosed["closure_date"] == _today()


def test_an_operator_can_correct_the_closure_date():
    closed = {**BASE, "stage": "completed", "closure_date": "2026-07-05"}

    row = cs._normalise({"closure_date": "2026-07-01"}, existing=closed)

    assert row["closure_date"] == "2026-07-01"


def test_closure_month_drives_attribution_when_recorded():
    """Registered in June, closed in July — the closure belongs to July."""
    row = {**BASE, "stage": "completed", "closure_date": "2026-07-05"}

    assert cs._row_display_month(row) == "2026-06"
    assert cs._row_closure_month(row) == "2026-07"


def test_closure_month_falls_back_to_the_registration_month():
    """Rows closed before closure dates were recorded must not move."""
    row = {**BASE, "stage": "completed"}

    assert cs._row_closure_month(row) == cs._row_display_month(row) == "2026-06"


def test_computed_rows_expose_the_closure_date_and_month():
    enriched = cs._with_computed(
        {**BASE, "stage": "completed", "closure_date": "2026-07-05"}
    )

    assert enriched["closure_date"] == "2026-07-05"
    assert enriched["closure_month"] == "2026-07"
    # The complimentary itself is unchanged — only when it counts moves.
    assert cs.admin_complimentary_amount(enriched) == cs.PROFILE_CLOSURE_COMPLIMENTARY_AMOUNT


def test_closure_date_is_a_patchable_field():
    assert "closure_date" in cs._ALLOWED_FIELDS
