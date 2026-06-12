#!/usr/bin/env python3
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\static\assets\app-BkUk1ts9.js").read_text(encoding="utf-8", errors="ignore")

# find fleet panel block
start = s.find("fleet-defaults-panel")
print("=== fleet defaults (start) ===")
print(s[start-500:start+2000])

# find where xt===fleet panel is rendered
for needle in ['xt==="fleet"', "value===\"fleet\"", 'hidden:xt!=="fleet"']:
    i = s.find(needle)
    if i >= 0:
        print(f"\n=== {needle} ===")
        print(s[i:i+800])
