import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _extract_daily_ops_slice import extract_function

js = pathlib.Path(__file__).resolve().parents[1] / "static/assets/dashboard.bundle.js"
js = js.read_text(encoding="utf-8", errors="replace")

names = ["BT", "Wce", "kW", "_W", "rY", "tY", "PN", "nW", "ej"]
for n in names:
    sig = f"function {n}("
    i = js.find(sig)
    if i < 0:
        print(n, "NOT FOUND")
        continue
    fn = extract_function(js, sig)
    print(f"{n}: idx={i}, len={len(fn) if fn else 0}")

# L0 array
for pat in ["L0=[", "L0 = [", 'L0=["']:
    i = js.find(pat)
    if i >= 0:
        print(f"L0 at {i}: {js[i:i+200]}")
        break
