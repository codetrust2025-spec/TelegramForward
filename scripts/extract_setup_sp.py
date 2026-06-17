#!/usr/bin/env python3
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s = Path(r"C:\Users\codet\OneDrive\Desktop\Automation\static\assets\app-BkUk1ts9.js").read_text(encoding="utf-8", errors="ignore")

# find accountFilter / le state - search AR array usage
i = s.find('AR=[{value:Rt,label:"Forward"')
print(s[i:i+500])

# sp component - setup per account - message editor?
i = s.find("function sp(")
print("\n=== sp setup panel ===")
print(s[i:i+2500][:2500])
