# Final production-shaped rehearsal

Date: 2026-08-16
Tooling: monolith `codex/split-current-main-resync-20260815`, all fixes of 2026-08-16
Releases: Marketing `2f6fe881…`, Operations `0207819…`
Result: **PASS**, after three further defects were found and fixed

This is the run that closes the residual left by the first rehearsal: the
earlier one predated several tool changes, and one of its checks turned out to
have been vacuous. Everything below was executed end to end on current code.

It did not pass first time. A fresh rehearsal on changed tooling found three
new arithmetic defects, two of which would have failed reconciliation during
the real cutover.

## What was found this time

**The plan counted files the copy refuses.** `build_plan` counted every file in
a migrated tree; `execute` skips excluded ones. Expected and migrated therefore
differed by exactly the number of secrets present — reconciliation failing
*because the safety feature worked*. Production keeps six `.session` files
inside `data/accounts`, a migrated tree, so this would have failed at cutover.
Caught by planting decoy session files in the snapshot rather than trusting
that the sanitiser had already removed the real ones.

**The quarantine manifest was counted as a migrated record.** It describes the
migration; it is not something the migration moved. Migrated exceeded expected
by one.

**Its ledger row was counted too.** The manifest is ledgered so a re-run does
not rewrite it, and the reconciliation counts ledger rows. Resume checkpoints
already had this exact shape and were already excluded; artefact rows now share
that exclusion via a kind prefix.

## Sequence and evidence

| step | result |
|---|---|
| Read-only `pg_dump` of production | 108 MB, **8 s**, sha256 `509c69fa…` |
| Restore into a disposable container | **18 s**, 51 tables, 0 diagnostics, 195 candidates |
| Isolation | own `postgres:16` container, loopback `127.0.0.1:15433`, own volume, host PostgreSQL untouched |
| Sanitiser | **42 s**, PASS, no residual real-looking data |
| Independent audit | **PASS** |
| Destination schemas from the release migration chains | Marketing 2 tables / 0 FKs, Operations 39 tables / **32 FKs** |
| `--execute` | **12 s**, Marketing 238 records, Operations 318 |
| `--reconcile` | **PASS** both targets, ownership isolation **PASS** both |
| `migration_validate` | **PASS** |

### Independent sanitisation audit

| check | result |
|---|---|
| rows compared row-by-row on the primary key | 237,076, **0 unchanged** |
| keyless tables compared as multisets | **0 survivors** |
| personal fragments from `redact` columns | **0 survived** |
| real addresses harvested from scrubbed columns | 1,873, **0 survived anywhere** |
| real long numbers harvested | 1,547, **0 survived in a scrubbed column** |
| JSON stores audited against the source | 226 files, 2,443 personal atoms, **0 survived** |

### Migration validation

| check | result |
|---|---|
| row parity, 37 shared tables | PASS, 0 differing |
| 32 declared foreign keys | PASS, 0 violated |
| 13 undeclared reference paths | PASS, **0 orphans** |
| natural-key duplicates after the second run | PASS, **0** |
| file references with nothing behind them | PASS, **0** |

## The specific verifications requested

**Candidate source is PostgreSQL.** Source table 195, destination table 195,
JSON mirror 102. The destination matches the table, not the mirror.

**The 36 archive-only records follow the quarantine policy.** The manifest
records file=102, table=195, both=66, **archive_only=36**, and lists all 36 ids
with the treatment and the operator action if the drift changes.

**The archive is outside every runtime read path.** `candidates.json` is
**absent** from the Operations data directory root — the path
`features/candidate_store.py` reads — and present in `_archive/`, holding all
102 records. This matters because `use_postgres()` fails open, so a missing
`DATABASE_URL` would otherwise have promoted the superseded mirror over the
live store.

**Evidence, proof and resume trees migrate exactly.**

| tree | source | destination |
|---|---|---|
| `candidates_proofs` | 211 | 211 |
| `candidates_resumes` | 37 | 37 |
| `payment_evidence` | 6 | 6 |
| `data_room` | 4 | 4 |
| `handler_expense_proofs` | 16 | 16 |
| `pending_slot_payments` | 11 | 11 |
| `accounts` (Marketing) | 226 | 226 |
| `crm` (Marketing) | 8 | 8 |

**Telegram sessions are excluded.** Two decoy `.session` files were planted in
a migrated tree alongside an ordinary `state.json`. Sessions in either
destination: **0**. The ordinary neighbour was copied, so the exclusion is
selective rather than the tree being skipped.

**Inherited dangling references are reported, not misclassified.**
`inherited_broken_references: 70`, reconcile `PASS`. The migration copies files
wholesale and neither creates nor repairs these; they are a monolith data
quality issue worth fixing separately.

**Ownership isolation.** PASS both directions — no table owned by one service
holds rows in the other.

**Idempotent second run.** 0 records written; rows unchanged at Marketing 240 /
Operations 247,688; files unchanged at 527.

**Checkpoint and resume.** SIGKILL at 16,440 rows with 8 ledger rows surviving.
Resumed in **8 s** to reconcile PASS and validate PASS.

**The source is never written.** 140,939 key-table rows before the interrupt and
after the resume.

**Rollback.** Both destinations dropped and their trees removed; the sanitised
copy and the unsanitised copy both still hold 195 candidates.

## Production was untouched

Verified before the export, after the export, and after the whole rehearsal:

- `/health` **200** throughout
- PM2 restart counter **3**, unchanged
- nginx active, serving `releases/68a28ecf…`
- database 353 MB, 51 tables, 195 candidates
- `data/candidates.json` mtime unchanged at 2026-07-22 10:37:13
- 5 Telegram session files intact

No migration step connected to the production database. The only production
access was one `pg_dump` and reads of `data/`.

## Disposal

Container destroyed, volume destroyed, the 108 MB dump shredded, sanitised
snapshot and shipped release trees removed, and both rehearsal directories
deleted. 649 MB → nothing. Zero rehearsal containers, zero volumes, no
`production.dump` anywhere on the host. The leftover reports were scanned
before deletion: 0 addresses, 0 phone-shaped runs, 0 UPI ids.

## Cutover cost, measured

| phase | seconds |
|---|---|
| `pg_dump` of production | 8 |
| destination schemas | 0 |
| migration | 12 |
| reconcile | <1 |
| validate | ~5 |
| resume after an interrupt | 8 |

**About 25 seconds of data work.** Sanitisation (42 s) and the audit are
rehearsal-only. The cutover window is bounded by service start, proxy switch,
TLS and the three provider callbacks that must be re-registered one at a time —
not by the migration.
