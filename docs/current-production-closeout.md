# Current production closeout — Tele-Automation

Verified: 2026-08-17, against live production. Read-only throughout; nothing was
deployed, restarted, migrated or modified while preparing this.

Supersedes `post-cutover-closeout.md`, which describes 2026-08-16 and is stale in
several places. That document is retained as history and is now banner-marked.

---

## 1. Executive status

**PRODUCTION DEPLOYED AND STABLE.**

All three domains serve 200. Both services healthy. Operations has moved on six
releases since the cutover; Marketing has not moved. Six product features ship;
six were decommissioned and their historical data was deliberately retained. The
three AI inference nodes are online behind a dynamic, fail-closed firewall guard
that was verified by connection test, not by reading its config.

One real security defect is open: **logout does not revoke the session token**.

---

## 2. Current production domains

| domain | status | serves |
|---|---|---|
| `https://teleautomation.online` | 200 | static entry page, three legacy redirects, three provider compatibility proxies |
| `https://marketing.teleautomation.online` | 200 | Marketing |
| `https://operations.teleautomation.online` | 200 | Operations |

nginx `sites-enabled` contains exactly one site, `teleautomation-production`.

## 3. Current release SHAs

Read from live `/version`, not from documentation.

| service | SHA | note |
|---|---|---|
| Marketing | `2f6fe881624f221b420f9871445691cacf7c2dfe` | unchanged since cutover |
| Operations | `ad5e0e61d14add2fad7a4526fa7cb33763d8d7a8` | PR #10, slot-booking-source parity; equals `origin/main` |
| monolith rollback | `68a28ecf2301c537eb8ee96f7d30649bd832c2f1` | release directory present, pm2 entry stopped |

**The old closeout records Operations as `0207819…`. That is now six releases
behind.** The apex is static files served by nginx and carries no release SHA.

## 4. Current product feature set

Taken from the built bundle — what a user actually sees — rather than from the
source tree, which still contains decommissioned code.

Shipping: **Daily Ops · Candidates · Slot Booking · Mail Alerts · Data Room ·
AI Mail Review**.

Absent from the bundle, confirmed by string count of 0 each: Daily Briefing,
Mail Audit, Payment Reconciliation, BGV Register, Handler Kit, Settings.

Route count fell from 153 at cutover to **124** now. `/auth/handler-kit`,
BGV and briefing routes are gone; no mail-audit feature route exists.

The source tree still contains references to the decommissioned features
(13 × "Daily Ops", 5 × "Handler Kit", 4 × "Mail Audit", 3 × "Daily Briefing",
2 × "BGV Register", 1 × "Payment Reconciliation"). These are unbuilt files and
tests, not shipped product — worth a tidy-up, not a correctness problem.

## 5. Authentication

| | Marketing | Operations |
|---|---|---|
| cookie name | `ta_session` | `ta_operations_session` |
| `HttpOnly` | yes | yes |
| `Secure` | yes | yes |
| `SameSite` | lax | lax |
| `Domain` | host-only (absent) | host-only (absent) |

Distinct names and host-only scope are what keep the two apart. A `Domain` on
the parent would make both readable from either subdomain and undo the split.

Verified: correct credentials 200; wrong password, wrong username and empty body
all 401; Marketing's cookie against Operations 401 and the reverse 401.

**Only one session per service is active.** Logging in again invalidates the
previous cookie. This is worth knowing before it is reported as random logouts.

### Logout — open security issue, re-confirmed today

Logout clears the cookie in the browser but **does not revoke the token**.
Tested by capturing the raw `Set-Cookie` value, calling `/auth/logout`, then
replaying that captured value — which tests the token rather than whether the
browser was told to forget it:

| service | before logout | after logout |
|---|---|---|
| Marketing | 200 | **200** |
| Operations | 200 | **200** |

There is no server-side revocation. A token captured before logout stays valid
until it expires. This was suspected previously and is **confirmed current**.

## 6. Marketing verification

Release `2f6fe881…`, container up 18 hours, healthy.

Authenticated and returning 200: `/auth/status`, `/groups`,
`/groups/health-summary`, `/groups/lists`, `/inbox`, `/ai/smart-reply/config`.
`/crm/call-now/options` returns 422 because it requires query parameters.

WebSocket routes declared: `/ws` and `/voice/ws/{join_token}`.

`/account/status` returns 200 but takes **28 seconds**, consistently across three
attempts. It queries Telegram once per account; nginx allows 3600s so it
completes. Unchanged from the previous measurement — not a regression.

Verification level: authenticated route and bundle level, not browser-driven.

## 7. Operations verification

Release `ad5e0e6…`, container restarted 13:58 UTC, healthy.

