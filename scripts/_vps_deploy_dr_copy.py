"""Deploy Data room credential copy buttons."""

from __future__ import annotations



import os

import sys



sys.stdout.reconfigure(encoding="utf-8", errors="replace")



HOST = "187.127.169.159"

REMOTE = "/opt/telegramforward"

PASSWORD = os.environ.get("VPS_PASSWORD", "")





def main() -> None:

    import paramiko



    if not PASSWORD:

        print("Set VPS_PASSWORD")

        sys.exit(1)



    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    ssh = paramiko.SSHClient()

    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(HOST, username="root", password=PASSWORD, timeout=30)

    sftp = ssh.open_sftp()

    for rel in (

        "dashboard/src/components/DataRoomPanel.jsx",

        "dashboard/src/index.css",

    ):

        sftp.put(os.path.join(root, rel.replace("/", os.sep)), f"{REMOTE}/{rel}")

        print("uploaded", rel)

    sftp.close()

    _, o, _ = ssh.exec_command(

        f"cd {REMOTE}/dashboard && npm run build && cd {REMOTE} && "

        "bash scripts/production_update.sh 2>/dev/null | tail -6",

        timeout=600,

    )

    print(o.read().decode())

    ssh.close()

    print("Done — hard refresh Data room → Credentials.")





if __name__ == "__main__":

    main()

