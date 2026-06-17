"""Restore candidates.json + add bootstrap route + deploy."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST, REMOTE = "187.127.169.159", "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
BACKUP = (
    f"{REMOTE}.old/backups/pre_update_20260603_084737/data/candidates.json"
)


def add_bootstrap_route() -> None:
    server_path = os.path.join(REPO, "server.py")
    text = open(server_path, encoding="utf-8").read()
    if "/candidates/bootstrap" in text:
        return
    needle = '@app.get("/candidates/pending-works")'
    block = '''@app.get("/candidates/bootstrap")
async def candidates_bootstrap(
    request: Request,
    stage: str | None = Query(default=None),
    task: str | None = Query(default=None),
    search: str | None = Query(default=None),
    month: str | None = Query(default=None),
    pending_only: bool = Query(default=False),
    reference: str | None = Query(default=None),
    include_global_stats: bool = Query(default=False),
):
    from core.dashboard_access import handler_reference_scope
    from features import candidate_store

    reference = handler_reference_scope(request, reference)
    payload = candidate_store.bootstrap_data(
        stage=stage,
        task=task,
        search=search,
        month=month,
        pending_only=pending_only,
        reference=reference,
        include_global_stats=include_global_stats,
    )
    return {"status": "ok", **payload}


'''
    if needle not in text:
        raise RuntimeError("pending-works route anchor missing in server.py")
    open(server_path, "w", encoding="utf-8", newline="\n").write(text.replace(needle, block + needle, 1))
    print("Added /candidates/bootstrap route")


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD required", file=sys.stderr)
        return 1

    add_bootstrap_route()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)

    restore_cmd = (
        f"cp {BACKUP} {REMOTE}/data/candidates.json && "
        f"cp {BACKUP} {REMOTE}.old/data/candidates.json && "
        f"python3 -c \"import json; d=json.load(open('{REMOTE}/data/candidates.json')); "
        f"print('restored', len(d.get('candidates',[])), 'candidates')\""
    )
    _, o, e = client.exec_command(restore_cmd)
    print(o.read().decode("utf-8", errors="replace"))
    err = e.read().decode("utf-8", errors="replace")
    if err:
        print(err, file=sys.stderr)

    sftp = client.open_sftp()
    sftp.put(os.path.join(REPO, "server.py"), f"{REMOTE}/server.py")
    print("uploaded server.py")
    sftp.close()

    _, o, _ = client.exec_command(f"cd {REMOTE} && pm2 restart telegram-backend --update-env 2>&1 | tail -2")
    print(o.read().decode("utf-8", errors="replace"))
    client.close()
    print("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
