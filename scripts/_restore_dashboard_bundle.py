"""Restore production to dashboard.bundle.js (SFTP)."""
import os
import re
import sys
import urllib.request

import paramiko

HOST = "187.127.169.159"
USER = "root"
REMOTE_STATIC = "/opt/telegramforward/static"
REMOTE_ASSETS = f"{REMOTE_STATIC}/assets"
REMOTE_INDEX = f"{REMOTE_STATIC}/index.html"
BUNDLE_JS = "dashboard.bundle.js"
BUNDLE_CSS = "dashboard.bundle.css"

repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
local_static = os.path.join(repo, "static")
local_assets = os.path.join(local_static, "assets")
local_index = os.path.join(local_static, "index.html")

pwd = os.environ.get("VPS_PASSWORD", "")
if not pwd:
    print("VPS_PASSWORD required", file=sys.stderr)
    sys.exit(1)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=pwd, timeout=60)
sftp = c.open_sftp()

for name in (BUNDLE_JS, BUNDLE_CSS):
    remote = f"{REMOTE_ASSETS}/{name}"
    local = os.path.join(local_assets, name)
    try:
        st = sftp.stat(remote)
        print(f"remote {name}: {st.st_size} bytes")
    except OSError as e:
        print(f"MISSING on VPS: {remote} ({e})", file=sys.stderr)
        sftp.close()
        c.close()
        sys.exit(2)
    os.makedirs(local_assets, exist_ok=True)
    if not os.path.isfile(local) or os.path.getsize(local) != st.st_size:
        print(f"downloading {name}...")
        sftp.get(remote, local)
    else:
        print(f"local {name} already present ({st.st_size} bytes)")

print("uploading index.html to VPS...")
sftp.put(local_index, REMOTE_INDEX)
sftp.close()
c.close()

# Verify live site
html = urllib.request.urlopen("https://teleautomation.online/", timeout=30).read().decode()
print("live index snippet:", re.search(r"assets/[^\"']+", html).group() if re.search(r"assets/[^\"']+", html) else html[:200])
if "dashboard.bundle.js" not in html:
    print("FAIL: live HTML does not reference dashboard.bundle.js", file=sys.stderr)
    sys.exit(3)

js_path = "/assets/dashboard.bundle.js"
js = urllib.request.urlopen("https://teleautomation.online" + js_path, timeout=120).read()
print(f"live bundle size: {len(js)} bytes")
needles = ["Daily ops", "Works pending", "daily-ops", "cand-workspace"]
text = js.decode("utf-8", errors="ignore")
for n in needles:
    ok = n in text
    print(f"  {n!r}: {'OK' if ok else 'MISSING'}")
    if not ok:
        sys.exit(4)

css = urllib.request.urlopen("https://teleautomation.online/assets/dashboard.bundle.css", timeout=60).read().decode("utf-8", errors="ignore")
for n in ("daily-ops", "cand-workspace"):
    print(f"  css {n!r}: {'OK' if n in css else 'missing'}")

print("RESTORE OK")
