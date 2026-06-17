import pathlib
import re

js_path = pathlib.Path(__file__).resolve().parents[1] / "static/assets/dashboard.bundle.js"
js = js_path.read_text(encoding="utf-8", errors="replace")
print("size", len(js))
needles = [
    "Daily ops", "daily-ops", "Works pending", "cand-workspace",
    "Add prompt", "dr-vault-actions", "Pending only", 'id:"daily"',
]
for n in needles:
    print(repr(n), "OK" if n in js else "MISSING", js.count(n))

idx = js.find('id:"daily",label:"Daily ops"')
print("\ntab idx", idx)
if idx >= 0:
    print(js[idx - 100 : idx + 200])

# Find daily tab render block
for pat in [r'o==="daily"', r'u==="daily"', r'c==="daily"']:
    m = re.search(pat, js)
    if m:
        print(f"\nrender match {pat} at {m.start()}")
        print(js[m.start() : m.start() + 8000][:8000])

# daily-ops CSS class
idx2 = js.find("daily-ops")
print("\ndaily-ops at", idx2)
if idx2 >= 0:
    print(js[max(0, idx2 - 100) : idx2 + 500])
