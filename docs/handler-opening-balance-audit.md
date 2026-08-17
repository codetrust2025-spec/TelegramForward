# Handler opening-balance audit — AUG 2026

Date: 2026-08-17
Scope: read-only. No production data, code, config or deployment was changed.
Result: **root cause proven — missing payout/salary/recovery stores, not duplication**

---

## 1. The formula, exactly as it runs

`features/candidate_store.py`

```python
# _carry_forward_balances(target_month)   — line ~5889
prior_balance = (prior_commission + prior_salary) - prior_paid - prior_recoveries

# stats() assembly                        — line 6323
net_payable   = (owed - recoveries - paid_out) + prior_balance
cash_payout   = max(0, net_payable)
carry_forward_receivable = max(0, -net_payable)
```

`dashboard/src/candidates/EarningsBreakdown.jsx`

```js
grossPayable = priorBalance + totalEarned      // line 272
net         += Number(p.net_payable) || 0      // line 124 — sums per-handler closings
```

The frontend performs no accounting of its own. It renders `prior_balance` and
`net_payable` as received.

**The opening balance is not stored and not migrated. It is recomputed from
transactions on every request**, over all months strictly before the target,
excluding 2026-04 and 2026-05 which are hard-coded as settled.

## 2. Source of each term

| term | source | present in Operations? |
|---|---|---|
| `prior_commission` | `candidates_store` (PostgreSQL) via `handler_earning_allocations()` | **yes** |
| `prior_salary` | `features/handler_salaries.py` → `/var/lib/teleautomation-operations/handler_salaries.json` | **NO — file absent** |
| `prior_paid` | `features/handler_expenses.py` → `/var/lib/teleautomation-operations/handler_expenses.json` | **NO — file absent** |
| `prior_recoveries` | `payment_verification_engine.ledger_entries(action="referrer_recovery")` | **NO — returns 0 rows** |

Each of the four is wrapped in its own `try/except: pass`. A missing source
therefore contributes zero silently, and the run reports success.

With three of the four terms at zero the formula degenerates to:

```
prior_balance = prior_commission
```

That is precisely what production is showing.

## 3. Verified live

```
handler          priorComm   priorSal  priorPaid  priorRecov   = opening
thrilok             72,000          0          0           0      72,000
pavan kalyan        48,500          0          0           0      48,500
venugopal           33,500          0          0           0      33,500
TOTAL              154,000          0          0           0     154,000
```

154,000 opening + 5,500 current earnings = **159,500**, matching the page total
exactly. The fourth handler shown in the summary carries no balance.

## 4. What the missing stores contain

Read read-only from the monolith at `/opt/telegramforward/data`.

**`handler_expenses.json`** — 14,277 bytes, 25 rows, ₹293,000 total.
₹10,000 falls in/after Aug and ₹126,000 in the settled Apr/May window, leaving
**₹157,000 that should reduce the August opening balance**:

| handler | payouts in scope | months |
|---|---|---|
| thrilok | ₹87,000 | Jun ₹45,000 · Jul ₹42,000 |
| pavan kalyan | ₹40,000 | Jun ₹34,000 · Jul ₹6,000 |
| venugopal | ₹30,000 | Jun ₹10,000 · Jul ₹20,000 |

**`handler_salaries.json`** — 330 bytes. Thrilok, ₹15,000/month, active from
2026-05, no end date → **₹30,000 owed for Jun + Jul**, currently counted as zero.

**`payment_verification_ledger.json`** — monolith holds 16 entries including 2
`referrer_recovery` rows totalling **₹10,000** against `Lukka Pavan Kalyan`.
Operations' own ledger returns **0** recovery rows. `_reference_key()` maps both
`Pavan Kalyan` and `Lukka Pavan Kalyan` to `pavan kalyan`, so this recovery does
attach to him.

## 5. Corrected ledger

| handler | shown opening | + salary | − payouts | − recovery | **true opening** | delta |
|---|---:|---:|---:|---:|---:|---:|
| thrilok | 72,000 | 30,000 | 87,000 | 0 | **15,000** | −57,000 |
| pavan kalyan | 48,500 | 0 | 40,000 | 10,000 | **−1,500** | −50,000 |
| venugopal | 33,500 | 0 | 30,000 | 0 | **3,500** | −30,000 |
| **TOTAL** | **154,000** | 30,000 | 157,000 | 10,000 | **17,000** | **−137,000** |

Closing balance:

| | |
|---|---|
| shown today | ₹1,59,500 |
| corrected (17,000 + 5,500 current) | **₹22,500** |
| **overstatement** | **₹1,37,000** |

Pavan Kalyan's −₹1,500 means the company has **overpaid** him by ₹1,500. The
code already models this: `carry_forward_receivable = max(0, -net_payable)`.

