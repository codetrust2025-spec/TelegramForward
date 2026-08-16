#!/usr/bin/env python3
"""Produce a production-SHAPED, PII-free snapshot for the pre-cutover rehearsal.

The migration tool is proven against synthetic data. What remains before a
production cutover is a rehearsal against data with production's *shape* — real
row counts, real cardinality, real relationship density, real legacy oddities —
without any real person's data in it. This tool produces that.

How it differs from generated synthetic data
  Generated data has invented distributions. A snapshot sanitised from a
  restored backup keeps the true shape: how many candidates actually carry
  proofs, how long mail bodies really are, how many rows a table really has.
  Those are exactly the properties that break a migration at scale.

Sanitisation properties
  Deterministic   the same input value always maps to the same output, so joins,
                  de-duplication and identity resolution behave as they do in
                  production.
  Irreversible    mapping is HMAC-based under a salt generated per run and never
                  written anywhere, so the output cannot be mapped back.
  Format-aware    a phone stays a plausible phone, an email stays an email, a
                  UPI id stays a UPI id. Format-dependent code paths still run.
  Fail-closed     a text column that looks sensitive and is not explicitly
                  classified aborts the run. A column added to the schema later
                  cannot silently start leaking.

Safety
  Never writes to the source. Refuses a production target outright. Refuses a
  production SOURCE unless --source-is-restored-backup is passed, which asserts
  the DSN points at a restored copy rather than the live system.

  Intended source is a restored backup, NOT live production. Reading live
  production requires separate explicit approval and is not this tool's job.

Usage
  python scripts/sanitize_snapshot.py \
      --source-dsn postgresql://user@host/restored_copy \
      --target-dsn postgresql://user@host/sanitized \
      --source-data-dir /path/to/restored/data \
      --target-data-dir /path/to/sanitized/data \
      --verify
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable

PRODUCTION_MARKERS = ("teleautomation.online", "prod", "production")

# Columns whose values are replaced. Grouped by the kind of value so the
# replacement keeps the original's shape.
#
# This registry is the auditable statement of what counts as sensitive. It is
# deliberately explicit: see SAFE_TEXT_COLUMNS for the counterpart list, and
# _assert_all_text_classified for the check that keeps both honest.
SCRUB: dict[str, str] = {}


def _register(kind: str, columns: Iterable[str]) -> None:
    for c in columns:
        SCRUB[c] = kind


_register("person_name", [
    "candidate_name", "recruiter_name", "sender_name", "account_holder_name",
    "actor", "updated_by", "created_by", "reviewer", "approved_by",
    # Marketing-side CRM and inbox tables. These live in the monolith schema and
    # not in the Operations one the registry was first written against, so the
    # first production-shaped run refused to proceed until they were classified.
    "name", "username", "profile_name", "display_name", "first_name", "last_name",
])
_register("email", [
    "recruiter_email", "email_address", "candidate_email", "sender_email",
    "recipient_email", "reply_to_email", "return_path_email",
])
_register("phone", [
    "payment_phone_number", "normalized_payment_phone_number", "phone",
    # E.164 numbers and WhatsApp ids are phone numbers in a different dress.
    "phone_e164", "whatsapp_wa_id", "wa_id", "mobile", "whatsapp",
])
_register("upi", ["upi_id", "normalized_upi_id"])
_register("bank_account", ["bank_account_identifier"])
_register("company_name", ["company_name", "provider_name"])
_register("free_text", [
    "summary", "ai_summary", "evidence_summary", "review_notes", "notes",
    "subject", "email_subject", "body_text", "html_body_text",
    "extracted_text", "attachment_evidence", "cited_attachment",
    "source_snippet", "remark", "interview_attendance_remark", "task",
    # Message bodies. The single most sensitive free-text column in the product:
    # real conversations with real people.
    "text", "message", "body", "caption", "last_message",
    # Prose columns the content check found. Replaced outright rather than
    # redacted, because prose carries names, and no pattern finds a name the
    # way one finds an address or a number.
    "location", "detail", "verification_problems",
])
_register("domain", ["company_domain", "sender_domain", "email_domain"])
# Text that must keep its structure because something parses it, but which can
# carry a real address or number inside. The value is preserved and only the
# personal parts inside it are replaced. Found by the first production-shaped
# run: SPF and authentication-results headers, RFC message ids and calendar
# uids all embed real addresses, and none of their column names look sensitive.
_register("redact", [
    "received_spf", "authentication_results", "rfc_message_id", "calendar_uid",
    "error_message", "quoted_evidence", "lead_key", "application_key",
    "job_title", "job_role", "headers", "raw_headers", "snippet_text",
    # A meeting link is an access credential: the id in it joins a real call.
    # Redacted rather than replaced so it stays a URL and anything that parses
    # one still runs.
    "meeting_link", "cited_message_id",
])
_register("filename", ["filename", "original_name", "latest_resume"])
_register("credential", ["credential_ciphertext", "access_token", "refresh_token"])
_register("ip", ["source_ip", "client_ip"])
# Hashes and fingerprints are not PII, but they let an attacker confirm a guess
# by recomputing the digest. Re-hashed under the run salt instead of copied.
_register("rehash", [
    "body_hash", "content_signature", "attachment_fingerprint", "sha256",
])

# Text columns that carry no personal data and MUST be preserved verbatim,
# because behaviour depends on their exact values.
SAFE_TEXT_COLUMNS: frozenset[str] = frozenset({
    # identifiers and foreign keys
    "id", "candidate_id", "email_analysis_id", "mailbox_message_id", "mailbox_id",
    "message_id", "thread_id", "attachment_id", "verification_id", "referrer_id",
    "company_id", "source_id", "run_id", "finding_id", "external_id",
    "idempotency_key", "extracted_text_reference", "slot", "candidate_key",
    "history_id", "entitlement_id", "evidence_id", "case_id", "queue_id",
    "job_id", "notification_id", "approval_id", "gap_id", "event_id",
    # Opaque single-token identifiers. The content check flags these because a
    # numeric id of seven digits or more is indistinguishable from a phone
    # number by shape alone. Each was inspected on the production-shaped copy:
    # every value is one token, no whitespace, no address anywhere in the
    # column. They are preserved for the same reason candidate_id above is —
    # they are the join keys, and reconciliation, orphan detection and
    # duplicate detection are only meaningful if they survive intact.
    "event_fingerprint", "alias_candidate_id", "canonical_candidate_id",
    "sync_cursor", "provider_history_id", "source_history_id", "booking_id",
    "correlation_id", "gmail_account_id", "ai_recruitment_event_id",
    "booking_audit_id", "pipeline_event_id",
    # enums, states and machine labels
    "status", "state", "stage", "contract_name", "model_name", "prompt_name",
    "attachment_type", "email_intent", "outcome", "decision", "role",
    "transaction_type", "settlement_status", "verification_status", "owner_type",
    "source_module", "source_entity_type", "source_entity_id", "mime_type",
    "action", "direction", "reason", "error_code", "ai_last_error_code",
    "ignore_reason", "block_reason", "interview_round", "technology",
    "service_type", "opportunity_type", "purpose", "mode", "source",
    "last_error", "migration_name", "checksum", "kind", "target",
    "processing_mode", "confidence_band", "review_kind", "category",
})

# A text column matching this and absent from both lists aborts the run.
LOOKS_SENSITIVE = re.compile(
    r"name|phone|mobile|email|address|upi|bank|ifsc|holder|resume|proof|"
    r"subject|snippet|body|note|remark|summary|text|content|actor|user|"
    r"password|token|credential|secret|_ip$|^ip$|whatsapp|telegram|attach",
    re.I,
)

TEXTUAL = {"text", "character varying", "character", "citext"}

# Personal data as it appears INSIDE a value. The digit rule deliberately
# refuses to match when the run is part of a longer alphanumeric token, because
# a 32-character hex id contains a 10-digit run roughly always and is not a
# phone number.
EMAIL_IN_TEXT = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
UPI_IN_TEXT = re.compile(r"[A-Za-z0-9._-]+@(?:ok[a-z]+|paytm|ybl|upi|axl|ibl|apl)\b")
DIGITS_IN_TEXT = re.compile(r"(?<![0-9A-Za-z])\d{7,}(?![0-9A-Za-z])")

# Our own output. The verifier must not report the sanitiser's replacements as
# leaks: a hex email local-part is all digits about one time in a hundred, and
# that is not a phone number.
SCRUBBER_OUTPUT = re.compile(
    r"^[0-9a-f]{10}@sanitized\.invalid$|^[0-9a-f]{8}@sanitizedbank$|"
    r"^SANITIZED-NOT-A-CREDENTIAL-[0-9a-f]+$|^sanitized-[0-9a-f]{8,10}[.]|"
    r"^sanitized narrative |^198\.51\.100\.\d+$")


def looks_like_personal_data(text: str) -> bool:
    """Does this INPUT value contain personal data, whatever its column is
    called? Used to classify the source before anything is copied.

    Deliberately stricter than the output check below, and the two are not
    interchangeable. Here a ten-digit run is suspicious whatever it starts with,
    because a real Indian mobile very often starts with 9. On the output side a
    9 is the marker of an already-sanitised number, so the same rule there would
    report every replacement as a leak.
    """
    if SCRUBBER_OUTPUT.match(text):
        return False
    return bool(EMAIL_IN_TEXT.search(text) or UPI_IN_TEXT.search(text)
                or DIGITS_IN_TEXT.search(text))


# Output side. A value is a leak only if it still carries something the
# sanitiser would never emit.
OUTPUT_LEAK_PATTERNS = {
    "email that is not sanitized.invalid":
        re.compile(r"[A-Za-z0-9._%+-]+@(?!sanitized\.invalid|sanitizedbank)"
                   r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    # The boundaries are alphanumeric, not just digits. Without that this fires
    # inside every 32-character hex message id, because a long hex string
    # contains a 10-digit run almost always. Sanitised numbers start with 9, so
    # a run starting 6-8 is one the sanitiser did not produce.
    "10-digit phone not starting 9":
        re.compile(r"(?<![0-9A-Za-z])[6-8]\d{9}(?![0-9A-Za-z])"),
}


def output_leak_label(text: str) -> str | None:
    """Name the reason this OUTPUT value still looks real, or None if clean."""
    if SCRUBBER_OUTPUT.match(text):
        return None
    for label, rx in OUTPUT_LEAK_PATTERNS.items():
        if rx.search(text):
            return label
    return None


FIRST = ["Aarav", "Diya", "Vihaan", "Ananya", "Advait", "Ishita", "Kabir",
         "Meera", "Rohan", "Saanvi", "Arjun", "Nitya", "Dhruv", "Priya"]
LAST = ["Sharma", "Iyer", "Reddy", "Nair", "Gupta", "Menon", "Patel",
        "Rao", "Khanna", "Bose", "Verma", "Pillai"]
COMPANIES = ["Northwind Systems", "Blue Harbour Tech", "Kestrel Labs",
             "Vantage Soft", "Ridgeline Data", "Parallax Consulting",
             "Ironwood Analytics"]


class SanitizeError(RuntimeError):
    """Fatal, reported with context rather than a traceback."""


# ---------------------------------------------------------------------------
# Deterministic, irreversible, format-preserving replacement
# ---------------------------------------------------------------------------

class Scrubber:
    def __init__(self, salt: bytes) -> None:
        self._salt = salt
        self._memo: dict[tuple[str, str], str] = {}

    def _digest(self, kind: str, value: str) -> bytes:
        return hmac.new(self._salt, f"{kind}\x00{value}".encode("utf-8"),
                        hashlib.sha256).digest()

    def _int(self, kind: str, value: str, mod: int) -> int:
        return int.from_bytes(self._digest(kind, value)[:8], "big") % mod

    def value(self, kind: str, original: Any) -> Any:
        if original is None:
            return None
        text = str(original)
        if not text.strip():
            return original
        key = (kind, text)
        if key in self._memo:
            return self._memo[key]
        out = self._make(kind, text)
        self._memo[key] = out
        return out

    def _make(self, kind: str, text: str) -> str:
        d = self._digest(kind, text)
        if kind == "person_name":
            return (f"{FIRST[self._int(kind, text, len(FIRST))]} "
                    f"{LAST[self._int(kind + 'l', text, len(LAST))]}")
        if kind == "company_name":
            return COMPANIES[self._int(kind, text, len(COMPANIES))]
        if kind == "email":
            local = d.hex()[:10]
            return f"{local}@sanitized.invalid"
        if kind == "phone":
            digits = "".join(ch for ch in text if ch.isdigit())
            n = len(digits) or 10
            # Keep length, and keep a leading 9 so Indian-mobile validators pass.
            body = str(self._int(kind, text, 10 ** (n - 1))).zfill(n - 1)
            return "9" + body
        if kind == "upi":
            return f"{d.hex()[:8]}@sanitizedbank"
        if kind == "bank_account":
            digits = "".join(ch for ch in text if ch.isdigit())
            n = max(len(digits), 9)
            return str(self._int(kind, text, 10 ** n)).zfill(n)
        if kind == "ip":
            # 198.51.100.0/24 is reserved for documentation (RFC 5737), so a
            # sanitised address can never route anywhere real.
            return f"198.51.100.{d[0] % 254 + 1}"
        if kind == "credential":
            return f"SANITIZED-NOT-A-CREDENTIAL-{d.hex()[:12]}"
        if kind == "rehash":
            return hashlib.sha256(d).hexdigest()[:len(text)] if text else text
        if kind == "domain":
            return f"sanitized-{d.hex()[:8]}.invalid"
        if kind == "redact":
            # Keep the value; replace only the personal parts inside it, so
            # anything that parses this text still parses it. Replacements go
            # through the ordinary scrubbers, so they stay deterministic and a
            # redacted number still joins to the same number elsewhere.
            out = UPI_IN_TEXT.sub(lambda m: self.value("upi", m.group(0)), text)
            out = EMAIL_IN_TEXT.sub(lambda m: self.value("email", m.group(0)), out)
            out = DIGITS_IN_TEXT.sub(lambda m: self.value("phone", m.group(0)), out)
            return out
        if kind == "filename":
            stem, ext = os.path.splitext(text)
            return f"sanitized-{d.hex()[:10]}{ext or '.bin'}"
        if kind == "free_text":
            # Preserve approximate length: extraction, truncation and column
            # limits all behave differently on a 20-character body than on a
            # 4,000-character one.
            target = min(len(text), 4000)
            unit = f"sanitized narrative {d.hex()[:6]}. "
            return (unit * (target // len(unit) + 1))[:max(target, len(unit))].strip()
        raise SanitizeError(f"no scrubber implemented for kind {kind!r}")


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

def _assert_not_production(label: str, value: str | None) -> None:
    if not value:
        return
    low = value.lower()
    for marker in PRODUCTION_MARKERS:
        if marker in low:
            raise SanitizeError(
                f"refusing to run: {label} contains the production marker "
                f"{marker!r}."
            )


def _connect(dsn: str):
    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SanitizeError("psycopg2 is required. Install psycopg2-binary.") from exc
    return psycopg2.connect(dsn)


def _scrub_json_text(raw: Any, kind: str, scrub: "Scrubber") -> Any:
    """Scrub the string leaves of a json/jsonb value, preserving its structure."""
    if raw is None:
        return None
    try:
        doc = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    except (TypeError, ValueError):
        # Not parseable as JSON: treat as opaque text rather than risk emitting
        # something the column will reject.
        return json.dumps(str(scrub.value(kind, raw)))

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: (scrub.value(JSON_SCRUB_FIELDS[k], v)
                        if k in JSON_SCRUB_FIELDS and not isinstance(v, (dict, list))
                        else walk(v))
                    for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, str) and node.strip():
            return scrub.value(kind, node)
        return node

    return json.dumps(walk(doc))


def _assert_all_text_classified(conn, sample_rows: int = 400) -> list[str]:
    """Fail closed on any text column nobody has classified that either looks
    sensitive by name or turns out to hold personal data.

    The name test alone is not enough, and the first production-shaped run
    proved it: `received_spf`, `authentication_results`, `rfc_message_id` and
    `lead_key` are innocuous names holding real addresses and real account ids.
    So each unrecognised column is also asked what it actually contains.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema='public' ORDER BY table_name, ordinal_position")
        rows = cur.fetchall()

    unclassified: list[str] = []
    for table, col, dtype in rows:
        if dtype not in TEXTUAL or col in SCRUB or col in SAFE_TEXT_COLUMNS:
            continue
        if LOOKS_SENSITIVE.search(col):
            unclassified.append(f"{table}.{col} (name looks sensitive)")
            continue
        with conn.cursor() as cur:
            cur.execute(
                f'SELECT "{col}" FROM "{table}" '
                f'WHERE "{col}" IS NOT NULL AND "{col}" <> %s LIMIT %s',
                ("", sample_rows))
            sampled = [str(r[0]) for r in cur.fetchall()]
        hits = sum(1 for v in sampled if looks_like_personal_data(v))
        if hits:
            unclassified.append(
                f"{table}.{col} (personal data in {hits}/{len(sampled)} sampled rows)")
    return unclassified


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def sanitize_database(src_dsn: str, dst_dsn: str, scrub: Scrubber,
                      batch: int = 5000) -> dict[str, int]:
    import psycopg2.extras

    src = _connect(src_dsn)
    psycopg2.extras.register_default_json(conn_or_curs=src, loads=lambda s: s)
    psycopg2.extras.register_default_jsonb(conn_or_curs=src, loads=lambda s: s)
    dst = _connect(dst_dsn)
    counts: dict[str, int] = {}
    try:
        unclassified = _assert_all_text_classified(src)
        if unclassified:
            raise SanitizeError(
                "these text columns look sensitive but are classified neither as "
                "scrubbed nor as safe, so the run is aborted rather than risk "
                "copying real data:\n  " + "\n  ".join(unclassified) +
                "\n\nAdd each to SCRUB or to SAFE_TEXT_COLUMNS in this file."
            )

        with src.cursor() as c:
            c.execute("SELECT table_name FROM information_schema.tables "
                      "WHERE table_schema='public' AND table_type='BASE TABLE' "
                      "ORDER BY table_name")
            tables = [r[0] for r in c.fetchall()]

        # Alphabetical order is not a valid insertion order: interview_mail_analyses
        # references mailbox_messages. Reuse the migration tool's ordering rather
        # than maintaining a second copy of the same logic.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from split_migrate import _fk_order  # noqa: PLC0415 - avoids a hard import cycle
        tables = _fk_order(src, tables)

        for table in tables:
            with src.cursor() as c:
                c.execute(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s "
                    "ORDER BY ordinal_position", (table,))
                cols = c.fetchall()
            with dst.cursor() as c:
                c.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s", (table,))
                present = {r[0] for r in c.fetchall()}
            use = [(n, dt) for n, dt in cols if n in present]
            if not use:
                continue
            names = [n for n, _ in use]
            quoted = ", ".join(f'"{n}"' for n in names)
            insert = f'INSERT INTO "{table}" ({quoted}) VALUES %s ON CONFLICT DO NOTHING'
            moved = 0
            try:
                with src.cursor(name=f"sanitize_{table}") as s:
                    s.itersize = batch
                    s.execute(f'SELECT {quoted} FROM "{table}"')
                    buf: list[tuple] = []
                    for row in s:
                        out = []
                        for (name, dt), val in zip(use, row):
                            kind = SCRUB.get(name)
                            if not kind:
                                out.append(val)
                            elif dt in ("json", "jsonb"):
                                # Replacing a JSON column with prose produces
                                # invalid JSON. Scrub the string leaves inside
                                # it and keep the structure intact.
                                out.append(_scrub_json_text(val, kind, scrub))
                            else:
                                out.append(scrub.value(kind, val))
                        buf.append(tuple(out))
                        if len(buf) >= batch:
                            with dst.cursor() as d:
                                psycopg2.extras.execute_values(d, insert, buf, page_size=len(buf))
                            dst.commit(); moved += len(buf); buf = []
                    if buf:
                        with dst.cursor() as d:
                            psycopg2.extras.execute_values(d, insert, buf, page_size=len(buf))
                        dst.commit(); moved += len(buf)
            except Exception as exc:
                dst.rollback()
                raise SanitizeError(
                    f"table {table} failed to sanitise: {exc}. Already-written "
                    f"tables are left intact; the source was not modified."
                ) from exc
            if moved:
                counts[table] = moved
                print(f"  {table}: {moved} rows", flush=True)
    finally:
        src.close()
        dst.close()
    return counts


