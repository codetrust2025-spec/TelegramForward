# Payment Verification and Settlement Engine V2

## Repository findings

Payment screenshots currently enter through three compatible API families:

1. Public slot booking:
   - `POST /public/slots/extract-payment-ai`
   - `POST /public/slots/payment-proof`
2. Candidate records:
   - `POST /candidates/{candidate_id}/proofs`
3. Handler payouts and reimbursements:
   - `POST /handler-expenses`
   - `POST /handler-expenses/{expense_id}/proofs`

Legacy company-only validation was located in
`features/company_payment_verification.py` and the public booking hint in
`dashboard/src/pages/SubmitSlotPage.jsx`. The legacy Python function is now a
backward-compatible registry-backed facade; the UI no longer states that every
referrer payment is rejected.

The current Ollama path is:

`API upload -> features/payment_verification_engine.py ->
features/ollama_payment_extract.py -> core/ai_gateway.py ->
configured primary/backup Ollama node`.

Booking eligibility is rechecked in `features/candidate_store.py` against the
posted central ledger entry before a slot is imported. Handler month-end
recoveries are read from the same ledger by `features/candidate_store.py`.

Candidate and handler data remain in their existing JSON-backed stores. The
central engine audit store defaults to
`data/payment_verification_ledger.json`.

The repository does not contain a separate historical referrer table. Its
existing source of truth is the canonicalized `candidate.reference` data
exposed by `candidate_store.reference_dropdown_names()`. The compatibility
registry in `features/referrer_registry.py` materializes stable IDs and aliases
for those records without replacing the legacy field or creating a second
second referrer record. The resolved names come from your existing candidate
reference data (shown here as generic placeholders, not real people).

## Current flow

```text
Screenshot upload
  -> PaymentVerificationEngine
  -> Ollama Vision extraction (facts only)
  -> normalized receiver identifiers
  -> deterministic receiver registry match
  -> duplicate/reference/hash checks
  -> verification state
  -> immutable financial allocation
  -> entitlement (candidate payments)
  -> existing proof/booking/payout flow
```

OCR code remains installed but inactive. `PAYMENT_EXTRACTION_PROVIDER=OLLAMA`
and `OCR_ENABLED=false` prevent OCR from taking part in decisions.

## Receiver decisions

- Company identifier match: `VERIFIED_COMPANY_PAYMENT`
- Registered referrer identifier match: `VERIFIED_REFERRER_PAYMENT`
- No registry match: `UNKNOWN_RECEIVER`
- Name-only, ambiguous, low-confidence, or missing UTR:
  `PENDING_MANUAL_REVIEW`
- Reused payment for a different source entity: `DUPLICATE_PAYMENT`

Names are secondary evidence only. Automatic authorization requires a unique
configured UPI, phone, or account identifier.

## Receiver account registry

The resolved registry is centralized in
`features/payment_verification_engine.py`. It merges:

- verified company account configuration;
- `PAYMENT_RECEIVER_REGISTRY_FILE` (default
  `data/payment_receiver_accounts.json`);
- the backwards-compatible trusted
  `PAYMENT_REFERRER_RECEIVERS_JSON` administrator setting;
- discovered historical candidate reference names as **UNVERIFIED**,
  name-only review records.

Registry accounts carry owner type/IDs, account-holder name, stable payment
identifiers, verification status, active/validity dates, provider and audit
metadata. Exact normalized UPI, exact phone, or exact account matching is
required. Partial/suffix account matching is not used. Active duplicate
ownership is returned by `receiver_registry_conflicts()` and blocks automatic
authorization.

Example verified referrer row (placeholder data):

```json
{
  "id": "referrer-sample",
  "owner_type": "REFERRER",
  "referrer_id": "referrer-sample",
  "account_holder_name": "SAMPLE REFERRER",
  "upi_id": "referrer@upi",
  "verification_status": "VERIFIED",
  "is_active": true,
  "verified_by": "admin"
}
```

The account-holder aliases (e.g. `Sample Referrer`) resolve to the one existing
referrer compatibility ID. Exact normalized `referrer@upi` matching is
authoritative; the payment amount is not part of receiver classification.

Fresh installations bootstrap the confirmed mapping from the tracked
`config/referrers.seed.json` and
`config/payment_receiver_accounts.seed.json` files. Runtime administrator
changes are written to the configured `data/` registry and then take
precedence over bootstrap data.

## Referrer administration

Fleet administrators can manage accounts through:

- `GET /referrers`
- `GET /referrers/{referrer_id}/payment-accounts`
- `POST /referrers/{referrer_id}/payment-accounts`
- `PATCH /referrer-payment-accounts/{account_id}`
- `DELETE /referrer-payment-accounts/{account_id}`

