"""The sanitiser's classification registry is the thing that stops a rehearsal
from copying real people's data into a disposable database.

These tests exist because the registry was first written against the Operations
schema and was therefore incomplete for the monolith one. The fail-closed check
caught it, which is the design working — but the columns it caught should stay
caught, and nothing should be able to quietly reclassify them as safe.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "sanitize_snapshot",
    Path(__file__).resolve().parents[1] / "scripts" / "sanitize_snapshot.py",
)
sz = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sz)


# Columns the first production-shaped run refused to proceed on, with the kind
# each must keep. If a change unclassifies one of these, real values reach the
# snapshot.
PRODUCTION_EXPOSED = {
    "contact_links.phone_e164": ("phone_e164", "phone"),
    "contact_links.whatsapp_wa_id": ("whatsapp_wa_id", "phone"),
    "contact_links.profile_name": ("profile_name", "person_name"),
    "crm_leads.name": ("name", "person_name"),
    "crm_leads.username": ("username", "person_name"),
    "inbox_conversations.username": ("username", "person_name"),
    "inbox_conversations.name": ("name", "person_name"),
    "inbox_messages.text": ("text", "free_text"),
}


@pytest.mark.parametrize("qualified", sorted(PRODUCTION_EXPOSED))
def test_columns_the_production_schema_exposed_stay_classified(qualified):
    column, expected_kind = PRODUCTION_EXPOSED[qualified]
    assert sz.SCRUB.get(column) == expected_kind, (
        f"{qualified} must be scrubbed as {expected_kind!r}; it holds real "
        f"personal data in the production schema"
    )


def test_no_column_is_both_scrubbed_and_preserved():
    """A column in both lists would be preserved verbatim by whichever check
    runs first, so the contradiction has to be impossible rather than ordered."""
    overlap = sorted(set(sz.SCRUB) & set(sz.SAFE_TEXT_COLUMNS))
    assert not overlap, f"classified as both scrubbed and safe: {overlap}"


def test_every_scrub_kind_has_an_implementation():
    """A kind with no branch in _make raises only when a row of that kind is
    reached — potentially deep into a long run."""
    scrubber = sz.Scrubber(b"test-salt-not-a-real-one")
    for column, kind in sorted(sz.SCRUB.items()):
        out = scrubber.value(kind, "sample value 1234567890")
        assert out, f"{column} ({kind}) produced an empty value"


def test_unclassified_sensitive_column_is_reported():
    """The fail-closed check itself: a new sensitive-looking text column that
    nobody classified must be reported, not passed through."""

    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, _sql):
            pass

        def fetchall(self):
            return [
                ("new_table", "candidate_home_address", "text"),
                ("new_table", "status", "text"),           # safe-listed
                ("new_table", "phone_e164", "text"),       # now scrubbed
                ("new_table", "row_count", "integer"),     # not textual
            ]

    class _Conn:
        def cursor(self):
            return _Cur()

    unclassified = sz._assert_all_text_classified(_Conn())
    assert unclassified == ["new_table.candidate_home_address"]


def test_scrubbing_is_deterministic_and_irreversible():
    original = "Lakshmi Narayanan"
    a = sz.Scrubber(b"salt-one")
    b = sz.Scrubber(b"salt-two")

    # Same salt, same input -> same output, so joins and de-duplication behave
    # as they do in production.
    assert a.value("person_name", original) == a.value("person_name", original)
    # Different run salt -> different output, so two snapshots cannot be
    # correlated back to a shared original.
    assert a.value("person_name", original) != b.value("person_name", original)
    # The original must not survive anywhere in the replacement.
    assert original not in a.value("person_name", original)


def test_message_bodies_keep_their_shape_without_their_content():
    """inbox_messages.text is the most sensitive column in the schema. Length
    has to survive because truncation and column limits depend on it."""
    scrubber = sz.Scrubber(b"salt")
    secret = "Please transfer 5000 to 9876543210, my UPI is real@okaxis"
    out = scrubber.value("free_text", secret)

    assert "9876543210" not in out
    assert "real@okaxis" not in out
    assert "5000" not in out
    assert abs(len(out) - len(secret)) <= len("sanitized narrative 000000. ")


def test_phone_scrub_keeps_length_and_validator_compatibility():
    scrubber = sz.Scrubber(b"salt")
    out = scrubber.value("phone", "9876543210")
    assert out != "9876543210"
    assert len(out) == 10 and out.isdigit() and out.startswith("9")


def test_sensitive_looking_safe_columns_are_identifiers_or_enums():
    """SAFE_TEXT_COLUMNS is an override of the fail-closed check, so anything in
    it that looks sensitive needs to be an id, an enum or a machine label."""
    deliberate = {
        "attachment_id", "attachment_type", "contract_name",
        "email_analysis_id", "email_intent", "extracted_text_reference",
        "migration_name", "model_name", "prompt_name",
    }
    flagged = {c for c in sz.SAFE_TEXT_COLUMNS if sz.LOOKS_SENSITIVE.search(c)}
    unreviewed = flagged - deliberate
    assert not unreviewed, (
        "these were added to the safe list without review, and each one "
        f"disables the fail-closed check for that column: {sorted(unreviewed)}"
    )
