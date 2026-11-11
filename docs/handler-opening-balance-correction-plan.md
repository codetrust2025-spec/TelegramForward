# Handler opening-balance correction — DEPLOYED AND VERIFIED

Date: 2026-08-17
Status: **executed in production 2026-08-17T20:56Z, verified through the live backend.**
Supersedes the figures in [`handler-opening-balance-audit.md`](handler-opening-balance-audit.md) §5 and §8.

> **Outcome.** August opening **₹1,54,000 → ₹22,000**, closing **₹1,59,500 →
> ₹32,500**, matching the rehearsal exactly. Operations release
> `ad5e0e6` → `e74b8a0`. Marketing untouched. No database row was edited and no
> balance was set by hand — every figure is derived, and changed only because
> its missing inputs came back.
>
> Backups, both state snapshots and an exact `ROLLBACK.sh` are retained in
> `/opt/teleautomation-backups/pre-openingbalance-20260817T171800Z/`.
> Rollback was not needed and was not used.
>
> Sections 1–9 below are the pre-execution record and are left as written.
> Section 11 records what actually happened.

---

## 1. What changed since the audit

The audit computed the corrected balances by summing the monolith JSON by hand.
Running the **actual backend** against a restored copy proved two of those
figures wrong. Both errors made the correction look larger than it is.

| | audit said | rehearsal proved | why |
|---|---:|---:|---|
| Pavan Kalyan opening | −1,500 | **+3,500** | a ₹5,000 payout is **voided** and must not count |
| total opening | 17,000 | **22,000** | same ₹5,000 |
| total closing | 22,500 | **32,500** | restoring salaries also accrues Thrilok's **August** salary (₹15,000), which the audit's `opening + 5,500` shortcut omitted |
| Thrilok opening | 15,000 | 15,000 | unchanged |
| Venugopal opening | 3,500 | 3,500 | unchanged |

The voided row is not an anomaly — it is the anti-double-count control working:

```json
{ "id": "6b179d677b", "reference": "Pavan Kalyan", "amount": 5000,
  "date": "2026-07-28", "void_status": "RECLASSIFIED_TO_RECOVERY",
  "void_reason": "Same transaction as recovery le_200d03469da441e0
                  (matched on payment_id). Money must affect the balance once.",
  "voided_by": "authorized administrator", "voided_at": "2026-08-03T11:40:11Z" }
```

An administrator voided it on 2026-08-03 precisely because the same ₹5,000 is
already the `referrer_recovery` `le_200d03469da441e0`. Counting it, as the audit
did, would have deducted one transfer twice — the exact error the void prevents.

## 2. Phase 1 — the sources are authoritative

Byte-identical between the live monolith and the snapshot taken at the cutover,
so nothing has drifted since the split:

| file | bytes | rows | SHA-256 (first 32) | monolith == pre-cutover backup |
|---|---:|---:|---|---|
| `handler_expenses.json` | 14,277 | 25 | `4b7806a9782d44cf8aa64e328453d30c` | **yes** |
| `handler_salaries.json` | 330 | 1 | `125421c5f7e109af3c6a7335165705c4` | **yes** |
| `payment_verification_ledger.json` | 293,421 | 16 entries | `170eb89b4f6c36326434da4e483c6618` | **yes** |

Not stale duplicates: `handler_expenses.json` grew 9,419 B → 14,277 B between
the 2026-07-19 and 2026-08-16 backups, adding 6 rows with **zero** rows removed
and **zero** mutated — the signature of a live append-only ledger.

Date range 2026-04-28 → 2026-08-07. In scope for the August opening (months
before August, excluding the settled Apr/May), **non-voided**: Thrilok ₹87,000,
Pavan Kalyan ₹35,000, Venugopal ₹30,000 — ₹152,000.

Salary store: Thrilok only, ₹15,000/month, `active_from` 2026-05, no end date.

Ledger: 2 × `referrer_recovery` of ₹5,000 on 2026-07-22, both
`LUKKA PAVAN KALYAN` → resolves to handler key `pavan kalyan`.

> **Single point of failure.** These three files exist in exactly one live
> location plus two tarballs. Losing `/opt/telegramforward/data` loses the only
> convenient copy of the company's payout history.

