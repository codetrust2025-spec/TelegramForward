"""Extract daily-ops related slices from dashboard.bundle.js into Vite modules."""
from __future__ import annotations

import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(REPO, "static", "assets", "dashboard.bundle.js")
OUT_DIR = os.path.join(REPO, "dashboard", "src", "dailyOps")

# Minified function names in bundle -> readable export names
FUNCTION_MAP = {
    "function kW(": "function InterviewRoster(",
    "function _W(": "function DailyOpsPanel(",
    "function PN(": "export function PendingWorksProvider(",
    "function cY(": "export function usePendingWorksContext(",
    "function uB(": "export function usePendingWorksContextOptional(",
}


def extract_function(js: str, signature: str) -> tuple[str, int, int] | None:
    idx = js.find(signature)
    if idx < 0:
        return None
    # find opening brace of function body
    brace = js.find("{", idx)
    if brace < 0:
        return None
    depth = 0
    i = brace
    while i < len(js):
        ch = js[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return js[idx : i + 1], idx, i + 1
        i += 1
    return None


def find_all_function_starts(js: str, names: list[str]) -> dict[str, int]:
    out = {}
    for name in names:
        for pat in (f"function {name}(", f"function {name} ("):
            idx = js.find(pat)
            if idx >= 0:
                out[name] = idx
                break
    return out


def main() -> None:
    if not os.path.isfile(BUNDLE):
        print(f"Missing {BUNDLE}", file=sys.stderr)
        sys.exit(1)

    js = open(BUNDLE, encoding="utf-8", errors="replace").read()
    print(f"Bundle size: {len(js)}")

    # Core components
    targets = [
        "function kW(",
        "function _W(",
        "function PN(",
        "function cY(",
        "function uB(",
    ]
    extracted: dict[str, str] = {}
    for sig in targets:
        res = extract_function(js, sig)
        if res:
            chunk, start, end = res
            extracted[sig] = chunk
            print(f"OK {sig} len={len(chunk)} at {start}")
        else:
            print(f"MISSING {sig}")

    # Find helper functions referenced by kW - search backwards from kW for nearby defs
    helper_names = [
        "xI", "vce", "Lk", "ice", "vw", "Gb", "bb", "Vm", "rI", "yW", "bW", "xce",
        "hce", "tce", "jce", "vW", "kce", "_ce", "W$", "Ace", "dce", "ej", "Jle",
        "Uoe", "kI", "O0", "yI", "vI", "xw", "RT", "rY", "tY", "L0", "Vb", "O0",
        "nW", "sW", "iW", "lW", "cW", "uW", "fW", "dW", "hW", "pW", "mW", "gW",
        "oce", "lce", "jce", "kce", "vce", "yce", "wce", "xce", "zce", "Bce",
    ]
    # Scan for ops-slot-modal and related slot modal
    for pat in ["ops-slot-modal", "function nW(", "function ej(", "const L0="]:
        idx = js.find(pat)
        print(f"  {pat!r}: {idx}")

    # Extract a window before kW containing helper functions
    kw_idx = js.find("function kW(")
    if kw_idx >= 0:
        window_start = max(0, kw_idx - 120000)
        window = js[window_start:kw_idx]
        # find all function XX( in window
        funcs_in_window = re.findall(r"function ([A-Za-z_$][\w$]*)\(", window)
        print(f"\nFunctions in 120KB before kW: {len(funcs_in_window)}")
        unique = sorted(set(funcs_in_window))
        print(", ".join(unique[:80]))

    os.makedirs(OUT_DIR, exist_ok=True)
    raw_path = os.path.join(OUT_DIR, "_extracted_raw.js")
    with open(raw_path, "w", encoding="utf-8", newline="\n") as f:
        for sig, chunk in extracted.items():
            f.write(f"\n/* === {sig} === */\n")
            f.write(chunk)
            f.write("\n")
    print(f"\nWrote raw extract to {raw_path}")


if __name__ == "__main__":
    main()
