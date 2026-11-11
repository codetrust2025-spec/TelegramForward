# Producing a sanitized production-shaped snapshot

Status: **mechanism ready, not yet run against production-shaped data**
Tool: `scripts/sanitize_snapshot.py`

The migration tool is proven against synthetic data. The remaining pre-cutover
gate is a rehearsal against data with production's *shape* — real row counts,
real cardinality, real relationship density, real legacy oddities — containing
no real person's data. This document is the approved procedure for producing it.

Synthetic data has invented distributions. A sanitized snapshot keeps the true
shape: how many candidates actually carry proofs, how long mail bodies really
are, how many rows a table really holds. Those are precisely the properties that
break a migration at scale.

## What the tool guarantees

| Property | How |
|---|---|
| Deterministic | the same input value always maps to the same output, so joins, de-duplication and identity resolution behave as in production |
| Irreversible | HMAC under a salt generated per run and never written anywhere |
| Format-aware | a phone stays a plausible phone, an email an email, a UPI id a UPI id, so format-dependent code paths still run |
| Length-aware | free text keeps approximate length, since truncation and column limits behave differently on 20 characters than on 4,000 |
| Fail-closed | a sensitive-looking text column that is classified neither as scrubbed nor as safe **aborts the run** |
| Non-destructive | never writes to the source; refuses a production target outright |

The fail-closed check is the important one. A column added to the schema months
from now cannot silently start leaking: the run stops and names the column.

## Coverage

74 candidate columns across 22 of 39 tables were reviewed by hand and split into
an explicit scrub registry and an explicit safe list. Pattern matching alone was
not sufficient — `contract_name`, `model_name`, `prompt_name` and `body_hash`
match a PII regex but are enums and digests, while `actor` and `reference` do
not obviously read as personal data but are.

Scrubbed kinds: person names, emails, phones, UPI ids, bank identifiers, company
names, free text, filenames, credentials, IP addresses, and hashes (re-hashed,
because a copied digest lets an attacker confirm a guess by recomputing it).

Files: JSON stores are walked field by field. Payment proofs and Data Room
documents are replaced by same-size placeholders, because size and extension are
what migration cares about. Telegram sessions, VAPID keys, `.env` and credential
files are **never copied in any form**.

## Procedure

Production is never read directly by this tool. Work from a restored backup.

```bash
# 1. On the production host, take a logical backup. READ-ONLY.
#    Requires explicit approval; not part of this tool's remit.
pg_dump --no-owner --no-acl -Fc teleautomation > backup.dump

# 2. Restore it somewhere disposable and isolated. NOT production.
createdb restored_copy
pg_restore --no-owner --no-acl -d restored_copy backup.dump

# 3. Create the sanitized target with the real schema.
createdb sanitized
DATABASE_URL=postgresql://…/sanitized python -m core.migrations.runner

# 4. Sanitize.
python scripts/sanitize_snapshot.py \
    --source-dsn postgresql://…/restored_copy \
    --target-dsn postgresql://…/sanitized \
    --source-data-dir /restore/data \
    --target-data-dir /sanitized/data \
    --source-is-restored-backup \
    --verify --report sanitize-report.json

# 5. Rehearse the split against the sanitized snapshot.
python scripts/split_migrate.py --execute \
    --data-dir /sanitized/data \
    --source-dsn postgresql://…/sanitized \
    --marketing-dsn … --marketing-data-dir … \
    --operations-dsn … --operations-data-dir … \
    --confirm-non-production
python scripts/split_migrate.py --reconcile …
```

`--source-is-restored-backup` exists so that pointing the source at something
production-named is a deliberate, visible act. The target guard has no override.

## Verified behaviour

Exercised against the real 39-table Operations schema, 483 rows across 38
tables, with deliberately planted production-shaped values.

| Check | Result |
|---|---|
| Rows preserved | 483 source → 483 destination, 0 tables mismatched |
| Foreign keys in output | **32 / 32 valid** |
| Planted values surviving anywhere | **0 of 14** searched across every text and jsonb column |
| JSON stores sanitized | 8 |
| Binary evidence replaced by placeholders | 13 |
| Secrets never copied | VAPID keys refused |
| Output verification scan | no residual real-looking data |

Example transformations: `ramesh.kumar@example.com` → `8274e67878@sanitized.invalid`,
`admin.jyothi` → `Saanvi Nair`, `49.37.201.14` → `198.51.100.217`
(RFC 5737 documentation range, unroutable), `Dear Ramesh, your CTC is 12LPA…` →
length-preserved filler.

### Defects this exercise exposed and fixed

1. **Foreign-key ordering.** The sanitizer copied tables alphabetically and
   failed on `interview_mail_analyses` → `mailbox_messages`. It now reuses
   `split_migrate._fk_order` rather than carrying a second copy of that logic.
2. **JSON columns.** `attachment_evidence` is `jsonb`; replacing it with prose
   produced invalid JSON. Scrubbing is now type-aware and walks the string
   leaves, preserving structure.
3. **Verifier false positive.** A 64-character SHA-256 digest eventually
   contains a 10-digit run that matches a phone pattern. Re-hashed columns are
   excluded from that scan.

## Remaining gate

This mechanism is ready. It has **not** been run against production-shaped data,
because that requires a production backup, which requires explicit approval and
a disposable host to restore onto. Until that rehearsal passes, production
cutover stays blocked — but synthetic staging is unaffected and may proceed.