## 3. Phase 2 — the ledger merge

Operations' ledger holds **0 entries** but **2 payments and 3 evidence records
written after the cutover**. Overwriting it destroys those; overwriting the
monolith's loses the history. So: merge, never copy.

`scripts/merge_payment_ledger.py` — dry-run by default.

| collection | identity key | why this key |
|---|---|---|
| `entries` | `idempotency_key` → `id` | both unique (16/16) |
| `payments` | `payment_id` | **only** unique key: `idempotency_key` is 27/28 and `evidence_id` 27/28, because one proof is reused across two payments |
| `evidence` | `evidence_id` | unique (33/33) |
| `entitlements` | `entitlement_id` | unique (11/11) |

The tool re-verifies uniqueness at run time and **refuses** rather than guess —
keying `payments` on the obvious `idempotency_key` would have silently collapsed
two real payments into one.

Rehearsed result — **zero collisions**, so the merge is a pure union:

| collection | before | available | imported | after |
|---|---:|---:|---:|---:|
| entries | 0 | 16 | 16 | 16 |
| payments | 2 | 28 | 28 | 30 |
| evidence | 3 | 33 | 33 | 36 |
| entitlements | 0 | 11 | 11 | 11 |
| **total** | **5** | **88** | **88** | **93** |

- All 5 post-cutover Operations rows survive **and stay first** in file order.
- **Idempotent**: the second run imported 0 rows and left the file
  byte-identical (`4a3923243bad2ef1ade5668a2979de5e` both times).
- Handler names are imported **verbatim**. Normalisation happens at read time;
  rewriting names in a financial record is not part of this correction.

## 4. Phase 3 — isolated rehearsal

Sealed environment: a **copy** of the Operations volume, a **disposable**
PostgreSQL restored from a read-only dump with rehearsal-only credentials, on a
**separate docker network** — verified unable to reach the production database.
The app image ran with an overridden command so no background worker started.

Baseline first, to prove fidelity: **72,000 / 48,500 / 33,500 = 154,000**,
matching production exactly.

After restoring the two files and merging the ledger, through the real
`stats()` and `_carry_forward_balances()`:

| handler | opening now | **opening after** | closing now | **closing after** |
|---|---:|---:|---:|---:|
| Thrilok | 72,000 | **15,000** | 72,000 | **30,000** |
| Pavan Kalyan | 48,500 | **3,500** | 54,000 | **−1,000** |
| Venugopal | 33,500 | **3,500** | 33,500 | **3,500** |
| **total** | **154,000** | **22,000** | **159,500** | **32,500** |

Opening overstated by **₹1,32,000**. Closing falls by ₹1,27,000 — less than the
opening, because Thrilok's August salary (₹15,000) becomes visible at the same
time.

Pavan Kalyan's −₹1,000 is a genuine overpayment; the code already models it as
`carry_forward_receivable = 1,000`, with `cash_payout = 0`.

> **Decision needed.** Thrilok's ₹15,000 August salary accrues for the current,
> incomplete month, because `active_until` is null. That is existing behaviour
> and the configuration's plain meaning, but it means the correction *raises*
> his closing balance from ₹15,000 to ₹30,000. Confirm this is intended before
> paying against it.

## 5. Phase 4 — month by month, each amount exactly once

| month | handler | opening | commission | salary | paid | recovery | closing |
|---|---|---:|---:|---:|---:|---:|---:|
| Jun | Thrilok | 0 | 45,000 | 15,000 | 45,000 | 0 | 15,000 |
| | Pavan Kalyan | 0 | 41,000 | 0 | 34,000 | 0 | 7,000 |
| | Venugopal | 0 | 12,500 | 0 | 10,000 | 0 | 2,500 |
| Jul | Thrilok | 15,000 | 27,000 | 15,000 | 42,000 | 0 | 15,000 |
| | Pavan Kalyan | 7,000 | 7,500 | 0 | 1,000 | 10,000 | 3,500 |
| | Venugopal | 2,500 | 21,000 | 0 | 20,000 | 0 | 3,500 |
| Aug | Thrilok | 15,000 | 0 | 15,000 | 0 | 0 | 30,000 |
| | Pavan Kalyan | 3,500 | 5,500 | 0 | 10,000 | 0 | −1,000 |
| | Venugopal | 3,500 | 0 | 0 | 0 | 0 | 3,500 |

