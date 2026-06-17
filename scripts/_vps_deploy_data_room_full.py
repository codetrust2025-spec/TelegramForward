"""Full production deploy: Data room + inbox sender badges + related backend."""

from __future__ import annotations



import os

import sys



sys.stdout.reconfigure(encoding="utf-8", errors="replace")



HOST = "187.127.169.159"

USER = "root"

REMOTE = "/opt/telegramforward"

PASSWORD = os.environ.get("VPS_PASSWORD", "")



FILES = [

    "features/data_room_store.py",

    "services/data_room_service.py",

    "core/ai_smart_reply.py",

    "core/dm_store.py",

    "core/dashboard_auth_vps.py",

    "services/dm_inbox_service.py",

    "messaging/message_router.py",

    "workers/account_worker.py",

    "server.py",

    "dashboard/src/App.jsx",

    "dashboard/src/components/DataRoomPanel.jsx",

    "dashboard/src/components/InboxPanel.jsx",

    "dashboard/src/inbox/MessageBubble.jsx",

    "dashboard/src/index.css",

    "config/dashboard_handlers.yaml",

]





def main() -> None:

    import paramiko



    if not PASSWORD:

        print("Set VPS_PASSWORD")

        sys.exit(1)



    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    ssh = paramiko.SSHClient()

    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    sftp = ssh.open_sftp()



    for rel in FILES:

        local = os.path.join(root, rel.replace("/", os.sep))

        if not os.path.isfile(local):

            print(f"SKIP missing {rel}")

            continue

        remote = f"{REMOTE}/{rel}"

        remote_dir = os.path.dirname(remote).replace("\\", "/")

        ssh.exec_command(f"mkdir -p {remote_dir}")

        sftp.put(local, remote)

        print(f"uploaded {rel}")



    # Ensure data room data dir exists

    ssh.exec_command(f"mkdir -p {REMOTE}/data/data_room")

    local_opp = os.path.join(root, "data", "data_room", "opportunities.json")

    if os.path.isfile(local_opp):

        sftp.put(local_opp, f"{REMOTE}/data/data_room/opportunities.json")



    sftp.close()

    py = f"{REMOTE}/venv/bin/python"



    cmds = [

        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} -m py_compile "

        "features/data_room_store.py services/data_room_service.py "

        "core/dm_store.py server.py core/ai_smart_reply.py",

        f"cd {REMOTE}/dashboard && npm run build",

        f"cd {REMOTE} && bash scripts/production_update.sh 2>/dev/null || "

        f"(cp -f dashboard/dist/index.html static/index.html && "

        f"rm -f static/assets/index-*.js static/assets/index-*.css && "

        f"cp -f dashboard/dist/assets/* static/assets/)",

        f"cd {REMOTE} && pm2 restart telegram-backend --update-env",

        "sleep 4",

        f"grep -l 'Data room' {REMOTE}/static/assets/*.js 2>/dev/null | head -1 || echo UI_VERIFY_FAIL",

        f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:8000/health",

        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} -c "

        "\"from features import data_room_store; from core.dm_store import repair_outbound_sender_labels; "

        "from core.config import ACCOUNTS; t=sum(repair_outbound_sender_labels(s) for s in ACCOUNTS); "

        "print('data_room', data_room_store.stats_summary()); print('sender_repair', t)\"",

    ]



    for cmd in cmds:

        print(f"\n>>> {cmd[:100]}...")

        _, stdout, stderr = ssh.exec_command(cmd, timeout=600)

        out = stdout.read().decode("utf-8", errors="replace")

        err = stderr.read().decode("utf-8", errors="replace")

        if out.strip():

            print(out[-4000:] if len(out) > 4000 else out)

        if err.strip():

            print(err[-2000:], file=sys.stderr)



    # Nginx data-room API route

    nginx_script = os.path.join(root, "scripts", "_vps_nginx_data_room_fix.py")

    if os.path.isfile(nginx_script):

        print("\n>>> nginx data-room patch")

        _, o, e = ssh.exec_command(

            f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} scripts/_vps_nginx_data_room_fix.py",

            timeout=60,

        )

        # run locally instead - upload nginx script

        sftp2 = ssh.open_sftp()

        sftp2.put(nginx_script, f"{REMOTE}/scripts/_vps_nginx_data_room_fix.py")

        sftp2.close()

        _, o, e = ssh.exec_command(

            f"cd {REMOTE} && VPS_PASSWORD={PASSWORD!r} PYTHONPATH={REMOTE} {py} "

            "scripts/_vps_nginx_data_room_fix.py",

            timeout=60,

        )

        print(o.read().decode())

        print(e.read().decode(), file=sys.stderr)



    ssh.close()

    print("\nDone — https://teleautomation.online — hard refresh (Ctrl+Shift+R), open Data room tab.")





if __name__ == "__main__":

    main()