- 124 routes, 40 tables, **32 foreign keys**
- 27 migrations applied, matching 27 migration files in the release
- Zero error signatures in the last hour
- `/api/ai-recruitment/ollama/status` 200

## 8. Slot Booking parity

`POST /bookings/confirm` with an empty body returns **422** and creates nothing —
the boundary holds. The retired `/public/slots/book` returns **410 Gone**.
`/public/slots/booked` returns 200.

Booking-source parity is **implemented**. The running build contains a dedicated
`src/utils/bookingSource.js` with tests, plus the literals `AI Auto-booked`,
`Candidate booked` and `Booked`, and `SubmitSlotConfirmedSlots.test.jsx`.

| component | status |
|---|---|
| `AiProcessingStatus.jsx` | **present** — previously an open gap, now closed |
| `TwelveHourTimePicker.jsx` | **absent** — still an open parity gap |

## 9. AI Mail Review and OCR

AI Mail Review is active and in the bundle. OCR is controlled from inside it —
there is **no standalone Settings route** (`/settings` and `/api/settings` both
absent).

`/ai/ocr-policy` currently reports:

```
enabled=false  mode=ai  source=admin  updated_by=operations_admin
```

OCR is therefore **off by admin choice**, not by absence of a control.

## 10. AI node connectivity

`/api/ai-recruitment/ollama/nodes` returns three nodes, all **online**:

| node | status | primary |
|---|---|---|
| RTX 4060 | online | no |
| Jagadeesh | online | **yes** |
| Praveen | online | no |

Probed directly from inside the Operations container:

| forwarder | result |
|---|---|
| `172.17.0.1:11435` (Jagadeesh) | HTTP 200 in 0.1s, 8 models |
| `172.17.0.1:11436` (Praveen) | HTTP 200 in 0.1s, 9 models |
| `172.17.0.1:11437` (RTX 4060) | HTTP 200 in 0.2s, 2 models |

The RTX 4060 tunnel, previously recorded as missing, is now up.

## 11. Dynamic Ollama firewall guard

Present and active:

- `/usr/local/sbin/ops-ollama-guard.sh` (755, 76 lines)
- `/usr/local/sbin/ops-ollama-watch.sh` (755, 28 lines)
- `ops-ollama-guard.service` — active, enabled, `Type=oneshot`,
  `RemainAfterExit=yes`, `ExecStop` tears the chain down
- `ops-ollama-watch.service` — active, enabled, `Restart=always`
- `ops-ollama-fwd@.socket` / `ops-ollama-fwd@.service` — socket-activated
  forwarders bound to `172.17.0.1:11435`, `:11436`, `:11437`

**The IP is resolved dynamically, not pinned.** `resolve_ip()` calls
`docker inspect` on the Operations container at apply time and requires exactly
one running container with exactly one IPv4; anything else installs no ACCEPT.
The only literal address in the script is the docker0 gateway.

Current chain, with live counters:

```
-A INPUT -d 172.17.0.1/32 -p tcp -m multiport --dports 11435,11436,11437 -j OPS_OLLAMA
-A OPS_OLLAMA -s 172.19.0.5/32 -j ACCEPT      7603 pkts / 635K
-A OPS_OLLAMA -j DROP                           65 pkts / 3900 B
```

`172.19.0.5` **is** the Operations container's current address — a resolved
value, not a stale constant. No hard-coded dependency remains.

The watcher is **event-driven**: it blocks on `docker events` filtered to
start/die/destroy for that container. Not polling.

Isolation proven by connection test, not by reading rules:

| from | 11435 | 11436 | 11437 |
|---|---|---|---|
| Operations | connected | connected | connected |
| Marketing | TimeoutError | TimeoutError | TimeoutError |

No forwarder is bound to `0.0.0.0` or any public address. Fail-closed holds: the
chain always ends in DROP, and the ACCEPT is only added after the previous one
is removed.

## 12. WebSockets

Verified with a real client — raw TLS socket, full handshake, `Sec-WebSocket-Accept`
recomputed and compared, then a masked ping frame sent.

| socket | result |
|---|---|
| Marketing `/ws` authenticated | **101**, accept valid, ping → 2-byte pong |
| Marketing `/ws` anonymous | 403 |
| Operations `/ws/mail-monitoring` authenticated | **101**, accept valid, ping → 2-byte pong |
| Operations `/ws/mail-monitoring` anonymous | 403 |
| Operations `/ws` | 403 — **route not declared**, absence rather than failure |

## 13. Provider integrations

