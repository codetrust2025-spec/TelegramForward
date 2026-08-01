# TeleAutomation — Gemini CLI Project Context

> **Authoritative policy:** Gemini must first follow `PROJECT_RULES.md`,
> `AGENTS.md`, and `DEVELOPMENT_WORKFLOW.md`. Any instruction below permitting
> direct development/push on `main`, legacy file upload, or deployment without
> a verified backup is superseded.

This file is automatically loaded by Gemini CLI when you run `gemini` from this directory.
It gives you full project context so you can start working immediately.

---

## What this project is

A production Telegram message-forwarding automation system with:
- A **Python/FastAPI backend** running on a VPS (Ubuntu, PM2-managed)
- A **React dashboard** (Vite) for operators to manage accounts, view stats, book interview slots, manage CRM inbox
- **10 Telegram accounts** forwarding messages to ~284 groups independently
- A **Daily Ops module** for interview scheduling and attendance tracking
- A **CRM inbox** with WhatsApp + Telegram unified messaging

---

## Repo & working directory

- **Local path:** `C:\Users\codet\OneDrive\Desktop\Teleautomation_prod\TelegramForward`
- **GitHub (public):** https://github.com/codetrust2025-spec/TelegramForward
- **Branch:** `main`
- **Raw file access:** `https://raw.githubusercontent.com/codetrust2025-spec/TelegramForward/main/<path>`

---

## Architecture overview

```
TelegramForward/
├── server.py                  # FastAPI entrypoint — thin API layer only
├── core/                      # Read-only shared config + per-slot Telethon clients
│   ├── config.py              # Constants, paths (immutable at runtime)
│   ├── telegram_client.py     # One Telethon client per account slot
│   ├── groups_store.py        # Master groups list (read-only for workers)
│   ├── message_store.py       # Message text (read-only for workers)
│   ├── broadcast.py           # WebSocket fan-out
│   └── smart_engine.py        # Weighted group shuffle, health scoring
├── features/                  # Self-contained operations (no cross-imports)
│   ├── group_operation.py     # Atomic per-group op used by workers
│   ├── send_message.py
│   ├── check_last_message.py
│   ├── health_check.py
│   └── ...
├── workers/
│   ├── account_worker.py      # Independent 24/7 loop per account
│   └── account_state.py       # Mutable state for ONE account only
├── services/
│   └── account_registry.py    # Worker registry — no shared execution
├── events/                    # Event bus system
├── dashboard/                 # React + Vite frontend
│   └── src/
│       ├── dailyOps/          # Daily Ops feature (interview roster, filter bar)
│       │   ├── DailyOpsPanel.jsx      ← filter bar lives here
│       │   ├── InterviewRoster.jsx    ← roster table (child of DailyOpsPanel)
│       │   ├── dailyOpsModule.jsx
│       │   └── dateRangePresets.js
│       ├── components/        # Shared UI components
│       │   ├── crm/           # CRM-specific components
│       │   └── ui/            # Generic UI primitives
│       ├── inbox/             # Inbox/chat UI
│       ├── desktop/           # Desktop layout
│       ├── mobile/            # Mobile layout
│       ├── candidates/        # Candidate management
│       ├── context/           # React context (AuthContext, ConfirmContext)
│       ├── utils/             # Logic helpers (no UI)
│       └── App.jsx
├── scripts/                   # Operational + deploy scripts
│   ├── git_deploy_gate.py     # Verify git clean before deploying
│   ├── vps_deploy_dashboard_static.py
│   ├── vps_deploy_auth_routes.py
│   └── dev.py                 # Local dev: uvicorn --reload + Vite HMR
├── data/                      # Runtime data (groups, messages, account state)
├── static/                    # Built React app (served by FastAPI)
└── requirements.txt
```

---

## Key tech stack

| Layer | Tech |
|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn, Telethon 1.36 |
| Frontend | React 18, Vite, JSX |
| Process manager (VPS) | PM2 |
| Reverse proxy (VPS) | Nginx |
| AI features | Ollama (local, SSH-tunneled), qwen2.5:7b |
| Database | PostgreSQL (VPS), JSON files for runtime state |
| Push notifications | Web Push (pywebpush) |

