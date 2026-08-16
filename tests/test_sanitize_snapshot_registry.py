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

    columns = [
        ("new_table", "candidate_home_address", "text"),  # name looks sensitive
        ("new_table", "status", "text"),                  # safe-listed
        ("new_table", "phone_e164", "text"),              # scrubbed
        ("new_table", "row_count", "integer"),            # not textual
        ("new_table", "dispatch_v2", "text"),        # innocuous name, real data
        ("new_table", "queue_label", "text"),             # innocuous name, clean
    ]
    # What each unrecognised column would return when sampled.
    samples = {
        "dispatch_v2": [("forwarded to recruiter@acme-hiring.com",)],
        "queue_label": [("batch-7 evening",)],
    }

    class _Cur:
        def __init__(self):
            self._rows = columns

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, sql, params=None):
            if "information_schema" in sql:
                self._rows = columns
            else:
                column = sql.split('"')[1]
                self._rows = samples.get(column, [])

        def fetchall(self):
            return self._rows

    class _Conn:
        def cursor(self):
            return _Cur()

    unclassified = sz._assert_all_text_classified(_Conn())
    assert unclassified == [
        "new_table.candidate_home_address (name looks sensitive)",
        "new_table.dispatch_v2 (personal data in 1/1 sampled rows)",
    ]


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


def test_content_check_catches_an_innocuous_name_holding_real_data():
    """The reason the name test is not enough. `received_spf` looks like a
    protocol field and holds the real sender's address."""
    spf = "pass (google.com: domain of recruiter@acme-hiring.com designates ...)"
    assert sz.looks_like_personal_data(spf)

    msgid = "<CAF7x9y=abc@mail.acme-hiring.com>"
    assert sz.looks_like_personal_data(msgid)

    lead_key = "telegram:9876543210"
    assert sz.looks_like_personal_data(lead_key)


def test_content_check_does_not_fire_on_opaque_identifiers():
    """A 32-character hex id contains a 10-digit run almost always. Treating
    that as a phone number would make the check useless through noise."""
    for opaque in (
        "18f3a4b26123456789cdef0123456789",
        "199a7c1234567890",
        "a1b2c3d4e5f60718293a4b5c6d7e8f90",
    ):
        assert not sz.looks_like_personal_data(opaque), opaque


def test_content_check_does_not_fire_on_our_own_output():
    scrubber = sz.Scrubber(b"salt")
    for kind, sample in (("email", "someone@real.com"),
                         ("person_name", "Real Person"),
                         ("free_text", "a real narrative about a real person"),
                         ("ip", "203.0.113.9")):
        assert not sz.looks_like_personal_data(str(scrubber.value(kind, sample)))


def test_redact_keeps_structure_and_removes_the_personal_parts():
    """redact exists for text something else parses. The surrounding structure
    has to survive or the format-dependent code path stops being exercised."""
    scrubber = sz.Scrubber(b"salt")
    spf = "pass (google.com: domain of recruiter@acme-hiring.com designates 10.1.2.3)"
    out = scrubber.value("redact", spf)

    assert "recruiter@acme-hiring.com" not in out
    assert out.startswith("pass (google.com: domain of ")
    assert out.endswith("designates 10.1.2.3)")
    assert "@sanitized.invalid" in out
    assert sz.output_leak_label(out) is None


def test_redact_is_deterministic_so_joins_still_work():
    """A redacted message id has to keep joining to the same message id
    wherever else it appears, or the migration's dedupe stops being tested."""
    scrubber = sz.Scrubber(b"salt")
    msgid = "<CAF7x9y=abc@mail.acme-hiring.com>"
    assert scrubber.value("redact", msgid) == scrubber.value("redact", msgid)
    # and a different original must not collide with it
    other = "<CAF7x9y=xyz@mail.acme-hiring.com>"
    assert scrubber.value("redact", msgid) != scrubber.value("redact", other)


def test_redact_replaces_embedded_numbers_with_non_phone_shaped_ones():
    scrubber = sz.Scrubber(b"salt")
    out = scrubber.value("redact", "telegram:9876543210")
    assert out.startswith("telegram:")
    assert "9876543210" not in out
    assert sz.output_leak_label(out) is None


def test_the_two_detectors_are_not_interchangeable():
    """A real Indian mobile usually starts with 9, and so does every number the
    sanitiser emits. The source check must catch the first; the output check
    must not report the second. Collapsing them breaks one or the other."""
    real_nine = "call me on 9876543210"
    assert sz.looks_like_personal_data(real_nine)      # source: catch it
    assert sz.output_leak_label(real_nine) is None     # output: 9 means sanitised

    real_eight = "call me on 8876543210"
    assert sz.looks_like_personal_data(real_eight)
    assert sz.output_leak_label(real_eight) == "10-digit phone not starting 9"


def test_domain_kind_does_not_resolve_anywhere_real():
    scrubber = sz.Scrubber(b"salt")
    out = scrubber.value("domain", "acme-hiring.com")
    assert "acme-hiring" not in out
    assert out.endswith(".invalid")


def test_columns_the_verifier_caught_are_now_classified():
    """The second production-shaped run's findings, pinned the same way as the
    first run's."""
    expected = {
        "received_spf": "redact",
        "authentication_results": "redact",
        "rfc_message_id": "redact",
        "calendar_uid": "redact",
        "error_message": "redact",
        "quoted_evidence": "redact",
        "lead_key": "redact",
        "application_key": "redact",
        "job_title": "redact",
        "job_role": "redact",
        "company_domain": "domain",
    }
    for column, kind in expected.items():
        assert sz.SCRUB.get(column) == kind, f"{column} must be scrubbed as {kind}"


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


def test_a_pooled_name_is_never_handed_back_unchanged():
    """The name pool is 14 x 12. About one name in 168 hashes onto itself, and
    a real person seeing their own name in the output cannot tell that from a
    leak. Every name in the pool must map to something else."""
    scrubber = sz.Scrubber(b"salt")
    for first in sz.FIRST:
        for last in sz.LAST:
            original = f"{first} {last}"
            assert scrubber.value("person_name", original).casefold() != original.casefold()
    for company in sz.COMPANIES:
        assert scrubber.value("company_name", company).casefold() != company.casefold()


def test_avoiding_self_collision_stays_deterministic():
    a, b = sz.Scrubber(b"same-salt"), sz.Scrubber(b"same-salt")
    for name in ("Aarav Sharma", "Someone Else", sz.FIRST[0] + " " + sz.LAST[0]):
        assert a.value("person_name", name) == b.value("person_name", name)


def test_ai_prose_columns_are_replaced_not_redacted():
    """Redaction finds addresses and numbers. It cannot find a name, and these
    columns are AI text about a named candidate at a named company."""
    for column in ("ai_reason", "recommended_action", "reasoning", "rationale",
                   "mismatch_detail", "booking_block_reason"):
        assert sz.SCRUB.get(column) == "free_text", column


def test_status_vocabularies_are_preserved_exactly():
    for column in ("candidate_status", "booking_status", "system_status",
                   "source_type", "previous_detected_status"):
        assert column in sz.SAFE_TEXT_COLUMNS, column
        assert column not in sz.SCRUB, column
