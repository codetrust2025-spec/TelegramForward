# Feature ownership matrix

Source: `main` at `68a28ecf2301c537eb8ee96f7d30649bd832c2f1`.

Each row has exactly one target classification. `PLATFORM/INFRASTRUCTURE` means
each project owns an independent implementation/configuration where needed; it
does not authorize a shared runtime database or filesystem.

| Feature / behavior | Classification | Current evidence and boundary rule |
|---|---|---|
| Telegram account provisioning and OTP lifecycle | MARKETING | Account routes, Telethon client and account manager |
| Telegram session files and string-session snapshots | MARKETING | Account/session lifecycle; never copied to Operations |
| Account worker lifecycle, restart and watchdog | MARKETING | Account worker/runtime/manager |
| Telegram groups, health and assignments | MARKETING | Groups router and group stores |
| Group joining and membership refresh | MARKETING | Join features and membership scheduler |
| Campaign posting | MARKETING | Account feature runtime and worker |
| Forwarding and forward-message jobs | MARKETING | Forwarding/accounts routes and forward service |
| Marketing schedules, retry and rate coordination | MARKETING | Messaging queue/retry and account worker |
| DM inbox, media, export and read state | MARKETING | Inbox router and DM service/stores |
| CRM leads, notes, follow-ups and spam controls | MARKETING | CRM router/stores/services |
| Telegram and web voice calls | MARKETING | Voice/call APIs and call services |
| WhatsApp communication and media | MARKETING | WhatsApp API/BSP/services |
| Marketing Web Push subscriptions | MARKETING | Marketing-owned subscription/key store |
| Smart reply, lead qualification and marketing AI | MARKETING | AI smart-reply routes/store/engine |
| Marketing communication analytics | MARKETING | Stats, metrics, account observability |
| Marketing notification sounds | MARKETING | Inbox/call/DM sound events |
| Candidate lifecycle and identity | OPERATIONS | Candidate router/store/identity resolver |
| Candidate resumes, attachments and profile photos | OPERATIONS | Candidate attachments and candidate routes |
| Candidate proof archive/history/replace | OPERATIONS | Candidate routes and payment evidence history |
| Public slots and booking confirmation | OPERATIONS | Public-slot API and candidate store |
| Interview scheduling, attendee and attendance | OPERATIONS | Candidate routes/store and Daily Ops |
| Interview reminders and calendar identity | OPERATIONS | Reminder loop and calendar parser |
| Interview reconciliation | OPERATIONS | Reconciliation service and migration 024 |
| Gmail OAuth and mailbox management | OPERATIONS | Recruitment-mail API/provider/store |
| Gmail Pub/Sub and ingestion queue | OPERATIONS | Recruitment-mail routes/store/migration 011 |
| Recruitment classification and review | OPERATIONS | Recruitment agent, semantics and review APIs |
| Offer verification and job-status truth | OPERATIONS | Offer visibility/store and migrations |
| Mail notifications and mail WebSocket | OPERATIONS | Mail notification routes and realtime store |
| Mail outcome audit and cleanup | OPERATIONS | Audit routes/store/migrations 019-021 |
| Mail audit AI queue/results | OPERATIONS | Audit AI module/worker and migration 022 |
| Operations Web Push subscriptions | OPERATIONS | Must use an Operations-owned store; delivery may use a Marketing contract only when the channel is Marketing-owned |
| OCR policy and operational document/image OCR | OPERATIONS | OCR routes/policy and operations extractors; must remain gated by OCR policy |
| Payment receiver and referrer registry | OPERATIONS | Referrer/payment registry modules |
| Payment evidence and proof files | OPERATIONS | Evidence store and candidate/expense routes |
| Payment verification and duplicate protection | OPERATIONS | Verification/fraud/transaction identity modules |
| Payment allocation and reconciliation | OPERATIONS | Allocation/reconciliation modules and UI |
| Payment ledger and entitlements | OPERATIONS | Payment migration 017 and candidate-store logic |
| Handler/company expenses and proofs | OPERATIONS | Expenses router and stores |
| Handler salaries and payout privacy | OPERATIONS | Salary store and payout reference scope |
| BGV register and cases | OPERATIONS | BGV feature, routes and UI |
| Data Room records, credentials and offer cache | OPERATIONS | Data Room router/stores/service |
| Operator tasks and pending works | OPERATIONS | Operator task/candidate stores and Daily Ops |
| Daily Ops and operational reports | OPERATIONS | Daily Ops frontend and candidate reporting |
| Daily briefing | OPERATIONS | Candidate/attendance/payment reporting; CRM inputs must arrive through a contract |
| Staff directory | OPERATIONS | Operational staff/handler configuration |
| Marketing opportunity/lead handoff to Operations | SHARED-CONTRACT | Versioned idempotent opportunity event; Operations persists the result |
| Operations request for Telegram/WhatsApp delivery | SHARED-CONTRACT | Versioned delivery command; Marketing owns provider execution |
| Operations request for Marketing CRM summary | SHARED-CONTRACT | Bounded read-only summary or durable projection; no CRM file/DB access |
| Candidate/contact external identity link | SHARED-CONTRACT | Stable external IDs and redacted snapshots only |
| Operations delivery status back to caller | SHARED-CONTRACT | Delivery ID/status contract with reconciliation |
| Health endpoints | PLATFORM/INFRASTRUCTURE | Independent health per service; must not require peer availability |
| Authentication/session signing | PLATFORM/INFRASTRUCTURE | Independent cookies/secrets and route registries per service |
| Admin/handler role policy | PLATFORM/INFRASTRUCTURE | Preserve current semantics initially, with independent authorization tests |
| Internal service authentication | PLATFORM/INFRASTRUCTURE | Separate service credential/signature configuration |
| PostgreSQL connection and migration runner | PLATFORM/INFRASTRUCTURE | Independent DB URL, ledger and schema per project |
| Logging, correlation IDs and metrics | PLATFORM/INFRASTRUCTURE | Independent redacted logs with cross-service correlation |
| AI/Ollama gateway and node selection | PLATFORM/INFRASTRUCTURE | Both domains consume AI independently; no domain database sharing |
| Common React primitives and accessibility helpers | PLATFORM/INFRASTRUCTURE | May be duplicated or later packaged; no runtime coupling |
| Notification sound engine | PLATFORM/INFRASTRUCTURE | Independent registries; feature events remain domain-owned |
| Docker, Compose, Nginx templates and CI | PLATFORM/INFRASTRUCTURE | Independent build/test/deployment configuration |
| Production cutover and rollback tooling | PLATFORM/INFRASTRUCTURE | Designed now, not executed during resync |
| Android application containing Accounts plus Candidates/Daily Ops/Data Room | UNKNOWN/REQUIRES-DECISION | Current client spans both domains; choose two apps or a dual-service shell before final mobile parity |
| Monolith-wide Knowledge Assistant | UNKNOWN/REQUIRES-DECISION | Currently reads both CRM and candidate/payment/attendance stores; split into owner-specific assistants or define bounded query contracts |
| Legacy combined admin dashboard endpoint | UNKNOWN/REQUIRES-DECISION | Must be decomposed; retaining one combined endpoint would recreate coupling |

## Enforced ownership consequences

- Operations cannot import Marketing CRM, smart-reply, Web Push or WhatsApp
  provider modules.
- Marketing cannot import candidate, booking, payment, recruitment-mail or Data
  Room stores.
- Shared contracts exchange commands/events/projections, never database handles,
  file paths, provider credentials, cookies or live session state.
- Service startup and health must remain valid when the peer service is offline.

