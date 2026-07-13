# AI Interview, Offer and Candidate Mail Tracking

This feature monitors explicitly authorized Gmail mailboxes using only the
read-only `gmail.readonly` OAuth scope. It never sends, deletes, labels,
archives, or marks mail as read. All feature flags are disabled by default.

## Activation

1. Create a Google OAuth web client and configure its exact callback URL.
2. Generate a Fernet key outside the repository:
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
3. Configure the variables documented in `.env.example`.
4. Apply `core/migrations/001_recruitment_mail_tracking.sql` to PostgreSQL. The
   application also applies this idempotent migration during startup.
5. Enable `AI_INTERVIEW_OFFER_TRACKING_ENABLED` first while leaving mailbox sync
   disabled. Connect and verify a dedicated test mailbox, then enable sync.

OAuth refresh tokens are encrypted before storage and never returned by APIs.
Bulk import creates pending records only; every mailbox owner must grant OAuth
access. AI statuses never overwrite an administrator-confirmed status.

## Delivered capabilities

- Per-candidate Gmail onboarding, connection verification, monitoring controls,
  manual sync, disconnect, and secure pending bulk import.
- Cheap pre-filtering before AI, cleaned email content, strict JSON Schema
  extraction, ISO date/time enforcement, confidence thresholds, bounded JSON
  repair, model fallback, and a manual-review fallback.
- Interview, assessment, status, offer, joining, rejection, and document-event
  detection with supporting evidence and risk flags.
- PDF, DOCX, TXT, and image extraction with SHA-256 caching. Scans use OCR and
  the configured Ollama vision model as fallback. Legacy DOC files use
  `antiword` or LibreOffice when either converter is installed.
- Durable PostgreSQL jobs, incremental Gmail history cursors, expired-cursor
  recovery, retry/dead-letter handling, idempotent records, and mailbox failure
  isolation.
- Admin metrics and charts, review queue, evidence viewer, editable extracted
  fields, duplicate/false-positive decisions, candidate timeline, offer review,
  conflict flags, audit logging, and Web Push alerts.
- Candidate-list AI filters and direct navigation to each candidate mailbox.

## Data and security boundaries

The additive migration creates mailbox, message metadata, attachment cache,
event, status-history, offer-case, risk-flag, queue, and audit tables. Full email
bodies are not stored. Evidence and extracted attachment text are returned only
by administrator-protected endpoints. OAuth state is signed and short-lived.
Disconnect removes the encrypted credential and cursor. The provider interface
is vendor-neutral; only Gmail is implemented today.

## Worker behavior

The scheduler creates durable `mailbox_sync_jobs`. PostgreSQL row locking with
`SKIP LOCKED` prevents duplicate claims. Gmail history IDs provide incremental
sync. Provider message IDs and event constraints make processing idempotent.
Temporary failures use bounded exponential rescheduling while other mailboxes
continue.

## Verification

Run the complete non-interactive verification from the repository root:

```powershell
python scripts/test_ai_recruitment_feature.py
```

This performs the credential scan, backend suite, evaluation fixtures, migration
structure checks, Python compilation/import, frontend formatting, tests, lint,
type-check, production build, and production dependency audit. It does not need
mailbox credentials and never prompts for input.

The equivalent individual commands are:

```powershell
python -m pytest -q
python -m compileall core services workers tests
cd dashboard
npm test -- --run
npm run lint:recruitment
npm run build
```

Before production activation, apply the migration to staging PostgreSQL,
complete Gmail OAuth with a dedicated test mailbox, verify initial and
incremental sync, reset the history cursor to verify recovery, upload every
supported attachment type, exercise all review actions, and confirm disconnect
prevents subsequent syncs.

## Known deployment limitations

- Google OAuth credentials and consent-screen approval must be supplied by the
  deployment owner.
- Legacy DOC extraction requires `antiword` or LibreOffice; without either, the
  document is routed to manual review.
- Existing legacy Ollama extractors still call Ollama directly; this feature
  uses the central gateway.
- A 3.8 GB VPS is insufficient for the configured Qwen 7B models.
- Live migration and OAuth consent cannot be validated without staging database
  and Google credentials.
- The dashboard currently depends on `xlsx@0.18.5`; npm reports high-severity
  issues and no patched version on that package line. Replace it before
  accepting untrusted spreadsheet uploads.
