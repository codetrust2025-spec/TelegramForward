"""Extract daily-ops slice from dashboard.bundle.js (helpers + kW + _W)."""
from __future__ import annotations

import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(REPO, "static", "assets", "dashboard.bundle.js")
OUT = os.path.join(REPO, "dashboard", "src", "dailyOps", "bundleSlice.js")


def find_function_body_start(js: str, sig: str) -> int | None:
    idx = js.find(sig)
    if idx < 0:
        return None
    # Walk from '(' after function name to matching ')' then '{'
    paren = js.find("(", idx)
    if paren < 0:
        return None
    depth = 0
    i = paren
    while i < len(js):
        ch = js[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                brace = js.find("{", i)
                return brace if brace >= 0 else None
        i += 1
    return None


def extract_function(js: str, sig: str) -> str | None:
    idx = js.find(sig)
    if idx < 0:
        return None
    body_start = find_function_body_start(js, sig)
    if body_start is None:
        return None
    depth = 0
    i = body_start
    while i < len(js):
        ch = js[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return js[idx : i + 1]
        i += 1
    return None


def main() -> None:
    js = open(BUNDLE, encoding="utf-8", errors="replace").read()

    kw_sig = "function kW("
    w_sig = "function _W("
    kw_idx = js.find(kw_sig)
    w_idx = js.find(w_sig)
    if kw_idx < 0 or w_idx < 0:
        print("kW or _W not found", file=sys.stderr)
        sys.exit(1)

    # Helpers block: from last export-like boundary before kW
    search_start = max(0, kw_idx - 150000)
    pre = js[search_start:kw_idx]
    # Start after previous major component (candidates panel ends ~ _Component35)
    markers = [
        pre.rfind("function _Component35("),
        pre.rfind("export function CandidatesPanel("),
        pre.rfind("function kx("),
        pre.rfind("function AdminPanel("),
        pre.rfind("function _Component36("),
    ]
    rel = max(m for m in markers if m >= 0) if any(m >= 0 for m in markers) else 0
    slice_start = search_start + rel if rel else search_start

    # End after _W function
    w_fn = extract_function(js, w_sig)
    if not w_fn:
        print("_W extract failed", file=sys.stderr)
        sys.exit(1)
    slice_end = js.find(w_sig) + len(w_fn)

    chunk = js[slice_start:slice_end]
    print(f"Slice: {slice_start}..{slice_end} ({len(chunk)} bytes)")

    kw_fn = extract_function(js, kw_sig)
    print(f"kW len: {len(kw_fn) if kw_fn else 0}")
    print(f"_W len: {len(w_fn)}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(chunk)
    print(f"Wrote {OUT}")

    # Also extract PN block
    pn = extract_function(js, "function PN(")
    print(f"PN len: {len(pn) if pn else 0}")

    # List function names in slice
    names = re.findall(r"function ([A-Za-z_$][\w$]*)\(", chunk)
    print(f"Functions in slice: {len(names)}")
    print(", ".join(sorted(set(names))[:60]))


if __name__ == "__main__":
    main()
