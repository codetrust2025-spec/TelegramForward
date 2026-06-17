"""Minimal Me->N alias fix for daily ops extract (no API stripping)."""
from pathlib import Path
import re

p = Path(__file__).resolve().parents[1] / "dashboard/src/dailyOps/dailyOpsModule.core.jsx"
t = p.read_text(encoding="utf-8")
t = re.sub(r"const Me=Wi,ia=\{Fragment:Wi\.Fragment\},Woe=typeof window[^;]+;", "", t)
for hook in ("useState", "useEffect", "useMemo", "useCallback", "useRef", "useContext"):
    t = t.replace(f"Me.{hook}", f"N.{hook}")
p.write_text(t, encoding="utf-8")
print("Patched Me aliases in", p)
