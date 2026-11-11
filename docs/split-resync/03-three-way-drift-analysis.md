# Three-way drift analysis

Compared inputs:

- A: July `teleautomation-messaging` extraction
- B: July `teleautomation-business` extraction
- C: current monolith `main` at
  `68a28ecf2301c537eb8ee96f7d30649bd832c2f1`

Generated/runtime files were excluded from the tracked-file comparison.

## File-level baseline

| Comparison | Common files | Identical | Different | Current-only | Split-only |
|---|---:|---:|---:|---:|---:|
| Current vs Marketing | 402 | 364 | 38 | 482 | 37 |
| Current vs Operations | 144 | 58 | 86 | 740 | 31 |

The large current-only counts include the opposite domain, current tests,
deployment tools and documentation; they are not all intended for each output.
They do confirm that path-copy parity is not a valid split method.

The content-equivalent rewritten split baseline (`8f165b9`) is 387 commits behind
current `main`. Subject classification finds at least 183 Operations-keyword
commits and only a small set of directly named Marketing commits; platform,
security, deployment and refactor commits still require per-project review.

## Route-level drift

Static application route extraction found approximately:

- Current monolith: 298 route decorators
- July Marketing: 134
- July Operations: 118

Current route behavior missing from both old outputs includes the following
meaningful Operations surfaces:

- OCR policy and audit.
- Mailbox health/overview and multi-node Ollama administration.
- Mail outcome audit, cleanup, gaps, history, approvals and AI-audit controls.
- Referrers and referrer payment accounts.
- BGV dashboard/cases/collections/settlements.
- Candidate typed attachments, profile photo and proof archive/history/replace.
- Payment and handler-expense reconciliation.
- Booking confirmation and stronger payment/slot flows.
- Data Room offer-letter analysis.

The split-only internal routes are:

- Marketing: `GET /internal/v1/operational-summary`
- Marketing: `POST /internal/v1/notifications`
- Operations: `POST /internal/v1/opportunities`

They are provisional bridge implementations rather than complete frozen
contracts.

## Marketing three-way assessment

### Identical / reusable

Most Telegram account, worker, group, joining, campaign, forwarding, inbox, CRM,
call, WhatsApp and communication store modules remain byte-identical and are the
correct reuse base.

### Changed after split

Thirty-eight common tracked files differ. Material backend changes are concentrated
in smart-reply configuration/behavior, AI/Postgres persistence, auth, config,
knowledge assistant, economy preset and WhatsApp media. Frontend changes affect
the shared app shells, smart-reply settings, inbox/call flows, auth UI, responsive
shell and notification behavior.

### New current behavior not represented

- Current `api/routers` refactor and closed-by-default API-root registration.
- Hardened environment-only Telegram credentials.
- New notification sound/event infrastructure.
- Additional Android account API/repository code, while Android also gained
  Operations navigation and therefore cannot be copied wholesale.

### Wrong assignment or coupling

- `core/knowledge_assistant.py` now reads Marketing CRM and Operations candidate,
  payment and attendance stores.
- Smart-reply opportunity detection currently invokes Data Room behavior; the old
  split replaced this with a synchronous network producer, but without durable
  delivery.
- The Marketing compatibility bridge forwards broad legacy Operations routes and
  trusts user identity headers. It is temporary cutover infrastructure, not a
  permanent shared API.
- The old Marketing migration inventory CSV incorrectly contains Business rows,
  so it is obsolete evidence.

## Operations three-way assessment

### Identical / reusable

The July candidate/recruitment-mail foundation, public-slot flow, Data Room base,
expense/salary stores, Gmail provider, recruitment agent and Business dashboard
are useful starting points. Only 58 common tracked files remain identical.

### Changed after split

Eighty-six common files differ, including candidate persistence, public slots,
recruitment mail APIs/store/worker, Gmail provider, interview booking/reminders,
auth, daily briefing, Data Room, payment proof validation and most Operations UI
shells.

### Missing current implementation

- Migrations 011 through 025 from current main.
- Gmail durable ingestion and AI lease/dead-letter handling.
- Outcome audit, audit cleanup/provenance and audit AI.
- Calendar identity and canonical interview reconciliation.
- Payment engine v2, durable evidence, history, allocation, transaction identity,
  duplicate release, ledger/entitlement and reconciliation.
- BGV register and pages.
- Typed candidate attachments, profile photos and resume/proof lifecycle fixes.
- Booking block reasons, stale-write protection, idempotency fixes, timezone/time
  normalization, source/provenance display and clash scoping.
- OCR policy/status UI and the required AI processing status behavior.
- Referrer payment-account administration, staff configuration and newer
  operational notification behavior.
- The corresponding current Python and frontend regression tests.

### Wrong duplication or obsolete split-only code

- Operations directly calls Marketing Web Push/WhatsApp modules in the monolith;
  the old split client only changes this to synchronous HTTP.
- `011_cross_project_outbox.sql` conflicts numerically with current migration 011
  and is not wired to a dispatcher.
- `main.py` contains a large pre-router copy of old Operations routes; current
  behavior moved to `api/routers` and continued changing afterward.
- Old contract documentation says contracts are not frozen while the final report
  says adapters are complete.

## Shared dependency redesign required

| Current coupling | Required redesign |
|---|---|
| Operations booking/recruitment code calls Marketing Web Push and WhatsApp providers | Operations outbox -> versioned Marketing delivery command -> delivery status/reconciliation |
| Operations daily briefing reads Marketing CRM | Bounded CRM summary/projection contract |
| Operations Data Room backfill reads Marketing CRM and smart-reply history | Marketing opportunity events; any backfill runs on Marketing and emits events |
| Marketing smart reply writes Operations Data Room | Durable opportunity event contract |
| Contact links span candidates and conversations | External IDs and redacted snapshots on both sides |
| One auth cookie protects both domains | Independent cookies plus signed service identity for internal calls |
| One Web Push subscription file serves mixed notifications | Owner-specific subscription stores or explicit Marketing delivery contract |
| One Android client calls both domain APIs | Product decision: two clients or an authenticated dual-service shell |

## Migration reconstruction finding

The old Business CI loops over SQL files in lexical order, but no migration creates
`candidates_store`; migration 010 queries that table. Therefore a real fresh
PostgreSQL validation would fail even before considering the 011 conflict.

The deterministic target is:

1. Introduce an Operations baseline migration that creates `candidates_store` and
   a migration ledger.
2. Preserve the semantic order of current migrations 001-025 after verifying
   dependencies and fresh-database safety.
3. Move the cross-project outbox after the current chain under a non-conflicting
   version and extend it with inbox/deduplication/retry/dead-letter state.
4. Give Marketing its own migration ledger and schema for Marketing-owned
   PostgreSQL state and cross-project reliability tables.
5. Test both chains on disposable PostgreSQL before any data-cutover planning is
   considered verified.