# ---------------------------------------------------------------------------
# JSON stores and file trees
# ---------------------------------------------------------------------------

JSON_SCRUB_FIELDS = {
    "name": "person_name", "phone": "phone", "email": "email",
    "notes": "free_text", "task": "free_text", "remark": "free_text",
    "reference": "person_name", "consultancy": "company_name",
    "account_holder_name": "person_name", "upi_id": "upi",
    "bank_account_identifier": "bank_account", "username": "person_name",
    "latest_resume": "filename", "original_name": "filename",
    "interview_attendance_remark": "free_text", "endpoint": "credential",
    "auth": "credential", "p256dh": "credential", "keys": "credential",
}


def _walk_json(node: Any, scrub: Scrubber) -> Any:
    if isinstance(node, dict):
        return {k: (scrub.value(JSON_SCRUB_FIELDS[k], v)
                    if k in JSON_SCRUB_FIELDS and not isinstance(v, (dict, list))
                    else _walk_json(v, scrub))
                for k, v in node.items()}
    if isinstance(node, list):
        return [_walk_json(v, scrub) for v in node]
    return node


def sanitize_files(src_dir: Path, dst_dir: Path, scrub: Scrubber) -> dict[str, int]:
    """Sanitise JSON stores; replace binary evidence with same-size placeholders."""
    stats = {"json": 0, "placeholders": 0, "skipped_secrets": 0}
    # Sessions and signing keys are never copied in any form.
    never_copy = re.compile(r"\.session|vapid|\.env|credential", re.I)
    for src in sorted(p for p in src_dir.rglob("*") if p.is_file()):
        rel = src.relative_to(src_dir)
        if never_copy.search(rel.as_posix()):
            stats["skipped_secrets"] += 1
            continue
        out = dst_dir / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() == ".json":
            try:
                doc = json.loads(src.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            out.write_text(json.dumps(_walk_json(doc, scrub), indent=1), encoding="utf-8")
            stats["json"] += 1
        else:
            # Payment proofs and Data Room documents are images and PDFs of real
            # people's records. Size and extension are the properties migration
            # cares about, so a same-size placeholder preserves the shape.
            size = src.stat().st_size
            out.write_bytes(b"SANITIZED-PLACEHOLDER\n" * (max(size // 22, 1)))
            stats["placeholders"] += 1
    return stats


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify(dst_dsn: str, dst_dir: Path | None) -> list[str]:
    """Re-scan the OUTPUT for anything that still looks like real data."""
    problems: list[str] = []
    conn = _connect(dst_dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND data_type IN "
                "('text','character varying','character')")
            targets = cur.fetchall()
            for table, col in targets:
                if col in SAFE_TEXT_COLUMNS:
                    continue
                # Hash columns are hex, and a 64-character digest will sooner or
                # later contain a 10-digit run that looks like a phone number.
                # They are already re-hashed under the run salt, so scanning them
                # only produces false positives.
                if SCRUB.get(col) == "rehash":
                    continue
                cur.execute(f'SELECT "{col}" FROM "{table}" WHERE "{col}" IS NOT NULL LIMIT 2000')
                for (val,) in cur.fetchall():
                    label = output_leak_label(str(val))
                    if label:
                        problems.append(f"{table}.{col}: {label}")
                        break
    finally:
        conn.close()
    if dst_dir and dst_dir.exists():
        for p in dst_dir.rglob("*.json"):
            label = output_leak_label(p.read_text(encoding="utf-8", errors="replace"))
            if label:
                problems.append(f"{p.name}: {label}")
    return sorted(set(problems))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source-dsn", required=True,
                    help="restored backup, NOT live production")
    ap.add_argument("--target-dsn", required=True)
    ap.add_argument("--source-data-dir", type=Path)
    ap.add_argument("--target-data-dir", type=Path)
    ap.add_argument("--source-is-restored-backup", action="store_true",
                    help="assert the source DSN is a restored copy, not the live system")
    ap.add_argument("--verify", action="store_true",
                    help="re-scan the output for surviving real data")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args(argv)

    try:
        _assert_not_production("--target-dsn", args.target_dsn)
        if args.target_data_dir:
            _assert_not_production("--target-data-dir", str(args.target_data_dir))
        if not args.source_is_restored_backup:
            _assert_not_production("--source-dsn", args.source_dsn)

        # Generated per run and never written down: without it the mapping cannot
        # be reversed, even by whoever ran the tool.
        salt = secrets.token_bytes(32)
        scrub = Scrubber(salt)

        print("=== sanitising database ===")
        counts = sanitize_database(args.source_dsn, args.target_dsn, scrub)
        total = sum(counts.values())
        print(f"  {total} rows across {len(counts)} tables")

        stats = {}
        if args.source_data_dir and args.target_data_dir:
            print("=== sanitising files ===")
            stats = sanitize_files(args.source_data_dir, args.target_data_dir, scrub)
            print(f"  json={stats['json']} placeholders={stats['placeholders']} "
                  f"never-copied secrets={stats['skipped_secrets']}")

        result = "PASS"
        problems: list[str] = []
        if args.verify:
            print("=== verifying output ===")
            problems = verify(args.target_dsn, args.target_data_dir)
            if problems:
                result = "FAIL"
                for p in problems[:40]:
                    print(f"  LEAK {p}")
            else:
                print("  no residual real-looking data found")
        print(f"\nRESULT: {result}")

        if args.report:
            args.report.write_text(json.dumps({
                "rows_by_table": counts, "row_total": total,
                "files": stats, "verification": result,
                "problems": problems,
            }, indent=2), encoding="utf-8")
            print(f"report written to {args.report}")
        return 0 if result == "PASS" else 1

    except SanitizeError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
