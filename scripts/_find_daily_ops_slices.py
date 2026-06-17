"""Find correct daily ops slice boundaries in monolith bundle."""
from __future__ import annotations

from pathlib import Path

js = Path("static/assets/dashboard.bundle.js").read_text(encoding="utf-8")

patterns = [
    "L0=[",
    "const ww=",
    "function Bk(",
    "function kW(",
    "function _W(",
    "function lY(",
    "function oY(",
    "function iY(",
    "function cB(",
]
for pat in patterns:
    i = js.find(pat)
    print(f"{pat}: {i}")

pos = js.find("function _W(")
depth = 0
started = False
end = None
for i in range(pos, min(pos + 120000, len(js))):
    ch = js[i]
    if ch == "{":
        depth += 1
        started = True
    elif ch == "}":
        depth -= 1
        if started and depth == 0:
            end = i + 1
            break

print(f"_W start {pos} end {end} len {end - pos if end else None}")
if end:
    print("after _W:", repr(js[end : end + 120]))

# slice1: fix end after uB
uB = js.find("function uB(){return N.useContext(TS)}")
print(f"uB block at {uB}, end {uB + len('function uB(){return N.useContext(TS)}')}")

# pending works start
for pat in ["function PN(", "function eY="]:
    print(pat, js.find(pat))

# kW end
pos = js.find("function kW(")
depth = 0
started = False
kend = None
for i in range(pos, min(pos + 200000, len(js))):
    ch = js[i]
    if ch == "{":
        depth += 1
        started = True
    elif ch == "}":
        depth -= 1
        if started and depth == 0:
            kend = i + 1
            break
print(f"kW start {pos} end {kend} len {kend - pos if kend else None}")
