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

## Not yet rehearsed

The synthetic source exercised one PostgreSQL table. A full-scale rehearsal
against a sanitized copy of the real 35-table monolith schema, with realistic
row volumes, is still required before cutover.