The payout modal presents this as **Payment Accounts**, masks identifiers,
shows verification/activity/history, and supports add, verify, reject,
activate/deactivate, and removal of unused unverified accounts. These routes
are administrator-only. Verified/rejected or financially linked accounts must
be deactivated and retained, not deleted.

Existing `/handler-expenses` routes and `candidate.reference` fields are
unchanged for API and data compatibility. User-facing selectors say
**All Referrers**.

## Direct-to-referrer allocation

For a candidate payment of ₹5,000 with a 50% commission rule:

- Gross commission earned: ₹2,500
- Commission already received directly: ₹2,500
- Company share recoverable: ₹2,500
- Total month-end payout adjustment: ₹5,000

The full receipt is not stored as a generic expense. All financial calculations
also retain paise-valued `*_minor` fields and avoid binary floating point.

## Payment scopes and entitlements

- `PROFILE`: reusable candidate entitlement
- `ROUND`: single-use round entitlement
- `SLOT`: single-use slot entitlement
- `OTHER`: explicit non-booking scope

Historical profile payments are not copied into future rounds. New modules can
reference the original `payment_id` and `entitlement_id`.

## Existing API compatibility

No endpoint was removed or renamed. Existing responses retain fields such as
`company_payment_verified`, `ledger_action`, and `ledger_status`. V2 adds:

- `verification_state`
- `reason_codes`
- `booking_eligible`
- `payment_id`
- `evidence_id`
- `ledger_entry_id`
- `entitlement_id`
- `payment_scope`

Registered-referrer payments now unlock booking only after verification and
ledger posting. Unknown or pending payments remain blocked.

## Configuration

```dotenv
PAYMENT_ENGINE_V2_ENABLED=true
PAYMENT_EXTRACTION_PROVIDER=OLLAMA
OCR_ENABLED=false
PAYMENT_VERIFICATION_OCR_ENABLED=false
REFERRER_RECEIVER_FLOW_ENABLED=true
PAYMENT_MIN_EXTRACTION_CONFIDENCE=80
PAYMENT_DEFAULT_COMMISSION_PCT=50
PAYMENT_COMMISSION_RULES_JSON=
PAYMENT_REFERRER_RECEIVERS_JSON=
PAYMENT_RECEIVER_REGISTRY_FILE=
REFERRER_REGISTRY_FILE=
PAYMENT_EVIDENCE_MAX_BYTES=10485760
```

Each trusted referrer registry record must contain a stable identifier:

```json
[
  {
    "id": "referrer-pawan",
    "name": "Referrer One",
    "upi_ids": ["pawan@bank"],
    "phones": ["9999999999"],
    "accounts": ["1234"],
    "active": true
  }
]
```

## Migration

PostgreSQL deployments should first apply
`core/migrations/017_payment_engine_v2.sql`. It creates receiver accounts,
evidence, verification, ledger and entitlement tables with one-owner checks,
active-identifier uniqueness, duplicate transaction/UTR protection and
idempotency constraints. The current JSON compatibility path remains active
until the database repository adapter is enabled.

Preview only:

```powershell
python scripts/migrate_payment_engine_v2.py
```

Apply during a maintenance window:

```powershell
python scripts/migrate_payment_engine_v2.py --apply
```

Apply mode creates `payment_verification_ledger.json.pre-v2` before changing
the ledger. It also writes/backups the centralized registry file, normalizes
identifiers, lists duplicate ownership conflicts, and keeps historical
name-only referrers UNVERIFIED. Historical unknown rows are marked disputed;
the migration never guesses a receiver.

The dry run also reports `referrer_count`, `referrer_registry_path`, and the
resolved `pavan_referrer_id`. Apply mode materializes all current legacy
reference names with stable IDs before writing receiver-account records.

Before applying, review the dry-run counts and resolve `registry_conflicts`.
After applying, an administrator must verify each referrer account through the
existing trusted business process; do not bulk-promote discovered names.

## Known limitations

- A screenshot is evidence, not bank-settlement confirmation.
- Referrer auto-approval requires administrators to populate the receiver
  registry with stable identifiers.
- The repository currently uses JSON atomic replacement rather than a
  transactional SQL database. The central write is atomic within one process,
  but multi-host financial scale should migrate these entities to database
  tables with unique constraints and row transactions.
- The public extraction and proof-save endpoints remain separate for API
  compatibility. Idempotency prevents duplicate financial posting, but a
  future SQL migration should wrap proof storage, ledger posting and booking
  creation in one database transaction/outbox workflow.
