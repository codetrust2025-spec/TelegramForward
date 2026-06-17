import re
import urllib.request

base = "https://teleautomation.online"
t = urllib.request.urlopen(f"{base}/assets/app-sPW-AjZE.js").read().decode("utf-8", "replace")

paths = sorted(set(re.findall(r'"(/(?:inbox|crm|push|alerts|ai)[^"]{0,60})"', t)))
print("paths from bundle", len(paths))
for p in paths[:50]:
    print(" ", p)

print("\n--- probe ---")
extra = [
    "/alerts",
    "/alerts/status",
    "/alerts/config",
    "/alerts/settings",
    "/push/vapid-public-key",
    "/push/subscribe",
    "/inbox?sync=0",
]
for p in sorted(set(paths + extra)):
    try:
        req = urllib.request.Request(base + p, headers={"Accept": "application/json"})
        r = urllib.request.urlopen(req, timeout=12)
        ct = r.headers.get("Content-Type", "")
        body = r.read(200)
        kind = "HTML" if body[:15].strip().startswith(b"<") else "JSON-ish"
        print(f"{p:45} {r.status} {kind} {ct[:40]}")
    except urllib.error.HTTPError as e:
        b = e.read(80)
        kind = "HTML" if b[:15].strip().startswith(b"<") else "other"
        print(f"{p:45} {e.code} {kind}")
