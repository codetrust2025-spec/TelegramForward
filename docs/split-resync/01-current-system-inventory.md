# Current-main system inventory

Source: `main` at `68a28ecf2301c537eb8ee96f7d30649bd832c2f1`.

This inventory records the current monolith behavior that the final split must
preserve. Runtime data and secret values were not read.

## Runtime composition

`server.py` creates one FastAPI application, installs both Marketing and
Operations routes, starts both Telegram/account workers and the recruitment-mail
worker, serves one React/Vite dashboard, and exposes the shared `/ws` plus the
Operations `/ws/mail-monitoring` socket.

The current route surface contains approximately 298 statically registered HTTP
and WebSocket decorators. Route installation is split between `server.py`, the
`api/routers` package, and installer functions under `core`.

## Marketing / Messaging behavior

- Telegram account provisioning, login, logout, lifecycle, session handling,
  health, restart, and per-account worker isolation.
- Account groups, joined-group scans, assignments, invalid-group tracking, group
  health, joining, campaign posting, forwarding, scheduling, rate coordination,
  retries, and execution policy.
- Direct-message inbox, media, export, read state, message actions, CRM lead state,
  follow-ups, spam controls, call scheduling, and contact links.
- AI smart replies, qualification, lead graph, marketing knowledge behavior,
  economy presets, and manual approval.
- Telegram/voice calls, WhatsApp webhooks and sending, Web Push, communication
  notification sounds, and Android account/inbox functionality.

Primary route families include `/account`, `/accounts`, `/groups`, `/fleet`,
`/inbox`, `/crm`, `/ai/smart-reply`, `/whatsapp`, `/voice`, `/call`, `/push`,
`/state`, `/stats`, `/metrics`, and `/ws`.

## Operations / Business behavior

- Candidate lifecycle, identity resolution, candidate attachments, resumes,
  profile photos, proof history/archive/replace, pending works, roster and exports.
- Public slots, booking confirmation, invite/resume/payment extraction, payment
  proof verification, booking conflict handling, attendance, attendee assignment,
  reminders, calendar identity, and interview reconciliation.
- Recruitment Gmail OAuth, Pub/Sub ingestion, durable ingestion and AI queues,
  mailbox synchronization, recruitment classification, review, offer verification,
  notifications, outcome audit, AI audit, cleanup, approvals, and WebSocket events.
- Payment receiver registry, evidence, verification, allocation, transaction
  identity, duplicate protection, ledger, entitlements, reconciliation, receipts,
  and recalculation audit.
- Handler and company expenses, salaries, referrer payment accounts, BGV, Data
  Room, operator tasks, daily operations, daily briefing, OCR policy, staff
  directory, and operational reporting.

Primary route families include `/candidates`, `/public/slots`, `/bookings`,
`/api/candidate-mailboxes`, `/api/ai-recruitment`, `/api/mail-monitoring`,
`/api/mail-outcome-audit`, `/api/mail-audit-ai`, `/payments`, `/handler-expenses`,
`/handler-salaries`, `/data-room`, `/bgv`, `/ai/ocr-policy`, and
`/ws/mail-monitoring`.

## Background execution

- Per-account Telegram workers, queue processors, persisted worker resume,
  watchdogs, health monitoring, account shutdown monitoring, joined-membership
  scheduling, inbox listeners, periodic inbox sync, and statistics reset.
- Recruitment-mail durable mailbox jobs, Gmail ingestion, AI leases/retries,
  watch renewal, AI recovery, outcome audit, AI audit, and dead-letter behavior.
- Daily briefing scheduler and interview reminder loop.
- Async notification, call, media, and AI-summary tasks.

Neither final service may start the other service's worker family.

## Authentication and authorization

The current dashboard uses signed `ta_session` cookies and the admin/handler
operator profile. The API middleware protects registered API roots while allowing
explicit public routes and selected operations-token calls.

