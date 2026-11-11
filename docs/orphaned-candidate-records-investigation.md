# The 36 candidate records that exist only in candidates.json

Date: 2026-08-16
Method: read-only investigation of live production. No write was issued.
Result: **no hard blocker**, one migration rule change, two tool defects fixed

Candidate identities are withheld throughout. Records are labelled C01–C36;
the mapping lives only on the host.

## Classification

| | count | records |
|---|---|---|
| **A** — intentionally deleted / stale historical mirror | 5 | C02, C10, C32, C33, C34 |
| **B** — still referenced by live operational data | **0** | — |
| **C** — likely missing from PostgreSQL unexpectedly | 0 | — |
| **D** — ambiguous, cannot safely determine | 31 | the remainder |

**B = 0 clears the hard blocker.** Every reference to any of the 36, anywhere,
is a file *path* — `/candidates_proofs/<id>/…`, `/candidates_resumes/<id>/…` —
embedded in a live candidate's `proofs[].url`, `resumes[].url` or
`latest_resume.url`, and in two `interview_auto_booking_audit` snapshots whose
own `candidate_id` is a live candidate. No booking, interview, attendance,
mail, BGV, payment or audit row *belongs* to any of the 36. No booking
snapshot's own `id` is one of them.

That has an operational consequence: **the proof and resume files under those
superseded ids must migrate**, or live candidates' URLs break. They do — the
`candidates_proofs` and `candidates_resumes` trees migrate wholesale.

## How much the evidence is worth

An adversarial review of this investigation refuted every load-bearing claim,
and two of its objections were verified as correct. They are recorded here
because they change how much weight the "no references" finding can carry.

**The control group was selected on the outcome.** The first draft argued that
absence of references was meaningful because 20 candidates present in both
stores drew 1,431 mailbox references while the 36 drew none. But **169 of the
195 live candidates (87%) also have zero mailbox references.** Zero references
is the *modal* state of a live candidate. The control was drawn from the
referenced minority, and the contrast it produced was an artefact of that
choice.

**Every referencing table post-dates the records.** Earliest rows:

| table | earliest row |
|---|---|
| `mailbox_messages` | 2026-07-13 |
| `candidate_mailboxes` | 2026-07-13 |
| `recruitment_audit_log` | 2026-07-13 |
| `ai_recruitment_events` | 2026-07-13 |
| `candidate_status_history` | 2026-07-14 |
| `mail_realtime_events` | 2026-07-17 |
| `interview_auto_booking_audit` | 2026-07-20 |

The 36 were created in 2026-06 and stop updating in 2026-07. The entire
recruitment-mail subsystem was built after they went quiet, so it could never
have referenced them. **Their absence from these tables measures the pipeline's
age, not the candidates' reality.**

So B = 0 does not rest on absence of references. It rests on the sweep finding
no *entity* reference through any channel that could carry one:

- 1,826,205 text and jsonb cells across 618 columns in 49 tables
- 20 second-hop identifiers owned by the 36 (`proofs[].id`, `resumes[].id`,
  `slot_screenshot_proof_id`, `latest_resume.id`) swept across the same
  surface — **no new references**
- the file-backed payment indexes the empty payment tables conceal:
  `payment_evidence/manifest.json` (5 entries) and
  `pending_slot_payments/index.json` (1) — **zero references**
- every Marketing store and table

## Why 31 are ambiguous rather than stale

The file is demonstrably superseded. `candidates.json` holds exactly the 102
records of `candidates_email_import_20260715_080150.json`, and the PostgreSQL
export written 13 minutes later holds 112 records and **zero of the 36** — they
were already absent from the live store at that moment. Since then the live
store gained 129 records that never existed in the file.

But *superseded file* does not establish *intentionally removed record*. For 31
of them there is no corroboration in either direction:

- 22 carry no phone and no email at all, so identity matching cannot run
- identity data is too sparse for the rest to help: 195 live records hold only
  34 distinct phones, 20 distinct emails and 37 distinct names, one email
  covering 13 records and one phone covering 26
- `telegram_user_id` is present as a field on 35 of them and **unpopulated
  system-wide**, in the 36 and in the live store alike
- no deletion, archival or merge marker exists on any record

Only 5 have positive corroboration: C02 and C10 appear in the 2026-07-12
pre-dedupe backup and have their files inherited by live candidates; C10, C32,
C33 and C34 have a live twin on a *distinctive* contact value — one held by at
most two live records. Naive matching suggested 13 twins, but several matched
11–18 live records at once, which identifies an organisation, not a person.

**No financial exposure among the ambiguous 31.** The only two records marked
`paid`, and the only two carrying revenue, are C33 and C34 — both with a
distinctive live twin, so the money followed the person. The four uncorroborated
records carrying proof entries have entries that resolve to no file on disk, no
amount and no status.

## Recommended treatment, and what changed

Migrate nothing into `candidates_store` from the file, and quarantine rather
than discard:

1. `candidates_store` is built from PostgreSQL. The 36 are never created, so
   they cannot appear as live candidates — 27 of the ambiguous ones are marked
   `interview_attended` and 30 `slot_confirmed`, and activating that as current
   business state is the outcome most worth avoiding.
2. The mirror is preserved, **in `_archive/`, which the application never
   reads**. This changed as a direct result of the review: the file was
   previously written to the Operations data directory root. `use_postgres()`
   in `core/db/connection.py` is a presence check on `DATABASE_URL` that **fails
   open**, and `features/candidate_store.py` falls back to
   `DATA_DIR/candidates.json`. An unset variable would have promoted this
   superseded 102-record file to the live candidate store and hidden all 195
   real candidates — the exact harm the exclusion exists to prevent, by a
   different route.
3. A quarantine manifest is written beside it naming the archive-only ids, the
   counts, the treatment and the operator action if the drift changes. The
   exclusion was otherwise invisible: file copied, table migrated, both green,
   and nothing recording that a decision had been made.
4. The proof and resume trees migrate wholesale, so files under superseded ids
   survive for the live candidates that inherited their URLs.

## Two tool defects this investigation exposed

**`_check_cross_references` was a structural no-op.** It read `proof["path"]`
or `proof["file"]`; real proof entries carry
`{id, url, note, size, filename, mime_type, uploaded_at, original_name}` and
have neither key, so `ref` was always `None` and `broken_refs` was always empty
— for every candidate, on every run since it was written. It also resolved
against `data/payment_evidence` (6 files) rather than `candidates_proofs` (211)
and `candidates_resumes` (37). **Gate 16's "0 broken references" was therefore
vacuous.** Fixed, and rerun read-only against production: **70 real broken
references**, proof and resume entries whose file exists nowhere.

Those 70 are inherited, not caused by the migration, which copies files
wholesale and neither creates nor repairs them. They are now reported and
counted but excluded from the pass/fail condition — failing a cutover on a
pre-existing monolith condition is the pressure that turns a check back into a
no-op. They are worth fixing in the monolith, separately.

**The archive was written to the application's read path**, described above.

## Open item for the owner

The 31 ambiguous records are quarantined, not deleted and not activated.
Deciding whether they were retired on purpose or lost in the July move to
PostgreSQL needs someone who was there; no evidence in the system settles it.
The quarantine holds them indefinitely at no cost, so the decision can wait.
