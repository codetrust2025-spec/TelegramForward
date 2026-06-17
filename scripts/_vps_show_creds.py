"""Print production dashboard credentials from VPS."""

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

    sftp.put(

        os.path.join(root, "scripts", "_vps_show_creds_remote.py"),

        f"{REMOTE}/scripts/_vps_show_creds_remote.py",

    )

    sftp.close()

    py = f"{REMOTE}/venv/bin/python"

    _, o, e = ssh.exec_command(

        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} scripts/_vps_show_creds_remote.py",

        timeout=60,

    )

    print(o.read().decode())

    err = e.read().decode()

    if err.strip():

        print(err, file=sys.stderr)

    ssh.close()





if __name__ == "__main__":

    main()

