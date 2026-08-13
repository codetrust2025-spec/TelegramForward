"""A wording heuristic must never outrank the model's own verdict.

Migration 012 restores interview reviews that a legacy cleanup had archived.
Its CASE falls back to `structured_result->>'interview_event'` whenever
`original_primary_status` is not an INTERVIEW_* value:

    SET primary_status=CASE
          WHEN COALESCE(e.original_primary_status,'') LIKE 'INTERVIEW_%'
            THEN e.original_primary_status
          ELSE e.structured_result->>'interview_event'
        END

`interview_event` is derived from wording by `classify_context`, not answered by
the model. In Production that promoted five events to INTERVIEW_CONFIRMED whose
own stored result said SELECTION_NEEDS_REVIEW. The clearest is a Naukri notice
whose entire body is:

    "The status of your job application on Naukri.com has been updated"

which states no interview, no date and no time. It was left sitting in the
review queue labelled as a confirmed interview.

Migration 025 restores the verdict each event was actually built from, and
keeps the row visible so the restore's real purpose -- not losing the review --
still holds.
"""

from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "core" / "migrations"
RESTORE = (MIGRATIONS / "012_recruitment_mail_restore_interview_reviews.sql").read_text(encoding="utf-8")
TRUTH = (MIGRATIONS / "025_recruitment_mail_restore_status_truth.sql").read_text(encoding="utf-8")


def test_the_heuristic_fallback_that_caused_this_still_exists_upstream():
    """If 012 ever stops using the heuristic, 025 is no longer needed."""
    assert "structured_result->>'interview_event'" in RESTORE


def test_the_correction_restores_the_models_own_verdict():
    assert "SET primary_status = original_primary_status" in TRUTH


def test_the_correction_only_touches_rows_the_restore_relabelled():
    assert "cleanup_version = 'interview_cleanup_restore_v1'" in TRUTH
    assert "primary_status LIKE 'INTERVIEW_%'" in TRUTH


def test_it_never_downgrades_an_event_the_model_called_an_interview():
    """The model's answer is the authority in both directions."""
    for guard in (
        "COALESCE(original_primary_status, '') NOT LIKE 'INTERVIEW_%'",
        "COALESCE(structured_result->>'status', '') NOT LIKE 'INTERVIEW_%'",
        "COALESCE(structured_result->>'primary_status', '') NOT LIKE 'INTERVIEW_%'",
    ):
        assert guard in TRUTH, guard


def test_it_only_touches_events_carrying_no_schedule_at_all():
    """A row with a real date or time is evidence of a real interview."""
    assert "interview_date IS NULL" in TRUTH
    assert "interview_time IS NULL" in TRUTH


def test_it_never_blanks_the_status():
    """original_primary_status must be present, or there is nothing to restore."""
    assert "COALESCE(original_primary_status, '') <> ''" in TRUTH


def test_it_is_idempotent_because_migrations_run_on_every_startup():
    """`ensure_schema` replays every migration each boot, unconditionally."""
    assert "cleanup_version = 'interview_cleanup_restore_truth_v3'" in TRUTH
    # the row it stamps no longer matches its own predicate
    assert TRUTH.index("SET primary_status") < TRUTH.index("WHERE cleanup_version")


def test_the_restore_keeps_the_event_visible():
    """025 must not undo 012's purpose: the review has to stay reachable."""
    assert "visible_in_offer_review" not in TRUTH.split("WHERE")[0]


def test_every_migration_is_registered_for_the_startup_sweep():
    """`ensure_schema` globs *_recruitment_mail_*.sql; a misnamed file is skipped."""
    assert (MIGRATIONS / "025_recruitment_mail_restore_status_truth.sql").exists()
    assert sorted(p.name for p in MIGRATIONS.glob("*_recruitment_mail_*.sql"))[-1] == (
        "025_recruitment_mail_restore_status_truth.sql"
    )