---

## Non-negotiable architecture rules

1. **Every account is fully isolated.** Account A crashing never affects Account B.
2. **Features do not import each other.** Each is callable standalone.
3. **Workers never write to master data.** Only read `groups_list.json` and `message.txt`.
4. **server.py is a thin API layer.** No business logic — all execution in `workers/` and `features/`.
5. **No global mutable state.** All state is per-account (`AccountState`).

---

## Mandatory deploy workflow (ALWAYS follow this order)

```powershell
# 1. Edit code in TelegramForward only (never in Desktop\Automation scratch copy)

# 2. If frontend (dashboard/src) changed — rebuild:
cd dashboard
npm run build
cd ..

# 3. Commit everything including static/ after build:
git add -A
git commit -m "your message"
git push origin main

# 4. Verify git is clean and pushed before deploying:
python scripts/git_deploy_gate.py --require

# 5. Deploy:
python scripts/vps_deploy_dashboard_static.py   # for frontend changes
python scripts/vps_deploy_auth_routes.py        # for backend changes
```

**Never deploy before committing. Never leave prod-only changes without a matching git commit.**

---

## Local development

```powershell
cd C:\Users\codet\OneDrive\Desktop\Teleautomation_prod\TelegramForward
python scripts/dev.py
# OR double-click start-dev.bat
```

- Backend: `uvicorn --reload` on port 8000, watches `core/`, `features/`, `workers/`, `services/`, `server.py`
- Frontend: Vite HMR on port 5173
- Workers auto-resume after reload (`data/.running_workers.json`)

---

## Environment variables (never commit these)

| Variable | Purpose |
|---|---|
| `TELEGRAM_API_ID` | Telegram app ID |
| `TELEGRAM_API_HASH` | Telegram app hash |
| `DASHBOARD_USERNAME` | Login username |
| `DASHBOARD_PASSWORD` | Login password |
| `OPS_API_TOKEN` | Internal API auth |
| `VPS_PASSWORD` | VPS root password — set as local env var only, never in .env |
| `OLLAMA_BASE_URL` | Ollama endpoint (tunneled from laptop) |

See `.env.example` for full list. Copy to `.env` on VPS only.

**Never commit:** `.env`, `*.session`, `VPS_PASSWORD`

---

## Account slots

- `account1` through `account10` (up to 12 slots configured)
- Each has its own session file: `session_account1.session` etc.
- Per-account data: `data/accounts/{slot}/`
- Start/stop via API: `POST /account/{slot}/start` or `POST /account/{slot}/stop`

---

## Common tasks

### Find the filter bar UI
→ `dashboard/src/dailyOps/DailyOpsPanel.jsx`
Filter state: `attendeeFilter`, `roundFilter`, `technologyFilter`, `candidateSearch`, `fromDate`, `toDate`, `rangePreset`

### Add a new API endpoint
→ Edit `server.py`. Keep it thin — call into `features/` or `services/`.

### Change forwarding behavior
→ `workers/account_worker.py` (loop logic), `features/group_operation.py` (per-group atomic op)

### Check VPS logs
→ `python check_vps_logs.py` or `python scripts/vps_pm2_logs.py`

### Deploy only backend changes
→ `python scripts/vps_deploy_auth_routes.py` (after commit + push)

### Deploy only frontend changes
→ `cd dashboard && npm run build && cd ..` → commit → `python scripts/vps_deploy_dashboard_static.py`

---

## Safety rules for Gemini

- Do NOT modify `.env`, `*.session` files
- Do NOT run destructive git commands (`reset --hard`, `force push`, `branch -D`)
- Do NOT deploy to VPS without first verifying git is clean: `python scripts/git_deploy_gate.py --require`
- Do NOT clone the repo or create copies — the working copy is already at the path above
- Always push to `origin/main` only
- Always rebuild dashboard (`npm run build`) before deploying if any `dashboard/src/` file was changed
