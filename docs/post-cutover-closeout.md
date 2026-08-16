# Post-cutover verification and closeout

Date: 2026-08-17
Classification: **PRODUCTION DEPLOYED AND STABLE**

Verification performed against live production after the 2026-08-16 cutover. No
migration was re-run, no database recreated, no credential rotated.

## What is running

| | |
|---|---|
| `teleautomation.online` | static entry page + narrow legacy redirects + provider compatibility proxies |
| `marketing.teleautomation.online` | Marketing, release `2f6fe881…` |
| `operations.teleautomation.online` | Operations, release `0207819…` |
| monolith | stopped, retained at `68a28ecf…` as the rollback target |

## Authentication and sessions

Both dashboards accept the stored credentials and refuse everything else — wrong
password, wrong username and an empty body all return 401.

The two services issue **differently named** cookies, `ta_session` and
`ta_operations_session`, both `HttpOnly`, `Secure`, `SameSite=lax`, and both
**host-only**: no `Domain` attribute. That last detail is what keeps the
subdomains apart. A cookie scoped to the parent domain would be readable by
both, and the separation the split exists for would be undone by one attribute.

Measured rather than assumed:

- Marketing's cookie against Operations: **401**
- Operations' cookie against Marketing: **401**
- logout invalidates the session on both

Only one session per service is active at a time — logging in again invalidates
the previous cookie. Worth knowing before someone reports being "randomly logged
out" after opening a second tab.

## Marketing walkthrough

Authenticated, read-only. `/auth/status`, `/health`, `/version`, `/groups`,
`/groups/health`, `/groups/health-summary`, `/groups/lists`, `/groups/removed`,
`/inbox`, `/inbox/delete-config`, `/ai/smart-reply/config`,
`/ai/smart-reply/assessment` all return 200 with real payloads. The frontend
bundle is served and fetches cleanly.

`/account/status` returns 200 but takes **28 seconds**: it queries Telegram once
per account. nginx allows 3600s so it completes, but the UI will sit on a
spinner for half a minute. Inherited behaviour, not a cutover regression.

## Operations walkthrough

Authenticated, read-only, all 200 with real data: `/candidates` (234 KB),
`/api/mail-monitoring/booking-audit` (320 KB), `/payments/reconciliation`
(38 KB), `/api/candidate-mailboxes/overview`, `/api/candidate-mailboxes/health`,
`/ai/ocr-policy`, `/ai/ocr-policy/audit`, `/bgv/cases`, `/handler-expenses`,
`/handler-salaries`, `/company-expenses`, `/data-room`,
`/candidates/interviews/filter-options`.

The booking boundary behaves: `POST /bookings/confirm` with an empty body
returns **422** and creates nothing, and the retired `/public/slots/book`
returns **410 Gone**.

## WebSockets

Real upgrades, not just reachability:

| socket | authenticated | anonymous |
|---|---|---|
| Marketing `/ws` | **101 Switching Protocols** | 403 |
| Operations `/ws/mail-monitoring` | **101 Switching Protocols** | 403 |
| Operations `/ws` | 403 | 403 |

Operations declares only `/ws/mail-monitoring`; `/ws` is absent from its route
table, so 403 there is absence of a route rather than a broken socket. Marketing
declares `/ws` and `/voice/ws/{join_token}`.

The client builds its socket URL from `window.location.host` and picks `wss`
under https (`dashboard/src/config.js:11`), so there is no hardcoded host and no
mixed content. Neither bundle contains `ws://`, `localhost`, `sslip.io` or
`staging`.

## Provider callbacks

| provider | status | note |
|---|---|---|
| WhatsApp | **WORKING THROUGH COMPATIBILITY PROXY** | apex, subdomain and direct-to-service all answer **403** identically to an unsigned probe — nginx is not deciding the outcome, Marketing's signature check is. Re-registration is a tidy-up, not a fix. |
| Google OAuth | **MANUAL RE-REGISTRATION REQUIRED** | the app already sends `https://operations.teleautomation.online/api/candidate-mailboxes/oauth/google/callback`; Google must be told, or new mailbox connections fail with `redirect_uri_mismatch`. Existing tokens are unaffected. |
| Gmail Pub/Sub | **NOT CONFIGURED** | topic and verification token are both empty, as in the monolith. Ingestion is poll-only. The endpoint exists if it is ever enabled. |
| Payment gateway | **NOT APPLICABLE** | none exists; proofs are user-uploaded screenshots. |
| Telegram | **NOT APPLICABLE** | Telethon connects outbound; there is no webhook to register. |

## Data, isolation and policy

- Operations: 195 candidates, 15,151 mailbox messages, **32 foreign keys**
- Cross-database access refused at the role level: `role "marketing_app" does not exist` in the Operations database
- No PostgreSQL port published to the host
- Quarantine intact: 36 archive-only, `candidates.json` **absent** from the application read path and present in `_archive/`
- VAPID keys byte-identical to pre-cutover; **9 push subscriptions** preserved
- Telegram session material: 14 files in Marketing, **0** in Operations, **5 of 5** `.session` files carry an authorised entry
- Cross-service calls succeed in both directions

## Monitoring, first production hour

155 successful requests per service. Every non-2xx traced to a cause:

- **27 + 14 × 401** — login attempts with the retired monolith credentials, plus
  my own anonymous probes. User-side, not defects.
- **8 × 403** — the anonymous WebSocket rejections above, working as intended.
- **1 × 500** — `GET /assets`, a bare directory path reached only by my probe.
  The application raises `RuntimeError: File at path /app/static/assets is not a
  file` rather than returning 404. No client requests it: the page references
  `/assets/app-*.js` and `/assets/index-*.css`. Cosmetic, inherited, left alone.
- **1 × 422, 1 × 410, 3 × 400, 3 × 404** — the deliberate boundary probes.

Operations logged **zero** error signatures. Marketing's are single-occurrence
Telethon coroutine teardown from the container that was stopped during the
cutover, not from the running one.

Mail ingestion is live: 42 sync jobs in 30 minutes. Cross-service outbox is
empty, which is the correct resting state. All four containers healthy, 41 G
disk free, 1.7 GB of 16 GB memory, load under 1.

## Backup and rollback

`/opt/teleautomation-backups/pre-cutover-20260816T183348Z`, 609 MB, mode 600
root:

- database dump readable, **51 tables**
- runtime archive intact
- rollback SHA recorded
- monolith release `68a28ecf…` present on disk, pm2 entry stopped
- monolith database untouched at 355 MB

Rollback remains proxy-first and was deliberately not exercised against healthy
production.

## Staging

Containers removed, nginx site removed, `sites-enabled` contains only
`teleautomation-production`. Zero `sslip.io` and zero `staging` references in
live nginx configuration. The four staging volumes and the unused sslip.io
certificate remain on disk; neither is shared with production, and removing them
is optional housekeeping.

## Non-blocking inherited issues

Documented, not fixed, because none is causing a production failure:

- **70 dangling evidence references** in the candidate store — proof and resume
  entries whose file exists nowhere. Pre-existing; the migration copies files
  wholesale and neither creates nor repairs these.
- **36 quarantined candidate records** awaiting an owner decision.
- `/account/status` takes 28 seconds.
- `GET /assets` returns 500 instead of 404.
