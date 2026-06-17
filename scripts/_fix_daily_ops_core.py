"""Fix duplicate symbols and broken API strips in extracted daily ops module."""
from __future__ import annotations

import re
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "dashboard/src/dailyOps/dailyOpsModule.core.jsx"
t = p.read_text(encoding="utf-8")

# Repair broken partial API strips from the extractor.
t = t.replace('}//${window.location.protocol}//${window.location.host}`:"";', "")
t = t.replace("}//${window.location.host}`:\"\";", "")
t = re.sub(r'\}\/\/\$\{window\.location\.host\}`:"";', "", t)

# Remove embedded dev API bootstrap from pending-works slice.
t = re.sub(
    r'const nY=typeof window<"u"&&window\.location\.port==="3000",'
    r'aY=nY\?"":typeof window<"u"\?\$\{window\.location\.protocol\}//\$\{window\.location\.host\}`:"";',
    "",
    t,
    count=1,
)
t = t.replace("${window.location.protocolfunction sY()", "function sY()")

# Drop accidental Vite bootstrap injected into the daily-ops slice.
t = re.sub(
    r"const Me=Wi,ia=\{Fragment:Wi\.Fragment\},Woe=typeof window[^;]+;",
    "",
    t,
)
t = re.sub(r"const yce=typeof window[^;]+;", "", t)
t = re.sub(r"const zce=typeof window[^;]+;", "", t)
t = re.sub(r"Zx=zce\?[^;]+;", "", t)
t = re.sub(r"Xo=yce\?[^;]+;", "", t)
t = re.sub(r",Xo=yce\?[^;]+;", ",", t)
t = re.sub(
    r'sn=Woe\?"":typeof window<"u"\?\$\{window\.location\.protocol\}//\$\{window\.location\.host\}`:"";',
    "",
    t,
)
t = re.sub(
    r'sn=[^;]*window\.location\.protocol[^;]*;',
    "",
    t,
)

# Monolith React alias -> our header alias.
for name in ("useState", "useEffect", "useMemo", "useCallback", "useRef", "useContext"):
    t = t.replace(f"Me.{name}", f"N.{name}")

# Header should not duplicate runtime aliases.
for line in (
    "const Me = React\n",
    "const Xo = API\n",
    "const Zx = API\n",
    "const sn = API\n",
    "const zce = false\n",
):
    t = t.replace(line, "")

if "const aY = API" not in t:
    t = t.replace(
        "const eY = API\n",
        "const eY = API\nconst aY = API\nconst nY = false\nconst Xo = API\nconst Zx = API\nconst sn = API\n",
        1,
    )

p.write_text(t, encoding="utf-8")
print("Fixed", p)