Current behavior deliberately gives authenticated handlers broad dashboard/API
access in several helpers, while payout data is separately reference-scoped.
This is current production behavior and must not be silently strengthened or
weakened during the split. Each extracted service needs its own registered roots,
cookie name/domain policy, public-route allowlist, service authentication, and
authorization regression tests.

## Persistence inventory

### PostgreSQL

- One optional `DATABASE_URL`/`POSTGRES_URL` currently serves both domains.
- `candidates_store` holds candidate JSON payload rows.
- `ai_smart_reply_store` holds Marketing AI configuration/state.
- Twenty-five tracked Operations migrations create recruitment mail, Gmail queue,
  audit, interview and payment tables.
- `candidates_store` is a production schema assumption but is not created by the
  tracked migration chain. Migration 010 reads it, so the current/old Business
  fresh-database chain is incomplete.

### Marketing file/session state

- Telegram SQLite sessions and string-session snapshots.
- `data/accounts/*` account state, posting mode, group intelligence, send history,
  worker checkpoints, login state, and DM inbox/media state.
- Groups/message defaults, fleet defaults, CRM leads/calls/block list, contact
  links, AI smart-reply JSON fallback, Web Push subscriptions/keys, WhatsApp media,
  voice-call state, worker restart/resume state, and statistics.

### Operations file state

- Candidate JSON fallback, proofs, resumes and attachment data.
- Payment evidence, pending payment proofs, receiver/referrer registries,
  verification ledger and recalculation audit.
- Handler/company expenses and proofs, salaries, BGV register, historical booking
  records, operator tasks, Data Room opportunities/credentials/offer cache, daily
  briefing, interview reminder state, OCR policy, staff directory, and Ollama node
  state.

All runtime files remain excluded from source and must be migrated only through a
future verified data-cutover procedure.

## Frontend

The current React/Vite dashboard contains both domains. Marketing views include
the account fleet, campaign/forwarding setup, inbox/CRM, smart replies and
communication administration. Operations views include Candidates, Handler Kit,
Daily Ops, Recruitment Mail, mail notifications, Outcome Audit, Payment
Reconciliation, BGV, Data Room, daily briefing and OCR administration.

Desktop and mobile view registries are not identical: the desktop shell currently
registers payment reconciliation and BGV directly, while the mobile shell does
not expose both in its main-view mapping. Parity work must preserve current
reachable behavior and add focused route/navigation tests rather than treating a
successful Vite build as sufficient.

The Android client is mixed-domain: it contains Accounts/Inbox as well as
Candidates/Daily Ops/Data Room/Handler Kit. Its final ownership is therefore
`UNKNOWN/REQUIRES-DECISION`; copying it wholesale into Marketing would preserve an
Operations dependency.

## Configuration

Static inspection found roughly 171 environment names referenced across source
and tooling, while the root `.env.example` documents 91 keys. Some unmatched
names are tool/dev variables, but many live application settings are undocumented.
The final projects require owner-specific examples generated from actual runtime
usage, without values.

## CI and deployment

Current required CI compiles the backend, runs the full Python suite, installs the
frontend with `npm ci`, runs frontend tests and builds Vite. It does not validate a
fresh PostgreSQL schema, build containers, start Compose, or run cross-service
contracts.

Production uses an immutable VPS release, Nginx, PM2 and PostgreSQL. This production
path remains out of scope for mutation. The split outputs currently contain only
unverified local Docker/Compose and Nginx plans.

## Inventory blockers carried into design

1. Mixed modules (`api/routers/ai.py`, `core/knowledge_assistant.py`, admin and
   notification code) require behavior-level separation rather than whole-file
   ownership.
2. Operations directly invokes Marketing Web Push/WhatsApp and reads Marketing CRM
   and smart-reply state.
3. Marketing opportunity detection directly depends on Operations Data Room
   persistence in the monolith.
4. The tracked Operations migration chain lacks the `candidates_store` baseline.
5. The July outbox is a table only; no complete dispatcher/reconciliation path is
   wired.
6. The Android application spans both domains.
7. Runtime persistence cannot rely on the old Compose files because they do not
   declare the required persistent volumes.

