#!/usr/bin/env python3
import re
from pathlib import Path

p = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\static\assets\app-BkUk1ts9.js")
s = p.read_text(encoding="utf-8", errors="ignore")

for term in ["minCountdown", "Fleet sleeping", "function Ds(", "sleeping:", "sleepingCount"]:
    idx = 0
    n = 0
    while n < 3:
        i = s.find(term, idx)
        if i < 0:
            break
        print(f"\n=== {term} @ {i} ===")
        print(s[max(0, i - 200) : i + 400])
        idx = i + len(term)
        n += 1

# find fleet object builder - search for minCountdown assignment
for m in re.finditer(r"minCountdown[^;]{0,300}", s):
    print("\n=== assign ===")
    print(m.group(0)[:300])
