#!/usr/bin/env python3
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\static\assets\app-BkUk1ts9.js").read_text(encoding="utf-8", errors="ignore")

# find Rt = forwarding constant
for m in re.finditer(r'Rt="(\w+)"|const Rt=', s):
    print(m.group(0)[:80], "at", m.start())

# more context on fleet defaults - campaign branch
i = s.find("Default campaign message")
print("\n=== campaign message block ===")
print(s[i-400:i+900])

# workspace mode filter labels
for term in ["Forwarding", "Campaign", "workspaceMode", "accountFilter", "modes"]:
    if term in s[s.find("fleet-defaults"):s.find("fleet-defaults")+5000]:
        pass
i = s.find("function ap(")
print("\n=== ap component (fleet defaults) ===")
print(s[i:i+400])
