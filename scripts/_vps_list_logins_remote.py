"""Run on VPS: list operator + Telegram logins (no passwords)."""
import json
import os

import yaml

BASE = "/opt/telegramforward"
STATE = os.path.join(BASE, "data", "accounts")

print("=== DASHBOARD OPERATOR LOGINS ===")
env = {}
for path in [os.path.join(BASE, ".env"), os.path.join(BASE, "data", ".env")]:
    if not os.path.isfile(path):
        continue
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DASHBOARD_USERNAME="):
                env["username"] = line.split("=", 1)[1].strip().strip('"').strip("'")
            if line.startswith("DASHBOARD_PASSWORD="):
                env["password_set"] = bool(line.split("=", 1)[1].strip())

handlers = []
hp = os.path.join(BASE, "config", "dashboard_handlers.yaml")
if os.path.isfile(hp):
    with open(hp, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    for row in raw.get("handlers") or []:
        if isinstance(row, dict) and row.get("username"):
            handlers.append({
                "username": row.get("username"),
                "reference": row.get("reference") or "",
            })

if env.get("username"):
    print(f"  Admin: {env['username']} (password set: {env.get('password_set', False)})")
else:
    print("  Admin: admin (default username if password set in .env)")
if handlers:
    print("  Handlers:")
    for h in handlers:
        ref = f" | ref {h['reference']}" if h["reference"] else ""
        print(f"    - {h['username']}{ref}")
else:
    print("  Handlers: none configured")

print()
print("=== TELEGRAM ACCOUNT SLOTS ===")
cfg = os.path.join(BASE, "data", "accounts_config.json")
slots = []
if os.path.isfile(cfg):
    with open(cfg, encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        slots = sorted(raw.keys())
if not slots:
    slots = [f"account{i}" for i in range(1, 11)]

logged = []
empty = []
for slot in slots:
    info_path = os.path.join(STATE, slot, "account_info.json")
    sess = os.path.join(BASE, f"session_{slot}.session")
    has_sess = os.path.isfile(sess)
    if os.path.isfile(info_path):
        with open(info_path, encoding="utf-8") as f:
            info = json.load(f)
        name = info.get("display_name") or info.get("name") or "-"
        user = info.get("username") or ""
        phone = info.get("phone") or "-"
        un = f"@{user}" if user and not str(user).startswith("@") else (user or "-")
        logged.append((slot, name, un, phone, has_sess))
    else:
        empty.append((slot, has_sess))

print(f"  Logged in: {len(logged)} / {len(slots)}")
for slot, name, un, phone, has_sess in logged:
    sess_note = "session ok" if has_sess else "no session file"
    print(f"    {slot}: {name} ({un}) | {phone} | {sess_note}")
if empty:
    print(f"  Empty slots ({len(empty)}):")
    for slot, has_sess in empty:
        note = "has .session" if has_sess else "empty"
        print(f"    {slot}: - ({note})")
