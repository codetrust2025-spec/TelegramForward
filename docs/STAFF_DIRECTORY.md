# Staff Directory (staff names & personal phone numbers)

Real staff names, personal phone numbers and WhatsApp links must **never** be
committed to Git. They live in an external, git-ignored config file and are
loaded at runtime. Source and the committed `*.example.json` contain
placeholders only.

## Where the real directory belongs

- **File:** `config/staff_directory.json` (git-ignored — see `.gitignore`).
- **Override path:** set env `STAFF_DIRECTORY_FILE=/abs/path/staff_directory.json`.
- **On the server:** place the real `config/staff_directory.json` under the app
  root (`/opt/telegramforward/config/staff_directory.json`). It is deploy-safe:
  the git-based deploy never overwrites git-ignored files.

## Format

Copy the template and fill in real values:

```bash
cp config/staff_directory.example.json config/staff_directory.json
# edit config/staff_directory.json with the real names/numbers
```

```json
{
  "persona_name": "Karthik",
  "members": {
    "senior_tech":    {"name": "…", "phone": "9000000001",      "whatsapp": "https://wa.me/91…"},
    "data_lead":      {"name": "…", "phone": "+91 90000 00002", "whatsapp": "https://wa.me/91…"},
    "react_lead_a":   {"name": "…", "phone": "+91 …",           "whatsapp": "https://wa.me/91…"},
    "react_lead_b":   {"name": "…", "phone": "+91 …",           "whatsapp": "https://wa.me/91…"},
    "devops_lead":    {"name": "…", "phone": "+91 …",           "whatsapp": "https://wa.me/91…"},
    "operator_extra": {"name": "…", "phone": "…",               "whatsapp": ""}
  }
}
```

Role slugs (no real name appears in source):

| slug | role |
|--|--|
| `persona` | auto-reply persona identity |
| `senior_tech` | senior software engineer (Java / AI / interview-dev) |
| `data_lead` | senior data analyst (Power BI / data) — pricing owner |
| `react_lead_a` / `react_lead_b` | React / frontend seniors |
| `devops_lead` | DevOps / Cloud senior |
| `operator_extra` | extra operator number (human-operator detection) |

> The `phone` string is stored **exactly** as the app renders it (some sites use
> bare 10 digits, others `+91 xxxxx xxxxx`). `staff_directory.phone_digits(slug)`
> returns the last 10 digits for matching/allowlists.

## How to add staff / rotate numbers

1. Edit `config/staff_directory.json` on the server (or your secure copy).
2. Add a member under `members` with a new role slug, or change an existing
   `phone` / `whatsapp` / `name`.
3. Restart the backend (`pm2 restart telegram-backend`) — the directory is read
   at import. No code change or redeploy is required for value changes.
4. To reference a **new** slug in code, add an accessor call
   (`staff_directory.name("<slug>")`) — never hardcode the value.

## How to configure / deploy safely

- Keep the real file out of Git (already git-ignored).
- Ship it to the server out-of-band (scp / secrets manager), not via the repo.
- CI / fresh clones fall back to the placeholders in `core/staff_directory.py`
  so the app stays importable and tests pass without the real file.
- Consumed by `core/ai_smart_reply.py`, `core/ai_smart_reply_store.py`,
  `core/config.py`, `core/karthik_economy_preset.py`.

## Remaining manual step for the dashboard

`dashboard/src/teleautomation-app.jsx` shows a staff contact number. The
frontend cannot read the Python directory, so it currently renders a
placeholder. Wire it to a backend endpoint that returns the configured contact
(e.g. from `ai_smart_reply_store` config) before relying on that display.
