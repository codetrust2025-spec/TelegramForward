import urllib.request

js = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-sjsEbgmN.js", timeout=30
).read().decode("utf-8", "replace")

for label in ["Pending collections", "Pending only", "cand-stat-card--clickable", "onPending"]:
    idx = js.find(label)
    print(f"\n=== {label} @ {idx} ===")
    if idx >= 0:
        chunk = js[max(0, idx - 500) : idx + 800]
        print(chunk.encode("ascii", "replace").decode())
