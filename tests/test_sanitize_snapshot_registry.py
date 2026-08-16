"""The sanitiser's classification registry is the thing that stops a rehearsal
from copying real people's data into a disposable database.

These tests exist because the registry was first written against the Operations
schema and was therefore incomplete for the monolith one. The fail-closed check
caught it, which is the design working — but the columns it caught should stay
caught, and nothing should be able to quietly reclassify them as safe.
"""

from __future__ import annotations

import importlib.util
import json
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


def test_json_keys_that_are_phone_numbers_are_scrubbed():
    """leads, the DM inbox, the block list and voice calls are all keyed BY
    phone number. Scrubbing only values leaves the numbers in the keys."""
    scrubber = sz.Scrubber(b"salt")
    doc = {"leads": {"9876543210": {"status": "new"},
                     "918887776665": {"status": "old"}}}
    out = sz._walk_json(doc, scrubber)

    assert "9876543210" not in out["leads"]
    assert "918887776665" not in out["leads"]
    assert len(out["leads"]) == 2
    # the value under each key is carried across intact
    assert sorted(v["status"] for v in out["leads"].values()) == ["new", "old"]


def test_json_key_scrubbing_is_stable_across_stores():
    """contact_links and leads key the same person by the same number. If the
    two stores scrub it differently the migration's cross-store join stops
    being exercised."""
    scrubber = sz.Scrubber(b"salt")
    a = sz._walk_json({"leads": {"9876543210": 1}}, scrubber)
    b = sz._walk_json({"links": {"9876543210": 2}}, scrubber)
    assert list(a["leads"]) == list(b["links"])


def test_payment_evidence_fields_are_registered():
    """The ledger is the most sensitive store in the product and none of these
    were in the registry."""
    for field, kind in (("utr", "rehash"), ("utr_number", "rehash"),
                        ("transaction_reference", "rehash"),
                        ("receiver_upi_id", "upi"), ("sender_upi_id", "upi"),
                        ("sender_account_identifier", "bank_account"),
                        ("receiver_phone", "phone"),
                        ("raw_detected_text", "free_text"),
                        ("raw_ollama_response", "free_text")):
        assert sz.JSON_SCRUB_FIELDS.get(field) == kind, field


def test_json_values_under_unregistered_keys_are_redacted():
    """A name-based registry cannot keep up with a growing store, so an
    unknown key holding an address must still be handled."""
    scrubber = sz.Scrubber(b"salt")
    doc = {"some_new_field_nobody_registered": "ping recruiter@acme-hiring.com"}
    out = sz._walk_json(doc, scrubber)
    value = out["some_new_field_nobody_registered"]
    assert "recruiter@acme-hiring.com" not in value
    assert value.startswith("ping ")


def test_json_strings_inside_lists_are_redacted():
    scrubber = sz.Scrubber(b"salt")
    out = sz._walk_json({"blocked": ["9876543210", "ok"]}, scrubber)
    assert "9876543210" not in out["blocked"]
    assert "ok" in out["blocked"]


def test_json_leaves_non_personal_data_alone():
    scrubber = sz.Scrubber(b"salt")
    doc = {"status": "active", "count": 7, "enabled": True, "when": "2026-08-15"}
    assert sz._walk_json(doc, scrubber) == doc


def test_json_numbers_that_identify_a_person_are_replaced():
    """Telegram chat ids and phone numbers are plain JSON integers. The walker
    stepped over every non-string, leaving 1,306 real chat ids in the output."""
    scrubber = sz.Scrubber(b"salt")
    out = sz._walk_json({"chat_id": 9803205077, "from_id": -1001234567890}, scrubber)

    assert out["chat_id"] != 9803205077
    assert len(str(out["chat_id"])) == len("9803205077")
    # Telegram group ids are negative and the sign is load-bearing
    assert out["from_id"] < 0
    assert len(str(abs(out["from_id"]))) == len("1001234567890")


def test_timestamps_are_not_mistaken_for_identities():
    """Epoch seconds and millisecond timestamps sit in the same digit range as
    a chat id. Replacing them corrupts ordering and protects nobody."""
    scrubber = sz.Scrubber(b"salt")
    doc = {"created_at": 1755261234, "updated_at_ms": 1755261234567,
           "timestamp": 1755261234, "count": 42}
    assert sz._walk_json(doc, scrubber) == doc


def test_a_bare_ten_digit_mobile_is_caught_whatever_the_key_is_called():
    scrubber = sz.Scrubber(b"salt")
    out = sz._walk_json({"whatever": 9876543210}, scrubber)
    assert out["whatever"] != 9876543210


