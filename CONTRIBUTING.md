# Contributing to TelegramForward

All contributors, including maintainers and AI assistants, use the same review and safety process.

## Read first

- `PROJECT_RULES.md` — authoritative policy and invariants
- `DEVELOPMENT_WORKFLOW.md` — required change lifecycle
- `ARCHITECTURE.md` — technical architecture
- `DEPLOYMENT.md` — Production release process
- `RECOVERY.md` — incident and drift recovery

## Development setup

### Backend

Use Python 3.12 unless the repository explicitly pins another version.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
```

Never point development at Production databases, accounts, sessions, mailboxes, queues, AI tunnels, or credentials. Use sanitized local/test configuration.

### Frontend

The frontend is in `dashboard/`. The last validated toolchain is Node 20.19.0 and npm 10.8.2.

```bash
cd dashboard
npm ci
npm test
npm run build
```

`dashboard/package-lock.json` is authoritative and changes only with an intentional dependency update.

### Android

When `android/` changes, run relevant Gradle tests using its checked-in wrapper. Do not add build outputs to Git.

## Branches

1. Synchronize `main` with `origin/main`.
2. Confirm the worktree is clean or preserve existing work.
3. Create a focused branch from `main`.

Recommended names: `feature/<name>`, `fix/<name>`, `docs/<name>`, `test/<name>`, or `codex/<name>` for Codex-created work.

Never develop on `main` and never force-push shared branches.

## Commits

- Keep commits focused and reviewable.
- Prefer imperative Conventional Commit-style subjects, such as `fix(bookings): preserve idempotent confirmation`.
- Do not combine unrelated formatting, refactoring, and behavior changes.
- Never commit secrets, runtime data, uploads, logs, sessions, databases, caches, or backups.
- Inspect explicit staged files and run `git diff --cached --check` before commit.

## Tests and quality gates

Every change runs the complete backend and frontend suites before review. Behavior changes additionally require focused regression tests, import/compile checks for startup changes, and security review for authentication, payment, booking, PII, upload, and integration paths.

Baseline failures must be proven unrelated and documented. New failures block the change.

## Pull Requests

A PR includes the problem, intended behavior, implementation, tests/builds, screenshots for UI changes, migration/rollback notes, security/data impact, limitations, and follow-up work. Reviewers verify requirements, regression coverage, and absence of protected runtime data.

Merge normally through GitHub review. Do not bypass review with direct pushes.

GitHub branch protection requires:

- at least one approving review from someone other than the author;
- dismissal of stale approvals when new commits change the reviewed diff;
- all review conversations resolved;
- required checks `Backend tests` and `Frontend tests` passing on the current head;
- an up-to-date branch before merge;
- no direct pushes, force-pushes, or deletion of `main`, including by administrators.

## Security reporting

Do not put credentials, candidate data, payment evidence, session contents, or Production diagnostics in public issues. Notify the owner privately, rotate exposed credentials, and follow `RECOVERY.md`.

## Deployment

Merge does not authorize deployment. Production deployment is a separate explicitly approved operation governed by `DEPLOYMENT.md` and requires a verified backup.
