#!/usr/bin/env python3
import re
from pathlib import Path

root = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\dashboard\src")
app = (root / "App.jsx").read_text(encoding="utf-8")
imports = re.findall(r"from '\./([^']+)'", app)
missing = [imp for imp in imports if not (root / imp).exists()]
print("missing", len(missing))
for m in missing:
    print(m)