Verified:

1. **Carry-forward once** — every previous closing equals the next opening, for
   every handler, both transitions. 0 mismatches.
2. **Referral commission once** — one allocation per deduplicated candidate row.
3. **Salary once per period** — Jun+Jul = ₹30,000, not ₹15,000 and not ₹45,000.
4. **Payouts reduce once** — the ledger's ₹83,000 of `approved_expense` rows are
   *not* added on top of `handler_expenses`: August `handler_paid_out_total`
   is ₹10,000, exactly the one non-voided August expense row.
5. **Recovery reduces once** — ₹10,000 total, applied in both the July and
   August windows once each, under the resolved key.
6. **Complimentary not double-counted** — ₹5,000 each for Thrilok and Pavan
   Kalyan, verified as a subset of `prior_commission`, never added on top.
7. **Negative opening works** — becomes `carry_forward_receivable`, not a
   negative payout.

Cross-store double-count scan: the second recovery (`le_f48d5ab8b49848b2`) has
**no** expense twin. Two amount-and-party coincidences surfaced against June
rows dated 2026-06-03 and 2026-06-10 with unrelated notes — different
transactions that share a ₹5,000 amount, not duplicates.

> **Pre-existing open item, unchanged by this correction.** Both recovery
> entries cite the same `evidence_id` `ev_9430918548004ce8`. ₹5,000 of Pavan
> Kalyan's reduction therefore rests on the reused-proof question that was
> already open before this work.

## 6. Phase 5 — so it cannot happen silently again

**The silent zero had two layers**, and the module layer fired first: every one
of `handler_expenses._load()`, `handler_salaries._load_records()` and
`_load_ledger()` returns an *empty store* when the file is missing. The
`try/except: pass` blocks in `_carry_forward_balances` never even ran.

- Added `store_available()` / `ledger_available()` to the three modules, which
  distinguish "readable and empty" from "cannot be read".
- `_carry_forward_balances` now raises `AccountingSourceUnavailable` per source,
  logs at ERROR, and returns `unreconciled` + `unreconciled_sources`.
- `stats()` exposes `earnings_unreconciled` / `earnings_unreconciled_sources`,
  probed independently so the warning still reaches the client when there are
  no prior-month rows to attach it to.
- The Earnings Breakdown renders a red banner stating the figures were computed
  without the named sources and must not be paid against.
- **No accounting formula changed.** Every figure is identical when all sources
  are readable.

Registry gap, in `scripts/split_migrate.py`: the docstring promised an unlisted
source "surfaces as UNCLASSIFIED rather than being dropped", but `build_plan`
only ever walked the registry — nothing enumerated the directory, so an
unregistered file was invisible, not unclassified. Now the directory is swept,
orphans are reported, and `--execute`/`--reconcile` **refuse to run**. The six
lost stores are registered.

Verified through the real backend, with the patched modules loaded:

| state | `earnings_unreconciled` | sources named |
|---|---|---|
| stores missing | **True** | `handler_expenses`, `handler_salaries` |
| correction applied | **False** | — |

## 7. Phase 6 — regression tests

`teleautomation-business/tests/test_handler_carry_forward.py` — 16 tests.
`TelegramForward/tests/test_merge_payment_ledger.py` — 10.
`TelegramForward/tests/test_split_store_registry.py` — 6.

Covering: carry once · referral once · salary once per period, honouring
`active_until` · payout reduces once · **voided payout does not** · recovery
reduces once · complimentary inside commission · negative opening becomes a
receivable · each of the three stores missing ⇒ `unreconciled` · all present ⇒
reconciled · **empty ≠ missing** · merge idempotent · merge refuses a non-unique
identity key · three-month chain.

One test documents a real fragility: the ₹10,000 recovery attaches to Pavan
Kalyan **only because a referrer-registry alias** maps `LUKKA PAVAN KALYAN` to
`pavan kalyan`. Without it the money lands on a handler with no earnings and
reduces nothing.

Results: 16/16, 10/10, 6/6. Full suites: Operations **1074 passed**, tooling
**1852 passed**, dashboard builds clean.

