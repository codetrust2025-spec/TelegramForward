# WhatsApp Business API — TeleAutomation

Unified inbox: Telegram + WhatsApp messages appear in the same CRM thread when linked by phone number.

## Enable

Add to `.env` on the server:

```bash
WHATSAPP_ENABLED=1
WHATSAPP_BSP=interakt
WHATSAPP_API_KEY=your_interakt_api_key
WHATSAPP_PHONE_NUMBER_ID=          # Gupshup source number if using Gupshup
WHATSAPP_WEBHOOK_VERIFY_TOKEN=choose_a_random_secret_string
WHATSAPP_DEFAULT_SLOT=account1     # slot for WhatsApp-only leads (no Telegram link)
```

Restart PM2 after changing env vars.

## Webhook URL

Register this URL in Interakt / Meta:

```
https://YOUR_DOMAIN/webhooks/whatsapp
```

Verify token must match `WHATSAPP_WEBHOOK_VERIFY_TOKEN`.

Nginx must allow `POST /webhooks/whatsapp` without dashboard auth (already public in `dashboard_auth.py`).

## Flow

1. Lead messages on Telegram → phone mined from chat or Karthik qualification → `contact_links` table
2. Same lead messages on WhatsApp → webhook matches phone → appends to **same** inbox thread
3. No Telegram link → synthetic negative `user_id` on `WHATSAPP_DEFAULT_SLOT`

## API

| Endpoint | Purpose |
|----------|---------|
| `GET /webhooks/whatsapp` | Meta/Interakt verification challenge |
| `POST /webhooks/whatsapp` | Inbound messages + delivery status |
| `GET /whatsapp/status` | Enabled, BSP, link count, templates |
| `POST /inbox/{slot}/reply` | Pass `"channel": "whatsapp"` to send on WhatsApp |
| `POST /crm/leads/{slot}/{user_id}/link-phone` | Manual link `{ "phone": "9876543210" }` |
| `POST /whatsapp/send-template` | `{ "slot", "user_id", "template", "params": [] }` |

## Templates

Edit `config/whatsapp_templates.yaml`, then submit matching names to your BSP for Meta approval.

## Sprint status

| Phase | Status |
|-------|--------|
| Schema v2 + contact links | Done |
| Webhook listen + inbound | Done |
| Human send from dashboard UI | Done |
| Delivery status callbacks | Done |
| Karthik reply on WhatsApp | Done |
| Inbound image display + cache | Done |
| Auto-save WA images to candidate proofs | Done (when converted) |
| Sidebar channel badges (TG/WA) | Done |

## Local test (no BSP)

```bash
curl -X POST http://127.0.0.1:8000/webhooks/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"type":"message_received","data":{"customer":{"phone_number":"919876543210","name":"Test User"},"message":{"id":"test1","message_type":"text","text":"Hello from WhatsApp"}}}'
```

Set `WHATSAPP_ENABLED=1` first. Message appears under `WHATSAPP_DEFAULT_SLOT` in Inbox.

## Production deploy

```bash
# From project root (Windows PowerShell):
$env:VPS_PASSWORD = "your-vps-root-password"
python scripts/_deploy_whatsapp_once.py

# Or pass password as argument:
python scripts/_deploy_whatsapp_once.py YOUR_VPS_PASSWORD
```

This builds the dashboard, uploads all WhatsApp files + static, runs schema migrate, restarts PM2, and hits `/health` + `/whatsapp/status`.

## Production `.env` (on VPS `/opt/telegramforward/.env`)

```bash
WHATSAPP_ENABLED=1
WHATSAPP_BSP=interakt
WHATSAPP_API_KEY=your_interakt_api_key
WHATSAPP_WEBHOOK_VERIFY_TOKEN=choose_a_long_random_string
WHATSAPP_DEFAULT_SLOT=account1
WHATSAPP_MEDIA_ACCESS_TOKEN=your_meta_permanent_token
```

Then: `pm2 restart telegram-backend --update-env`

## Interakt setup checklist

1. Create Interakt account → connect WhatsApp Business number
2. **Developer → Webhook URL:** `https://YOUR_DOMAIN/webhooks/whatsapp`
3. **Verify token:** same as `WHATSAPP_WEBHOOK_VERIFY_TOKEN` in `.env`
4. Subscribe to: `message_received`, `message_status` (delivery/read)
5. Submit templates from `config/whatsapp_templates.yaml` for Meta approval
6. Copy **API Key** → `WHATSAPP_API_KEY`
7. Copy **Meta access token** (from Meta Business Suite) → `WHATSAPP_MEDIA_ACCESS_TOKEN`

## Nginx

Ensure `/webhooks/whatsapp` proxies to port 8000 (same as API). No special auth — Meta calls this URL directly.

```nginx
location /webhooks/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## Smoke test (local)

```bash
python scripts/_smoke_whatsapp_once.py
```
