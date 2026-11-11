# Sanitized split-migration rehearsal

Date: 2026-08-15
Tool: `scripts/split_migrate.py`
Result: **PASS**

Production was not involved at any point. The rehearsal ran against a wholly
synthetic snapshot and three disposable PostgreSQL 16.14 databases on
`127.0.0.1:55432`.

## What was rehearsed

A generated snapshot standing in for a monolith: 40 candidates, 120 Telegram
groups, 5 referrers, 3 receiver accounts, 3 audit records, 10 payment-proof
files, 3 Data Room documents, 2 account files, 25 PostgreSQL rows in
`recruitment_audit_log`, plus two deliberate decoys — a `*.session` pair the
tool must refuse, and one candidate whose payment proof points at a missing
file.

No real candidate, payment, session or credential data was read or copied.

## Results

| Gate | Result |
|---|---|
| Dry run reports counts, ownership, ambiguity and broken refs without writing | PASS |
| Marketing records classified | 122 records / 3 ledger units |
| Operations records classified | 89 records / 58 ledger units |
| Ambiguous held back for a decision | 1 (`web_push_subscriptions.json`) |
| Excluded and never copied | 4 (2 Telegram sessions, 2 VAPID keys) |
| Broken reference detected | 1 of 1 planted |
| Execute, first run | marketing 3, operations 58 written |
| Execute, second run (idempotency) | marketing 0, operations 0 written |
| Reconciliation: expected vs migrated | PASS both targets |
| Reconciliation: duplicate ledger keys | 0 both targets |
| Ownership isolation: foreign tables with rows | none in either target |
| Telegram session files reaching any destination | 0 |

Destination contents after the run: Marketing holds `groups_list.json` and two
account files and has no `candidates_store` table at all; Operations holds 40
`candidates_store` rows, 25 `recruitment_audit_log` rows and 16 files across
`payment_evidence`, `data_room`, the referrer registry and the receiver
registry.

## Failure handling, observed rather than asserted

The first execution against a source database aborted on
`recruitment_audit_log` with `can't adapt type 'dict'`. The tool reported the
table, the cause and the fact that the ledger and already-migrated tables were
left intact, then exited non-zero. Re-running after the fix resumed without
duplicating anything. This is the intended behaviour: fail loudly, preserve
evidence, stay re-runnable.

The cause was that `psycopg2` decodes `jsonb` into `dict` on read and cannot
adapt it back on insert. Source connections now read `json`/`jsonb` as raw
text, which round-trips losslessly.

## Reconciliation is not declared clean while references are broken

With the planted broken reference present, all four count and isolation checks
passed but the overall result was still `FAIL`. Reconciliation only returns
`PASS` once counts match, no duplicate ledger keys exist, ownership is
isolated, and no broken references or duplicate source ids remain.

## Safety properties

- Any DSN or data directory containing a production marker aborts before a
  connection is opened.
- `--execute` refuses to run without `--confirm-non-production`.
- Telegram sessions and VAPID keys are classified `EXCLUDED`, never copied.
- `web_push_subscriptions.json` is `AMBIGUOUS`: it serves both dashboards and
  needs a product decision before cutover rather than a silent guess.

## Fuller rehearsal across the real schema

A second, substantially larger rehearsal ran against the **actual 39-table
Operations schema** built by the real migration chain, seeded with synthetic
rows through an introspecting seeder that honours nullability, check
constraints and foreign keys: **255 rows across 38 of 39 tables**, with real
parent/child relationships rather than isolated rows.

| Gate | Result |
|---|---|
| Source seeded | 255 rows, 38/39 tables |
| Execute, first run | marketing 4, operations 91 units |
| Execute, second run | 0 and 0 |
| Reconciliation | **PASS** |
| Ownership isolation | PASS — Marketing has no `candidates_store` |
| Destination rows | 362 across 37/40 Operations tables |
| **Foreign keys validated in destination** | **32 of 32, zero violations** |
| Telegram sessions reaching a destination | 0 (2 source decoys correctly refused) |

### Defect this rehearsal exposed

The first fuller run failed on `interview_mail_analyses` with a foreign key
violation against `mailbox_messages`. The registry listed tables alphabetically,
which is not a valid insertion order, and the small single-table rehearsal could
never have revealed it.

Insertion order is now derived from the live schema by topologically sorting the
owned tables on their foreign keys, so a newly added constraint cannot silently
reintroduce the problem. Every foreign key in the destination is now explicitly
`VALIDATE CONSTRAINT`-checked after the run.

### Web push ownership, resolved

`web_push_subscriptions.json` is **Marketing-owned**, no longer ambiguous.
Marketing holds the entire implementation (`core/web_push_api.py`, the VAPID key
endpoint and both subscribe routes); Operations has no push implementation and
no subscription UI, and already reaches users through Marketing's
`POST /internal/v1/notifications` contract (`services/messaging_client.py`).
Subscriptions are therefore assigned to one owner with an explicit cross-project
notification API, rather than duplicated or split.

## Production-scale execution

The copy path was rewritten for volume and re-verified against the same real
39-table schema seeded to **1,547 rows across 38 of 39 tables**.

| Property | Before | Now |
|---|---|---|
| Read | `fetchall()` — whole table into memory | keyset pagination on the primary key, or a server-side cursor when the key is composite |
| Insert | one round trip per row | `execute_values` in batches of 5,000 |
| Resume | table restarts from row 0 | resumes after the last committed key |
| Progress | silent | per-table counts, and every 50,000 rows within a table |

A checkpoint is written **inside the same transaction as its batch**, so a
recorded key can never be ahead of committed rows; an interruption loses at most
one batch. Checkpoints live in the ledger under `source_kind='pg_checkpoint'`
and are cleared when their table completes. Reconciliation excludes them, since
they are bookkeeping rather than migrated units.

### Verified

| Gate | Result |
|---|---|
| Execute | marketing 4, operations 91 units; 1,518 destination rows across 37 tables |
| Second run | 0 and 0 |
| Reconciliation | **PASS** |
| Foreign keys validated in destination | **32 of 32, zero violations** |
| Stale checkpoints after success | 0 |

### Resume, proven rather than asserted

`recruitment_audit_log` was emptied in the destination, its completion marker
removed, and a checkpoint planted at the midpoint key. The next run reported
`resuming after key synthetic-recruitment_audit_log-id-27` and copied **20 rows,
not 40** — it resumed instead of restarting — then cleared the checkpoint.

## Still not rehearsed

True production row counts, and the real distribution of legacy or malformed
records. The mechanics are now volume-appropriate, but the largest table
rehearsed here is thousands of rows, not millions. A sanitized export of
production-shaped data remains a pre-cutover gate, and no such export mechanism
exists in the repository today.
