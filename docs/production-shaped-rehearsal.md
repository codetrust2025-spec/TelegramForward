# Production-shaped migration rehearsal (Gate 16)

Date: 2026-08-16
Result: **PASS**, after four blocking defects were found and fixed
Authorisation: read-only production export, approved 2026-08-15

The earlier rehearsal in `split-migration-rehearsal.md` ran against generated
data and passed. This one ran against data with production's real shape, and it
did not pass — it found four defects that would each have caused silent data
loss or secret disclosure during a cutover. That difference is the entire
argument for this gate.

## What production was, and was not, allowed to do

Production was read once: a `pg_dump --format=custom` of the live database,
107 MB, 11 seconds, and a read of `data/` for the file trees. Nothing else.

Verified before and after: `/health` returned 200 throughout, the PM2 restart
counter stayed at 3 for the whole exercise, nginx stayed active, and the
production database was neither written to nor connected to by any migration
step. The rehearsal ran in its own `postgres:16` container bound to
`127.0.0.1:15432` with its own volume, not the host PostgreSQL.

## The four defects

### 1. Candidates migrated from a stale mirror — 129 live candidates lost

The monolith stores candidates twice, as `candidates.json` and as the
`candidates_store` table, and the two have drifted:

| | count |
|---|---|
| `candidates.json` | 102 |
| `candidates_store` (PostgreSQL) | 195 |
| in both | 66 |
| only in PostgreSQL | 129 |
| only in the file | 36 |

The split tool built the destination table from the file.

Which copy is live is not a matter of opinion. Of the 26 candidates that
recruitment mail actually references, **all 26 are in PostgreSQL and 7 are in
the file**. Migrating from the file would have dropped 129 live candidates,
resurrected 36 the product no longer has, and left 19 of the 26 mail-active
candidates with no candidate record — while reporting a clean run, because a
plausible number of rows did arrive.

Every one of the 100,000-plus orphaned references the validator then found was
a pointer to one of the missing candidates.

Fixed: `candidates_store` migrates from PostgreSQL. The file is still copied,
because *not authoritative* is not the same as *discarded*. The tool now
measures this class of drift and reports it instead of picking a winner
quietly.

**Open decision for the owner: the 36 file-only records are not migrated.**
They are either candidates the product deleted, or candidates the PostgreSQL
store lost. That is a business question.

### 2. Evidence file trees not migrated — 275 files left behind

`FILE_TREES` declared `data/payment_evidence`, which holds six files. The
evidence the product actually writes lives elsewhere:

| tree | files | size |
|---|---|---|
| `data/candidates_proofs` | 211 | 37.1 MB |
| `data/candidates_resumes` | 37 | 10.2 MB |
| `data/handler_expense_proofs` | 16 | 1.2 MB |
| `data/pending_slot_payments` | 11 | 0.8 MB |
| `data/crm` (Marketing stores) | 8 | 11.8 MB |

None were migrated, and nothing said so: the declared tree copied cleanly, so
the run reported success. Payment proofs and resumes would simply not have
arrived.

Fixed. The trees that should *not* move are now named as well — `demo_tools` is
474 MB of third-party installers — because a tree nobody listed looks exactly
like a tree somebody decided against.

### 3. Live Telegram sessions would have been copied

`EXCLUDED_GLOBS` was consulted only when printing the plan. The copy loop took
every file under a declared tree, and production keeps **six `.session` files
inside `data/accounts`**, which is a migrated tree. A cutover would have copied
live Telegram session secrets into the Marketing destination — precisely what
the tool's own docstring promises never happens.

The rehearsal did not surface this through its output, because the sanitiser
strips sessions before the migration ever sees them. A real cutover reads the
live directory. Found by reading the copy path against the stated guarantee.

Fixed: enforced during the copy, and the plan's glob is now recursive, since
the sessions sit in `data/accounts/<name>/` and a top-level glob reported none.

