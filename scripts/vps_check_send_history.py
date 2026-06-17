#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("python3 - <<'PY'\nimport json, time\nfrom pathlib import Path\nfor slot in ['account10','account7']:\n    p=Path(f'/opt/telegramforward.old/data/accounts/{slot}/send_history.json')\n    if not p.exists():\n        print(slot, 'no history'); continue\n    d=json.loads(p.read_text())\n    recent=sorted(d.items(), key=lambda x: x[1].get('ts',0) if isinstance(x[1],dict) else 0)[-5:]\n    print(slot, 'entries', len(d), 'recent:')\n    for k,v in recent:\n        if isinstance(v,dict):\n            print(' ', k, v.get('result'), v.get('ts'))\nPY", timeout=30)
print(stdout.read().decode())
c.close()
