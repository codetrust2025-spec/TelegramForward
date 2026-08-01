# Project Rules — Authoritative Policy

This is the single authoritative policy for TelegramForward. It governs humans, maintainers, release operators, automation, and AI assistants. Procedural manuals may not weaken these rules.

## 1. Source of truth

- Reviewed GitHub `main` is canonical application source.
- Production runtime data is operational data, not source code.
- Build artifacts are valid only when tied reproducibly to an exact Git commit.
- Production markers/manifests are evidence, not substitutes for Git.
- These manuals are versioned with code and updated when policy or architecture changes.

## 2. Mandatory lifecycle

`Requirements -> Feature branch from main -> Development -> Backend/Frontend tests -> Commit -> Push -> Pull Request -> Review -> Merge to main -> Backup verification -> Production deployment -> Verification -> Monitoring`

- Never develop, commit, or push directly on `main`.
- Never force-push or rewrite shared history.
- Never bypass PR review.
- Merge approval and deployment approval are separate.
- Never deploy a branch, dirty tree, local patch, or uncommitted file.

GitHub `main` must remain protected with no direct pushes or force-pushes, administrator enforcement, at least one approving review, stale-review dismissal, resolved review conversations, a strict up-to-date requirement, and passing `Backend tests` and `Frontend tests` status checks.

## 3. Protected data

Never commit or overwrite `.env`/secrets, credentials, uploads/resumes/evidence, databases, sessions, logs, caches, temporary/runtime JSON, queues/workers, backups, rollback archives, or forensic evidence. Use sanitized templates and fixtures; Production values never appear in source, tests, commits, PRs, screenshots, commands, or reports.

## 4. Architecture invariants

- Accounts and workers remain isolated.
- Business behavior belongs in focused domain modules, not duplicated across routes, UI effects, uploads, or background handlers.
- API/UI layers orchestrate and validate; they do not create hidden mutation paths.
- Persistent mutations are explicit, rollback-safe, and idempotent when requests may repeat.
- Integrations use timeouts, bounded retries, observable failures, and safe disabled/test modes.
- Configuration is centralized; do not duplicate environment/path definitions as compatibility patches.

## 5. Booking and payment invariants

- Flow: basic details -> payment verification -> invite verification -> final confirmation.
- Upload, OCR, AI verification, form changes, previews, retries, and auto-save create no candidate or booking.
- `POST /bookings/confirm` is the only public creation boundary.
- The retired legacy endpoint remains HTTP 410.
- Confirmation validates before writing, is idempotent, and leaves no partial records on failure.
- Payment identity uses UTR/transaction ID, never filename.
- Reuse is backend-authorized only for the same candidate by phone/candidate ID when the prior booking is `cancelled` or `not_attended`.
- Reuse is blocked for active, confirmed, attended, completed, different-candidate, invalid-reference, or already-rebooked payments.
- Rebookings retain auditable previous-booking and reused-payment links.
- The backend enforces minimum payment and duplicate/reuse rules; UI checks are advisory.
- Re-Service is admin-controlled, invisible as a special candidate flow, one-time, payment-free only with a valid entitlement, and consumed only after successful completion.

## 6. AI and evidence invariants

- AI receives original allowlisted images, not thumbnails.
- OCR/vision normalization never silently changes monetary magnitude, dates, times, references, or identities.
- Conflicting evidence is Needs Review, not Verified.
- Automatic invite extraction requires explicit supported date, start time, and timezone evidence.
- Ambiguous/low-confidence extraction uses manual fields and logs the exact safe failure reason.
- Raw AI responses are protected runtime evidence, not source files.

## 7. Testing policy

- Behavior changes require regression tests for success, rejection, idempotency, rollback, authorization, duplicates, and no-side-effect boundaries.
- Run focused tests and complete affected suites.
- New failures block progress.
- Baseline failures require reproduction on the approved base, exact enumeration, proof of non-causality, and documentation.
- Never weaken or skip tests merely to obtain green status.

## 8. Dependencies and builds

- Dependency declarations and lockfiles are reviewed source artifacts.
- Frontend uses `npm ci` and the checked-in package lock.
- Python Production locks are generated/verified on the target Linux platform; Windows-generated locks do not prove Linux reproducibility.
- Build in a disposable clean checkout and record tool versions, package/build hashes, manifest, and critical asset hashes.
- Stale Production bundles are never canonical source.

## 9. Deployment

- Deploy only the exact reviewed GitHub `main` commit from a clean artifact.
- Deployment automation must fail unless the target commit exactly equals the merged `origin/main` commit; it must never deploy a feature branch or PR head.
- Use immutable `/opt/telegramforward/releases/<commit>/` directories and atomic `/opt/telegramforward/current`.
- Keep the previous verified release and verify a restorable backup first.
- Preserve all protected runtime paths outside releases.
- Automatically roll back failed critical checks.
- Record commit, release ID, operator, UTC timestamp, hashes, verification, and rollback evidence.
- Follow `DEPLOYMENT.md`; legacy in-place and single-file workflows are prohibited.

## 10. Recovery

- Preserve stable Production before reconciling source.
- Separate source from runtime data and compare business behavior before choosing versions.
- Record provenance and never blindly copy Production directories into Git.
- Follow `RECOVERY.md` for incidents, drift, rollback, and disaster recovery.

## 11. Documentation governance

- `PROJECT_RULES.md` defines policy.
- `AGENTS.md` and `CLAUDE.md` bind AI assistants.
- `CONTRIBUTING.md` is the contributor entry point.
- `DEVELOPMENT_WORKFLOW.md` defines change lifecycle.
- `DEPLOYMENT.md` defines releases.
- `RECOVERY.md` defines incident recovery.
- `ARCHITECTURE.md` is technical documentation and does not override policy.
- Older operational docs are historical unless they explicitly defer to this manual set.

Changes to these rules require a dedicated reviewed PR. Emergency pressure, convenience, or tool limitations do not waive them.
