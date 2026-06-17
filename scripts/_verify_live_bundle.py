import urllib.request

needles = [
    "Works pending", "PendingWorksProvider", "daily-ops", "Daily ops",
    "cand-workspace", "Add prompt", "dr-vault-actions", "pending-works-strip", "ops-dashboard",
]
js = urllib.request.urlopen("https://teleautomation.online/assets/app-CQX6ikmo.js", timeout=60).read().decode("utf-8", "replace")
print("live bundle bytes:", len(js))
for n in needles:
    print(f"  {n!r}: {'OK' if n in js else 'MISSING'}")
html = urllib.request.urlopen("https://teleautomation.online/", timeout=30).read().decode("utf-8", "replace")
import re
print("active:", re.findall(r"/assets/[^\"']+", html))
