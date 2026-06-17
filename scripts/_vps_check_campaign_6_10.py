"""Check account6/10 campaign switch + account9 forwarding."""
from __future__ import annotations

import json
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SLOTS = ("account6", "account9", "account10")


def main() -> int:
    pwd = os.environ.get("VPS_PASSWORD", "")
    if not pwd:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", username="root", password=pwd, timeout=30)

    cmd = r"""
BASE=/opt/telegramforward
CK=/tmp/ta_ck_campaign.txt
. $BASE/.env
curl -s -c $CK -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' \
  -d "{\"username\":\"${DASHBOARD_USERNAME:-admin}\",\"password\":\"$DASHBOARD_PASSWORD\"}" > /dev/null
for slot in account6 account9 account10; do
  echo "=== $slot posting-mode ==="
  curl -s -b $CK "http://127.0.0.1:8000/account/$slot/posting-mode"
  echo
  g=$BASE/data/accounts/$slot/groups.txt
  if [ -f "$g" ]; then echo "groups.txt lines: $(wc -l < "$g")"; else echo "groups.txt: missing"; fi
done
curl -s -b $CK http://127.0.0.1:8000/state
"""
    _, o, _ = c.exec_command(cmd, timeout=45)
    raw = o.read().decode(errors="replace")
    state_json = raw.split("\n")[-1] if raw.strip() else "{}"
    # state is last line only if multiline - parse more carefully
    idx = raw.rfind('{"running"')
    if idx < 0:
        idx = raw.rfind('{"active_account"')
    if idx >= 0:
        print(raw[:idx])
        try:
            d = json.loads(raw[idx:])
            for slot in SLOTS:
                s = (d.get("account_states") or {}).get(slot) or {}
                i = (d.get("account_info") or {}).get(slot) or {}
                print(
                    f"RUN {slot} {i.get('name', '?')[:28]:28} | "
                    f"running={s.get('running')} camp={s.get('campaign_running')} "
                    f"fwd={s.get('forwarding_running')} mode={s.get('posting_mode')}"
                )
        except json.JSONDecodeError:
            print(raw[idx:idx + 500])
    else:
        print(raw)

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