| provider | status | detail |
|---|---|---|
| WhatsApp | **WORKING THROUGH COMPATIBILITY PROXY** | apex and direct-to-Marketing both return 403 to an unsigned probe — identical, so Marketing's signature check decides, not nginx. Re-pointing remains cleanup, not repair. No real event was sent. |
| Google OAuth | **MANUAL RE-REGISTRATION REQUIRED** | Operations sends `https://operations.teleautomation.online/api/candidate-mailboxes/oauth/google/callback`. Still not registered — unchanged since cutover. |
| Gmail Pub/Sub | **NOT CONFIGURED** | topic and verification token both empty; ingestion is poll-only. |
| Payments | **NOT APPLICABLE** | zero payment-gateway callback routes in the build. |
| Telegram | **NOT APPLICABLE** (outbound) | Telethon connects outward; no webhook exists. |

The apex still proxies all three provider paths (3 matches in the live nginx
site). Those come out once each provider is re-registered.

Telegram session ownership: **5 `.session` + 9 StringSessions in Marketing,
0 in Operations, 5 of 5 authorised.**

## 14. Database integrity

| | |
|---|---|
| Operations tables | 40 |
| Foreign keys | **32** |
| Migrations applied | 27 of 27 |
| Marketing tables | 3 |

Live application counts (growing, as expected on a live system):

| table | rows |
|---|---|
| `candidates_store` | 198 |
| `mailbox_messages` | 15,405 |
| `recruitment_audit_log` | 3,366 |
| `interview_auto_booking_audit` | 169 |
| `mail_realtime_events` | 115,194 |
| `mailbox_sync_jobs` | 58,217 |

## 15. Historical Mail Audit preservation

Retained and intact — **39,641 rows across ten tables, 4 approvals**:

| table | rows |
|---|---|
| `mail_outcome_audit_finding_history` | 12,909 |
| `mail_outcome_audit_findings` | 12,771 |
| `mail_outcome_audit_cleanup_log` | 12,663 |
| `mail_outcome_audit_runs` | 632 |
| `mail_outcome_audit_gaps` | 616 |
| `mail_outcome_audit_candidates` | 21 |
| `mail_audit_ai_queue` | 15 |
| `mail_audit_ai_results` | 10 |
| `mail_outcome_audit_approvals` | **4** |
| `mail_audit_ai_log` | 0 |

**The decommissioned code is not writing to them.** No application module
references any audit table; the single reference in the whole image is
`/app/scripts/decommissioned_audit_tables.py`, the gated drop tool — which was
**not run**. No mail-audit feature route exists in the build.

This is retained historical data, not an active feature. `mail_outcome_audit_runs`
has no `created_at` column, which is structural rather than a gap.

## 16. Backups

All under `/opt/teleautomation-backups` unless noted.

| backup | size | purpose |
|---|---|---|
| `pre-cutover-20260816T183348Z` | 609 M | pre-cutover; dump verified 51/51 tables, runtime archive intact, rollback SHA recorded, mode 600 |
| `pre-decommission-20260817T081000Z` | 112 M | before the six-feature decommission |
| `pre-cleanup-20260817T084255Z` | 112 M | before cleanup |
| `pre-ainodes-20260817T090940Z` | 112 M | before AI-node work |
| `pre-cardlayout-20260817T110715Z` | 112 M | before the card-layout change |
| `pre-uirevert-20260817T113040Z` | 112 M | before the layout revert |
| `pre-slotparity-20260817T132052Z` | 113 M | **latest** — before slot-booking parity |
| `ollama-config-20260817T114223Z` | 28 K | Ollama configuration |
| `ollama-guard-20260817T135249Z` | 28 K | firewall guard configuration |
| `nginx-pre-cutover-20260816T184312Z.tar.gz` | 12 K | nginx before the cutover |
| `/opt/pre-split-backup-20260719` | ~514 M | pre-split monolith (db dump, data dir, session files) |

Only `pre-cutover` was re-verified byte-for-byte today. The others are present
with plausible sizes; their contents were not individually validated.

## 17. Rollback images

Ten Operations rollback tags, five releases × (api, migrate):

| tag SHA | release |
|---|---|
| `0207819…` | PR #4 — the original cutover release |
| `25a60e6…` | PR #5 — decommission |
| `4f8b232…` | PR #7 — AI node styling |
| `0037351…` | PR #8 — AI node card layout |
| `2c0f9a7…` | PR #9 — revert AI node card layout |

`:latest` on both `operations-api` and `operations-migrate` is the running
`ad5e0e6…`. Marketing carries only `:latest` — it has not been redeployed.

Total image disk 1.359 GB, only 10.27 MB reclaimable, 1 dangling image.

> **No registry backs these images.** They exist only on this host.
> **Do not run `docker image prune -a` while rollback tags are required** — it
> would delete every rollback target irrecoverably.

Retention: keep at least `0207819…` (cutover baseline) and the two most recent.
The intermediate layout-experiment tags (`0037351`, `2c0f9a7`) are the first
candidates to retire once `ad5e0e6…` has run clean for a while.

