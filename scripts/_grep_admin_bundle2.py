import re
import urllib.request

t = urllib.request.urlopen("https://teleautomation.online/assets/app-sPW-AjZE.js").read().decode("utf-8", "replace")

# paths after API base variable
paths = set()
for m in re.finditer(r"\$\{[a-zA-Z0-9_]{1,4}\}/([a-zA-Z0-9_/-]+)", t):
    paths.add("/" + m.group(1))

for prefix in ("admin", "metrics", "workspace", "ai", "stats", "alerts"):
    hits = sorted(p for p in paths if p.startswith("/" + prefix) or prefix in p)
    if hits:
        print(f"\n== {prefix} ==")
        for h in hits[:40]:
            print(h)

print("\n== HTTP error UI ==")
for m in re.finditer(r".{0,50}HTTP.{0,50}404.{0,30}", t):
    print(m.group()[:120])

for m in re.finditer(r"HTTP \$\{[a-zA-Z0-9_.]+\}", t):
    print("tpl:", m.group())