def test_json_keys_fall_back_to_the_column_registry():
    """An AI response blob uses the same field names as the columns it feeds.
    Classifying a column should classify it inside documents too."""
    assert sz._json_kind("candidate_name") == "person_name"
    assert sz._json_kind("recruiter_email") == "email"
    assert sz._json_kind("job_title") == "redact"
    # the JSON-specific registry still wins where it disagrees
    assert sz._json_kind("utr") == "rehash"


def test_unclassified_json_column_is_scrubbed_not_copied():
    """41 of 42 json columns in the production schema had no declared kind and
    were being copied through verbatim."""
    scrubber = sz.Scrubber(b"salt")
    raw = json.dumps({"candidate_name": "Lakshmi Narayanan",
                      "recruiter_email": "recruiter@acme-hiring.com",
                      "chat_id": 9803205077,
                      "note": "call 9876543210"})
    out = sz._scrub_json_text(raw, None, scrubber)

    assert "Lakshmi Narayanan" not in out
    assert "recruiter@acme-hiring.com" not in out
    assert "9803205077" not in out
    assert "9876543210" not in out
    assert json.loads(out)["candidate_name"]        # still valid JSON


def test_sanitised_output_inside_a_document_is_not_read_as_a_leak():
    """A hex email local-part comes out all digits about one in a hundred
    times. Whole-value matching misses it once the value is a serialised
    document, and then the digits read as a phone sitting next to an @.
    Every jsonb column in the production schema reported exactly that."""
    doc = ("{'candidate': {'name': 'Diya Iyer', "
           "'email': '6123456789@sanitized.invalid'}}")
    assert sz.output_leak_label(doc) is None


def test_a_real_number_beside_sanitised_output_is_still_caught():
    """Stripping our own replacements must not blind the scan to what is left."""
    doc = ("{'email': '6123456789@sanitized.invalid', "
           "'note': 'call 8876543210'}")
    assert sz.output_leak_label(doc) == "10-digit phone not starting 9"


def test_other_replacement_shapes_are_stripped_inside_documents():
    scrubber = sz.Scrubber(b"salt")
    parts = [str(scrubber.value(kind, sample)) for kind, sample in (
        ("email", "a@b.com"), ("upi", "x@okaxis"), ("ip", "203.0.113.9"),
        ("credential", "tok"), ("filename", "cv.pdf"), ("free_text", "x" * 40))]
    assert sz.output_leak_label("{'v': [" + ", ".join(parts) + "]}") is None


def test_telegram_access_hash_is_scrubbed():
    """access_hash is not a hash of anything public. Paired with a user id it
    is what lets you contact that person, so it is closer to a credential."""
    scrubber = sz.Scrubber(b"salt")
    doc = {"conversations": {"7959168911": {"access_hash": 1234567890123456789}}}
    out = sz._walk_json(doc, scrubber)
    hashes = [v["access_hash"] for v in out["conversations"].values()]
    assert hashes[0] != 1234567890123456789
    assert len(str(abs(hashes[0]))) == 19


def test_access_hash_length_is_inside_the_identity_range():
    """A 19-digit value has to be reachable, or the rule silently skips the one
    field in the store that matters most."""
    assert sz._is_numeric_identity("access_hash", 1234567890123456789)
    assert sz._is_numeric_identity("peer_access_hash", -987654321098765432)


def test_telegram_call_key_material_is_not_copied():
    """tg_call_p is the 2048-bit Diffie-Hellman prime for an encrypted call and
    tg_call_a is the secret exponent beside it. 617 decimal digits, so both sat
    outside the identity range and were being copied verbatim."""
    scrubber = sz.Scrubber(b"salt")
    prime = int("7" * 617)
    secret = int("3" * 615)
    out = sz._walk_json({"sessions": {"abc": {"tg_call_p": prime,
                                              "tg_call_a": secret}}}, scrubber)
    got = out["sessions"]["abc"]
    assert got["tg_call_p"] != prime
    assert got["tg_call_a"] != secret
    # length is preserved so anything that checks the modulus size still works
    assert len(str(got["tg_call_p"])) == 617
    assert len(str(got["tg_call_a"])) == 615


def test_key_material_is_caught_by_size_not_by_name():
    """Naming the field would only cover the fields we happen to know about."""
    assert sz._is_key_material(int("1" * 32))
    assert sz._is_key_material(-int("9" * 200))
    assert not sz._is_key_material(1755261234567)
    assert not sz._is_key_material(True)


def test_digit_string_is_deterministic_and_exact_length():
    a, b = sz.Scrubber(b"s"), sz.Scrubber(b"s")
    for length in (1, 9, 10, 32, 617):
        first = a.digit_string("number", "seed", length)
        assert len(first) == length
        assert first.isdigit()
        assert first == b.digit_string("number", "seed", length)
    assert sz.Scrubber(b"other").digit_string("number", "seed", 40) != \
        a.digit_string("number", "seed", 40)