### 4. Sanitiser gaps found by the production schema

The sanitiser was written against the 39-table Operations schema. Production's
monolith schema has 51 tables and 42 json/jsonb columns. Working outward from
each failure:

- Eight Marketing-side columns were unclassified, and the fail-closed check
  correctly refused to run rather than copy them.
- The classification check tested column *names*. `received_spf`,
  `authentication_results`, `rfc_message_id` and `lead_key` are innocuous names
  holding real addresses — about 24,000 rows of them. It now tests content.
- **41 of 42 json/jsonb columns were copied verbatim**, because the copy loop
  read the declared kind before the column type. Among them
  `candidates_store.payload` (personal data in 193 of 195 sampled rows) and
  every stored AI response.
- JSON dict *keys* were never scrubbed, and these stores are keyed **by phone
  number** — 412 real numbers sat in the keys while every value beneath them was
  being carefully replaced.
- The JSON field registry had 19 names against a store that had outgrown them,
  leaving the payment ledger untouched: UTRs, UPI ids, account identifiers and
  the raw OCR text of proof screenshots.
- JSON *numbers* were stepped over entirely: 1,306 Telegram `chat_id` values,
  and `access_hash`, which paired with a user id is what lets you contact that
  person.
- `tg_call_p` and `tg_call_a` in `crm/voice_calls.json` — the Diffie-Hellman
  prime and **secret exponent** for encrypted calls, 617 digits each — fell
  outside every length rule and were copied.

## Evidence

Sanitisation is verified by `scripts/sanitization_audit.py`, which is
deliberately independent of the sanitiser: it takes real values out of the
source and looks for them in the output, rather than re-running the sanitiser's
own checks. A bug that makes the sanitiser skip a column makes its self-check
skip the same column.

| check | result |
|---|---|
| rows compared row-by-row on the primary key | 234,634, **0 unchanged** |
| keyless tables compared as multisets | 33 columns, **0 survivors** |
| personal fragments taken from `redact` columns | 3,063, **0 survived** |
| real addresses harvested from scrubbed columns | 1,873, **0 survived anywhere** |
| real long numbers harvested | 1,533, **0 survived in a scrubbed column** |
| JSON stores audited against the source | 226 files, 2,443 personal atoms, **0 survived** |

Migration validation, by `scripts/migration_validate.py`:

| check | result |
|---|---|
| row parity across 37 shared tables | PASS |
| 32 declared foreign keys | PASS, none violated |
| 13 undeclared reference paths | PASS, 0 orphans |
| natural-key duplicates after the second run | PASS, 0 |
| file references with nothing behind them | PASS, 0 |
| reconciliation, both targets | PASS |
| ownership isolation, both targets | PASS |
| idempotent second run | 0 records written, counts unchanged |
| interrupted run resumed | SIGKILL at 30,788 rows, 12 ledger entries survived, resumed to a PASS |
| source after interrupt and resume | unchanged, 139,533 rows |
| rollback | destinations dropped, monolith intact |

## Measured timings

| phase | seconds |
|---|---|
| `pg_dump` of production, 107 MB | 11 |
| restore into the disposable target | 17 |
| destination schemas from both release migration chains | 1 |
| split migration, 244,907 records and 340 files | 12 |
| reconcile | 1 |
| idempotent second run | 1 |
| resume after an interrupt | 7 |
| post-migration validation | 5 |

Sanitisation (20s) and the independent audit (93s) are rehearsal-only and are
not part of a cutover.

**Data work in a production cutover: about 30 seconds** — dump, schema,
migrate, reconcile, validate. The 30-minute cutover window in the runbook is
not constrained by the data step. It is constrained by service start, proxy
switch, TLS, and the three provider callbacks that must be re-registered one at
a time.

## Disposal

The rehearsal environment held a full copy of production. Container, volume,
dump file and sanitised snapshot were destroyed on completion.
