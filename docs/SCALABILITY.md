# Scalability Plan — TelegramForward (50+ accounts)

## Current architecture (single process)

- **One** Python process (FastAPI + asyncio)
- **Per-account** `asyncio.Queue` (priority heap) in memory
- **Per-account** `AccountWorker` + queue processor task
- **HealthMonitor** loop (30s) per-slot checks
- **JSON** persistence on disk

Isolation rule preserved: no shared queue consumer across accounts.

## Phase 1 — Harden single host (implemented)

| Component | Purpose |
|-----------|---------|
| `RetryManager` | Exponential backoff + jitter, FloodWait/network classification |
| `HealthMonitor` | Stuck worker, dead processor, queue full/high watermark |
| Priority queue | RETRY > DM > GROUP/JOIN > RUN_CYCLE |
| Backpressure | `MAX_QUEUE_SIZE` (default 200), `QueueBackpressureError` |
| `EventBus` | Channels: UI, CRM, logs, metrics |
| `metrics_store` / `alert_store` | Per-account counters and alert ring |
| `GET /metrics`, `/alerts` | Ops endpoints |

Env tuning for 50 accounts on one machine:

```bash
QUEUE_MAX_SIZE=150
QUEUE_BACKPRESSURE_POLICY=delay   # delay | reject | drop_low
HEALTH_CHECK_INTERVAL=45
WORKER_STALE_SECONDS=3600
AUTO_RESTART_ON_CRASH=1
RETRY_MAX_ATTEMPTS=6
```

## Phase 2 — Redis queue (prepared, not active)

`messaging/queue_backend.py` defines:

- `InMemoryQueueBackend` — production today
- `RedisQueueBackend` — stub; activate with `QUEUE_BACKEND=redis` + `REDIS_URL`

### Redis key design (per-account isolation)

```
tf:queue:{account_id}:high   # LIST — retry + priority
tf:queue:{account_id}:normal # LIST — group/dm/cycle
tf:meta:{account_id}         # HASH — depth, last_dequeue
```

**Rules:**

- Producers (API) `LPUSH` only to the slot in the URL path
- Consumers: **one worker process per account** OR one process with N tasks each `BRPOP` one account key — never one consumer for all keys

### Migration steps

1. Implement `RedisQueueBackend.enqueue/dequeue` with `redis.asyncio`
2. Replace `AccountQueue.put/get` to delegate to backend when `QUEUE_BACKEND=redis`
3. Run API process stateless; worker processes colocated or separate
4. Keep Telethon sessions on same host as that account's worker (session locality)

## Phase 3 — Multi-process workers

```
┌─────────────┐     ┌──────────────────┐
│  API tier     │     │  Worker tier      │
│  FastAPI x1   │────▶│  worker@account1  │
│  (no Telethon)│     │  worker@account2  │
└─────────────┘     │  ...              │
                    └──────────────────┘
                           │
                    Redis / file sessions
```

- **API tier:** MessageRouter → Redis queue only
- **Worker tier:** `python -m workers.runner --account account7` one process per slot (or pool of 5 slots per process with strict isolation)
- **WebSocket:** Redis pub/sub channel `tf:events` → API fans out to browsers

## Phase 4 — 50+ accounts

| Limit | Mitigation |
|-------|------------|
| SQLite session lock | StringSession sidecar per slot; one Telethon connection per worker process |
| Event loop load | Split workers across 2–4 machines by account range |
| Full-state WS | Diff payloads per `account_id` only |
| JSON CRM/inbox | Move to SQLite/Postgres per deployment |

## What NOT to do

- Single global queue for all accounts
- One Telethon client shared across slots
- One worker task consuming multiple account queues

## Verification checklist (50 accounts)

- [ ] `QUEUE_MAX_SIZE * 50` memory bounded (~10k tasks max)
- [ ] HealthMonitor interval × 50 < CPU budget
- [ ] Stagger starts: 8s between accounts on boot
- [ ] `GET /metrics` monitored externally (Prometheus exporter optional)
- [ ] Single instance lock on port 8000 (Windows)
