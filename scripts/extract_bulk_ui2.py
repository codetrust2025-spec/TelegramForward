#!/usr/bin/env python3
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\static\assets\app-BkUk1ts9.js").read_text(encoding="utf-8", errors="ignore")

# find all setup-column-panel conditions
for m in re.finditer(r'setup-column-panel\$\{xt==="(\w+)"', s):
    print("panel tab:", m.group(1))

i = s.find('xt==="fleet"')
print("\n=== fleet/bulk panel ===")
print(s[i:i+1200])

i2 = s.find("panel--message")
# find parent context - search backwards for setup tab
idx = s.find("panel--message")
while idx > 0:
    chunk = s[max(0,idx-2000):idx]
    if "setup-column" in chunk or "xt===" in chunk:
        print("\n=== message panel context ===")
        print(chunk[-800:])
        break
    idx = s.rfind("panel--message", 0, idx)
