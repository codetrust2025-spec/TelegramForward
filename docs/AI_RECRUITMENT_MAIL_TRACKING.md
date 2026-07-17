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
## Mail monitoring notifications and real-time delivery (v4)

The mailbox scheduler remains the Gmail ingestion mechanism. It polls only due
connected mailboxes, uses Gmail `historyId`/History API pagination for incremental
changes, and falls back to a bounded 30-day scan only when Gmail expires a cursor.
WebSocket is used only for backend-to-dashboard delivery after data is committed.

- Notification API: `GET /api/mail-monitoring/notifications`
- Unread/dashboard summary: `GET /api/mail-monitoring/summary`
- Missed-event replay: `GET /api/mail-monitoring/events?after_event_id=...`
- Review actions: `POST /api/mail-monitoring/notifications/{id}/{action}`
- Authenticated WebSocket: `/ws/mail-monitoring`
- Additive migration: `core/migrations/007_recruitment_mail_notifications.sql`

The WebSocket sends metadata only and never sends a complete email body. The UI
uses exponential reconnect, heartbeat, event-ID deduplication, local last-event
tracking, BroadcastChannel coordination, and a 30-second API fallback.

Required production settings are documented in `.env.example`. The canonical
mail model variable is `OLLAMA_MAIL_MODEL`; `AI_RECRUITMENT_MODEL` remains a
backward-compatible fallback. Enable the feature only after PostgreSQL migration,
Google OAuth, credential encryption, and Ollama health checks pass.

## Gmail push and automatic interview booking (v5)

Gmail push is an accelerator over the durable scheduler. Configure a Google
Cloud Pub/Sub topic that grants Gmail publish permission and a push subscription
to `GMAIL_PUSH_WEBHOOK_URL?token=<GMAIL_PUBSUB_VERIFICATION_TOKEN>`. The webhook
stores/deduplicates the Pub/Sub message ID and queues the existing History API
worker; it never fetches or analyzes email inline. Gmail watches are registered
when monitoring is enabled and renewed within 24 hours of expiry. Scheduled
incremental sync remains the outage fallback.

Validated Ollama outcomes now support `interview_confirmed`,
`interview_rescheduled`, and `interview_cancelled`. Only an `OLLAMA` result with
`VALIDATED` schema status can mutate a slot. Confirmed/rescheduled interviews
require an explicit ISO date, 12-hour AM/PM time, valid IANA timezone, candidate
mailbox match, configured confidence, existing payment/ownership rules, Gmail
and booking deduplication, and the existing overlap check. Non-IST schedules are
converted to the existing Asia/Kolkata roster calendar. Payment amounts and
proof states are never changed.

The additive `008_recruitment_mail_auto_booking.sql` migration stores Pub/Sub
deliveries, interview analyses, booking audit/history, and booking metadata on
notifications. Candidate slot rows remain in the existing candidate store.
Administrators can inspect audit history at
`GET /api/mail-monitoring/booking-audit`. The dashboard responds to
`slot_auto_booked`, `interview_rescheduled`, and `interview_cancelled` events by
refreshing the live roster; API polling and missed-event replay remain active.

For staged activation, deploy with `AI_INTERVIEW_AUTO_BOOKING_ENABLED=false`,
apply all migrations, verify Pub/Sub delivery and Ollama extraction with a test
mailbox, then set the flag to `true` and restart the API/worker processes. A
rollback sets that flag and `AI_MAILBOX_SYNC_ENABLED` to `false`; existing
bookings and audit rows are retained and the additive migration need not be
reversed.
