import re
import urllib.request

base = "https://teleautomation.online"
t = urllib.request.urlopen(f"{base}/assets/app-Bh_EAEC2.js").read().decode("utf-8", "replace")

paths = set()
for m in re.finditer(r'fetch\(`\$\{[a-zA-Z0-9_]+\}(/[^`?]+)', t):
    paths.add(m.group(1))
for m in re.finditer(r'"(/(?:inbox|crm|ai|accounts|state|analytics|refresh)[^"]*)"', t):
    paths.add(m.group(1))

print("fetch paths sample:")
for p in sorted(paths)[:60]:
    print(" ", p)

print("\n--- probe (unauthenticated) ---")
extra = [
    "/analytics?days=30",
    "/refresh-joined",
    "/accounts",
    "/state",
    "/inbox?sync=0",
    "/ai/smart-reply/config",
    "/ai/smart-reply/assessment",
    "/crm/stats",
    "/alerts",
]
for p in sorted(set(list(paths)[:30] + extra)):
    url = base + p.split("?")[0] if "?" not in p else base + p
    if not p.startswith("/"):
        continue
    try:
        r = urllib.request.urlopen(url, timeout=12)
        body = r.read(80)
        kind = "HTML" if body[:15].strip().startswith(b"<") else "JSON"
        print(f"{p[:50]:50} {r.status} {kind}")
    except urllib.error.HTTPError as e:
        body = e.read(80)
        kind = "HTML" if body[:15].strip().startswith(b"<") else "other"
        print(f"{p[:50]:50} {e.code} {kind}")