> Two pre-existing failures in `tests/test_ocr_policy.py` are unrelated to this
> work — confirmed by stashing every change and re-running: they fail
> identically on committed `main` (`ad5e0e6`), the deployed release.

## 8. Latent issue found, deliberately not changed

`prior_paid` keys on `reference.lower()`, while `prior_commission` and
`prior_recoveries` key on `_reference_key()`, which also applies aliases. A
payout recorded under an alias spelling would attach to a different bucket and
silently fail to reduce the balance.

Every spelling in the live data (`Thrilok`, `Pavan Kalyan`, `PAVAN KALYAN`,
`Venugopal`, `Ravinder`) normalises identically under both, so **this changes no
figure today**. Changing it is an accounting-behaviour change and is left for a
separate decision rather than folded into this correction.

## 9. The other four unmigrated stores — audit only, not restored

| store | monolith | in Operations | retained feature affected |
|---|---|---|---|
| `company_expenses.json` | 4 rows | absent | **yes** — `/expenses/company` returns 0 rows |
| `operator_tasks.json` | 3 tasks | absent | **yes** — task queue returns 0 |
| `historical_booking_records.json` | 1 record | absent | module loads; no route observed |
| `bgv_register.json` | 1 case | absent | **no code reference** in Operations |

**None is an input to `_carry_forward_balances`, so none affects any handler
balance.** Reported for a separate decision; not restored or modified here.

## 10. Production correction — the steps, for approval

Nothing below has been run.

1. Fresh full backup of the Operations data volume **and** database.
2. Back up the current `payment_verification_ledger.json` separately, by SHA.
3. Copy `handler_expenses.json` and `handler_salaries.json` into
   `/var/lib/teleautomation-operations/`, matching the existing files' owner
   and mode.
4. `merge_payment_ledger.py --source … --target … --report …` **dry run first**;
   confirm 88 imported / 0 collisions; then `--apply --backup-dir …`.
5. Verify SHA-256, byte size, owner and mode of all three files.
6. **A restart should not be needed**: none of the three loaders caches, so each
   is read per request, and the release is unchanged. This rests on reading the
   loaders, not on an observed long-running process — so if step 7 still shows
   the old figures, restart `operations-api` and re-check before concluding the
   copy failed. (The Phase 5 code fix is a *separate* PR-and-deploy, not part of
   this data correction.)
7. Load Earnings Breakdown for August 2026; expect opening **₹22,000**, closing
   **₹32,500**.
8. Compare every handler before/after against the table in §4.
9. Confirm no unrelated financial record changed: candidate count still 198,
   the 5 post-cutover ledger rows still present and first.
10. Re-run the merge once to confirm it reports 0 imported (idempotency holds in
    production, not just rehearsal).
11. Check all six Operations features healthy; both sites 200.

**Rollback.** Delete the two copied files and restore
`payment_verification_ledger.json` from the step-2 backup by SHA. Balances
return to today's values exactly, because the opening balance is derived and
never stored. No database change is involved, so no database rollback is needed.

---

## Verification summary

- **Changed in production: nothing.** Ledger still `602fc7077f32b2f0`, 22,066 B;
  both stores still absent; operations 200, marketing 200.
- **Tested**: 32 new tests, both full suites, dashboard build, and the real
  backend in a sealed copy of production data.
- **Not tested**: the production correction itself, which needs approval; and
  the Phase 5 code fix under real HTTP traffic (it was exercised by direct
  backend calls with the patched modules mounted, not through a deployed build).

---

## 11. Execution record — 2026-08-17

Run in the approved order: code first, so the fail-visible behaviour was proven
on the live service *before* the data that would hide it was restored.

### Backups (all verified before anything changed)

`/opt/teleautomation-backups/pre-openingbalance-20260817T171800Z/`

| artefact | bytes | verification |
|---|---:|---|
| `operations_prod.dump` | 117,838,634 | `pg_restore --list` readable |
| `operations_data_volume.tar.gz` | 47,046,700 | `gzip -t` OK, 595 members |
| `payment_verification_ledger.json.pre-correction` | 22,066 | sha `602fc707…` matched live |
| `env.production.pre-correction` | — | mode 600 preserved |

