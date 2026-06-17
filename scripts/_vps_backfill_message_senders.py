"""Re-tag mislabeled outbound inbox rows (Operator -> AI for Karthik auto-replies)."""

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

    local_dm = os.path.join(root, "core", "dm_store.py")

    sftp.put(local_dm, f"{REMOTE}/core/dm_store.py")

    sftp.close()

    print("uploaded core/dm_store.py")



    py = f"{REMOTE}/venv/bin/python"

    cmd = f"""cd {REMOTE} && PYTHONPATH={REMOTE} {py} -c "

from core.config import ACCOUNTS

from core.dm_store import repair_outbound_sender_labels

total = 0

for slot in ACCOUNTS:

    n = repair_outbound_sender_labels(slot)

    if n:

        print(slot, n)

    total += n

print('patched', total, 'messages')

"

"""

    _, o, e = ssh.exec_command(cmd, timeout=120)

    print(o.read().decode())

    err = e.read().decode()

    if err.strip():

        print(err, file=sys.stderr)

    ssh.close()





if __name__ == "__main__":

    main()

