import json, os, tempfile, paramiko
from collections import defaultdict

PASSWORD = os.environ.get("VPS_PASSWORD", "")
paths = [
    "/opt/telegramforward/data/candidates.json.pre_pg_backup_20260528_082739",
    "/opt/telegramforward.old/backups/pre_update_20260611_134335/data/candidates.json",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", PASSWORD, timeout=30)
sftp = c.open_sftp()

for remote in paths:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            sftp.get(remote, tmp.name)
            data = json.load(open(tmp.name, encoding="utf-8"))
        os.unlink(tmp.name)
    except OSError:
        print("missing", remote)
        continue
    rows = data.get("candidates") or []
    by_month = defaultdict(lambda: {"rev": 0, "n": 0})
    for r in rows:
        m = (r.get("date") or "")[:7] or "undated"
        by_month[m]["rev"] += int(r.get("payment") or 0)
        by_month[m]["n"] += 1
    print("===", remote.split("/")[-1], "rows", len(rows))
    for m in sorted(by_month.keys(), reverse=True)[:8]:
        print(f"  {m}: ₹{by_month[m]['rev']:,} ({by_month[m]['n']} candidates)")
    print()

sftp.close()
c.close()