## 18. Staging and legacy resources

| resource | state |
|---|---|
| staging containers | 0 — removed |
| staging nginx site | removed; only `teleautomation-production` enabled |
| staging volumes | **4 retained** (`marketing_data`, `marketing_db`, `operations_data`, `operations_db`) |
| sslip.io certificate | still on disk, unused by any enabled site |
| `/opt/staging` | 13 M, retained |
| `/opt/rehearsal*` | absent — cleaned |
| monolith release dir | present (rollback target) |

Zero `sslip.io` and zero `staging` references in live nginx configuration.
Nothing here was deleted during this task.

## 19. Current known issues

Reassessed. Items fixed since the previous closeout are marked resolved and
excluded from the active list.

**Active:**

1. **Logout does not revoke the token** — confirmed today on both services. A
   token captured before logout remains valid until expiry. Security defect.
2. **`TwelveHourTimePicker.jsx` missing** — Book Slot parity gap.
3. **`/account/status` takes 28 s** — queries Telegram per account. Inherited.
4. **`GET /assets` returns 500** instead of 404 — a bare directory path. No
   client requests it; the page references `/assets/app-*.js`. Cosmetic. It is
   the only 500 in the last hour (257 × 200, 2 × 403, 1 × 500, 1 × 422), and
   both occurrences were caused by this verification.
5. **Decommissioned feature source still in the repo** — unbuilt files and tests
   for the six removed features.
6. **Host-only production configuration** — see §20.

**Resolved since the previous closeout:**

- `AiProcessingStatus.jsx` missing → **now present**
- RTX 4060 tunnel missing → **now up and serving**
- Ollama unreachable from Docker → **forwarders + dynamic guard in place**
- 70 dangling evidence references and 36 quarantined candidate records — these
  were carried as inherited data-quality items; **not re-verified today** and so
  not asserted either way rather than copied forward as fact.

## 20. Host-only configuration and source-control debt

Live production configuration existing **only on the VPS**:

| path | classification |
|---|---|
| `/opt/teleautomation/.env.production` (600) | **secret — must stay out of Git** |
| `/opt/teleautomation/docker-compose.production.yml` (644) | non-secret — should be version-controlled |
| `/etc/nginx/sites-available/teleautomation-production` (644) | non-secret — should be version-controlled |
| `/usr/local/sbin/ops-ollama-guard.sh` (755) | non-secret — should be version-controlled |
| `/usr/local/sbin/ops-ollama-watch.sh` (755) | non-secret — should be version-controlled |
| `/etc/systemd/system/ops-ollama-{guard,watch}.service` | non-secret — should be version-controlled |
| `/etc/systemd/system/ops-ollama-fwd@.{service,socket}` | non-secret — should be version-controlled |

Neither deployed tree carries a `.git` directory — both are extracted artifacts,
which is correct for a deploy but means the host is the only copy of the files
above. The nginx site and the compose file have partial counterparts in the
Marketing repo, but the live versions have diverged.

Nothing was moved or committed during this task.

## 21. Recommended follow-up priorities

1. **Revoke sessions on logout.** The only confirmed security defect. Needs a
   server-side token denylist or a session store; the cookie is already
   correctly scoped and flagged, so this is the remaining gap.
2. **Bring the non-secret host-only configuration under version control** — the
   two Ollama scripts, four systemd units, the nginx site and the production
   compose file. Today a host rebuild would lose the firewall guard entirely.
3. **Close the `TwelveHourTimePicker.jsx` parity gap.**
4. **Re-point the Google OAuth redirect** in the Google console — the only
   remaining external action. New mailbox connections fail until then; existing
   tokens are unaffected.
5. **Make `/account/status` non-blocking** — 28 s of Telegram round-trips on a
   page load.
6. **Tidy the decommissioned feature source** out of the Operations repo.
7. **Re-verify the inherited data-quality items** (dangling evidence references,
   quarantined candidate records) as a separate scoped piece of work.
8. **Retire the two AI-node layout rollback tags** once `ad5e0e6…` has proven
   stable, and consider a registry so rollback images are not host-only.

Ordered by risk: 1 and 2 both concern recoverability, 3–5 are functional, 6–8
are hygiene.

## 22. Final classification

**PRODUCTION DEPLOYED AND STABLE.**

Three domains serving, both services healthy on verified release SHAs, six
features shipping, 32 foreign keys intact, historical audit data preserved and
inert, three AI nodes online behind a dynamic fail-closed guard proven by
connection test, real WebSocket upgrades on both sockets, backups and rollback
targets retained.

One confirmed security defect (logout token revocation) and one parity gap
remain open. Neither prevents production operation.
