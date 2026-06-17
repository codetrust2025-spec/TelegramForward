"""Deploy auth API + set DASHBOARD_PASSWORD on running VPS backend."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER = "187.127.169.159", "root"
OLD = "/opt/telegramforward.old"
PWD = os.environ.get("VPS_PASSWORD", "")
NEW_PASSWORD = "734720077743"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def patch_server(text: str) -> str:
    if "install_dashboard_auth" not in text:
        needle = 'app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])'
        insert = needle + "\n\nfrom core.dashboard_auth_api import install_dashboard_auth\ninstall_dashboard_auth(app)"
        if needle not in text:
            raise RuntimeError("CORS middleware line not found in server.py")
        text = text.replace(needle, insert, 1)

    old_roots = 'api_roots = {"groups", "account", "accounts", "login", "message", "start", "stop", "state", "health", "ws", "inbox", "crm", "stats"}'
    new_roots = (
        'api_roots = {"groups", "account", "accounts", "login", "auth", "message", "start", "stop", '
        '"state", "health", "ws", "inbox", "crm", "stats", "admin", "ai", "candidates", '
        '"metrics", "alerts", "handler-expenses", "handler-salaries", "push", "devices", "demo-tools", "workspace"}'
    )
    if old_roots in text:
        text = text.replace(old_roots, new_roots, 1)
    return text


def update_env(path: str, sftp: paramiko.SFTPClient) -> None:
    try:
        with sftp.open(path, "r") as f:
            lines = f.read().decode("utf-8").splitlines()
    except OSError:
        lines = []
    out = []
    found = False
    for line in lines:
        if line.startswith("DASHBOARD_PASSWORD="):
            out.append(f"DASHBOARD_PASSWORD={NEW_PASSWORD}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"DASHBOARD_PASSWORD={NEW_PASSWORD}")
    tmp = path + ".tmp"
    with sftp.open(tmp, "w") as f:
        f.write("\n".join(out) + "\n")
    sftp.rename(tmp, path)


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()

    for name in ("dashboard_auth_api.py", "dashboard_auth_vps.py"):
        local = os.path.join(REPO, "core", name)
        remote = f"{OLD}/core/dashboard_auth_api.py" if name.endswith("_api.py") else f"{OLD}/core/dashboard_auth.py"
        print(f"upload core/{name} -> {remote}")
        sftp.put(local, remote)

    with sftp.open(f"{OLD}/server.py", "r") as f:
        server = f.read().decode("utf-8")
    server = patch_server(server)
    with sftp.open(f"{OLD}/server.py", "w") as f:
        f.write(server.encode("utf-8"))
    print("patched server.py")

    sftp.close()

    env_cmd = (
        f'for f in "{OLD}/.env" /opt/telegramforward/.env; do '
        f'[ -f "$f" ] || touch "$f"; '
        f'if grep -q "^DASHBOARD_PASSWORD=" "$f"; then '
        f'sed -i "s/^DASHBOARD_PASSWORD=.*/DASHBOARD_PASSWORD={NEW_PASSWORD}/" "$f"; '
        f"else echo DASHBOARD_PASSWORD={NEW_PASSWORD} >> \"$f\"; fi; "
        f'echo "set $f"; done'
    )
    _, o, e = c.exec_command(env_cmd, timeout=30)
    print(o.read().decode("utf-8", errors="replace"))
    if e.read():
        print("env stderr:", e.read().decode()[:200])

    cmds = [
        "pm2 restart telegram-backend",
        "sleep 3",
        f'curl -s -X POST http://127.0.0.1:8000/auth/verify-admin -H "Content-Type: application/json" -d \'{{"password":"{NEW_PASSWORD}"}}\'',
        f'curl -s -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" -d \'{{"username":"admin","password":"{NEW_PASSWORD}"}}\'',
    ]
    for cmd in cmds:
        print(">>>", cmd[:100])
        _, o, e = c.exec_command(cmd, timeout=60)
        print(o.read().decode("utf-8", errors="replace")[:500])
        err = e.read().decode("utf-8", errors="replace")
        if err:
            print("stderr:", err[:300])

    c.close()
    print("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
