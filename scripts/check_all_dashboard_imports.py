#!/usr/bin/env python3
import re
from pathlib import Path

root = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\dashboard\src")
pat = re.compile(r"from ['\"](\.[^'\"]+)['\"]")
missing = set()
for f in root.rglob("*"):
    if f.suffix not in {".jsx", ".js"}:
        continue
    text = f.read_text(encoding="utf-8", errors="replace")
    for rel in pat.findall(text):
        if not rel.startswith("."):
            continue
        target = (f.parent / rel).resolve()
        ok = target.exists() or (target.with_suffix(".jsx")).exists() or (target.with_suffix(".js")).exists()
        if not ok:
            missing.add(str(target.relative_to(root.parent)))
print("missing", len(missing))
for m in sorted(missing):
    print(m)
