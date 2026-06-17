# Smart Batch Forward Message

One-shot forwarding: user picks a t.me post, selects groups, clicks **Send** once. The backend runs a single job that processes groups in configurable batches (default **100**, max **100**).

## Files

| Layer | Files |
|-------|--------|
| Batch config | `core/forward_message_batch.py` |
| Job runner | `services/forward_message_service.py` |
| API | `server.py` (forward-message routes) |
| UI state | `services/account_manager.py` (`forward_message_jobs`) |
| Dashboard | `dashboard/src/components/ForwardMessagePanel.jsx` |
| Styles | `dashboard/src/index.css` |
| App wire | `dashboard/src/App.jsx` |

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/forward-message/settings` | Global batch settings |
| POST | `/forward-message/settings` | Save batch size / delays |
| GET | `/account/{slot}/forward-message/groups` | Joined groups list |
| POST | `/account/{slot}/forward-message/preview` | Load message preview |
| POST | `/account/{slot}/forward-message/start` | Start job (`target_ids`, optional `batch_size`) |
| GET | `/account/{slot}/forward-message/job` | Job status |
| POST | `/account/{slot}/forward-message/cancel` | Cancel job |

## Data

- Settings: `data/forward_message_settings.json`
- Job state: persisted per slot at `data/<slot>/forward_message_job.json`, restored on server start (running jobs marked failed); also included in WebSocket `/state` as `forward_message_jobs`

## Deploy

```bash
python scripts/_vps_deploy_forward_tick_live.py
```

Hard refresh https://teleautomation.online

**Requirement:** Stop the 24/7 account worker before starting a batch forward job (same Telegram session).

## Test plan

1. Log in to a test account; stop worker if running.
2. Paste valid `https://t.me/channel/123` → **Load preview** shows text/media hint.
3. **Refresh groups** → select 5–10 groups; set batch size **3** → **Send**.
4. Confirm dashboard: batch 1/3, processed count increases, sent/failed/remaining, % bar, ETA.
5. Wait for completion → summary + attempt log.
6. Start job with worker running → error “Stop the account worker…”.
7. Cancel mid-job → status cancelled, partial counts kept.

## Rollback

1. Restore previous `services/forward_message_service.py`, `server.py`, `ForwardMessagePanel.jsx` from git.
2. Redeploy dashboard + `pm2 restart telegram-backend`.
3. Remove `data/forward_message_settings.json` if needed (optional).

## 24/7 Forwarding worker (Posting setup)

Uses the **same** `data/forward_message_settings.json` batch rules:

- Up to **100** groups per batch (226 joined → 3 batches: 100 + 100 + 26)
- **0.5–1.5s** between groups inside a batch
- **~3s** pause between batches
- **~20 min** rest after the full tick completes, then next tick

Campaign posting and inbox/CRM are unchanged.
