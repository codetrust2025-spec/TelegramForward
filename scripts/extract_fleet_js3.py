#!/usr/bin/env python3
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\static\assets\app-BkUk1ts9.js").read_text(encoding="utf-8", errors="ignore")

for term in ["function Us(", "sleeping", "status===\"sleeping\""]:
    i = s.find(term)
    if i >= 0:
        print(f"\n=== {term} @ {i} ===")
        print(s[i:i+1200][:1200])

# get full Ds
m = re.search(r"function Ds\(e\)\{[^}]+\}[^}]*\}", s)
if m:
    print("\n=== Ds full ===")
    print(m.group(0)[:400])
