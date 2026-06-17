import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _extract_daily_ops_slice import extract_function

js = pathlib.Path(__file__).resolve().parents[1] / "static/assets/dashboard.bundle.js"
js = js.read_text(encoding="utf-8", errors="replace")

patterns = [
    "const TS=", "function tY(", "function rY(", "function PN(", "function lY(",
    "function iY(", "function cB(", "aY=", "eY=", "Zx=", "sY=", "function G$(",
    "function OT(", "function Po(", "L0=[", "function kW(", "function _W(",
    "function Wce(", "function BT(",
]
for pat in patterns:
    i = js.find(pat)
    print(f"{pat:25} {i}")