## 6. Answers to the specific questions

1. **Thrilok's ₹72,000** is his summed commission allocations across Jun+Jul 2026
   candidate rows — with ₹87,000 of real payouts invisible and ₹30,000 of owed
   salary also invisible. True figure: **₹15,000**.
2. Composed of `prior_commission` only, including ₹5,000 profile-closure
   complimentary counted **once** (it is a subset of commission, not an addition).
3. **Pavan Kalyan's ₹48,500** is likewise commission alone. True: **−₹1,500**.
4. Includes ₹5,000 complimentary, counted once.
5. **No — these figures did not exist pre-split.** The monolith held all three
   stores, so it computed the payouts and salary correctly.
6. **The discrepancy appeared at the cutover**, when the stores failed to migrate.
7. **No.** Nothing is counted more than once.
8. **No.** There is no opening-balance snapshot anywhere in the service, so a
   snapshot plus a transaction replay is structurally impossible.
9. **Yes — payout records are missing**: `handler_expenses.json` and
   `handler_salaries.json` are absent, and the recovery ledger returns nothing.
10. **Neither** was migrated. The migration copied the commission-bearing
    candidate rows and nothing that offsets them.

**AUG opening does equal JUL closing exactly once.** The carry-forward arithmetic
is self-consistent. Both figures are built from the same incomplete inputs, so
they agree with each other and are wrong together. The defect is the inputs, not
the carry-forward.

## 7. Root cause

**Classification: D — missing payout/history records**, caused by an omission in
the split migration's ownership registry. Not A, B, E, F or G.

`JSON_STORES` in `scripts/split_migrate.py` (monolith repo) never listed
`handler_expenses.json`, `handler_salaries.json`, `company_expenses.json`,
`historical_booking_records.json`, `bgv_register.json` or `operator_tasks.json`.
The registry's own docstring promises that an unlisted source "surfaces as
UNCLASSIFIED rather than being dropped" — that guarantee did not hold for
top-level JSON stores, which were simply never enumerated.

The four `try/except: pass` blocks then converted a missing file into a silent
zero rather than an error. Either alone would have been survivable; together they
turned a migration omission into wrong money on screen.

## 8. Proposed correction — for approval, not executed

**No production data needs editing.** The opening balance is derived, so
restoring the source files corrects every figure automatically.

**Step 1 — restore three stores into the Operations data volume** (copy from the
monolith, which is intact and read-only in this audit):

| file | bytes | destination |
|---|---|---|
| `handler_expenses.json` | 14,277 | `/var/lib/teleautomation-operations/` |
| `handler_salaries.json` | 330 | `/var/lib/teleautomation-operations/` |
| `payment_verification_ledger.json` | 293,421 | merge, do not overwrite — Operations' own 22,066-byte file has post-cutover entries |

The ledger needs a merge rather than a copy, and that merge should be reviewed
before it runs.

**Step 2 — code fix so this cannot recur silently.** Replace the four bare
`except: pass` blocks in `_carry_forward_balances` with a fail-loud path: if a
store the formula depends on is absent, the API should mark the figure
`unreconciled` rather than return a confident wrong number.

**Step 3 — close the registry gap** in `scripts/split_migrate.py` so an
unenumerated top-level JSON store is reported as UNCLASSIFIED, as documented.

Expected result after step 1, with no data edited:

| handler | opening now | opening after | closing now | closing after |
|---|---:|---:|---:|---:|
| thrilok | 72,000 | 15,000 | 72,000 | 15,000 |
| pavan kalyan | 48,500 | −1,500 | 54,000 | 4,000 |
| venugopal | 33,500 | 3,500 | 33,500 | 3,500 |
| **total** | **154,000** | **17,000** | **1,59,500** | **22,500** |

## 9. Regression tests required

1. Previous unpaid balance carries forward exactly once.
2. Current-month earnings added exactly once.
3. A payout reduces the balance exactly once.
4. A fully-paid previous month opens the next month at zero.
5. Salary accrues once per active month, respecting `active_from`/`active_until`.
6. Profile-closure complimentary is counted as a subset of commission, never added.
7. `opening + earned − paid ± adjustments = closing` holds for every handler.
8. **A missing payout store makes the API report `unreconciled`, not a confident
   balance** — the test that would have caught this.
9. Fixture parity: the split produces the same balances as the pre-split monolith
   for Jun/Jul 2026.

## 10. Rollback

Step 1 adds files that do not currently exist; rollback is deleting them, and the
balances return to today's values. Step 2 and 3 are code changes behind the
normal PR and release path, with the existing rollback image tags available.
Back up the Operations data volume before step 1 regardless.
