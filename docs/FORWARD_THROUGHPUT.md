# Increasing forward post count

**Forward posts** increment only on a successful forward (`record_send(..., "forward")`). Skips and failures do not count.

## Diagnose failures

```powershell
$env:VPS_PASSWORD = '...'
python scripts/_vps_forward_failure_diag.py
```

After deploy, each account’s `/state` → `forwarding.failure_counts` shows the last tick breakdown (e.g. `cant_write`, `blocked`, `flood`).

Account logs also include `fail reasons: cant_write=120, flood=40` at end of each tick.

## Throughput knobs (PM2 / server env)

| Variable | Default | Effect |
|----------|---------|--------|
| `FORWARD_TICK_MIN` | 60 | Minimum groups attempted per tick |
| `FORWARD_TICK_MAX` | 100 | Maximum groups per tick |
| `FORWARD_REST_MIN_SECONDS` | 600 (10m) | Shortest pause between ticks |
| `FORWARD_REST_MAX_SECONDS` | 1800 (30m) | Longest pause between ticks |

Example (more posts per day, higher flood risk):

```bash
export FORWARD_TICK_MAX=120
export FORWARD_REST_MIN_SECONDS=480
export FORWARD_REST_MAX_SECONDS=900
pm2 restart telegram-backend --update-env
```

Batch pacing: `data/forward_message_settings.json` — `batch_size`, `delay_min_seconds`, `delay_max_seconds`, `batch_pause_seconds`.

## Join pool (more targets)

- Add groups to each account’s master list.
- Forwarding joins ~1 group every 2 completed ticks (daily join limits apply).
- Only **joined** Telegram groups are forwarded to.

## Fix failures first

If success rate is under ~40%, raising tick size or shortening rest will mostly add **failed** attempts, not posts. Use failure breakdown to fix:

- **cant_write / blocked** — remove bad groups from master or mark dead (campaign invalid/blocked lists are now skipped in forward ticks).
- **flood** — longer delays or longer rest between ticks.
- **invalid / no_peer** — refresh joined-group cache, fix usernames.
- **session_error** — reconnect account; transient retries are attempted once.
