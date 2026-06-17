"""Build dailyOpsModule.core.js from monolith bundle slices."""
from __future__ import annotations

import os
import re
import shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(REPO, "static", "assets", "dashboard.bundle.js")
OUT_JS = os.path.join(REPO, "dashboard", "src", "dailyOps", "dailyOpsModule.core.js")
OUT_JSX = os.path.join(REPO, "dashboard", "src", "dailyOps", "dailyOpsModule.core.jsx")

# PendingWorksProvider + context
SLICE1_START = 146547
SLICE1_END = 149961

# L1 (flood-wait helper) + vt (account slot label)
SLICE_VT_START = 150880
SLICE_VT_END = 151145  # ends after function vt(){…}; 151150 cut mid-word "function"

# Candidate stats/export helpers + payout UI deps (cP, uP, O0, D_, hee, th, fP, Y5, …)
SLICE0_START = 325949  # const YQ=… through g2/lP/JQ/ZQ/eee
SLICE0_END = 340410

# Resume preview helpers (Foe, CT, qoe, sI, Ioe, …) immediately before daily ops UI
QOE_START = 2563478  # function Foe (PDF width probe)
QOE_END = 2568495    # stops before const L0=

# Daily ops UI: Wce, BT, _W, …
SLICE2_START = 2568495
SLICE2_END = 2821602

HEADER = r'''/**
 * Daily ops + PendingWorks — extracted from dashboard.bundle.js (monolith).
 * Do not edit by hand; regenerate via scripts/_build_daily_ops_module.py
 */
import React from 'react'
import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from 'react/jsx-runtime'
import { useAuth } from '../context/AuthContext.jsx'
import { API } from '../config.js'

const N = React
const o = { jsx: _jsx, jsxs: _jsxs, Fragment: _Fragment }
const xc = useAuth
const aY = API
const nY = false
const eY = API
const Xo = API
const Zx = API
const sn = API
const We = API
const Go = API
const Kx = API
const zce = false

'''

FOOTER = r'''
export {
  PN as PendingWorksProvider,
  cY as usePendingWorksContext,
  uB as usePendingWorksContextOptional,
  _W as DailyOpsPanel,
  kW as InterviewRoster,
  lY as navigatePendingWorkToCandidates,
  cB as markCandidatesPendingWorksFilter,
  oY as consumePendingWorkOpenIntent,
  iY as stashPendingWorkOpenIntent,
}
'''


def strip_slice1_prefix(chunk: str) -> str:
    chunk = re.sub(r"^eY=[^;]+;", "", chunk, count=1)
    chunk = chunk.replace(
        'const nY=typeof window<"u"&&window.location.port==="3000",'
        'aY=nY?"":typeof window<"u"?`${window.location.protocol}//${window.location.host}`:"";',
        "",
    )
    return chunk


def strip_slice2_bootstrap(chunk: str) -> str:
    chunk = chunk.replace(
        'const Me=Wi,ia={Fragment:Wi.Fragment},Woe=typeof window<"u"&&window.location.port==="3000",'
        'sn=Woe?"":typeof window<"u"?`${window.location.protocol}//${window.location.host}`:"",',
        "const ",
    )
    chunk = chunk.replace(
        'const yce=typeof window<"u"&&window.location.port==="3000",'
        'Xo=yce?"":typeof window<"u"?`${window.location.protocol}//${window.location.host}`:"";',
        "",
    )
    chunk = chunk.replace(
        'const zce=typeof window<"u"&&window.location.port==="3000",'
        'Zx=zce?"":typeof window<"u"?`${window.location.protocol}//${window.location.host}`:"";',
        "",
    )
    for hook in ("useState", "useEffect", "useMemo", "useCallback", "useRef", "useContext"):
        chunk = chunk.replace(f"Me.{hook}", f"N.{hook}")
    chunk = chunk.replace(
        'const da=Wi,yA={Fragment:Wi.Fragment},Tce=typeof window<"u"&&window.location.port==="3000",'
        'Go=Tce?"":typeof window<"u"?`${window.location.protocol}//${window.location.host}`:"";',
        "const da=N,yA={Fragment:N.Fragment};",
    )
    chunk = chunk.replace(
        'const Ice=typeof window<"u"&&window.location.port==="3000",'
        'Kx=Ice?"":typeof window<"u"?`${window.location.protocol}//${window.location.host}`:"";',
        "",
    )
    return chunk


def main() -> None:
    js = open(BUNDLE, encoding="utf-8", errors="replace").read()
    slice1 = strip_slice1_prefix(js[SLICE1_START:SLICE1_END])
    slice_vt = js[SLICE_VT_START:SLICE_VT_END]
    slice0 = js[SLICE0_START:SLICE0_END]
    qoe = js[QOE_START:QOE_END]
    slice2 = strip_slice2_bootstrap(js[SLICE2_START:SLICE2_END])

    os.makedirs(os.path.dirname(OUT_JS), exist_ok=True)
    with open(OUT_JS, "w", encoding="utf-8", newline="\n") as f:
        f.write(HEADER)
        f.write("\n/* --- pending works provider --- */\n")
        f.write(slice1)
        f.write("\n\n/* --- account / flood-wait helpers --- */\n")
        f.write(slice_vt)
        f.write("\n\n/* --- candidate stats / payout deps --- */\n")
        f.write(slice0)
        f.write("\n\n/* --- resume preview helpers --- */\n")
        f.write(qoe)
        f.write("\n\n/* --- daily ops UI --- */\n")
        f.write(slice2)
        f.write("\n")
        f.write(FOOTER)

    shutil.copyfile(OUT_JS, OUT_JSX)
    print(f"Wrote {OUT_JS} ({os.path.getsize(OUT_JS)} bytes)")
    print(f"Copied to {OUT_JSX}")


if __name__ == "__main__":
    main()
