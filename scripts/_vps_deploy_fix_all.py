"""Deploy fix-all round 4: smoke tests, web push, env checks."""

from __future__ import annotations



import os

import secrets

import subprocess

import sys



sys.stdout.reconfigure(encoding="utf-8", errors="replace")



HOST = "187.127.169.159"

USER = "root"

REMOTES = ["/opt/telegramforward", "/opt/telegramforward.old"]

PASSWORD = os.environ.get("VPS_PASSWORD", "")

PY = "/opt/telegramforward/venv/bin/python"

BUILD_STAMP = "2026-06-07-success-rate-fix"





BACKEND_FILES = [

    "core/broadcast.py",

    "core/config.py",

    "core/dashboard_access.py",

    "core/dashboard_auth_api.py",

    "core/dashboard_auth_vps.py",

    "core/dm_store.py",

    "core/demo_tools_api.py",

    "core/voice_call_api.py",

    "core/web_push_api.py",

    "core/whatsapp_api.py",

    "core/joined_membership.py",

    "core/telegram_forward.py",

    "features/demo_tools.py",

    "features/telegram_joined_stats.py",

    "features/web_push.py",

    "messaging/queue_backend.py",

    "services/whatsapp_bsp.py",

    "services/whatsapp_send_service.py",

    "server.py",

    "dashboard/src/App.jsx",

    "dashboard/src/components/AppViewNav.jsx",

    "dashboard/src/utils/workspaceMode.js",

    "dashboard/src/utils/workspaceDashboard.js",

    "dashboard/src/utils/accountUi.js",

    "dashboard/src/utils/whatsapp.js",

    "dashboard/src/desktop/DesktopApp.jsx",

    "dashboard/src/desktop/deskFeedUtils.js",

    "dashboard/src/mobile/mobileUtils.js",

    "dashboard/src/components/LogPanel.jsx",

    "dashboard/src/inbox/InboxMediaAttachment.jsx",

    "dashboard/src/components/ui/ResponsiveOptions.jsx",

]



DASHBOARD_SRC_DIRS = [

    "dashboard/src/components",

    "dashboard/src/inbox",

    "dashboard/src/utils",

    "dashboard/src/desktop",

    "dashboard/src/mobile",

    "dashboard/src/candidates",

    "dashboard/src/admin",

    "dashboard/src/context",

]





def _ensure_remote_dir(sftp, path: str) -> None:

    parts = path.replace("\\", "/").split("/")

    cur = ""

    for part in parts:

        if not part:

            continue

        cur = f"{cur}/{part}" if cur else part

        if cur.startswith("/"):

            try:

                sftp.stat(cur)

            except OSError:

                try:

                    sftp.mkdir(cur)

                except OSError:

                    pass





def _upload_tree(sftp, local_root: str, remote_root: str, rel_dir: str) -> None:

    local_dir = os.path.join(local_root, rel_dir.replace("/", os.sep))

    if not os.path.isdir(local_dir):

        return

    for root, _dirs, files in os.walk(local_dir):

        for name in files:

            local = os.path.join(root, name)

            rel = os.path.relpath(local, local_root).replace("\\", "/")

            remote = f"{remote_root}/{rel}"

            _ensure_remote_dir(sftp, os.path.dirname(remote))

            sftp.put(local, remote)

            print(f"  {remote_root}: {rel}")





