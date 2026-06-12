#!/usr/bin/env python3
"""Patch Settings -> Shutdown in live bundle and any source found."""
from __future__ import annotations
import os, socket, sys
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

REMOTE = r'''
import os, re, shutil, glob
from datetime import datetime, timezone

STAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
OLD = 'label:"Settings"'
NEW = 'label:"Shutdown"'
patched = []

# 1) live bundle referenced by index.html
import re as _re
html = open("/opt/telegramforward.old/static/index.html").read()
m = _re.search(r'/assets/(app-[^"]+\.js)', html)
if not m:
    raise SystemExit("no app js in index.html")
js_path = "/opt/telegramforward.old/static/assets/" + m.group(1)
shutil.copy2(js_path, js_path + ".bak_" + STAMP)
s = open(js_path, encoding="utf-8").read()
if OLD not in s:
    raise SystemExit(f"pattern not in {js_path}")
s = s.replace(OLD, NEW, 1)
open(js_path, "w", encoding="utf-8").write(s)
patched.append(js_path)
print("patched bundle:", js_path)

# 2) any dashboard source with same pattern
for p in glob.glob("/opt/telegramforward.old/dashboard/src/**/*.jsx", recursive=True):
    try:
        txt = open(p, encoding="utf-8").read()
    except Exception:
        continue
    if OLD in txt:
        shutil.copy2(p, p + ".bak_" + STAMP)
        open(p, "w", encoding="utf-8").write(txt.replace(OLD, NEW, 1))
        patched.append(p)

print("all patched:", patched)
# verify
s2 = open(js_path).read()
idx = s2.find('id:"settings"')
print("verify:", s2[idx:idx+60])
'''

def ssh_run(script: str) -> str:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
    _, o, e = c.exec_command(f"python3 << 'PYEOF'\n{script}\nPYEOF", timeout=120)
    return o.read().decode() + e.read().decode()

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(ssh_run(REMOTE))
