# Auto-restart & 24/7 operation

## Non-negotiable rule

After **any** watched code change:

1. System **detects** the change (watchfiles / PM2 watch)
2. System **restarts** automatically (no manual stop/start)
3. **Updated code** runs in the new process
4. **Workers resume** from `data/.running_workers.json`

## Development

```bash
python run.py
```

| Layer | Behavior |
|-------|----------|
| Backend | `uvicorn server:app --reload` + watchfiles |
| Frontend | Vite HMR on port 3000 |
| Debounce | `RELOAD_DELAY=1.0` (env) |
| Crash respawn | `scripts/dev.py` restarts backend if it exits (max 12/min) |

### Watched (triggers backend restart)

- `core/`, `features/`, `workers/`, `services/`, `scripts/`
- `server.py`, `run.py`
- `*.py`, `.env`, `.json`, `.yaml` (config at project root)

### Ignored (no restart loop)

- `data/` (groups, sessions, logs, intelligence JSON)
- `*.session`, `dashboard/`, `static/`, `logs/`

## Production (PM2)

```bash
npm install -g pm2
pm2 start ecosystem.config.cjs
pm2 logs telegram-backend
```

| Setting | Value |
|---------|--------|
| `watch` | `true` on Python source |
| `autorestart` | `true` on crash |
| `max_restarts` | 30 |
| `kill_timeout` | 15s (graceful Telethon disconnect) |
| `ignore_watch` | `data/`, sessions, logs |

Set `PM2_FILE_WATCH=0` to use in-process uvicorn reload instead of PM2 file watch.

## Graceful restart sequence

1. **Shutdown** → save running slots → `data/.running_workers.json`
2. **Disconnect** all Telethon clients (release SQLite sessions)
3. **New process** starts with new code
4. **Startup** → staggered `resume_persisted_workers()` (8s between accounts)
5. **Watchdog** → every 45s, restart dead/stuck worker tasks

## Restart logging

All events append to `data/reload.log`:

```
2026-05-20 14:00:01 — [system] Restart triggered (file change: server.py) (restart #42)
```

Restart counter: `data/.restart_count.json`

## 24/7 worker behavior

Each account worker:

```
while running:
    execute_cycle()   # never exits except user STOP
    on error → log → wait 30s → continue
    on crash → auto-restart task in 5s
```

- **FloodWait** → only that account sleeps; others continue
- **Network** → reconnect with retries (`telegram_client._connect_with_retry`)
- **State** → join limits, intelligence, blocked groups on disk under `data/accounts/{slot}/`

## Watchdog

`core/worker_watchdog.py` (started with FastAPI):

- Running but task died → relaunch task
- Running but no activity for 45 min (not in flood sleep) → restart task

Env: `WORKER_STALE_SECONDS`, `WATCHDOG_INTERVAL_SECONDS`

## Validation

```bash
python scripts/validate_auto_reload.py
```

| Check | Expected |
|-------|----------|
| Code change → restart | YES |
| Manual restart needed | NO |
| Workers auto-resume | YES |
| Duplicate workers | NO |
| Crash loops | Protected (12/min) |
| 24/7 until user stops | YES |

## Opt out (rare)

```bash
python run.py --no-reload   # use PM2 watch instead
NO_RELOAD=1 python scripts/uvicorn_reload.py
```
