"""Start forwarding on account9 (Madhu) and verify."""
from __future__ import annotations

import json
import os
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, SLOT = "187.127.169.159", "root", "account9"


def main() -> int:
    pwd = os.environ.get("VPS_PASSWORD", "")
    if not pwd:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=pwd, timeout=30)

    remote = r"""
set -e
BASE=/opt/telegramforward
CK=/tmp/ta_session_ck.txt
rm -f "$CK"
if [ -f "$BASE/.env" ]; then
  set -a
  . "$BASE/.env"
  set +a
fi
USER="${DASHBOARD_USERNAME:-admin}"
PASS="${DASHBOARD_PASSWORD:-}"
if [ -z "$PASS" ]; then
  echo "AUTH: disabled — calling API without login"
  AUTH_HDR=""
else
  echo "AUTH: logging in as $USER"
  curl -s -c "$CK" -X POST http://127.0.0.1:8000/auth/login \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$USER\",\"password\":\"$PASS\"}" | head -c 200
  echo ""
  AUTH_HDR="-b $CK"
fi
echo ">>> posting mode"
curl -s $AUTH_HDR "http://127.0.0.1:8000/account/SLOT/posting-mode"
echo ""
echo ">>> start forwarding"
curl -s -X POST $AUTH_HDR "http://127.0.0.1:8000/account/SLOT/start?feature=forwarding"
echo ""
""".replace("SLOT", SLOT)

    def run(cmd: str) -> str:
        _, o, e = c.exec_command(cmd, timeout=60)
        return (o.read() + e.read()).decode(errors="replace")

    print(run(remote))

    time.sleep(4)

    print("\n>>> state slice")
    raw = run(
        r"""
BASE=/opt/telegramforward
CK=/tmp/ta_session_ck.txt
curl -s -b "$CK" http://127.0.0.1:8000/state
"""
    )
    try:
        d = json.loads(raw)
        st = (d.get("account_states") or {}).get(SLOT) or {}
        info = (d.get("account_info") or {}).get(SLOT) or {}
        print(f"name: {info.get('name')}")
        print(f"running: {st.get('running')}")
        print(f"forwarding_running: {st.get('forwarding_running')}")
        print(f"posting_mode: {st.get('posting_mode')}")
        print(f"notification: {st.get('notification')}")
        fwd = st.get("forwarding") or {}
        print(
            f"fwd cycle={fwd.get('cycle') or st.get('forwarding_cycle')} "
            f"success={fwd.get('success') or st.get('forwarding_success')} "
            f"active_groups={fwd.get('active_groups') or st.get('forwarding_active_groups')}"
        )
    except json.JSONDecodeError:
        print(raw[:800])

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