def main() -> int:

    if not PASSWORD:

        print("VPS_PASSWORD not set", file=sys.stderr)

        return 1



    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    dash = os.path.join(repo, "dashboard")



    print(">>> local dashboard build")

    r = subprocess.run(["npm", "run", "build"], cwd=dash, shell=os.name == "nt", check=False)

    if r.returncode != 0:

        return r.returncode



    import paramiko



    ssh = paramiko.SSHClient()

    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"Connecting {USER}@{HOST}...")

    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    sftp = ssh.open_sftp()



    for remote_root in REMOTES:

        for rel in BACKEND_FILES:

            local = os.path.join(repo, rel.replace("/", os.sep))

            remote = f"{remote_root}/{rel}"

            try:

                _ensure_remote_dir(sftp, os.path.dirname(remote))

                sftp.put(local, remote)

                print(f"  {remote_root}: {rel}")

            except OSError as e:

                print(f"  skip {remote}: {e}")



        for rel_dir in DASHBOARD_SRC_DIRS:

            print(f"  {remote_root}: sync {rel_dir}/")

            _upload_tree(sftp, repo, remote_root, rel_dir)



    static = os.path.join(repo, "static")

    for rel in ["index.html"] + [

        f"assets/{n}" for n in os.listdir(os.path.join(static, "assets"))

    ]:

        local = os.path.join(static, rel.replace("/", os.sep))

        for remote_root in REMOTES:

            remote = f"{remote_root}/static/{rel}"

            _ensure_remote_dir(sftp, os.path.dirname(remote))

            sftp.put(local, remote)

    print("  static bundle uploaded")



    sftp.close()



    ops_token = secrets.token_urlsafe(24)

    remote_cmds = [

        "if [ -L /opt/telegramforward/dashboard ]; then "

        "rm /opt/telegramforward/dashboard && mkdir -p /opt/telegramforward/dashboard; fi",

        "if [ -L /opt/telegramforward.old/dashboard ]; then "

        "rm /opt/telegramforward.old/dashboard && mkdir -p /opt/telegramforward.old/dashboard; fi",

        f"grep -q '^OPS_API_TOKEN=' /opt/telegramforward/.env 2>/dev/null || "

        f"echo 'OPS_API_TOKEN={ops_token}' >> /opt/telegramforward/.env",

        f"cd /opt/telegramforward && PYTHONPATH=/opt/telegramforward {PY} -c "

        "\"from core.config import ACCOUNT_SLOTS; from core.dm_store import repair_conversation_keys; "

        "print('repairs', sum(len(repair_conversation_keys(s)) for s in ACCOUNT_SLOTS))\"",

        f"cd /opt/telegramforward && PYTHONPATH=/opt/telegramforward {PY} -c "

        "\"from core.dashboard_access import handler_forbidden_path; "

        "assert not handler_forbidden_path('/start','POST'); "

        "assert not handler_forbidden_path('/inbox','GET'); "

        "print('access_ok')\"",

        "grep -q '^WHATSAPP_WEBHOOK_SECRET=' /opt/telegramforward/.env 2>/dev/null "
        "|| echo 'WARN: WHATSAPP_WEBHOOK_SECRET not set — inbound WA webhooks disabled'",

        "grep -q '^DEMO_TOOLS_LOCKEDIN_WINDOWS_URL=' /opt/telegramforward/.env 2>/dev/null "
        "|| echo 'WARN: DEMO_TOOLS_* not set — Karthik demo links disabled'",

        "for f in /opt/telegramforward/config/dashboard_handlers.yaml "
        "/opt/telegramforward.old/config/dashboard_handlers.yaml; do "
        "[ -f \"$f\" ] && chmod 600 \"$f\" && echo \"chmod 600 $f\"; done",

        "pm2 delete telegram-backend 2>/dev/null; true",

        f"cd /opt/telegramforward && PYTHONPATH=/opt/telegramforward NO_RELOAD=1 "

        f"pm2 start {PY} --name telegram-backend --cwd /opt/telegramforward "

        f"-- scripts/uvicorn_reload.py --host 0.0.0.0 --port 8000",

        "sleep 5",

        "pm2 save",

        "rsync -a --delete /opt/telegramforward/static/ /opt/telegramforward.old/static/",

        "curl -s http://127.0.0.1:8000/health | head -c 120",

        f"grep -o 'app-[A-Za-z0-9_-]*\\.js' /opt/telegramforward/static/index.html | head -1",

    ]

    for cmd in remote_cmds:

        print(f"\n$ {cmd[:100]}...")

        _, o, e = ssh.exec_command(cmd, timeout=180)

        out = o.read().decode("utf-8", errors="replace").strip()

        err = e.read().decode("utf-8", errors="replace").strip()

        if out:

            print(out)

        if err:

            print(err, file=sys.stderr)



    ssh.close()

    print(f"\nDone — stamp {BUILD_STAMP}. Hard refresh teleautomation.online")

    return 0





if __name__ == "__main__":

    raise SystemExit(main())


