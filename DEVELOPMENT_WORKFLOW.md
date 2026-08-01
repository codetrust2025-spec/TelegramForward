# Development Workflow

This document defines the mandatory lifecycle for every repository change. `PROJECT_RULES.md` contains the governing policy.

## Workflow overview

```mermaid
flowchart LR
    R[Requirements] --> B[Feature branch from main]
    B --> D[Development]
    D --> T[Backend and frontend tests]
    T --> C[Commit]
    C --> P[Push]
    P --> PR[Pull Request]
    PR --> RV[Review]
    RV --> M[Merge to main]
    M --> BK[Verify backup]
    BK --> DP[Deploy exact merge commit]
    DP --> V[Verify]
    V --> MN[Monitor]
```

## 1. Requirements

Record the user-visible problem, acceptance criteria, validation order, affected backend/frontend/database/AI/mobile paths, migration needs, risks, and explicit non-goals. Resolve ambiguous business behavior before implementation.

## 2. Prepare a feature branch

```bash
git status --short --branch
git fetch origin main
git switch main
git pull --ff-only origin main
git switch -c <type>/<short-description>
```

Preserve a dirty starting worktree without deleting changes. Never use destructive reset merely to make the tree clean.

## 3. Development

- Trace the complete behavior before patching symptoms.
- Prefer small, testable functions and existing abstractions.
- Keep persistent changes explicit, idempotent where requests may repeat, and rollback-safe.
- Keep uploads and AI analysis side-effect free unless an approved final mutation boundary is executing.
- Avoid unrelated cleanup and undocumented compatibility behavior.

### Critical booking/payment rules

- Upload, OCR, AI verification, field changes, and auto-save create no candidate or booking.
- Only `POST /bookings/confirm` may create booking records.
- Confirmation is idempotent and rolls back partial writes on failure.
- Payment identity uses UTR/transaction reference, not filename.
- Payment reuse is backend-authorized only under `PROJECT_RULES.md`.

## 4. Test locally

Run focused tests during development, then complete affected suites before review.

### Backend

```bash
python -m pytest -q tests
python -m compileall -q server.py core features services workers api
```

### Frontend

```bash
cd dashboard
npm ci
npm test
npm run build
```

Documentation-only changes also run the standard backend and frontend suites, plus link, command, formatting, policy-consistency, and `git diff --check` validation. A missing toolchain or infrastructure failure must be reported and resolved or explicitly waived during review; it must not be silently skipped.

## 5. Review the diff

```bash
git status --short
git diff --check
git diff --stat
git diff
```

Confirm only intended files changed, no secret or Production value appears, no runtime data is tracked, generated files are expected, tests cover failure paths, and documentation matches behavior.

## 6. Commit and push

```bash
git add <explicit-files>
git diff --cached --check
git diff --cached --stat
git commit -m "<type>(<scope>): <imperative summary>"
git push -u origin <branch>
```

Stage explicit files rather than indiscriminately adding the repository.

## 7. Pull Request and review

- Open a PR into `main`.
- Include requirements, behavior, tests, risks, screenshots, and rollback notes.
- Wait for required checks and review.
- Resolve findings with focused commits.
- Do not rewrite reviewed history unless reviewers explicitly request it.
- Merge normally without force-pushing.

## 8. Synchronize after merge

```bash
git switch main
git fetch origin main
git pull --ff-only origin main
git rev-parse main
git rev-parse origin/main
```

The hashes must match before deployment preparation.

## 9. Backup, deploy, verify, monitor

Follow `DEPLOYMENT.md`. A merged PR is not deployment authorization. Verify a restorable backup, deploy only the exact merged commit from a clean release artifact, validate all gates, and monitor after switching.

## Stop conditions

Stop for unexpected data mutation, secret exposure, ambiguous payment/booking behavior, a new regression, an invalid backup, Git/manifest/Production divergence, failed health checks, or failed rollback.