`ABSENT_BEFORE_CORRECTION.txt` records that both handler stores were absent, so
the pre-state is unambiguous. `SHA256SUMS` covers the directory.

### Release

`ad5e0e6` → **`e74b8a0`** (PR #11, CI green). The previous image was tagged
`rollback-ad5e0e61…` *before* the build, and the previous source tree kept at
`/opt/teleautomation-business.prev-20260817T172032Z`. Marketing stayed on
`2f6fe88` and was never rebuilt.

Two things worth recording. The staged source tree differed from the live one by
exactly one file each way — host-only `RELEASE_SHA` and the new test — so the
deployed tree was provably the merged commit. And `RELEASE_SHA_OPERATIONS` in
`.env.production` was **stale** (`0207819…`) while the running image had been
built with `ad5e0e6`: past builds passed the value inline instead of through the
file. Writing it into the file fixed that drift as a side effect.

### Fail-visible behaviour, proven on production

With the new code live and the stores still missing:

```
unavailable_accounting_sources : ['handler_expenses', 'handler_salaries']
stats.earnings_unreconciled    : True
```

The old ₹1,54,000 / ₹1,59,500 were still computed — but no longer presented as
settled. After the restore the flag cleared to `False` with an empty source list.

### Data restored

| file | bytes | mode | sha256 (destination == authoritative source) |
|---|---:|---|---|
| `handler_expenses.json` | 14,277 | 644 | `4b7806a9782d44cf8aa64e328453d30c…` ✔ |
| `handler_salaries.json` | 330 | 644 | `125421c5f7e109af3c6a7335165705c4…` ✔ |
| `payment_verification_ledger.json` | 315,332 | 644 | `4a3923243bad2ef1ade5668a2979de5e…` |

### Ledger merge

Dry run first, and it reproduced the rehearsal byte for byte — same before hash
`e1eecb3f…`, same after hash `4a392324…`.

| collection | before | imported | collided | after |
|---|---:|---:|---:|---:|
| entries | 0 | 16 | 0 | 16 |
| payments | 2 | 28 | 0 | 30 |
| evidence | 3 | 33 | 0 | 36 |
| entitlements | 0 | 11 | 0 | 11 |

**88 imported, 0 collisions.** The second run imported **0** and left the file
byte-identical — idempotency demonstrated in production, not just rehearsal.
All 5 post-cutover Operations rows survived and remain first in file order.

### Result

| month | | opening before | opening after | closing before | closing after |
|---|---|---:|---:|---:|---:|
| Jun | total | 0 | 0 | 98,500 | **24,500** |
| Jul | total | 98,500 | **24,500** | 154,000 | **22,000** |
| Aug | Thrilok | 72,000 | **15,000** | 72,000 | **30,000** |
| | Pavan Kalyan | 48,500 | **3,500** | 54,000 | **−1,000** |
| | Venugopal | 33,500 | **3,500** | 33,500 | **3,500** |
| | **total** | **154,000** | **22,000** | **159,500** | **32,500** |

Confirmed over authenticated HTTP, not only in-process: `/candidates/stats`
returns opening 22,000, closing 32,500, `earnings_unreconciled: false`.

Every carry-forward tie holds (Jun→Jul→Aug, 0 mismatches), the ₹5,000 Pavan
payout remains `RECLASSIFIED_TO_RECOVERY` and excluded, the ₹10,000 recovery
applies once in July's own column and once into August's opening, and the
ledger's ₹83,000 of `approved_expense` rows are still not counted as payouts.
`LUKKA PAVAN KALYAN` resolves to `pavan kalyan`.

### Two observations, neither caused by this change

- **`candidates_store` moved 198 → 199.** A candidate was logged by an operator
  at 18:56Z, after the backup. Nothing here writes to the database. It is dated
  2026-08-18 and references Ravinder, who is payout-excluded, so it is immaterial
  to handler balances — the figures re-verified identically afterwards.
- **Ollama node `jagadeesh` is offline**, its reverse tunnel absent from
  `127.0.0.1:11435`. The container recreate did *not* break the firewall guard:
  `ops-ollama-watch` re-applied it automatically and the other two nodes reach
  Ollama through the same path. The tunnel is a remote-laptop condition.
