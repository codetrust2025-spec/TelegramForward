"""Seed credentials section + purge legacy credential rows from partner opportunities."""

from __future__ import annotations



import os

import sys



sys.stdout.reconfigure(encoding="utf-8", errors="replace")



HOST = "187.127.169.159"

REMOTE = "/opt/telegramforward"

PASSWORD = os.environ.get("VPS_PASSWORD", "")



FILES = [

    "features/data_room_store.py",

    "features/data_room_credentials_store.py",

    "server.py",

    "dashboard/src/components/DataRoomPanel.jsx",

    "dashboard/src/index.css",

]





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

    for rel in FILES:

        local = os.path.join(root, rel.replace("/", os.sep))

        sftp.put(local, f"{REMOTE}/{rel}")

        print(f"uploaded {rel}")

    sftp.close()



    py = f"{REMOTE}/venv/bin/python"

    cmd = f"""cd {REMOTE} && PYTHONPATH={REMOTE} {py} -c "

import os, yaml

from features.data_room_store import purge_legacy_credential_opportunities, stats_summary

from features.data_room_credentials_store import save_credentials



removed = purge_legacy_credential_opportunities()

handlers = []

hp = '{REMOTE}/config/dashboard_handlers.yaml'

if os.path.isfile(hp):

    with open(hp, encoding='utf-8') as f:

        handlers = (yaml.safe_load(f) or {{}}).get('handlers') or []



admin_user, admin_pass = 'admin', ''

for path in ['{REMOTE}/.env', '{REMOTE}/data/.env']:

    if not os.path.isfile(path):

        continue

    with open(path, encoding='utf-8') as f:

        for line in f:

            s = line.strip()

            if s.startswith('DASHBOARD_USERNAME='):

                admin_user = s.split('=', 1)[1].strip().strip(chr(34)).strip(chr(39)) or admin_user

            if s.startswith('DASHBOARD_PASSWORD='):

                admin_pass = s.split('=', 1)[1].strip().strip(chr(34)).strip(chr(39))



cred = save_credentials(

    site_url='https://teleautomation.online',

    admin_username=admin_user,

    admin_password=admin_pass,

    handlers=handlers,

    vps_host='187.127.169.159',

)

print('purged_legacy_opportunities', removed)

print('credentials_count', cred.get('count'))

print('partner_stats', stats_summary())

"

"""

    _, o, e = ssh.exec_command(cmd, timeout=120)

    print(o.read().decode())

    if e.read().decode().strip():

        print(e.read().decode(), file=sys.stderr)



    _, o, _ = ssh.exec_command(

        f"cd {REMOTE}/dashboard && npm run build && cd {REMOTE} && "

        "bash scripts/production_update.sh 2>/dev/null; "

        "pm2 restart telegram-backend --update-env",

        timeout=600,

    )

    print(o.read().decode()[-2000:])

    ssh.close()

    print("Done — Data room: Credentials section + Business opportunities.")





if __name__ == "__main__":

    main()

