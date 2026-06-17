#!/usr/bin/env python3
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

s = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\static\assets\app-BkUk1ts9.js").read_text(encoding="utf-8", errors="ignore")

# fleet builder around minCountdown
i = s.find("minCountdown:w??0")
chunk = s[i - 2500 : i + 500]
print("=== FLEET BUILDER ===")
print(chunk)

# Ds formatter
for m in re.finditer(r"function Ds\([^)]*\)\{[^}]+\}", s):
    print("\n=== Ds ===")
    print(m.group(0))

# Forwarding performance panel
i2 = s.find("Fleet sleeping")
print("\n=== PANEL ===")
print(s[i2 - 800 : i2 + 200])

# search w= min countdown logic
for pat in [r"let w=", r"w=Math", r"minCountdown", r"next_cycle_in"]:
    for m in re.finditer(pat + r".{0,80}", chunk):
        print("hit:", m.group(0)[:120])
